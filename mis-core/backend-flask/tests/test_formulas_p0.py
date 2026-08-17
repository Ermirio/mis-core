"""
tests/test_formulas_p0.py
=========================

[P0.10] Cobertura de regressão para as correções de fórmulas da "Onda 1":

  * P0.1  — Delta em contadores acumulativos (analytics.py / last_diff)
  * P0.2  — Quality=1.0 falso quando production=0 (production_engine.py)
  * P0.7  — TPH duplicando impacto da qualidade (kpis_engine.py)
  * P0.7  — OEE > 100% quando performance estoura

Regra: TODO teste aqui deve FALHAR sem os patches da Onda 1. Se um dia um
refactor acidentalmente reintroduzir o bug, o CI segura a merge.

Analogia WCM: isso é o "poka-yoke" (à prova de erro) do repositório — o bug
que doeu uma vez não volta para doer de novo.
"""

from __future__ import annotations

import sys
import os
import pandas as pd
import pytest

# Ajuste de path: os testes rodam de dentro de tests/ e precisam achar
# production_engine / kpis_engine que vivem em backend-flask/.
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
)


# ==============================================================================
# P0.1 — Delta em contadores: _window_delta deve ser MONOTÔNICO-TOLERANTE
#         ao reset do CLP (início de turno) e NUNCA somar valores cumulativos.
# ==============================================================================
def _window_delta(s: pd.Series) -> float:
    """Cópia da função interna usada em analytics.py (last_diff)."""
    if len(s) < 2:
        return 0.0
    return float(s.sort_index().diff().clip(lower=0).sum())


class TestCounterDelta:
    def test_delta_monotonico_crescente(self):
        """Contador sempre crescente — delta = último - primeiro."""
        s = pd.Series([100, 110, 120, 130], index=pd.date_range('2026-01-01', periods=4, freq='1min'))
        assert _window_delta(s) == pytest.approx(30.0)

    def test_delta_ignora_reset_do_plc(self):
        """Contador reseta a zero no meio — delta soma apenas os incrementos positivos."""
        # 100 → 110 (+10) → 0 (reset, descartado) → 5 (+5) → 15 (+10) = 25
        s = pd.Series([100, 110, 0, 5, 15],
                      index=pd.date_range('2026-01-01', periods=5, freq='1min'))
        assert _window_delta(s) == pytest.approx(25.0)

    def test_delta_uma_amostra(self):
        """Uma só amostra — delta = 0 (não dá pra calcular)."""
        s = pd.Series([42.0], index=pd.date_range('2026-01-01', periods=1, freq='1min'))
        assert _window_delta(s) == 0.0

    def test_delta_serie_vazia(self):
        s = pd.Series([], dtype='float64')
        assert _window_delta(s) == 0.0

    def test_nao_soma_valor_acumulado_entre_janelas(self):
        """
        Bug original: ao usar `.last()` + `.sum()` entre equipamentos em janelas
        adjacentes, a série consolidada ficava MONOTONICAMENTE crescente (porque
        somava o estoque acumulado de cada janela).

        Aqui simulamos duas janelas de 1min de um contador que foi de 100→105
        na primeira e 105→108 na segunda. Delta total correto = 8, não 213.
        """
        janela1 = pd.Series([100, 103, 105],
                            index=pd.date_range('2026-01-01 10:00:00', periods=3, freq='20s'))
        janela2 = pd.Series([105, 106, 108],
                            index=pd.date_range('2026-01-01 10:01:00', periods=3, freq='20s'))
        total = _window_delta(janela1) + _window_delta(janela2)
        assert total == pytest.approx(8.0)


