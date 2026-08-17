"""
Testes da conversão de valores OPC UA → tipos Python.

Importante porque os CLPs entregam tipos de formas distintas:
  - REAL como float (esperado), às vezes como Decimal
  - DINT/UDINT/INT como int (esperado), às vezes como bool (porque o
    Python trata True/False como subtipos de int)
  - BOOL às vezes vem como int 0/1
  - STRING às vezes vem como bytes (servidores legados)

A regra: NUNCA derrubar o pipeline. Em caso de falha, devolve None
e o handler grava 'semleitura' no Redis.
"""
import pytest

from app.opc.conversion import opc_to_python


# ── REAL ──────────────────────────────────────────────────────────────

def test_real_de_float():
    assert opc_to_python("REAL", 1.5) == 1.5


def test_real_de_int():
    assert opc_to_python("REAL", 320) == 320.0
    assert isinstance(opc_to_python("REAL", 320), float)


def test_real_de_string_numerica():
    assert opc_to_python("REAL", "2.93") == 2.93


def test_real_de_string_invalida_retorna_none():
    assert opc_to_python("REAL", "abc") is None


# ── DINT / UDINT / INT / UINT ─────────────────────────────────────────

@pytest.mark.parametrize("tipo", ["DINT", "UDINT", "INT", "UINT"])
def test_int_types_de_int(tipo):
    assert opc_to_python(tipo, 13) == 13


@pytest.mark.parametrize("tipo", ["DINT", "UDINT", "INT", "UINT"])
def test_int_types_de_float(tipo):
    # asyncua pode entregar valor numérico como float — convertemos para int
    assert opc_to_python(tipo, 13.0) == 13


def test_int_de_bool_true_eh_1():
    # bool é subtipo de int — evitamos retornar True quando esperamos contador
    assert opc_to_python("DINT", True) == 1
    assert opc_to_python("DINT", False) == 0
    assert isinstance(opc_to_python("DINT", True), int)
    assert not isinstance(opc_to_python("DINT", True), bool)


def test_int_de_string_invalida_retorna_none():
    assert opc_to_python("DINT", "abc") is None


# ── BOOL ──────────────────────────────────────────────────────────────

def test_bool_de_bool():
    assert opc_to_python("BOOL", True) is True
    assert opc_to_python("BOOL", False) is False


def test_bool_de_int():
    assert opc_to_python("BOOL", 1) is True
    assert opc_to_python("BOOL", 0) is False
    assert opc_to_python("BOOL", 42) is True


def test_bool_de_string():
    assert opc_to_python("BOOL", "TRUE") is True
    assert opc_to_python("BOOL", "false") is False
    assert opc_to_python("BOOL", "  YES  ") is True
    assert opc_to_python("BOOL", "no") is False


# ── STRING ────────────────────────────────────────────────────────────

def test_string_de_string():
    assert opc_to_python("STRING", "AUTO") == "AUTO"


def test_string_de_bytes():
    # Servidores legados às vezes entregam string como bytes
    assert opc_to_python("STRING", b"AUTO") == "AUTO"


def test_string_de_int():
    # Numero virando string — pode acontecer em campos descritivos
    assert opc_to_python("STRING", 42) == "42"


def test_string_de_bytes_invalido_nao_quebra():
    # bytes inválidos UTF-8 → 'replace' substitui sem erro
    result = opc_to_python("STRING", b"\xff\xfe\x00valor")
    assert isinstance(result, str)
    assert "valor" in result


# ── Casos extremos ────────────────────────────────────────────────────

def test_none_retorna_none():
    for tipo in ["REAL", "DINT", "BOOL", "STRING"]:
        assert opc_to_python(tipo, None) is None


def test_tipo_desconhecido_vira_string():
    # Defensivo: tipo inválido cadastrado no admin não derruba o serviço
    assert opc_to_python("UNKNOWN", 42) == "42"


def test_tipo_vazio_vira_string():
    assert opc_to_python("", 42) == "42"
