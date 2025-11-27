from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from .models import (
    LinhaProducao, Equipamento, Sensor, MetricaProducao, 
    Defeito, ConexaoOPC, TagColeta,
    TurnoProducao, CalendarioProducao, EventoEstadoEquipamento
)
from .serializers import (
    LinhaProducaoSerializer, EquipamentoSerializer, SensorSerializer,
    MetricaProducaoSerializer, DefeitoSerializer, ConexaoOPCSerializer,
    TagColetaSerializer, EquipamentoColetorSerializer, MetricaConsolidadaInputSerializer,
    TurnoProducaoSerializer, CalendarioProducaoSerializer,
    EventoEstadoEquipamentoSerializer, EventoEstadoCreateSerializer
)


class LinhaProducaoViewSet(viewsets.ModelViewSet):
    queryset = LinhaProducao.objects.all()
    serializer_class = LinhaProducaoSerializer
    
    @action(detail=False, methods=['get'])
    def ativas(self, request):
        """Retorna apenas linhas ativas"""
        ativas = self.queryset.filter(ativa=True)
        serializer = self.get_serializer(ativas, many=True)
        return Response(serializer.data)


class EquipamentoViewSet(viewsets.ModelViewSet):
    queryset = Equipamento.objects.select_related('linha').prefetch_related('sensores')
    serializer_class = EquipamentoSerializer
    
    @action(detail=False, methods=['get'])
    def por_linha(self, request):
        """Retorna equipamentos de uma linha específica"""
        linha_id = request.query_params.get('linha_id')
        if linha_id:
            equipamentos = self.queryset.filter(linha_id=linha_id)
            serializer = self.get_serializer(equipamentos, many=True)
            return Response(serializer.data)
        return Response({'error': 'linha_id é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)


class ConexaoOPCViewSet(viewsets.ModelViewSet):
    queryset = ConexaoOPC.objects.all()
    serializer_class = ConexaoOPCSerializer


class TagColetaViewSet(viewsets.ModelViewSet):
    queryset = TagColeta.objects.select_related('equipamento', 'conexao')
    serializer_class = TagColetaSerializer


class SensorViewSet(viewsets.ModelViewSet):
    queryset = Sensor.objects.all()
    serializer_class = SensorSerializer
    
    @action(detail=False, methods=['get'])
    def por_linha(self, request):
        """Retorna sensores de uma linha específica"""
        linha_id = request.query_params.get('linha_id')
        if linha_id:
            sensores = self.queryset.filter(linha_id=linha_id)
            serializer = self.get_serializer(sensores, many=True)
            return Response(serializer.data)
        return Response({'error': 'linha_id é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)


class MetricaProducaoViewSet(viewsets.ModelViewSet):
    queryset = MetricaProducao.objects.select_related('linha', 'equipamento')
    serializer_class = MetricaProducaoSerializer
    
    def get_queryset(self):
        """Permite filtrar métricas por linha, equipamento, período e datas"""
        queryset = super().get_queryset()
        
        # Filtro por linha
        linha_id = self.request.query_params.get('linha_id')
        if linha_id:
            queryset = queryset.filter(linha_id=linha_id)
        
        # Filtro por equipamento
        equipamento_id = self.request.query_params.get('equipamento_id')
        if equipamento_id:
            queryset = queryset.filter(equipamento_id=equipamento_id)
        
        # Filtro por período
        periodo = self.request.query_params.get('periodo')
        if periodo:
            queryset = queryset.filter(periodo=periodo)
        
        # Filtro por data inicial
        data_inicio = self.request.query_params.get('data_inicio')
        if data_inicio:
            queryset = queryset.filter(data_hora__gte=data_inicio)
        
        # Filtro por data final
        data_fim = self.request.query_params.get('data_fim')
        if data_fim:
            queryset = queryset.filter(data_hora__lte=data_fim)
        
        return queryset.order_by('-data_hora')
    
    @action(detail=False, methods=['get'])
    def ultima_hora(self, request):
        """Retorna a última métrica horária de cada equipamento"""
        linha_id = request.query_params.get('linha_id')
        
        if not linha_id:
            return Response({
                'error': 'linha_id é obrigatório'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Busca última métrica de cada equipamento
        equipamentos = Equipamento.objects.filter(linha_id=linha_id, status='ATIVO')
        resultados = []
        
        for eq in equipamentos:
            metrica = MetricaProducao.objects.filter(
                equipamento=eq,
                periodo='HORA'
            ).order_by('-data_hora').first()
            
            if metrica:
                serializer = self.get_serializer(metrica)
                resultados.append(serializer.data)
        
        return Response(resultados)


class DefeitoViewSet(viewsets.ModelViewSet):
    queryset = Defeito.objects.all()
    serializer_class = DefeitoSerializer


# ===== NOVOS VIEWSETS =====

class TurnoProducaoViewSet(viewsets.ModelViewSet):
    """ViewSet para turnos de produção"""
    queryset = TurnoProducao.objects.all()
    serializer_class = TurnoProducaoSerializer
    
    @action(detail=False, methods=['get'])
    def ativos(self, request):
        """Retorna apenas turnos ativos"""
        ativos = self.queryset.filter(ativo=True)
        serializer = self.get_serializer(ativos, many=True)
        return Response(serializer.data)


class CalendarioProducaoViewSet(viewsets.ModelViewSet):
    """ViewSet para calendário de produção"""
    queryset = CalendarioProducao.objects.select_related('linha', 'turno')
    serializer_class = CalendarioProducaoSerializer
    
    def get_queryset(self):
        """Permite filtrar por linha e data"""
        queryset = super().get_queryset()
        
        linha_id = self.request.query_params.get('linha_id')
        if linha_id:
            queryset = queryset.filter(linha_id=linha_id)
        
        data = self.request.query_params.get('data')
        if data:
            queryset = queryset.filter(data=data)
        
        return queryset.order_by('-data')


class EventoEstadoEquipamentoViewSet(viewsets.ModelViewSet):
    """ViewSet para eventos de estado"""
    queryset = EventoEstadoEquipamento.objects.select_related('equipamento')
    serializer_class = EventoEstadoEquipamentoSerializer
    
    def get_queryset(self):
        """Permite filtrar por equipamento e período"""
        queryset = super().get_queryset()
        
        equipamento_id = self.request.query_params.get('equipamento_id')
        if equipamento_id:
            queryset = queryset.filter(equipamento_id=equipamento_id)
        
        equipamento_codigo = self.request.query_params.get('equipamento_codigo')
        if equipamento_codigo:
            queryset = queryset.filter(equipamento__codigo=equipamento_codigo)
        
        # Filtro por período
        inicio = self.request.query_params.get('inicio')
        if inicio:
            queryset = queryset.filter(inicio__gte=inicio)
        
        fim = self.request.query_params.get('fim')
        if fim:
            queryset = queryset.filter(inicio__lte=fim)
        
        return queryset.order_by('-inicio')
    
    @action(detail=False, methods=['get'])
    def abertos(self, request):
        """Retorna eventos ainda abertos (sem fim)"""
        abertos = self.queryset.filter(fim__isnull=True)
        serializer = self.get_serializer(abertos, many=True)
        return Response(serializer.data)


# ===== ENDPOINTS ESPECIAIS PARA O COLETOR =====

@api_view(['GET'])
def configuracao_coletor(request):
    """
    Endpoint GET /api/configuracao_coletor/
    
    Retorna toda a configuração necessária para o Coletor:
    - Equipamentos ativos
    - Conexões OPC
    - Tags de coleta com seus Node IDs
    
    Este é o "ponto único de verdade" para o Coletor buscar sua configuração.
    """
    try:
        # Busca apenas equipamentos ativos de linhas ativas
        equipamentos = Equipamento.objects.filter(
            status='ATIVO',
            linha__ativa=True
        ).select_related('linha').prefetch_related(
            'tags_coleta',
            'tags_coleta__conexao'
        ).order_by('linha__codigo', 'ordem_na_linha')
        
        # Filtra apenas tags ativas
        for eq in equipamentos:
            eq.tags_coleta_ativas = eq.tags_coleta.filter(ativa=True, conexao__ativa=True)
        
        serializer = EquipamentoColetorSerializer(equipamentos, many=True)
        
        return Response({
            'status': 'success',
            'timestamp': timezone.now().isoformat(),
            'total_equipamentos': equipamentos.count(),
            'equipamentos': serializer.data
        })
    
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def eventos_estado(request):
    """
    Endpoint POST /api/eventos_estado/
    
    Recebe eventos de mudança de estado do Coletor OPC.
    
    Payload esperado:
    {
        "equipamento_codigo": "L01_ENCH_01",
        "estado": "RUN",
        "timestamp": "2024-01-15T10:30:00Z",
        "origem": "OPC",
        "observacao": "Mudança automática de estado"
    }
    
    Lógica:
    1. Fecha o último evento aberto do equipamento (se existir)
    2. Cria um novo evento com o novo estado
    """
    try:
        serializer = EventoEstadoCreateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'status': 'error',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Busca o equipamento pelo código
        try:
            equipamento = Equipamento.objects.get(codigo=data['equipamento_codigo'])
        except Equipamento.DoesNotExist:
            return Response({
                'status': 'error',
                'message': f"Equipamento com código '{data['equipamento_codigo']}' não encontrado"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Fecha o último evento aberto
        evento_fechado = EventoEstadoEquipamento.fechar_evento_aberto(equipamento)
        
        # Cria novo evento
        novo_evento = EventoEstadoEquipamento.objects.create(
            equipamento=equipamento,
            estado=data['estado'],
            inicio=data['timestamp'],
            origem=data.get('origem', 'OPC'),
            observacao=data.get('observacao', '')
        )
        
        return Response({
            'status': 'success',
            'message': 'Evento de estado registrado',
            'evento_id': novo_evento.id,
            'evento_anterior_fechado': evento_fechado.id if evento_fechado else None
        }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Erro interno: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def metricas_consolidadas(request):
    """
    Endpoint POST /api/metricas_consolidadas/
    
    Recebe dados agregados do Flask/Coletor e os salva no MySQL.
    
    Payload esperado:
    {
        "linha_id": 1,
        "equipamento_id": 2,  // opcional
        "data_hora": "2024-01-15T10:00:00Z",
        "periodo": "HORA",
        "contagem_entrada": 5000,
        "contagem_saida": 4950,
        "velocidade_planejada": 100.0,
        "velocidade_real": 98.5,
        "tempo_programado": 60.0,
        "tempo_producao": 55.0,
        "tempo_parada": 3.0,
        "tempo_setup": 2.0,
        "tempo_nao_programado": 0.0,
        "disponibilidade": 92.0,  // opcional, será calculado se não fornecido
        "performance": 98.5,      // opcional
        "qualidade": 99.0,        // opcional
        "oee": 89.7               // opcional
    }
    
    Nota: Os KPIs (disponibilidade, performance, qualidade, oee) são opcionais.
    Se não forem fornecidos, serão calculados automaticamente pelo model.save()
    """
    try:
        serializer = MetricaConsolidadaInputSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'status': 'error',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Busca a linha
        try:
            linha = LinhaProducao.objects.get(id=data['linha_id'])
        except LinhaProducao.DoesNotExist:
            return Response({
                'status': 'error',
                'message': f"Linha com id {data['linha_id']} não encontrada"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Busca o equipamento (se fornecido)
        equipamento = None
        if data.get('equipamento_id'):
            try:
                equipamento = Equipamento.objects.get(id=data['equipamento_id'])
            except Equipamento.DoesNotExist:
                return Response({
                    'status': 'error',
                    'message': f"Equipamento com id {data['equipamento_id']} não encontrado"
                }, status=status.HTTP_404_NOT_FOUND)
        
        # Prepara defaults para update_or_create
        defaults = {
            'turno': data.get('turno', ''),
            'contagem_entrada': data['contagem_entrada'],
            'contagem_saida': data['contagem_saida'],
            'velocidade_planejada': data['velocidade_planejada'],
            'velocidade_real': data['velocidade_real'],
            'tempo_programado': data.get('tempo_programado', 60.0),
            'tempo_producao': data['tempo_producao'],
            'tempo_parada': data['tempo_parada'],
            'tempo_setup': data['tempo_setup'],
            'tempo_nao_programado': data.get('tempo_nao_programado', 0.0),
        }
        
        # Adiciona KPIs se fornecidos (senão serão calculados no save)
        if 'disponibilidade' in data:
            defaults['disponibilidade'] = data['disponibilidade']
        if 'performance' in data:
            defaults['performance'] = data['performance']
        if 'qualidade' in data:
            defaults['qualidade'] = data['qualidade']
        if 'oee' in data:
            defaults['oee'] = data['oee']
        
        # Cria ou atualiza a métrica
        metrica, created = MetricaProducao.objects.update_or_create(
            linha=linha,
            equipamento=equipamento,
            data_hora=data['data_hora'],
            periodo=data['periodo'],
            defaults=defaults
        )
        
        return Response({
            'status': 'success',
            'message': 'Métrica criada' if created else 'Métrica atualizada',
            'metrica_id': metrica.id,
            'disponibilidade': metrica.disponibilidade,
            'performance': metrica.performance,
            'qualidade': metrica.qualidade,
            'oee': metrica.oee
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Erro interno: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
