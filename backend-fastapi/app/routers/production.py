"""
Endpoints operacionais v2.

Esta camada substitui gradualmente os endpoints Flask usados pelos cards.
Por enquanto a ingestao ainda grava no Influx via Flask/coletor, entao aqui
somente lemos o ultimo ponto consolidado em `production`.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.services.influx import InfluxAsyncClient, InfluxQueryError

router = APIRouter(tags=["production"])


ESTADOS_MAQUINA = {
    0: "Parado",
    1: "Produzindo",
    2: "Aguardando",
    3: "Bloqueado",
    4: "Parado/Falha",
    5: "Setup",
    6: "Teste",
    7: "Aguardando Manutencao",
    8: "Manutencao",
    9: "Falta de Material",
    10: "Outro",
    11: "Partindo",
    12: "Aguardando Condicoes",
    13: "Parando",
    999: "Offline",
}


def _line_status_from_equipment_state(state_code: int) -> str:
    """Estado operacional da linha a partir do equipamento-base."""
    if state_code == 999:
        return "Offline"
    if state_code == 4:
        return "Falha/Quebra"
    if state_code in (5, 6, 7, 8):
        return "Manutencao/Setup"
    if state_code in (2, 3, 9, 12):
        return "Aguardando"
    if state_code in (1, 11):
        return "Produzindo"
    return "Parada"


def _escape_tag(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _num(point: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        variants = (key, key[5:]) if key.startswith("last_") else (key, f"last_{key}")
        value = next((point.get(k) for k in variants if point.get(k) is not None), None)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _str(point: dict[str, Any], *keys: str, default: str = "N/A") -> str:
    for key in keys:
        variants = (key, key[5:]) if key.startswith("last_") else (key, f"last_{key}")
        value = next((point.get(k) for k in variants if point.get(k) not in (None, "")), None)
        if value not in (None, ""):
            return str(value)
    return default


def _norm(value: str | None) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _point_dt(point: dict[str, Any]) -> datetime | None:
    # ``time`` is the source/OPC timestamp and can legitimately lag while a
    # PLC group is being processed. ``timestamp_medicao`` is stamped by the
    # ingestion service and is the authoritative communication heartbeat.
    value = point.get("timestamp_medicao")
    if value is not None:
        try:
            return datetime.fromtimestamp(float(value), timezone.utc)
        except (TypeError, ValueError, OSError):
            pass
    value = point.get("time")
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value) / 1000.0, timezone.utc)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError, OSError):
        return None


def _is_fresh(point: dict[str, Any], max_age_s: int = 300) -> bool:
    ts = _point_dt(point)
    if not ts:
        return False
    return (datetime.now(timezone.utc) - ts).total_seconds() <= max_age_s


async def _django_get(path: str, params: dict[str, Any] | None = None) -> Any:
    settings = get_settings()
    base = settings.django_api_url.rstrip("/")
    async with httpx.AsyncClient(timeout=settings.django_timeout_s) as client:
        response = await client.get(f"{base}/{path.lstrip('/')}", params=params)
        response.raise_for_status()
        return response.json()


async def _resolve_line(identifier: str) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for params in ({"codigo": identifier}, {"search": identifier}):
        try:
            data = await _django_get("linhas/", params)
        except httpx.HTTPError:
            continue
        items = data.get("results", data) if isinstance(data, dict) else data
        if isinstance(items, list):
            candidates.extend(items)

    target = _norm(identifier)
    for line in candidates:
        if _norm(line.get("codigo")) == target or _norm(line.get("nome")) == target:
            return line
    return candidates[0] if candidates else None


async def _line_equipments(identifier: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    line = await _resolve_line(identifier)
    if not line:
        return None, []

    params = {"linha": line.get("id"), "page_size": 10000}
    try:
        data = await _django_get("equipamentos/", params)
    except httpx.HTTPError:
        return line, []

    equipments = data.get("results", data) if isinstance(data, dict) else data
    if not isinstance(equipments, list):
        equipments = []
    def equipment_order(item: dict[str, Any]) -> tuple[int, str]:
        try:
            order = int(item.get("ordem_na_linha"))
        except (TypeError, ValueError):
            order = 999999
        return order, str(item.get("codigo") or "")

    equipments.sort(key=equipment_order)
    return line, equipments


async def _latest_points(
    codes: list[str],
    *,
    line_code: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Return the latest production point for each equipment in one line.

    Equipment codes are only unique inside a line (for example, ``E001`` is
    reused by several lines).  Querying by code alone can therefore return a
    fresh point belonging to a different line, or an older point chosen from
    the wrong series.  Line-scoped endpoints must always pass ``line_code``.
    """
    points: dict[str, dict[str, Any]] = {}
    for code in codes:
        point = await _latest_production_point(code, line_code=line_code)
        if point:
            points[code] = point
    return points


