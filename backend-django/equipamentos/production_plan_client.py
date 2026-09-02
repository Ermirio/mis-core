"""Leitura resiliente do plano corporativo já replicado localmente na VM.

Este módulo nunca acessa o SQL Server. O único upstream é o
production-plan-service na rede Docker interna.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from typing import Any

import requests


logger = logging.getLogger(__name__)
BASE_URL = os.getenv("PRODUCTION_PLAN_URL", "http://production-plan-service:8080").rstrip("/")
TIMEOUT = float(os.getenv("PRODUCTION_PLAN_TIMEOUT_SECONDS", "1.5"))
CACHE_SECONDS = int(os.getenv("PRODUCTION_PLAN_CACHE_SECONDS", "60"))
_cache: dict[tuple[str, str, str], tuple[float, dict[str, Any] | None]] = {}
_product_cache: dict[str, tuple[float, dict[str, Any] | None]] = {}
_lock = threading.Lock()


def _normalize_sku(value: Any) -> str:
    sku = str(value or '').strip()
    return sku[:-2] if sku.endswith('.0') else sku


def _format_grams_from_description(description: str) -> float | None:
    """Extrai o peso da unidade de venda de descrições como 9X2.2KG."""
    match = re.search(
        r'\b\d+\s*[Xx]\s*(\d+(?:[.,]\d+)?)\s*(KG|G)\b',
        str(description or ''),
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    value = float(match.group(1).replace(',', '.'))
    return value * 1000 if match.group(2).upper() == 'KG' else value


def _shift_code(turno) -> str | None:
    raw = str(getattr(turno, "codigo", "") or getattr(turno, "nome", "")).upper()
    for number in ("1", "2", "3"):
        if raw == f"T{number}" or raw.startswith(number):
            return f"T{number}"
    return None


def planned_tons_for_shift(linha, data, turno) -> dict[str, Any] | None:
    """Retorna toneladas do último plano para linha/data/turno.

    Falha fechada: qualquer indisponibilidade retorna None e permite ao
    consumidor usar a meta local existente, sem quebrar o dashboard.
    """
    line_code = str(getattr(linha, "codigo", "")).upper()
    shift = _shift_code(turno)
    day = data.isoformat()
    if not line_code or not shift:
        return None
    key = (line_code, day, shift)
    now = time.monotonic()
    with _lock:
        cached = _cache.get(key)
        if cached and now - cached[0] < CACHE_SECONDS:
            return cached[1]
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/plan/summary",
            params={"day": day, "shift": shift, "line": line_code},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("rows") or []
        planned_tons = round(sum(float(row.get("planned_tons") or 0) for row in rows), 3)
        result = {
            "planned_tons": planned_tons,
            "snapshot_ts": payload.get("snapshot_ts"),
            "day": day,
            "shift": shift,
            "line": line_code,
            "items": sum(int(row.get("plan_items") or 0) for row in rows),
            "skus": sum(int(row.get("skus") or 0) for row in rows),
        } if planned_tons > 0 else None
    except Exception as exc:
        logger.warning(
            "Plano dinâmico indisponível para %s/%s/%s: %s",
            line_code,
            day,
            shift,
            exc,
        )
        result = None
    with _lock:
        _cache[key] = (now, result)
    return result


def product_context_for_sku(sku: Any) -> dict[str, Any] | None:
    """Resolve descrição e formato no mestre local replicado do plano.

    O SKU é a identidade do produto. Quando o OPC envia descrição ou formato
    divergentes, o cadastro corporativo prevalece. Falhas preservam o contexto
    recebido do processo e nunca derrubam o card.
    """
    normalized_sku = _normalize_sku(sku)
    if not normalized_sku or normalized_sku == 'N/A':
        return None
    now = time.monotonic()
    with _lock:
        cached = _product_cache.get(normalized_sku)
        if cached and now - cached[0] < CACHE_SECONDS:
            return cached[1]
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/plan/current",
            params={"sku": normalized_sku},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        items = response.json().get('items') or []
        item = next(
            (
                row for row in items
                if _normalize_sku(row.get('sku')) == normalized_sku
            ),
            None,
        )
        if item:
            description = str(item.get('description') or '').strip()
            result = {
                'sku': normalized_sku,
                'description': description or None,
                'format_grams': _format_grams_from_description(description),
                'unit_weight': item.get('unit_weight'),
                'source': 'plano_corporativo_local',
            }
        else:
            result = None
    except Exception as exc:
        logger.warning('Mestre de produto indisponível para SKU %s: %s', normalized_sku, exc)
        result = None
    with _lock:
        _product_cache[normalized_sku] = (now, result)
    return result
