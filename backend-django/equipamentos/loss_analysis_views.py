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
from decimal import Decimal

from equipamentos.models import (
    LinhaProducao, Equipamento, EventoEstadoEquipamento,
    TipoFalha, MetricaProducao, EstadoEquipamento, HistoricoSKU
)
from django.db import models
from django.db.models import Sum, Avg
from equipamentos.influx_helpers import get_realtime_metrics
from equipamentos.turno_helpers import obter_turno_atual, calcular_inicio_turno, calcular_fim_turno


@api_view(['GET'])
def perdas_analise(request, linha_id):
    """
    GET /api/linhas/{linha_id}/perdas-analise/
    
    Retorna análise completa de perdas da linha
    
    Query params:
    - periodo: HORA, TURNO, DIA (default: TURNO)
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
        periodo = request.query_params.get('periodo', 'TURNO')
        data_inicio_param = request.query_params.get('data_inicio')
        data_fim_param = request.query_params.get('data_fim')
        
        # Definir intervalo de tempo
        if data_inicio_param and data_fim_param:
            data_inicio = timezone.datetime.fromisoformat(data_inicio_param.replace('Z', '+00:00'))
            data_fim = timezone.datetime.fromisoformat(data_fim_param.replace('Z', '+00:00'))
        else:
            # Default: turno atual
            turno_atual = obter_turno_atual()
            data_inicio = calcular_inicio_turno(turno_atual)
            data_fim = timezone.now()
        
        # Buscar equipamentos da linha
        equipamentos = Equipamento.objects.filter(
            linha=linha,
            status='ATIVO'
        ).order_by('ordem_na_linha')
        
        # Buscar meta de vazão
        meta_vazao = float(linha.meta_toneladas_hora) if linha.meta_toneladas_hora else 12.0
        
        # Inicializar contadores
        total_perdas_ton = Decimal('0.0')
        breakdown_por_tipo = {
            'paradas': {'toneladas': Decimal('0.0'), 'percentual': 0.0, 'tempo_minutos': 0},
            'descarte': {'toneladas': Decimal('0.0'), 'percentual': 0.0, 'pecas': 0},
            'velocidade': {'toneladas': Decimal('0.0'), 'percentual': 0.0},
            'setup': {'toneladas': Decimal('0.0'), 'percentual': 0.0, 'tempo_minutos': 0},
        }
        breakdown_por_equipamento = []
        breakdown_por_falha = {}
        
        # Analisar cada equipamento
        for equipamento in equipamentos:
            # 1. Perdas por Paradas
            eventos_parada = EventoEstadoEquipamento.objects.filter(
                equipamento=equipamento,
                estado__in=[
                    EstadoEquipamento.FAULT,
                    EstadoEquipamento.FALTA_MAT,
                    EstadoEquipamento.AGUARD_MNT,
                    EstadoEquipamento.WAIT_PREV,
                    EstadoEquipamento.BLOCK_NEXT,
                ],
                inicio__gte=data_inicio,
                inicio__lt=data_fim,
                fim__isnull=False
            )
            
            tempo_parado_min = 0
            toneladas_paradas = Decimal('0.0')
            principal_causa = None
            maior_tempo = 0
            
            for evento in eventos_parada:
                duracao_min = evento.duracao_segundos / 60.0 if evento.duracao_segundos else 0
                tempo_parado_min += duracao_min
                
                # Calcular toneladas perdidas
                ton_perdidas = Decimal(str((duracao_min / 60.0) * meta_vazao))
                toneladas_paradas += ton_perdidas
                
                # Atualizar evento com toneladas perdidas
                if not evento.toneladas_perdidas:
                    evento.toneladas_perdidas = ton_perdidas
                    evento.save(update_fields=['toneladas_perdidas'])
                
                # Identificar principal causa
                if evento.tipo_falha and duracao_min > maior_tempo:
                    maior_tempo = duracao_min
                    principal_causa = evento.tipo_falha.nome
                
                # Agregar por tipo de falha
                if evento.tipo_falha:
                    falha_key = evento.tipo_falha.nome
                    if falha_key not in breakdown_por_falha:
                        breakdown_por_falha[falha_key] = {
                            'tipo_falha': falha_key,
                            'categoria': evento.tipo_falha.get_categoria_display(),
                            'frequencia': 0,
                            'tempo_total_minutos': 0,
                            'toneladas_perdidas': Decimal('0.0'),
                            'percentual': 0.0
                        }
                    breakdown_por_falha[falha_key]['frequencia'] += 1
                    breakdown_por_falha[falha_key]['tempo_total_minutos'] += duracao_min
                    breakdown_por_falha[falha_key]['toneladas_perdidas'] += ton_perdidas
            
            breakdown_por_tipo['paradas']['toneladas'] += toneladas_paradas
            breakdown_por_tipo['paradas']['tempo_minutos'] += int(tempo_parado_min)
            
            # 2. Perdas por Setup
            eventos_setup = EventoEstadoEquipamento.objects.filter(
                equipamento=equipamento,
                estado=EstadoEquipamento.SETUP,
                inicio__gte=data_inicio,
                inicio__lt=data_fim,
                fim__isnull=False
            )
            
            tempo_setup_min = 0
            toneladas_setup = Decimal('0.0')
            
            for evento in eventos_setup:
                duracao_min = evento.duracao_segundos / 60.0 if evento.duracao_segundos else 0
                tempo_setup_min += duracao_min
                ton_perdidas = Decimal(str((duracao_min / 60.0) * meta_vazao))
                toneladas_setup += ton_perdidas
                
                if not evento.toneladas_perdidas:
                    evento.toneladas_perdidas = ton_perdidas
                    evento.save(update_fields=['toneladas_perdidas'])
            
            breakdown_por_tipo['setup']['toneladas'] += toneladas_setup
            breakdown_por_tipo['setup']['tempo_minutos'] += int(tempo_setup_min)
            
            # 3. Perdas por Descarte (da métrica)
            metrica = MetricaProducao.objects.filter(
                equipamento=equipamento,
                data_hora__gte=data_inicio,
                data_hora__lt=data_fim
            ).order_by('-data_hora').first()
            
            if metrica and metrica.descarte > 0:
                formato = float(metrica.formato_gramas) if metrica.formato_gramas else 0
                if formato > 0:
                    ton_descarte = Decimal(str((metrica.descarte * formato) / 1_000_000.0))
                    breakdown_por_tipo['descarte']['toneladas'] += ton_descarte
                    breakdown_por_tipo['descarte']['pecas'] += metrica.descarte
            
            # Adicionar ao breakdown por equipamento
            total_eq = toneladas_paradas + toneladas_setup
            if total_eq > 0:
                breakdown_por_equipamento.append({
                    'equipamento_id': equipamento.id,
                    'equipamento_nome': equipamento.nome,
                    'toneladas_perdidas': float(total_eq),
                    'percentual': 0.0,  # Será calculado depois
                    'tempo_parado_minutos': int(tempo_parado_min + tempo_setup_min),
                    'principal_causa': principal_causa or 'Não especificada'
                })
        
        # Calcular total de perdas
        total_perdas_ton = (
            breakdown_por_tipo['paradas']['toneladas'] +
            breakdown_por_tipo['descarte']['toneladas'] +
            breakdown_por_tipo['setup']['toneladas']
        )
        
        # Calcular percentuais
        if total_perdas_ton > 0:
            for tipo in breakdown_por_tipo:
                ton = breakdown_por_tipo[tipo]['toneladas']
                breakdown_por_tipo[tipo]['percentual'] = round(float(ton / total_perdas_ton) * 100, 1)
                breakdown_por_tipo[tipo]['toneladas'] = float(ton)
            
            for eq in breakdown_por_equipamento:
                eq['percentual'] = round((eq['toneladas_perdidas'] / float(total_perdas_ton)) * 100, 1)
            
            for falha in breakdown_por_falha.values():
                falha['percentual'] = round(float(falha['toneladas_perdidas'] / total_perdas_ton) * 100, 1)
                falha['toneladas_perdidas'] = float(falha['toneladas_perdidas'])
        
        # Ordenar por maior perda
        breakdown_por_equipamento.sort(key=lambda x: x['toneladas_perdidas'], reverse=True)
        breakdown_por_falha_list = sorted(
            breakdown_por_falha.values(),
            key=lambda x: x['toneladas_perdidas'],
            reverse=True
        )
        
        return Response({
            'linha_id': linha.id,
            'linha_nome': linha.nome,
            'periodo': periodo,
            'data_inicio': data_inicio.isoformat(),
            'data_fim': data_fim.isoformat(),
            'total_perdas_ton': float(total_perdas_ton),
            'breakdown_por_tipo': breakdown_por_tipo,
            'breakdown_por_equipamento': breakdown_por_equipamento,
            'breakdown_por_falha': breakdown_por_falha_list
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
            inicio_turno=inicio_turno
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
