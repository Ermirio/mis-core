"""
Endpoints portados do Flask para o Django como parte da eliminação total
do backend Flask (item 18 do plano principal, ver docs/migracao-flask-fastapi.md).

Os endpoints aqui replicam o contrato HTTP do Flask (mesmas URLs, mesmo
shape de resposta) para que o cutover do frontend seja apenas trocar
FLASK_API_URL por DJANGO_API_URL.

Cada onda do plano Flask-out vai adicionando endpoints novos neste
arquivo. Quando todos estiverem aqui, o serviço Flask é removido do
docker-compose + nginx e a pasta backend-flask/ é deletada.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any

import pytz
import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import golden_state_queue as gs_queue
from .models import LinhaProducao, Equipamento, EventoEstadoEquipamento, EstadoEquipamento
from .production_engine import ProductionEngine
from .turno_helpers import obter_turno_atual, calcular_inicio_turno, calcular_fim_turno
from .utils import get_meta_turno
from .waste_dashboard_views import query_influxdb

# Engine in-memory compartilhado entre requests (substitui o Flask app
# context). Inicializado lazy na primeira ingestão.
_production_engine = None
_engine_lock = threading.Lock()


def _get_production_engine():
    global _production_engine
    if _production_engine is None:
        with _engine_lock:
            if _production_engine is None:
                # ConfigManager do engine bate em /equipamentos do Django.
                # Como o engine roda DENTRO do Django, usa loopback.
                django_url = 'http://localhost:8000/api'
                _production_engine = ProductionEngine(_influx_client(), django_url)
    return _production_engine


# ===== Helpers de ingestão (espelham backend-flask/routes.py:42-189) =====

_last_counts: dict = {}


def _calc_speed_rpm(eq: str, current: int) -> int:
    prev = _last_counts.get(eq)
    _last_counts[eq] = current
    if prev is None or current < prev:
        return 0
    return int((current - prev) * 12)


INT_FIELDS = {
    'estado_maquina', 'estado', 'contagem_saida', 'contagem_entrada',
    'descarte', 'planejado_op',
}
FLOAT_FIELDS = {
    'velocidade_atual', 'velocidade', 'velocidade_real', 'formato',
    'formato_gramas', 'oee_realtime', 'performance_realtime',
    'quality_realtime', 'availability_realtime', 'toneladas_op',
    'toneladas_turno', 'toneladas_refugo_turno', 'percentual_descarte_turno',
    'diferenca_op', 'producao_op_acumulada', 'producao_turno_acumulada',
    'refugo_op_acumulado', 'refugo_turno_acumulado',
    'descarte_turno_acumulado', 'tempo_parado_turno',
    'tempo_planejado_turno', 'timestamp_medicao',
}
STRING_FIELDS = {
    'ordem_producao', 'ordem_producao_field', 'sku_codigo',
    'sku_codigo_field', 'descricao', 'cuc', 'connection_status',
}
CORE_FIELD_NAMES = INT_FIELDS | FLOAT_FIELDS | STRING_FIELDS
_influx_type_conflicts_seen: set = set()


PLC_STATE_TO_EVENT_STATE = {
    0: EstadoEquipamento.OUTRO,
    1: EstadoEquipamento.RUN,
    2: EstadoEquipamento.WAIT_PREV,
    3: EstadoEquipamento.BLOCK_NEXT,
    4: EstadoEquipamento.FAULT,
    5: EstadoEquipamento.SETUP,
    6: EstadoEquipamento.TESTE_PROJ,
    7: EstadoEquipamento.AGUARD_MNT,
    8: EstadoEquipamento.MANUTENCAO,
    9: EstadoEquipamento.FALTA_MAT,
    10: EstadoEquipamento.OUTRO,
    11: EstadoEquipamento.PARTINDO,
    # O frontend ja conhece AGUARD_COND, mas o modelo Django ainda nao tem
    # esse choice. Enquanto o catalogo de estados nao for migrado, preserva a
    # timeline usando OUTRO em vez de falhar a ingestao.
    12: EstadoEquipamento.OUTRO,
    13: EstadoEquipamento.PARANDO,
    999: EstadoEquipamento.OUTRO,
}


def _parse_event_timestamp(value):
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        dt = parse_datetime(value.strip())
    else:
        dt = None
    if dt is None:
        return timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _event_state_from_payload(value) -> str:
    if isinstance(value, str):
        text = value.strip().upper()
        valid_states = {choice[0] for choice in EstadoEquipamento.choices}
        if text in valid_states:
            return text
        try:
            value = int(float(text))
        except (TypeError, ValueError):
            return EstadoEquipamento.OUTRO
    try:
        code = int(float(value))
    except (TypeError, ValueError):
        return EstadoEquipamento.OUTRO
    return PLC_STATE_TO_EVENT_STATE.get(code, EstadoEquipamento.OUTRO)


def _event_code_from_payload(value) -> int:
    if isinstance(value, str):
        text = value.strip().upper()
        reverse = {
            EstadoEquipamento.OUTRO: 0,
            EstadoEquipamento.RUN: 1,
            EstadoEquipamento.WAIT_PREV: 2,
            EstadoEquipamento.BLOCK_NEXT: 3,
            EstadoEquipamento.FAULT: 4,
            EstadoEquipamento.SETUP: 5,
            EstadoEquipamento.TESTE_PROJ: 6,
            EstadoEquipamento.AGUARD_MNT: 7,
            EstadoEquipamento.MANUTENCAO: 8,
            EstadoEquipamento.FALTA_MAT: 9,
            EstadoEquipamento.PARTINDO: 11,
            EstadoEquipamento.PARANDO: 13,
        }
        if text in reverse:
            return reverse[text]
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _sync_estado_timeline(equipamento: Equipamento, estado_raw, timestamp=None):
    """Materializa estado realtime em EventoEstadoEquipamento para timeline.

    O card usa Influx/production. A timeline usa MySQL/Eventos. Durante a
    migracao Flask -> Django, nem todo coletor chama /eventos_estado/; por
    isso a ingestao principal tambem precisa manter a timeline.
    """
    estado = _event_state_from_payload(estado_raw)
    event_ts = _parse_event_timestamp(timestamp)

    eventos_abertos = list(
        EventoEstadoEquipamento.objects
        .filter(equipamento=equipamento, fim__isnull=True)
        .order_by('-inicio', '-id')
    )
    evento_aberto = eventos_abertos[0] if eventos_abertos else None
    if evento_aberto and event_ts < evento_aberto.inicio:
        event_ts = max(timezone.now(), evento_aberto.inicio)

    if evento_aberto and evento_aberto.estado == estado:
        # Repara apenas a condição aberta duplicada; preserva o evento mais
        # recente e fecha os demais sem apagar histórico.
        for duplicado in eventos_abertos[1:]:
            duplicado.fim = max(duplicado.inicio, evento_aberto.inicio)
            duplicado.save(update_fields=['fim', 'duracao_segundos'])
        return evento_aberto

    for aberto in eventos_abertos:
        aberto.fim = max(aberto.inicio, event_ts)
        aberto.save(update_fields=['fim', 'duracao_segundos'])

    return EventoEstadoEquipamento.objects.create(
        equipamento=equipamento,
        estado=estado,
        inicio=event_ts,
        origem='OPC',
        observacao='Sincronizado automaticamente a partir de /api/dados/inserir',
    )


def _coerce_influx_field(name, value):
    if value is None:
        return None
    try:
        if name in INT_FIELDS:
            return int(float(value))
        if name in FLOAT_FIELDS:
            return float(value)
        if name in STRING_FIELDS:
            return str(value)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return float(value)
        return str(value)
    except (TypeError, ValueError):
        return None


def _add_dynamic_fields(fields, medicoes, excluded=None):
    excluded = set(excluded or [])
    for name, value in medicoes.items():
        if name in fields or name in excluded:
            continue
        coerced = _coerce_influx_field(name, value)
        if coerced is not None:
            fields[name] = coerced


def _write_points_resilient(influx_client, points):
    if not influx_client:
        return
    try:
        influx_client.write_points(points)
    except Exception as exc:
        msg = str(exc)
        if 'field type conflict' not in msg.lower():
            raise
        retry_points = []
        for point in points:
            if point.get('measurement') != 'production':
                retry_points.append(point)
                continue
            retry_point = dict(point)
            retry_point['fields'] = {
                name: value for name, value in point.get('fields', {}).items()
                if name in CORE_FIELD_NAMES
            }
            retry_points.append(retry_point)
        influx_client.write_points(retry_points)

logger = logging.getLogger(__name__)


def _normalize_line_name(linha_nome: str) -> str:
    """Equivalente Django ao normalize_line_name do Flask (routes.py:9).

    'Linha 01' -> 'L01', 'L1' -> 'L01' (zero-pad), 'L01' -> 'L01'.
    """
    if not linha_nome:
        return linha_nome
    nome_upper = linha_nome.upper().strip()
    if nome_upper.startswith('L') and len(nome_upper) <= 4 and nome_upper[1:].isdigit():
        n = int(nome_upper[1:])
        return f'L{n:02d}' if n < 100 else f'L{n}'
    if 'LINHA' in nome_upper:
        parts = nome_upper.replace('LINHA', '').strip().split()
        if parts and parts[0].isdigit():
            n = int(parts[0])
            return f'L{n:02d}' if n < 100 else f'L{n}'
    return nome_upper.replace('LINHA ', 'L').replace('LINHA', 'L')


def _escape_influx_tag(value: str) -> str:
    return str(value or '').replace('\\', '\\\\').replace("'", "\\'")


def _equipment_identity_where(codigo: str, *, slug: str | None = None, linha_codigo: str | None = None) -> str:
    eq = _escape_influx_tag(codigo)
    line_value = _escape_influx_tag(linha_codigo) if linha_codigo else ''
    if not eq or not line_value:
        raise ValueError("Consulta de equipamento exige codigo e linha_codigo.")
    return f"\"equipment\" = '{eq}' AND \"line\" = '{line_value}'"


def _influx_client():
    """Cria um cliente InfluxDB com as settings do Django."""
    from influxdb import InfluxDBClient
    return InfluxDBClient(
        host=settings.INFLUXDB_HOST,
        port=settings.INFLUXDB_PORT,
        username=settings.INFLUXDB_USER,
        password=settings.INFLUXDB_PASSWORD,
        database=settings.INFLUXDB_DATABASE,
    )


def _normalize_oee(v):
    # Padroniza OEE para a escala 0-100 (ISO 22400-2).
    # Equipamentos antigos gravam como fração 0-1; o engine novo grava 0-100.
    # Sem padronizar, max(oees) misturava as escalas e a fábrica mostrava
    # 95% quando a única linha tinha OEE real de 0.79 (=79%) ou 115% no gargalo.
    #
    # CAP EM 100%: OEE por definição é "% do potencial atingido" e não pode
    # ultrapassar 100%. Quando o coletor reporta >100% (linha rodando acima
    # da velocidade_nominal cadastrada), isso indica configuração incorreta
    # — capamos aqui para manter coerência entre /linha/<>/kpis,
    # /fabrica/kpis e /metricas_fabrica_consolidadas/, e sinalizamos com a
    # variável `velocidade_nominal` o ajuste necessário no admin.
    try:
        x = float(v or 0)
    except (TypeError, ValueError):
        return 0.0
    if 0 < x <= 1.5:
        x *= 100.0
    if x < 0:
        return 0.0
    if x > 100:
        return 100.0
    return x


# ===== ONDA 1: /health, /health/system, /realtime/all =====

@api_view(['GET'])
def flask_health(request):
    """GET /api/flask-replacement/health -> {status: ok}.

    Substitui o Flask /api/health (linha 1437 do routes.py).
    """
    return Response({'status': 'ok'})


@api_view(['GET'])
def flask_health_system(request):
    """GET /api/flask-replacement/health/system.

    Substitui o Flask /api/health/system (linha 224 do routes.py).
    Checa conectividade Django -> InfluxDB e presença de dados recentes
    no coletor. Mantém HTTP 200 para a tela de diagnóstico conseguir exibir
    cada dependência mesmo quando uma delas estiver indisponível.
    """
    return Response(_system_health_status())


def _system_health_status() -> dict[str, Any]:
    health: dict[str, Any] = {
        'influxdb': False,
        'django': True,
        'coletor': False,
        'details': {},
    }

    client = None
    try:
        client = _influx_client()
        client.ping()
        health['influxdb'] = True
    except Exception as e:
        health['details']['influxdb_error'] = str(e)

    if client is not None:
        try:
            recent = list(client.query(
                "SELECT alive, cycle_seconds, equipment_count, measurement_count "
                "FROM collector_heartbeat "
                "WHERE service = 'mis-core-coletor' AND time > now() - 10m "
                "ORDER BY time DESC LIMIT 1"
            ).get_points())
            heartbeat = recent[0] if recent else {}
            health['coletor'] = int(heartbeat.get('alive') or 0) == 1
            if health['coletor']:
                health['details']['coletor'] = {
                    'last_heartbeat': heartbeat.get('time'),
                    'cycle_seconds': heartbeat.get('cycle_seconds'),
                    'equipment_count': heartbeat.get('equipment_count'),
                    'measurement_count': heartbeat.get('measurement_count'),
                    'max_age_minutes': 10,
                }
            else:
                health['details']['coletor_error'] = (
                    'Heartbeat do coletor ausente nos últimos 10 minutos'
                )
        except Exception as e:
            health['details']['coletor_error'] = str(e)

    return health


@api_view(['GET'])
def flask_health_ready(request):
    """Readiness real para Docker/nginx; retorna 503 se uma dependência cair."""
    health = _system_health_status()
    health['ready'] = all(health[key] for key in ('django', 'influxdb', 'coletor'))
    return Response(health, status=200 if health['ready'] else 503)


@api_view(['GET'])
def flask_realtime_all(request):
    """GET /api/flask-replacement/realtime/all.

    Substitui o Flask /api/realtime/all (linha 272 do routes.py).
    Retorna o último ponto conhecido de cada equipamento no Influx
    (janela 1h) no shape esperado pelos consumidores (Sidebar,
    FactorySynoptic, DiagnosticosLogs, HomeV2).
    """
    try:
        query = (
            'SELECT last(estado_maquina) as estado_maquina, '
            'last(velocidade_atual) as velocidade_atual, '
            'last(ordem_producao) as ordem_producao, '
            'last(sku_codigo) as sku_codigo, '
            'last(descricao) as descricao, '
            'last(cuc) as cuc, '
            'last(oee_realtime) as oee, '
            'last(formato_gramas) as formato_gramas, '
            'last(contagem_saida) as contagem_saida, '
            'last(descarte) as descarte, '
            'last(temperatura) as temperatura, '
            'last(pressao) as pressao, '
            'last(peso_real) as peso_real '
            'FROM production WHERE time > now() - 1h '
            'GROUP BY "equipment"'
        )

        # query_influxdb() usa a API simplificada que retorna pontos com tag
        # mesclada. Para acessar a tag 'equipment', usamos a API raw do
        # client diretamente quando necessário.
        from influxdb import InfluxDBClient
        client = InfluxDBClient(
            host=settings.INFLUXDB_HOST,
            port=settings.INFLUXDB_PORT,
            username=settings.INFLUXDB_USER,
            password=settings.INFLUXDB_PASSWORD,
            database=settings.INFLUXDB_DATABASE,
        )
        rs = client.query(query)

        equipamentos: dict[str, Any] = {}
        for (name, tags), points in rs.items():
            equipment_code = (tags or {}).get('equipment')
            if not equipment_code:
                continue
            for point in points:
                equipamentos[equipment_code] = {
                    'medicoes': {
                        'estado_maquina': int(point.get('estado_maquina') or 0),
                        'velocidade_atual': float(point.get('velocidade_atual') or 0),
                        'ordem_producao': point.get('ordem_producao', 'N/A'),
                        'sku_codigo': point.get('sku_codigo', 'N/A'),
                        'descricao': point.get('descricao', 'N/A'),
                        'cuc': point.get('cuc', 'N/A'),
                        'oee': _normalize_oee(point.get('oee')),
                        'formato_gramas': float(point.get('formato_gramas') or 0),
                        'contagem_saida': float(point.get('contagem_saida') or 0),
                        'descarte': float(point.get('descarte') or 0),
                        'temperatura': float(point.get('temperatura') or 0),
                        'pressao': float(point.get('pressao') or 0),
                        'peso_real': float(point.get('peso_real') or 0),
                    },
                    'timestamp': point.get('time'),
                }
                break  # last() devolve 1 ponto por série

        return Response(equipamentos)
    except Exception as e:
        logger.exception('flask_realtime_all falhou')
        return Response({'error': str(e)}, status=500)


# ===== ONDA 2: /linha/<codigo>/{status, overview-status, ole-realtime, historico} =====

@api_view(['GET'])
def flask_linha_status(request, linha_nome: str):
    """GET /api/linha/<linha_nome>/status — substitui Flask routes.py:320.

    Retorna status atual de todos os equipamentos da linha (último ponto
    Influx + flag stale quando age > 45s).
    """
    try:
        line_norm = _normalize_line_name(linha_nome)
        query = (
            'SELECT last(estado_maquina) as estado_maquina, '
            'last(ordem_producao) as ordem_producao, '
            'last(sku_codigo) as sku_codigo, '
            'last(descricao) as descricao, '
            'last(cuc) as cuc '
            f"FROM production WHERE \"line\" = '{line_norm}' "
            'GROUP BY "equipment"'
        )
        rs = _influx_client().query(query)

        equipamentos = []
        from dateutil import parser as dtparser
        for (_, tags), points in rs.items():
            equipment_name = (tags or {}).get('equipment', 'Unknown')
            for point in points:
                # Staleness check
                is_stale = False
                ts_str = point.get('time')
                if ts_str:
                    try:
                        last_dt = dtparser.parse(ts_str)
                        age = (datetime.now(last_dt.tzinfo) - last_dt).total_seconds()
                        if age > 45:
                            is_stale = True
                    except Exception:
                        pass
                state_val = int(point.get('estado_maquina') or 0)
                if is_stale:
                    state_val = 0
                equipamentos.append({
                    'nome': equipment_name,
                    'medicoes': {
                        'estado_maquina': state_val,
                        'ordem_producao': point.get('ordem_producao', 'N/A'),
                        'sku_codigo': point.get('sku_codigo', 'N/A'),
                        'descricao': point.get('descricao', 'N/A'),
                        'cuc': point.get('cuc', 'N/A'),
                    },
                })
                break
        return Response({
            'equipamentos': equipamentos,
            'agregados': {'total_equipamentos': len(equipamentos)},
        })
    except Exception as e:
        logger.exception('flask_linha_status falhou')
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def flask_linha_overview_status(request, linha_nome: str):
    """GET /api/linha/<linha_nome>/overview-status — substitui Flask routes.py:1211.

    Status consolidado da linha: Produzindo > Falha > Manutenção/Setup >
    Aguardando > Parada > Offline. Dados stale (>5min) viram 0 para não
    reportar falha velha.
    """
    try:
        line_norm = _normalize_line_name(linha_nome)
        client = _influx_client()
        STALE = 300
        from dateutil import parser as dtparser

        def parse_states(rs):
            out = {}
            for (_, tags), points in rs.items():
                eq = (tags or {}).get('equipment')
                if not eq:
                    continue
                for p in points:
                    estado = p.get('estado')
                    if estado is None:
                        continue
                    state_val = int(estado)
                    ts_str = p.get('time')
                    if ts_str:
                        try:
                            last_dt = dtparser.parse(ts_str)
                            age = (datetime.now(last_dt.tzinfo) - last_dt).total_seconds()
                            if age > STALE:
                                state_val = 0
                        except Exception:
                            pass
                    out[eq] = state_val
            return out

        # Tentativa 1: production com filtro de linha
        q1 = (
            f"SELECT last(estado_maquina) AS estado FROM production "
            f"WHERE \"line\" = '{line_norm}' GROUP BY \"equipment\""
        )
        last_states = parse_states(client.query(q1))
        # Tentativa 2: production sem filtro (coletor pode ter parado de
        # escrever a tag "line")
        if not last_states:
            q2 = 'SELECT last(estado_maquina) AS estado FROM production GROUP BY "equipment"'
            last_states = parse_states(client.query(q2))
        if not last_states:
            return Response({'status': 'Offline', 'reason': 'No Data'})

        estados = list(last_states.values())
        if any(e in (1, 11) for e in estados):
            status = 'Produzindo'
        elif any(e == 4 for e in estados):
            status = 'Falha/Quebra'
        elif any(e in (5, 6, 8) for e in estados):
            status = 'Manutenção/Setup'
        elif any(e == 2 for e in estados):
            status = 'Aguardando'
        else:
            status = 'Parada'
        return Response({'status': status, 'equipamentos': last_states})
    except Exception as e:
        logger.exception('flask_linha_overview_status falhou')
        return Response({'status': 'Offline', 'error': str(e)}, status=500)


@api_view(['GET'])
def flask_linha_ole_realtime(request, linha_nome: str):
    """GET /api/linha/<linha_nome>/ole-realtime — substitui Flask routes.py:799.

    Versão simplificada (sem production_engine in-memory do Flask): lê
    direto do Influx + Django ORM. Mesmo shape de resposta.
    """
    try:
        line_norm = _normalize_line_name(linha_nome)

        # Resolve linha + lista ordenada de equipamentos
        linha = (
            LinhaProducao.objects
            .filter(codigo__iexact=line_norm)
            .prefetch_related('equipamentos')
            .first()
        )
        if not linha:
            return Response({'error': f'Linha {line_norm} não encontrada'}, status=404)

        eqs = sorted(linha.equipamentos.all(), key=lambda e: (e.ordem_na_linha, e.codigo))
        if not eqs:
            return Response({'error': 'Linha sem equipamentos cadastrados'}, status=404)

        primeiro_eq = eqs[0].codigo
        ultimo_eq = eqs[-1].codigo

        # Produção real (toneladas) = último valor de toneladas_turno do
        # último equipamento. Fallback: penúltimo, depois MAX da linha.
        client = _influx_client()
        producao_real_ton = 0.0
        taxa_instantanea = 0.0

        def _last_value(equipment_code: str, field: str) -> float:
            q = f"SELECT last({field}) as v FROM production WHERE \"equipment\" = '{equipment_code}'"
            pts = list(client.query(q).get_points())
            if pts and pts[0].get('v') is not None:
                try:
                    return float(pts[0]['v'])
                except (TypeError, ValueError):
                    return 0.0
            return 0.0

        producao_real_ton = _last_value(ultimo_eq, 'toneladas_turno')
        if producao_real_ton == 0 and len(eqs) > 1:
            producao_real_ton = _last_value(eqs[-2].codigo, 'toneladas_turno')

        # Velocidade do primeiro equipamento (dita ritmo)
        vel = _last_value(primeiro_eq, 'velocidade_atual')
        fmt = _last_value(primeiro_eq, 'formato_gramas')
        if fmt > 0 and vel > 0:
            taxa_instantanea = (vel * 60 * fmt) / 1_000_000.0

        # Meta de turno: helper já existente (PR 4) com fallback para meta padrão
        turno_atual = obter_turno_atual()
        meta_toneladas = 0.0
        tempo_decorrido = 0.0
        tempo_total_turno = 0.0
        if turno_atual:
            hoje = timezone.localtime(timezone.now()).date()
            meta = get_meta_turno(linha, hoje, turno_atual)  # em unidades
            # Converte unidades para toneladas usando formato do primeiro eq
            if meta and fmt > 0:
                meta_toneladas = (meta * fmt) / 1_000_000.0

            inicio = calcular_inicio_turno(turno_atual)
            fim = calcular_fim_turno(turno_atual)
            now = timezone.localtime(timezone.now())
            tempo_total_turno = (fim - inicio).total_seconds()
            tempo_decorrido = min((now - inicio).total_seconds(), tempo_total_turno)

        # OLE, projeção e ritmo
        producao_esperada = 0.0
        ole = 0.0
        projecao = producao_real_ton
        ritmo_necessario = 0.0
        if meta_toneladas > 0 and tempo_total_turno > 0:
            producao_esperada = meta_toneladas * (tempo_decorrido / tempo_total_turno)
            if producao_esperada > 0:
                ole = (producao_real_ton / producao_esperada) * 100.0
            tempo_restante_h = (tempo_total_turno - tempo_decorrido) / 3600.0
            if tempo_restante_h > 0:
                projecao = producao_real_ton + (taxa_instantanea * tempo_restante_h)
                if projecao < producao_real_ton:
                    projecao = producao_real_ton
                saldo = meta_toneladas - producao_real_ton
                ritmo_necessario = max(0.0, saldo / tempo_restante_h)

        # Contexto (OP, SKU, etc) do primeiro equipamento
        q_ctx = (
            f"SELECT last(sku_codigo) as sku, last(ordem_producao) as op, "
            f"last(descricao) as descricao, last(cuc) as cuc, "
            f"last(formato_gramas) as fmt FROM production "
            f"WHERE \"equipment\" = '{primeiro_eq}'"
        )
        line_context = {'sku': 'N/A', 'op': 'N/A', 'descricao': 'N/A', 'cuc': 'N/A', 'formato': 0.0}
        try:
            pts = list(client.query(q_ctx).get_points())
            if pts:
                p = pts[0]
                line_context['sku'] = str(p.get('sku') or 'N/A')
                line_context['op'] = str(p.get('op') or 'N/A')
                line_context['descricao'] = str(p.get('descricao') or 'N/A')
                line_context['cuc'] = str(p.get('cuc') or 'N/A')
                line_context['formato'] = float(p.get('fmt') or 0)
        except Exception:
            pass

        # Equipamentos online: ponto nos últimos 2 min
        q_online = (
            f"SELECT count(estado_maquina) AS n FROM production "
            f"WHERE \"line\" = '{line_norm}' AND time > now() - 2m "
            f"GROUP BY \"equipment\""
        )
        try:
            rs = client.query(q_online)
            equipamentos_online = sum(1 for _, points in rs.items() if list(points))
        except Exception:
            equipamentos_online = 0

        return Response({
            'ole': round(ole, 1),
            'producao_real': round(producao_real_ton, 3),
            'producao_esperada': round(producao_esperada, 3),
            'projecao': round(projecao, 3),
            'ritmo_necessario': round(ritmo_necessario, 1),
            'taxa_instantanea': round(taxa_instantanea, 1),
            'meta_turno': round(meta_toneladas, 1),
            'tempo_decorrido_perc': round(
                (tempo_decorrido / tempo_total_turno * 100) if tempo_total_turno > 0 else 0, 1
            ),
            'equipamentos_online': equipamentos_online,
            'equipamentos_total': len(eqs),
            'sku': line_context['sku'],
            'op': line_context['op'],
            'descricao': line_context['descricao'],
            'cuc': line_context['cuc'],
            'formato': line_context['formato'],
        })
    except Exception as e:
        logger.exception('flask_linha_ole_realtime falhou')
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def flask_linha_historico(request, linha_nome: str):
    """GET /api/linha/<linha_nome>/historico?start&end&interval — substitui Flask routes.py:1653.

    Retorna histórico agregado: producao_total (spread contagem_saida) e
    oee_medio por bucket de tempo.
    """
    try:
        start_str = request.query_params.get('start')
        end_str = request.query_params.get('end')
        interval = request.query_params.get('interval', '1h')
        line_norm = _normalize_line_name(linha_nome)

        if not start_str or not end_str:
            end_dt = datetime.utcnow()
            start_dt = end_dt - timedelta(hours=24)
            s_str = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            e_str = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            try:
                s_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                e_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                s_str = s_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                e_str = e_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            except Exception:
                s_str, e_str = start_str, end_str

        group_by = '1000d' if interval == 'total' else interval
        query = (
            f"SELECT sum(producao) as producao_total, mean(oee) as oee_medio "
            f"FROM ( "
            f"  SELECT spread(contagem_saida) as producao, mean(oee_realtime) as oee "
            f"  FROM production WHERE \"line\" = '{line_norm}' "
            f"  AND time >= '{s_str}' AND time <= '{e_str}' "
            f"  GROUP BY time({group_by}), \"equipment\" "
            f") GROUP BY time({group_by}) fill(0)"
        )
        rs = _influx_client().query(query)
        historico = []
        for p in rs.get_points():
            historico.append({
                'data_hora': p['time'],
                'producao_total': int(p.get('producao_total') or 0),
                'oee_medio': float(p.get('oee_medio') or 0),
            })
        return Response({'linha': linha_nome, 'historico': historico})
    except Exception as e:
        logger.exception('flask_linha_historico falhou')
        return Response({'error': str(e)}, status=500)


# ===== ONDA 3: /linha/<>/kpis, /equipamento/<>/kpis, /fabrica/{kpis,mapa} =====

# Espelho do constants.ESTADOS_MAQUINA do Flask para evitar dependência.
_ESTADOS_MAQUINA = {
    0: 'Online', 1: 'Produzindo', 2: 'Aguardando Anterior', 3: 'Bloqueado Próximo',
    4: 'Parado/Falha', 5: 'Setup', 6: 'Teste/Projeto', 7: 'Aguardando Manutenção',
    8: 'Manutenção', 9: 'Falta de Material', 11: 'Partindo',
    12: 'Aguardando Condições', 13: 'Parando',
}


def _calcular_tph(velocidade: float, formato_g: float) -> float:
    """TPH (ton/h) = velocidade(unid/min) × 60min × formato(g) / 1_000_000."""
    try:
        return round((float(velocidade or 0) * 60 * float(formato_g or 0)) / 1_000_000, 3)
    except Exception:
        return 0.0


@api_view(['GET'])
def flask_linha_kpis(request, linha_nome: str):
    """GET /api/linha/<linha_nome>/kpis — substitui Flask kpis_routes.py:34.

    Usa Teoria das Restrições (Goldratt): OEE da linha = OEE do gargalo
    (menor TPH > 0). Mantém ranking completo no retorno.
    """
    try:
        line_norm = _normalize_line_name(linha_nome)
        q = (
            'SELECT last(velocidade_atual) as velocidade, '
            'last(formato_gramas) as formato, '
            'last(quality_realtime) as qualidade, '
            'last(oee_realtime) as oee, '
            'last(availability_realtime) as disponibilidade, '
            'last(performance_realtime) as performance, '
            'last(estado_maquina) as estado, '
            'last(toneladas_turno) as toneladas_turno '
            f"FROM production WHERE \"line\" = '{line_norm}' GROUP BY \"equipment\""
        )
        rs = _influx_client().query(q)

        equipamentos = []
        for (_, tags), points in rs.items():
            equipment_name = (tags or {}).get('equipment', 'Unknown')
            point = list(points)[0] if points else {}
            velocidade = point.get('velocidade', 0)
            formato = point.get('formato', 0)
            tph = _calcular_tph(velocidade, formato)
            equipamentos.append({
                'nome': equipment_name,
                'tph_real': tph,
                'oee': _normalize_oee(point.get('oee')),
                'disponibilidade': _normalize_oee(point.get('disponibilidade')),
                'performance': _normalize_oee(point.get('performance')),
                'qualidade': _normalize_oee(point.get('qualidade')),
                'estado': int(point.get('estado') or 0),
                'velocidade': float(velocidade or 0),
                'formato': float(formato or 0),
            })

        ranking = sorted(equipamentos, key=lambda x: x['tph_real'], reverse=True)
        candidatos = [e for e in equipamentos if e['tph_real'] > 0]
        if candidatos:
            gargalo = min(candidatos, key=lambda x: x['tph_real'])
        else:
            gargalo = ranking[-1] if ranking else None

        if gargalo:
            kpis = {
                'oee': round(gargalo['oee'], 2),
                'disponibilidade': round(gargalo['disponibilidade'], 2),
                'performance': round(gargalo['performance'], 2),
                'qualidade': round(gargalo['qualidade'], 2),
                'tph_medio': round(gargalo['tph_real'], 3),
            }
        else:
            kpis = {'oee': 0, 'disponibilidade': 0, 'performance': 0, 'qualidade': 0, 'tph_medio': 0}

        return Response({
            'linha': linha_nome,
            'gargalo': gargalo,
            'ranking': ranking,
            'equipamentos': equipamentos,
            'kpis': kpis,
        })
    except Exception as e:
        logger.exception('flask_linha_kpis falhou')
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def flask_equipamento_kpis(request, eq_codigo: str):
    """GET /api/equipamento/<codigo>/kpis — substitui Flask kpis_routes.py:47."""
    try:
        q = (
            'SELECT last(velocidade_atual) as velocidade, '
            'last(formato_gramas) as formato, '
            'last(quality_realtime) as qualidade, '
            'last(oee_realtime) as oee, '
            'last(availability_realtime) as disponibilidade, '
            'last(performance_realtime) as performance, '
            'last(estado_maquina) as estado, '
            'last(toneladas_turno) as toneladas_turno '
            f"FROM production WHERE \"equipment\" = '{eq_codigo}'"
        )
        pts = list(_influx_client().query(q).get_points())
        if not pts:
            return Response({})
        p = pts[0]
        velocidade = p.get('velocidade', 0)
        formato = p.get('formato', 0)
        return Response({
            'equipamento': eq_codigo,
            'kpis': {
                'tph_real': _calcular_tph(velocidade, formato),
                'oee': _normalize_oee(p.get('oee')),
                'disponibilidade': _normalize_oee(p.get('disponibilidade')),
                'performance': _normalize_oee(p.get('performance')),
                'qualidade': _normalize_oee(p.get('qualidade')),
                'estado': int(p.get('estado') or 0),
                'velocidade': float(velocidade or 0),
                'formato': float(formato or 0),
            },
        })
    except Exception as e:
        logger.exception('flask_equipamento_kpis falhou')
        return Response({'error': str(e)}, status=500)


def _resolve_periodo(period: str):
    """Resolve start/end/remaining_hours para 'turno'|'dia'|'semana'|'mes'."""
    from datetime import time as dt_time
    import calendar as _calendar
    tz = pytz.timezone('America/Sao_Paulo')
    now = datetime.now(tz)
    today = now.date()
    turno_atual = obter_turno_atual() if period == 'turno' else None

    if period == 'turno' and turno_atual:
        start = calcular_inicio_turno(turno_atual)
        end = calcular_fim_turno(turno_atual)
    elif period == 'dia':
        start = datetime.combine(today, dt_time.min).replace(tzinfo=tz)
        end = datetime.combine(today, dt_time.max).replace(tzinfo=tz)
    elif period == 'semana':
        seg = today - timedelta(days=today.weekday())
        start = datetime.combine(seg, dt_time.min).replace(tzinfo=tz)
        end = datetime.combine(seg + timedelta(days=6), dt_time.max).replace(tzinfo=tz)
    elif period == 'mes':
        last_day = _calendar.monthrange(today.year, today.month)[1]
        start = datetime.combine(today.replace(day=1), dt_time.min).replace(tzinfo=tz)
        end = datetime.combine(today.replace(day=last_day), dt_time.max).replace(tzinfo=tz)
    else:
        start = end = now
    remaining = max(0.0, (end - now).total_seconds() / 3600.0)
    return start, end, remaining, turno_atual


def _primeiro_equipamento_por_linha() -> dict:
    """Retorna { 'L01': 'L01_Enchedora', ... } via ORM Django (sem HTTP)."""
    mapping = {}
    for linha in LinhaProducao.objects.prefetch_related('equipamentos').all():
        eqs = sorted(linha.equipamentos.all(), key=lambda e: (e.ordem_na_linha or 999))
        if eqs:
            mapping[linha.codigo] = eqs[0].codigo
    return mapping


@api_view(['GET'])
def flask_fabrica_kpis(request):
    """GET /api/fabrica/kpis?period=turno|dia|semana|mes — substitui
    Flask kpis_routes.py:74 e factory_kpis_engine.get_factory_kpis().
    """
    period = request.query_params.get('period', 'turno')
    try:
        from .models import CalendarioProducao
        client = _influx_client()
        start_dt, end_dt, remaining_h, turno_info = _resolve_periodo(period)

        primeiro_eq_map = _primeiro_equipamento_por_linha()
        active_lines = list(LinhaProducao.objects.filter(ativa=True))

        lines_kpi = []
        total_planned = total_real = total_flow_real = total_oee_real = 0.0
        active_line_count = 0

        for linha in active_lines:
            line_code = linha.codigo

            # Planned (Django ORM)
            line_planned = 0.0
            cal_qs = CalendarioProducao.objects.filter(
                linha=linha, data__gte=start_dt.date(), data__lte=end_dt.date(),
            )
            if period == 'turno' and turno_info:
                cal_qs = cal_qs.filter(turno=turno_info)
            for cal in cal_qs:
                meta = float(cal.meta_producao_turno or 0)
                if meta > 1000:  # smart conversion KG -> ton
                    meta /= 1000.0
                line_planned += meta

            # Real (InfluxDB) — Teoria das Restrições (Goldratt): a linha é
            # tão produtiva quanto seu gargalo. Por isso:
            #   line_oee = OEE do equipamento gargalo (menor TPH > 0)
            #   line_tph = TPH do gargalo (não soma de TPH de todo mundo)
            # Antes usava-se max(oees) na linha, o que dava 95% quando o
            # gargalo era 79%.
            line_real = line_oee = line_tph = 0.0
            line_status = 'Sem Dados'
            estado_primeiro_cod = None
            estado_primeiro_txt = None

            try:
                if period == 'turno':
                    q_real = (
                        f"SELECT last(toneladas_turno) as val, last(oee_realtime) as oee, "
                        f"last(estado_maquina) as state, last(velocidade_atual) as vel, "
                        f"last(formato_gramas) as fmt FROM production "
                        f"WHERE \"line\" = '{line_code}' GROUP BY \"equipment\""
                    )
                    rs_real = client.query(q_real)
                    eq_rows = []
                    states_seen = []
                    for (_, tags), pts in rs_real.items():
                        for p in pts:
                            tph_eq = _calcular_tph(p.get('vel'), p.get('fmt'))
                            eq_rows.append({
                                'eq': (tags or {}).get('equipment'),
                                'val': float(p.get('val') or 0),
                                'oee': _normalize_oee(p.get('oee')),
                                'tph': tph_eq,
                            })
                            if p.get('state') is not None:
                                states_seen.append(p.get('state'))
                            break

                    if eq_rows:
                        # produção da linha = max(toneladas_turno por equip)
                        line_real = max((r['val'] for r in eq_rows), default=0.0)
                        candidatos = [r for r in eq_rows if r['tph'] > 0]
                        if candidatos:
                            gargalo = min(candidatos, key=lambda r: r['tph'])
                        else:
                            # fallback: equipamento de menor OEE (linha parada)
                            gargalo = min(eq_rows, key=lambda r: r['oee'])
                        line_oee = gargalo['oee']
                        line_tph = gargalo['tph']

                    # Status pelo 1o equipamento
                    primeiro_eq = primeiro_eq_map.get(line_code)
                    if primeiro_eq:
                        q_state = (
                            f"SELECT last(estado_maquina) as state FROM production "
                            f"WHERE \"equipment\" = '{primeiro_eq}'"
                        )
                        pts_st = list(client.query(q_state).get_points())
                        if pts_st:
                            estado_primeiro_cod = int(pts_st[0].get('state') or 0)
                            estado_primeiro_txt = _ESTADOS_MAQUINA.get(
                                estado_primeiro_cod, str(estado_primeiro_cod)
                            )
                            line_status = estado_primeiro_txt
                    if line_status == 'Sem Dados' and eq_rows:
                        if any(s == 1 for s in states_seen) or line_tph > 0:
                            line_status = 'Rodando'
                        else:
                            line_status = 'Parada'
                else:
                    # Dia/Semana/Mes: produção agregada
                    s_str = start_dt.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
                    e_str = end_dt.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
                    q_agg = (
                        f"SELECT max(toneladas_turno) as val FROM production "
                        f"WHERE \"line\" = '{line_code}' "
                        f"AND time >= '{s_str}' AND time <= '{e_str}' GROUP BY shift"
                    )
                    for (_, _), pts in client.query(q_agg).items():
                        for p in pts:
                            line_real += float(p.get('val') or 0)
                    q_oee = (
                        f"SELECT mean(oee_realtime) as oee FROM production "
                        f"WHERE \"line\" = '{line_code}' "
                        f"AND time >= '{s_str}' AND time <= '{e_str}'"
                    )
                    pts_oee = list(client.query(q_oee).get_points())
                    if pts_oee:
                        line_oee = _normalize_oee(pts_oee[0].get('oee'))
                    now = datetime.now(pytz.timezone('America/Sao_Paulo'))
                    elapsed_h = max(0.016, (now - start_dt).total_seconds() / 3600.0)
                    line_tph = line_real / elapsed_h if elapsed_h > 0 else 0.0
                    line_status = 'Histórico'
            except Exception:
                logger.exception('Erro KPIs InfluxDB para %s', line_code)

            lines_kpi.append({
                'linha': line_code,
                'oee_real': round(line_oee, 1),
                'oee_planejado': round(linha.meta_oee or 85.0, 1),
                'producao_real_t': round(line_real, 1),
                'producao_planejada_t': round(line_planned, 1),
                'tph_real': round(line_tph, 1),
                'status': line_status,
                'estado_primeiro_equipamento_codigo': estado_primeiro_cod if period == 'turno' else None,
                'estado_primeiro_equipamento': estado_primeiro_txt if period == 'turno' else None,
            })
            total_planned += line_planned
            total_real += line_real
            total_flow_real += line_tph
            if line_oee > 0 or line_status == 'Rodando':
                total_oee_real += line_oee
                active_line_count += 1

        # OEE fabril = média simples dos OEE das linhas que estão ativas.
        # Faz sentido para o usuário: cada linha contribui igualmente.
        # Linhas paradas (oee=0) entram no denominador via active_line_count
        # apenas se status='Rodando' — evita inflar o índice ignorando-as
        # quando deveria penalizar.
        avg_oee = (total_oee_real / active_line_count) if active_line_count > 0 else 0.0
        required_flow = 0.0
        if remaining_h > 0 and total_planned > total_real:
            required_flow = (total_planned - total_real) / remaining_h

        # layout_fabrica vem do cadastro Django (substitui o layout_config
        # hard-coded do Flask). Posições x/y podem ser configuradas em
        # campos no admin futuramente.
        layout_fabrica = [
            {
                'linha': l.codigo,
                'area': (l.area.nome if l.area else 'Outros'),
                'posicao_x': 0,
                'posicao_y': 0,
                'w': 1,
                'h': 1,
                'critico': False,
            }
            for l in active_lines
        ]

        return Response({
            'oee_fabril_real': round(avg_oee, 1),
            'oee_fabril_planejado': 85.0,
            'producao_real_t': round(total_real, 1),
            'producao_planejada_t': round(total_planned, 1),
            'vazao_total_tph': round(total_flow_real, 1),
            'vazao_necessaria_tph': round(required_flow, 1),
            'linhas': lines_kpi,
            'layout_fabrica': layout_fabrica,
        })
    except Exception as e:
        logger.exception('flask_fabrica_kpis falhou')
        return Response({
            'oee_fabril_real': 0, 'oee_fabril_planejado': 0,
            'producao_real_t': 0, 'producao_planejada_t': 0,
            'vazao_total_tph': 0, 'vazao_necessaria_tph': 0,
            'linhas': [], 'layout_fabrica': [],
            'error': str(e),
        })


@api_view(['GET'])
def flask_fabrica_mapa(request):
    """GET /api/fabrica/mapa — substitui Flask routes.py:1440 e
    factory_kpis_engine.get_factory_map_data(). Retorna lista de linhas
    ativas com status (do 1o equipamento) + OLE (max OEE) + layout.
    """
    try:
        client = _influx_client()
        primeiro_eq_map = _primeiro_equipamento_por_linha()
        out = []
        for linha in LinhaProducao.objects.filter(ativa=True).select_related('area'):
            line_code = linha.codigo
            line_status = 'Sem Dados'
            line_ole = 0.0
            estado_cod = None
            primeiro_eq = primeiro_eq_map.get(line_code)
            if primeiro_eq:
                try:
                    q = f"SELECT last(estado_maquina) as state FROM production WHERE \"equipment\" = '{primeiro_eq}'"
                    pts = list(client.query(q).get_points())
                    if pts:
                        estado_cod = int(pts[0].get('state') or 0)
                        line_status = _ESTADOS_MAQUINA.get(estado_cod, str(estado_cod))
                except Exception:
                    pass
            try:
                # OLE da linha = OEE do gargalo (menor TPH > 0), igual em
                # flask_linha_kpis. Mantém coerência entre /fabrica/mapa e
                # /linha/<>/kpis exibidos lado a lado no FactoryPanel.
                q_g = (
                    f"SELECT last(oee_realtime) as oee, "
                    f"last(velocidade_atual) as vel, last(formato_gramas) as fmt "
                    f"FROM production WHERE \"line\" = '{line_code}' GROUP BY \"equipment\""
                )
                rs_g = client.query(q_g)
                rows = []
                for (_, _), pts in rs_g.items():
                    for p in pts:
                        rows.append({
                            'oee': _normalize_oee(p.get('oee')),
                            'tph': _calcular_tph(p.get('vel'), p.get('fmt')),
                        })
                        break
                if rows:
                    candidatos = [r for r in rows if r['tph'] > 0]
                    if candidatos:
                        line_ole = min(candidatos, key=lambda r: r['tph'])['oee']
                    else:
                        line_ole = min(rows, key=lambda r: r['oee'])['oee']
            except Exception:
                pass
            out.append({
                'linha': line_code,
                'status': line_status,
                'ole': round(line_ole, 1),
                'layout': {
                    'area': (linha.area.nome if linha.area else 'Outros'),
                    'pos_x': 0, 'pos_y': 0, 'w': 1, 'h': 1, 'critico': False,
                },
            })
        return Response(out)
    except Exception as e:
        logger.exception('flask_fabrica_mapa falhou')
        return Response([], status=500)


# ===== ONDA 4: /equipamento/dados/<>, /equipamento/<>/historico-detalhado, /operacao/dados/<> =====

@api_view(['GET'])
def flask_equipamento_dados(request, codigo: str):
    """GET /api/equipamento/dados/<codigo> — substitui Flask routes.py:1740.

    Snapshot leve do equipamento (velocidade, estado, peças, refugos)
    para Home e LineDeepView.
    """
    try:
        identity_where = _equipment_identity_where(
            codigo,
            slug=request.query_params.get('equipamento_slug'),
            linha_codigo=request.query_params.get('linha_codigo'),
        )
        q = (
            'SELECT last(estado_maquina) as estado, '
            'last(velocidade_atual) as velocidade_atual, '
            'last(velocidade) as velocidade, '
            'last(contagem_saida) as contagem_saida, '
            'last(producao_turno_acumulada) as producao_turno_acumulada, '
            'last(refugo_turno_acumulado) as refugo_turno_acumulado, '
            'last(descarte_turno_acumulado) as descarte_turno_acumulado, '
            'last(descarte) as descarte '
            f"FROM production WHERE {identity_where}"
        )
        pts = list(_influx_client().query(q).get_points())
        if not pts:
            return Response({
                'velocidade_atual': 0,
                'estado_atual': 'Offline',
                'pecas_produzidas': 0,
                'refugos': 0,
                'timestamp': None,
            })
        p = pts[0]
        estado_int = int(p.get('estado') or 0)
        return Response({
            'velocidade_atual': float(p.get('velocidade_atual') or p.get('velocidade') or 0),
            'estado_atual': _ESTADOS_MAQUINA.get(estado_int, 'Desconhecido'),
            'pecas_produzidas': float(
                p.get('producao_turno_acumulada') or p.get('contagem_saida') or 0
            ),
            'refugos': float(
                p.get('refugo_turno_acumulado')
                or p.get('descarte_turno_acumulado')
                or p.get('descarte')
                or 0
            ),
            'timestamp': p.get('time'),
        })
    except Exception as e:
        logger.exception('flask_equipamento_dados falhou')
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def flask_operacao_dados(request, codigo: str):
    """GET /api/operacao/dados/<codigo> — substitui Flask routes.py:1794.

    Dados operacionais (SKU, OP, CUC, contadores OP+turno). Versão sem
    production_engine in-memory: lê tudo do Influx.
    """
    try:
        # Pega ultimo de cada campo do equipamento.
        identity_where = _equipment_identity_where(
            codigo,
            slug=request.query_params.get('equipamento_slug'),
            linha_codigo=request.query_params.get('linha_codigo'),
        )
        q = f"SELECT last(*) FROM production WHERE {identity_where}"
        pts = list(_influx_client().query(q).get_points())
        if not pts:
            return Response({'error': 'No data'}, status=404)
        d = pts[0]

        def _g(*keys, cast=str, default=None):
            for k in keys:
                v = d.get(f'last_{k}')
                if v is not None:
                    try:
                        return cast(v) if cast else v
                    except (TypeError, ValueError):
                        return default
            return default

        produzido_turno = _g('producao_turno_acumulada', 'contagem_saida', cast=float, default=0) or 0
        refugo_turno = _g('refugo_turno_acumulado', 'descarte_turno_acumulado', 'descarte', cast=float, default=0) or 0
        planejado_op = _g('planejado_op', cast=int, default=0) or 0
        produzido_op = _g('producao_op_acumulada', cast=float, default=0) or 0
        refugo_op = _g('refugo_op_acumulado', cast=float, default=0) or 0
        oee = _normalize_oee(_g('oee_realtime', 'oee', cast=float, default=0) or 0)
        formato_g = _g('formato_gramas', 'formato', cast=float, default=0) or 0

        toneladas_turno = (produzido_turno * formato_g) / 1_000_000.0 if formato_g > 0 else 0
        toneladas_refugo = (refugo_turno * formato_g) / 1_000_000.0 if formato_g > 0 else 0
        toneladas_op = (produzido_op * formato_g) / 1_000_000.0 if formato_g > 0 else 0
        pct_descarte = (
            (refugo_turno / produzido_turno * 100) if produzido_turno > 0 else 0
        )

        return Response({
            'equipamento': codigo,
            'cuc': _g('cuc', cast=str, default='N/A'),
            'sku': _g('sku_codigo', cast=str, default='N/A'),
            'descricao': _g('descricao', cast=str, default='N/A'),
            'ordem_producao': _g('ordem_producao', cast=str, default='N/A'),
            'formato_gramas': formato_g,
            'planejado_op': planejado_op,
            'produzido_op': produzido_op,
            'diferenca_op': max(0, planejado_op - produzido_op),
            'toneladas_op': round(toneladas_op, 3),
            'oee': oee,
            'pecas_boas': max(0, produzido_op - refugo_op),
            'pecas_ruins': refugo_op,
            'produzido_turno': produzido_turno,
            'descarte_turno': refugo_turno,
            'refugo_turno': refugo_turno,
            'pecas_boas_turno': produzido_turno,
            'pecas_ruins_turno': refugo_turno,
            'percentual_descarte_turno': round(pct_descarte, 2),
            'toneladas_turno': round(toneladas_turno, 3),
            'toneladas_refugo_turno': round(toneladas_refugo, 3),
            'turno_atual': 'N/A',
            'timestamp': datetime.utcnow().isoformat(),
        })
    except Exception as e:
        logger.exception('flask_operacao_dados falhou')
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def flask_equipamento_historico_detalhado(request, codigo: str):
    """GET /api/equipamento/<codigo>/historico-detalhado — substitui Flask routes.py:1453.

    Histórico agregado por janela com filtros start/end/interval.
    """
    try:
        start_param = request.query_params.get('start')
        end_param = request.query_params.get('end')
        interval_param = request.query_params.get('interval')
        periodo = request.query_params.get('period', 'hora')
        data_ref = request.query_params.get('date')

        # Resolve janela
        if start_param and end_param:
            try:
                start_time = datetime.fromisoformat(start_param.replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(end_param.replace('Z', '+00:00'))
            except Exception:
                start_time = datetime.utcnow() - timedelta(hours=24)
                end_time = datetime.utcnow()
        else:
            now = datetime.utcnow()
            if data_ref:
                try:
                    dt_ref = datetime.strptime(data_ref, '%Y-%m-%d')
                    start_time = dt_ref.replace(hour=0, minute=0, second=0)
                    end_time = dt_ref.replace(hour=23, minute=59, second=59)
                except Exception:
                    start_time = now - timedelta(hours=24)
                    end_time = now
            else:
                end_time = now
                if periodo == 'dia':
                    start_time = now - timedelta(days=7)
                elif periodo == 'semana':
                    start_time = now - timedelta(weeks=4)
                elif periodo == 'mes':
                    start_time = now - timedelta(days=30)
                elif periodo == 'turno':
                    start_time = now - timedelta(hours=48)
                else:
                    start_time = now - timedelta(hours=24)

        # Resolve agrupamento
        if interval_param in ('total', 'consolidado'):
            group_by = None
        elif interval_param:
            group_by = interval_param
        else:
            group_by = {
                'dia': '1d', 'mes': '1d', 'semana': '1w', 'turno': '8h',
            }.get(periodo, '1h')

        s_str = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
        e_str = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')

        if group_by:
            query = (
                'SELECT spread(contagem_saida) as producao, '
                'spread(contagem_entrada) as entrada, '
                'spread(descarte) as descarte, '
                'mean(velocidade_atual) as velocidade_media, '
                'mean(oee_realtime) as oee_medio, '
                'mean(disponibilidade) as disp_media, '
                'mean(performance) as perf_media, '
                'mean(qualidade) as qual_media, '
                'last(*) '
                f"FROM production WHERE \"equipment\" = '{codigo}' "
                f"AND time >= '{s_str}' AND time <= '{e_str}' "
                f"GROUP BY time({group_by}) fill(0)"
            )
        else:
            # Sem agrupamento por tempo: agregação total
            query = (
                'SELECT spread(contagem_saida) as producao, '
                'spread(contagem_entrada) as entrada, '
                'spread(descarte) as descarte, '
                'mean(velocidade_atual) as velocidade_media, '
                'mean(oee_realtime) as oee_medio '
                f"FROM production WHERE \"equipment\" = '{codigo}' "
                f"AND time >= '{s_str}' AND time <= '{e_str}'"
            )

        pts = list(_influx_client().query(query).get_points())
        historico = []
        for p in pts:
            # Ignora buckets vazios
            if (p.get('producao') or 0) == 0 and (p.get('oee_medio') or 0) == 0:
                continue
            item = {
                'data_hora': p.get('time'),
                'producao': int(p.get('producao') or 0),
                'entrada': int(p.get('entrada') or 0),
                'descarte': int(p.get('descarte') or 0),
                'velocidade_media': float(p.get('velocidade_media') or 0),
                'oee': float(p.get('oee_medio') or 0),
                'disponibilidade': float(p.get('disp_media') or 0),
                'performance': float(p.get('perf_media') or 0),
                'qualidade': float(p.get('qual_media') or 0),
            }
            # Campos dinâmicos last_*
            for k, v in p.items():
                if k.startswith('last_'):
                    clean = k.replace('last_', '')
                    if clean in (
                        'velocidade_atual', 'oee_realtime', 'disponibilidade',
                        'performance', 'qualidade', 'contagem_saida',
                        'contagem_entrada', 'descarte',
                    ):
                        continue
                    item[clean] = v
            historico.append(item)

        return Response({
            'equipamento': codigo,
            'periodo': periodo,
            'historico': historico,
        })
    except Exception as e:
        logger.exception('flask_equipamento_historico_detalhado falhou')
        return Response({'error': str(e)}, status=500)


# ===== ONDA 5: /diagnostics/* + /golden-state/* =====

def _get_equipamento_realtime(codigo: str) -> dict:
    """Lê o snapshot atual de um equipamento do Influx no shape esperado
    pelas regras de diagnóstico (medicoes + timestamp).
    """
    try:
        q = f"SELECT last(*) FROM production WHERE \"equipment\" = '{codigo}'"
        pts = list(_influx_client().query(q).get_points())
        if not pts:
            return {'medicoes': {}, 'timestamp': None}
        p = pts[0]
        medicoes = {}
        for k, v in p.items():
            if k.startswith('last_'):
                medicoes[k[len('last_'):]] = v
        return {'medicoes': medicoes, 'timestamp': p.get('time')}
    except Exception:
        logger.exception('_get_equipamento_realtime falhou')
        return {'medicoes': {}, 'timestamp': None}


def _get_equipment_history(equipamento_codigo: str, minutes: int = 120) -> list[dict]:
    """Histórico de estados do equipamento na janela. Reproduz a lógica
    do Flask backend-flask/services/diagnostics_engine.py."""
    history: list[dict] = []
    try:
        q = (
            f"SELECT estado_maquina FROM production "
            f"WHERE \"equipment\" = '{equipamento_codigo}' "
            f"AND time > now() - {minutes}m "
            f"ORDER BY time ASC"
        )
        pts = list(_influx_client().query(q).get_points())
        if not pts:
            return history
        for i in range(len(pts) - 1):
            curr, nxt = pts[i], pts[i + 1]
            try:
                start_time = datetime.fromisoformat(curr['time'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(nxt['time'].replace('Z', '+00:00'))
                duration = (end_time - start_time).total_seconds()
            except Exception:
                duration = 0
            state_code = int(curr.get('estado_maquina') or 0)
            state_map = {
                0: 'OFFLINE', 1: 'PRODUZINDO', 2: 'WAIT_PREV', 3: 'BLOCK_NEXT',
                4: 'PARADO', 5: 'SETUP', 8: 'MANUTENCAO', 9: 'FALTA_MAT', 11: 'PARTINDO',
            }
            history.append({
                'estado': state_map.get(state_code, f'STATE_{state_code}'),
                'inicio': curr['time'],
                'duracao_segundos': duration,
            })
        # Mais recente primeiro (StarvationRule espera assim)
        history.reverse()
        return history
    except Exception:
        logger.exception('_get_equipment_history falhou')
        return history


def _get_latest_golden_state(equipamento_codigo: str) -> dict | None:
    """Último Golden State capturado para o equipamento."""
    try:
        q = (
            f"SELECT * FROM golden_state_profile "
            f"WHERE equipamento = '{equipamento_codigo}' AND sku != 'N/A' "
            f"ORDER BY time DESC LIMIT 1"
        )
        pts = list(_influx_client().query(q).get_points())
        if pts:
            return pts[0]
        q2 = (
            f"SELECT * FROM golden_state_profile "
            f"WHERE equipamento = '{equipamento_codigo}' "
            f"ORDER BY time DESC LIMIT 1"
        )
        pts = list(_influx_client().query(q2).get_points())
        return pts[0] if pts else None
    except Exception:
        logger.exception('_get_latest_golden_state falhou')
        return None


def _get_golden_state_history(equipamento_codigo: str, sku: str | None = None, limit: int = 20) -> list[dict]:
    """Histórico de Golden States do equipamento."""
    try:
        if sku:
            q = (
                f"SELECT * FROM golden_state_profile "
                f"WHERE equipamento = '{equipamento_codigo}' AND sku = '{sku}' "
                f"ORDER BY time DESC LIMIT {limit}"
            )
        else:
            q = (
                f"SELECT * FROM golden_state_profile "
                f"WHERE equipamento = '{equipamento_codigo}' "
                f"ORDER BY time DESC LIMIT {limit}"
            )
        return list(_influx_client().query(q).get_points())
    except Exception:
        logger.exception('_get_golden_state_history falhou')
        return []


def _evaluate_diagnostic_rules(equipamento_codigo: str, realtime: dict, history: list, golden: dict | None) -> list[dict]:
    """Espelha backend-flask/services/diagnostic_rules.py - 3 regras."""
    alerts: list[dict] = []

    # 1) MicroStopsRule (>4 paradas curtas <60s em 60min)
    if history:
        stops = [
            e for e in history
            if e.get('estado') in ('PARADO', 'FALTA_MAT', 'MANUTENCAO')
            and e.get('duracao_segundos', 0) < 60
        ]
        if len(stops) >= 4:
            alerts.append({
                'rule': 'MicroStops', 'severity': 'warning',
                'message': f'{len(stops)} micro-paradas detectadas nos últimos 60 min.',
                'details': {'stops_count': len(stops), 'threshold': 4},
                'timestamp': datetime.utcnow().isoformat(),
            })

    # 2) StarvationRule (estado WAIT_PREV/BLOCK_NEXT > 10 min)
    if history:
        latest = history[0]
        if latest.get('estado') in ('WAIT_PREV', 'BLOCK_NEXT'):
            try:
                start_t = datetime.fromisoformat(latest['inicio'].replace('Z', '+00:00')).replace(tzinfo=None)
                duration_min = (datetime.utcnow() - start_t).total_seconds() / 60
                if duration_min > 10:
                    state_name = 'Aguardando Anterior' if latest['estado'] == 'WAIT_PREV' else 'Bloqueado pelo Próximo'
                    alerts.append({
                        'rule': 'StarvationBlockage', 'severity': 'warning',
                        'message': f'Equipamento {state_name} por {int(duration_min)} min.',
                        'details': {'state': latest['estado'], 'duration_min': duration_min},
                        'timestamp': datetime.utcnow().isoformat(),
                    })
            except Exception:
                pass

    # 3) GoldenStateDeviationRule (velocidade < 85% do Golden)
    if golden:
        target = golden.get('velocidade_atual')
        current = realtime.get('medicoes', {}).get('velocidade_atual')
        if target and current and target > 0:
            try:
                deviation = abs(float(target) - float(current)) / float(target) * 100
                if deviation > 15 and float(current) < float(target):
                    alerts.append({
                        'rule': 'GoldenStateDeviation', 'severity': 'warning',
                        'message': f'Velocidade {int(deviation)}% abaixo do Golden State ({current} vs {target}).',
                        'details': {
                            'metric': 'velocidade_atual',
                            'current': float(current), 'target': float(target),
                            'deviation': deviation,
                        },
                        'timestamp': datetime.utcnow().isoformat(),
                    })
            except (TypeError, ValueError):
                pass

    return alerts


def _get_equipment_sensors_via_orm(equipamento_codigo: str) -> list[dict]:
    """Retorna sensores do equipamento via ORM Django (substitui chamada
    HTTP do Flask para si mesmo).

    Aceita slug ("L01.E001") ou código curto ("E001"). Para código curto,
    pega o primeiro match — fallback usado apenas em queries internas
    onde a linha já está implícita pelo contexto (ex.: tag Influx contém
    o `equipment` da série). Para evitar ambiguidade em produção, todas
    as chamadas externas devem usar slug.
    """
    if not equipamento_codigo:
        return []
    if '.' in equipamento_codigo:
        # Slug: identificador estável.
        eq = Equipamento.objects.filter(slug=equipamento_codigo).first()
    else:
        # Código curto: legacy. Usa o primeiro match — em base com códigos
        # duplicados, log um warning.
        candidates = Equipamento.objects.filter(codigo=equipamento_codigo)
        n = candidates.count()
        if n > 1:
            logger.warning(
                "_get_equipment_sensors_via_orm: código '%s' encontrado em %d linhas — "
                "usando o primeiro. Migre para slug para evitar isso.",
                equipamento_codigo, n,
            )
        eq = candidates.first()
    if not eq:
        return []
    return [
        {
            'tag_influxdb': s.tag_influxdb,
            'tipo': s.tipo,
            'valor_min': s.valor_min,
            'valor_max': s.valor_max,
            'lsl': s.lsl,
            'usl': s.usl,
            'nominal': s.nominal,
        }
        for s in eq.sensores.all()
    ]


def _capture_golden_state(equipamento_codigo: str, capture_type: str = 'MANUAL') -> dict | None:
    """Captura o estado atual como Golden State (escreve no Influx)."""
    try:
        client = _influx_client()
        rs = client.query(f"SELECT last(*) FROM production WHERE \"equipment\" = '{equipamento_codigo}'")
        pts = list(rs.get_points())
        if not pts:
            return None
        profile = pts[0]
        fields = {
            'velocidade_atual': float(profile.get('last_velocidade_atual') or 0),
            'oee_atual': _normalize_oee(profile.get('last_oee_realtime') or 0),
        }
        for sensor in _get_equipment_sensors_via_orm(equipamento_codigo):
            tag = sensor.get('tag_influxdb')
            if not tag:
                continue
            val = profile.get(f'last_{tag}')
            if val is not None:
                try:
                    fields[tag] = float(val)
                    if sensor.get('valor_min') is not None:
                        fields[f'{tag}_min'] = float(sensor['valor_min'])
                    if sensor.get('valor_max') is not None:
                        fields[f'{tag}_max'] = float(sensor['valor_max'])
                except (TypeError, ValueError):
                    pass
        point = {
            'measurement': 'golden_state_profile',
            'tags': {
                'equipamento': equipamento_codigo,
                'sku': str(profile.get('last_sku_codigo') or 'N/A'),
                'capture_type': capture_type,
            },
            'time': datetime.utcnow().isoformat(),
            'fields': fields,
        }
        client.write_points([point])
        return profile
    except Exception:
        logger.exception('_capture_golden_state falhou')
        return None


@api_view(['GET'])
def flask_diagnostics_alerts(request, equipamento_codigo: str):
    """GET /api/diagnostics/alerts/<codigo> — substitui Flask routes.py:1618."""
    try:
        realtime = _get_equipamento_realtime(equipamento_codigo)
        history = _get_equipment_history(equipamento_codigo)
        sku_filter = request.query_params.get('sku')
        if request.query_params.get('current_sku_only') == 'true':
            med = realtime.get('medicoes', {})
            sku_filter = med.get('sku_codigo') or med.get('sku')
        golden = _get_latest_golden_state(equipamento_codigo)
        alerts = _evaluate_diagnostic_rules(equipamento_codigo, realtime, history, golden)
        gs_history = _get_golden_state_history(equipamento_codigo, sku=sku_filter)
        return Response({
            'status': 'success',
            'alerts': alerts,
            'golden_state': golden,
            'golden_state_history': gs_history,
        })
    except Exception as e:
        logger.exception('flask_diagnostics_alerts falhou')
        return Response({'status': 'error', 'message': str(e)}, status=500)


@api_view(['POST'])
def flask_diagnostics_capture(request, equipamento_codigo: str):
    """POST /api/diagnostics/capture/<codigo> — substitui Flask routes.py:1596."""
    try:
        profile = _capture_golden_state(equipamento_codigo, capture_type='MANUAL')
        if profile:
            return Response({
                'status': 'success',
                'message': 'Golden State captured successfully',
                'profile': profile,
            })
        return Response({
            'status': 'error',
            'message': 'Failed to capture Golden State (no data?)',
        }, status=400)
    except Exception as e:
        logger.exception('flask_diagnostics_capture falhou')
        return Response({'status': 'error', 'message': str(e)}, status=500)


@api_view(['POST'])
def flask_golden_state_apply(request):
    """POST /api/golden-state/apply — substitui Flask blueprints/golden_state.py:10.

    Enfileira comandos para o coletor escrever setpoints/limits no CLP.
    """
    try:
        import uuid
        data = request.data
        eq_codigo = data.get('equipamento_codigo')
        if not eq_codigo:
            return Response({'error': 'equipamento_codigo required'}, status=400)

        profile_time = data.get('profile_timestamp')
        profile = data.get('profile_data') or {}
        if profile_time and not profile:
            q = (
                f"SELECT * FROM golden_state_profile "
                f"WHERE \"equipamento\" = '{eq_codigo}' AND time = '{profile_time}'"
            )
            pts = list(_influx_client().query(q).get_points())
            if not pts:
                return Response({'error': 'Profile not found'}, status=404)
            profile = pts[0]
        if not profile:
            return Response({'error': 'No profile data'}, status=400)

        # Filtra sensores SETPOINT/LIMIT e monta comandos
        sensors = _get_equipment_sensors_via_orm(eq_codigo)
        commands = []
        for sensor in sensors:
            if sensor.get('tipo') not in ('SETPOINT', 'LIMIT'):
                continue
            tag = sensor.get('tag_influxdb')
            if not tag:
                continue
            val = profile.get(tag, profile.get(f'last_{tag}'))
            if val is not None:
                commands.append({'tag': tag, 'value': val})
        if not commands:
            return Response({'status': 'skipped', 'message': 'No writable parameters found.'})

        batch_id = str(uuid.uuid4())
        gs_queue.add_command('GLOBAL', {
            'id': batch_id, 'equipamento_codigo': eq_codigo, 'commands': commands,
        })
        return Response({'status': 'queued', 'batch_id': batch_id, 'count': len(commands)})
    except Exception as e:
        logger.exception('flask_golden_state_apply falhou')
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def flask_golden_state_pending(request):
    """GET /api/golden-state/pending — coletor consome a fila."""
    return Response(gs_queue.get_pending_commands('GLOBAL'))


@api_view(['POST'])
def flask_golden_state_callback(request):
    """POST /api/golden-state/callback — coletor reporta status."""
    data = request.data or {}
    batch_id = data.get('batch_id')
    status_str = data.get('status')
    if not batch_id or not status_str:
        return Response({'error': 'Invalid data'}, status=400)
    gs_queue.update_command_status(
        batch_id, status_str, data.get('message', ''), int(data.get('progress', 0) or 0)
    )
    return Response({'status': 'ok'})


@api_view(['GET'])
def flask_golden_state_status(request, batch_id: str):
    """GET /api/golden-state/status/<batch_id> — frontend polleia progresso."""
    return Response(gs_queue.get_command_status(batch_id))


# ===== ONDA 7: /api/dados/inserir (CRÍTICO — caminho hot do coletor) =====

def _processar_item_ingestao(item: dict, influx_client, engine) -> bool:
    """Processa 1 payload de equipamento: roda production_engine + escreve Influx.
    Retorna True se OK.

    Identificação do equipamento (Solução 2 da identidade ISA-95):
      - preferencial: `equipamento_slug` ("L01.E001")
      - fallback: `equipamento_codigo` + `linha_codigo`
      - legacy: `equipamento_codigo` sozinho (só funciona se único globalmente)
    """
    try:
        from .resolvers import (
            resolver_de_payload,
            EquipamentoAmbiguo,
            EquipamentoIdentityConflict,
        )
        from .models import Equipamento as _Eq
        try:
            equipamento = resolver_de_payload(item)
        except EquipamentoAmbiguo as exc:
            logger.warning(
                "dados/inserir: código '%s' ambíguo (%d opções) — rejeitado. "
                "Coletor precisa enviar equipamento_slug ou linha_codigo.",
                exc.codigo, len(exc.opcoes),
            )
            return False
        except EquipamentoIdentityConflict as exc:
            logger.error("dados/inserir: %s Payload rejeitado.", exc)
            return False
        except _Eq.DoesNotExist:
            logger.warning(
                "dados/inserir: equipamento não encontrado · payload=%s",
                {k: item.get(k) for k in ('equipamento_slug', 'equipamento_codigo', 'linha_codigo')},
            )
            return False
        except (ValueError, TypeError):
            return False

        eq = equipamento.codigo  # mantém retrocompat para tag `equipment`
        slug = equipamento.slug   # nova tag canônica `equipment_slug`
        linha_obj = equipamento.linha
        area_obj = linha_obj.area if linha_obj else None
        fabrica_obj = area_obj.fabrica if area_obj else None
        line = linha_obj.codigo if linha_obj else _normalize_line_name(item.get('linha_codigo', ''))
        identity_key = slug or (f"{line}.{eq}" if line else eq)
        ts = item.get('timestamp')
        m = item.get('medicoes') or {}
        if not eq or not m:
            return False

        # OFFLINE explícito: PLC marcado offline vira estado=999 (NÃO 0)
        is_offline = m.get('plc_offline', False) or m.get('connection_status') == 'OFFLINE'
        if is_offline:
            if int(m.get('estado_maquina', 0) or 0) != 999:
                m['estado_maquina'] = 999
            m['velocidade_atual'] = 0
            m['oee'] = 0

        estado_raw = m.get('estado_maquina', m.get('estado', 0))
        est = _event_code_from_payload(estado_raw)
        try:
            _sync_estado_timeline(equipamento, estado_raw, ts)
        except Exception:
            logger.exception(
                'Falha ao sincronizar timeline de estado para %s (%s)',
                slug or eq,
                estado_raw,
            )
        cont = int(float(m.get('contagem_saida', 0)))
        desc = int(float(m.get('descarte', 0)))
        op = str(m.get('ordem_producao', 'N/A'))
        sku = str(m.get('sku_codigo', 'N/A'))
        plan = int(float(m.get('planejado_op', 0)))
        fmt = float(m.get('formato_gramas') or m.get('formato') or 0)
        cont_in = int(float(m.get('contagem_entrada', 0)))
        if cont_in > 0:
            desc = max(desc, cont_in - cont, 0)

        # Zero é uma leitura OPC válida (equipamento parado), não ausência de
        # dado. A cadeia com ``or`` descartava o zero e recalculava velocidade
        # pelo contador, podendo exibir máquina em movimento quando estava
        # parada. Só fazemos fallback quando a chave realmente não veio.
        vel_real = next(
            (
                m.get(field)
                for field in ('velocidade_atual', 'velocidade_real', 'velocidade')
                if m.get(field) is not None
            ),
            None,
        )
        if vel_real is not None:
            vel_calc = int(float(vel_real))
        else:
            vel_calc = _calc_speed_rpm(identity_key, cont)

        res = engine.processar_dados(
            equipamento=eq,
            op_atual=op,
            contagem_bruta=cont,
            descarte=desc,
            formato_gramas=fmt,
            planejado=plan,
            velocidade_atual=vel_calc,
            estado_maquina=est,
            contagem_entrada=cont_in,
            equipamento_slug=slug,
            linha_codigo=line,
            extra_context={
                'sku_codigo': sku,
                'descricao': str(m.get('descricao', 'N/A')),
                'cuc': str(m.get('cuc', 'N/A')),
                'ordem_producao': op,
                'formato_gramas': fmt,
            },
        )

        fields = {
            'velocidade_atual': vel_calc,
            'estado_maquina': est,
            'ordem_producao_field': op,
            'sku_codigo_field': sku,
            'producao_op_acumulada': res.get('producao_op', 0),
            'contagem_saida': cont,
            'contagem_entrada': cont_in,
            'descarte': desc,
            'toneladas_op': res.get('toneladas_op', 0),
            'diferenca_op': res.get('diferenca_op', 0),
            'producao_turno_acumulada': res.get('producao_turno', 0),
            'refugo_turno_acumulado': res.get('refugo_turno_acumulado', 0),
            'descarte_turno_acumulado': res.get('descarte_turno', 0),
            'toneladas_turno': res.get('toneladas_turno', 0),
            'toneladas_refugo_turno': res.get('toneladas_refugo_turno', 0),
            'percentual_descarte_turno': res.get('percentual_descarte_turno', 0),
            'oee_realtime': res.get('oee_realtime', 0),
            'performance_realtime': res.get('performance_realtime', 0),
            'quality_realtime': res.get('quality_realtime', 0),
            'availability_realtime': res.get('availability_realtime', 0),
            'refugo_op_acumulado': res.get('refugo_op_acumulado', 0),
            'tempo_parado_turno': res.get('tempo_parado_segundos', 0),
            'tempo_planejado_turno': res.get('tempo_planejado_segundos', 0),
            'planejado_op': plan,
            'timestamp_medicao': time.time(),
        }
        _add_dynamic_fields(fields, m)

        # Tags hierárquicas (factory/area/line/equipment) derivadas do
        # Repository — fonte única de verdade. Garante que TODA escrita
        # carregue a hierarquia completa, sem espaço para esquecer tag.
        from .influx_repository import EquipamentoInflux
        point_tags = dict(EquipamentoInflux(equipamento).tags)
        # Dimensões contextuais do ponto (turno, OP, SKU) — não fazem
        # parte da identidade do equipamento mas servem como filtros em
        # análises de produção.
        point_tags.update({
            'shift': res.get('turno_atual_nome', 'N/A'),
            'order_id': op,
            'sku': sku,
        })

        point = {
            'measurement': 'production',
            'tags': point_tags,
            'time': ts if ts else None,
            'fields': fields,
        }
        _write_points_resilient(influx_client, [point])
        return True
    except Exception:
        logger.exception('Erro processando item de ingestao')
        return False


@api_view(['POST'])
def flask_dados_inserir(request):
    """POST /api/dados/inserir — substitui Flask routes.py:539.

    Endpoint hot do coletor: recebe payload (single ou list), roda o
    production_engine para calcular OEE realtime + escreve no Influx.
    """
    try:
        influx_client = _influx_client()
        engine = _get_production_engine()
        data = request.data
        if data is None:
            return Response({'error': 'Body vazio'}, status=400)
        if isinstance(data, list):
            ok = 0
            for item in data:
                if _processar_item_ingestao(item, influx_client, engine):
                    ok += 1
            return Response({'status': 'success', 'processed': ok, 'total': len(data)})
        # Single payload
        if _processar_item_ingestao(data, influx_client, engine):
            return Response({'status': 'success'})
        return Response({'error': 'Dados incompletos'}, status=400)
    except Exception as e:
        logger.exception('flask_dados_inserir falhou')
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def flask_shift_reset(request):
    """POST /api/shift/reset — substitui Flask routes.py:191.

    Reset manual de turno: força o engine a recalcular o turno corrente
    e zerar os contadores acumulados de turno.
    """
    try:
        engine = _get_production_engine()
        # recarregar_configuracoes() chama shift_manager.forcar_atualizacao()
        # internamente + atualiza ConfigManager (velocidades nominais).
        engine.recarregar_configuracoes()
        engine.reset_shift_counters()
        return Response({'status': 'reset', 'message': 'Turno re-avaliado.'})
    except Exception as e:
        logger.exception('flask_shift_reset falhou')
        return Response({'error': str(e)}, status=500)