def _parse_hhmmss(value: str | None) -> time | None:
    if not value:
        return None
    try:
        parts = [int(part) for part in value.split(":")[:3]]
        return time(parts[0], parts[1], parts[2] if len(parts) > 2 else 0)
    except (ValueError, TypeError):
        return None


def _shift_window(day: date, start: time, end: time, now_local: datetime) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(day, start, tzinfo=now_local.tzinfo)
    end_dt = datetime.combine(day, end, tzinfo=now_local.tzinfo)
    if end <= start:
        end_dt += timedelta(days=1)
    return start_dt, end_dt


async def _current_calendar_window(line_id: int) -> dict[str, Any]:
    tz = timezone(timedelta(hours=-3))
    now_local = datetime.now(tz)

    try:
        turnos_data = await _django_get("turnos/", {"page_size": 10000})
    except httpx.HTTPError:
        turnos_data = []
    turnos = turnos_data.get("results", turnos_data) if isinstance(turnos_data, dict) else turnos_data
    turnos_by_id = {item.get("id"): item for item in turnos if isinstance(item, dict)}
    turnos_by_code = {item.get("codigo") or item.get("nome"): item for item in turnos if isinstance(item, dict)}

    calendar_entries: list[dict[str, Any]] = []
    for day in (now_local.date(), now_local.date() - timedelta(days=1)):
        try:
            data = await _django_get("calendario/", {"linha_id": line_id, "data": day.isoformat(), "page_size": 10000})
        except httpx.HTTPError:
            continue
        items = data.get("results", data) if isinstance(data, dict) else data
        if isinstance(items, list):
            calendar_entries.extend(items)

    fallback_meta = 0.0
    debug = "Sem calendario programado"
    for entry in calendar_entries:
        if not entry.get("programado"):
            continue
        meta = float(entry.get("meta_producao_turno") or 0)
        if meta > 1000:
            meta /= 1000.0
        if fallback_meta == 0 and meta > 0:
            fallback_meta = meta

        turno = turnos_by_id.get(entry.get("turno")) or turnos_by_code.get(entry.get("turno_codigo")) or turnos_by_code.get(entry.get("turno_nome"))
        start = _parse_hhmmss(turno.get("hora_inicio") if turno else None)
        end = _parse_hhmmss(turno.get("hora_fim") if turno else None)
        if not start or not end:
            continue

        entry_day = date.fromisoformat(entry.get("data"))
        start_dt, end_dt = _shift_window(entry_day, start, end, now_local)
        if start_dt <= now_local <= end_dt:
            total_s = max(0.0, (end_dt - start_dt).total_seconds())
            elapsed_s = min(total_s, max(0.0, (now_local - start_dt).total_seconds()))
            return {
                "meta": meta,
                "elapsed_s": elapsed_s,
                "total_s": total_s,
                "turno": entry.get("turno_nome") or entry.get("turno_codigo"),
                "debug": f"Turno ativo {entry.get('turno_nome') or entry.get('turno_codigo')}",
            }
        debug = "Calendario existe, mas nenhum turno ativo no horario atual"

    industrial_fallback = _industrial_shift_fallback(calendar_entries, now_local)
    if industrial_fallback:
        return industrial_fallback

    return {
        "meta": fallback_meta,
        "elapsed_s": 0.0,
        "total_s": 0.0,
        "turno": "Fora de Turno",
        "debug": debug,
    }


