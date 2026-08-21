"""
Loss Analysis Views
===================
Endpoints para análise de perdas e planejado vs real
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
import datetime
import heapq
import requests
from decimal import Decimal

from equipamentos.models import (
    LinhaProducao, Equipamento, EventoEstadoEquipamento,
    TipoFalha, MetricaProducao, EstadoEquipamento, HistoricoSKU
)
from django.db import models
from django.db.models import Sum, Avg
from equipamentos.influx_helpers import get_influx_client, get_realtime_metrics
from equipamentos.turno_helpers import obter_turno_atual, calcular_inicio_turno, calcular_fim_turno


def _last_state_seen_by_equipment(client, line_code):
    """Return the last measured state timestamp for each equipment in a line."""
    safe_line = str(line_code).replace('\\', '\\\\').replace("'", "\\'")
    query = (
        'SELECT last("estado_maquina") AS state FROM "production" '
        f'WHERE "line" = \'{safe_line}\' GROUP BY "equipment"'
    )
    result = client.query(query)
    output = {}
    for series in (result.raw or {}).get('series', []):
        equipment = (series.get('tags') or {}).get('equipment')
        values = series.get('values') or []
        if not equipment or not values or not values[0]:
            continue
        raw_time = values[0][0]
        try:
            output[equipment] = timezone.datetime.fromisoformat(
                str(raw_time).replace('Z', '+00:00')
            )
        except (TypeError, ValueError):
            continue
    return output


def _resolved_event_segments(events, window_start, window_end, last_seen=None):
    """Resolve overlapping/duplicated state events with latest-start-wins.

    Open OPC events are never extended indefinitely after telemetry stops.
    They are capped two minutes after the last measured state. The original
    database rows remain untouched; this is a read-time consistency layer.
    """
    candidates = []
    freshness_limit = last_seen + timedelta(minutes=2) if last_seen else None
    for event in events:
        start = max(event.inicio, window_start)
        end = min(event.fim or window_end, window_end)
        if event.fim is None and event.origem == 'OPC':
            end = min(end, freshness_limit) if freshness_limit else start
        if end > start:
            candidates.append((start, end, event))

    if not candidates:
        return []

    boundaries = sorted({window_start, window_end} | {
        value for start, end, _ in candidates for value in (start, end)
    })
    starts = sorted(candidates, key=lambda item: (item[0], item[2].id))
    active = []
    cursor = 0
    segments = []
    for left, right in zip(boundaries, boundaries[1:]):
        while cursor < len(starts) and starts[cursor][0] <= left:
            start, end, event = starts[cursor]
            heapq.heappush(active, (-start.timestamp(), -event.id, end, event))
            cursor += 1
        while active and active[0][2] <= left:
            heapq.heappop(active)
        if right <= left or not active:
            continue
        _, _, end, event = active[0]
        segment_end = min(right, end)
        if segment_end > left:
            segments.append((left, segment_end, event))
    return segments


@api_view(['GET'])
def perdas_analise(request, linha_id):
    """
    GET /api/linhas/{linha_id}/perdas-analise/
    
    Retorna análise completa de perdas da linha (Loss Tree).
    
    Query params:
    - periodo: HORA, TURNO, DIA, SEMANA, MES (default: TURNO)
    - data_inicio: data inicial (opcional)
    - data_fim: data final (opcional)
    """
    try:
        # Buscar linha
        try:
            linha = LinhaProducao.objects.get(id=linha_id)
        except LinhaProducao.DoesNotExist:
            return Response({
                'error': f'Linha {linha_id} não encontrada'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Parâmetros
        periodo = request.query_params.get('periodo', 'TURNO').upper()
        if periodo not in {'HORA', 'TURNO', 'DIA', 'SEMANA', 'MES'}:
            return Response({'error': f'Período inválido: {periodo}'}, status=400)

        # Todas as fronteiras operacionais usam o timezone local da fábrica.
        data_inicio, data_fim = _waste_period_window(request, periodo)
        agora = timezone.localtime()
        
        # Mapeamento de Estados para Buckets da Árvore de Perdas
        # Good Production (Produção Boa) é calculado por subtração no final
        PLANNED_LOSS_STATES = [
            EstadoEquipamento.SETUP,
            EstadoEquipamento.TESTE_PROJ
        ]
        UNPLANNED_LOSS_STATES = [
            EstadoEquipamento.FAULT,
            EstadoEquipamento.MANUTENCAO,
            EstadoEquipamento.AGUARD_MNT,
            EstadoEquipamento.FALTA_MAT,
            # Fallback para estados genéricos de parada
            'PARADO', 'STOP' 
        ]
        PERFORMANCE_LOSS_STATES = [ # Minor Stops / Speed Loss
            EstadoEquipamento.WAIT_PREV, # Starved
            EstadoEquipamento.BLOCK_NEXT # Blocked
        ]

        # Buscar equipamentos da linha
        equipamentos = Equipamento.objects.filter(
            linha=linha,
            status='ATIVO'
        ).order_by('ordem_na_linha')
        
        # Buscar meta de vazão (Ton/Hora) para cálculo de perdas financeiras/material
        meta_vazao = float(linha.meta_toneladas_hora) if linha.meta_toneladas_hora else 12.0
        
        # Inicializar Agregadores
        total_tempo_calendario_min = (data_fim - data_inicio).total_seconds() / 60.0
        
        # Estrutura de Retorno (Waterfall Buckets)
        loss_tree = {
            'total_time': total_tempo_calendario_min,
            'planned_loss': 0.0,    # Setup, Testes
            'unplanned_loss': 0.0,  # Quebras, Falta Material
            'performance_loss': 0.0,# Microparadas, Velocidade Reduzida
            'quality_loss': 0.0,    # Refugo
            'good_production': 0.0, # Tempo Produtivo Líquido
            'net_run_time': 0.0     # Tempo Rodando (inclui refugo e perda vel)
        }
        
        # Listas para Ranking
        ranking_equipamentos = [] # {nome, tipo_perda, duracao, toneladas}
        
        # Analisar cada equipamento para compor a visão da linha
        # NOTA: Para a visão da LINHA, idealmente olhamos para o GARGALO ou somamos perdas críticas.
        # Nesta implementação inicial, vamos SOMAR as perdas de disponibilidade de todos (peso bruto)
        # mas ponderar que paradas simultâneas não duplicam o tempo de linha parada logicamente.
        # Simplificação V1: Soma direta das perdas dos equipamentos para gerar o Pareto, 
        # mas para o Waterfall da linha, usamos o equipamento gargalo (ou final) como referência de tempo?
        # Decisão V1: Waterfall baseada na média dos equipamentos ou no gargalo. 
        # Vamos usar a soma das perdas para ranking e o Equipamento Gargalo para o Waterfall.
        
        # Identificar Gargalo (simplificado: equipamento com menor velocidade nominal ou marcado como gargalo)
        # Se não houver marcação, assume a Enchedora ou o do meio.
        gargalo = equipamentos.filter(tipo__icontains='ENCHEDORA').first() or equipamentos.first()

        try:
            influx_client = get_influx_client()
            state_last_seen = _last_state_seen_by_equipment(influx_client, linha.codigo)
        except Exception:
            state_last_seen = {}
        
        # Dicionários auxiliares para o Pareto
        pareto_reasons = {}
        reference_run_minutes = 0.0
        reference_covered_minutes = 0.0
        reference_event_count = 0
        reference_segment_count = 0
        
        for equipamento in equipamentos:
            # Buscar eventos neste intervalo (Concluídos OU em Andamento)
            # Interval overlap, not merely events that started inside the
            # window. An event opened before the shift/day and still active
            # must contribute only the portion that overlaps this period.
            eventos = EventoEstadoEquipamento.objects.filter(
                equipamento=equipamento,
                inicio__lt=data_fim,
            ).filter(models.Q(fim__isnull=True) | models.Q(fim__gt=data_inicio))
            
            eventos = list(eventos)
            segments = _resolved_event_segments(
                eventos,
                data_inicio,
                data_fim,
                state_last_seen.get(equipamento.codigo),
            )
            eq_stats = {
                'planned': 0.0,
                'unplanned': 0.0,
                'performance': 0.0,
                'run': 0.0,
            }

            for inicio_calculo, fim_calculo, evento in segments:
                duracao_min = (fim_calculo - inicio_calculo).total_seconds() / 60.0
                ton_perdidas = Decimal(str((duracao_min / 60.0) * meta_vazao))
                
                estado = evento.estado
                categoria = 'OUTRO'
                
                if estado in PLANNED_LOSS_STATES:
                    eq_stats['planned'] += duracao_min
                    categoria = 'PLANNED'
                    # Se for o gargalo, soma no Waterfall da linha
                    if equipamento.id == gargalo.id:
                        loss_tree['planned_loss'] += duracao_min
                        
                elif estado in UNPLANNED_LOSS_STATES:
                    eq_stats['unplanned'] += duracao_min
                    categoria = 'UNPLANNED'
                    if equipamento.id == gargalo.id:
                        loss_tree['unplanned_loss'] += duracao_min
                        
                elif estado in PERFORMANCE_LOSS_STATES:
                    eq_stats['performance'] += duracao_min
                    categoria = 'PERFORMANCE'
                    if equipamento.id == gargalo.id:
                        loss_tree['performance_loss'] += duracao_min
                elif estado in (
                    EstadoEquipamento.PARTINDO,
                    EstadoEquipamento.PARANDO,
                ):
                    eq_stats['performance'] += duracao_min
                    categoria = 'PERFORMANCE'
                    if equipamento.id == gargalo.id:
                        loss_tree['performance_loss'] += duracao_min
                elif estado == EstadoEquipamento.RUN:
                    eq_stats['run'] += duracao_min
                    categoria = 'RUN'
                
                # Popular Pareto (apenas Unplanned para começar)
                if categoria == 'UNPLANNED':
                    # Tenta usar o TipoFalha específico, senão usa o Estado
                    razao = evento.tipo_falha.nome if evento.tipo_falha else evento.get_estado_display()
                    if razao not in pareto_reasons:
                        pareto_reasons[razao] = 0.0
                    pareto_reasons[razao] += duracao_min

            if equipamento.id == gargalo.id:
                reference_run_minutes = eq_stats['run']
                reference_covered_minutes = sum(eq_stats.values())
                reference_event_count = len(eventos)
                reference_segment_count = len(segments)

            # Adicionar ao Ranking Geral
            total_perda_eq = eq_stats['planned'] + eq_stats['unplanned'] + eq_stats['performance']
            if total_perda_eq > 0:
                ranking_equipamentos.append({
                    'id': equipamento.id,
                    'nome': equipamento.nome,
                    'total_loss_min': round(total_perda_eq, 1),
                    'breakdown': eq_stats
                })

        # Cálculo de Perda de Qualidade (Refugo) e Performance
        # Baseado na produção do Equipamento GARGALO (ou final)
        
        pecas_boas = 0.0
        pecas_refugadas = 0.0
        velocidade_media = linha.velocidade_planejada
        
        # Logic to merge SQL History + Realtime for Current Shift if needed
        # Verifica se o período inclui o momento atual (Hoje, Semana, Mês)
        is_period_including_now = (data_fim >= agora)
        
        pecas_boas_history = 0.0
        pecas_ref_history = 0.0
        
        # 1. Busca Histórico (SQL)
        metricas_gargalo = MetricaProducao.objects.filter(
            equipamento=gargalo,
            periodo=periodo if periodo in ['HORA', 'TURNO', 'DIA'] else 'DIA', 
            data_hora__gte=data_inicio,
            data_hora__lte=data_fim
        )
        
        agregado = metricas_gargalo.aggregate(
            prod=Sum('contagem_saida'),
            refugo=Sum('descarte'), 
            vel=Avg('velocidade_real')
        )
        
        pecas_boas_history = float(agregado['prod'] or 0)
        pecas_ref_history = float(agregado['refugo'] or 0)
        if agregado['vel']: velocidade_media = float(agregado['vel'])

        # 2. Busca Realtime (Influx) se for Turno Atual ou incluir Agora
        pecas_boas_rt = 0.0
        pecas_ref_rt = 0.0
        
        if is_period_including_now and gargalo:
             # Busca formato
             formato = 1000.0
             tag_formato = gargalo.tags_coleta.filter(formato__gt=0).first()
             if tag_formato: formato = float(tag_formato.formato)
             
             # Precisamos saber o inicio do turno atual para pegar o delta
             turno_atual = obter_turno_atual()
             if turno_atual:
                 inicio_t = calcular_inicio_turno(turno_atual)
                 # Se o inicio do turno está dentro do periodo solicitado, somamos o realtime
                 if inicio_t >= data_inicio:
                     rt_metrics = get_realtime_metrics(
                         gargalo.codigo,
                         formato,
                         inicio_t,
                         linha_codigo=linha.codigo,
                     )
                     if rt_metrics:
                         c_atual = float(rt_metrics.get('contagem_atual') or 0.0)
                         c_inicio = float(rt_metrics.get('contagem_inicio_turno') or 0.0)
                         pecas_boas_rt = max(0, c_atual - c_inicio)
                         
                         # Refugo realtime (Fallback Flask se Influx vazio ou para complementar)
                         # Como get_realtime_metrics nao traz refugo, buscamos no Flask
                         try:
                             realtime_url = (
                                 f"http://fastapi:8000/api/v2/operacao/dados/{gargalo.codigo}"
                                 f"?linha={linha.codigo}"
                             )
                             try:
                                 resp = requests.get(realtime_url, timeout=1)
                             except Exception:
                                 resp = None
                             if resp is None or resp.status_code != 200:
                                 flask_url = f"http://mis-core-flask:5000/api/operacao/dados/{gargalo.codigo}"
                                 resp = requests.get(flask_url, timeout=1)
                             if resp.status_code == 200:
                                 d_flask = resp.json()
                                 pecas_ref_rt = float(
                                     d_flask.get('pecas_ruins_turno')
                                     or d_flask.get('descarte_turno')
                                     or d_flask.get('pecas_ruins')
                                     or 0
                                 )
                                 
                                 # Fallback também para produção se Influx retornar 0
                                 if pecas_boas_rt == 0:
                                     # pecas_boas no flask já considera (prod - ref) ou contagem bruta
                                     # Usando 'produzido_turno' - 'pecas_ruins' ou 'pecas_boas' direto se existir
                                     if 'pecas_boas' in d_flask:
                                         pecas_boas_rt = float(d_flask.get('pecas_boas_turno') or d_flask['pecas_boas'])
                                     else:
                                         prod_turno = float(d_flask.get('produzido_turno', 0))
                                         pecas_boas_rt = max(0, prod_turno - pecas_ref_rt)
                         except Exception as e:
                             print(f"Erro fallback perdas_analise: {e}")
                             pecas_ref_rt = 0.0

        # Soma Total
        pecas_boas = pecas_boas_history + pecas_boas_rt
        pecas_refugadas = pecas_ref_history + pecas_ref_rt

        # Estimativa de tempo perdido por qualidade: (Pecas Refugadas / Velocidade)
        tempo_qualidade_min = 0.0
        if velocidade_media > 0 and pecas_refugadas > 0:
             tempo_qualidade_min = (float(pecas_refugadas) / float(velocidade_media))
        
        loss_tree['quality_loss'] = tempo_qualidade_min
        
        # A cascata usa apenas estados efetivamente medidos no equipamento de
        # referência. Falta de produção ou de comunicação não vira perda de
        # performance por inferência.
        measured_run = max(0.0, reference_run_minutes)
        loss_tree['quality_loss'] = min(loss_tree['quality_loss'], measured_run)
        loss_tree['net_run_time'] = measured_run
        loss_tree['good_production'] = max(
            0.0, measured_run - loss_tree['quality_loss']
        )
        loss_tree['unclassified_time'] = max(
            0.0, loss_tree['total_time'] - reference_covered_minutes
        )

        # Formatar Pareto
        pareto_list = [
            {'name': k, 'value': round(v, 1)} 
            for k, v in sorted(pareto_reasons.items(), key=lambda item: item[1], reverse=True)[:5]
        ]
        
        # Ordenar Ranking
        ranking_equipamentos.sort(key=lambda x: x['total_loss_min'], reverse=True)

        return Response({
            'linha_id': linha.id,
            'periodo': periodo,
            'data_inicio': data_inicio.isoformat(),
            'data_fim': data_fim.isoformat(),
            'waterfall': loss_tree,
            'pareto_unplanned': pareto_list,
            'equipment_ranking': ranking_equipamentos,
            'data_quality': {
                'methodology': 'timeline_estado_equipamento_referencia',
                'reference_equipment': gargalo.nome if gargalo else None,
                'reference_equipment_code': gargalo.codigo if gargalo else None,
                'reference_last_seen': (
                    state_last_seen.get(gargalo.codigo).isoformat()
                    if gargalo and state_last_seen.get(gargalo.codigo) else None
                ),
                'reference_online': bool(
                    gargalo
                    and state_last_seen.get(gargalo.codigo)
                    and state_last_seen[gargalo.codigo] >= agora - timedelta(minutes=2)
                ),
                'no_production_in_period': pecas_boas <= 0,
                'source_event_count': reference_event_count,
                'resolved_segment_count': reference_segment_count,
                'unclassified_minutes': round(loss_tree['unclassified_time'], 1),
            },
        })
    
    except Exception as e:
        import logging
        logging.error(f"Erro em perdas_analise: {e}", exc_info=True)
        return Response({
            'error': f'Erro ao analisar perdas: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def planejado_vs_real(request, linha_id):
    """
    GET /api/linhas/{linha_id}/planejado-vs-real/
    
    Retorna comparação planejado vs real
    """
    try:
        # Buscar linha
        try:
            linha = LinhaProducao.objects.get(id=linha_id)
        except LinhaProducao.DoesNotExist:
            return Response({
                'error': f'Linha {linha_id} não encontrada'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Buscar meta
        meta_toneladas_turno = float(linha.meta_toneladas_turno) if linha.meta_toneladas_turno else 100.0
        meta_toneladas_hora = float(linha.meta_toneladas_hora) if linha.meta_toneladas_hora else 12.5
        
        # Buscar turno atual
        turno_atual = obter_turno_atual()
        inicio_turno = calcular_inicio_turno(turno_atual)
        fim_turno = calcular_fim_turno(turno_atual)
        
        # Buscar equipamento final e formato
        equipamento_final = Equipamento.objects.filter(
            linha=linha,
            status='ATIVO',
            tags_coleta__ativa=True
        ).order_by('ordem_na_linha').distinct().last()
        
        if not equipamento_final:
            return Response({
                'error': 'Equipamento final não encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Buscar formato
        formato = None
        for eq in Equipamento.objects.filter(linha=linha, status='ATIVO').order_by('ordem_na_linha'):
            tag_formato = eq.tags_coleta.filter(formato__gt=0).first()
            if tag_formato:
                formato = float(tag_formato.formato)
                break
        
        if not formato:
            return Response({
                'error': 'Formato não encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Buscar métricas em tempo real
        metricas_rt = get_realtime_metrics(
            equipamento_codigo=equipamento_final.codigo,
            formato_gramas=formato,
            inicio_turno=inicio_turno,
            linha_codigo=linha.codigo,
        )
        
        realizado_toneladas = float(metricas_rt['toneladas_turno'])
        percentual_atingimento = (realizado_toneladas / meta_toneladas_turno) * 100 if meta_toneladas_turno > 0 else 0
        
        # Gerar timeline hora a hora
        timeline = []
        hora_atual = inicio_turno
        acumulado_planejado = 0.0
        acumulado_real = 0.0
        
        while hora_atual < timezone.now() and hora_atual < fim_turno:
            acumulado_planejado += meta_toneladas_hora
            
            # Buscar produção real nesta hora (simplificado - usa proporção)
            horas_decorridas = (timezone.now() - inicio_turno).total_seconds() / 3600.0
            if horas_decorridas > 0:
                producao_hora = realizado_toneladas / horas_decorridas
                acumulado_real += producao_hora
            
            timeline.append({
                'hora': hora_atual.isoformat(),
                'planejado': round(acumulado_planejado, 2),
                'realizado': round(acumulado_real, 2),
                'gap': round(acumulado_real - acumulado_planejado, 2)
            })
            
            hora_atual += timedelta(hours=1)
        
        return Response({
            'linha_id': linha.id,
            'linha_nome': linha.nome,
            'meta_toneladas': meta_toneladas_turno,
            'realizado_toneladas': round(realizado_toneladas, 2),
            'percentual_atingimento': round(percentual_atingimento, 1),
            'timeline': timeline
        })
    
    except Exception as e:
        import logging
        logging.error(f"Erro em planejado_vs_real: {e}", exc_info=True)
        return Response({
            'error': f'Erro ao buscar planejado vs real: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({
            'error': f'Erro ao buscar planejado vs real: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def strategic_loss_aggregation(request, linha_id):
    """
    GET /api/linhas/{linha_id}/strategic-loss/
    
    Retorna agregação de perdas em tempo real do InfluxDB (Sangramento)
    Agrupado por categoria do CLP.
    """
    from equipamentos.influx_helpers import get_influx_client
    
    try:
        client = get_influx_client()
        if not client:
            return Response({'error': 'InfluxDB unavailable'}, status=503)
            
        # Parâmetros
        horas = request.query_params.get('horas', 12)
        turno = request.query_params.get('turno')
        
        # Query InfluxDB
        query = f"""
            SELECT SUM("perda_ton") as total_perda
            FROM "perda_tempo_real"
            WHERE time > now() - {horas}h
        """
        
        if turno:
            query += f" AND \"turno\" = '{turno}'"
            
        query += ' GROUP BY "evento_clp"'
        
        result = client.query(query)
        points = list(result.get_points())
        
        # Formata para o frontend
        data = []
        total_ton = 0.0
        
        for point in points:
            ton = float(point.get('total_perda', 0))
            total_ton += ton
            data.append({
                'categoria': point.get('evento_clp', 'OUTRO'),
                'toneladas': round(ton, 3)
            })
            
        # Ordena
        data.sort(key=lambda x: x['toneladas'], reverse=True)
        
        return Response({
            'total_toneladas': round(total_ton, 3),
            'breakdown': data
        })
        
    except Exception as e:
        import logging
        logging.error(f"Erro em strategic_loss_aggregation: {e}", exc_info=True)
        return Response({
            'error': f'Erro ao buscar perdas estratégicas: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def monthly_production_stats(request, linha_id):
    """
    GET /api/linhas/{linha_id}/monthly-production-stats/
    
    Retorna estatísticas de produção do mês atual:
    - Total produzido (toneladas)
    - OEE Médio
    """
    try:
        # Definir intervalo do mês atual
        agora = timezone.now()
        inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Filtrar métricas DIÁRIAS do mês para a linha
        metricas = MetricaProducao.objects.filter(
            linha_id=linha_id,
            periodo='DIA',
            data_hora__gte=inicio_mes,
            data_hora__lte=agora,
            equipamento__isnull=True # Apenas métricas da linha consolidada
        )
        
        # Agregar
        agregado = metricas.aggregate(
            total_toneladas=Sum('toneladas_produzidas'),
            media_oee=Avg('oee')
        )
        
        total_toneladas = agregado['total_toneladas'] or 0.0
        media_oee = agregado['media_oee'] or 0.0
        
        return Response({
            'mes': agora.strftime('%B/%Y'),
            'total_toneladas': round(total_toneladas, 2),
            'media_oee': round(media_oee, 1)
        })
        
    except Exception as e:
        import logging
        logging.error(f"Erro em monthly_production_stats: {e}", exc_info=True)
        return Response({'error': str(e)}, status=500)


from influxdb import InfluxDBClient
from decouple import config

# Configuração InfluxDB (Reutilizando do agregador)
INFLUX_HOST = config('INFLUXDB_HOST', default='127.0.0.1')
INFLUX_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUX_DB = config('INFLUXDB_DATABASE', default='industrial_db')
INFLUX_USER = config('INFLUXDB_USER', default=None)
INFLUX_PASS = config('INFLUXDB_USER_PASSWORD', default=None)

influx_client = InfluxDBClient(
    host=INFLUX_HOST,
    port=INFLUX_PORT,
    username=INFLUX_USER,
    password=INFLUX_PASS,
    database=INFLUX_DB
)

@api_view(['GET'])
def monthly_op_history(request, linha_id):
    """
    GET /api/linhas/{linha_id}/monthly-op-history/
    
    Retorna histórico de OPs filtrado por mês/ano/dia e turno.
    Query params:
    - mes: 1-12 (default: atual)
    - ano: YYYY (default: atual)
    - dia: 1-31 (opcional)
    - turno: A, B, C (opcional)
    """
    try:
        # Parâmetros de filtro
        agora = timezone.now()
        mes = int(request.query_params.get('mes', agora.month))
        ano = int(request.query_params.get('ano', agora.year))
        dia = request.query_params.get('dia')
        turno = request.query_params.get('turno')
        
        # Definir intervalo de filtro
        if dia:
            dia = int(dia)
            data_inicio_filtro = timezone.datetime(ano, mes, dia, 0, 0, 0, tzinfo=timezone.get_current_timezone())
            data_fim_filtro = data_inicio_filtro + timedelta(days=1)
        else:
            data_inicio_filtro = timezone.datetime(ano, mes, 1, 0, 0, 0, tzinfo=timezone.get_current_timezone())
            # Primeiro dia do próximo mês
            if mes == 12:
                data_fim_filtro = timezone.datetime(ano + 1, 1, 1, 0, 0, 0, tzinfo=timezone.get_current_timezone())
            else:
                data_fim_filtro = timezone.datetime(ano, mes + 1, 1, 0, 0, 0, tzinfo=timezone.get_current_timezone())
        
        # Buscar históricos de SKU (OPs) que estiveram ativos no período
        historicos = HistoricoSKU.objects.filter(
            linha_id=linha_id,
            data_inicio__lt=data_fim_filtro
        ).filter(
            models.Q(data_fim__gte=data_inicio_filtro) | models.Q(data_fim__isnull=True)
        ).order_by('-data_inicio')
        
        data = []
        for hist in historicos:
            # 1. Filtro de Turno (se solicitado)
            if turno:
                # Verifica no InfluxDB se houve produção neste turno para esta OP
                query_turno = f"""
                    SELECT count("producao_acumulada_op") 
                    FROM "producao" 
                    WHERE "ordem_producao" = '{hist.ordem_producao}' 
                    AND "turno" = '{turno}'
                """
                try:
                    result_turno = influx_client.query(query_turno)
                    points_turno = list(result_turno.get_points())
                    if not points_turno or points_turno[0]['count'] == 0:
                        continue # Pula esta OP se não rodou no turno selecionado
                except Exception as e:
                    # Se der erro no Influx, assume que não rodou para não mostrar dados errados
                    continue

            # 2. Buscar Total Produzido no InfluxDB (LAST value)
            # Isso garante o valor real acumulado, incluindo a produção atual
            total_produzido = 0.0
            try:
                query_prod = f"""
                    SELECT last("producao_acumulada_op") as total
                    FROM "producao" 
                    WHERE "ordem_producao" = '{hist.ordem_producao}'
                """
                result_prod = influx_client.query(query_prod)
                points_prod = list(result_prod.get_points())
                if points_prod:
                    total_produzido = float(points_prod[0]['total'])
            except Exception as e:
                # Fallback para MySQL se Influx falhar
                print(f"Erro Influx OP {hist.ordem_producao}: {e}")
                filtro_tempo = models.Q(data_hora__gte=hist.data_inicio)
                if hist.data_fim:
                    filtro_tempo &= models.Q(data_hora__lte=hist.data_fim)
                else:
                    filtro_tempo &= models.Q(data_hora__lte=timezone.now())
                
                metricas_op = MetricaProducao.objects.filter(
                    linha_id=linha_id,
                    periodo='TURNO',
                    equipamento__isnull=True
                ).filter(filtro_tempo)
                total_produzido = metricas_op.aggregate(total=Sum('toneladas_produzidas'))['total'] or 0.0
            
            # Status
            meta = hist.meta_producao or 0
            if hist.data_fim:
                status_op = "Concluída"
            elif meta > 0 and total_produzido >= meta:
                status_op = "Concluída (Meta Atingida)"
            else:
                status_op = "Em Andamento"
            
            data.append({
                'id': hist.id,
                'ordem_producao': hist.ordem_producao,
                'produto': f"{hist.produto.codigo} - {hist.produto.descricao}" if hist.produto else "N/A",
                'data_inicio': hist.data_inicio.isoformat(),
                'data_fim': hist.data_fim.isoformat() if hist.data_fim else None,
                'total_produzido': round(total_produzido, 2),
                'total_planejado': meta,
                'status': status_op
            })
            
        return Response(data)
        
    except Exception as e:
        import logging
        logging.error(f"Erro em monthly_op_history: {e}", exc_info=True)
        return Response({'error': str(e)}, status=500)
def _waste_period_window(request, periodo):
    agora = timezone.localtime()
    start = request.query_params.get('data_inicio')
    end = request.query_params.get('data_fim')
    if start and end:
        inicio = timezone.datetime.fromisoformat(start.replace('Z', '+00:00'))
        fim = timezone.datetime.fromisoformat(end.replace('Z', '+00:00'))
        current_tz = timezone.get_current_timezone()
        if timezone.is_naive(inicio):
            inicio = timezone.make_aware(inicio, current_tz)
        if timezone.is_naive(fim):
            fim = timezone.make_aware(fim, current_tz)
        return timezone.localtime(inicio), timezone.localtime(fim)
    if periodo == 'HORA':
        return agora - timedelta(hours=1), agora
    if periodo == 'DIA':
        return agora.replace(hour=0, minute=0, second=0, microsecond=0), agora
    if periodo == 'SEMANA':
        inicio = (agora - timedelta(days=agora.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return inicio, agora
    if periodo == 'MES':
        return agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0), agora
    turno = obter_turno_atual()
    return calcular_inicio_turno(turno), agora


def _influx_time(value):
    return value.astimezone(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')


def _influx_tag(value):
    return str(value).replace('\\', '\\\\').replace("'", "\\'")


def _positive_counter_delta(current, previous):
    if current is None:
        return 0.0, previous
    try:
        current = float(current)
    except (TypeError, ValueError):
        return 0.0, previous
    if previous is None:
        return 0.0, current
    delta = current - previous
    return (delta if delta > 0 else 0.0), current


@api_view(['GET'])
def strategic_waste_analysis(request, linha_id=None):
    """Period-correct, line-scoped waste analysis from Influx counters."""
    try:
        if not linha_id:
            linha_id = request.query_params.get('linha')
        if not linha_id:
            return Response({'error': 'linha é obrigatória'}, status=400)

        linha = LinhaProducao.objects.get(id=linha_id)
        periodo = request.query_params.get('periodo', 'TURNO').upper()
        if periodo not in {'HORA', 'TURNO', 'DIA', 'SEMANA', 'MES'}:
            return Response({'error': f'Período inválido: {periodo}'}, status=400)
        data_inicio, data_fim = _waste_period_window(request, periodo)
        start_influx = _influx_time(data_inicio)
        end_influx = _influx_time(data_fim)
        client = get_influx_client()

        equipamentos = Equipamento.objects.filter(
            linha=linha, status='ATIVO'
        ).select_related('linha').order_by('ordem_na_linha')

        total_waste_units = 0.0
        total_waste_tons = 0.0
        production_candidates = []
        ignored_non_run_production_units = 0.0
        missing_format_units = 0.0
        by_equipment = {}
        by_state = {}
        state_labels = {
            0: 'Parado/Desligado', 1: 'Produzindo', 2: 'Aguardando',
            3: 'Bloqueado', 4: 'Falha/Quebra', 5: 'Setup',
            6: 'Teste/Engenharia', 7: 'Aguard. Manut.', 8: 'Manutenção',
            9: 'Falta Material', 11: 'Partindo',
            12: 'Aguardando Condições', 13: 'Parando', 999: 'Offline',
        }

        for eq in equipamentos:
            line_tag = _influx_tag(linha.codigo)
            eq_tag = _influx_tag(eq.codigo)
            where = f'"line" = \'{line_tag}\' AND "equipment" = \'{eq_tag}\''
            baseline_query = (
                'SELECT last("refugo_op_acumulado") AS waste, '
                'last("contagem_saida") AS production, '
                'last("estado_maquina") AS state, '
                'last("formato_gramas") AS format '
                f'FROM "production" WHERE {where} AND time < \'{start_influx}\''
            )
            baseline = list(client.query(baseline_query).get_points())
            baseline = baseline[0] if baseline else {}

            query = (
                'SELECT "refugo_op_acumulado", "contagem_saida", '
                '"estado_maquina", "formato_gramas" '
                f'FROM "production" WHERE {where} '
                f'AND time >= \'{start_influx}\' AND time <= \'{end_influx}\' '
                'ORDER BY time ASC'
            )
            points = list(client.query(query).get_points())
            previous_waste = baseline.get('waste')
            previous_production = baseline.get('production')
            baseline_state = baseline.get('state')
            current_state = int(baseline_state) if baseline_state is not None else 999
            current_format = float(baseline.get('format') or 0.0)
            eq_waste_units = 0.0
            eq_waste_tons = 0.0
            eq_production_tons = 0.0

            for point in points:
                if point.get('state') is not None or point.get('estado_maquina') is not None:
                    current_state = int(point.get('estado_maquina', point.get('state')))
                if point.get('formato_gramas') is not None:
                    current_format = float(point['formato_gramas'] or 0.0)

                waste_delta, previous_waste = _positive_counter_delta(
                    point.get('refugo_op_acumulado'), previous_waste
                )
                production_delta, previous_production = _positive_counter_delta(
                    point.get('contagem_saida'), previous_production
                )
                if waste_delta:
                    eq_waste_units += waste_delta
                    total_waste_units += waste_delta
                    if current_format > 0:
                        tons = waste_delta * current_format / 1_000_000.0
                        eq_waste_tons += tons
                        total_waste_tons += tons
                    else:
                        missing_format_units += waste_delta
                    bucket = by_state.setdefault(
                        current_state, {'units': 0.0, 'tons': 0.0}
                    )
                    bucket['units'] += waste_delta
                    if current_format > 0:
                        bucket['tons'] += waste_delta * current_format / 1_000_000.0
                if production_delta:
                    # A saída do contador só representa produção efetiva quando
                    # o mesmo ponto confirma a máquina em RUN. Incrementos em
                    # Aguardando/Falha/Offline podem ocorrer por teste, ajuste ou
                    # ressincronização do CLP e não devem virar toneladas produzidas.
                    if current_state == 1 and current_format > 0:
                        eq_production_tons += production_delta * current_format / 1_000_000.0
                    else:
                        ignored_non_run_production_units += production_delta

            production_candidates.append(eq_production_tons)
            if eq_waste_units > 0:
                by_equipment[eq.nome] = {
                    'units': eq_waste_units,
                    'tons': eq_waste_tons,
                }

        # A peça atravessa vários equipamentos; somar produção de todos
        # multiplicaria o mesmo fluxo. A maior saída válida representa a linha.
        total_production_tons = max(production_candidates, default=0.0)
        total_mass = total_production_tons + total_waste_tons
        waste_percentage = (
            total_waste_tons / total_mass * 100.0 if total_mass > 0 else 0.0
        )
        ranking_list = [
            {
                'name': name,
                'value': round(values['units']),
                'tons': round(values['tons'], 4),
                'share': round(values['units'] / total_waste_units * 100.0, 1)
                if total_waste_units > 0 else 0.0,
            }
            for name, values in sorted(
                by_equipment.items(), key=lambda item: item[1]['units'], reverse=True
            )[:5]
        ]
        state_list = [
            {
                'id': str(state),
                'label': state_labels.get(state, f'Outro ({state})'),
                'value': round(values['units']),
                'tons': round(values['tons'], 4),
                'share': round(values['units'] / total_waste_units * 100.0, 1)
                if total_waste_units > 0 else 0.0,
            }
            for state, values in sorted(
                by_state.items(), key=lambda item: item[1]['units'], reverse=True
            )
        ]
        return Response({
            'periodo': periodo,
            'data_inicio': data_inicio.isoformat(),
            'data_fim': data_fim.isoformat(),
            'total_waste': round(total_waste_units),
            'total_waste_tons': round(total_waste_tons, 4),
            'unit': 'unidades',
            'waste_percentage': round(waste_percentage, 2),
            'total_production': round(total_production_tons, 4),
            'by_equipment': ranking_list,
            'by_state': state_list,
            'data_quality': {
                'waste_units_without_format': round(missing_format_units),
                'ignored_non_run_production_units': round(ignored_non_run_production_units),
                'production_basis': 'maior_saida_valida_da_linha',
                'production_rule': 'incremento_contagem_saida_com_estado_RUN_e_formato_valido',
            },
        })
    except LinhaProducao.DoesNotExist:
        return Response({'error': f'Linha {linha_id} não encontrada'}, status=404)
    except Exception as e:
        import logging
        logging.error(f"Erro em strategic_waste_analysis: {e}", exc_info=True)
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def factory_loss_analysis(request):
    """
    GET /api/fabrica/perdas-analise/
    Análise Agregada de Perdas da Fábrica (Soma de todas as linhas)
    """
    try:
        periodo = request.query_params.get('periodo', 'TURNO')
        data_inicio_param = request.query_params.get('data_inicio')
        data_fim_param = request.query_params.get('data_fim')
        
        agora = timezone.now()
        
        if data_inicio_param and data_fim_param:
            data_inicio = timezone.datetime.fromisoformat(data_inicio_param.replace('Z', '+00:00'))
            data_fim = timezone.datetime.fromisoformat(data_fim_param.replace('Z', '+00:00'))
        elif periodo == 'MES':
            data_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            data_fim = agora
        elif periodo == 'SEMANA':
            data_inicio = (agora - timedelta(days=agora.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            data_fim = agora
        elif periodo == 'DIA':
            data_inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
            data_fim = agora
        else: # TURNO
            turno_atual = obter_turno_atual()
            data_inicio = calcular_inicio_turno(turno_atual)
            data_fim = agora
            
        PLANNED_LOSS = [EstadoEquipamento.SETUP, EstadoEquipamento.TESTE_PROJ]
        UNPLANNED_LOSS = [EstadoEquipamento.FAULT, EstadoEquipamento.MANUTENCAO, EstadoEquipamento.AGUARD_MNT, EstadoEquipamento.FALTA_MAT, 'PARADO']
        PERFORMANCE_LOSS = [EstadoEquipamento.WAIT_PREV, EstadoEquipamento.BLOCK_NEXT]

        global_loss_tree = {
            'total_time': 0.0, 'planned_loss': 0.0, 'unplanned_loss': 0.0,
            'performance_loss': 0.0, 'quality_loss': 0.0, 'good_production': 0.0, 'net_run_time': 0.0
        }
        global_ranking = []
        global_pareto = {}

        linhas = LinhaProducao.objects.filter(ativa=True)
        
        for linha in linhas:
            tempo_cal = (data_fim - data_inicio).total_seconds() / 60.0
            global_loss_tree['total_time'] += tempo_cal
            
            equips = Equipamento.objects.filter(linha=linha, status='ATIVO')
            gargalo = equips.filter(tipo__icontains='ENCHEDORA').first() or equips.first()
            if not gargalo: continue

            eventos = EventoEstadoEquipamento.objects.filter(
                models.Q(fim__isnull=False) | models.Q(fim__isnull=True),
                equipamento=gargalo,
                inicio__gte=data_inicio, inicio__lt=data_fim
            )
            
            line_planned = 0.0
            line_unplanned = 0.0
            line_perf_loss = 0.0 
            
            for ev in eventos:
                if ev.fim: dur = ev.duracao_segundos
                else: dur = (min(timezone.now(), data_fim) - min(ev.inicio, min(timezone.now(), data_fim))).total_seconds()
                dur_min = dur / 60.0
                
                if ev.estado in PLANNED_LOSS: line_planned += dur_min
                elif ev.estado in UNPLANNED_LOSS: line_unplanned += dur_min
                elif ev.estado in PERFORMANCE_LOSS: line_perf_loss += dur_min 
                
                if ev.estado in UNPLANNED_LOSS:
                    razao = f"{ev.tipo_falha.nome if ev.tipo_falha else ev.get_estado_display()} ({linha.nome})"
                    global_pareto[razao] = global_pareto.get(razao, 0) + dur_min

            global_loss_tree['planned_loss'] += line_planned
            global_loss_tree['unplanned_loss'] += line_unplanned
            global_loss_tree['performance_loss'] += line_perf_loss 
            
            for eq in equips:
                evs_eq = EventoEstadoEquipamento.objects.filter(
                    models.Q(fim__isnull=False) | models.Q(fim__isnull=True),
                    equipamento=eq, inicio__gte=data_inicio, inicio__lt=data_fim
                )
                loss_eq = 0.0
                stats = {'planned':0, 'unplanned':0}
                for e in evs_eq:
                     if e.fim: d = e.duracao_segundos
                     else: d = (min(timezone.now(), data_fim) - min(e.inicio, min(timezone.now(), data_fim))).total_seconds()
                     dm = d/60.0
                     if e.estado in PLANNED_LOSS: stats['planned']+=dm
                     elif e.estado in UNPLANNED_LOSS: stats['unplanned']+=dm
                     
                     if e.estado in PLANNED_LOSS or e.estado in UNPLANNED_LOSS:
                         loss_eq += dm
                
                if loss_eq > 0:
                    global_ranking.append({
                        'id': eq.id, 'nome': f"{eq.nome} ({linha.nome})",
                        'total_loss_min': round(loss_eq, 1),
                        'breakdown': stats
                    })

            pecas_boas = 0
            refugo = 0
            if hasattr(linha, 'velocidade_planejada'): vel_plan = linha.velocidade_planejada
            else: vel_plan = 1000 
            
            metricas = MetricaProducao.objects.filter(
                equipamento=gargalo,
                data_hora__gte=data_inicio, data_hora__lte=data_fim
            ).aggregate(prod=Sum('contagem_saida'), ref=Sum('descarte'))
            
            if metricas['prod']: pecas_boas = metricas['prod']
            if metricas['ref']: refugo = metricas['ref']
            
            q_loss = (refugo / vel_plan) if vel_plan > 0 else 0
            global_loss_tree['quality_loss'] += q_loss
            
            gp_time = (pecas_boas / vel_plan) if vel_plan > 0 else 0
            global_loss_tree['good_production'] += gp_time

        tempo_disponivel = global_loss_tree['total_time'] - global_loss_tree['planned_loss'] - global_loss_tree['unplanned_loss']
        calc_perf_loss = max(0, tempo_disponivel - global_loss_tree['quality_loss'] - global_loss_tree['good_production'])
        global_loss_tree['performance_loss'] = calc_perf_loss

        global_ranking.sort(key=lambda x: x['total_loss_min'], reverse=True)
        global_ranking = global_ranking[:10]
        
        pareto_list = [{'name': k, 'value': round(v, 1)} for k, v in sorted(global_pareto.items(), key=lambda x: x[1], reverse=True)[:5]]

        return Response({
            'periodo': periodo,
            'waterfall': global_loss_tree,
            'pareto_unplanned': pareto_list,
            'equipment_ranking': global_ranking
        })
    except Exception as e:
        import logging
        logging.error(f"Erro factory_loss: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def factory_waste_analysis(request):
    """
    GET /api/fabrica/waste-analysis/
    Análise de Descarte Global
    """
    try:
        from influxdb import InfluxDBClient
        from django.conf import settings
        
        periodo = request.query_params.get('periodo', 'TURNO')
        agora = timezone.now()
        
        if periodo == 'MES':
            data_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            data_fim = agora
        elif periodo == 'DIA':
             data_inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
             data_fim = agora
        else:
             turno_atual = obter_turno_atual()
             data_inicio = calcular_inicio_turno(turno_atual)
             data_fim = agora

        client = InfluxDBClient(host=settings.INFLUXDB_HOST, port=settings.INFLUXDB_PORT, 
                                username=settings.INFLUXDB_USER, password=settings.INFLUXDB_PASSWORD, 
                                database=settings.INFLUXDB_DATABASE)
        
        start_influx = data_inicio.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_influx = data_fim.strftime('%Y-%m-%dT%H:%M:%SZ')

        equipamentos = Equipamento.objects.filter(status='ATIVO')
        
        total_waste_tons = 0.0
        total_production_tons = 0.0
        
        by_equipment = {}
        by_state = {}
        
        MAPEAMENTO_ESTADOS = {
            1: 'Produzindo', 2: 'Aguardando', 3: 'Bloqueado', 4: 'Falha/Quebra',
            5: 'Setup', 6: 'Teste/Engenharia', 7: 'Aguard. Manut.', 8: 'Manutenção',
            9: 'Falta Material', 0: 'Parado/Desligado',
            11: 'Partindo', 12: 'Aguardando Condições', 13: 'Parando'
        }

        for eq in equipamentos:
            try:
                # Build default format
                current_fmt = 500.0
                f_rs = client.query(f"SELECT last(\"formato_gramas\") as fmt FROM \"production\" WHERE \"equipment\" = '{eq.codigo}' AND time < '{start_influx}'" )
                f_pts = list(f_rs.get_points())
                if f_pts and f_pts[0]['fmt']: current_fmt = float(f_pts[0]['fmt'])
            except: 
                current_fmt = 500.0

            try:
                # Build seed state
                curr_state = 1
                s_rs = client.query(f"SELECT last(\"estado_maquina\") as state FROM \"production\" WHERE \"equipment\" = '{eq.codigo}' AND time < '{start_influx}'")
                s_pts = list(s_rs.get_points())
                if s_pts: curr_state = int(s_pts[0]['state'])
            except: curr_state = 1
            
            # Query ajustada: busca refugo_op_acumulado e contagem_saida
            query = f"SELECT \"refugo_op_acumulado\", \"contagem_saida\", \"estado_maquina\", \"formato_gramas\" FROM \"production\" WHERE \"equipment\" = '{eq.codigo}' AND time >= '{start_influx}' AND time <= '{end_influx}' ORDER BY time ASC"
            try:
                rs = client.query(query)
                points = list(rs.get_points())
                
                last_waste = None
                last_prod = None
                
                eq_waste_ton = 0.0
                eq_prod_ton = 0.0
                
                # Para evitar picos falsos no início da query (se o primeiro ponto já for alto)
                # tentamos pegar o last antes do período, ou assumimos o primeiro ponto como base.
                first_point = True

                for p in points:
                    try:
                        # Atualiza estado e formato se disponíveis
                        if 'estado_maquina' in p and p['estado_maquina'] is not None:
                            curr_state = int(p['estado_maquina'])
                        
                        if 'formato_gramas' in p and p['formato_gramas'] is not None:
                            try:
                                current_fmt = float(p['formato_gramas'])
                            except: pass
                        
                        # Processamento de Refugo (Delta)
                        val_waste = p.get('refugo_op_acumulado')
                        if val_waste is not None:
                            val_waste = float(val_waste)
                            if last_waste is not None:
                                delta = val_waste - last_waste
                                # Filtra spikes e resets
                                if delta > 0 and delta < 2000:
                                    delta_ton = (delta * current_fmt) / 1000000.0
                                    eq_waste_ton += delta_ton
                                    
                                    # Atribuição ao estado
                                    eff_state = curr_state
                                    if curr_state == 0: eff_state = 1 # Heurística: se tem descarte, não tá parado
                                    st_name = MAPEAMENTO_ESTADOS.get(eff_state, 'Outro')
                                    by_state[st_name] = by_state.get(st_name, 0.0) + delta_ton
                            
                            last_waste = val_waste

                        # Processamento de Produção (Delta)
                        val_prod = p.get('contagem_saida')
                        if val_prod is not None:
                            val_prod = float(val_prod)
                            if last_prod is not None:
                                delta_p = val_prod - last_prod
                                if delta_p > 0 and delta_p < 20000: # Limite seguro para produção
                                    delta_p_ton = (delta_p * current_fmt) / 1000000.0
                                    eq_prod_ton += delta_p_ton
                            
                            last_prod = val_prod
                            
                        # Inicializa 'last' no primeiro ponto para evitar contar acumulado passado como delta
                        if first_point:
                             # Se quisermos ser muito precisos, deveríamos buscar o last() ANTES do periodo.
                             # Mas, como estamos iterando, o primeiro delta será 0 pois last_waste será setado agora.
                             # Correto.
                             first_point = False
                             
                    except: continue
                
                if eq_waste_ton > 0 or eq_prod_ton > 0:
                    total_waste_tons += eq_waste_ton
                    total_production_tons += eq_prod_ton
                    
                    if eq_waste_ton > 0:
                        by_equipment[f"{eq.nome} ({eq.linha.nome})"] = eq_waste_ton
                    
            except: continue

        total_waste_tons = max(0.0, total_waste_tons)
        total_production_tons = max(0.0, total_production_tons)
        
        # Cálculo do Percentual Global
        # Formula: Descarte / (Produção Boa + Descarte)
        total_massa = total_production_tons + total_waste_tons
        waste_percentage = (total_waste_tons / total_massa * 100.0) if total_massa > 0 else 0.0
        
        rank_list = [{'name': k, 'value': round(v, 4), 'share': round((v/total_waste_tons)*100, 1) if total_waste_tons > 0 else 0} for k, v in sorted(by_equipment.items(), key=lambda x:x[1], reverse=True)[:10]]
        
        st_list = [{'id': k, 'label': k, 'value': round(v, 4), 'share': round((v/total_waste_tons)*100, 1) if total_waste_tons > 0 else 0} for k, v in sorted(by_state.items(), key=lambda x:x[1], reverse=True)]

        return Response({
            'periodo': periodo,
            'total_waste': round(total_waste_tons, 4),
            'waste_percentage': round(waste_percentage, 2), # Novo campo
            'total_production': round(total_production_tons, 4), # Debug info
            'unit': 'ton',
            'by_equipment': rank_list,
            'by_state': st_list
        })
    except Exception as e:
        import logging
        logging.error(f"Erro factory_waste: {e}", exc_info=True)
        return Response({'error': str(e)}, status=500)
