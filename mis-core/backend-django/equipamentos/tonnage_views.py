"""
Endpoints de Tonelagem
======================
Endpoints específicos para consulta de dados de produção em toneladas
TEMPO REAL: Busca direto do InfluxDB
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from equipamentos.models import LinhaProducao, MetricaProducao, Equipamento
from equipamentos.serializers import TonnageDataSerializer


@api_view(['GET'])
def tonelagem_tempo_real(request, linha_id):
    """
    GET /api/linhas/{linha_id}/tonelagem-tempo-real/
    
    Retorna tonelagem em tempo real da linha (InfluxDB)
    """
    try:
        # Importar helpers
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from influx_helpers import get_realtime_metrics
        from turno_helpers import obter_turno_atual, calcular_inicio_turno, calcular_fim_turno
        
        # Buscar linha
        try:
            linha = LinhaProducao.objects.get(id=linha_id)
        except LinhaProducao.DoesNotExist:
            return Response({
                'error': f'Linha {linha_id} não encontrada'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Buscar equipamento final e formato
        equipamentos_asc = Equipamento.objects.filter(
            linha=linha,
            status='ATIVO'
        ).order_by('ordem_na_linha')
        
        # Formato
        formato = None
        for eq in equipamentos_asc:
            tag_formato = eq.tags_coleta.filter(formato__gt=0).first()
            if tag_formato:
                formato = float(tag_formato.formato)
                break
        
        # Equipamento final
        equipamento_final = equipamentos_asc.filter(tags_coleta__ativa=True).distinct().last()
        
        if not equipamento_final or not formato:
            return Response({
                'linha_id': linha.id,
                'linha_nome': linha.nome,
                'toneladas_hora_atual': 0.0,
                'vazao_real': 0.0,
                'meta_vazao': None,
                'formato_atual': formato,
                'percentual_meta': 0.0,
                'timestamp': timezone.now().isoformat(),
                'message': 'Equipamento final ou formato não encontrado'
            })
        
        # Buscar métricas em tempo real do InfluxDB
        turno_atual = obter_turno_atual()
        inicio_turno = calcular_inicio_turno(turno_atual)
        fim_turno = calcular_fim_turno(turno_atual)
        
        metricas_rt = get_realtime_metrics(
            equipamento_codigo=equipamento_final.codigo,
            formato_gramas=formato,
            inicio_turno=inicio_turno
        )
        
        # Calcular percentual da meta (se existir)
        percentual_meta = 0.0
        meta_vazao = getattr(linha, 'meta_toneladas_hora', None)
        
        # Cálculos adicionais (Esperado, Projeção, Diferença)
        toneladas_esperada = 0.0
        projecao_otimista = 0.0
        diferenca_toneladas = 0.0
        
        if meta_vazao:
            meta_vazao_float = float(meta_vazao)
            agora = timezone.now()
            
            # 1. Esperado: Meta * Tempo decorrido
            # Se agora > fim_turno, usa fim_turno (turno já acabou)
            tempo_calculo = min(agora, fim_turno)
            horas_decorridas = (tempo_calculo - inicio_turno).total_seconds() / 3600.0
            if horas_decorridas > 0:
                toneladas_esperada = meta_vazao_float * horas_decorridas
            
            # 2. Projeção Otimista: Produzido + (Meta * Tempo restante)
            # Se agora > fim_turno, tempo restante é 0
            if agora < fim_turno:
                horas_restantes = (fim_turno - agora).total_seconds() / 3600.0
                projecao_otimista = metricas_rt['toneladas_turno'] + (meta_vazao_float * horas_restantes)
            else:
                projecao_otimista = metricas_rt['toneladas_turno']
                
            # 3. Diferença: Produzido - Esperado
            diferenca_toneladas = metricas_rt['toneladas_turno'] - toneladas_esperada

            if metricas_rt['vazao_ton_hora'] > 0:
                percentual_meta = (metricas_rt['vazao_ton_hora'] / meta_vazao_float) * 100
        
        return Response({
            'linha_id': linha.id,
            'linha_nome': linha.nome,
            'toneladas_hora_atual': metricas_rt['toneladas_turno'],
            'vazao_real': metricas_rt['vazao_ton_hora'],
            'meta_vazao': float(meta_vazao) if meta_vazao else None,
            'formato_atual': formato,
            'percentual_meta': round(percentual_meta, 1),
            'toneladas_esperada': round(toneladas_esperada, 3),
            'projecao_otimista': round(projecao_otimista, 3),
            'diferenca_toneladas': round(diferenca_toneladas, 3),
            'timestamp': timezone.now().isoformat()
        })
    
    except Exception as e:
        import logging
        logging.error(f"Erro em tonelagem_tempo_real: {e}")
        return Response({
            'error': f'Erro ao buscar tonelagem: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def historico_tonelagem(request, linha_id):
    """
    GET /api/linhas/{linha_id}/historico-tonelagem/
    
    Retorna histórico de tonelagem da linha (MySQL - turnos fechados)
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
        data_inicio = request.query_params.get('data_inicio')
        data_fim = request.query_params.get('data_fim')
        turno = request.query_params.get('turno')
        
        # Query base - busca métricas consolidadas
        queryset = MetricaProducao.objects.filter(
            linha_id=linha_id,
            equipamento__isnull=True,
            periodo=periodo
        )
        
        # Filtros de data
        if data_inicio:
            queryset = queryset.filter(data_hora__gte=data_inicio)
        else:
            queryset = queryset.filter(data_hora__gte=timezone.now() - timedelta(days=1))
        
        if data_fim:
            queryset = queryset.filter(data_hora__lte=data_fim)
        
        # Filtro de turno
        if turno and periodo == 'TURNO':
            queryset = queryset.filter(turno=turno)
        
        # Ordenar por data
        metricas = queryset.order_by('-data_hora')
        
        # FALLBACK: Se não houver métricas consolidadas, busca do último equipamento
        if not metricas.exists():
            queryset = MetricaProducao.objects.filter(
                linha_id=linha_id,
                periodo=periodo,
                equipamento__ordem_na_linha__isnull=False
            )
            
            if data_inicio:
                queryset = queryset.filter(data_hora__gte=data_inicio)
            else:
                queryset = queryset.filter(data_hora__gte=timezone.now() - timedelta(days=1))
            
            if data_fim:
                queryset = queryset.filter(data_hora__lte=data_fim)
            
            if turno and periodo == 'TURNO':
                queryset = queryset.filter(turno=turno)
            
            metricas = queryset.order_by('-equipamento__ordem_na_linha', '-data_hora')
        
        # Serializar
        serializer = TonnageDataSerializer(metricas, many=True)
        
        # Calcular totais
        toneladas_total = sum(float(m.toneladas_produzidas) for m in metricas)
        vazao_media = sum(float(m.vazao_real_ton_hora) for m in metricas) / len(metricas) if metricas else 0
        
        return Response({
            'linha_id': linha.id,
            'linha_nome': linha.nome,
            'periodo': periodo,
            'total_registros': metricas.count(),
            'toneladas_total': round(toneladas_total, 3),
            'vazao_media': round(vazao_media, 3),
            'dados': serializer.data
        })
    
    except Exception as e:
        return Response({
            'error': f'Erro ao buscar histórico: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def tonelagem_por_equipamento(request, equipamento_id):
    """
    GET /api/equipamentos/{equipamento_id}/tonelagem/
    
    Retorna tonelagem de um equipamento específico (MySQL)
    """
    try:
        periodo = request.query_params.get('periodo', 'HORA')
        limite = int(request.query_params.get('limite', 24))
        
        # Buscar métricas
        metricas = MetricaProducao.objects.filter(
            equipamento_id=equipamento_id,
            periodo=periodo
        ).order_by('-data_hora')[:limite]
        
        if not metricas:
            return Response({
                'error': 'Nenhum dado encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = TonnageDataSerializer(metricas, many=True)
        
        # Pegar informações do equipamento
        primeiro = metricas[0]
        
        return Response({
            'equipamento_id': equipamento_id,
            'equipamento_nome': primeiro.equipamento.nome if primeiro.equipamento else 'N/A',
            'formato_gramas': float(primeiro.formato_gramas) if primeiro.formato_gramas else None,
            'periodo': periodo,
            'total_registros': len(metricas),
            'dados': serializer.data
        })
    
    except Exception as e:
        return Response({
            'error': f'Erro ao buscar tonelagem do equipamento: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
