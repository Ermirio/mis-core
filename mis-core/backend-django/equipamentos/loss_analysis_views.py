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
        periodo = request.query_params.get('periodo', 'TURNO')
        data_inicio_param = request.query_params.get('data_inicio')
        data_fim_param = request.query_params.get('data_fim')
        
        # Definir intervalo de tempo
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
        
        # Dicionários auxiliares para o Pareto
        pareto_reasons = {}
        
        for equipamento in equipamentos:
            # Buscar eventos neste intervalo (Concluídos OU em Andamento)
            eventos = EventoEstadoEquipamento.objects.filter(
                models.Q(fim__isnull=False) | models.Q(fim__isnull=True),
                equipamento=equipamento,
                inicio__gte=data_inicio,
                inicio__lt=data_fim
            )
            
            eq_stats = {'planned': 0.0, 'unplanned': 0.0, 'performance': 0.0}
            
            for evento in eventos:
                # Se evento está aberto, calcula duração até agora ou fim do período
                if evento.fim:
                    duracao_real_segundos = evento.duracao_segundos
                else:
                    fim_calculo = min(timezone.now(), data_fim)
                    # Garante que início não é futuro (sanidade)
                    inicio_calculo = min(evento.inicio, fim_calculo)
                    duracao_real_segundos = (fim_calculo - inicio_calculo).total_seconds()
                
                duracao_min = duracao_real_segundos / 60.0 if duracao_real_segundos > 0 else 0
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
                
                # Popular Pareto (apenas Unplanned para começar)
                if categoria == 'UNPLANNED':
                    # Tenta usar o TipoFalha específico, senão usa o Estado
                    razao = evento.tipo_falha.nome if evento.tipo_falha else evento.get_estado_display()
                    if razao not in pareto_reasons:
                        pareto_reasons[razao] = 0.0
                    pareto_reasons[razao] += duracao_min

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
                     rt_metrics = get_realtime_metrics(gargalo.codigo, formato, inicio_t)
                     if rt_metrics:
                         c_atual = float(rt_metrics.get('contagem_atual') or 0.0)
                         c_inicio = float(rt_metrics.get('contagem_inicio_turno') or 0.0)
                         pecas_boas_rt = max(0, c_atual - c_inicio)
                         # Refugo realtime se houver logic
                         pecas_ref_rt = 0.0

        # Soma Total
        pecas_boas = pecas_boas_history + pecas_boas_rt
        pecas_refugadas = pecas_ref_history + pecas_ref_rt

        # Estimativa de tempo perdido por qualidade: (Pecas Refugadas / Velocidade)
        tempo_qualidade_min = 0.0
        if velocidade_media > 0 and pecas_refugadas > 0:
             tempo_qualidade_min = (float(pecas_refugadas) / float(velocidade_media))
        
        loss_tree['quality_loss'] = tempo_qualidade_min
        
        # Fechamento do Waterfall (Cálculo Reverso)
        # Total Time - Planned - Unplanned = Loading Time
        # Loading Time - Performance = Net Run Time
        # Net Run Time - Quality = Good Production Time
        
        # Ajuste Performance Loss: O que não é setup, falha ou refugo, mas não produziu na velocidade máxima
        # Tempo Rodando Real = (Pecas Totais / Velocidade Real)
        # Tempo Rodando Ideal = (Pecas Totais / Velocidade Nominal)
        # Perda Vel = Real - Ideal
        # loss_tree['performance_loss'] já tem microparadas (Blocked/Starved). 
        # Falta adicionar a perda por velocidade reduzida.
        
        # Tempo total disponível para produzir (excluindo paradas totais)
        tempo_disponivel = loss_tree['total_time'] - loss_tree['planned_loss'] - loss_tree['unplanned_loss']
        
        # Tempo Teórico para produzir as peças boas
        tempo_teorico_boas = (pecas_boas / linha.velocidade_planejada) if linha.velocidade_planejada > 0 else 0
        
        # O Good Production é EXATAMENTE o tempo teórico para fazer as peças boas na velocidade nominal
        loss_tree['good_production'] = tempo_teorico_boas
        
        # O resto é performance loss (inclui microparadas e velocidade baixa)
        # Performance Loss = Tempo Disponível - Tempo Qualidade - Good Production
        loss_tree['performance_loss'] = max(0, tempo_disponivel - loss_tree['quality_loss'] - loss_tree['good_production'])

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
            'equipment_ranking': ranking_equipamentos
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
@api_view(['GET'])
def strategic_waste_analysis(request, linha_id):
    """
    GET /api/linhas/{linha_id}/waste-analysis/
    
    Retorna análise detalhada de perdas (refugo) por Equipamento e por Contexto (Estado).
    """
    from equipamentos.influx_helpers import get_influx_client
    
    try:
        # 1. Setup Básico
        try:
            linha = LinhaProducao.objects.get(id=linha_id)
        except LinhaProducao.DoesNotExist:
            return Response({'error': 'Linha não encontrada'}, status=404)
            
        client = get_influx_client()
        if not client:
            return Response({'error': 'InfluxDB unavailable'}, status=503)

        # 2. Definição de Período
        periodo = request.query_params.get('periodo', 'TURNO')
        # ... Lógica de Datas igual a perdas_analise ...
        agora = timezone.now()
        data_inicio_param = request.query_params.get('data_inicio')
        data_fim_param = request.query_params.get('data_fim')
        
        if data_inicio_param and data_fim_param:
            data_inicio = timezone.datetime.fromisoformat(data_inicio_param.replace('Z', '+00:00'))
            data_fim = timezone.datetime.fromisoformat(data_fim_param.replace('Z', '+00:00'))
        elif periodo == 'MES':
            data_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            data_fim = agora
        elif periodo == 'DIA':
            data_inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
            data_fim = agora
        else: # TURNO
            turno_atual = obter_turno_atual()
            data_inicio = calcular_inicio_turno(turno_atual)
            data_fim = agora

        # Resolução Temporal para evitar query pesada
        # Para Turno/Hora = 1 minuto
        # Para Dia/Mes = 10 minutos (perde precisão mas ganha performance)
        group_time = '10m' if periodo in ['MES', 'SEMANA'] else '1m'
        
        start_influx = data_inicio.isoformat()
        end_influx = data_fim.isoformat()

        # 3. Equipamentos Ativos
        equipamentos = Equipamento.objects.filter(linha=linha, status='ATIVO')
        
        waste_by_equipment = {}
        waste_by_state = {}
        total_line_waste = 0
        
        MAPEAMENTO_ESTADOS = {
            1: 'Produzindo', 2: 'Aguardando', 3: 'Bloqueado', 4: 'Falha/Quebra',
            5: 'Setup', 6: 'Teste/Engenharia', 7: 'Aguard. Manut.', 8: 'Manutenção',
            9: 'Falta Material', 0: 'Parado/Desligado',
            11: 'Partindo', 12: 'Aguardando Condições', 13: 'Parando'
        }

        # 4. Processamento via InfluxDB (Raw Stream Processor)
        for eq in equipamentos:
            # 4.1 Buscar Estado Inicial (Seed)
            # Fundamental: Se o período começa e a máquina já está rodando, não teremos ponto de estado.
            # Precisamos buscar o último estado ANTES do início do período.
            seed_query = f"""
                SELECT last("estado_maquina") as state 
                FROM "production" 
                WHERE "equipment" = '{eq.codigo}' 
                AND time < '{start_influx}'
            """
            try:
                seed_rs = client.query(seed_query)
                seed_points = list(seed_rs.get_points())
                current_state_code = 0
                if seed_points:
                     current_state_code = int(seed_points[0].get('state', 0) or 0)
            except Exception as e:
                print(f"Erro seed state {eq.codigo}: {e}")
                current_state_code = 1 # Default seguro: Se não sabemos, assume que estava PRODUZINDO se houver descarte.

            # 4.2 Buscando dados do período
            query = f"""
                SELECT "descarte", "estado_maquina" 
                FROM "production" 
                WHERE "equipment" = '{eq.codigo}' 
                AND time >= '{start_influx}' AND time <= '{end_influx}' 
                ORDER BY time ASC
            """
            
            try:
                rs = client.query(query)
                points = list(rs.get_points())
                
                eq_total = 0
                last_waste_val = None
                # current_state_code já inicializado pelo Seed ou Default 1
                
                for p in points:
                    # Atualiza Estado Atual (se disponível no ponto)
                    if 'estado_maquina' in p and p['estado_maquina'] is not None:
                         state_val = int(p['estado_maquina'])
                         # Só atualiza para 0 se realmente confiarmos. 
                         # Mas vamos ser fiéis ao banco:
                         current_state_code = state_val
                    
                    # Processa Descarte
                    if 'descarte' in p and p['descarte'] is not None:
                        curr_waste = p['descarte']
                        
                        if last_waste_val is not None:
                            delta = curr_waste - last_waste_val
                            
                            if delta > 0 and delta < 1000:
                                eq_total += delta
                                total_line_waste += delta
                                # HEURÍSTICA DE CORREÇÃO:
                                # Se a máquina diz que está parada (0) mas gerou descarte, assumimos Produzindo (1).
                                # Isso corrige delay de sensores ou setup manual.
                                effective_state = current_state_code
                                if current_state_code == 0:
                                    effective_state = 1
                                
                                state_name = MAPEAMENTO_ESTADOS.get(effective_state, 'Outro')
                                if state_name not in waste_by_state:
                                    waste_by_state[state_name] = 0
                                waste_by_state[state_name] += delta
                                
                        last_waste_val = curr_waste
                
                if eq_total > 0:
                    waste_by_equipment[eq.nome] = eq_total
                    
            except Exception as e:
                print(f"Erro processando waste eq {eq.codigo}: {e}")
                continue

        # 5. Formatação para Frontend
        
        # Ranking Equipamentos (Top 5)
        ranking_list = [
            {'name': k, 'value': v, 'share': round((v/total_line_waste)*100, 1)} 
            for k, v in sorted(waste_by_equipment.items(), key=lambda item: item[1], reverse=True)
        ]
        
        # Breakdown por Estado
        state_list = [
            {'id': k, 'label': k, 'value': v, 'share': round((v/total_line_waste)*100, 1)}
            for k, v in sorted(waste_by_state.items(), key=lambda item: item[1], reverse=True)
        ]
        
        return Response({
            'periodo': periodo,
            'total_waste': int(total_line_waste),
            'by_equipment': ranking_list,
            'by_state': state_list
        })
        
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
        
        total_waste = 0.0
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
            
            query = f"SELECT \"descarte\", \"estado_maquina\", \"formato_gramas\" FROM \"production\" WHERE \"equipment\" = '{eq.codigo}' AND time >= '{start_influx}' AND time <= '{end_influx}' ORDER BY time ASC"
            try:
                rs = client.query(query)
                points = list(rs.get_points())
                last_waste = None
                eq_total = 0.0
                
                for p in points:
                    try:
                        if 'estado_maquina' in p and p['estado_maquina'] is not None:
                            curr_state = int(p['estado_maquina'])
                        if 'formato_gramas' in p and p['formato_gramas'] is not None:
                            try:
                                current_fmt = float(p['formato_gramas'])
                            except: pass
                        
                        if 'descarte' in p and p['descarte'] is not None:
                            val = p['descarte']
                            if last_waste is not None:
                                delta = val - last_waste
                                if delta > 0 and delta < 1000:
                                    delta_ton = (delta * current_fmt) / 1000000.0
                                    
                                    eq_total += delta_ton
                                    total_waste += delta_ton
                                    
                                    eff_state = curr_state
                                    if curr_state == 0: eff_state = 1
                                    
                                    st_name = MAPEAMENTO_ESTADOS.get(eff_state, 'Outro')
                                    by_state[st_name] = by_state.get(st_name, 0.0) + delta_ton
                            last_waste = val
                    except: continue
                
                if eq_total > 0:
                    by_equipment[f"{eq.nome} ({eq.linha.nome})"] = eq_total
                    
            except: continue

        total_waste = max(0.0, total_waste)
        
        rank_list = [{'name': k, 'value': round(v, 4), 'share': round((v/total_waste)*100, 1) if total_waste > 0 else 0} for k, v in sorted(by_equipment.items(), key=lambda x:x[1], reverse=True)[:10]]
        st_list = [{'id': k, 'label': k, 'value': round(v, 4), 'share': round((v/total_waste)*100, 1) if total_waste > 0 else 0} for k, v in sorted(by_state.items(), key=lambda x:x[1], reverse=True)]

        return Response({
            'periodo': periodo,
            'total_waste': round(total_waste, 4),
            'unit': 'ton',
            'by_equipment': rank_list,
            'by_state': st_list
        })
    except Exception as e:
        import logging
        logging.error(f"Erro factory_waste: {e}")
        return Response({'error': str(e)}, status=500)
