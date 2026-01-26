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
                    # Query para obter último e primeiro valor do período (para calcular delta)
                    query_first = f"""
                        SELECT FIRST("refugo_op_acumulado") as refugo, FIRST("contagem_saida") as prod, 
                               FIRST("formato_gramas") as fmt
                        FROM "production" 
                        WHERE "equipment" = '{eq.codigo}' 
                        AND time >= '{dt_inicio.isoformat()}' AND time <= '{dt_fim.isoformat()}'
                    """
                    query_last = f"""
                        SELECT LAST("refugo_op_acumulado") as refugo, LAST("contagem_saida") as prod,
                               LAST("formato_gramas") as fmt
                        FROM "production" 
                        WHERE "equipment" = '{eq.codigo}' 
                        AND time >= '{dt_inicio.isoformat()}' AND time <= '{dt_fim.isoformat()}'
                    """
                    
                    first_data = query_influxdb(query_first)
                    last_data = query_influxdb(query_last)
                    
                    if first_data and last_data:
                        first = first_data[0]
                        last = last_data[0]
                        
                        refugo_delta = (last.get('refugo') or 0) - (first.get('refugo') or 0)
                        prod_delta = (last.get('prod') or 0) - (first.get('prod') or 0)
                        formato = last.get('fmt') or 500  # gramas
                        
                        # Se delta negativo (virada de turno), usar valor absoluto do último
                        if refugo_delta < 0:
                            refugo_delta = last.get('refugo') or 0
                        if prod_delta < 0:
                            prod_delta = last.get('prod') or 0
                        
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
            # Simplificado: média por hora para todas as linhas
            eq_codes = [eq.codigo for linha in linhas for eq in Equipamento.objects.filter(linha=linha)]
            if eq_codes:
                eq_filter = " OR ".join([f"\"equipment\" = '{c}'" for c in eq_codes])
                query_temporal = f"""
                    SELECT SUM("refugo_op_acumulado") as refugo, SUM("contagem_saida") as prod
                    FROM "production"
                    WHERE ({eq_filter})
                    AND time >= '{dt_inicio.isoformat()}' AND time <= '{dt_fim.isoformat()}'
                    GROUP BY time(1h)
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
                'evolucao_temporal': evolucao_temporal[:24]  # Limitar a 24 pontos
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

