"""
Testes da regra de classificação (espelho do mock JSX).

Importante: a regra TEM QUE BATER 100% com a função `classificar()` em
ReceitaMonitorContent.jsx (linhas 261-271 do mock). Qualquer divergência
gera cores diferentes entre o badge calculado pelo backend e o calculado
pelo frontend → confunde o operador.
"""
import pytest

from app.classifier import classificar, is_numeric


@pytest.mark.parametrize("tipo", ["REAL", "DINT", "UDINT", "INT", "UINT"])
def test_is_numeric_para_tipos_numericos(tipo):
    assert is_numeric(tipo)


@pytest.mark.parametrize("tipo", ["BOOL", "STRING"])
def test_is_numeric_para_tipos_discretos(tipo):
    assert not is_numeric(tipo)


# ── semleitura ────────────────────────────────────────────────────────

def test_atual_none_eh_semleitura():
    assert classificar(tipo="REAL", receita=320, atual=None, tolerancia=8) == "semleitura"


def test_numerico_sem_receita_eh_semleitura():
    # Quando o formato não tem essa variável cadastrada, frontend ainda assim
    # pode pedir classificação — devolvemos 'semleitura' para não inflar alarmes.
    assert classificar(tipo="REAL", receita=None, atual=10.5, tolerancia=1) == "semleitura"


# ── BOOL / STRING ─────────────────────────────────────────────────────

def test_bool_igual_eh_normal():
    assert classificar(tipo="BOOL", receita=True, atual=True, tolerancia=None) == "normal"


def test_bool_diferente_eh_alarme():
    assert classificar(tipo="BOOL", receita=True, atual=False, tolerancia=None) == "alarme"


def test_string_igual_eh_normal():
    assert classificar(tipo="STRING", receita="AUTO", atual="AUTO", tolerancia=None) == "normal"


def test_string_diferente_eh_alarme():
    assert classificar(tipo="STRING", receita="AUTO", atual="MANUAL", tolerancia=None) == "alarme"


# ── Numérico com tolerância (caminho principal) ───────────────────────

def test_dentro_da_tolerancia_eh_normal():
    # |320 - 318.4| = 1.6 <= 8
    assert classificar(tipo="REAL", receita=320, atual=318.4, tolerancia=8) == "normal"


def test_dentro_de_dois_tol_eh_atencao():
    # |4.0 - 5.3| = 1.3, tol=1.0 → 1.0 < 1.3 <= 2.0 → atencao  (caso do mock)
    assert classificar(tipo="REAL", receita=4.0, atual=5.3, tolerancia=1.0) == "atencao"


def test_alem_de_dois_tol_eh_alarme():
    # |2.50 - 2.93| = 0.43, tol=0.15 → > 2*0.15=0.30 → alarme  (caso do mock)
    assert classificar(tipo="REAL", receita=2.50, atual=2.93, tolerancia=0.15) == "alarme"


def test_dint_no_limite_eh_normal():
    # |300 - 299| = 1 <= 10  (caso Velocidade_Rotulo do mock)
    assert classificar(tipo="DINT", receita=300, atual=299, tolerancia=10) == "normal"


# ── Numérico sem tolerância configurada ───────────────────────────────

def test_real_sem_tolerancia_igual_eh_normal():
    assert classificar(tipo="REAL", receita=10.0, atual=10.0, tolerancia=None) == "normal"


def test_real_sem_tolerancia_diferente_eh_alarme():
    assert classificar(tipo="REAL", receita=10.0, atual=10.5, tolerancia=None) == "alarme"


def test_dint_sem_tolerancia_arredonda():
    # DINT sem tol: epsilon=0.5 → 100 e 100.4 contam como "iguais"
    assert classificar(tipo="DINT", receita=100, atual=100.4, tolerancia=None) == "normal"
    assert classificar(tipo="DINT", receita=100, atual=101, tolerancia=None) == "alarme"


# ── Robustez: tipos inesperados ───────────────────────────────────────

def test_valor_nao_numerico_em_tag_numerica_eh_alarme():
    # Não deve quebrar — devolve alarme (sinaliza problema sem derrubar o serviço)
    assert classificar(tipo="REAL", receita=10.0, atual="abc", tolerancia=1.0) == "alarme"
