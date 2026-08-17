"""
test_influx_schema.py
=====================

Regression test para BUG-1 da revisão: garante que o FastAPI consulta o
schema InfluxDB que o coletor + Flask realmente gravam.

Schema canônico (definido em backend-flask/routes.py:528-540):
    measurement = "production"
    tags        = { equipment, line, shift, order_id, sku }
    fields      = { velocidade_atual, contagem_saida, refugo_op_acumulado,
                    estado_maquina, oee_realtime, ... (vários por ponto) }

Sem este teste, qualquer mudança que volte a tratar cada métrica como
measurement separada (ex.: `FROM "{field}"`) passa silenciosamente — a UI
recebe DataFrame vazio e o operador acha que o Analytics "não tem dados".
"""
from __future__ import annotations

import re

import pytest

from app.routers.analytics import _fetch_and_aggregate
from app.services.pipelines import OffMaskConfig


class _FakeInflux:
    """Mock que captura a query enviada para validar o schema."""

    def __init__(self):
        self.queries: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        pass

    async def query_df(self, q: str):
        # Pandas DataFrame vazio com a coluna esperada — basta para asserts.
        import pandas as pd
        self.queries.append(q)
        return pd.DataFrame()


@pytest.mark.asyncio
async def test_fetch_uses_production_measurement_and_equipment_tag():
    """
    Garante que `_fetch_and_aggregate`:
      - faz SELECT no measurement "production"
      - filtra pela tag "equipment" (NÃO "equipamento_code")
      - aliasa o field como AS value (mantém parsing estável)
    """
    inf = _FakeInflux()
    off = OffMaskConfig()  # default — vai consultar estado_maquina também

    await _fetch_and_aggregate(
        client=inf,
        equipamento_code="ENV-01-ENCR",
        tag_influx="velocidade_atual",
        t_start_iso="2026-04-25T00:00:00Z",
        t_end_iso="2026-04-26T00:00:00Z",
        rule="1m",
        off_mask=off,
    )

    assert inf.queries, "deveria ter feito ao menos uma query"

    target_q = inf.queries[0]
    # Schema correto: FROM "production" WHERE "equipment"='...'
    assert re.search(r'FROM\s+"production"', target_q), (
        f"query alvo deve ler measurement 'production', got: {target_q!r}"
    )
    assert "\"equipment\"='ENV-01-ENCR'" in target_q, (
        f"query alvo deve filtrar tag 'equipment', got: {target_q!r}"
    )
    assert '"velocidade_atual" AS value' in target_q, (
        f"query alvo deve alias o field como 'AS value', got: {target_q!r}"
    )

    # Como pedimos OFF-mask default e a métrica não é estado_maquina,
    # deve ter sido feita uma segunda query no mesmo schema.
    assert len(inf.queries) == 2, (
        f"esperava 2 queries (alvo + estado_maquina), got: {inf.queries}"
    )
    state_q = inf.queries[1]
    assert '"estado_maquina" AS value' in state_q
    assert 'FROM "production"' in state_q
    assert "\"equipment\"='ENV-01-ENCR'" in state_q


@pytest.mark.asyncio
async def test_fetch_skips_state_query_when_target_is_estado_maquina():
    """
    Self-mask seria absurdo (mascarar estado_maquina pelo próprio estado).
    O _fetch_and_aggregate deve detectar e pular a 2ª query.
    """
    inf = _FakeInflux()
    off = OffMaskConfig()
    await _fetch_and_aggregate(
        client=inf, equipamento_code="ENV-01-ENCR",
        tag_influx="estado_maquina",
        t_start_iso="2026-04-25T00:00:00Z",
        t_end_iso="2026-04-26T00:00:00Z",
        rule="1m", off_mask=off,
    )
    assert len(inf.queries) == 1
    assert '"estado_maquina" AS value' in inf.queries[0]


@pytest.mark.asyncio
async def test_fetch_skips_state_query_when_off_mask_disabled():
    """exclude_states=[] explicit no-op deve pular a query de estado."""
    inf = _FakeInflux()
    off = OffMaskConfig(exclude_states=[])
    await _fetch_and_aggregate(
        client=inf, equipamento_code="ENV-01-ENCR",
        tag_influx="velocidade_atual",
        t_start_iso="2026-04-25T00:00:00Z",
        t_end_iso="2026-04-26T00:00:00Z",
        rule="1m", off_mask=off,
    )
    assert len(inf.queries) == 1
