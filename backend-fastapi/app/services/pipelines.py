"""
app/services/pipelines.py
=========================

Pipelines de agregação kind-aware — o coração do "analytics honesto".

Problema herdado do Flask:
    `query_influx_to_df` tratava todo campo como GAUGE — aplicava MEAN num
    contador cumulativo e produzia gráficos que "sempre sobem". Agora, cada
    métrica passa pelo `metrics_catalog.MetricKind` e recebe a agregação
    apropriada:
        GAUGE    → MEAN (ou quantil pedido)
        COUNTER  → DELTA reset-tolerante
        STATE    → LAST (ou modo dominante)

Fluxo:
    1) consulta Influx em resolução nativa (raw points)
    2) aplica OFF-mask (usando estado_maquina e exclude_states)
    3) resample para granularidade efetiva (TimeRange.effective_granularity)
    4) agrega por kind
    5) devolve DataFrame/Series prontos para serialização
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.core.formulas import counter_delta
from app.core.metrics_catalog import (
    DEFAULT_EXCLUDE_STATES,
    LEGACY_CODE_TO_STATE,
    AggregationKind,
    EquipState,
    MetricDef,
    MetricKind,
    get_metric,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# OFF-MASK — fonte única de verdade
# ==============================================================================
@dataclass(frozen=True)
class OffMaskConfig:
    """
    Configuração do filtro "está parado? então ignora".

    - exclude_states=None     => usa DEFAULT_EXCLUDE_STATES
    - exclude_states=[]       => NÃO filtra nada (comportamento explícito do user)
    - exclude_states=[FAULT]  => filtra apenas esses estados
    """

    exclude_states: list[EquipState] | None = None

    def effective(self) -> set[EquipState]:
        if self.exclude_states is None:
            return set(DEFAULT_EXCLUDE_STATES)
        return set(self.exclude_states)

    def is_noop(self) -> bool:
        return self.exclude_states == []


def apply_off_mask(
    df: pd.DataFrame,
    state_series: pd.Series,
    cfg: OffMaskConfig,
) -> pd.DataFrame:
    """
    Zera (NaN) linhas do `df` em que o equipamento estava em estado excluído.

    `state_series` deve ser uma Series com o código numérico do estado
    (0..13/999), indexada por timestamp. Fazemos forward-fill para alinhar
    com o index do df (um estado vale até o próximo samplings).

    Importante: `df` é devolvido inalterado se cfg.is_noop(). Isso preserva
    a semântica "lista vazia = sem filtro" pedida pelo usuário.
    """
    if cfg.is_noop() or state_series is None or state_series.empty:
        return df

    excluded = cfg.effective()
    if not excluded:
        return df

    # Alinhar estado ao índice do df (forward-fill)
    aligned = state_series.reindex(df.index, method="ffill")
    # Mapear código numérico -> EquipState
    as_state = aligned.map(lambda c: LEGACY_CODE_TO_STATE.get(int(c), EquipState.OTHER)
                           if pd.notna(c) else EquipState.OTHER)
    mask = as_state.isin(excluded)

    out = df.copy()
    # NaN nas linhas filtradas (mantém index — resample depois ignora NaN)
    out.loc[mask] = np.nan
    return out


# ==============================================================================
# AGREGAÇÃO POR KIND
# ==============================================================================
def aggregate_series(
    s: pd.Series,
    metric: MetricDef,
    rule: str,
    agg: AggregationKind | None = None,
    apply_delta: bool = True,
) -> pd.Series:
    """
    Agrega uma série bruta (resolução nativa do Influx) em buckets `rule`
    (ex.: "30s", "1m") respeitando o kind da métrica.

    Regra de ouro por kind:
        GAUGE    -> mean (ou outro se explicitado)
        COUNTER  -> delta (reset-tolerante) — desativável com apply_delta=False
        STATE    -> last
        EVENT    -> count

    [GAP-1] apply_delta=False bypassa o counter_delta para COUNTERs e devolve
    o ÚLTIMO valor por bucket (série acumulada). Caso de uso raro: debug do
    contador puro do PLC. Default True mantém o comportamento correto de EDA.
    """
    if s.empty:
        return s

    rule = _pandas_freq(rule)
    effective_agg = agg or metric.default_agg

    if metric.kind is MetricKind.COUNTER or effective_agg is AggregationKind.DELTA:
        if apply_delta:
            return s.resample(rule).apply(
                lambda chunk: counter_delta(chunk.dropna().tolist()) if not chunk.empty else 0.0
            )
        # apply_delta=False: devolve o último valor por bucket (acumulado).
        return s.resample(rule).last()

    if metric.kind is MetricKind.STATE or effective_agg is AggregationKind.LAST:
        return s.resample(rule).last()

    if metric.kind is MetricKind.EVENT or effective_agg is AggregationKind.COUNT:
        return s.resample(rule).count()

    # GAUGE e outros — despacha pelo enum
    r = s.resample(rule)
    mapping = {
        AggregationKind.MEAN: r.mean,
        AggregationKind.SUM: r.sum,
        AggregationKind.P50: lambda: r.quantile(0.5),
        AggregationKind.P90: lambda: r.quantile(0.9),
        AggregationKind.P99: lambda: r.quantile(0.99),
        AggregationKind.NON_NULL_COUNT: r.count,
    }
    fn = mapping.get(effective_agg, r.mean)
    return fn()


def _pandas_freq(rule: str) -> str:
    """
    Normaliza granularidades da UI para aliases aceitos pelo Pandas atual.

    Influx/Grafana usam "1m", "5m", "10m" para minutos. No Pandas novo, "m"
    foi reservado para month-end, então convertemos para "min".
    """
    normalized = (rule or "1min").strip()
    minute_aliases = {
        "1m": "1min",
        "5m": "5min",
        "10m": "10min",
        "15m": "15min",
        "30m": "30min",
    }
    return minute_aliases.get(normalized, normalized)


def resolve_metric(name: str) -> MetricDef:
    """Resolve o nome da métrica, lançando erro claro se desconhecida."""
    m = get_metric(name)
    if not m:
        # Fallback permissivo: assume GAUGE/MEAN para compat com variáveis
        # ainda não catalogadas (não queremos quebrar a UI).
        return MetricDef(
            name=name,
            influx_field=name,
            kind=MetricKind.GAUGE,
            default_agg=AggregationKind.MEAN,
        )
    return m


# ==============================================================================
# DESCRIPTIVE STATS — para o painel EDA
# ==============================================================================
def descriptive_stats(s: pd.Series) -> dict[str, float | int | None]:
    """
    Retorna estatísticas descritivas prontas para a UI.
    NaN-aware, robusto a séries vazias (retorna zeros/None).
    """
    clean = pd.to_numeric(s, errors="coerce").dropna()
    n = int(clean.size)
    if n == 0:
        return {
            "count": 0, "mean": 0.0, "std": 0.0,
            "min": 0.0, "max": 0.0,
            "median": 0.0, "p90": 0.0, "p99": 0.0,
        }
    return {
        "count": n,
        "mean": float(clean.mean()),
        "std": float(clean.std(ddof=0)) if n > 1 else 0.0,
        "min": float(clean.min()),
        "max": float(clean.max()),
        "median": float(clean.median()),
        "p90": float(clean.quantile(0.9)),
        "p99": float(clean.quantile(0.99)),
    }


def compute_cp_cpk(s: pd.Series, lsl: float | None, usl: float | None) -> tuple[float | None, float | None]:
    """
    Cp  = (USL - LSL) / (6σ)
    Cpk = min( (USL - μ)/3σ, (μ - LSL)/3σ )

    None quando faltam limites ou σ=0 (série plana / amostra única).
    """
    clean = pd.to_numeric(s, errors="coerce").dropna()
    if clean.size < 2 or lsl is None or usl is None or usl <= lsl:
        return None, None
    sigma = float(clean.std(ddof=1))
    if sigma <= 0:
        return None, None
    mu = float(clean.mean())
    cp = (usl - lsl) / (6.0 * sigma)
    cpk = min((usl - mu) / (3.0 * sigma), (mu - lsl) / (3.0 * sigma))
    return float(cp), float(cpk)


__all__ = [
    "OffMaskConfig",
    "apply_off_mask",
    "aggregate_series",
    "resolve_metric",
    "descriptive_stats",
    "compute_cp_cpk",
]
