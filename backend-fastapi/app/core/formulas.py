"""
app/core/formulas.py
====================

Fórmulas KPI conforme ISO 22400-2 + boas práticas de WCM / TPM.

Por que toda fórmula vive aqui (single source of truth):
    No backend-flask existem DUAS implementações de OEE (production_engine e
    kpis_engine), com clipping e definições ligeiramente diferentes. Isso gera
    BIAS sistemático nos dashboards — "o OEE da Home diverge do OEE do
    Analytics" é a queixa recorrente. Aqui centralizamos, com testes,
    e os demais módulos apenas importam destas funções.

Regras (ISO 22400-2):
    Availability = Actual Production Time / Planned Production Time
    Performance  = (Total Count × Ideal Cycle Time) / Actual Production Time
                 = ≤ 1.0 por definição (se >1, calibração errada)
    Quality      = Good Count / Total Count    (indefinida se Total=0)
    OEE          = A × P × Q    (sempre em 0..1)

Diferença intencional entre "display" e "cálculo":
    - Em REAL TIME (UI), permitimos Performance até 1.05 (headroom de medição).
    - Para OEE, clipamos Performance em 1.0. Senão OEE "mentiroso" acima de 100%.
"""

from __future__ import annotations

from dataclasses import dataclass

# ==============================================================================
# OEE — ISO 22400-2
# ==============================================================================
@dataclass(frozen=True)
class OEEInputs:
    actual_production_time_s: float
    planned_production_time_s: float
    total_count: float
    good_count: float
    ideal_cycle_time_s: float      # tempo/ideal por unidade (s/un)
    # Guards para casos patológicos:
    raw_performance_cap: float = 1.05   # display only
    oee_performance_cap: float = 1.0    # ISO cap


@dataclass(frozen=True)
class OEEResult:
    availability: float           # 0..1
    performance: float            # 0..1 (cap=oee_performance_cap) — usada no OEE
    performance_raw: float        # 0..1.05 (cap=raw_performance_cap) — display
    quality: float                # 0..1
    quality_valid: bool           # False quando total_count == 0
    oee: float                    # 0..1 ou 0 se quality_valid=False
    oee_valid: bool


def compute_oee(inp: OEEInputs) -> OEEResult:
    """
    Calcula OEE + componentes.

    >>> r = compute_oee(OEEInputs(
    ...     actual_production_time_s=7200, planned_production_time_s=8000,
    ...     total_count=1000, good_count=980, ideal_cycle_time_s=7.0))
    >>> round(r.availability, 2)
    0.9
    >>> round(r.quality, 3)
    0.98
    """
    # Availability
    availability = 0.0
    if inp.planned_production_time_s > 0:
        availability = min(1.0, inp.actual_production_time_s / inp.planned_production_time_s)

    # Performance (raw e OEE-clipado)
    performance_raw = 0.0
    if inp.actual_production_time_s > 0 and inp.ideal_cycle_time_s > 0:
        ideal_output = inp.actual_production_time_s / inp.ideal_cycle_time_s
        if ideal_output > 0:
            performance_raw = inp.total_count / ideal_output

    performance_raw = max(0.0, min(inp.raw_performance_cap, performance_raw))
    performance = min(inp.oee_performance_cap, performance_raw)

    # Quality — INDEFINIDA quando total_count=0. Mantemos 1.0 para display
    # mas sinalizamos via quality_valid=False para downstream.
    quality_valid = inp.total_count > 0
    if quality_valid:
        quality = max(0.0, inp.good_count / inp.total_count)
    else:
        quality = 1.0

    # OEE só é VÁLIDO quando quality_valid, e é clipado em 1.0
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


# ==============================================================================
# TPH — Tonnes Per Hour (throughput físico da máquina)
# ==============================================================================
def compute_tph(velocity_upm: float, formato_g: float) -> float:
    """
    TPH = (velocidade_upm × 60min/h × formato_g) / 1_000_000 g/t

    Observação crítica: qualidade NÃO entra aqui — qualidade já está em OEE.
    Multiplicar qualidade no TPH produziria double-counting em relatórios.

    >>> compute_tph(60, 500)
    1.8
    >>> compute_tph(120, 250)
    1.8
    """
    try:
        v = float(velocity_upm or 0)
        g = float(formato_g or 0)
        return round((v * 60 * g) / 1_000_000.0, 3)
    except (TypeError, ValueError):
        return 0.0


