"""Regression tests for line-scoped production identity.

MIS Core reuses equipment codes (E001, E002, ...) across production lines.
Every line endpoint therefore has to filter InfluxDB by both tags.
"""

from __future__ import annotations

import pytest

from app.routers import production


class _FakeInflux:
    queries: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def query_raw(self, query: str):
        self.queries.append(query)
        return {
            "results": [{
                "series": [{
                    "columns": ["time", "estado_maquina"],
                    "values": [[1787166806124, 1]],
                }]
            }]
        }


@pytest.mark.asyncio
async def test_latest_point_filters_equipment_and_line(monkeypatch):
    _FakeInflux.queries = []
    monkeypatch.setattr(production, "InfluxAsyncClient", _FakeInflux)

    point = await production._latest_production_point("E001", line_code="L20")

    assert point == {"time": 1787166806124, "estado_maquina": 1}
    assert len(_FakeInflux.queries) == 1
    query = _FakeInflux.queries[0]
    assert '"equipment" = \'E001\'' in query
    assert '"line" = \'L20\'' in query
    assert "ORDER BY time DESC LIMIT 1" in query


@pytest.mark.asyncio
async def test_latest_points_preserves_line_scope_for_reused_codes(monkeypatch):
    calls: list[tuple[str, str | None]] = []

    async def fake_latest(code: str, *, line_code: str | None = None):
        calls.append((code, line_code))
        return {"time": 1787166806124, "estado_maquina": 1}

    monkeypatch.setattr(production, "_latest_production_point", fake_latest)

    points = await production._latest_points(["E001", "E002"], line_code="L15")

    assert set(points) == {"E001", "E002"}
    assert calls == [("E001", "L15"), ("E002", "L15")]


def test_freshness_prefers_ingestion_timestamp_over_lagging_opc_time(monkeypatch):
    now = production.datetime.now(production.timezone.utc).timestamp()
    point = {
        "time": int((now - 3600) * 1000),
        "timestamp_medicao": now - 30,
    }

    assert production._is_fresh(point, max_age_s=300)


@pytest.mark.asyncio
async def test_equipment_endpoint_neutralizes_stale_operational_values(monkeypatch):
    stale_ts = production.datetime.now(production.timezone.utc).timestamp() - 3600

    async def fake_latest(code: str, *, line_code: str | None = None):
        return {
            "time": int(stale_ts * 1000),
            "timestamp_medicao": stale_ts,
            "velocidade_atual": 282,
            "estado_maquina": 1,
            "oee_realtime": 91,
        }

    monkeypatch.setattr(production, "_latest_production_point", fake_latest)

    result = await production.get_equipamento_dados("E001", linha="L06")

    assert result["comunicacao_online"] is False
    assert result["estado_atual"] == "Offline"
    assert result["velocidade_atual"] == 0
    assert result["oee_atual"] == 0
    assert result["data_age_s"] >= 3599


@pytest.mark.asyncio
async def test_equipment_endpoint_preserves_fresh_zero_speed(monkeypatch):
    now = production.datetime.now(production.timezone.utc).timestamp()

    async def fake_latest(code: str, *, line_code: str | None = None):
        return {
            "time": int(now * 1000),
            "timestamp_medicao": now,
            "velocidade_atual": 0.0,
            "estado_maquina": 4,
        }

    monkeypatch.setattr(production, "_latest_production_point", fake_latest)

    result = await production.get_equipamento_dados("E001", linha="L06")

    assert result["comunicacao_online"] is True
    assert result["estado_atual"] == "Parado/Falha"
    assert result["velocidade_atual"] == 0
