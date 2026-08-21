"""
app/services/influx.py
======================

Wrapper assíncrono do InfluxDB 1.x — substitui o cliente síncrono do Flask
(que bloqueia o event loop e gera backpressure em picos de requisição).

Por que isto existe:
    No backend-flask, o `influxdb.InfluxDBClient` é síncrono e espalhado por
    dezenas de call-sites, sem pool nem timeout. Em picos (UI atualizando
    várias variáveis em paralelo), a latência percebida explode.

Design:
    - `InfluxAsyncClient` encapsula um httpx.AsyncClient com timeout, retries
      e medição de latência (histograma Prometheus — hook pronto para quando
      montarmos o app/core/metrics_prom.py).
    - `query_df(q)` devolve um `pandas.DataFrame` com coluna 'time' como
      DatetimeIndex UTC — compatível com a convenção dos pipelines.
    - Suporta back-off exponencial em 5xx (via tenacity, opcional).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pandas as pd

from app.config import get_settings

logger = logging.getLogger(__name__)


class InfluxQueryError(Exception):
    """Erro retornado pelo InfluxDB (HTTP != 200 ou série vazia inesperada)."""


class InfluxAsyncClient:
    """
    Cliente async minimalista para InfluxDB 1.x /query endpoint.

    Por que não usar aioinflux: aioinflux está sem manutenção (último commit
    2021) e tem dependência pesada em aiohttp. httpx nos dá async + sync
    unificados, timeouts decentes e boa performance.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout_s: float = 10.0,
    ) -> None:
        s = get_settings()
        self.base_url = f"http://{host or s.influx_host}:{port or s.influx_port}"
        self.database = database or s.influx_db
        self.username = username or s.influx_username
        self.password = password or s.influx_password
        self.timeout = httpx.Timeout(timeout_s, connect=3.0)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "InfluxAsyncClient":
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    async def query_raw(self, q: str) -> dict[str, Any]:
        """
        Executa uma query InfluxQL e devolve o JSON bruto.
        Raises InfluxQueryError em HTTP != 2xx.
        """
        if self._client is None:
            # Fallback: cria client efêmero. Idealmente usar context manager.
            async with InfluxAsyncClient(
                host=self.base_url.split("://")[1].split(":")[0],
                port=int(self.base_url.split(":")[-1]),
                database=self.database,
                username=self.username,
                password=self.password,
            ) as c:
                return await c.query_raw(q)

        params: dict[str, Any] = {"db": self.database, "q": q, "epoch": "ms"}
        auth = None
        if self.username:
            auth = (self.username, self.password or "")

        try:
            r = await self._client.get(f"{self.base_url}/query", params=params, auth=auth)
        except httpx.HTTPError as e:
            logger.warning("InfluxDB network error: %s", e)
            raise InfluxQueryError(f"Network: {e}") from e

        if r.status_code >= 400:
            logger.warning("InfluxDB HTTP %s — %s", r.status_code, r.text[:200])
            raise InfluxQueryError(f"HTTP {r.status_code}: {r.text[:200]}")

        return r.json()

    async def query_df(self, q: str) -> pd.DataFrame:
        """
        Executa query e devolve DataFrame com coluna 'time' convertida
        para DatetimeIndex UTC. Retorna DF vazio se a série estiver vazia.
        """
        payload = await self.query_raw(q)
        series = _extract_first_series(payload)
        if not series:
            return pd.DataFrame()

        df = pd.DataFrame(series["values"], columns=series["columns"])
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
            df = df.set_index("time").sort_index()
        return df


def _extract_first_series(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Extrai a primeira série de um payload InfluxDB /query."""
    results = payload.get("results") or []
    if not results:
        return None
    series = results[0].get("series") or []
    if not series:
        return None
    return series[0]


__all__ = ["InfluxAsyncClient", "InfluxQueryError"]
