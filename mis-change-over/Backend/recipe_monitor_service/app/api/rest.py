"""
Rotas REST do mis-recipe-intelligent.

Endpoints:
  GET  /linhas/{nome}/config           — Config OPC da linha (proxy + cache do Django)
  GET  /linhas/{nome}/snapshot         — Estado atual de todas as variáveis  [TODO Fase 3]
  POST /linhas/{nome}/sincronizar      — Proxy autenticado para Django PATCH

Notas:
  - /config é útil para o frontend descobrir tag_plc, unidade, tolerância,
    tipo etc. sem precisar chamar o Django diretamente. Cache TTL é
    OPC_CONFIG_TTL_SECONDS (futuro — usa o Django direto por enquanto).
  - /snapshot depende do Redis store (Fase 3). Retorna 503 até lá.
"""
from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import get_operator_jwt, get_operator_jwt_optional
from ..classifier import classificar
from ..django_client import DjangoAPIError, get_django_client
from ..opc.line_manager import get_line_manager
from ..schemas import (
    DjangoLinhaConfig,
    HistoricoPonto,
    SincronizarRequest,
    SincronizarResponse,
    Snapshot,
    SnapshotVariavel,
)
from ..state.redis_store import get_redis_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/linhas/{linha_nome}", tags=["linhas"])


def _to_django_string(valor) -> str:
    """
    Normaliza um valor (qualquer tipo) para string como Django espera em
    FormatoVariavel.valor (CharField). BOOL → 'TRUE'/'FALSE' para casar
    com o que `escrever_plc` ([views.py:175]) e o admin já manipulam.

    Floats que sao numeros inteiros viram int strings ("32.0" → "32") para
    evitar `ValueError: invalid literal for int()` em `escrever_plc` quando
    o tipo no banco e' DINT/UDINT/INT/UINT. Para REAL, "1" tambem funciona
    em `float("1")`.
    """
    if isinstance(valor, bool):
        return "TRUE" if valor else "FALSE"
    if isinstance(valor, float) and valor.is_integer() and abs(valor) < 1e15:
        return str(int(valor))
    return str(valor)


# ╔════════════════════════════════════════════════════════════════════╗
# ║ GET /linhas/{nome}/config                                          ║
# ╚════════════════════════════════════════════════════════════════════╝

@router.get("/config", response_model=DjangoLinhaConfig)
async def get_line_config(
    linha_nome: str,
    jwt: Annotated[str | None, Depends(get_operator_jwt_optional)],
) -> DjangoLinhaConfig:
    """
    Retorna a configuração OPC da linha (URLs, equipamentos, tags).

    Internamente chama /api/opc-configs/ do Django e filtra pela linha.
    """
    try:
        configs = await get_django_client().get_opc_configs(jwt=jwt)
    except DjangoAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha ao consultar Django: {e}",
        ) from e

    for linha_cfg in configs.linhas_configuracoes:
        if linha_cfg.nome == linha_nome:
            return linha_cfg

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Linha '{linha_nome}' não encontrada ou não tem configuração OPC.",
    )


# ╔════════════════════════════════════════════════════════════════════╗
# ║ GET /linhas/{nome}/snapshot                                        ║
# ╚════════════════════════════════════════════════════════════════════╝

