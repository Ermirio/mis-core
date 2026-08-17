"""
app/routers/kpis.py
===================

Endpoints /api/v2/kpis — OEE, TPH, Give-Away consolidados.

Estratégia:
    Os KPIs usam EXCLUSIVAMENTE as fórmulas em app.core.formulas (SSOT).
    Este router é só o "wiring" entre HTTP e as fórmulas. Qualquer nova
    regra (ex.: mudar cap de Performance) é feita UM lugar.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.formulas import (
    GiveAwayResult,
    OEEInputs,
    OEEResult,
    compute_give_away,
    compute_line_tph,
    compute_oee,
    compute_tph,
)

router = APIRouter(prefix="/kpis", tags=["kpis"])


# ---------- OEE ----------
class OEERequest(BaseModel):
    actual_production_time_s: float = Field(..., ge=0)
    planned_production_time_s: float = Field(..., gt=0)
    total_count: float = Field(..., ge=0)
    good_count: float = Field(..., ge=0)
    ideal_cycle_time_s: float = Field(..., gt=0)


class OEEResponse(BaseModel):
    availability: float
    performance: float
    performance_raw: float
    quality: float
    quality_valid: bool
    oee: float
    oee_valid: bool


@router.post("/oee", response_model=OEEResponse)
async def post_oee(req: OEERequest) -> OEEResponse:
    """Calcula OEE (ISO 22400-2) + flags de validade."""
    r: OEEResult = compute_oee(OEEInputs(
        actual_production_time_s=req.actual_production_time_s,
        planned_production_time_s=req.planned_production_time_s,
        total_count=req.total_count,
        good_count=req.good_count,
        ideal_cycle_time_s=req.ideal_cycle_time_s,
    ))
    return OEEResponse(**r.__dict__)


# ---------- TPH equipamento ----------
class TPHRequest(BaseModel):
    velocity_upm: float = Field(..., ge=0)
    formato_g: float = Field(..., gt=0)


@router.post("/tph")
async def post_tph(req: TPHRequest) -> dict[str, float]:
    """TPH = (upm × 60 × g) / 1e6  —  qualidade NÃO entra (anti double-counting)."""
    return {"tph": compute_tph(req.velocity_upm, req.formato_g)}


# ---------- TPH linha (gargalo) ----------
class LineTPHRequest(BaseModel):
    equipment_tphs: list[float] = Field(..., min_length=1, max_length=50)


@router.post("/tph/line")
async def post_line_tph(req: LineTPHRequest) -> dict[str, float]:
    """TPH da linha = mínimo dos equipamentos (Teoria das Restrições)."""
    return {"tph": compute_line_tph(req.equipment_tphs)}


# ---------- Give Away (INMETRO-aware) ----------
class GiveAwayRequest(BaseModel):
    avg_weight_g: float = Field(..., ge=0)
    target_weight_g: float = Field(..., gt=0)
    production_count: float = Field(..., ge=0)
    inmetro_tolerance_pct: float = Field(default=1.0, ge=0, le=10)


class GiveAwayResponse(BaseModel):
    kg_total: float
    pct: float
    samples: int


@router.post("/give-away", response_model=GiveAwayResponse)
async def post_give_away(req: GiveAwayRequest) -> GiveAwayResponse:
    r: GiveAwayResult = compute_give_away(
        req.avg_weight_g, req.target_weight_g,
        req.production_count, req.inmetro_tolerance_pct,
    )
    return GiveAwayResponse(**r.__dict__)


__all__ = ["router"]
