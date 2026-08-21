"""
API de Análise de Descartes - Dashboard Dedicado
Endpoints para análise consolidada de descartes por linha, período e fábrica.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import datetime, timedelta
import pytz
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Configurações
FLASK_API_URL = "http://mis-core-flask:5000/api"
INFLUXDB_HOST = settings.INFLUXDB_HOST
INFLUXDB_PORT = settings.INFLUXDB_PORT
INFLUXDB_DATABASE = settings.INFLUXDB_DATABASE
INFLUXDB_USER = settings.INFLUXDB_USER
INFLUXDB_PASSWORD = settings.INFLUXDB_PASSWORD


def get_turno_atual():
    """Retorna horários do turno atual baseado na hora local."""
    tz = pytz.timezone('America/Sao_Paulo')
    now = datetime.now(tz)
    hora = now.hour

    # Turnos: 06:00-14:00, 14:00-22:00, 22:00-06:00
    if 6 <= hora < 14:
        inicio = now.replace(hour=6, minute=0, second=0, microsecond=0)
        fim = now.replace(hour=14, minute=0, second=0, microsecond=0)
        turno_nome = "Turno 1 (06:00-14:00)"
    elif 14 <= hora < 22:
        inicio = now.replace(hour=14, minute=0, second=0, microsecond=0)
        fim = now.replace(hour=22, minute=0, second=0, microsecond=0)
        turno_nome = "Turno 2 (14:00-22:00)"
    else:
        if hora >= 22:
            inicio = now.replace(hour=22, minute=0, second=0, microsecond=0)
            fim = (now + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
        else:
            inicio = (now - timedelta(days=1)).replace(hour=22, minute=0, second=0, microsecond=0)
            fim = now.replace(hour=6, minute=0, second=0, microsecond=0)
        turno_nome = "Turno 3 (22:00-06:00)"

    return inicio, fim, turno_nome


def get_periodo_range(periodo: str, data_inicio: str = None, data_fim: str = None):
    """Retorna range de datas baseado no período selecionado."""
    tz = pytz.timezone('America/Sao_Paulo')
    now = datetime.now(tz)

    if periodo == 'TURNO':
        inicio, fim, nome = get_turno_atual()
        return inicio, now, nome
    elif periodo == 'DIA':
        inicio = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return inicio, now, f"Hoje ({now.strftime('%d/%m/%Y')})"
    elif periodo == 'SEMANA':
        inicio = now - timedelta(days=now.weekday())
        inicio = inicio.replace(hour=0, minute=0, second=0, microsecond=0)
        return inicio, now, "Esta Semana"
    elif periodo == 'MES':
        inicio = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return inicio, now, f"Este Mês ({now.strftime('%B/%Y')})"
    elif periodo == 'ANO':
        inicio = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return inicio, now, f"Este Ano ({now.year})"
    elif periodo == 'CUSTOM' and data_inicio and data_fim:
        inicio = datetime.fromisoformat(data_inicio).replace(tzinfo=tz)
        fim = datetime.fromisoformat(data_fim).replace(tzinfo=tz)
        return inicio, fim, f"{inicio.strftime('%d/%m')} a {fim.strftime('%d/%m/%Y')}"
    else:
        # Default: último turno
        inicio, fim, nome = get_turno_atual()
        return inicio, now, nome


def query_influxdb(query: str):
    """Executa query no InfluxDB e retorna resultados."""
    try:
        from influxdb import InfluxDBClient
        client = InfluxDBClient(
            host=INFLUXDB_HOST,
            port=INFLUXDB_PORT,
            username=INFLUXDB_USER,
            password=INFLUXDB_PASSWORD,
            database=INFLUXDB_DATABASE
        )
        result = client.query(query)
        return list(result.get_points())
    except Exception as e:
        logger.error(f"Erro InfluxDB: {e}")
        return []


ESTADO_MAP = {
    -1: 'Indefinido',
    0: 'Parado',
    1: 'Produzindo',
    2: 'Aguardando',
    3: 'Bloqueado',
    4: 'Falha',
    5: 'Setup',
    6: 'Teste',
    7: 'Aguardando manutencao',
    8: 'Manutencao',
    9: 'Falta de material',
    10: 'Outro',
    11: 'Partindo',
    12: 'Aguardando condicoes',
    13: 'Parando',
    999: 'Offline',
}

ESTADO_INDEFINIDO_CODE = '-1'


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _first_present(point, *keys):
    for key in keys:
        value = point.get(key)
        if value not in (None, ''):
            return value
    return None


def _counter_delta(current, previous):
    current = _safe_float(current, None)
    if current is None:
        return 0.0
    if previous is None:
        return 0.0
    previous = _safe_float(previous, 0.0)
    delta = current - previous
    if delta >= 0:
        return delta
    # Reset de contador no periodo: o valor atual passa a representar o novo acumulado.
    return max(current, 0.0)


def _split_filter(value):
    if not value or str(value).lower() in ('todos', 'all'):
        return set()
    return {part.strip().lower() for part in str(value).split(',') if part.strip()}


def _matches_filter(value, selected):
    if not selected:
        return True
    normalized = str(value or '').strip().lower()
    return normalized in selected


def _state_label(code):
    return ESTADO_MAP.get(_safe_int(code, -1), f'Estado {code}')


def _format_code(value):
    value = _safe_float(value, 0.0)
    if value <= 0:
        return 'sem-formato'
    if value.is_integer():
        return str(int(value))
    return f'{value:g}'


def _format_label(value):
    code = _format_code(value)
    if code == 'sem-formato':
        return 'Sem formato'
    return f'{code} g'


def _product_info(point):
    # sku_codigo_field e um vestigio de uma renomeacao antiga. Mantido na lista
    # como fallback defensivo enquanto coletor/Influx convivem com dados legados.
    code = _first_present(point, 'sku_codigo', 'sku_codigo_field', 'produto')
    desc = _first_present(point, 'descricao', 'produto')
    code = str(code or '').strip()
    desc = str(desc or '').strip()
    if not code or code.lower() in ('none', 'n/a', 'nan'):
        code = 'sem-produto'
    label = desc if desc and desc.lower() not in ('none', 'n/a', 'nan') else code
    if code != 'sem-produto' and label != code:
        label = f'{code} - {label}'
    if code == 'sem-produto':
        label = 'Sem produto'
    return code, label


def _waste_counter(point):
    return _first_present(
        point,
        'refugo_turno',
        'descarte_turno',
        'refugo_op',
        'descarte_raw',
    )


def _production_counter(point):
    return _first_present(point, 'prod_turno', 'prod')


def _parse_influx_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None


def _local_dt(value):
    dt = _parse_influx_time(value) if isinstance(value, str) else value
    if not dt:
        return None
    tz = pytz.timezone('America/Sao_Paulo')
    if dt.tzinfo is None:
        return tz.localize(dt)
    return dt.astimezone(tz)


def _time_bucket_minute(dt):
    local = _local_dt(dt)
    if not local:
        return ''
    return local.replace(second=0, microsecond=0).isoformat()


def _line_status_from_states(states):
    values = [_safe_int(value, 999) for value in states]
    if not values:
        return '999', 'Offline'
    first_state = values[0]
    if first_state == 4:
        return '4', 'Falha/Quebra'
    if first_state in (5, 6, 7, 8):
        return '5', 'Manutencao/Setup'
    if first_state in (2, 3, 9, 12):
        return '2', 'Aguardando/Bloqueada'
    if first_state in (1, 11):
        return '1', 'Produzindo'
    if first_state == 999:
        return '999', 'Offline'
    return '0', 'Parada'


def _equipment_sort_key(equipment):
    order = equipment.ordem_na_linha
    if order is None:
        order = 999999
    return order, equipment.codigo or ''


def _shift_intervals_for_period(turno, dt_inicio, dt_fim):
    if not turno:
        return []

    tz = pytz.timezone('America/Sao_Paulo')
    start_local = _local_dt(dt_inicio)
    end_local = _local_dt(dt_fim)
    if not start_local or not end_local:
        return []

    intervals = []
    day = (start_local - timedelta(days=1)).date()
    last_day = end_local.date()
    while day <= last_day:
        inicio = tz.localize(datetime.combine(day, turno.hora_inicio))
        fim_day = day if turno.hora_fim > turno.hora_inicio else day + timedelta(days=1)
        fim = tz.localize(datetime.combine(fim_day, turno.hora_fim))
        if fim >= start_local and inicio <= end_local:
            intervals.append((max(inicio, start_local), min(fim, end_local)))
        day += timedelta(days=1)
    return intervals


def _matches_shift(dt, intervals):
    if not intervals:
        return True
    local = _local_dt(dt)
    if not local:
        return False
    return any(start <= local <= end for start, end in intervals)


def _fallback_turnos():
    from types import SimpleNamespace
    from datetime import time
    return [
        SimpleNamespace(codigo='T1', nome='Turno 1', hora_inicio=time(6, 0), hora_fim=time(14, 0)),
        SimpleNamespace(codigo='T2', nome='Turno 2', hora_inicio=time(14, 0), hora_fim=time(22, 0)),
        SimpleNamespace(codigo='T3', nome='Turno 3', hora_inicio=time(22, 0), hora_fim=time(6, 0)),
    ]


class WasteDashboardSummaryView(APIView):
    """
    GET /api/descartes/resumo/

    Retorna resumo consolidado de descartes para as linhas selecionadas.

    Query Params:
    - linhas: L01,L02 ou 'todas'
    - periodo: TURNO|DIA|SEMANA|MES|ANO|CUSTOM
    - data_inicio: ISO date (para CUSTOM)
    - data_fim: ISO date (para CUSTOM)
    """

    def _get_v2(self, request):
        # Parametros
        linhas_param = request.query_params.get('linhas', 'todas')
        periodo = request.query_params.get('periodo', 'TURNO')
        data_inicio = request.query_params.get('data_inicio')
        data_fim = request.query_params.get('data_fim')
        produto_filter = _split_filter(request.query_params.get('produto'))
        formato_filter = _split_filter(request.query_params.get('formato'))
        estado_filter = _split_filter(request.query_params.get('estado'))

        dt_inicio, dt_fim, periodo_label = get_periodo_range(periodo, data_inicio, data_fim)

        from .models import LinhaProducao, Equipamento

        if linhas_param == 'todas':
            linhas_qs = LinhaProducao.objects.all()
        else:
            codigos = [c.strip() for c in linhas_param.split(',')]
            linhas_qs = LinhaProducao.objects.filter(codigo__in=codigos)

        linhas = list(linhas_qs)
        if not linhas:
            return Response({'error': 'Nenhuma linha encontrada'}, status=404)

        equipamentos = list(
            Equipamento.objects
            .filter(linha__in=linhas)
            .select_related('linha')
            .order_by('linha__codigo', 'ordem_na_linha', 'codigo')
        )
        equipamentos_por_linha = {}
        for eq in equipamentos:
            equipamentos_por_linha.setdefault(eq.linha_id, []).append(eq)
        for items in equipamentos_por_linha.values():
            items.sort(key=_equipment_sort_key)

        dados_por_linha = []
        total_descarte_tons = 0.0
        total_producao_tons = 0.0
        total_unidades_ruins = 0.0
        top_equipamentos = []
        evolucao_temporal = {}
        descarte_por_estado_raw = {}
        descarte_por_produto_raw = {}
        descarte_por_formato_raw = {}
        matriz_estado_produto_raw = {}
        produtos_disponiveis = {}
        formatos_disponiveis = {}
        estados_disponiveis = {}
        pontos_sem_estado = 0  # diagnose: pontos sem 'estado_maquina' no Influx

        for linha in linhas:
            linha_descarte_tons = 0.0
            linha_producao_tons = 0.0
            linha_unidades = 0.0

            query_inicio = dt_inicio - timedelta(minutes=5)

            for eq in equipamentos_por_linha.get(linha.id, []):
                query_series = f"""
                    SELECT LAST("refugo_turno_acumulado") as "refugo_turno",
                           LAST("descarte_turno_acumulado") as "descarte_turno",
                           LAST("refugo_op_acumulado") as "refugo_op",
                           LAST("descarte") as "descarte_raw",
                           LAST("producao_turno_acumulada") as "prod_turno",
                           LAST("contagem_saida") as "prod",
                           LAST("estado_maquina") as "state",
                           LAST("formato_gramas") as "fmt",
                           LAST("formato") as "fmt_alt",
                           LAST("sku_codigo") as "sku_codigo",
                           LAST("sku_codigo_field") as "sku_codigo_field",
                           LAST("descricao") as "descricao",
                           LAST("produto") as "produto"
                    FROM "production"
                    WHERE "equipment" = '{eq.codigo}'
                    AND time >= '{query_inicio.isoformat()}' AND time <= '{dt_fim.isoformat()}'
                    GROUP BY time(1m)
                """
                points = query_influxdb(query_series)

                eq_refugo_delta = 0.0
                eq_prod_delta = 0.0
                eq_descarte_tons = 0.0
                eq_prod_tons = 0.0
                last_waste_counter = None
                last_prod_counter = None
                last_state_code = None  # carry-forward do ultimo state valido

                for point in points:
                    product_code, product_label = _product_info(point)
                    formato_raw = _first_present(point, 'fmt', 'fmt_alt')
                    formato_code = _format_code(formato_raw)
                    formato_label = _format_label(formato_raw)
                    # Resolve state: nao usar default fixo (1=Produzindo) porque
                    # isso fazia todo descarte aparecer como ocorrido em PRODUZINDO.
                    # Prefere o ultimo state conhecido na janela; se nunca houve,
                    # marca como Indefinido.
                    raw_state = point.get('state')
                    state_int = None
                    if raw_state not in (None, ''):
                        try:
                            state_int = int(float(raw_state))
                        except (TypeError, ValueError):
                            state_int = None
                    if state_int is None:
                        state_int = last_state_code  # carry-forward
                    else:
                        last_state_code = state_int
                    if state_int is None:
                        state_code = ESTADO_INDEFINIDO_CODE
                        pontos_sem_estado += 1
                    else:
                        state_code = str(state_int)
                    state_label = _state_label(state_code)

                    waste_counter = _waste_counter(point)
                    prod_counter = _production_counter(point)
                    diff_refugo = _counter_delta(waste_counter, last_waste_counter)
                    diff_prod = _counter_delta(prod_counter, last_prod_counter)
                    last_waste_counter = _safe_float(waste_counter, last_waste_counter)
                    last_prod_counter = _safe_float(prod_counter, last_prod_counter)

                    point_dt = _parse_influx_time(point.get('time'))
                    if point_dt and point_dt < dt_inicio:
                        continue

                    produtos_disponiveis[product_code] = product_label
                    formatos_disponiveis[formato_code] = formato_label
                    estados_disponiveis[state_code] = state_label

                    if not (
                        _matches_filter(product_code, produto_filter)
                        and _matches_filter(formato_code, formato_filter)
                        and _matches_filter(state_code, estado_filter)
                    ):
                        continue

                    formato = _safe_float(formato_raw, 500.0) or 500.0
                    tons_refugo = (diff_refugo * formato) / 1000000.0
                    tons_prod = (diff_prod * formato) / 1000000.0

                    eq_refugo_delta += diff_refugo
                    eq_prod_delta += diff_prod
                    eq_descarte_tons += tons_refugo
                    eq_prod_tons += tons_prod

                    bucket = point.get('time', '')[:13] if point.get('time') else ''
                    if bucket:
                        temporal = evolucao_temporal.setdefault(bucket, {'descarte': 0.0, 'producao': 0.0})
                        temporal['descarte'] += diff_refugo
                        temporal['producao'] += diff_prod

                    if diff_refugo > 0:
                        descarte_por_estado_raw[state_code] = descarte_por_estado_raw.get(state_code, 0.0) + tons_refugo

                        produto_bucket = descarte_por_produto_raw.setdefault(product_code, {
                            'produto': product_label,
                            'codigo': product_code,
                            'tons': 0.0,
                            'unidades': 0.0,
                        })
                        produto_bucket['tons'] += tons_refugo
                        produto_bucket['unidades'] += diff_refugo

                        formato_bucket = descarte_por_formato_raw.setdefault(formato_code, {
                            'formato': formato_label,
                            'codigo': formato_code,
                            'tons': 0.0,
                            'unidades': 0.0,
                        })
                        formato_bucket['tons'] += tons_refugo
                        formato_bucket['unidades'] += diff_refugo

                        matrix_key = (state_code, product_code)
                        matrix_bucket = matriz_estado_produto_raw.setdefault(matrix_key, {
                            'estado_code': _safe_int(state_code),
                            'estado_label': state_label,
                            'produto': product_label,
                            'produto_codigo': product_code,
                            'tons': 0.0,
                            'unidades': 0.0,
                        })
                        matrix_bucket['tons'] += tons_refugo
                        matrix_bucket['unidades'] += diff_refugo

                linha_descarte_tons += eq_descarte_tons
                linha_producao_tons += eq_prod_tons
                linha_unidades += eq_refugo_delta

                if eq_refugo_delta > 0:
                    top_equipamentos.append({
                        'equipamento': eq.nome,
                        'linha': linha.nome,
                        'unidades': int(eq_refugo_delta),
                        'tons': round(eq_descarte_tons, 4),
                        'percentual': 0,
                    })

            linha_percentual = (linha_descarte_tons / linha_producao_tons * 100) if linha_producao_tons > 0 else 0
            dados_por_linha.append({
                'linha': linha.nome,
                'codigo': linha.codigo,
                'descarte_tons': round(linha_descarte_tons, 4),
                'descarte_percentual': round(linha_percentual, 2),
                'producao_tons': round(linha_producao_tons, 3),
                'unidades_ruins': int(linha_unidades),
            })

            total_descarte_tons += linha_descarte_tons
            total_producao_tons += linha_producao_tons
            total_unidades_ruins += linha_unidades

        for eq in top_equipamentos:
            eq['percentual'] = round((eq['tons'] / total_descarte_tons * 100) if total_descarte_tons > 0 else 0, 1)
        top_equipamentos = sorted(top_equipamentos, key=lambda x: x['tons'], reverse=True)[:10]
        linha_maior_descarte = max(dados_por_linha, key=lambda x: x['descarte_tons']) if dados_por_linha else None
        percentual_consolidado = (total_descarte_tons / total_producao_tons * 100) if total_producao_tons > 0 else 0

        evolucao_temporal = [
            {
                'hora': bucket,
                'descarte': round(values['descarte'], 3),
                'producao': round(values['producao'], 3),
            }
            for bucket, values in sorted(evolucao_temporal.items())
        ]

        descarte_por_estado = []
        for state_code, tons in descarte_por_estado_raw.items():
            descarte_por_estado.append({
                'estado_code': _safe_int(state_code),
                'estado_label': _state_label(state_code),
                'tons': round(tons, 4),
                'percentual': 0,
            })
        total_waste_state = sum(d['tons'] for d in descarte_por_estado)
        for d in descarte_por_estado:
            d['percentual'] = round((d['tons'] / total_waste_state * 100) if total_waste_state > 0 else 0, 1)
        descarte_por_estado = sorted(descarte_por_estado, key=lambda x: x['tons'], reverse=True)

        descarte_por_produto = []
        for item in descarte_por_produto_raw.values():
            descarte_por_produto.append({
                'codigo': item['codigo'],
                'produto': item['produto'],
                'tons': round(item['tons'], 4),
                'unidades': int(item['unidades']),
                'percentual': round((item['tons'] / total_descarte_tons * 100) if total_descarte_tons > 0 else 0, 1),
            })
        descarte_por_produto = sorted(descarte_por_produto, key=lambda x: x['tons'], reverse=True)[:12]

        descarte_por_formato = []
        for item in descarte_por_formato_raw.values():
            descarte_por_formato.append({
                'codigo': item['codigo'],
                'formato': item['formato'],
                'tons': round(item['tons'], 4),
                'unidades': int(item['unidades']),
                'percentual': round((item['tons'] / total_descarte_tons * 100) if total_descarte_tons > 0 else 0, 1),
            })
        descarte_por_formato = sorted(descarte_por_formato, key=lambda x: x['tons'], reverse=True)[:12]

        matriz_estado_produto = []
        for item in matriz_estado_produto_raw.values():
            matriz_estado_produto.append({
                'estado_code': item['estado_code'],
                'estado_label': item['estado_label'],
                'produto_codigo': item['produto_codigo'],
                'produto': item['produto'],
                'tons': round(item['tons'], 4),
                'unidades': int(item['unidades']),
                'percentual': round((item['tons'] / total_descarte_tons * 100) if total_descarte_tons > 0 else 0, 1),
            })
        matriz_estado_produto = sorted(matriz_estado_produto, key=lambda x: x['tons'], reverse=True)[:20]

        estado_critico = descarte_por_estado[0] if descarte_por_estado else None
        produto_critico = descarte_por_produto[0] if descarte_por_produto else None
        formato_critico = descarte_por_formato[0] if descarte_por_formato else None
        if total_descarte_tons > 0:
            partes = []
            if estado_critico:
                partes.append(f"{estado_critico['percentual']}% em {estado_critico['estado_label']}")
            if produto_critico:
                partes.append(f"produto {produto_critico['produto']}")
            if formato_critico:
                partes.append(f"formato {formato_critico['formato']}")
            insight_msg = "Maior concentracao observada: " + ", ".join(partes) + "."
        else:
            insight_msg = "Nao houve descarte real contabilizado para os filtros selecionados."

        return Response({
            'periodo': periodo,
            'periodo_label': periodo_label,
            'data_inicio': dt_inicio.isoformat(),
            'data_fim': dt_fim.isoformat(),
            'linhas_selecionadas': [l.nome for l in linhas],
            'filtros_aplicados': {
                'produto': sorted(produto_filter) if produto_filter else ['todos'],
                'formato': sorted(formato_filter) if formato_filter else ['todos'],
                'estado': sorted(estado_filter) if estado_filter else ['todos'],
            },
            'filtros_disponiveis': {
                'produtos': [
                    {'codigo': code, 'label': label}
                    for code, label in sorted(produtos_disponiveis.items(), key=lambda item: item[1])
                ],
                'formatos': [
                    {'codigo': code, 'label': label}
                    for code, label in sorted(
                        formatos_disponiveis.items(),
                        key=lambda item: _safe_float(item[0], 999999.0)
                    )
                ],
                'estados': [
                    {'codigo': code, 'label': label}
                    for code, label in sorted(
                        estados_disponiveis.items(),
                        key=lambda item: _safe_int(item[0], 999999)
                    )
                ],
            },
            'consolidado': {
                'descarte_tons': round(total_descarte_tons, 4),
                'descarte_percentual': round(percentual_consolidado, 2),
                'producao_tons': round(total_producao_tons, 3),
                'total_unidades': int(total_unidades_ruins),
            },
            'por_linha': dados_por_linha,
            'top_equipamentos': top_equipamentos,
            'linha_maior_descarte': linha_maior_descarte,
            'evolucao_temporal': evolucao_temporal[:24],
            'descarte_por_estado': descarte_por_estado,
            'descarte_por_produto': descarte_por_produto,
            'descarte_por_formato': descarte_por_formato,
            'matriz_estado_produto': matriz_estado_produto,
            'diagnostico': {
                # Quantos pontos do Influx vieram sem o campo 'estado_maquina'
                # depois de aplicar carry-forward. Util para alertar quando a
                # qualidade do dado de estado esta degradada.
                'pontos_sem_estado': pontos_sem_estado,
            },
            'insight': {
                'titulo': 'Leitura do periodo',
                'mensagem': insight_msg,
                'estado_critico': estado_critico,
                'produto_critico': produto_critico,
                'formato_critico': formato_critico,
            },
        })

    def _get_v3(self, request):
        linhas_param = request.query_params.get('linhas', 'todas')
        periodo = request.query_params.get('periodo', 'TURNO')
        data_inicio = request.query_params.get('data_inicio')
        data_fim = request.query_params.get('data_fim')
        turno_param = request.query_params.get('turno', 'todos')
        produto_filter = _split_filter(request.query_params.get('produto'))
        formato_filter = _split_filter(request.query_params.get('formato'))
        estado_equipamento_filter = _split_filter(
            request.query_params.get('estado_equipamento') or request.query_params.get('estado')
        )
        estado_linha_filter = _split_filter(request.query_params.get('estado_linha'))

        dt_inicio, dt_fim, periodo_label = get_periodo_range(periodo, data_inicio, data_fim)

        from .models import LinhaProducao, Equipamento, TurnoProducao

        if linhas_param == 'todas':
            linhas_qs = LinhaProducao.objects.all()
        else:
            codigos = [c.strip() for c in linhas_param.split(',')]
            linhas_qs = LinhaProducao.objects.filter(codigo__in=codigos)

        linhas = list(linhas_qs)
        if not linhas:
            return Response({'error': 'Nenhuma linha encontrada'}, status=404)

        turnos = list(TurnoProducao.objects.filter(ativo=True).order_by('hora_inicio'))
        if not turnos:
            turnos = _fallback_turnos()
        turnos_by_code = {str(t.codigo).lower(): t for t in turnos}
        selected_turno = None
        if turno_param and turno_param.lower() not in ('todos', 'all'):
            selected_turno = turnos_by_code.get(turno_param.lower())
        shift_intervals = _shift_intervals_for_period(selected_turno, dt_inicio, dt_fim)

        equipamentos = list(
            Equipamento.objects
            .filter(linha__in=linhas)
            .select_related('linha')
            .order_by('linha__codigo', 'ordem_na_linha', 'codigo')
        )
        equipamentos_por_linha = {}
        for eq in equipamentos:
            equipamentos_por_linha.setdefault(eq.linha_id, []).append(eq)
        for items in equipamentos_por_linha.values():
            items.sort(key=_equipment_sort_key)

        query_inicio = dt_inicio - timedelta(minutes=5)
        events = []
        production_events = []
        line_states_by_bucket = {}
        line_state_timeline = {}
        produtos_disponiveis = {}
        formatos_disponiveis = {}
        estados_equipamento_disponiveis = {}

        for linha in linhas:
            for eq in equipamentos_por_linha.get(linha.id, []):
                query_series = f"""
                    SELECT LAST("refugo_turno_acumulado") as "refugo_turno",
                           LAST("descarte_turno_acumulado") as "descarte_turno",
                           LAST("refugo_op_acumulado") as "refugo_op",
                           LAST("descarte") as "descarte_raw",
                           LAST("producao_turno_acumulada") as "prod_turno",
                           LAST("contagem_saida") as "prod",
                           LAST("estado_maquina") as "state",
                           LAST("formato_gramas") as "fmt",
                           LAST("formato") as "fmt_alt",
                           LAST("sku_codigo") as "sku_codigo",
                           LAST("sku_codigo_field") as "sku_codigo_field",
                           LAST("descricao") as "descricao",
                           LAST("produto") as "produto"
                    FROM "production"
                    WHERE "equipment" = '{eq.codigo}'
                    AND time >= '{query_inicio.isoformat()}' AND time <= '{dt_fim.isoformat()}'
                    GROUP BY time(1m)
                """
                points = query_influxdb(query_series)
                last_waste_counter = None
                last_prod_counter = None
                last_state_code = None  # carry-forward por equipamento

                for point in points:
                    point_dt = _local_dt(point.get('time'))
                    if not point_dt:
                        continue

                    product_code, product_label = _product_info(point)
                    formato_raw = _first_present(point, 'fmt', 'fmt_alt')
                    formato_code = _format_code(formato_raw)
                    formato_label = _format_label(formato_raw)
                    # Mesma estrategia da _get_v2: nao usar default fixo,
                    # usar carry-forward, marcar Indefinido se nunca houver.
                    raw_state = point.get('state')
                    state_int = None
                    if raw_state not in (None, ''):
                        try:
                            state_int = int(float(raw_state))
                        except (TypeError, ValueError):
                            state_int = None
                    if state_int is None:
                        state_int = last_state_code
                    else:
                        last_state_code = state_int
                    equipamento_state_code = (
                        ESTADO_INDEFINIDO_CODE if state_int is None else str(state_int)
                    )
                    equipamento_state_label = _state_label(equipamento_state_code)

                    waste_counter = _waste_counter(point)
                    prod_counter = _production_counter(point)
                    diff_refugo = _counter_delta(waste_counter, last_waste_counter)
                    diff_prod = _counter_delta(prod_counter, last_prod_counter)
                    last_waste_counter = _safe_float(waste_counter, last_waste_counter)
                    last_prod_counter = _safe_float(prod_counter, last_prod_counter)

                    if point_dt < dt_inicio or not _matches_shift(point_dt, shift_intervals):
                        continue

                    bucket = _time_bucket_minute(point_dt)
                    line_bucket_key = (linha.id, bucket)
                    line_states_by_bucket.setdefault(line_bucket_key, {})[eq.codigo] = equipamento_state_code
                    line_state_timeline.setdefault(linha.id, {})[bucket] = line_states_by_bucket[line_bucket_key]

                    produtos_disponiveis[product_code] = product_label
                    formatos_disponiveis[formato_code] = formato_label
                    estados_equipamento_disponiveis[equipamento_state_code] = equipamento_state_label

                    if not (
                        _matches_filter(product_code, produto_filter)
                        and _matches_filter(formato_code, formato_filter)
                        and _matches_filter(equipamento_state_code, estado_equipamento_filter)
                    ):
                        continue

                    formato = _safe_float(formato_raw, 500.0) or 500.0
                    base = {
                        'linha_id': linha.id,
                        'linha': linha.nome,
                        'linha_codigo': linha.codigo,
                        'equipamento': eq.nome,
                        'equipamento_codigo': eq.codigo,
                        'bucket': bucket,
                        'produto_codigo': product_code,
                        'produto': product_label,
                        'formato_codigo': formato_code,
                        'formato': formato_label,
                        'estado_equipamento_code': equipamento_state_code,
                        'estado_equipamento_label': equipamento_state_label,
                        'formato_gramas': formato,
                    }
                    if diff_prod > 0:
                        production_events.append({
                            **base,
                            'unidades': diff_prod,
                            'tons': (diff_prod * formato) / 1000000.0,
                        })
                    if diff_refugo > 0:
                        events.append({
                            **base,
                            'unidades': diff_refugo,
                            'tons': (diff_refugo * formato) / 1000000.0,
                        })

        estados_linha_disponiveis = {}
        line_transitions = []
        for linha in linhas:
            previous_code = None
            previous_label = None
            for bucket, states in sorted(line_state_timeline.get(linha.id, {}).items()):
                code, label = _line_status_from_states(states.values())
                estados_linha_disponiveis[code] = label
                if previous_code is not None and previous_code != code:
                    line_transitions.append({
                        'linha': linha.nome,
                        'linha_codigo': linha.codigo,
                        'hora': bucket,
                        'de': previous_label,
                        'para': label,
                    })
                previous_code = code
                previous_label = label

        def with_line_state(item):
            code, label = _line_status_from_states(
                line_states_by_bucket.get((item['linha_id'], item['bucket']), {}).values()
            )
            estados_linha_disponiveis[code] = label
            return {**item, 'estado_linha_code': code, 'estado_linha_label': label}

        events = [with_line_state(event) for event in events]
        production_events = [with_line_state(event) for event in production_events]
        if estado_linha_filter:
            events = [event for event in events if _matches_filter(event['estado_linha_code'], estado_linha_filter)]
            production_events = [
                event for event in production_events
                if _matches_filter(event['estado_linha_code'], estado_linha_filter)
            ]

        line_totals = {}
        total_descarte_tons = 0.0
        total_unidades_ruins = 0.0
        for event in events:
            bucket = line_totals.setdefault(event['linha_codigo'], {
                'linha': event['linha'],
                'codigo': event['linha_codigo'],
                'descarte_tons': 0.0,
                'producao_tons': 0.0,
                'unidades_ruins': 0.0,
            })
            bucket['descarte_tons'] += event['tons']
            bucket['unidades_ruins'] += event['unidades']
            total_descarte_tons += event['tons']
            total_unidades_ruins += event['unidades']

        total_producao_tons = 0.0
        for event in production_events:
            bucket = line_totals.setdefault(event['linha_codigo'], {
                'linha': event['linha'],
                'codigo': event['linha_codigo'],
                'descarte_tons': 0.0,
                'producao_tons': 0.0,
                'unidades_ruins': 0.0,
            })
            bucket['producao_tons'] += event['tons']
            total_producao_tons += event['tons']

        dados_por_linha = []
        for linha in linhas:
            bucket = line_totals.get(linha.codigo, {
                'linha': linha.nome,
                'codigo': linha.codigo,
                'descarte_tons': 0.0,
                'producao_tons': 0.0,
                'unidades_ruins': 0.0,
            })
            percentual = (bucket['descarte_tons'] / bucket['producao_tons'] * 100) if bucket['producao_tons'] > 0 else 0
            dados_por_linha.append({
                'linha': bucket['linha'],
                'codigo': bucket['codigo'],
                'descarte_tons': round(bucket['descarte_tons'], 4),
                'descarte_percentual': round(percentual, 2),
                'producao_tons': round(bucket['producao_tons'], 3),
                'unidades_ruins': int(bucket['unidades_ruins']),
            })

        def grouped(items, key_fn, base_fn):
            result = {}
            for item in items:
                key = key_fn(item)
                bucket = result.setdefault(key, {**base_fn(item), 'tons': 0.0, 'unidades': 0.0})
                bucket['tons'] += item['tons']
                bucket['unidades'] += item['unidades']
            return list(result.values())

        top_equipamentos = grouped(
            events,
            lambda item: (item['linha_codigo'], item['equipamento_codigo']),
            lambda item: {'equipamento': item['equipamento'], 'linha': item['linha']},
        )
        for item in top_equipamentos:
            item['percentual'] = round((item['tons'] / total_descarte_tons * 100) if total_descarte_tons > 0 else 0, 1)
            item['tons'] = round(item['tons'], 4)
            item['unidades'] = int(item['unidades'])
        top_equipamentos = sorted(top_equipamentos, key=lambda x: x['tons'], reverse=True)[:10]

        descarte_por_estado_equipamento = grouped(
            events,
            lambda item: item['estado_equipamento_code'],
            lambda item: {
                'estado_code': _safe_int(item['estado_equipamento_code']),
                'estado_label': item['estado_equipamento_label'],
            },
        )
        descarte_por_estado_linha = grouped(
            events,
            lambda item: item['estado_linha_code'],
            lambda item: {
                'estado_code': _safe_int(item['estado_linha_code']),
                'estado_label': item['estado_linha_label'],
            },
        )

        for dataset in (descarte_por_estado_equipamento, descarte_por_estado_linha):
            total = sum(item['tons'] for item in dataset)
            for item in dataset:
                item['percentual'] = round((item['tons'] / total * 100) if total > 0 else 0, 1)
                item['tons'] = round(item['tons'], 4)
                item['unidades'] = int(item['unidades'])
            dataset.sort(key=lambda x: x['tons'], reverse=True)

        descarte_por_produto = grouped(
            events,
            lambda item: item['produto_codigo'],
            lambda item: {'codigo': item['produto_codigo'], 'produto': item['produto']},
        )
        descarte_por_formato = grouped(
            events,
            lambda item: item['formato_codigo'],
            lambda item: {'codigo': item['formato_codigo'], 'formato': item['formato']},
        )
        for dataset in (descarte_por_produto, descarte_por_formato):
            for item in dataset:
                item['percentual'] = round((item['tons'] / total_descarte_tons * 100) if total_descarte_tons > 0 else 0, 1)
                item['tons'] = round(item['tons'], 4)
                item['unidades'] = int(item['unidades'])
            dataset.sort(key=lambda x: x['tons'], reverse=True)

        matriz_estado_equipamento_produto = grouped(
            events,
            lambda item: (item['estado_equipamento_code'], item['produto_codigo']),
            lambda item: {
                'estado_code': _safe_int(item['estado_equipamento_code']),
                'estado_label': item['estado_equipamento_label'],
                'produto_codigo': item['produto_codigo'],
                'produto': item['produto'],
            },
        )
        matriz_estado_linha_produto = grouped(
            events,
            lambda item: (item['estado_linha_code'], item['produto_codigo']),
            lambda item: {
                'estado_code': _safe_int(item['estado_linha_code']),
                'estado_label': item['estado_linha_label'],
                'produto_codigo': item['produto_codigo'],
                'produto': item['produto'],
            },
        )
        for dataset in (matriz_estado_equipamento_produto, matriz_estado_linha_produto):
            for item in dataset:
                item['percentual'] = round((item['tons'] / total_descarte_tons * 100) if total_descarte_tons > 0 else 0, 1)
                item['tons'] = round(item['tons'], 4)
                item['unidades'] = int(item['unidades'])
            dataset.sort(key=lambda x: x['tons'], reverse=True)

        evolucao_raw = {}
        for event in events:
            hour = event['bucket'][:13]
            bucket = evolucao_raw.setdefault(hour, {'descarte': 0.0, 'producao': 0.0})
            bucket['descarte'] += event['unidades']
        for event in production_events:
            hour = event['bucket'][:13]
            bucket = evolucao_raw.setdefault(hour, {'descarte': 0.0, 'producao': 0.0})
            bucket['producao'] += event['unidades']
        evolucao_temporal = [
            {'hora': hour, 'descarte': round(values['descarte'], 3), 'producao': round(values['producao'], 3)}
            for hour, values in sorted(evolucao_raw.items())
        ][:24]

        linha_maior_descarte = max(dados_por_linha, key=lambda x: x['descarte_tons']) if dados_por_linha else None
        percentual_consolidado = (total_descarte_tons / total_producao_tons * 100) if total_producao_tons > 0 else 0
        estado_linha_critico = descarte_por_estado_linha[0] if descarte_por_estado_linha else None
        estado_equipamento_critico = descarte_por_estado_equipamento[0] if descarte_por_estado_equipamento else None
        produto_critico = descarte_por_produto[0] if descarte_por_produto else None
        formato_critico = descarte_por_formato[0] if descarte_por_formato else None
        if total_descarte_tons > 0:
            partes = []
            if estado_linha_critico:
                partes.append(f"{estado_linha_critico['percentual']}% com linha em {estado_linha_critico['estado_label']}")
            if estado_equipamento_critico:
                partes.append(f"equipamento em {estado_equipamento_critico['estado_label']}")
            if produto_critico:
                partes.append(f"produto {produto_critico['produto']}")
            insight_msg = "Maior concentração observada: " + ", ".join(partes) + "."
        else:
            insight_msg = "Não houve descarte real contabilizado para os filtros selecionados."

        return Response({
            'periodo': periodo,
            'periodo_label': periodo_label,
            'data_inicio': dt_inicio.isoformat(),
            'data_fim': dt_fim.isoformat(),
            'linhas_selecionadas': [l.nome for l in linhas],
            'filtros_aplicados': {
                'produto': sorted(produto_filter) if produto_filter else ['todos'],
                'formato': sorted(formato_filter) if formato_filter else ['todos'],
                'estado_equipamento': sorted(estado_equipamento_filter) if estado_equipamento_filter else ['todos'],
                'estado_linha': sorted(estado_linha_filter) if estado_linha_filter else ['todos'],
                'turno': [turno_param or 'todos'],
            },
            'filtros_disponiveis': {
                'produtos': [
                    {'codigo': code, 'label': label}
                    for code, label in sorted(produtos_disponiveis.items(), key=lambda item: item[1])
                ],
                'formatos': [
                    {'codigo': code, 'label': label}
                    for code, label in sorted(
                        formatos_disponiveis.items(),
                        key=lambda item: _safe_float(item[0], 999999.0)
                    )
                ],
                'estados': [
                    {'codigo': code, 'label': label}
                    for code, label in sorted(
                        estados_equipamento_disponiveis.items(),
                        key=lambda item: _safe_int(item[0], 999999)
                    )
                ],
                'estados_equipamento': [
                    {'codigo': code, 'label': label}
                    for code, label in sorted(
                        estados_equipamento_disponiveis.items(),
                        key=lambda item: _safe_int(item[0], 999999)
                    )
                ],
                'estados_linha': [
                    {'codigo': code, 'label': label}
                    for code, label in sorted(
                        estados_linha_disponiveis.items(),
                        key=lambda item: _safe_int(item[0], 999999)
                    )
                ],
                'turnos': [
                    {
                        'codigo': str(turno.codigo),
                        'label': f'{turno.nome} ({turno.hora_inicio.strftime("%H:%M")}-{turno.hora_fim.strftime("%H:%M")})',
                    }
                    for turno in turnos
                ],
            },
            'consolidado': {
                'descarte_tons': round(total_descarte_tons, 4),
                'descarte_percentual': round(percentual_consolidado, 2),
                'producao_tons': round(total_producao_tons, 3),
                'total_unidades': int(total_unidades_ruins),
            },
            'por_linha': dados_por_linha,
            'top_equipamentos': top_equipamentos,
            'linha_maior_descarte': linha_maior_descarte,
            'evolucao_temporal': evolucao_temporal,
            'descarte_por_estado': descarte_por_estado_equipamento,
            'descarte_por_estado_equipamento': descarte_por_estado_equipamento,
            'descarte_por_estado_linha': descarte_por_estado_linha,
            'descarte_por_produto': descarte_por_produto[:12],
            'descarte_por_formato': descarte_por_formato[:12],
            'matriz_estado_produto': matriz_estado_equipamento_produto[:20],
            'matriz_estado_equipamento_produto': matriz_estado_equipamento_produto[:20],
            'matriz_estado_linha_produto': matriz_estado_linha_produto[:20],
            'mudancas_estado_linha': line_transitions[:50],
            'verificacao_estado_linha': {
                'total_mudancas': len(line_transitions),
                'criterio': 'Estado da linha = estado do primeiro equipamento ordenado da linha no minuto analisado',
            },
            'insight': {
                'titulo': 'Leitura do período',
                'mensagem': insight_msg,
                'estado_critico': estado_equipamento_critico,
                'estado_equipamento_critico': estado_equipamento_critico,
                'estado_linha_critico': estado_linha_critico,
                'produto_critico': produto_critico,
                'formato_critico': formato_critico,
            },
        })

    def get(self, request):
        try:
            return self._get_v3(request)
        except Exception as e:
            logger.exception("Erro no WasteDashboardSummaryView")
            return Response({'error': str(e)}, status=500)

    def get_legacy(self, request):
        try:
            # Parâmetros
            linhas_param = request.query_params.get('linhas', 'todas')
            periodo = request.query_params.get('periodo', 'TURNO')
            data_inicio = request.query_params.get('data_inicio')
            data_fim = request.query_params.get('data_fim')

            # Obter range de datas
            dt_inicio, dt_fim, periodo_label = get_periodo_range(periodo, data_inicio, data_fim)

            # Obter lista de linhas
            from .models import LinhaProducao, Equipamento

            if linhas_param == 'todas':
                linhas = LinhaProducao.objects.all()
            else:
                codigos = [c.strip() for c in linhas_param.split(',')]
                linhas = LinhaProducao.objects.filter(codigo__in=codigos)

            if not linhas.exists():
                return Response({'error': 'Nenhuma linha encontrada'}, status=404)

            # Coletar dados por linha
            dados_por_linha = []
            total_descarte_tons = 0
            total_producao_tons = 0
            total_unidades_ruins = 0
            top_equipamentos = []
            evolucao_temporal = {}

            for linha in linhas:
                equipamentos = Equipamento.objects.filter(linha=linha)

                linha_descarte_tons = 0
                linha_producao_tons = 0
                linha_unidades = 0

                for eq in equipamentos:
                    # Query para somar diferenças não-negativas (incrementos reais)
                    # Isso captura o total produzido/descartado mesmo se o contador resetar (ex: troca de OP)
                    # Agrupamos por 1m para ter resolução fina dos incrementos

                    query_refugo = f"""
                        SELECT SUM("diff") FROM (
                            SELECT NON_NEGATIVE_DIFFERENCE(LAST("refugo_op_acumulado")) as "diff"
                            FROM "production"
                            WHERE "equipment" = '{eq.codigo}'
                            AND time >= '{dt_inicio.isoformat()}' AND time <= '{dt_fim.isoformat()}'
                            GROUP BY time(1m)
                        )
                    """

                    query_prod = f"""
                        SELECT SUM("diff") FROM (
                            SELECT NON_NEGATIVE_DIFFERENCE(LAST("contagem_saida")) as "diff"
                            FROM "production"
                            WHERE "equipment" = '{eq.codigo}'
                            AND time >= '{dt_inicio.isoformat()}' AND time <= '{dt_fim.isoformat()}'
                            GROUP BY time(1m)
                        )
                    """

                    # Formato: pegar o último (simplificação aceitável)
                    query_fmt = f"""
                        SELECT LAST("formato_gramas") as fmt
                        FROM "production"
                        WHERE "equipment" = '{eq.codigo}'
                        AND time >= '{dt_inicio.isoformat()}' AND time <= '{dt_fim.isoformat()}'
                    """

                    refugo_data = query_influxdb(query_refugo)
                    prod_data = query_influxdb(query_prod)
                    fmt_data = query_influxdb(query_fmt)

                    refugo_delta = 0
                    prod_delta = 0
                    formato = 500.0

                    if refugo_data and 'sum' in refugo_data[0]:
                        refugo_delta = refugo_data[0]['sum'] or 0

                    if prod_data and 'sum' in prod_data[0]:
                        prod_delta = prod_data[0]['sum'] or 0

                    if fmt_data and 'fmt' in fmt_data[0]:
                        formato = fmt_data[0]['fmt'] or 500.0

                    eq_descarte_tons = (refugo_delta * formato) / 1000000
                    eq_prod_tons = (prod_delta * formato) / 1000000

                    linha_descarte_tons += eq_descarte_tons
                    linha_producao_tons += eq_prod_tons
                    linha_unidades += refugo_delta

                    # Top equipamentos
                    if refugo_delta > 0:
                        top_equipamentos.append({
                            'equipamento': eq.nome,
                            'linha': linha.nome,
                            'unidades': int(refugo_delta),
                            'tons': round(eq_descarte_tons, 4),
                            'percentual': 0  # Calculado depois
                        })

                # Calcular percentual da linha
                linha_percentual = (linha_descarte_tons / linha_producao_tons * 100) if linha_producao_tons > 0 else 0

                dados_por_linha.append({
                    'linha': linha.nome,
                    'codigo': linha.codigo,
                    'descarte_tons': round(linha_descarte_tons, 4),
                    'descarte_percentual': round(linha_percentual, 2),
                    'producao_tons': round(linha_producao_tons, 3),
                    'unidades_ruins': int(linha_unidades)
                })

                total_descarte_tons += linha_descarte_tons
                total_producao_tons += linha_producao_tons
                total_unidades_ruins += linha_unidades

            # Calcular percentuais dos top equipamentos
            for eq in top_equipamentos:
                eq['percentual'] = round((eq['tons'] / total_descarte_tons * 100) if total_descarte_tons > 0 else 0, 1)

            # Ordenar top equipamentos
            top_equipamentos = sorted(top_equipamentos, key=lambda x: x['tons'], reverse=True)[:10]

            # Linha com maior descarte
            linha_maior_descarte = max(dados_por_linha, key=lambda x: x['descarte_tons']) if dados_por_linha else None

            # Percentual consolidado
            percentual_consolidado = (total_descarte_tons / total_producao_tons * 100) if total_producao_tons > 0 else 0

            # Query para evolução temporal (agrupado por hora)
            # Usando NON_NEGATIVE_DIFFERENCE para somar incrementos por hora
            eq_codes = [eq.codigo for linha in linhas for eq in Equipamento.objects.filter(linha=linha)]
            if eq_codes:
                eq_filter = " OR ".join([f"\"equipment\" = '{c}'" for c in eq_codes])

                # Query complexa: Soma das diferenças de TODOS equipamentos, agrupados por 1h
                query_temporal = f"""
                    SELECT SUM("diff_refugo") as refugo, SUM("diff_prod") as prod FROM (
                        SELECT NON_NEGATIVE_DIFFERENCE(LAST("refugo_op_acumulado")) as "diff_refugo",
                               NON_NEGATIVE_DIFFERENCE(LAST("contagem_saida")) as "diff_prod"
                        FROM "production"
                        WHERE ({eq_filter})
                        AND time >= '{dt_inicio.isoformat()}' AND time <= '{dt_fim.isoformat()}'
                        GROUP BY time(1h), "equipment"
                    ) GROUP BY time(1h)
                """

                temporal_data = query_influxdb(query_temporal)
                evolucao_temporal = [
                    {
                        'hora': p.get('time', ''),
                        'descarte': p.get('refugo') or 0,
                        'producao': p.get('prod') or 0
                    }
                    for p in temporal_data if p.get('time')
                ]

            # === ANÁLISE DE DESCARTE POR ESTADO ===
            # Estratégia: Buscar delta refugo e estado minuto a minuto para cada equipamento
            # e correlacionar: se houve descarte naquele minuto, atribuir ao estado daquele minuto.

            descarte_por_estado_raw = {}  # {0: 15.5, 1: 200.0, ...}

            for linha in linhas:
                equipamentos = Equipamento.objects.filter(linha=linha)
                for eq in equipamentos:
                    # Busca detalhada minuto a minuto
                    query_state_waste = f"""
                        SELECT NON_NEGATIVE_DIFFERENCE(LAST("refugo_op_acumulado")) as "diff_refugo",
                               LAST("estado_maquina") as "state",
                               LAST("formato_gramas") as "fmt"
                        FROM "production"
                        WHERE "equipment" = '{eq.codigo}'
                        AND time >= '{dt_inicio.isoformat()}' AND time <= '{dt_fim.isoformat()}'
                        GROUP BY time(1m)
                    """
                    state_data = query_influxdb(query_state_waste)

                    for point in state_data:
                        diff = point.get('diff_refugo', 0)
                        if diff and diff > 0:
                            state = int(point.get('state') or 1) # Default 1 (Produzindo) se null
                            fmt = float(point.get('fmt') or 500.0)

                            tons = (diff * fmt) / 1000000.0

                            descarte_por_estado_raw[state] = descarte_por_estado_raw.get(state, 0) + tons

            # Mapeamento de Estados (Conforme dataValidation.ts)
            ESTADO_MAP = {
                0: 'Parado',
                1: 'Produzindo',
                2: 'Aguardando',
                3: 'Manutenção',
                4: 'Offline'
            }

            descarte_por_estado = []
            for state_code, tons in descarte_por_estado_raw.items():
                label = ESTADO_MAP.get(state_code, f'Estado {state_code}')
                descarte_por_estado.append({
                    'estado_code': state_code,
                    'estado_label': label,
                    'tons': round(tons, 4),
                    'percentual': 0 # Calculado abaixo
                })

            # Calcular percentuais
            total_waste_state = sum(d['tons'] for d in descarte_por_estado)
            for d in descarte_por_estado:
                d['percentual'] = round((d['tons'] / total_waste_state * 100) if total_waste_state > 0 else 0, 1)

            # Ordenar por maior descarte
            descarte_por_estado = sorted(descarte_por_estado, key=lambda x: x['tons'], reverse=True)

            response_data = {
                'periodo': periodo,
                'periodo_label': periodo_label,
                'data_inicio': dt_inicio.isoformat(),
                'data_fim': dt_fim.isoformat(),
                'linhas_selecionadas': [l.nome for l in linhas],
                'consolidado': {
                    'descarte_tons': round(total_descarte_tons, 4),
                    'descarte_percentual': round(percentual_consolidado, 2),
                    'producao_tons': round(total_producao_tons, 3),
                    'total_unidades': int(total_unidades_ruins)
                },
                'por_linha': dados_por_linha,
                'top_equipamentos': top_equipamentos,
                'linha_maior_descarte': linha_maior_descarte,
                'evolucao_temporal': evolucao_temporal[:24],
                'descarte_por_estado': descarte_por_estado  # Novo campo
            }

            return Response(response_data)

        except Exception as e:
            logger.exception("Erro no WasteDashboardSummaryView")
            return Response({'error': str(e)}, status=500)


class WasteLinhasDisponiveisView(APIView):
    """
    GET /api/descartes/linhas/
    Retorna lista de linhas disponíveis para seleção.
    """

    def get(self, request):
        from .models import LinhaProducao
        linhas = LinhaProducao.objects.all().values('id', 'nome', 'codigo')
        return Response(list(linhas))

