"""
WebSocket endpoint do mis-recipe-intelligent.

Conexão por linha:  ws://<host>/ws/linhas/{nome}/stream

Mensagens enviadas pelo servidor (JSON):
  - {"tipo": "hello",       "linha": "L21", "timestamp_ms": ...}
  - {"tipo": "opc_status",  "linha": "L21", "online": true/false, "timestamp_ms": ...}
  - {"tipo": "update",      "linha": "L21", "variavel_id": 12, "valor": 1.004,
                            "timestamp_ms": ..., "status": "normal"}
  - {"tipo": "ping",        "timestamp_ms": ...}    # heartbeat

Mensagens aceitas do cliente (JSON):
  - {"tipo": "pong"}    # ignorado por enquanto

Fluxo:
  1. Aceita a conexão e dispara `line_manager.ensure_subscribed(linha)`
     (idempotente — abre subscription OPC se ainda não houver).
  2. Assina os canais Redis da linha (updates + opc_status) via PubSub.
  3. Em paralelo: heartbeat a cada HEARTBEAT_INTERVAL_S.
  4. Desconexão → `line_manager.release_one(linha)` (refcount--; grace
     period cuida do fechamento eventual).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..opc.line_manager import get_line_manager
from ..state.redis_store import get_redis_store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ws"])

HEARTBEAT_INTERVAL_S = 20


@router.websocket("/ws/linhas/{linha_nome}/stream")
async def stream_line(websocket: WebSocket, linha_nome: str) -> None:
    """
    Token JWT pode vir de duas formas:
      1. Query string ?token=...  (preferido para browsers — não suportam
         Authorization header em WebSocket nativo)
      2. Authorization: Bearer ...  (clientes não-browser)

    Aqui apenas registramos o token para uso futuro (validação delegada ao
    Django nos endpoints REST). A conexão WS em si não exige autenticação
    nesta fase — todo acesso a dados sensíveis passa pelo Django.
    """
    token = websocket.query_params.get("token") or _extract_bearer(
        websocket.headers.get("authorization")
    )
    await websocket.accept()
    logger.info("[WS] cliente conectado em linha=%s token_present=%s",
                linha_nome, bool(token))

    line_manager = get_line_manager()
    redis = get_redis_store()

    refcount_acquired = False
    fan_task: asyncio.Task | None = None
    heartbeat_task: asyncio.Task | None = None

    try:
        await line_manager.ensure_subscribed(linha_nome)
        refcount_acquired = True

        await websocket.send_json({
            "tipo": "hello",
            "linha": linha_nome,
            "timestamp_ms": _now_ms(),
        })

        # Estado inicial OPC online/offline — útil para o frontend pintar
        # o badge "OPC UA Conectado/Offline" sem esperar o primeiro update.
        try:
            online = await redis.is_opc_online(linha_nome)
            await websocket.send_json({
                "tipo": "opc_status",
                "linha": linha_nome,
                "online": online,
                "timestamp_ms": _now_ms(),
            })
        except Exception:
            logger.exception("[WS] falha lendo opc_online inicial linha=%s", linha_nome)

        # Tasks paralelas:
        #   - fan_redis_to_ws: assina Redis e encaminha
        #   - heartbeat: ping a cada N segundos (detecta socket morto)
        fan_task = asyncio.create_task(
            _fan_redis_to_ws(websocket, linha_nome),
            name=f"ws-fan:{linha_nome}",
        )
        heartbeat_task = asyncio.create_task(
            _heartbeat(websocket),
            name=f"ws-hb:{linha_nome}",
        )

        # Reader do cliente — apenas para detectar disconnect rapidamente.
        # Ignora payloads (não temos protocolo de subida ainda).
        while True:
            try:
                msg = await websocket.receive_text()
            except WebSocketDisconnect:
                raise
            # ignora silenciosamente
            if msg and len(msg) > 8192:
                logger.warning("[WS] mensagem do cliente acima do limite — descartada")

    except WebSocketDisconnect:
        logger.info("[WS] cliente desconectou linha=%s", linha_nome)
    except Exception:
        logger.exception("[WS] erro inesperado linha=%s", linha_nome)
    finally:
        for t in (fan_task, heartbeat_task):
            if t is not None and not t.done():
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
        if refcount_acquired:
            try:
                await line_manager.release_one(linha_nome)
            except Exception:
                logger.exception("[WS] falha no release_one(%s)", linha_nome)


# ── Background tasks ──────────────────────────────────────────────────

async def _fan_redis_to_ws(websocket: WebSocket, linha: str) -> None:
    """Assina Redis pub/sub e encaminha cada mensagem ao WS."""
    redis = get_redis_store()
    try:
        async for msg in redis.subscribe_line(linha):
            # `msg` já é dict (json.loads feito no store)
            try:
                await websocket.send_text(json.dumps(msg))
            except Exception:
                # Socket caiu; sair do laço — o finally do handler limpa.
                return
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("[WS] erro no fan-out Redis linha=%s", linha)


async def _heartbeat(websocket: WebSocket) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_S)
        try:
            await websocket.send_json({"tipo": "ping", "timestamp_ms": _now_ms()})
        except Exception:
            return


def _now_ms() -> int:
    return int(time.time() * 1000)


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    s = authorization.strip()
    if s.lower().startswith("bearer "):
        return s[7:].strip() or None
    return s or None