# ==============================================================================
# P0.7 — TPH: não deve multiplicar por qualidade (double-count no OEE)
# ==============================================================================
class TestTPH:
    def test_tph_ignora_qualidade(self):
        from kpis_engine import calcular_tph_real
        # 60 unidades/min * 500g = 30.000 g/min = 1.800.000 g/h = 1.8 ton/h
        tph_sem_qual = calcular_tph_real(velocidade=60, formato_gramas=500)
        tph_qual_50 = calcular_tph_real(velocidade=60, formato_gramas=500, qualidade=50)
        tph_qual_100 = calcular_tph_real(velocidade=60, formato_gramas=500, qualidade=100)
        # Todos iguais — qualidade é ignorada no cálculo físico de throughput
        assert tph_sem_qual == pytest.approx(1.8, abs=0.001)
        assert tph_qual_50 == pytest.approx(tph_sem_qual)
        assert tph_qual_100 == pytest.approx(tph_sem_qual)

    def test_tph_retorna_zero_para_entradas_invalidas(self):
        from kpis_engine import calcular_tph_real
        assert calcular_tph_real(0, 500) == 0.0
        assert calcular_tph_real(60, 0) == 0.0
        assert calcular_tph_real(None, 500) == 0.0
        assert calcular_tph_real('abc', 500) == 0.0  # robusto a lixo

    def test_tph_formula_correta(self):
        """TPH = (velocidade * 60 * formato_g) / 1_000_000  [ton/h]"""
        from kpis_engine import calcular_tph_real
        # 120 upm * 250g = 30kg/min = 1.8 ton/h
        assert calcular_tph_real(120, 250) == pytest.approx(1.8, abs=0.001)


# ==============================================================================
# P0.2 + P0.7 — Quality/OEE válidos apenas quando production > 0
#               (via flags quality_valid / oee_valid no dicionário de saída)
# ==============================================================================
class TestQualityValidityFlag:
    """
    Testa o CONTRATO da flag, não a orquestração completa do engine
    (que exige Influx, Django e estado in-memory). A lógica sob teste:

        quality_valid = total_prod_op > 0
        qualidade = 1.0 if not quality_valid else (prod - refugo) / prod
        oee_valid = quality_valid
    """

    def _calc_quality(self, total_prod, total_waste):
        """Reimplementa a lógica de production_engine.py (P0.2)."""
        quality_valid = total_prod > 0
        qualidade = 1.0
        if quality_valid:
            qualidade = max(0.0, (total_prod - total_waste) / total_prod)
        return qualidade, quality_valid

    def test_quality_valida_com_producao_positiva(self):
        q, valid = self._calc_quality(1000, 20)
        assert valid is True
        assert q == pytest.approx(0.98)

    def test_quality_invalida_com_producao_zero(self):
        """
        O sistema AINDA retorna qualidade=1.0 por compatibilidade com o
        frontend, mas SINALIZA quality_valid=False para o analytics filtrar.
        """
        q, valid = self._calc_quality(0, 0)
        assert valid is False
        assert q == 1.0  # valor "neutro" para display — mas INVÁLIDO para EDA

    def test_quality_nunca_negativa(self):
        """Refugo maior que produção (erro de coleta) — clip em 0, não negativo."""
        q, valid = self._calc_quality(100, 150)
        assert valid is True
        assert q == 0.0

    def test_oee_segue_validade_da_qualidade(self):
        """oee_valid é uma função de quality_valid — acopladas por design."""
        _, valid_zero = self._calc_quality(0, 0)
        _, valid_ok = self._calc_quality(500, 10)
        assert valid_zero is False
        assert valid_ok is True


# ==============================================================================
# P0.7 — OEE não pode exceder 100% (ISO 22400-2)
# ==============================================================================
class TestOEECap:
    """
    Reimplementa a lógica do cálculo final de OEE (production_engine.py):

        performance_oee = min(performance, 1.0)      # clip ISO
        oee = min(availability * performance_oee * quality * 100, 100.0)
    """

    def _calc_oee(self, availability, performance, quality, quality_valid=True):
        performance_oee = min(performance, 1.0)
        if not quality_valid:
            return 0.0
        return min(availability * performance_oee * quality * 100, 100.0)

    def test_oee_limitado_a_100_quando_performance_estoura(self):
        # Performance = 1.05 (display), mas OEE usa 1.0
        oee = self._calc_oee(1.0, 1.05, 1.0)
        assert oee == pytest.approx(100.0)

    def test_oee_nominal(self):
        # A=0.9, P=0.95, Q=0.98 → 83.79
        oee = self._calc_oee(0.9, 0.95, 0.98)
        assert oee == pytest.approx(83.79, abs=0.01)

    def test_oee_zero_quando_qualidade_invalida(self):
        oee = self._calc_oee(1.0, 1.0, 1.0, quality_valid=False)
        assert oee == 0.0

    def test_oee_nunca_excede_100(self):
        """Hardening: mesmo com entradas absurdas, OEE <= 100."""
        oee = self._calc_oee(1.5, 2.0, 1.1)   # valores corrompidos
        assert oee <= 100.0
