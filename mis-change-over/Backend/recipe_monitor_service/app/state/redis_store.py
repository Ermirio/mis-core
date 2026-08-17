"""
Redis store: estado em tempo real + canal pub/sub.

Layout das chaves (todas no DB do REDIS_URL):

  linha:{nome}:atual                HASH    {variavel_id: JSON-encoded value}
  linha:{nome}:ts                   HASH    {variavel_id: timestamp_ms}
  linha:{nome}:hist:{variavel_id}   LIST    JSON-encoded HistoricoPonto (LPUSH+LTRIM)
  linha:{nome}:opc_online           STRING  "1" com TTL (refresh a cada datachange)

Canal pub/sub:

  linha:{nome}:updates              JSON: {"variavel_id": int, "valor": ...,
                                           "timestamp_ms": int, "status": "..."}
  linha:{nome}:opc_status           JSON: {"online": bool, "timestamp_ms": int}

Notas:
  - Valores são serializados como JSON. BOOL/STRING/REAL/INT viram tipos
    JSON nativos. Recuperação faz `json.loads` direto.
  - O TTL em `opc_online` é o sinal de saúde: se o subscription handler
    parar de receber datachanges, a chave expira e marcamos a linha offline.
  - O histórico circular vive em LIST (cap = HISTORY_MAX_POINTS). LPUSH
    insere mais novo no head; o frontend reverte se quiser ordem temporal.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Optional

from redis import asyncio as aioredis

from ..config import get_settings
from ..schemas import HistoricoPonto

logger = logging.getLogger(__name__)

# ── TTL em segundos para a chave 'opc_online'.
#    Refrescada por DUAS vias:
#      1. A cada datachange (record_datachange) — quando algum valor muda
#      2. A cada ciclo do healthcheck do pool (a cada ~10s) — mesmo sem datachange
#    O TTL precisa ser > 2× HEALTHCHECK_INTERVAL_S (=10s) com folga para tolerar
#    1 healthcheck perdido sem o frontend piscar como offline em linha parada.
OPC_ONLINE_TTL_S = 35


# ╔════════════════════════════════════════════════════════════════════╗
# ║ Key builders                                                       ║
# ╚════════════════════════════════════════════════════════════════════╝

def k_atual(linha: str) -> str:           return f"linha:{linha}:atual"
def k_ts(linha: str) -> str:              return f"linha:{linha}:ts"
def k_hist(linha: str, var_id: int) -> str:   return f"linha:{linha}:hist:{var_id}"
def k_online(linha: str) -> str:          return f"linha:{linha}:opc_online"
def ch_updates(linha: str) -> str:        return f"linha:{linha}:updates"
def ch_opc_status(linha: str) -> str:     return f"linha:{linha}:opc_status"


# ╔════════════════════════════════════════════════════════════════════╗
# ║ Store                                                              ║
# ╚════════════════════════════════════════════════════════════════════╝

class RedisStore:
    """
    Wrapper async sobre redis-py. Mantém um cliente para comandos comuns
    e cria PubSub sob demanda em subscribe_updates / subscribe_opc_status.
    """

    def __init__(self, redis_url: str, history_max_points: int):
        self._url = redis_url
        self._history_max = history_max_points
        self._redis: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Ping com timeout para falhar cedo se Redis não está disponível.
            try:
                await asyncio.wait_for(self._redis.ping(), timeout=3)
            except Exception:
                # Não derruba o serviço aqui — o startup pode prosseguir e
                # o reader OPC vai logar falhas até o Redis voltar.
                logger.warning("Redis indisponível em %s — seguiremos tentando", self._url)

    async def aclose(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None

    @property
    def client(self) -> aioredis.Redis:
        if self._redis is None:
            raise RuntimeError("RedisStore not connected — call connect() first.")
        return self._redis

    # ── Escrita ──────────────────────────────────────────────────────

    async def record_datachange(
        self,
        *,
        linha: str,
        variavel_id: int,
        valor: Any,
        timestamp_ms: int,
        publish_status: str,
    ) -> None:
        """
        Grava um datachange e publica. Tudo em pipeline para um único RTT.

        publish_status é o resultado de classifier.classificar() — vai junto
        no canal pub/sub para que o WS não precise re-classificar.
        """
        ponto = HistoricoPonto(t=timestamp_ms, valor=valor).model_dump()
        ponto_json = json.dumps(ponto, default=_json_default)
        valor_json = json.dumps(valor, default=_json_default)

        pipe = self.client.pipeline()
        pipe.hset(k_atual(linha), str(variavel_id), valor_json)
        pipe.hset(k_ts(linha), str(variavel_id), str(timestamp_ms))
        pipe.lpush(k_hist(linha, variavel_id), ponto_json)
        pipe.ltrim(k_hist(linha, variavel_id), 0, self._history_max - 1)
        pipe.set(k_online(linha), "1", ex=OPC_ONLINE_TTL_S)
        pipe.publish(
            ch_updates(linha),
            json.dumps({
                "tipo": "update",
                "linha": linha,
                "variavel_id": variavel_id,
                "valor": valor,
                "timestamp_ms": timestamp_ms,
                "status": publish_status,
            }, default=_json_default),
        )
        await pipe.execute()

    async def mark_opc_status(self, *, linha: str, online: bool) -> None:
        """
        Sinaliza explicitamente queda/restabelecimento da conexão OPC.
        Chamado pelo line_manager em eventos de connect/disconnect/reconnect.
        """
        timestamp_ms = int(time.time() * 1000)
        if online:
            await self.client.set(k_online(linha), "1", ex=OPC_ONLINE_TTL_S)
        else:
            await self.client.delete(k_online(linha))
        await self.client.publish(
            ch_opc_status(linha),
            json.dumps({
                "tipo": "opc_status",
                "linha": linha,
                "online": online,
                "timestamp_ms": timestamp_ms,
            }),
        )

    # ── Leitura ──────────────────────────────────────────────────────

    async def is_opc_online(self, linha: str) -> bool:
        v = await self.client.get(k_online(linha))
        return v == "1"

    async def get_snapshot_atual(self, linha: str) -> dict[int, Any]:
        """Retorna {variavel_id: valor} (decodificado de JSON)."""
        raw = await self.client.hgetall(k_atual(linha))
        return {int(k): json.loads(v) for k, v in raw.items()}

    async def get_snapshot_ts(self, linha: str) -> dict[int, int]:
        """Retorna {variavel_id: timestamp_ms}."""
        raw = await self.client.hgetall(k_ts(linha))
        return {int(k): int(v) for k, v in raw.items()}

    async def get_historico(
        self, linha: str, variavel_id: int, *, limit: Optional[int] = None
    ) -> list[HistoricoPonto]:
        """
        Retorna histórico em ORDEM CRONOLÓGICA (mais antigo → mais novo),
        adequado para plotar em gráfico linha-do-tempo direto.

        Como armazenamos com LPUSH (mais recente no head), revertemos aqui
        para que o frontend receba pronto. Updates via WS sao appendados ao
        final pelo cliente, mantendo a ordem.
        """
        limit = limit or self._history_max
        raw = await self.client.lrange(k_hist(linha, variavel_id), 0, limit - 1)
        pontos = [HistoricoPonto.model_validate(json.loads(s)) for s in raw]
        # LPUSH ordem: [newest, ..., oldest] → reverter → [oldest, ..., newest]
        pontos.reverse()
        return pontos

    # ── Pub/Sub ──────────────────────────────────────────────────────

    async def subscribe_line(self, linha: str) -> AsyncIterator[dict]:
        """
        Gerador async que entrega mensagens dos canais de uma linha
        (updates + opc_status) como dicts já parsed. Quem chama é
        responsável por fechar o gerador (ex.: WS disconnect).
        """
        pubsub = self.client.pubsub()
        await pubsub.subscribe(ch_updates(linha), ch_opc_status(linha))
        try:
            async for msg in pubsub.listen():
                if msg is None:
                    continue
                if msg.get("type") != "message":
                    continue
                data = msg.get("data")
                if not data:
                    continue
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    logger.warning("Mensagem mal-formada no canal %s: %r",
                                   msg.get("channel"), data)
        finally:
            try:
                await pubsub.unsubscribe(ch_updates(linha), ch_opc_status(linha))
                await pubsub.aclose()
            except Exception:
                pass


# ── Helpers ───────────────────────────────────────────────────────────

def _json_default(o: Any) -> Any:
    """Fallback de serialização para tipos que o json não conhece."""
    # asyncua entrega alguns valores como bytes ou tipos numpy/datetime;
    # convertemos para algo serializável de forma segura.
    if isinstance(o, (bytes, bytearray)):
        try:
            return o.decode("utf-8", errors="replace")
        except Exception:
            return repr(o)
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


# ── Singleton ─────────────────────────────────────────────────────────

_store: RedisStore | None = None


def get_redis_store() -> RedisStore:
    global _store
    if _store is None:
        settings = get_settings()
        _store = RedisStore(
            redis_url=settings.redis_url,
            history_max_points=settings.history_max_points,
        )
    return _store


async def close_redis_store() -> None:
    global _store
    if _store is not None:
        await _store.aclose()
        _store = None
