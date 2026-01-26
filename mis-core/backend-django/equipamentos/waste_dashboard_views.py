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

logger = logging.getLogger(__name__)

# Configurações
FLASK_API_URL = "http://mis-core-flask:5000/api"
INFLUXDB_HOST = "mis-core-influxdb"
INFLUXDB_PORT = 8086
INFLUXDB_DATABASE = "industrial_db"
INFLUXDB_USER = "admin"
INFLUXDB_PASSWORD = "admin123"


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
    
    def get(self, request):
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
                            state = int(point.get('state', 1)) # Default 1 (Produzindo) se null
                            fmt = point.get('fmt', 500.0)
                            
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

