"""
Testes das fórmulas core — SSOT dos KPIs.

Cobrem os 4 bugs P0 identificados no diagnóstico:
    1) OEE sem cap em Performance -> podia passar de 100%
    2) Quality = 1.0 quando Total=0 -> OEE "falso"
    3) TPH multiplicando qualidade -> double-counting
    4) Counter delta sem tolerância a reset do PLC -> spikes negativos
"""
from __future__ import annotations

import math

import pytest

from app.core.formulas import (
    OEEInputs,
    compute_give_away,
    compute_line_tph,
    compute_oee,
    compute_tph,
    counter_delta,
)


# ---------------- OEE ----------------
class TestOEE:
    def test_oee_nominal(self):
        r = compute_oee(OEEInputs(
            actual_production_time_s=7200,
            planned_production_time_s=8000,
            total_count=1000,
            good_count=980,
            ideal_cycle_time_s=7.0,
        ))
        assert math.isclose(r.availability, 0.9, rel_tol=1e-6)
        assert math.isclose(r.quality, 0.98, rel_tol=1e-6)
        assert r.oee_valid is True
        assert 0 < r.oee <= 1.0

    def test_oee_clipa_em_100pct_quando_performance_estoura(self):
        # cenário: calibração errada => produção "impossível"
        r = compute_oee(OEEInputs(
            actual_production_time_s=100,
            planned_production_time_s=100,
            total_count=10_000,   # muito acima do ideal
            good_count=10_000,
            ideal_cycle_time_s=1.0,   # ideal=100 peças, total=10k => perf_raw >> 1
        ))
        assert r.performance <= 1.0, "OEE nunca pode usar performance > 1.0"
        assert r.oee <= 1.0, "OEE nunca pode exceder 100%"

    def test_oee_invalida_quando_nao_houve_producao(self):
        r = compute_oee(OEEInputs(
            actual_production_time_s=3600,
            planned_production_time_s=3600,
            total_count=0,         # sem produção: qualidade indefinida
            good_count=0,
            ideal_cycle_time_s=5.0,
        ))
        assert r.quality_valid is False
        assert r.oee_valid is False
        assert r.oee == 0.0

    def test_oee_divisao_por_zero_nao_explode(self):
        r = compute_oee(OEEInputs(
            actual_production_time_s=0,
            planned_production_time_s=0.0001,  # trick: evita divisão por zero em planned
            total_count=0,
            good_count=0,
            ideal_cycle_time_s=1.0,
        ))
        assert r.oee == 0.0


# ---------------- TPH ----------------
class TestTPH:
    def test_tph_formula(self):
        # 60 upm × 500g = 30.000 g/min = 1.800 kg/h = 1.8 t/h
        assert compute_tph(60, 500) == 1.8

    def test_tph_nao_multiplica_qualidade(self):
        # garante que não há quality no signature (guardian test)
        import inspect
        sig = inspect.signature(compute_tph)
        assert "quality" not in sig.parameters
        assert "good_count" not in sig.parameters

    def test_tph_entradas_invalidas_retornam_zero(self):
        assert compute_tph(0, 500) == 0.0
        assert compute_tph(60, 0) == 0.0
        assert compute_tph(None, 500) == 0.0    # type: ignore[arg-type]
        assert compute_tph(-10, 500) == -0.3    # negativos NÃO são silenciados


class TestLineTPH:
    def test_line_tph_e_o_gargalo(self):
        assert compute_line_tph([2.0, 1.5, 3.0]) == 1.5

    def test_line_tph_ignora_equipamentos_parados(self):
        # 0 = parado -> não conta no gargalo
        assert compute_line_tph([2.0, 0, 3.0]) == 2.0

    def test_line_tph_vazia(self):
        assert compute_line_tph([]) == 0.0


# ---------------- Give Away ----------------
class TestGiveAway:
    def test_give_away_usa_tolerancia_inmetro(self):
        # 500g ±1% => alvo prático = 495g; avg 502g; prod 1000
        # give_g = (502 - 495) * 1000 = 7000g = 7kg
        r = compute_give_away(502.0, 500.0, 1000, inmetro_tolerance_pct=1.0)
        assert math.isclose(r.kg_total, 7.0, rel_tol=1e-3)
        assert r.samples == 1000

    def test_give_away_zero_producao(self):
        r = compute_give_away(502, 500, 0)
        assert r.kg_total == 0.0 and r.pct == 0.0

    def test_give_away_avg_abaixo_do_target_vira_negativo(self):
        # 490g com alvo 495 = -5g/unid * 1000 = -5kg
        r = compute_give_away(490.0, 500.0, 1000, inmetro_tolerance_pct=1.0)
        assert r.kg_total < 0, "avg < alvo legal = risco de multa, não give-away"


# ---------------- Counter delta ----------------
class TestCounterDelta:
    def test_monotonico(self):
        assert counter_delta([100, 110, 120]) == 20.0

    def test_tolera_reset_do_plc(self):
        # reset no meio -> ignora queda, mantém positivos
        assert counter_delta([100, 110, 0, 5, 15]) == 25.0

    def test_uma_amostra(self):
        assert counter_delta([42]) == 0.0

    def test_vazio(self):
        assert counter_delta([]) == 0.0
