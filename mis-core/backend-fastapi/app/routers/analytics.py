"""
app/routers/analytics.py
========================

Endpoints /api/v2/analytics — EDA científica (stats, timeseries, correlação).

Estes endpoints são o "cérebro de cientista de dados" do core. Eles
substituem progressivamente o blueprints/analytics.py do Flask, mas
mantêm contratos compatíveis para permitir migração incremental via
Strangler Pattern (frontend pode chamar /api/analytics/* OU /api/v2/analytics/*).

Garantias que o Flask legado não dava:
    - OFF-mask sempre aplicado (exclude_states com default seguro)
    - Counter-deltas reset-tolerantes (via pipelines.aggregate_series)
    - TimeRange datetime-based com granularidade auto (Grafana-style)
    - Validação estrita de entrada (Pydantic v2 -> 422 em vez de 500)
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, status
from scipy import stats as scipy_stats

from app.config import get_settings
from app.core.metrics_catalog import MetricKind
from app.schemas.analytics import (
    AnalyticsQuery,
    CorrelationMatrix,
    CorrelationQuery,
    CorrelationResponse,
    DescriptiveStats,
    HistogramBin,
    TimeSeriesPoint,
    VariableStatsResult,
)
from app.services.influx import InfluxAsyncClient, InfluxQueryError
from app.services.pipelines import (
    OffMaskConfig,
    aggregate_series,
    apply_off_mask,
    compute_cp_cpk,
    descriptive_stats,
    resolve_metric,
)

logger = logging.getLogger(__name__)
# COMPAT: mantemos o prefixo "/analyze" para espelhar o Flask legado
# (blueprints/analytics.py registra /analyze/stats, /analyze/correlation,
# /analyze/timeseries). Assim, o frontend migra trocando apenas a BASE_URL
# de /api -> /api/v2 — sem tocar nos path.
router = APIRouter(prefix="/analyze", tags=["analyze"])


# ----------------------------------------------------------------------
# Query helper — fetch + OFF-mask + aggregate (o coração comum)
# ----------------------------------------------------------------------
async def _fetch_and_aggregate(
    client: InfluxAsyncClient,
    equipamento_code: str,
    tag_influx: str,
    t_start_iso: str,
    t_end_iso: str,
    rule: str,
    off_mask: OffMaskConfig,
    apply_delta: bool = True,
) -> pd.Series:
    """
    Consulta Influx na resolução nativa, aplica OFF-mask via estado_maquina,
    e agrega por kind. Devolve Series indexada por timestamp.

    Schema InfluxDB (BUG-1 fix): o coletor + Flask gravam tudo numa ÚNICA
    measurement chamada `production`, com cada métrica como FIELD e o código
    do equipamento como TAG `equipment` (ver backend-flask/routes.py:528-540).
    Antes este método consultava `FROM "{metric.influx_field}"` tratando cada
    métrica como measurement separada — devolvia SEMPRE vazio em produção.
    """
    metric = resolve_metric(tag_influx)
    field = metric.influx_field

    # 1) série alvo (raw) — usa alias AS value para padronizar o parsing
    q_target = (
        f'SELECT "{field}" AS value FROM "production" '
        f"WHERE \"equipment\"='{equipamento_code}' "
        f"AND time >= '{t_start_iso}' AND time <= '{t_end_iso}'"
    )
    df_target = await client.query_df(q_target)
    if df_target.empty or "value" not in df_target.columns:
        return pd.Series(dtype=float)

    s_target = pd.to_numeric(df_target["value"], errors="coerce")

    # 2) série de estado para mask (apenas se vamos filtrar e se a métrica
    #    NÃO é o próprio estado — senão geramos self-mask)
    if not off_mask.is_noop() and field != "estado_maquina":
        q_state = (
            'SELECT "estado_maquina" AS value FROM "production" '
            f"WHERE \"equipment\"='{equipamento_code}' "
            f"AND time >= '{t_start_iso}' AND time <= '{t_end_iso}'"
        )
        df_state = await client.query_df(q_state)
        if not df_state.empty and "value" in df_state.columns:
            state_series = pd.to_numeric(df_state["value"], errors="coerce")
            df_masked = apply_off_mask(
                s_target.to_frame(name="value"),
                state_series,
                off_mask,
            )
            s_target = df_masked["value"]

    # 3) agregação por kind/rule
    return aggregate_series(s_target, metric, rule=rule, apply_delta=apply_delta)


# ======================================================================
# POST /analytics/stats  — EDA descritiva (média, mediana, quantis, Cp/Cpk)
# ======================================================================
@router.post("/stats", response_model=list[VariableStatsResult])
async def analytics_stats(query: AnalyticsQuery) -> list[VariableStatsResult]:
    s_cfg = get_settings()
    if len(query.variables) > s_cfg.max_correlation_variables:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"max {s_cfg.max_correlation_variables} variables per request",
        )

    t_start = query.time_range.start.isoformat()
    t_end = query.time_range.end.isoformat()
    rule = query.time_range.effective_granularity()
    off_mask = OffMaskConfig(exclude_states=query.effective_exclude_states())

    results: list[VariableStatsResult] = []
    async with InfluxAsyncClient() as influx:
        for var in query.variables:
            try:
                s = await _fetch_and_aggregate(
                    influx,
                    var.equipamento_code,
                    var.tag_influx,
                    t_start,
                    t_end,
                    rule,
                    off_mask,
                    apply_delta=query.apply_delta,
                )
            except InfluxQueryError as e:
                logger.warning("stats: influx error for %s/%s: %s",
                               var.equipamento_code, var.tag_influx, e)
                s = pd.Series(dtype=float)

            stats_dict = descriptive_stats(s)
            cp, cpk = compute_cp_cpk(s, var.lsl, var.usl)
            stats_dict["cp"] = cp
            stats_dict["cpk"] = cpk

            # Histograma (se houver dados)
            clean = pd.to_numeric(s, errors="coerce").dropna()
            if clean.size:
                counts, bins = np.histogram(clean, bins=min(30, max(5, int(np.sqrt(clean.size)))))
                hist = HistogramBin(counts=counts.tolist(), bins=bins.tolist())
            else:
                hist = HistogramBin(counts=[], bins=[])

            results.append(VariableStatsResult(
                variable=var.alias or f"{var.equipamento_code}:{var.tag_influx}",
                n_unique=int(clean.nunique()) if clean.size else 0,
                is_discrete=bool(clean.size and clean.nunique() <= 10),
                stats=DescriptiveStats(**stats_dict),
                histogram=hist,
            ))

    return results


# ======================================================================
# POST /analytics/timeseries  — série agregada (para gráficos)
# ======================================================================
@router.post("/timeseries", response_model=dict[str, TimeSeriesPoint])
async def analytics_timeseries(query: AnalyticsQuery) -> dict[str, TimeSeriesPoint]:
    t_start = query.time_range.start.isoformat()
    t_end = query.time_range.end.isoformat()
    rule = query.time_range.effective_granularity()
    off_mask = OffMaskConfig(exclude_states=query.effective_exclude_states())

    out: dict[str, TimeSeriesPoint] = {}
    async with InfluxAsyncClient() as influx:
        for var in query.variables:
            alias = var.alias or f"{var.equipamento_code}:{var.tag_influx}"
            try:
                s = await _fetch_and_aggregate(
                    influx, var.equipamento_code, var.tag_influx,
                    t_start, t_end, rule, off_mask,
                    apply_delta=query.apply_delta,
                )
            except InfluxQueryError as e:
                logger.warning("timeseries: %s", e)
                s = pd.Series(dtype=float)

            # Control limits: média ± 3σ (Shewhart)
            clean = pd.to_numeric(s, errors="coerce").dropna()
            mean = float(clean.mean()) if clean.size else None
            std = float(clean.std(ddof=0)) if clean.size > 1 else None
            ucl = mean + 3 * std if (mean is not None and std) else None
            lcl = mean - 3 * std if (mean is not None and std) else None

            out[alias] = TimeSeriesPoint(
                timestamps=[t.isoformat() for t in s.index] if not s.empty else [],
                values=[None if pd.isna(v) else float(v) for v in s.values],
                stats={
                    "mean": mean, "std": std, "ucl": ucl, "lcl": lcl,
                    "lsl": var.lsl, "usl": var.usl, "nominal": var.nominal,
                },
            )

    return out


# ======================================================================
# POST /analytics/correlation  — matriz + scatter
# ======================================================================
@router.post("/correlation", response_model=CorrelationResponse)
async def analytics_correlation(query: CorrelationQuery) -> CorrelationResponse:
    s_cfg = get_settings()
    if len(query.variables) > s_cfg.max_correlation_variables:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"max {s_cfg.max_correlation_variables} variables per request",
        )
    if len(query.variables) < 2:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "correlation needs at least 2 variables",
        )

    t_start = query.time_range.start.isoformat()
    t_end = query.time_range.end.isoformat()
    rule = query.time_range.effective_granularity()
    off_mask = OffMaskConfig(exclude_states=query.effective_exclude_states())

    frames: dict[str, pd.Series] = {}
    async with InfluxAsyncClient() as influx:
        for var in query.variables:
            alias = var.alias or f"{var.equipamento_code}:{var.tag_influx}"
            try:
                s = await _fetch_and_aggregate(
                    influx, var.equipamento_code, var.tag_influx,
                    t_start, t_end, rule, off_mask,
                    apply_delta=query.apply_delta,
                )
            except InfluxQueryError:
                s = pd.Series(dtype=float)
            frames[alias] = s

    if not frames or all(s.empty for s in frames.values()):
        return CorrelationResponse(
            correlation_matrix=CorrelationMatrix(
                columns=list(frames.keys()),
                values=[], p_values=[],
                method=query.method, n_points=0, resample_rule=rule,
            ),
            scatter_data={},
        )

    df = pd.DataFrame(frames).dropna(how="all").dropna()
    cols = df.columns.tolist()
    n = len(cols)

    values = [[1.0] * n for _ in range(n)]
    p_values = [[0.0] * n for _ in range(n)]

    corr_fn = scipy_stats.pearsonr if query.method == "pearson" else scipy_stats.spearmanr
    for i in range(n):
        for j in range(i + 1, n):
            xi, xj = df[cols[i]].to_numpy(), df[cols[j]].to_numpy()
            if xi.size < 3 or np.std(xi) == 0 or np.std(xj) == 0:
                r, p = float("nan"), float("nan")
            else:
                r, p = corr_fn(xi, xj)
            values[i][j] = values[j][i] = float(r)
            p_values[i][j] = p_values[j][i] = float(p)

    scatter_data = {c: df[c].tolist() for c in cols}

    return CorrelationResponse(
        correlation_matrix=CorrelationMatrix(
            columns=cols, values=values, p_values=p_values,
            method=query.method, n_points=len(df), resample_rule=rule,
        ),
        scatter_data=scatter_data,
    )


__all__ = ["router"]
