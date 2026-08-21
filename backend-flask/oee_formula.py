"""
backend-flask/oee_formula.py
============================

Fórmula canônica de OEE — espelho 1:1 de
`backend-fastapi/app/core/formulas.py::compute_oee`.

Por que duplicado:
    Os containers Flask e FastAPI rodam separados (sem import cruzado). Para
    garantir que ambos calculem OEE IDENTICO, mantemos esta cópia textual.
    REGRA: qualquer mudança de fórmula precisa ser feita em AMBOS os arquivos
    (Flask aqui, FastAPI em app/core/formulas.py). O CI deve ter teste de
    consistência (test_formulas_parity.py — TODO).

Fórmulas (ISO 22400-2):
    Availability = Actual Production Time / Planned Production Time
    Performance  = (Total Count × Ideal Cycle Time) / Actual Production Time
                  ≤ 1.0 por definição (cap) ; raw permite até 1.05 para display
    Quality      = Good Count / Total Count   (indefinida se Total=0)
    OEE          = A × P × Q   (sempre em 0..1)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OEEInputs:
    actual_production_time_s: float
    planned_production_time_s: float
    total_count: float          # INPUT total (good + reject)
    good_count: float           # OUTPUT bom
    ideal_cycle_time_s: float   # tempo ideal por unidade (s/un) — = 60/vel_nominal_upm
    raw_performance_cap: float = 1.05
    oee_performance_cap: float = 1.0


@dataclass(frozen=True)
class OEEResult:
    availability: float
    performance: float          # cap ISO (≤1.0)
    performance_raw: float      # cap display (≤1.05)
    quality: float
    quality_valid: bool
    oee: float
    oee_valid: bool


def compute_oee(inp: OEEInputs) -> OEEResult:
    """Calcula OEE + componentes — espelho de FastAPI/formulas.compute_oee."""
    # Availability
    availability = 0.0
    if inp.planned_production_time_s > 0:
        availability = min(1.0, inp.actual_production_time_s / inp.planned_production_time_s)

    # Performance — count × ideal_cycle / actual_time
    performance_raw = 0.0
    if inp.actual_production_time_s > 0 and inp.ideal_cycle_time_s > 0:
        ideal_output = inp.actual_production_time_s / inp.ideal_cycle_time_s
        if ideal_output > 0:
            performance_raw = inp.total_count / ideal_output

    performance_raw = max(0.0, min(inp.raw_performance_cap, performance_raw))
    performance = min(inp.oee_performance_cap, performance_raw)

    # Quality — Good/Total. Indefinida se Total=0.
    quality_valid = inp.total_count > 0
    if quality_valid:
        quality = max(0.0, min(1.0, inp.good_count / inp.total_count))
    else:
        quality = 1.0

    # OEE
    oee_valid = quality_valid
    oee = min(1.0, availability * performance * quality) if oee_valid else 0.0

    return OEEResult(
        availability=availability,
        performance=performance,
        performance_raw=performance_raw,
        quality=quality,
        quality_valid=quality_valid,
        oee=oee,
        oee_valid=oee_valid,
    )


__all__ = ["OEEInputs", "OEEResult", "compute_oee"]
