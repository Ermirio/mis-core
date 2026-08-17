"""
SubscriptionHandler ligado ao Redis store.

Cada linha tem UMA subscription (eventualmente em UM servidor OPC, ou
distribuída entre vários se os equipamentos da linha apontam para CLPs
distintos). Os `MonitoredItems` são criados pelo `line_manager`.

Quando o servidor OPC empurra `datachange_notification`, este handler:
  1. Converte o valor cru → tipo Python via `opc_to_python`
  2. Classifica (precisa receita do Django + tolerância do Variavel)
  3. Grava em Redis (atual + histórico) e publica no canal pub/sub

Como NÃO conhecemos a receita aqui (ela depende do formato escolhido
pelo operador, e isso é UI-side), publicamos apenas o valor + status
'normal'/'semleitura' baseado em **presença** de leitura. A
classificação final contra a receita é feita no `rest.py /snapshot`
ou no frontend, que junta valor + receita do formato selecionado.

ISSO É IMPORTANTE: o status que vai no canal WS é "tem leitura ou não".
"normal" aqui significa "leitura OK, sem opinião sobre receita".
"""
from __future__ import annotations

import logging
import time
from typing import Any

from asyncua.common.subscription import SubscriptionItemData

from ..state.redis_store import RedisStore
from .conversion import opc_to_python

logger = logging.getLogger(__name__)