def compute_line_tph(equipment_tphs: list[float]) -> float:
    """
    TPH da LINHA = gargalo = mínimo dos TPHs dos equipamentos.

    Armadilha comum: somar ou média. Isso ignora que a linha é serial e o
    elo mais lento dita o ritmo (Teoria das Restrições — Goldratt).

    >>> compute_line_tph([2.0, 1.5, 3.0])
    1.5
    >>> compute_line_tph([])
    0.0
    """
    values = [t for t in equipment_tphs if t and t > 0]
    return round(min(values), 3) if values else 0.0


# ==============================================================================
# GIVE AWAY — perda por excesso de peso (INMETRO-aware)
# ==============================================================================
@dataclass(frozen=True)
class GiveAwayResult:
    kg_total: float              # quanto em kg "demos de graça" no período
    pct: float                   # % sobre a massa-alvo (peso_target × produção)
    samples: int                 # nº de leituras contadas


def compute_give_away(
    avg_weight_g: float,
    target_weight_g: float,
    production_count: float,
    inmetro_tolerance_pct: float = 1.0,
) -> GiveAwayResult:
    """
    Give Away = (peso_medio - peso_target_ajustado) × produção

    INMETRO (NIE-DIMEL-081): produto embalado pode pesar o nominal MENOS uma
    tolerância regulamentada (T1/T2) sem violar. O "alvo" prático para
    efeitos de giveaway é (target × (1 - tolerance/100)), não o nominal cru.
    Ou seja, podemos legalmente entregar um pouquinho abaixo do nominal.

    Exemplo:
        produto de 500g com T1=±1% → alvo prático = 495g.
        se avg_weight = 502g, give away = 7g/unidade.

    >>> r = compute_give_away(502.0, 500.0, 1000, inmetro_tolerance_pct=1.0)
    >>> round(r.kg_total, 3)
    7.0
    >>> round(r.pct, 3)
    1.414
    """
    if production_count <= 0 or target_weight_g <= 0:
        return GiveAwayResult(kg_total=0.0, pct=0.0, samples=int(production_count or 0))

    target_practical = target_weight_g * (1 - inmetro_tolerance_pct / 100.0)
    give_g = (avg_weight_g - target_practical) * production_count
    give_kg = give_g / 1000.0

    reference_mass_kg = (target_practical * production_count) / 1000.0
    pct = (give_kg / reference_mass_kg) * 100 if reference_mass_kg > 0 else 0.0

    return GiveAwayResult(
        kg_total=round(give_kg, 3),
        pct=round(pct, 3),
        samples=int(production_count),
    )


# ==============================================================================
# COUNTER DELTA — tolerante a reset (idêntico ao fix do analytics.py P0.1)
# ==============================================================================
def counter_delta(values: list[float]) -> float:
    """
    Delta de um contador acumulativo, tolerante a reset do CLP.

    Estratégia: soma dos deltas POSITIVOS entre amostras consecutivas.
    Um reset (queda brusca para 0) produz delta negativo → ignorado.

    >>> counter_delta([100, 110, 120])
    20.0
    >>> counter_delta([100, 110, 0, 5, 15])   # reset no meio
    25.0
    >>> counter_delta([])
    0.0
    >>> counter_delta([42])
    0.0
    """
    if not values or len(values) < 2:
        return 0.0
    total = 0.0
    prev = values[0]
    for v in values[1:]:
        diff = v - prev
        if diff > 0:
            total += diff
        prev = v
    return round(total, 6)


__all__ = [
    "OEEInputs",
    "OEEResult",
    "compute_oee",
    "compute_tph",
    "compute_line_tph",
    "GiveAwayResult",
    "compute_give_away",
    "counter_delta",
]
