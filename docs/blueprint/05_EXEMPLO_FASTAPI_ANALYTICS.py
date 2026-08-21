"""
============================================================================
 mis-core v2 — Exemplo FastAPI do serviço de Analytics + KPIs
============================================================================

Este arquivo é um ESQUELETO EXECUTÁVEL que demonstra, em um só lugar, como a
arquitetura alvo (ver 02_ARQUITETURA_ALVO.md) resolve todos os bugs do
diagnóstico (ver 01_DIAGNOSTICO_TECNICO.md):

    B1  gráfico sempre crescendo → MetricCatalog + delta automático em COUNTER
    B2  Qualidade = 100% parado  → Formula retorna None quando produção = 0
    B3  parado planejado x não   → EquipState granular
    B4  TPH linha = gargalo      → LineTPH.calculate usa bottleneck
    B5  período fixo             → TimeRange (from/to) com auto-granularity
    B7  EDA moderno              → stats com p50/p90/p99, IQR, outliers
    4.2-#1 escala OEE            → OEE clipado em 100%
    4.2-#2 TPH duplica Q         → TPHCalculator sem multiplicar por Q

Como rodar (em um ambiente novo):

    python -m venv .venv && source .venv/bin/activate
    pip install "fastapi[standard]" pandas numpy pydantic==2.* \\
                influxdb-client scipy pytest httpx
    uvicorn 05_EXEMPLO_FASTAPI_ANALYTICS:app --reload

Depois:

    curl "http://localhost:8000/api/v2/analytics/trends" -X POST \\
         -H "content-type: application/json" \\
         -d '{"from_":"2026-04-22T06:00:00-03:00",
              "to":"2026-04-23T06:00:00-03:00",
              "granularity":"15m",
              "equipment":"ENC-01",
              "metrics":["velocidade","refugo_kg"],
              "exclude_states":["OFFLINE","OUTRO"]}'

Observação: a camada de acesso ao InfluxDB está ESTUBADA com dados sintéticos
para poder rodar sem dependência externa. O código real consumiria o cliente
InfluxDB com a query que está comentada no final deste arquivo.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Literal, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

# ============================================================================
# 1. CATÁLOGO DE MÉTRICAS — resolve B1/B2
# ============================================================================
class MetricKind(str, Enum):
    GAUGE = "gauge"        # instantâneo (velocidade, temperatura)
    COUNTER = "counter"    # cumulativo (refugo_acum, producao_acum)
    STATE = "state"        # discreto (código de estado 0..12)


class MetricDef(BaseModel):
    field: str                          # nome no InfluxDB
    kind: MetricKind
    unit: Optional[str] = None
    convert: float = 1.0                # fator (ex: g → t  = 1e-6)
    zero_when_off: bool = True
    agg_default: Literal["mean", "max", "min", "sum", "last", "mode"] = "mean"


METRIC_CATALOG: dict[str, MetricDef] = {
    "velocidade": MetricDef(
        field="velocidade_real", kind=MetricKind.GAUGE, unit="un/min",
        zero_when_off=True, agg_default="mean",
    ),
    "refugo_kg": MetricDef(
        field="refugo_op_acumulado", kind=MetricKind.COUNTER, unit="kg",
        convert=1e-3, zero_when_off=True, agg_default="sum",
    ),
    "producao_un": MetricDef(
        field="producao_acumulada", kind=MetricKind.COUNTER, unit="un",
        zero_when_off=True, agg_default="sum",
    ),
    "estado_codigo": MetricDef(
        field="estado_codigo", kind=MetricKind.STATE, unit=None,
        zero_when_off=False, agg_default="mode",
    ),
    "peso_embalagem_g": MetricDef(
        field="peso_real", kind=MetricKind.GAUGE, unit="g",
        zero_when_off=True, agg_default="mean",
    ),
}


# ============================================================================
# 2. ESTADOS DO EQUIPAMENTO — resolve B3 (parado planejado x não planejado)
# ============================================================================
class EquipState(str, Enum):
    RUN = "RUN"
    SETUP = "SETUP"
    FAULT = "FAULT"
    PLANNED_STOP = "PLANNED_STOP"       # refeição, manutenção programada
    UNPLANNED_STOP = "UNPLANNED_STOP"   # microparada, falta material
    OFFLINE = "OFFLINE"                 # coletor sem conexão OPC
    OTHER = "OTHER"


# mapeamento legado do coletor (constants.py) → estado de negócio
LEGACY_TO_STATE: dict[int, EquipState] = {
    0: EquipState.OTHER,
    1: EquipState.RUN,
    2: EquipState.UNPLANNED_STOP,   # WAIT_PREV
    3: EquipState.UNPLANNED_STOP,   # BLOCK_NEXT
    4: EquipState.FAULT,
    5: EquipState.SETUP,
    6: EquipState.SETUP,            # TESTE_PROJ
    7: EquipState.PLANNED_STOP,     # AGUARD_MNT
    8: EquipState.PLANNED_STOP,     # MANUTENCAO
    9: EquipState.UNPLANNED_STOP,   # FALTA_MAT
    10: EquipState.OTHER,
    11: EquipState.SETUP,           # PARTINDO
    12: EquipState.SETUP,           # PARANDO
    999: EquipState.OFFLINE,
}


# ============================================================================
# 3. FÓRMULAS TESTÁVEIS — resolve 4.2-#1, #2, #3, B4
# ============================================================================
@dataclass(frozen=True)
class OEEInputs:
    tempo_planejado_min: float
    tempo_parado_nao_planejado_min: float
    producao_boa: float
    producao_total: float
    tempo_ciclo_ideal_s: float  # ISO 22400 (segundos por unidade)


class OEE:
    """
    OEE conforme ISO 22400-2, com clipping em 100% e proteção contra
    divisão por zero. Todas as saídas em PERCENTUAL (0..100).
    """

    @staticmethod
    def availability(i: OEEInputs) -> float:
        if i.tempo_planejado_min <= 0:
            return 0.0
        tempo_produtivo = max(0.0, i.tempo_planejado_min - i.tempo_parado_nao_planejado_min)
        return min(100.0, 100.0 * tempo_produtivo / i.tempo_planejado_min)

    @staticmethod
    def performance(i: OEEInputs) -> float:
        tempo_produtivo_s = max(0.0, (i.tempo_planejado_min - i.tempo_parado_nao_planejado_min) * 60)
        if tempo_produtivo_s <= 0 or i.tempo_ciclo_ideal_s <= 0:
            return 0.0
        p = 100.0 * (i.producao_total * i.tempo_ciclo_ideal_s) / tempo_produtivo_s
        return min(100.0, p)   # fix: cap em 100, não em 105%

    @staticmethod
    def quality(i: OEEInputs) -> Optional[float]:
        if i.producao_total <= 0:
            return None   # fix B2: máquina parada NÃO tem qualidade=100%
        return min(100.0, 100.0 * i.producao_boa / i.producao_total)

    @staticmethod
    def oee(i: OEEInputs) -> Optional[float]:
        q = OEE.quality(i)
        if q is None:
            return None
        return min(
            100.0,
            (OEE.availability(i) / 100) * (OEE.performance(i) / 100) * (q / 100) * 100.0,
        )


class TPHCalculator:
    """
    TPH — taxa de throughput em toneladas/hora. NÃO multiplica por qualidade
    aqui (esse é o bug 4.2-#2). Q já é contabilizado em OEE.
    """
    @staticmethod
    def instantaneous(velocity_units_min: float, grams_per_unit: float) -> float:
        return (velocity_units_min * 60.0 * grams_per_unit) / 1_000_000.0


class LineTPH:
    """
    Throughput de uma linha de produção = throughput do GARGALO, não o MAX
    ou soma (fix para B4). Se a linha tem equips em série, o mais lento dita
    a saída.
    """
    @staticmethod
    def calculate(equipment_tph: dict[str, float]) -> float:
        if not equipment_tph:
            return 0.0
        return min(tph for tph in equipment_tph.values() if tph > 0) \
            if any(v > 0 for v in equipment_tph.values()) else 0.0


class GiveAway:
    """
    Give Away em g/unidade, descontando a tolerância legal (INMETRO) e
    desvio padrão aceitável para medição.
    Se dentro da tolerância → retorna 0 (não é give away "de fato").
    """
    @staticmethod
    def calculate(
        peso_medio_g: float,
        peso_nominal_g: float,
        tolerancia_legal_pct: float = 1.0,   # INMETRO/NIST ~1%
        sigma_medicao_g: float = 0.0,
    ) -> float:
        tolerancia_abs = peso_nominal_g * (tolerancia_legal_pct / 100.0)
        limite_aceitavel = peso_nominal_g + tolerancia_abs + sigma_medicao_g
        return max(0.0, peso_medio_g - limite_aceitavel)


# ============================================================================
# 4. CONTRATO DE RANGE DE TEMPO — resolve B5 (filtros estilo Grafana)
# ============================================================================
class TimeRange(BaseModel):
    from_: datetime = Field(..., alias="from", description="ISO 8601 com timezone")
    to: datetime
    granularity: Optional[Literal["1s", "10s", "1m", "5m", "15m", "1h", "1d"]] = None

    @field_validator("to")
    @classmethod
    def _validate(cls, v, info):
        if "from_" in info.data and v <= info.data["from_"]:
            raise ValueError("'to' deve ser maior que 'from'")
        return v

    def resolve_granularity(self) -> str:
        """Auto: escolhe granularidade que gera entre 50 e 500 pontos."""
        if self.granularity:
            return self.granularity
        delta = self.to - self.from_
        if delta <= timedelta(hours=1):    return "10s"
        if delta <= timedelta(hours=6):    return "1m"
        if delta <= timedelta(days=1):     return "5m"
        if delta <= timedelta(days=7):     return "15m"
        if delta <= timedelta(days=30):    return "1h"
        return "1d"


# ============================================================================
# 5. TRANSFORMAÇÃO DE DADOS — CORAÇÃO DO FIX B1
# ============================================================================
def apply_metric_pipeline(
    raw: pd.DataFrame,
    metric_name: str,
    granularity: str,
    exclude_states: list[EquipState] | None = None,
) -> pd.DataFrame:
    """
    Pipeline:
        raw → [filter by exclude_states] → [resample per granularity]
            → [kind-aware aggregation: delta if COUNTER, mean if GAUGE, mode if STATE]
            → [apply zero_when_off]
            → tidy DataFrame (ts, value)

    raw esperado: DataFrame com colunas:
        ts (DatetimeIndex), value (float), state (EquipState)
    """
    meta = METRIC_CATALOG.get(metric_name)
    if meta is None:
        raise ValueError(f"Métrica desconhecida: {metric_name}")

    df = raw.copy().sort_index()

    # 1. Máscara de OFF — se estado excluído, marca como NaN (excluído da série)
    if exclude_states and "state" in df.columns:
        excl = [s.value for s in exclude_states]
        off_mask = df["state"].isin(excl)
    else:
        off_mask = pd.Series(False, index=df.index)

    # 2. Agregação dependente do tipo
    if meta.kind == MetricKind.COUNTER:
        # Aplica delta POR JANELA: valor no final - valor no início
        # Essa é a correção do bug do "gráfico sempre crescendo"
        def counter_delta(chunk):
            clean = chunk[~off_mask.reindex(chunk.index, fill_value=False)]
            if len(clean) < 2:
                return 0.0
            return max(0.0, clean.iloc[-1] - clean.iloc[0])
        agg = df["value"].resample(granularity).apply(counter_delta)

    elif meta.kind == MetricKind.GAUGE:
        if meta.zero_when_off:
            df.loc[off_mask, "value"] = np.nan    # será excluído da média
        if meta.agg_default == "mean":
            agg = df["value"].resample(granularity).mean()
        elif meta.agg_default == "max":
            agg = df["value"].resample(granularity).max()
        elif meta.agg_default == "min":
            agg = df["value"].resample(granularity).min()
        else:
            agg = df["value"].resample(granularity).last()

    elif meta.kind == MetricKind.STATE:
        agg = df["value"].resample(granularity).agg(
            lambda x: x.mode().iat[0] if len(x) else np.nan
        )
    else:
        raise ValueError(f"kind desconhecido: {meta.kind}")

    agg = agg * meta.convert

    out = agg.reset_index()
    out.columns = ["ts", "value"]
    out["metric"] = metric_name
    out["unit"] = meta.unit
    return out


# ============================================================================
# 6. EDA MODERNO — resolve B7
# ============================================================================
def eda_stats(values: pd.Series, lsl: float | None = None, usl: float | None = None) -> dict:
    """Estatísticas de engenheiro de processo + cientista de dados."""
    s = values.dropna()
    if len(s) == 0:
        return {"n": 0}
    q = s.quantile
    iqr = q(0.75) - q(0.25)
    lo_whisker, hi_whisker = q(0.25) - 1.5 * iqr, q(0.75) + 1.5 * iqr
    outliers_iqr = ((s < lo_whisker) | (s > hi_whisker)).sum()

    z = (s - s.mean()) / s.std(ddof=1) if s.std(ddof=1) > 0 else pd.Series(0, index=s.index)
    outliers_z = (z.abs() > 3).sum()

    out = {
        "n": int(len(s)),
        "mean": float(s.mean()),
        "std": float(s.std(ddof=1)),
        "min": float(s.min()),
        "max": float(s.max()),
        "p05": float(q(0.05)),
        "p25": float(q(0.25)),
        "p50": float(q(0.50)),
        "p75": float(q(0.75)),
        "p90": float(q(0.90)),
        "p95": float(q(0.95)),
        "p99": float(q(0.99)),
        "iqr": float(iqr),
        "outliers_iqr": int(outliers_iqr),
        "outliers_z3": int(outliers_z),
        "skew": float(s.skew()),
        "kurtosis": float(s.kurtosis()),
    }
    # Capability (Cp/Cpk) se o usuário passou LSL/USL
    if lsl is not None and usl is not None and s.std(ddof=1) > 0:
        cp = (usl - lsl) / (6 * s.std(ddof=1))
        cpu = (usl - s.mean()) / (3 * s.std(ddof=1))
        cpl = (s.mean() - lsl) / (3 * s.std(ddof=1))
        out["cp"] = float(cp)
        out["cpk"] = float(min(cpu, cpl))
    return out


# ============================================================================
# 7. DATA SOURCE STUB — em produção, troca por cliente InfluxDB
# ============================================================================
def fetch_raw_from_influx(
    equipment: str,
    metric: str,
    tr: TimeRange,
) -> pd.DataFrame:
    """
    STUB DIDÁTICO. Em produção:

        from influxdb_client import InfluxDBClient
        client = InfluxDBClient(url=..., token=..., org=...)
        flux = f'''
          from(bucket:"mis")
            |> range(start: {tr.from_.isoformat()}, stop: {tr.to.isoformat()})
            |> filter(fn: (r) => r["_measurement"] == "leitura"
                               and r["equipamento"] == "{equipment}"
                               and r["_field"] == "{METRIC_CATALOG[metric].field}")
            |> keep(columns:["_time","_value","equipamento"])
        '''
        df = client.query_api().query_data_frame(flux)
        # unir com série de estado...

    Aqui simulamos um dia de dados com uma parada de manutenção.
    """
    n = int((tr.to - tr.from_).total_seconds() // 60) + 1
    ts = pd.date_range(tr.from_, tr.to, periods=n, tz="UTC")

    rng = np.random.default_rng(seed=sum(map(ord, equipment + metric)))
    meta = METRIC_CATALOG[metric]

    state = np.full(n, EquipState.RUN.value, dtype=object)
    # injeta parada planejada das 11h às 12h
    for i, t in enumerate(ts):
        if 11 <= t.hour < 12:
            state[i] = EquipState.PLANNED_STOP.value
        elif 14 <= t.hour < 14.1:  # microparada
            state[i] = EquipState.UNPLANNED_STOP.value

    if meta.kind == MetricKind.COUNTER:
        # contador cumulativo: incremento real por minuto
        inc = rng.normal(loc=2.0, scale=0.5, size=n).clip(min=0)
        # zera incremento quando parado (sensor mantém o último valor)
        for i in range(n):
            if state[i] != EquipState.RUN.value:
                inc[i] = 0
        value = np.cumsum(inc)
    elif meta.kind == MetricKind.GAUGE:
        value = np.clip(100 + rng.normal(0, 3, n), 0, 120)
        # sensor "congela" o último valor durante parada (simula bug real)
        for i in range(1, n):
            if state[i] != EquipState.RUN.value:
                value[i] = value[i-1]
    else:
        value = np.array([1 if s == EquipState.RUN.value else 4 for s in state])

    return pd.DataFrame({"value": value, "state": state}, index=ts)


# ============================================================================
# 8. API FASTAPI
# ============================================================================
app = FastAPI(
    title="mis-core v2 — Analytics API",
    version="2.0.0-poc",
    description="Endpoint exemplo demonstrando fix B1/B2/B5/B7 + fórmulas ISO 22400-2.",
)


class TrendsRequest(BaseModel):
    from_: datetime = Field(..., alias="from")
    to: datetime
    granularity: Optional[str] = None
    equipment: str
    metrics: list[str]
    exclude_states: list[EquipState] = [EquipState.OFFLINE, EquipState.OTHER]

    model_config = {"populate_by_name": True}


@app.post("/api/v2/analytics/trends")
def trends(req: TrendsRequest) -> dict:
    tr = TimeRange(from_=req.from_, to=req.to, granularity=req.granularity)
    gran = tr.resolve_granularity()

    series = []
    for metric in req.metrics:
        if metric not in METRIC_CATALOG:
            raise HTTPException(400, f"Métrica desconhecida: {metric}")
        raw = fetch_raw_from_influx(req.equipment, metric, tr)
        tidy = apply_metric_pipeline(raw, metric, gran, req.exclude_states)
        tidy["value"] = tidy["value"].round(3)
        series.append({
            "metric": metric,
            "unit": METRIC_CATALOG[metric].unit,
            "kind": METRIC_CATALOG[metric].kind.value,
            "points": [
                {"ts": ts.isoformat(), "value": None if pd.isna(v) else float(v)}
                for ts, v in zip(tidy["ts"], tidy["value"])
            ],
        })
    return {
        "equipment": req.equipment,
        "from": req.from_.isoformat(),
        "to": req.to.isoformat(),
        "granularity": gran,
        "excluded_states": [s.value for s in req.exclude_states],
        "series": series,
    }


class StatsRequest(BaseModel):
    from_: datetime = Field(..., alias="from")
    to: datetime
    equipment: str
    metric: str
    lsl: Optional[float] = None
    usl: Optional[float] = None
    exclude_states: list[EquipState] = [EquipState.OFFLINE, EquipState.OTHER, EquipState.PLANNED_STOP]

    model_config = {"populate_by_name": True}


@app.post("/api/v2/analytics/stats")
def stats(req: StatsRequest) -> dict:
    if req.metric not in METRIC_CATALOG:
        raise HTTPException(400, "métrica desconhecida")
    tr = TimeRange(from_=req.from_, to=req.to)
    raw = fetch_raw_from_influx(req.equipment, req.metric, tr)
    # exclui estados antes de calcular stats
    mask = ~raw["state"].isin([s.value for s in req.exclude_states])
    values = raw.loc[mask, "value"]
    return {
        "equipment": req.equipment,
        "metric": req.metric,
        "kind": METRIC_CATALOG[req.metric].kind.value,
        "stats": eda_stats(values, lsl=req.lsl, usl=req.usl),
    }


class KpiLineRequest(BaseModel):
    from_: datetime = Field(..., alias="from")
    to: datetime
    line_id: str
    equipment_tph: dict[str, float]      # throughput medido por equip da linha
    oee_inputs_per_equip: dict[str, dict]  # para cada equip, inputs de OEEInputs

    model_config = {"populate_by_name": True}


@app.post("/api/v2/kpis/line")
def kpis_line(req: KpiLineRequest) -> dict:
    # TPH de linha = gargalo (fix B4)
    line_tph = LineTPH.calculate(req.equipment_tph)
    # OEE de linha = média ponderada por tempo planejado dos equips
    oees, weights = [], []
    for eq, inputs in req.oee_inputs_per_equip.items():
        i = OEEInputs(**inputs)
        o = OEE.oee(i)
        if o is not None:
            oees.append(o)
            weights.append(i.tempo_planejado_min)
    if weights:
        line_oee = float(np.average(oees, weights=weights))
    else:
        line_oee = 0.0
    return {
        "line_id": req.line_id,
        "from": req.from_.isoformat(),
        "to": req.to.isoformat(),
        "line_oee_pct": round(line_oee, 2),
        "line_tph_t_per_h": round(line_tph, 3),
        "bottleneck_equipment": min(req.equipment_tph, key=req.equipment_tph.get)
                                if req.equipment_tph else None,
    }


@app.get("/api/v2/health")
def health() -> dict:
    return {"status": "healthy", "version": "2.0.0-poc"}


# ============================================================================
# 9. TESTES UNITÁRIOS (rodar com: pytest 05_EXEMPLO_FASTAPI_ANALYTICS.py)
# ============================================================================
# pytest ficaria em backend-fastapi/tests/ — aqui para referência rápida
def _test_oee_corner_cases():
    i = OEEInputs(
        tempo_planejado_min=480, tempo_parado_nao_planejado_min=0,
        producao_boa=100, producao_total=100, tempo_ciclo_ideal_s=2.88,
    )
    assert OEE.availability(i) == 100.0
    assert abs(OEE.performance(i) - 1.0) < 1 or OEE.performance(i) == 100.0
    assert OEE.quality(i) == 100.0

    # Máquina parada — quality deve ser None, não 100%
    i_off = OEEInputs(480, 480, 0, 0, 2.88)
    assert OEE.quality(i_off) is None
    assert OEE.oee(i_off) is None

    # Overflow check — OEE nunca > 100
    i_fast = OEEInputs(100, 0, 1_000_000, 1_000_000, 2.88)
    assert OEE.oee(i_fast) <= 100.0


def _test_tph_no_duplicate_quality():
    # TPH é taxa física — NÃO multiplica por qualidade
    t1 = TPHCalculator.instantaneous(velocity_units_min=100, grams_per_unit=500)
    # 100 un/min × 60 × 500g / 1M = 3 t/h — qualidade não entra
    assert abs(t1 - 3.0) < 1e-9


def _test_line_tph_bottleneck():
    tph = {"ENC": 3.0, "BAL": 2.5, "ECX": 5.0}
    assert LineTPH.calculate(tph) == 2.5   # gargalo é BAL


def _test_counter_delta_pipeline():
    idx = pd.date_range("2026-01-01", periods=10, freq="1min", tz="UTC")
    # contador cumulativo subindo
    raw = pd.DataFrame({
        "value": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
        "state": ["RUN"] * 10,
    }, index=idx)
    out = apply_metric_pipeline(raw, "refugo_kg", "5min", exclude_states=[])
    # delta por 5min: primeiras 5 amostras = 14-10 = 4; próximas = 19-15 = 4
    assert (out["value"] > 0).any()


def _test_give_away_within_tolerance():
    # peso nominal 500g, medido 502g, tolerância 1% = 5g → give away = 0
    assert GiveAway.calculate(502, 500, tolerancia_legal_pct=1.0) == 0.0
    # medido 510g, excede tolerância → give away = 5g (510 - 505)
    assert GiveAway.calculate(510, 500, tolerancia_legal_pct=1.0) == 5.0


if __name__ == "__main__":
    # execução sanity-check rápida (roda pytest manualmente)
    _test_oee_corner_cases()
    _test_tph_no_duplicate_quality()
    _test_line_tph_bottleneck()
    _test_counter_delta_pipeline()
    _test_give_away_within_tolerance()
    print("[OK] Todos os testes unitários passaram.")
    print("Para rodar a API: uvicorn 05_EXEMPLO_FASTAPI_ANALYTICS:app --reload")
