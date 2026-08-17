"""
coletor/resilience.py
=====================

[P0.4 + P0.5 + P0.6] Building blocks de resiliência para o coletor OPC UA.

Inspirado nas práticas de SRE de players industriais (PI AF / Kepware / OSIsoft):
um coletor de dados de chão de fábrica **NUNCA** pode perder dados silenciosamente,
nem exigir restart manual quando a rede balança. Este módulo fornece:

  1. `retry_async`  — decorator tenacity com backoff exponencial para operações I/O.
  2. `CircuitBreaker` — protege contra chamadas a APIs externas degradadas.
  3. `ConnectionWatchdog` — task assíncrona que monitora a saúde de conexões OPC
     e dispara reconexão automática ANTES do próximo ciclo de coleta falhar.
  4. `OfflineBuffer` — fila durável em SQLite para pacotes de dados que falharam
     ao chegar no Flask/Django (ex.: rede caiu, backend reiniciou). Replay FIFO
     automático quando a conexão volta.
  5. `AsyncHttpClient` — httpx.AsyncClient wrapper com timeouts e retry built-in,
     substitui o `requests.post(..., timeout=X)` síncrono que BLOQUEIA o event loop.

Analogia (processo industrial):
  Pense neste módulo como o "no-break + gerador" do coletor. O coletor continua
  rodando mesmo quando: OPC oscila (→ watchdog reconecta), Flask cai (→ buffer
  SQLite guarda os pacotes), ou o Django está em deploy (→ circuit breaker evita
  flood de tentativas). Quando a rede volta, o replay da fila acontece em FIFO.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger('Coletor.resilience')


# ==============================================================================
# 1) RETRY COM BACKOFF EXPONENCIAL
# ==============================================================================
# Por que não usar `tenacity` direto no call-site?
# - Queremos política UNIFORME (max 5 tentativas, base 0.5s, max 10s).
# - Queremos LOG estruturado de cada retry para debugging em campo.
# - Queremos poder trocar a biblioteca (tenacity é a escolha padrão, mas
#   caso não esteja instalada em ambiente legado, o fallback deve funcionar).
# ==============================================================================
try:
    from tenacity import (
        AsyncRetrying,
        RetryError,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
        before_sleep_log,
    )
    _TENACITY_AVAILABLE = True
except ImportError:  # pragma: no cover — fallback quando tenacity não está disponível
    _TENACITY_AVAILABLE = False


async def retry_async(
    coro_fn: Callable[..., Awaitable[Any]],
    *args,
    retryable_exceptions: tuple = (OSError, ConnectionError, asyncio.TimeoutError, TimeoutError),
    max_attempts: int = 5,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    operation_name: str = 'operation',
    **kwargs,
) -> Any:
    """
    Executa uma coroutine com retry e backoff exponencial.
    Exemplo:

        result = await retry_async(
            cliente.connect,
            operation_name='opc.connect',
        )

    Se todas as tentativas falharem, relança a última exceção.
    """
    if _TENACITY_AVAILABLE:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=base_delay, max=max_delay),
                retry=retry_if_exception_type(retryable_exceptions),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            ):
                with attempt:
                    return await coro_fn(*args, **kwargs)
        except RetryError as e:  # pragma: no cover
            logger.error(
                f"❌ [{operation_name}] Excedido max_attempts={max_attempts}: {e.last_attempt.exception()}",
                exc_info=True,
            )
            raise e.last_attempt.exception()
    else:
        # Fallback manual (sem tenacity)
        attempt = 0
        last_exc: Optional[BaseException] = None
        while attempt < max_attempts:
            try:
                return await coro_fn(*args, **kwargs)
            except retryable_exceptions as e:
                last_exc = e
                attempt += 1
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                logger.warning(
                    f"⚠️ [{operation_name}] Tentativa {attempt}/{max_attempts} falhou: {e}. "
                    f"Aguardando {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
        logger.error(
            f"❌ [{operation_name}] Todas {max_attempts} tentativas falharam.",
            exc_info=(type(last_exc), last_exc, last_exc.__traceback__) if last_exc else False,
        )
        if last_exc:
            raise last_exc


# ==============================================================================
# 2) CIRCUIT BREAKER — evita "stampede" contra um serviço degradado
# ==============================================================================
# Estado: CLOSED (tudo ok) → OPEN (abre após N falhas) → HALF_OPEN (tenta 1
# requisição de teste) → CLOSED (se ok) ou OPEN (se falhou).
#
# Regra de ouro: melhor deixar 1 ciclo de coleta falhar RAPIDAMENTE do que ficar
# 30s pendurado tentando contatar um Flask que está em deploy. "Fail fast" é a
# marca dos bons coletores SCADA.
# ==============================================================================
@dataclass
class CircuitBreaker:
    """
    Circuit Breaker simples (thread-unsafe, mas adequado para event loop único).

    Uso:
        cb = CircuitBreaker(name='flask-api', fail_threshold=5, reset_timeout=30.0)
        try:
            await cb.call(http_client.post, url, json=data)
        except CircuitOpenError:
            # fallback: grava no buffer offline
            buffer.enqueue(data)
    """
    name: str
    fail_threshold: int = 5
    reset_timeout: float = 30.0  # segundos até tentar HALF_OPEN

    _state: str = field(default='CLOSED', init=False)
    _failure_count: int = field(default=0, init=False)
    _opened_at: float = field(default=0.0, init=False)

    async def call(self, coro_fn: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        now = time.monotonic()
        if self._state == 'OPEN':
            if now - self._opened_at >= self.reset_timeout:
                logger.info(f"🔧 [CB:{self.name}] transitioning OPEN → HALF_OPEN")
                self._state = 'HALF_OPEN'
            else:
                raise CircuitOpenError(f"Circuit breaker '{self.name}' is OPEN")

        try:
            result = await coro_fn(*args, **kwargs)
        except Exception:
            self._failure_count += 1
            if self._failure_count >= self.fail_threshold or self._state == 'HALF_OPEN':
                self._state = 'OPEN'
                self._opened_at = now
                logger.error(
                    f"🚨 [CB:{self.name}] OPEN após {self._failure_count} falhas. "
                    f"Pausa de {self.reset_timeout}s."
                )
            raise
        else:
            if self._state == 'HALF_OPEN':
                logger.info(f"✅ [CB:{self.name}] HALF_OPEN → CLOSED (recuperado)")
            self._state = 'CLOSED'
            self._failure_count = 0
            return result

    @property
    def state(self) -> str:
        return self._state


class CircuitOpenError(Exception):
    """Levantado quando o circuit breaker está aberto."""


# ==============================================================================
# 3) CONNECTION WATCHDOG — reconexão automática de OPC UA
# ==============================================================================
# Analogia WCM: é o Jidoka (autonomação) do coletor — a máquina detecta o defeito
# (conexão caiu) E age sozinha (reconecta), sem esperar operador (você, reiniciando).
#
# O watchdog roda em task separada do loop de coleta principal. Cada `check_interval`
# segundos, testa a saúde de TODAS as conexões registradas e dispara `reconnect_fn`
# para as que estão doentes.
# ==============================================================================
class ConnectionWatchdog:
    """
    Watchdog assíncrono que monitora e reconecta conexões OPC automaticamente.

    Uso:
        async def health_check(url): ...
        async def reconnect(url): ...

        wd = ConnectionWatchdog(health_check_fn=health_check, reconnect_fn=reconnect)
        wd.register('opc.tcp://linha1:4840')
        asyncio.create_task(wd.run())
    """

    def __init__(
        self,
        health_check_fn: Callable[[str], Awaitable[bool]],
        reconnect_fn: Callable[[str], Awaitable[bool]],
        check_interval: float = 10.0,
        unhealthy_streak_to_reconnect: int = 2,
    ):
        self.health_check_fn = health_check_fn
        self.reconnect_fn = reconnect_fn
        self.check_interval = check_interval
        self.unhealthy_streak_to_reconnect = unhealthy_streak_to_reconnect
        self._urls: set[str] = set()
        self._unhealthy_counts: dict[str, int] = {}
        self._stop_event = asyncio.Event()

    def register(self, url: str) -> None:
        self._urls.add(url)
        self._unhealthy_counts.setdefault(url, 0)

    def unregister(self, url: str) -> None:
        self._urls.discard(url)
        self._unhealthy_counts.pop(url, None)

    async def stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        logger.info(f"🛡️ Watchdog iniciado (intervalo={self.check_interval}s)")
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.check_interval)
            except asyncio.TimeoutError:
                pass  # intervalo normal de check
            if self._stop_event.is_set():
                break
            await self._tick()
        logger.info("🛡️ Watchdog encerrado")

    async def _tick(self) -> None:
        for url in list(self._urls):
            try:
                healthy = await self.health_check_fn(url)
            except Exception as e:
                logger.warning(f"⚠️ [watchdog] erro no health_check({url}): {e}")
                healthy = False

            if healthy:
                if self._unhealthy_counts.get(url, 0) > 0:
                    logger.info(f"✅ [watchdog] {url} voltou a ficar saudável.")
                self._unhealthy_counts[url] = 0
                continue

            self._unhealthy_counts[url] = self._unhealthy_counts.get(url, 0) + 1
            streak = self._unhealthy_counts[url]
            logger.warning(f"⚠️ [watchdog] {url} unhealthy (streak={streak})")

            if streak >= self.unhealthy_streak_to_reconnect:
                logger.info(f"🔌 [watchdog] tentando reconectar {url}...")
                try:
                    ok = await self.reconnect_fn(url)
                    if ok:
                        self._unhealthy_counts[url] = 0
                        logger.info(f"🎉 [watchdog] reconexão bem-sucedida: {url}")
                    else:
                        logger.warning(f"❌ [watchdog] reconexão falhou: {url}")
                except Exception as e:
                    logger.error(f"💥 [watchdog] exceção ao reconectar {url}: {e}", exc_info=True)


# ==============================================================================
# 4) OFFLINE BUFFER — fila durável em SQLite
# ==============================================================================
# Por que SQLite e não arquivo JSON Lines?
# - SQLite garante atomicidade (WAL mode): dois writers não corrompem.
# - Permite queries FIFO com LIMIT sem ler o arquivo inteiro.
# - É zero-config (`pip install` não precisa).
# - Aguenta MILHÕES de registros sem degradar.
#
# Schema: (id INTEGER PK, ts REAL, endpoint TEXT, payload_json TEXT, attempts INTEGER)
# Estratégia de replay:
#   - A cada ciclo de coleta, tenta drenar até `batch_size` registros.
#   - Se o POST sucede, deleta o registro.
#   - Se falha, incrementa `attempts`. Depois de `max_attempts`, move para DLQ
#     (ou apenas loga — decisão do operador).
# ==============================================================================
class OfflineBuffer:
    """Fila durável em SQLite para payloads que falharam ao enviar."""

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            endpoint TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_outbox_endpoint ON outbox (endpoint, id);
    """

    def __init__(self, db_path: str | Path = 'coletor_buffer.db', max_attempts: int = 20):
        self.db_path = str(db_path)
        self.max_attempts = max_attempts
        self._lock = asyncio.Lock()
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute('PRAGMA journal_mode=WAL;')
            conn.execute('PRAGMA synchronous=NORMAL;')
            conn.executescript(self.SCHEMA)
            conn.commit()
        finally:
            conn.close()

    async def enqueue(self, endpoint: str, payload: Any) -> int:
        """Enfileira um payload para envio posterior. Retorna o ID."""
        async with self._lock:
            # sqlite3 é síncrono — rodamos em thread pool para não bloquear o loop
            return await asyncio.to_thread(self._enqueue_sync, endpoint, payload)

    def _enqueue_sync(self, endpoint: str, payload: Any) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "INSERT INTO outbox (ts, endpoint, payload_json, attempts) VALUES (?, ?, ?, 0)",
                (time.time(), endpoint, json.dumps(payload, default=str)),
            )
            conn.commit()
            rid = cur.lastrowid
            logger.info(f"💾 [buffer] enfileirado {endpoint} id={rid} (size={conn.execute('SELECT COUNT(*) FROM outbox').fetchone()[0]})")
            return rid
        finally:
            conn.close()

    async def pending_count(self) -> int:
        return await asyncio.to_thread(self._pending_count_sync)

    def _pending_count_sync(self) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            return conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
        finally:
            conn.close()

    async def drain(
        self,
        endpoint: str,
        sender: Callable[[Any], Awaitable[bool]],
        batch_size: int = 50,
    ) -> tuple[int, int]:
        """
        Drena até `batch_size` itens do buffer para `endpoint`, enviando via `sender`.
        Retorna (sucessos, falhas).
        """
        async with self._lock:
            rows = await asyncio.to_thread(self._fetch_batch_sync, endpoint, batch_size)

        success, fail = 0, 0
        for row_id, payload_json, attempts in rows:
            try:
                payload = json.loads(payload_json)
                ok = await sender(payload)
            except Exception as e:
                logger.warning(f"⚠️ [buffer.drain] erro sender id={row_id}: {e}")
                ok = False

            if ok:
                await asyncio.to_thread(self._delete_sync, row_id)
                success += 1
            else:
                new_attempts = attempts + 1
                err_msg = None
                if new_attempts >= self.max_attempts:
                    logger.error(
                        f"☠️ [buffer] id={row_id} atingiu max_attempts={self.max_attempts}, "
                        f"descartando (considere DLQ)."
                    )
                    await asyncio.to_thread(self._delete_sync, row_id)
                else:
                    await asyncio.to_thread(self._bump_attempts_sync, row_id, new_attempts, err_msg)
                fail += 1

        if success or fail:
            logger.info(f"🔁 [buffer.drain:{endpoint}] success={success} fail={fail}")
        return success, fail

    def _fetch_batch_sync(self, endpoint: str, batch_size: int):
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "SELECT id, payload_json, attempts FROM outbox "
                "WHERE endpoint = ? ORDER BY id ASC LIMIT ?",
                (endpoint, batch_size),
            )
            return cur.fetchall()
        finally:
            conn.close()

    def _delete_sync(self, row_id: int) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DELETE FROM outbox WHERE id = ?", (row_id,))
            conn.commit()
        finally:
            conn.close()

    def _bump_attempts_sync(self, row_id: int, attempts: int, err: Optional[str]) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE outbox SET attempts = ?, last_error = ? WHERE id = ?",
                (attempts, err, row_id),
            )
            conn.commit()
        finally:
            conn.close()


