"""
Endpoint para histórico detalhado da linha com OEE, produção, SKU e OP
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from .models import MetricaProducao, HistoricoSKU
from .serializers import MetricaProducaoSerializer
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
def historico_linha_detalhado(request, linha_id):
    """
    Retorna histórico detalhado da linha com OEE, produção, SKU, OP
    
    Query params:
    - periodo: HORA, TURNO, DIA (default: TURNO)
    - limit: número de registros (default: 50)
    - data_inicio: filtro de data inicial (opcional)
    - data_fim: filtro de data final (opcional)
    """
    try:
        periodo = request.GET.get('periodo', 'TURNO')
        limit = int(request.GET.get('limit', 50))
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        
        # Novos filtros
        turno = request.GET.get('turno')
        sku = request.GET.get('sku')
        op = request.GET.get('op')
        
        # Busca métricas da linha
        queryset = MetricaProducao.objects.filter(
            linha_id=linha_id,
            equipamento__isnull=True,
            periodo=periodo
        ).select_related('linha', 'produto') # Otimização: já traz o produto
        
        # Aplica filtros de data
        if data_inicio:
            queryset = queryset.filter(data_hora__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data_hora__lte=data_fim)
            
        # Aplica novos filtros
        if turno:
            queryset = queryset.filter(turno=turno)
        if sku:
            queryset = queryset.filter(produto__codigo=sku)
        if op:
            queryset = queryset.filter(ordem_producao__icontains=op)
        
        # Ordena e limita
        metricas = queryset.order_by('-data_hora')[:limit]
        
        # Serializa
        serializer = MetricaProducaoSerializer(metricas, many=True)
        
        # Enriquece com dados do produto (já carregados no select_related)
        resultado = []
        for i, metrica_data in enumerate(serializer.data):
            # O objeto original está na lista 'metricas' no mesmo índice
            metrica_obj = metricas[i]
            
            if metrica_obj.produto:
                metrica_data['sku_codigo'] = metrica_obj.produto.codigo
                metrica_data['sku_descricao'] = metrica_obj.produto.descricao
            else:
                metrica_data['sku_codigo'] = None
                metrica_data['sku_descricao'] = None
            
            resultado.append(metrica_data)
        
        return Response({
            'status': 'success',
            'total': len(resultado),
            'periodo': periodo,
            'dados': resultado
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar histórico detalhado: {e}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)