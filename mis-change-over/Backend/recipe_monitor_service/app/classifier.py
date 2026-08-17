"""
Classificação de leituras OPC vs valor de receita.

Espelha a função `classificar()` do mock ReceitaMonitorContent.jsx —
a regra precisa ser idêntica entre frontend e backend, porque o frontend
ainda calcula localmente em alguns pontos (delta, banner de alarmes).

Regra:
  - Sem leitura (atual is None)               → 'semleitura'
  - BOOL/STRING:  atual == receita ?           → 'normal' : 'alarme'
  - Numérico, |Δ| <= tolerancia                → 'normal'
  - Numérico, |Δ| <= 2 * tolerancia            → 'atencao'
  - Numérico, |Δ|  > 2 * tolerancia            → 'alarme'
  - Numérico sem tolerância cadastrada         → 'normal' se Δ == 0,
                                                 'alarme' caso contrário
"""
from __future__ import annotations

from typing import Optional

from .schemas import StatusClassificacao, TipoVariavel

NUMERIC_TYPES: frozenset[str] = frozenset({"REAL", "DINT", "UDINT", "INT", "UINT"})


def is_numeric(tipo: str) -> bool:
    return tipo.upper() in NUMERIC_TYPES


def classificar(
    *,
    tipo: TipoVariavel,
    receita,
    atual,
    tolerancia: Optional[float],
) -> StatusClassificacao:
    """
    Classifica o estado de uma variável dado tipo, valor de receita,
    valor atual lido do CLP e tolerância configurada.

    Não trata exceções intencionalmente — quem chama deve validar entradas.
    """
    if atual is None:
        return "semleitura"

    # Tipos discretos: igual ou diferente, sem zona de atenção.
    if tipo == "BOOL" or tipo == "STRING":
        return "normal" if atual == receita else "alarme"

    # A partir daqui, todos numéricos.
    if receita is None:
        # Receita não cadastrada para essa variável neste formato.
        # Não dá para comparar — devolve 'semleitura' para sinalizar ao operador.
        return "semleitura"

    try:
        desvio = abs(float(atual) - float(receita))
    except (TypeError, ValueError):
        return "alarme"  # valor não-numérico em tag numérica — claramente errado

    if tolerancia is None or tolerancia <= 0:
        # Sem tolerância: só aceita exatamente o valor de receita.
        # Pequeno epsilon para floats DINT/UDINT/etc não derrubarem por arredondamento.
        epsilon = 1e-9 if tipo == "REAL" else 0.5
        return "normal" if desvio < epsilon else "alarme"

    if desvio <= tolerancia:
        return "normal"
    if desvio <= tolerancia * 2:
        return "atencao"
    return "alarme"
