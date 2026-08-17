"""
Entrypoint do mis-recipe-intelligent.

Rodar:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8100

Estrutura:
  - Lifespan gerencia ciclo de vida do cliente Django e (futuramente) do
    pool OPC e da conexão Redis.
  - Rotas REST + WS são montadas a partir de app/api/.
  - /health é mantida inline para simplicidade (sem dependências).

Em desenvolvimento, qualquer mudança em config.py exige restart — o cache
de `get_settings()` é por processo.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.rest import router as rest_router
from .api.ws import router as ws_router
from .config import get_settings
from .django_client import close_django_client, get_django_client
from .opc.line_manager import close_line_manager, get_line_manager
from .opc.pool import close_opc_pool, get_opc_pool
from .state.redis_store import close_redis_store, get_redis_store

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting mis-recipe-intelligent — Django=%s redis=%s",
                settings.django_base_url_clean, settings.redis_url)

    # Inicializa singletons na ordem certa:
    #  1. DjangoClient  — usado pelo line_manager
    #  2. RedisStore    — conecta e dá ping
    #  3. OPCPool       — vazio; preenche sob demanda quando line_manager pede
    #  4. LineManager   — junta os três acima
    get_django_client()
    redis_store = get_redis_store()
    await redis_store.connect()
    get_opc_pool()
    line_manager = get_line_manager()

    # Pré-carga opcional: se LINES_PRELOAD vier setado, abre subscriptions
    # imediatamente para essas linhas (não espera o primeiro WS).
    for linha in settings.lines_preload_list:
        try:
            await line_manager.ensure_subscribed(linha)
            # Incrementamos refcount artificialmente para não cair em grace
            # period imediatamente — preload significa "sempre quente".
            # release_one no shutdown não é chamado; tudo cai junto.
            logger.info("Linha preload ativa: %s", linha)
        except Exception:
            logger.exception("Falha no preload da linha %s", linha)

    try:
        yield
    finally:
        logger.info("Shutting down mis-recipe-intelligent")
        # Ordem inversa: fecha o que depende primeiro.
        await close_line_manager()
        await close_opc_pool()
        await close_redis_store()
        await close_django_client()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="mis-recipe-intelligent",
        description="Async OPC UA recipe monitor for MIS Change Over",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        """Liveness/readiness probe. Não chama dependências externas."""
        return {"status": "ok", "service": "mis-recipe-intelligent"}

    app.include_router(rest_router)
    app.include_router(ws_router)

    return app


app = create_app()
