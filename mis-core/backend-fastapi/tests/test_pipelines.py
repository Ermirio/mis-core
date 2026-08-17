"""
Testes de pipelines — OFF-mask + agregação kind-aware.

Estes testes são o "garantia escrita" de que Analytics nunca mais vai
exibir uma série "sempre crescente" ou uma média de um contador cumulativo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.core.metrics_catalog import AggregationKind, EquipState, MetricDef, MetricKind
from app.services.pipelines import (
    OffMaskConfig,
    aggregate_series,
    apply_off_mask,
    compute_cp_cpk,
    descriptive_stats,
)


def _make_ts(n=60, start="2026-04-23T00:00:00Z"):
    idx = pd.date_range(start, periods=n, freq="10s", tz="UTC")
    return idx


# ---------------- OFF-mask ----------------
class TestOffMask:
    def test_is_noop_para_lista_vazia(self):
        cfg = OffMaskConfig(exclude_states=[])
        assert cfg.is_noop() is True

    def test_none_usa_default(self):
        cfg = OffMaskConfig(exclude_states=None)
        assert EquipState.FAULT in cfg.effective()

    def test_mascara_nao_altera_se_noop(self):
        idx = _make_ts()
        df = pd.DataFrame({"v": np.arange(60, dtype=float)}, index=idx)
        state = pd.Series([4] * 60, index=idx)   # tudo FAULT
        out = apply_off_mask(df, state, OffMaskConfig(exclude_states=[]))
        pd.testing.assert_frame_equal(out, df)

    def test_mascara_zera_estados_excluidos(self):
        idx = _make_ts(10)
        df = pd.DataFrame({"v": np.arange(10, dtype=float)}, index=idx)
        # primeiros 5 em FAULT (cod=4), últimos 5 em RUNNING (cod=1)
        state = pd.Series([4]*5 + [1]*5, index=idx)
        out = apply_off_mask(df, state, OffMaskConfig())   # default
        assert out["v"].iloc[:5].isna().all()
        assert not out["v"].iloc[5:].isna().any()


# ---------------- Aggregate by kind ----------------
class TestAggregateByKind:
    def test_counter_usa_delta_tolerante_a_reset(self):
        idx = _make_ts(6)     # 60s total, buckets de 30s
        # contador cumulativo com reset no meio
        s = pd.Series([100, 110, 120, 0, 5, 15], index=idx)
        metric = MetricDef(
            name="cnt", influx_field="cnt",
            kind=MetricKind.COUNTER, default_agg=AggregationKind.DELTA,
        )
        out = aggregate_series(s, metric, rule="30s")
        # Primeiro bucket: 100→110→120 = +20
        # Segundo bucket: 0→5→15 = +15 (reset NÃO é contabilizado como negativo)
        assert round(out.iloc[0], 1) == 20.0
        assert round(out.iloc[1], 1) == 15.0

    def test_gauge_usa_mean(self):
        idx = _make_ts(6)
        s = pd.Series([10, 20, 30, 40, 50, 60], index=idx, dtype=float)
        metric = MetricDef(
            name="temp", influx_field="temp",
            kind=MetricKind.GAUGE, default_agg=AggregationKind.MEAN,
        )
        out = aggregate_series(s, metric, rule="30s")
        assert round(out.iloc[0], 1) == 20.0   # mean(10,20,30)
        assert round(out.iloc[1], 1) == 50.0   # mean(40,50,60)


# ---------------- Stats / Cp / Cpk ----------------
class TestStats:
    def test_descriptive_serie_vazia(self):
        out = descriptive_stats(pd.Series([], dtype=float))
        assert out["count"] == 0
        assert out["mean"] == 0.0

    def test_cp_cpk_serie_plana_retorna_none(self):
        s = pd.Series([5.0] * 20)
        cp, cpk = compute_cp_cpk(s, lsl=4.0, usl=6.0)
        assert cp is None and cpk is None, "sigma=0 deve dar None, não inf"

    def test_cp_cpk_processo_centrado(self):
        rng = np.random.default_rng(42)
        s = pd.Series(rng.normal(5.0, 0.1, 1000))   # mu=5, sigma=0.1
        cp, cpk = compute_cp_cpk(s, lsl=4.7, usl=5.3)
        # Cp = (5.3-4.7)/(6*0.1) ≈ 1.0 ; processo centrado => cpk≈cp
        assert 0.8 < cp < 1.2
        assert abs(cpk - cp) < 0.2