# ==============================================================================
# 5) ASYNC HTTP CLIENT — substitui `requests` síncrono
# ==============================================================================
# PROBLEMA: `requests.post(url, timeout=10)` BLOQUEIA o event loop por até 10s.
# Durante esses 10s, NADA da coleta OPC acontece — timeouts se acumulam,
# watchdog não roda, comandos não são atendidos.
#
# FIX: httpx.AsyncClient com timeout + connection pooling.
# Se `httpx` não estiver disponível, usa `aiohttp`. Se nenhum, fallback via
# `asyncio.to_thread(requests.post, ...)` que pelo menos libera o loop.
# ==============================================================================
class AsyncHttpClient:
    """Wrapper assíncrono simples sobre httpx/aiohttp/requests-in-thread."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self._backend = None
        self._client = None
        self._init_backend()

    def _init_backend(self) -> None:
        try:
            import httpx
            self._backend = 'httpx'
            self._client = httpx.AsyncClient(timeout=self.timeout)
            logger.info("🌐 [http] backend=httpx")
            return
        except ImportError:
            pass
        try:
            import aiohttp  # noqa
            self._backend = 'aiohttp'
            logger.info("🌐 [http] backend=aiohttp")
            return
        except ImportError:
            pass
        self._backend = 'requests-thread'
        logger.warning(
            "⚠️ [http] httpx/aiohttp não disponíveis — usando requests em thread "
            "(performance degradada). Instale `httpx` para melhor latência."
        )

    async def post_json(self, url: str, payload: Any) -> bool:
        try:
            if self._backend == 'httpx':
                resp = await self._client.post(url, json=payload, timeout=self.timeout)
                return 200 <= resp.status_code < 300
            elif self._backend == 'aiohttp':
                import aiohttp
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as s:
                    async with s.post(url, json=payload) as resp:
                        return 200 <= resp.status < 300
            else:
                import requests
                def _do():
                    r = requests.post(url, json=payload, timeout=self.timeout)
                    return 200 <= r.status_code < 300
                return await asyncio.to_thread(_do)
        except Exception as e:
            logger.warning(f"⚠️ [http.post_json:{url}] {e}")
            return False

    async def aclose(self) -> None:
        if self._backend == 'httpx' and self._client:
            await self._client.aclose()


__all__ = [
    'retry_async',
    'CircuitBreaker',
    'CircuitOpenError',
    'ConnectionWatchdog',
    'OfflineBuffer',
    'AsyncHttpClient',
]
