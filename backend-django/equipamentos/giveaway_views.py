from rest_framework.views import APIView
from rest_framework.response import Response
from .models import LinhaProducao, Equipamento
from .influx_helpers import equipment_where_clause
from influxdb import InfluxDBClient
from django.conf import settings
from datetime import datetime
import pytz
import logging

logger = logging.getLogger(__name__)

def query_influxdb(query):
    client = InfluxDBClient(
        host=settings.INFLUXDB_HOST,
        port=settings.INFLUXDB_PORT,
        username=settings.INFLUXDB_USER,
        password=settings.INFLUXDB_PASSWORD,
        database=settings.INFLUXDB_DATABASE
    )
    return list(client.query(query).get_points())

class GiveAwaySummaryView(APIView):
    """
    API para análise de Give Away (Controle de Peso).
    Lógica: (Média(Peso Real) - Peso Nominal) * Produção
    """
    
    def get(self, request):
        try:
            # Filtros de Data
            periodo = request.query_params.get('periodo', 'TURNO')
            dt_inicio_param = request.query_params.get('data_inicio')
            dt_fim_param = request.query_params.get('data_fim')
            
            # ... (Lógica de datas similar ao WasteDashboard) ...
            # Simplificação: Usar data fixa ou parametrizada para MVP
            # Recomendado extrair lógica de data para um helper utils
            
            # TODO: Refatorar lógica de data do waste_dashboard_views para utils/date_parsers.py
            # Por enquanto, replicando simplificadamente para foco na lógica de Influx
            
            # Lógica de Datas Ajustada para InfluxQL (UTC Z)
            now = datetime.now(pytz.timezone('America/Sao_Paulo'))
            
            if dt_inicio_param and dt_fim_param:
                # O frontend envia UTC (Z), então parseamos direto
                dt_inicio = datetime.fromisoformat(dt_inicio_param.replace('Z', '+00:00'))
                dt_fim = datetime.fromisoformat(dt_fim_param.replace('Z', '+00:00'))
            else:
                # Default: Últimas 24h
                dt_inicio = now.replace(hour=0, minute=0, second=0, microsecond=0)
                dt_fim = now

            # Converter para UTC e String Influx Friendly
            def format_influx_time(dt):
                return dt.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')

            time_start_str = format_influx_time(dt_inicio)
            time_end_str = format_influx_time(dt_fim)
            
            linhas_param = request.query_params.get('linhas', 'todas')
            if linhas_param == 'todas' or not linhas_param:
                linhas = LinhaProducao.objects.filter(ativa=True)
            else:
                codigos = linhas_param.split(',')
                linhas = LinhaProducao.objects.filter(codigo__in=codigos, ativa=True)

            results_by_line = []
            
            for linha in linhas:
                # 1. Identificar o "Checkweigher" ou Equipamento de Referência
                # Lógica Ajustada (User Request): Priorizar ENCHEDORA, depois BALANCA, depois Ordem 1
                from django.db.models import Q
                equipamento_peso = linha.equipamentos.filter(tipo='ENCHEDORA').first()
                
                if not equipamento_peso:
                    equipamento_peso = linha.equipamentos.filter(tipo='BALANCA').first()
                
                if not equipamento_peso:
                    equipamento_peso = linha.equipamentos.filter(ordem_na_linha=1).first()
                
                if not equipamento_peso:
                    logger.warning(f"Linha {linha.codigo}: Nenhum equipamento apto para Give Away encontrado.")
                    continue
                
                logger.info(f"GiveAway Debug - Linha: {linha.nome} | Equipamento selecionado: {equipamento_peso.nome} ({equipamento_peso.codigo})")
                    
                # 2. Query Influx (Agregação Estatística)
                # Usa 'peso_real' (tag padrao a partir do PR 9) com fallback
                # para 'ultimo_peso' (nome historico). 'formato_gramas' do
                # Influx tem prioridade; fallback para linha.formato_alvo_padrao.
                query = f"""
                    SELECT
                        MEAN("peso_real") as "peso_medio_real",
                        MEAN("ultimo_peso") as "peso_medio_legacy",
                        LAST("formato_gramas") as "peso_alvo",
                        LAST("formato") as "peso_alvo_alt",
                        NON_NEGATIVE_DIFFERENCE(LAST("contagem_saida")) as "producao"
                    FROM "production"
                    WHERE {equipment_where_clause(equipamento_peso)}
                    AND time >= '{time_start_str}' AND time <= '{time_end_str}'
                    GROUP BY time(1h)
                """

                try:
                    data_points = query_influxdb(query)
                    logger.info(f"GiveAway Debug - Query retornou {len(data_points)} pontos. Query: {query}")
                except Exception as e:
                    logger.error(f"GiveAway Debug - Erro Influx: {str(e)}")
                    data_points = []

                # Fallback de peso alvo: linha.formato_alvo_padrao
                fallback_peso_alvo = (
                    float(linha.formato_alvo_padrao) if linha.formato_alvo_padrao else None
                )

                total_giveaway_kg = 0.0
                total_producao_kg = 0.0
                total_unidades = 0

                for point in data_points:
                    peso_medio = point.get('peso_medio_real')
                    if peso_medio is None:
                        peso_medio = point.get('peso_medio_legacy')
                    peso_alvo = point.get('peso_alvo')
                    if peso_alvo is None:
                        peso_alvo = point.get('peso_alvo_alt')
                    if peso_alvo is None:
                        peso_alvo = fallback_peso_alvo
                    producao_unidades = point.get('producao') or 0  # Tratar None como 0

                    if peso_medio and peso_alvo and producao_unidades > 0:
                        # Diferença unitária (g)
                        diff_g = peso_medio - peso_alvo
                        
                        # Se diff_g < 0, estamos dando menos produto (Give Away negativo? Ou só consideramos excesso?)
                        # Geralmente Give Away é só excesso. Se for falta, é problema de qualidade/legal.
                        # Para "Give Away" financeiro, costuma-se somar tudo (média desviada).
                        # Vamos assumir o cálculo puro: Real - Teórico.
                        
                        # Total Give Away neste intervalo (kg)
                        giveaway_intervalo_kg = (diff_g * producao_unidades) / 1000.0
                        
                        # Total Produzido Teórico vs Real?
                        # Vamos acumular o Give Away
                        total_giveaway_kg += giveaway_intervalo_kg
                        total_unidades += producao_unidades
                        
                        # Produção Nominal (kg) para referência
                        total_producao_kg += (peso_alvo * producao_unidades) / 1000.0

                # Resultados consolidados da linha
                percentual = (total_giveaway_kg / total_producao_kg * 100) if total_producao_kg > 0 else 0.0
                
                results_by_line.append({
                    'linha': linha.nome,
                    'codigo': linha.codigo,
                    'equipamento_leitura': equipamento_peso.nome,
                    'giveaway_kg': round(total_giveaway_kg, 3),
                    'giveaway_percent': round(percentual, 2),
                    'producao_unidades': int(total_unidades),
                    'producao_nominal_kg': round(total_producao_kg, 3)
                })

            # Consolidação Geral
            total_geral_kg = sum(r['giveaway_kg'] for r in results_by_line)
            total_prod_kg = sum(r['producao_nominal_kg'] for r in results_by_line)
            avg_percent = (total_geral_kg / total_prod_kg * 100) if total_prod_kg > 0 else 0.0

            response_data = {
                'consolidado': {
                    'giveaway_kg': total_geral_kg,
                    'giveaway_percent': avg_percent,
                    'producao_ref_kg': total_prod_kg
                },
                'por_linha': sorted(results_by_line, key=lambda x: x['giveaway_kg'], reverse=True)
            }
            
            return Response(response_data)
        
        except Exception as e:
            logger.exception("Erro ao calcular Give Away")
            return Response({'error': str(e)}, status=500)