def _industrial_shift_fallback(calendar_entries: list[dict[str, Any]], now_local: datetime) -> dict[str, Any] | None:
    """
    Fallback temporario para a grade industrial historica 06-14 / 14-22 / 22-06.

    Durante a migracao Flask -> FastAPI, ainda existem telas Django calculando
    turno por essa grade fixa. Se o cadastro de horarios do admin estiver
    desalinhado, mas houver calendario programado para o turno padrao atual,
    usamos esse calendario como fonte da meta e marcamos a origem no debug.
    """
    hour = now_local.hour
    if 6 <= hour < 14:
        code = "T1"
        start_dt = now_local.replace(hour=6, minute=0, second=0, microsecond=0)
        end_dt = now_local.replace(hour=14, minute=0, second=0, microsecond=0)
        entry_date = now_local.date()
    elif 14 <= hour < 22:
        code = "T2"
        start_dt = now_local.replace(hour=14, minute=0, second=0, microsecond=0)
        end_dt = now_local.replace(hour=22, minute=0, second=0, microsecond=0)
        entry_date = now_local.date()
    else:
        code = "T3"
        if hour >= 22:
            start_dt = now_local.replace(hour=22, minute=0, second=0, microsecond=0)
            end_dt = (now_local + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
            entry_date = now_local.date()
        else:
            start_dt = (now_local - timedelta(days=1)).replace(hour=22, minute=0, second=0, microsecond=0)
            end_dt = now_local.replace(hour=6, minute=0, second=0, microsecond=0)
            entry_date = (now_local - timedelta(days=1)).date()

    for entry in calendar_entries:
        if not entry.get("programado"):
            continue
        if entry.get("data") != entry_date.isoformat():
            continue
        if (entry.get("turno_codigo") or entry.get("turno_nome")) != code:
            continue

        meta = float(entry.get("meta_producao_turno") or 0)
        if meta > 1000:
            meta /= 1000.0
        total_s = max(0.0, (end_dt - start_dt).total_seconds())
        elapsed_s = min(total_s, max(0.0, (now_local - start_dt).total_seconds()))
        return {
            "meta": meta,
            "elapsed_s": elapsed_s,
            "total_s": total_s,
            "turno": code,
            "debug": f"Fallback grade industrial padrao {code} (06/14/22)",
        }
    return None


def _aggregate_line_oee(points: dict[str, dict[str, Any]]) -> float:
    values = [_num(point, "last_oee_realtime") for point in points.values() if _num(point, "last_oee_realtime") > 0]
    return sum(values) / len(values) if values else 0.0


def _turno_waste(point: dict[str, Any]) -> float:
    persisted = _num(
        point,
        "last_refugo_turno_acumulado",
        "last_descarte_turno_acumulado",
        "last_descarte",
    )
    entrada = _num(point, "last_contagem_entrada")
    saida = _num(point, "last_producao_turno_acumulada", "last_contagem_saida")
    balance = max(0.0, entrada - saida) if entrada > 0 else 0.0
    return max(persisted, balance)


async def _latest_production_point(
    codigo: str,
    *,
    line_code: str | None = None,
) -> dict[str, Any] | None:
    eq = _escape_tag(codigo)
    predicates = [f'"equipment" = \'{eq}\'']
    if line_code:
        predicates.append(f'"line" = \'{_escape_tag(line_code)}\'')
    where = " AND ".join(predicates)
    query = f'SELECT * FROM "production" WHERE {where} ORDER BY time DESC LIMIT 1'
    async with InfluxAsyncClient() as influx:
        payload = await influx.query_raw(query)

    series = (payload.get("results") or [{}])[0].get("series") or []
    if not series:
        return None

    columns = series[0].get("columns") or []
    values = series[0].get("values") or []
    if not values:
        return None
    return dict(zip(columns, values[0]))


def _request_line_scope(
    *,
    linha: str | None = None,
    linha_codigo: str | None = None,
    equipamento_slug: str | None = None,
) -> str | None:
    """Resolve the line identity sent by current and legacy frontends."""
    if linha_codigo:
        return linha_codigo
    if linha:
        return linha
    if equipamento_slug and "." in equipamento_slug:
        return equipamento_slug.split(".", 1)[0]
    return None


@router.get("/equipamento/dados/{codigo}")
async def get_equipamento_dados(
    codigo: str,
    linha: str | None = None,
    linha_codigo: str | None = None,
    equipamento_slug: str | None = None,
) -> dict[str, Any]:
    line_scope = _request_line_scope(
        linha=linha,
        linha_codigo=linha_codigo,
        equipamento_slug=equipamento_slug,
    )
    try:
        point = await _latest_production_point(codigo, line_code=line_scope)
    except InfluxQueryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not point:
        return {
            "velocidade_atual": 0,
            "estado_atual": "Offline",
            "pecas_produzidas": 0,
            "refugos": 0,
            "timestamp": None,
        }

    is_fresh = _is_fresh(point)
    estado_codigo = (
        int(_num(point, "last_estado_maquina", default=999))
        if is_fresh
        else 999
    )
    produzido_turno = _num(
        point,
        "last_producao_turno_acumulada",
        "last_contagem_saida",
    )
    refugo_turno = _turno_waste(point)

    return {
        "equipamento": codigo,
        "velocidade_atual": _num(point, "last_velocidade_atual", "last_velocidade"),
        "estado_atual": ESTADOS_MAQUINA.get(estado_codigo, str(estado_codigo)),
        "estado_atual_id": estado_codigo,
        "comunicacao_online": is_fresh,
        "pecas_produzidas": produzido_turno,
        "refugos": refugo_turno,
        "oee_atual": _num(point, "last_oee_realtime"),
        "timestamp": point.get("time"),
    }


@router.get("/operacao/dados/{codigo}")
async def get_operacao_dados(
    codigo: str,
    linha: str | None = None,
    linha_codigo: str | None = None,
    equipamento_slug: str | None = None,
) -> dict[str, Any]:
    line_scope = _request_line_scope(
        linha=linha,
        linha_codigo=linha_codigo,
        equipamento_slug=equipamento_slug,
    )
    try:
        point = await _latest_production_point(codigo, line_code=line_scope)
    except InfluxQueryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not point:
        raise HTTPException(status_code=404, detail="No data")

    produzido_op = _num(point, "last_producao_op_acumulada")
    refugo_op = _num(point, "last_refugo_op_acumulado")
    produzido_turno = _num(
        point,
        "last_producao_turno_acumulada",
        "last_contagem_saida",
    )
    refugo_turno = _turno_waste(point)
    formato_gramas = _num(point, "last_formato_gramas", "last_formato")
    total_turno = produzido_turno + refugo_turno
    percentual_descarte_turno = (refugo_turno / total_turno * 100.0) if total_turno > 0 else 0.0

    return {
        "equipamento": codigo,
        "cuc": _str(point, "last_cuc"),
        "ordem_producao": _str(point, "last_ordem_producao_field", "last_ordem_producao"),
        "sku": _str(point, "last_sku_codigo_field", "last_sku_codigo"),
        "descricao": _str(point, "last_descricao", default="Produto nao identificado"),
        "formato_gramas": formato_gramas,
        "planejado_op": int(_num(point, "last_planejado_op")),
        "produzido_op": produzido_op,
        "diferenca_op": _num(point, "last_diferenca_op"),
        "toneladas_op": _num(point, "last_toneladas_op"),
        "produzido_turno": produzido_turno,
        "descarte_turno": refugo_turno,
        "refugo_turno": refugo_turno,
        "pecas_boas_turno": produzido_turno,
        "pecas_ruins_turno": refugo_turno,
        "percentual_descarte_turno": max(_num(point, "last_percentual_descarte_turno"), percentual_descarte_turno),
        "toneladas_turno": _num(point, "last_toneladas_turno"),
        "toneladas_refugo_turno": _num(point, "last_toneladas_refugo_turno"),
        "turno_atual": _str(point, "last_shift", default="N/A"),
        "oee": _num(point, "last_oee_realtime"),
        "pecas_boas": max(0.0, produzido_op - refugo_op),
        "pecas_ruins": refugo_op,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/linha/{linha}/overview-status")
async def get_linha_overview_status(linha: str) -> dict[str, Any]:
    try:
        line, equipments = await _line_equipments(linha)
        codes = [eq.get("codigo") for eq in equipments if eq.get("codigo")]
        line_code = line.get("codigo") if line else linha
        points = await _latest_points(codes, line_code=line_code)
    except (InfluxQueryError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not codes:
        return {"status": "Offline", "reason": "Linha sem equipamentos cadastrados", "equipamentos": {}}

    states: dict[str, int] = {}
    for code in codes:
        point = points.get(code)
        if not point or not _is_fresh(point):
            states[code] = 999
            continue
        states[code] = int(_num(point, "last_estado_maquina", default=999))

    # A repeated-code/partial-collection topology cannot use an offline first
    # cadastro as proof that the whole line lost communication. Prefer the
    # first equipment (in configured line order) that has a fresh point. The
    # line is Offline only when no equipment is communicating.
    base_code = next((code for code in codes if states.get(code) != 999), codes[0])
    base_state = states.get(base_code, 999)
    status = _line_status_from_equipment_state(base_state)
    online_count = sum(1 for state in states.values() if state != 999)

    return {
        "status": status,
        "equipamentos": states,
        "estado_base_equipamento": base_code,
        "estado_base_codigo": base_state,
        "equipamentos_online": online_count,
        "equipamentos_total": len(codes),
        "criterio": "primeiro_equipamento_com_dado_recente",
    }


@router.get("/linha/{linha}/ole-realtime")
async def get_linha_ole_realtime(linha: str) -> dict[str, Any]:
    try:
        line, equipments = await _line_equipments(linha)
        codes = [eq.get("codigo") for eq in equipments if eq.get("codigo")]
        line_code = line.get("codigo") if line else linha
        points = await _latest_points(codes, line_code=line_code)
    except (InfluxQueryError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not line:
        raise HTTPException(status_code=404, detail="Linha nao encontrada")

    first_code = codes[0] if codes else None
    last_code = codes[-1] if codes else None
    last_point = points.get(last_code or "") if last_code else None
    first_point = points.get(first_code or "") if first_code else None

    production_candidates = []
    if last_point:
        production_candidates.append(_num(last_point, "last_toneladas_turno"))
    if len(codes) > 1 and points.get(codes[-2]):
        production_candidates.append(_num(points[codes[-2]], "last_toneladas_turno"))
    production_candidates.extend(_num(point, "last_toneladas_turno") for point in points.values())
    producao_real_ton = max((value for value in production_candidates if value > 0), default=0.0)

    formato = _num(first_point or {}, "last_formato_gramas", "last_formato")
    if formato <= 0:
        formato = max((_num(point, "last_formato_gramas", "last_formato") for point in points.values()), default=0.0)
    velocidade = _num(first_point or {}, "last_velocidade_atual", "last_velocidade")
    taxa_instantanea = (velocidade * 60.0 * formato) / 1_000_000.0 if velocidade > 0 and formato > 0 else 0.0

    calendar = await _current_calendar_window(int(line.get("id")))
    meta_toneladas = float(calendar["meta"] or 0)
    tempo_decorrido = float(calendar["elapsed_s"] or 0)
    tempo_total_turno = float(calendar["total_s"] or 0)
    producao_esperada = (
        meta_toneladas * (tempo_decorrido / tempo_total_turno)
        if meta_toneladas > 0 and tempo_total_turno > 0
        else 0.0
    )

    line_oee = _aggregate_line_oee(points)
    if producao_esperada > 0:
        ole = (producao_real_ton / producao_esperada) * 100.0
        ole_source = "ole_vs_expected"
    else:
        ole = line_oee
        ole_source = "avg_equipment_oee_no_active_shift"

    tempo_restante_horas = max(0.0, (tempo_total_turno - tempo_decorrido) / 3600.0)
    if tempo_restante_horas > 0 and taxa_instantanea > 0:
        projecao = producao_real_ton + taxa_instantanea * tempo_restante_horas
    else:
        projecao = producao_real_ton
    ritmo_necessario = (
        max(0.0, (meta_toneladas - producao_real_ton) / tempo_restante_horas)
        if tempo_restante_horas > 0
        else 0.0
    )

    fresh_count = sum(1 for code in codes if points.get(code) and _is_fresh(points[code]))
    ordered_points = [points[code] for code in codes if points.get(code)]

    def metadata_score(point: dict[str, Any]) -> tuple[int, int]:
        present = sum(
            _str(point, *keys) != "N/A"
            for keys in (
                ("last_ordem_producao_field", "last_ordem_producao"),
                ("last_sku_codigo_field", "last_sku_codigo"),
                ("last_descricao",),
                ("last_cuc",),
            )
        )
        return (present, 1 if _is_fresh(point) else 0)

    context = max(ordered_points, key=metadata_score, default={})

    return {
        "ole": round(ole, 1),
        "ole_source": ole_source,
        "producao_real": round(producao_real_ton, 3),
        "producao_esperada": round(producao_esperada, 3),
        "producao_planejada_ate_agora": round(producao_esperada, 3),
        "projecao": round(max(projecao, producao_real_ton), 3),
        "ritmo_necessario": round(ritmo_necessario, 1),
        "taxa_instantanea": round(taxa_instantanea, 1),
        "meta_turno": round(meta_toneladas, 1),
        "tempo_decorrido": round(tempo_decorrido, 1),
        "tempo_total_turno": round(tempo_total_turno, 1),
        "tempo_decorrido_perc": round((tempo_decorrido / tempo_total_turno * 100.0) if tempo_total_turno > 0 else 0.0, 1),
        "turno_atual": calendar["turno"],
        "equipamentos_online": fresh_count,
        "equipamentos_total": len(codes),
        "sku": _str(context, "last_sku_codigo_field", "last_sku_codigo"),
        "op": _str(context, "last_ordem_producao_field", "last_ordem_producao"),
        "descricao": _str(context, "last_descricao"),
        "cuc": _str(context, "last_cuc"),
        "formato": formato,
        "debug_meta": calendar["debug"],
    }


@router.get("/linha/{linha}/kpis")
async def get_linha_kpis(linha: str) -> dict[str, Any]:
    try:
        line, equipments = await _line_equipments(linha)
        codes = [eq.get("codigo") for eq in equipments if eq.get("codigo")]
        line_code = line.get("codigo") if line else linha
        points = await _latest_points(codes, line_code=line_code)
    except (InfluxQueryError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    samples = list(points.values())
    count = len(samples)
    avg = lambda field: (sum(_num(point, field) for point in samples) / count) if count else 0.0

    gargalo_nome = "N/A"
    gargalo_oee = 0.0
    if equipments:
        by_code = {eq.get("codigo"): eq for eq in equipments}
        oees = [(code, _num(point, "last_oee_realtime")) for code, point in points.items()]
        if oees:
            gargalo_code, gargalo_oee = min(oees, key=lambda item: item[1])
            gargalo_nome = by_code.get(gargalo_code, {}).get("nome") or gargalo_code

    return {
        "kpis": {
            "disponibilidade": round(avg("last_availability_realtime"), 1),
            "performance": round(avg("last_performance_realtime"), 1),
            "qualidade": round(avg("last_quality_realtime"), 1),
            "descarte_ton": round(sum(
                (_turno_waste(point) * _num(point, "last_formato_gramas", "last_formato")) / 1_000_000.0
                for point in samples
            ), 3),
            "descarte_percent": round(avg("last_percentual_descarte_turno"), 2),
        },
        "gargalo": {
            "nome": gargalo_nome,
            "oee": round(gargalo_oee, 1),
        },
    }
