"""
Line Manager — orquestra subscriptions OPC por linha.

Modelo de uso:

    await line_manager.ensure_subscribed("L21")   # idempotente
    # ... cliente WS conectado, recebe updates
    await line_manager.release_one("L21")         # decrementa refcount

Cada linha mantém:
  - Lista de subscriptions ativas (uma por servidor OPC distinto na linha)
  - Map node_id → (variavel_id, tipo_db) usado pelo handler
  - Contador de "consumidores" (WS clients conectados a esta linha)
  - Snapshot da config do Django, com TTL

Quando refcount cai a zero, agenda **grace period** antes de cancelar
a subscription — evita derrubar/recriar a cada refresh de página.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from asyncua import Client, ua

from ..config import get_settings
from ..django_client import DjangoClient
from ..schemas import DjangoLinhaConfig
from ..state.redis_store import RedisStore
from .pool import OPCPool
from .subscription import LineSubscriptionHandler

logger = logging.getLogger(__name__)

# Tempo de tolerância antes de fechar subscriptions de uma linha sem
# consumidores. Mantemos quente para refresh de página / reconexão WS.
GRACE_PERIOD_S = 30


@dataclass
class _LineState:
    """Estado interno para UMA linha sob gestão."""
    nome: str
    config: Optional[DjangoLinhaConfig] = None
    config_loaded_at: float = 0.0
    refcount: int = 0
    # Subscriptions ativas: list de (url_opc, asyncua.Subscription, handler)
    subs: list[tuple[str, "ua.Subscription", LineSubscriptionHandler]] = field(default_factory=list)
    grace_task: Optional[asyncio.Task] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class LineManager:
    """
    Singleton — uma instância por processo do serviço.
    Coordena DjangoClient + OPCPool + RedisStore para uma linha.
    """

    def __init__(self, django: DjangoClient, opc_pool: OPCPool, redis: RedisStore):
        self.django = django
        self.opc_pool = opc_pool
        self.redis = redis
        self._lines: dict[str, _LineState] = {}
        self._lines_lock = asyncio.Lock()

    # ── API pública ───────────────────────────────────────────────────

    async def ensure_subscribed(self, linha: str) -> None:
        """
        Garante que esta linha está sendo monitorada via OPC.
        Idempotente. Cancela grace_task se houver — alguém voltou a usar.
        """
        state = await self._get_or_create_state(linha)

        async with state.lock:
            state.refcount += 1

            # Se está no grace period, cancela — alguém voltou.
            if state.grace_task and not state.grace_task.done():
                state.grace_task.cancel()
                state.grace_task = None
                logger.info("[%s] grace period cancelado (refcount=%d)",
                            linha, state.refcount)

            if state.subs:
                # Já ativa — só incrementamos o refcount.
                return

            await self._load_config_if_needed(state)
            if state.config is None or not _has_opc_tags(state.config):
                logger.warning("[%s] sem tags OPC configuradas — nada a monitorar", linha)
                return

            await self._open_subscriptions(state)

    async def release_one(self, linha: str) -> None:
        """
        Decrementa refcount. Quando chega a zero, agenda grace period.
        """
        state = self._lines.get(linha)
        if state is None:
            return

        async with state.lock:
            state.refcount = max(0, state.refcount - 1)
            if state.refcount > 0:
                return
            if state.grace_task and not state.grace_task.done():
                return  # já tem grace agendado
            state.grace_task = asyncio.create_task(
                self._grace_then_close(state), name=f"grace:{linha}"
            )

    async def shutdown_all(self) -> None:
        """Fecha tudo (usado no shutdown do app)."""
        async with self._lines_lock:
            states = list(self._lines.values())
            self._lines.clear()
        for s in states:
            async with s.lock:
                if s.grace_task and not s.grace_task.done():
                    s.grace_task.cancel()
                await self._close_subscriptions(s)

    # ── Detalhes internos ─────────────────────────────────────────────

    async def _get_or_create_state(self, linha: str) -> _LineState:
        async with self._lines_lock:
            state = self._lines.get(linha)
            if state is None:
                state = _LineState(nome=linha)
                self._lines[linha] = state
            return state

    async def _load_config_if_needed(self, state: _LineState) -> None:
        """Carrega/atualiza config OPC vinda do Django, respeitando TTL."""
        settings = get_settings()
        now = time.time()
        if (
            state.config is not None
            and (now - state.config_loaded_at) < settings.opc_config_ttl_seconds
        ):
            return
        try:
            configs = await self.django.get_opc_configs()
        except Exception:
            logger.exception("[%s] falha ao buscar /api/opc-configs/", state.nome)
            return
        for c in configs.linhas_configuracoes:
            if c.nome == state.nome:
                state.config = c
                state.config_loaded_at = now
                return
        logger.warning("[%s] linha não encontrada em /api/opc-configs/", state.nome)
        state.config = None

    async def _open_subscriptions(self, state: _LineState) -> None:
        """
        Para cada URL OPC distinta na linha, abre 1 subscription.
        Cada tag vira um MonitoredItem ligado ao handler da linha.

        Aplica os filtros configurados:
          - Equipamento de tipo em `ignore_equipment_types` → pulado inteiro
          - Variável com nome em `ignore_variable_names` → pulada
        """
        settings = get_settings()
        assert state.config is not None

        # Agrupa por URL OPC. Constrói node_to_var map global da linha.
        node_to_var: dict[str, tuple[int, str]] = {}
        nodes_por_url: dict[str, list[tuple[str, int, str]]] = {}

        ignored_eq = 0
        ignored_var = 0

        for equip in state.config.equipamentos:
            url = equip.conexao_opcua_url
            if not url:
                continue
            # Filtro 1: tipo de equipamento (ex.: BALANCA)
            if settings.should_ignore_equipment(equip.tipo_equipamento):
                ignored_eq += 1
                logger.info("[%s] ignorando equipamento %r (tipo=%s)",
                            state.nome, equip.nome, equip.tipo_equipamento)
                continue
            for v in equip.configuracoes_variaveis:
                if not v.tag_plc:
                    continue
                # Filtro 2: variável interceptada por trocar_sku (SKU_Esperado, ...)
                if settings.should_ignore_variable(v.nome_variavel_mestra):
                    ignored_var += 1
                    continue
                node_id = _build_node_id(equip.conexao_opcua_caminho_plc, v.tag_plc)
                node_to_var[node_id] = (v.variavel_mestra_id, v.tipo_variavel_mestra)
                nodes_por_url.setdefault(url, []).append(
                    (node_id, v.variavel_mestra_id, v.tipo_variavel_mestra)
                )

        if ignored_eq or ignored_var:
            logger.info("[%s] filtros aplicados: %d equipamento(s) e %d variável(is) ignorada(s)",
                        state.nome, ignored_eq, ignored_var)

        for url, items in nodes_por_url.items():
            try:
                managed = await self.opc_pool.get_or_create(
                    url,
                    on_state_change=self._make_state_listener(state.nome),
                )
                client: Client = await managed.get_client()

                handler = LineSubscriptionHandler(
                    linha=state.nome,
                    redis_store=self.redis,
                    node_to_var=node_to_var,  # compartilhado entre subs da linha
                )
                sub = await client.create_subscription(
                    period=settings.opc_subscription_interval_ms,
                    handler=handler,
                )
                nodes = [client.get_node(node_id) for (node_id, _, _) in items]
                await sub.subscribe_data_change(nodes)
                state.subs.append((url, sub, handler))

                logger.info(
                    "[%s] subscription aberta em %s (%d tags)",
                    state.nome, url, len(items),
                )
                await self.redis.mark_opc_status(linha=state.nome, online=True)
            except Exception:
                logger.exception("[%s] falha ao abrir subscription em %s", state.nome, url)
                await self.redis.mark_opc_status(linha=state.nome, online=False)

    def _make_state_listener(self, linha: str):
        async def _listener(url: str, online: bool) -> None:
            # Quando um servidor OPC desta linha muda de estado, sinalizamos.
            await self.redis.mark_opc_status(linha=linha, online=online)
        return _listener

    async def _close_subscriptions(self, state: _LineState) -> None:
        for url, sub, _ in state.subs:
            try:
                await sub.delete()
                logger.info("[%s] subscription fechada em %s", state.nome, url)
            except Exception:
                logger.warning("[%s] falha ao fechar subscription em %s", state.nome, url)
        state.subs.clear()
        await self.redis.mark_opc_status(linha=state.nome, online=False)

    async def _grace_then_close(self, state: _LineState) -> None:
        """Aguarda GRACE_PERIOD_S e, se ninguém voltou, fecha subs."""
        try:
            await asyncio.sleep(GRACE_PERIOD_S)
        except asyncio.CancelledError:
            return  # alguém voltou — abortamos o fechamento

        async with state.lock:
            if state.refcount > 0:
                return  # alguém voltou no fio do navalha
            logger.info("[%s] grace expirado, fechando subscriptions", state.nome)
            await self._close_subscriptions(state)
            state.grace_task = None


# ── Helpers ───────────────────────────────────────────────────────────

def _build_node_id(caminho_plc: str, tag_plc: str) -> str:
    """
    Constrói o NodeId no formato que o Django/OPC UA usa:
        ns=2;s=<caminho_plc><tag_plc>

    Reproduz a regra usada em `escrever_plc()` ([views.py:152]):
        node_path = f"ns=2;s={caminho_plc}{tag_plc}"
    """
    if tag_plc.startswith("ns=") or tag_plc.startswith("i="):
        # tag_plc já é um NodeId completo
        return tag_plc
    return f"ns=2;s={caminho_plc or ''}{tag_plc}"


def _has_opc_tags(config: DjangoLinhaConfig) -> bool:
    for equip in config.equipamentos:
        if equip.conexao_opcua_url:
            for v in equip.configuracoes_variaveis:
                if v.tag_plc:
                    return True
    return False


# ── Singleton ─────────────────────────────────────────────────────────

_manager: LineManager | None = None


def get_line_manager() -> LineManager:
    global _manager
    if _manager is None:
        # Importação tardia para evitar ciclo
        from ..django_client import get_django_client
        from ..state.redis_store import get_redis_store
        from .pool import get_opc_pool

        _manager = LineManager(
            django=get_django_client(),
            opc_pool=get_opc_pool(),
            redis=get_redis_store(),
        )
    return _manager


async def close_line_manager() -> None:
    global _manager
    if _manager is not None:
        await _manager.shutdown_all()
        _manager = None
