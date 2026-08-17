"""
Pool de conexões OPC UA persistentes.

Premissa central: **uma única conexão por URL de servidor OPC** —
compartilhada entre todas as linhas que apontam para o mesmo CLP.

Isso evita o problema clássico de N workers × M tags = N×M conexões
que o `mis-change-over` original sofre sob gunicorn.

Cada `ManagedClient`:
  - Mantém o `asyncua.Client` ativo
  - Tem uma task de healthcheck/reconnect em background
  - Faz backoff exponencial (settings.opc_reconnect_backoff_min..max)
  - Notifica callbacks de mudança de estado online/offline

Não cria subscriptions aqui — quem faz isso é o `line_manager`.
Este módulo só garante "tenho um Client conectado quando alguém pedir".
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Awaitable, Callable, Optional

from asyncua import Client

from ..config import get_settings

logger = logging.getLogger(__name__)

OnStateChange = Callable[[str, bool], Awaitable[None]]
"""callback(url, online) — chamado quando o estado da conexão muda."""


class ManagedClient:
    """
    Um asyncua.Client com vida própria: connect, reconnect, healthcheck.

    Estado:
      - `client`    : referência ao asyncua.Client atual (pode ser substituído
                      em reconexões — sempre acesse via `await get_client()`)
      - `online`    : True quando a conexão está ativa
      - `_listeners`: callbacks invocados em transições online/offline
    """

    def __init__(self, url: str, on_state_change: Optional[OnStateChange] = None):
        self.url = url
        self.client: Client = Client(url=url, timeout=10)
        self.online: bool = False
        self._listeners: list[OnStateChange] = []
        if on_state_change is not None:
            self._listeners.append(on_state_change)
        self._lock = asyncio.Lock()
        self._stop = asyncio.Event()
        self._supervisor_task: Optional[asyncio.Task] = None

    def add_listener(self, cb: OnStateChange) -> None:
        self._listeners.append(cb)

    async def _notify(self, online: bool) -> None:
        for cb in list(self._listeners):
            try:
                await cb(self.url, online)
            except Exception:
                logger.exception("Listener de %s falhou (online=%s)", self.url, online)

    async def start(self) -> None:
        """Conecta e dispara supervisor em background."""
        if self._supervisor_task is None or self._supervisor_task.done():
            self._stop.clear()
            self._supervisor_task = asyncio.create_task(
                self._supervisor(), name=f"opc-supervisor:{self.url}"
            )

    async def stop(self) -> None:
        self._stop.set()
        if self._supervisor_task and not self._supervisor_task.done():
            self._supervisor_task.cancel()
            try:
                await self._supervisor_task
            except (asyncio.CancelledError, Exception):
                pass
        async with self._lock:
            if self.online:
                try:
                    await self.client.disconnect()
                except Exception:
                    pass
                self.online = False
                await self._notify(False)

    async def get_client(self) -> Client:
        """
        Garante que o client está conectado e retorna-o.
        Bloqueia enquanto uma reconexão estiver em andamento.
        """
        async with self._lock:
            if not self.online:
                await self._connect_once()
            return self.client

    async def _connect_once(self) -> None:
        """Tenta conectar uma vez. Atualiza self.online e notifica."""
        try:
            await self.client.connect()
            self.online = True
            logger.info("[OPC] conectado %s", self.url)
            await self._notify(True)
        except Exception as e:
            logger.warning("[OPC] falha ao conectar %s: %s", self.url, e)
            self.online = False
            # Cria um Client novo — o asyncua não gosta de reconectar o mesmo objeto
            self.client = Client(url=self.url, timeout=10)

    async def _supervisor(self) -> None:
        """
        Loop: tenta conectar; se cair, reconecta com backoff exponencial.
        Healthcheck simples via leitura periódica do server status node.
        """
        settings = get_settings()
        backoff = settings.opc_reconnect_backoff_min
        HEALTHCHECK_INTERVAL_S = 10

        while not self._stop.is_set():
            async with self._lock:
                if not self.online:
                    await self._connect_once()

            if not self.online:
                jitter = random.uniform(0.5, 1.5)
                wait = min(backoff * jitter, settings.opc_reconnect_backoff_max)
                logger.info("[OPC] aguardando %.1fs antes de reconectar %s", wait, self.url)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=wait)
                    return  # stop solicitado
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, settings.opc_reconnect_backoff_max)
                continue

            # online → healthcheck periódico
            backoff = settings.opc_reconnect_backoff_min
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=HEALTHCHECK_INTERVAL_S)
                return  # stop solicitado
            except asyncio.TimeoutError:
                pass

            # Lê o ServerStatus para validar a conexão.
            # Se falhar, marca offline → loop reconecta no próximo tick.
            # Se passar, notifica online de novo → refresca o TTL do Redis
            # para evitar UI piscar offline em linha parada.
            try:
                async with self._lock:
                    if self.online:
                        node = self.client.get_node("i=2256")  # ServerStatus
                        await asyncio.wait_for(node.read_value(), timeout=5)
                # Healthcheck OK → refresca estado online nos listeners.
                # Sem isso, em linhas sem datachange por 35s+ a UI mostra offline.
                await self._notify(True)
            except Exception as e:
                logger.warning("[OPC] healthcheck falhou %s: %s — vai reconectar", self.url, e)
                async with self._lock:
                    self.online = False
                    try:
                        await self.client.disconnect()
                    except Exception:
                        pass
                    self.client = Client(url=self.url, timeout=10)
                await self._notify(False)


class OPCPool:
    """
    Singleton que mapeia URL → ManagedClient.
    Não destrói ManagedClients automaticamente — só no shutdown global,
    porque os custos de reconectar superam o custo de manter ocioso.
    """

    def __init__(self):
        self._by_url: dict[str, ManagedClient] = {}
        self._global_lock = asyncio.Lock()

    async def get_or_create(
        self, url: str, on_state_change: Optional[OnStateChange] = None
    ) -> ManagedClient:
        async with self._global_lock:
            mc = self._by_url.get(url)
            if mc is None:
                mc = ManagedClient(url, on_state_change=on_state_change)
                self._by_url[url] = mc
                await mc.start()
            elif on_state_change is not None:
                mc.add_listener(on_state_change)
            return mc

    async def shutdown(self) -> None:
        async with self._global_lock:
            await asyncio.gather(
                *(mc.stop() for mc in self._by_url.values()),
                return_exceptions=True,
            )
            self._by_url.clear()


# ── Singleton helpers ─────────────────────────────────────────────────

_pool: OPCPool | None = None


def get_opc_pool() -> OPCPool:
    global _pool
    if _pool is None:
        _pool = OPCPool()
    return _pool


async def close_opc_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.shutdown()
        _pool = None