class LineSubscriptionHandler:
    """
    Handler asyncua. UM por linha (não por servidor — para que ts/Redis
    estejam organizados por linha).

    O `node_to_var` mapeia o NodeId (string) recebido em datachange ao
    tuple (variavel_id, tipo_db) que precisamos.
    """

    # Sentinela para "ainda não vi nenhum valor desta variável".
    _NUNCA_VISTO = object()

    def __init__(
        self,
        *,
        linha: str,
        redis_store: RedisStore,
        node_to_var: dict[str, tuple[int, str]],
    ):
        self.linha = linha
        self.redis = redis_store
        self.node_to_var = node_to_var
        # Último valor gravado por variavel_id (filtro change-of-value).
        # Evita registrar pontos redundantes quando o servidor OPC reenvia
        # o mesmo valor (keep-alive, reconexão, ruído de float).
        self._last_values: dict[int, Any] = {}
        # Deadband para REAL: mudanças <= esse valor são tratadas como "sem
        # mudança". 0.0 = só filtra valores exatamente iguais. Aumente se
        # houver ruído analógico (ex.: 0.01).
        from ..config import get_settings
        self._deadband_real = get_settings().cov_deadband_real

    # asyncua chama este método de forma sync (não async) — ver docs.
    # Internamente, ele agenda na loop do client. Para gravar no Redis,
    # precisamos enfileirar uma task async.
    def datachange_notification(self, node, val: Any, data: SubscriptionItemData) -> None:
        import asyncio

        node_id_str = node.nodeid.to_string()
        mapping = self.node_to_var.get(node_id_str)
        if mapping is None:
            # Pode acontecer se um node foi adicionado depois e o map ficou stale.
            logger.debug("[%s] datachange p/ node desconhecido: %s", self.linha, node_id_str)
            return

        variavel_id, tipo_db = mapping
        valor = opc_to_python(tipo_db, val)

        # ── Filtro Change-of-Value ────────────────────────────────────────
        # Só registra/publica se o valor REALMENTE mudou desde o último ponto.
        # Evita pontos redundantes quando o servidor OPC reenvia o mesmo valor
        # (keep-alive, reconexão da subscription, ruído de float). É o
        # comportamento desejado: o gráfico mostra só mudanças reais.
        anterior = self._last_values.get(variavel_id, self._NUNCA_VISTO)
        if not self._mudou(tipo_db, valor, anterior):
            # Valor inalterado: não grava ponto novo. Apenas refresca o sinal
            # de "OPC online" para a linha não piscar offline numa variável estável.
            loop = asyncio.get_event_loop()
            loop.create_task(
                self.redis.mark_opc_status(linha=self.linha, online=True),
                name=f"opc-alive:{self.linha}:{variavel_id}",
            )
            return

        self._last_values[variavel_id] = valor

        # Usa SEMPRE o tempo de recepção no container (UTC, epoch consistente).
        # NÃO usamos o ServerTimestamp/SourceTimestamp do CLP porque:
        #   1. Relógios de CLP em chão de fábrica costumam estar dessincronizados.
        #   2. Misturar fontes (alguns pontos do CLP, outros do container) gera
        #      saltos no gráfico após o sort por timestamp.
        # Para um monitor AO VIVO, "quando recebemos a leitura" é o que importa
        # e garante todos os pontos no mesmo relógio. _server_ts_ms fica
        # disponível para uso futuro, mas não é mais a fonte primária.
        ts_ms = int(time.time() * 1000)

        # Status simplificado (ver docstring do módulo)
        status = "normal" if valor is not None else "semleitura"

        # Agendamos sem await — a callback do asyncua é sync.
        loop = asyncio.get_event_loop()
        loop.create_task(
            self._record(variavel_id=variavel_id, valor=valor, ts_ms=ts_ms, status=status),
            name=f"redis-write:{self.linha}:{variavel_id}",
        )

    def _mudou(self, tipo_db: str, novo: Any, anterior: Any) -> bool:
        """
        True se `novo` deve ser considerado uma mudança real em relação a
        `anterior`. Comparação exata para tipos discretos; deadband para REAL.
        """
        if anterior is self._NUNCA_VISTO:
            return True  # primeiro valor desta variável sempre registra
        # None ↔ valor é sempre mudança (ex.: leitura voltou ou caiu)
        if novo is None or anterior is None:
            return novo is not anterior
        if (tipo_db or "").upper() == "REAL":
            try:
                return abs(float(novo) - float(anterior)) > self._deadband_real
            except (TypeError, ValueError):
                return novo != anterior
        # BOOL / STRING / DINT / UDINT / INT / UINT → comparação exata
        return novo != anterior

    async def _record(self, *, variavel_id: int, valor: Any, ts_ms: int, status: str) -> None:
        try:
            await self.redis.record_datachange(
                linha=self.linha,
                variavel_id=variavel_id,
                valor=valor,
                timestamp_ms=ts_ms,
                publish_status=status,
            )
        except Exception:
            logger.exception("[%s] falha ao gravar datachange var=%s no Redis",
                             self.linha, variavel_id)

    # Outros callbacks que asyncua pode chamar — ignoramos por enquanto
    def status_change_notification(self, status) -> None:
        logger.info("[%s] OPC status change: %s", self.linha, status)

    def event_notification(self, event) -> None:
        pass  # não usamos events nessa fase


# ── Helpers ───────────────────────────────────────────────────────────

def _server_ts_ms(data: SubscriptionItemData) -> int | None:
    """
    Extrai timestamp do servidor OPC em ms epoch UTC.

    NOTA: atualmente NÃO é usado como fonte primária (ver datachange_notification)
    porque relógios de CLP costumam estar dessincronizados. Mantido para uso
    futuro / debug.

    Corrige o bug de datetime naive: asyncua às vezes devolve ServerTimestamp
    como datetime SEM tzinfo (naive). `.timestamp()` num naive assume o fuso
    LOCAL do container (TZ=America/Sao_Paulo, UTC-3) → 3h de erro. Forçamos UTC.
    """
    try:
        from datetime import timezone
        mv = data.monitored_item.Value
        st = mv.ServerTimestamp or mv.SourceTimestamp
        if st is None:
            return None
        if st.tzinfo is None:
            # OPC UA define timestamps em UTC — anexa tzinfo correto.
            st = st.replace(tzinfo=timezone.utc)
        return int(st.timestamp() * 1000)
    except Exception:
        return None
