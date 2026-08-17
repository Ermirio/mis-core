"""
Conversão de valores OPC UA → tipos Python serializáveis em JSON.

Cada `Variavel.tipo` do Django mapeia a um VariantType esperado pelo
servidor OPC. Quando lemos um valor via asyncua, ele já chega como tipo
Python nativo na maioria dos casos — mas alguns servidores devolvem
`Int16`/`Int32` como `int`, `Float` como `float`, e BOOL pode vir como
`bool` ou `int`. Esta camada normaliza tudo.

Importante: nunca derrubar o serviço por valor inesperado — sempre
devolver `None` em falha de conversão e logar.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def opc_to_python(tipo_db: str, raw: Any) -> Any:
    """
    Normaliza um valor lido do OPC UA conforme o tipo cadastrado no Django.

    Args:
        tipo_db: 'REAL' | 'DINT' | 'UDINT' | 'INT' | 'UINT' | 'BOOL' | 'STRING'
        raw:     valor cru retornado pelo asyncua

    Returns:
        - REAL                     → float
        - DINT / UDINT / INT/UINT  → int
        - BOOL                     → bool
        - STRING                   → str
        - tipo desconhecido        → repr(raw) como string
        - falha de conversão       → None  (loga warning)
    """
    if raw is None:
        return None
    t = (tipo_db or "").upper()

    try:
        if t == "REAL":
            return float(raw)
        if t in {"DINT", "UDINT", "INT", "UINT"}:
            # bools em Python são int — tratamos antes
            if isinstance(raw, bool):
                return 1 if raw else 0
            return int(raw)
        if t == "BOOL":
            if isinstance(raw, bool):
                return raw
            if isinstance(raw, (int, float)):
                return raw != 0
            if isinstance(raw, str):
                return raw.strip().lower() in {"true", "1", "yes", "on"}
            return bool(raw)
        if t == "STRING":
            if isinstance(raw, (bytes, bytearray)):
                return raw.decode("utf-8", errors="replace")
            return str(raw)
        # Tipo desconhecido — devolve string para não derrubar o pipeline
        return str(raw)
    except (TypeError, ValueError) as e:
        logger.warning("[OPC] conversão falhou tipo=%s raw=%r: %s", tipo_db, raw, e)
        return None
