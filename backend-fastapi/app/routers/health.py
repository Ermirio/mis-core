"""
app/routers/health.py
=====================

Liveness + readiness probes. Essenciais para rodar o FastAPI atrás de um
orquestrador (Docker compose, k8s, systemd restart=always) e descobrir
rapidamente se o problema é "o processo morreu" vs "o Influx está fora".

Por que separar liveness de readiness:
    - Liveness (`/healthz`) = o processo está vivo? (loop de eventos respondendo)
    - Readiness (`/ready`)  = o processo consegue atender tráfego? (dependências OK)
    Um kube restart só deve ocorrer no liveness, não no readiness.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__
from app.services.influx import InfluxAsyncClient, InfluxQueryError

router = APIRouter(tags=["health"])

_started_at = time.monotonic()


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_s: float
    now: datetime


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, str]


# COMPAT: o Flask legado expoe /api/health. Para permitir migracao sem
# quebrar monitores externos, aceitamos AMBOS /health e /healthz apontando
# para a mesma funcao, assim nginx pode rotear /api/health -> FastAPI sem
# surpresa.
@router.get("/healthz", response_model=HealthResponse, include_in_schema=True)
@router.get("/health",  response_model=HealthResponse, include_in_schema=False)
async def healthz() -> HealthResponse:
    """Liveness - so confirma que o processo responde."""
    return HealthResponse(
        status="ok",
        version=__version__,
        uptime_s=round(time.monotonic() - _started_at, 1),
        now=datetime.now(timezone.utc),
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"description": "Dependencia indisponivel"}},
)
async def ready() -> ReadinessResponse:
    """
    Readiness - verifica dependencias criticas. Retorna 503 se alguma falhar
    (o ingress pode entao tirar esta instancia do balanceamento).
    """
    checks: dict[str, str] = {}
    overall_ok = True

    # Influx
    try:
        async with InfluxAsyncClient() as c:
            await c.query_raw("SHOW DATABASES")
        checks["influx"] = "ok"
    except InfluxQueryError as e:
        checks["influx"] = f"fail: {e}"
        overall_ok = False
    except Exception as e:   # rede/DNS fora do Influx
        checks["influx"] = f"fail: {type(e).__name__}"
        overall_ok = False

    return ReadinessResponse(
        status="ok" if overall_ok else "degraded",
        checks=checks,
    )


__all__ = ["router"]
