"""
app/schemas/analytics.py
========================

Contratos dos endpoints /analytics — requests e responses com validação
via Pydantic v2 (inputs hostis são rejeitados com 422, sem 500 no servidor).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from app.core.metrics_catalog import EquipState
from app.schemas.time_range import TimeRange


# ----------------------------------------------------------------------
# Request — trends / timeseries / stats
# ----------------------------------------------------------------------
class VariableRef(BaseModel):
    """Referência a uma métrica consultada (por tag InfluxDB + equipamento)."""
    model_config = ConfigDict(extra="forbid")

    tag_influx: str = Field(..., min_length=1, max_length=64)
    equipamento_code: str = Field(..., min_length=1, max_length=32)
    alias: str | None = None
    lsl: float | None = None       # limite inferior de especificação (Cp/Cpk)
    usl: float | None = None       # limite superior
    nominal: float | None = None


class AnalyticsQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variables: list[VariableRef] = Field(..., min_length=1, max_length=25)
    time_range: TimeRange
    exclude_states: list[EquipState] | None = Field(
        default=None,
        description=(
            "Estados a excluir da análise (OFF-mask). None = default; "
            "[] = sem filtro; lista = estados a excluir."
        ),
    )
    # [GAP-1] aceito também o atalho `ignore_off` (bool) que o frontend POC
    # manda. Quando False, equivale a exclude_states=[].
    ignore_off: bool | None = Field(
        default=None,
        description=(
            "Atalho: False força exclude_states=[] (não filtra). True ou None "
            "preserva exclude_states (default ou explícito). Compat com frontend."
        ),
    )
    # [GAP-1] controla o DELTA em contadores acumulativos. True (default) é o
    # comportamento correto; False devolve a série bruta (uso raro de debug).
    apply_delta: bool = Field(
        default=True,
        description="Aplica delta reset-tolerante em métricas COUNTER. Padrão True.",
    )

    def effective_exclude_states(self) -> list[EquipState] | None:
        """Resolve exclude_states final considerando o atalho ignore_off."""
        if self.ignore_off is False:
            return []
        return self.exclude_states


class CorrelationQuery(AnalyticsQuery):
    method: str = Field(default="pearson", pattern="^(pearson|spearman)$")


# ----------------------------------------------------------------------
# Response — stats
# ----------------------------------------------------------------------
class DescriptiveStats(BaseModel):
    mean: float
    std: float
    min: float
    max: float
    median: float
    p90: float
    p99: float
    count: int
    cp: float | None = None
    cpk: float | None = None


class HistogramBin(BaseModel):
    counts: list[int]
    bins: list[float]


class VariableStatsResult(BaseModel):
    variable: str
    n_unique: int
    is_discrete: bool
    stats: DescriptiveStats
    histogram: HistogramBin


# ----------------------------------------------------------------------
# Response — timeseries
# ----------------------------------------------------------------------
class TimeSeriesPoint(BaseModel):
    timestamps: list[str]
    values: list[float | None]
    stats: dict[str, float | None]       # mean, std, ucl, lcl, lsl, usl, nominal


# ----------------------------------------------------------------------
# Response — correlation
# ----------------------------------------------------------------------
class CorrelationMatrix(BaseModel):
    columns: list[str]
    values: list[list[float]]
    p_values: list[list[float]]
    method: str
    n_points: int
    resample_rule: str


class CorrelationResponse(BaseModel):
    correlation_matrix: CorrelationMatrix
    scatter_data: dict[str, Any]


__all__ = [
    "VariableRef",
    "AnalyticsQuery",
    "CorrelationQuery",
    "DescriptiveStats",
    "HistogramBin",
    "VariableStatsResult",
    "TimeSeriesPoint",
    "CorrelationMatrix",
    "CorrelationResponse",
]
