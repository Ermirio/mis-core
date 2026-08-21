"""
app/main.py
===========

Fábrica da aplicação FastAPI. Usa o padrão `create_app()` para facilitar
testes (Dependency Injection override) e permitir múltiplas instâncias em
processos diferentes (ex.: analytics worker separado do gateway HTTP).

Montagem:
    /api/v2/healthz          liveness
    /api/v2/ready            readiness (Influx etc.)
    /api/v2/analytics/*      EDA científica
    /api/v2/kpis/*           OEE, TPH, give-away
    /metrics                 Prometheus (se habilitado)

Strangler Pattern:
    Por enquanto NÃO substituímos o Flask/Django existentes. O React pode
    começar a chamar /api/v2/* e manter compat com /api/* legado. O gateway
    (nginx) roteia por prefixo. Quando /api/v2 estiver maduro, reescrevemos
    o nginx para apontar /api/* -> FastAPI.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.routers import analytics as analytics_router
from app.routers import health as health_router
from app.routers import kpis as kpis_router
from app.routers import production as production_router


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """
    Startup / shutdown hooks. Aqui podemos abrir pools (httpx, asyncpg),
    inicializar Prometheus, etc. Tudo limpo no shutdown.
    """
    settings = get_settings()
    _configure_logging(settings.log_level)
    log = logging.getLogger("app.main")
    log.info("Starting %s v%s (env=%s)", settings.app_name, __version__, settings.environment)
    yield
    log.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    s = get_settings()

    app = FastAPI(
        title=s.app_name,
        version=__version__,
        description=(
            "mis-core FastAPI v2 — camada nova (Strangler). "
            "Analytics honesto (OFF-mask + counter-deltas), "
            "KPIs ISO 22400-2 single-source-of-truth, "
            "time-range Grafana-style."
        ),
        lifespan=_lifespan,
        openapi_url=f"{s.api_v2_prefix}/openapi.json",
        docs_url=f"{s.api_v2_prefix}/docs",
        redoc_url=f"{s.api_v2_prefix}/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers sob o prefixo /api/v2
    app.include_router(health_router.router, prefix=s.api_v2_prefix)
    app.include_router(analytics_router.router, prefix=s.api_v2_prefix)
    app.include_router(kpis_router.router, prefix=s.api_v2_prefix)
    app.include_router(production_router.router, prefix=s.api_v2_prefix)

    # Prometheus (opt-in — só monta se a lib estiver disponível)
    if s.prometheus_enabled:
        try:
            from prometheus_fastapi_instrumentator import Instrumentator

            Instrumentator().instrument(app).expose(app, endpoint="/metrics")
        except ImportError:
            logging.getLogger("app.main").warning(
                "prometheus_fastapi_instrumentator ausente — /metrics desabilitado"
            )

    return app


app = create_app()


__all__ = ["create_app", "app"]