@router.get("/snapshot", response_model=Snapshot)
async def get_snapshot(
    linha_nome: str,
    jwt: Annotated[str | None, Depends(get_operator_jwt_optional)],
) -> Snapshot:
    """
    Estado atual de todas variáveis da linha (último valor + histórico).

    Estratégia:
      1. Garante que o OPC reader está monitorando esta linha (refcount++)
         — Atenção: o cliente DEVE chamar release ao sair, normalmente
         via /linhas/{nome}/release. Para o caso "carregar a tela uma vez",
         usamos o WS para gerenciar refcount (snapshot puro não incrementa).
      2. Lê config OPC (via line_manager, que cacheia).
      3. Lê estado atual + histórico do Redis.
      4. Classifica como "normal" / "semleitura" (sem receita: o frontend
         conhece o formato escolhido e aplica a tolerância para apurar
         atencao/alarme contra a receita).
    """
    # 1. Garante config carregada — não incrementa refcount aqui (snapshot
    #    é leitura "ao vivo" do cache; quem mantém o reader ativo é o WS).
    manager = get_line_manager()
    state = await manager._get_or_create_state(linha_nome)  # noqa: SLF001
    async with state.lock:
        await manager._load_config_if_needed(state)  # noqa: SLF001
        config = state.config

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Linha '{linha_nome}' não encontrada no Django.",
        )

    # 2. Lê estado do Redis
    redis = get_redis_store()
    online = await redis.is_opc_online(linha_nome)
    atual_map = await redis.get_snapshot_atual(linha_nome)
    ts_map = await redis.get_snapshot_ts(linha_nome)

    # 3. Casa config × leituras → SnapshotVariavel[]
    #    Aplica os mesmos filtros do line_manager (tipos de equipamento e
    #    nomes de variáveis a ignorar) para que a UI mostre só o que é
    #    monitorado / sincronizável.
    from ..config import get_settings
    settings = get_settings()

    variaveis: list[SnapshotVariavel] = []
    ultima_atualizacao_ms: Optional[int] = None
    for equip in config.equipamentos:
        if settings.should_ignore_equipment(equip.tipo_equipamento):
            continue
        for v in equip.configuracoes_variaveis:
            if settings.should_ignore_variable(v.nome_variavel_mestra):
                continue
            valor_atual = atual_map.get(v.variavel_mestra_id)
            ts = ts_map.get(v.variavel_mestra_id)
            historico = await redis.get_historico(linha_nome, v.variavel_mestra_id)

            status_cls = classificar(
                tipo=v.tipo_variavel_mestra,
                receita=None,           # Snapshot puro não conhece receita
                atual=valor_atual,
                tolerancia=v.tolerancia_variavel_mestra,
            )

            variaveis.append(
                SnapshotVariavel(
                    id=v.variavel_mestra_id,
                    nome=v.nome_variavel_mestra,
                    equip=equip.nome,
                    clp=equip.conexao_opcua_nome or "",
                    tipo=v.tipo_variavel_mestra,
                    unidade=v.unidade_variavel_mestra or "",
                    receita=None,
                    tolerancia=v.tolerancia_variavel_mestra,
                    atual=valor_atual,
                    historico=historico,
                    ultima_leitura_ms=ts,
                    status=status_cls,
                    tag_plc=v.tag_plc,
                )
            )
            if ts is not None and (ultima_atualizacao_ms is None or ts > ultima_atualizacao_ms):
                ultima_atualizacao_ms = ts

    return Snapshot(
        linha=linha_nome,
        opc_online=online,
        ultima_atualizacao_ms=ultima_atualizacao_ms,
        variaveis=variaveis,
    )


# ╔════════════════════════════════════════════════════════════════════╗
# ║ POST /linhas/{nome}/sincronizar                                    ║
# ╚════════════════════════════════════════════════════════════════════╝

@router.post("/sincronizar", response_model=SincronizarResponse)
async def post_sincronizar(
    linha_nome: str,
    body: SincronizarRequest,
    jwt: Annotated[str, Depends(get_operator_jwt)],
) -> SincronizarResponse:
    """
    Repassa o sincronismo para o Django (PATCH /api/recipe-monitor/...).

    O JWT do operador é OBRIGATÓRIO — o Django valida grupo (TIM/Eng/Coord).

    Comportamento:
      - Se o frontend enviar `valor` em cada item, usamos esse valor.
      - Se NÃO enviar, futuramente buscaremos do Redis (último lido).
        Por enquanto (Fase 2), exigimos `valor` em todos os itens.
    """
    # Itens sem `valor` explícito são auto-preenchidos com o último valor
    # lido do Redis. Se a leitura não existir lá (linha sem reader ativo ou
    # tag não monitorada), o item entra com erro 400.
    redis = get_redis_store()
    cached_atual = await redis.get_snapshot_atual(linha_nome)

    variaveis_payload = []
    for item in body.variaveis:
        valor = item.valor
        if valor is None:
            valor = cached_atual.get(item.variavel_id)
        if valor is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Variável id={item.variavel_id} sem 'valor' explícito e "
                    "sem leitura recente no cache. Faça uma leitura primeiro "
                    "ou envie 'valor' no payload."
                ),
            )
        # Django espera strings — todos valores vão como string
        # (FormatoVariavel.valor é CharField).
        variaveis_payload.append({
            "variavel_id": item.variavel_id,
            "valor": _to_django_string(valor),
        })

    try:
        resp = await get_django_client().patch_sincronizar(
            formato_id=body.formato_id,
            linha_nome=linha_nome,
            observacao=body.observacao,
            variaveis=variaveis_payload,
            jwt=jwt,
        )
    except DjangoAPIError as e:
        # Propaga status do Django (403 grupo, 404 formato, 400 body inválido, ...)
        upstream_status = e.status_code or status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=upstream_status, detail=str(e.body or str(e))) from e

    return resp
