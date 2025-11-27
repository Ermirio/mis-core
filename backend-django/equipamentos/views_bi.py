"""
Views para BI (Business Intelligence)
Endpoints side-by-side para não interferir nas APIs existentes
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Avg, Count, Q
from datetime import datetime, timedelta

from equipamentos.models import (
    OrdemProducao, RegistroProducaoTurno, LinhaProducao, Area
)
from .serializers_bi import (
    OrdemProducaoSerializer, RegistroProducaoTurnoSerializer,
    ProducaoFabricaSerializer, ProducaoTecnologiaSerializer,
    ProducaoLinhaSerializer
)


class OrdemProducaoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para Ordens de Produção
    
    Endpoints:
    - GET /api/bi/ordens-producao/ - Lista todas as OPs
    - GET /api/bi/ordens-producao/<id>/ - Detalhe de uma OP
    - GET /api/bi/ordens-producao/ativas/ - Apenas OPs ativas
    - GET /api/bi/ordens-producao/concluidas/ - Apenas OPs concluídas
    """
    
    queryset = OrdemProducao.objects.select_related(
        'linha', 'linha__area', 'linha__area__fabrica', 'produto'
    ).all()
    serializer_class = OrdemProducaoSerializer
    filterset_fields = ['status', 'linha', 'produto']
    search_fields = ['codigo', 'descricao', 'produto__codigo']
    ordering_fields = ['data_planejada_inicio', 'meta_total', 'criado_em']
    ordering = ['-data_planejada_inicio']
    
    @action(detail=False, methods=['get'])
    def ativas(self, request):
        """Retorna apenas OPs em produção"""
        ops = self.get_queryset().filter(
            Q(status='PRODUZINDO') | Q(status='PAUSADA')
        )
        serializer = self.get_serializer(ops, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def concluidas(self, request):
        """Retorna apenas OPs concluídas"""
        ops = self.get_queryset().filter(status='CONCLUIDA')
        serializer = self.get_serializer(ops, many=True)
        return Response(serializer.data)


class RegistroProducaoTurnoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para Registros de Produção por Turno (somente leitura)
    
    Endpoints:
    - GET /api/bi/registros-turno/ - Lista todos os registros
    - GET /api/bi/registros-turno/<id>/ - Detalhe de um registro
    - GET /api/bi/registros-turno/periodo/ - Filtra por período
    """
    
    queryset = RegistroProducaoTurno.objects.select_related(
        'ordem_producao', 'linha', 'linha__area', 'linha__area__fabrica',
        'produto', 'turno'
    ).all()
    serializer_class = RegistroProducaoTurnoSerializer
    filterset_fields = ['data', 'turno', 'linha', 'ordem_producao']
    search_fields = ['ordem_producao__codigo', 'linha__codigo', 'produto__codigo']
    ordering_fields = ['data', 'oee', 'eficiencia', 'producao_unidades']
    ordering = ['-data', 'turno']
    
    @action(detail=False, methods=['get'])
    def periodo(self, request):
        """
        Filtra registros por período
        
        Query params:
        - data_inicio: YYYY-MM-DD
        - data_fim: YYYY-MM-DD
        - linha: código da linha (opcional)
        - turno: código do turno (opcional)
        """
        data_inicio = request.query_params.get('data_inicio')
        data_fim = request.query_params.get('data_fim')
        linha_codigo = request.query_params.get('linha')
        turno_codigo = request.query_params.get('turno')
        
        if not data_inicio or not data_fim:
            return Response(
                {'error': 'data_inicio e data_fim são obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        registros = self.get_queryset().filter(
            data__gte=data_inicio,
            data__lte=data_fim
        )
        
        if linha_codigo:
            registros = registros.filter(linha__codigo=linha_codigo)
        
        if turno_codigo:
            registros = registros.filter(turno__codigo=turno_codigo)
        
        serializer = self.get_serializer(registros, many=True)
        return Response(serializer.data)


class ProducaoBIViewSet(viewsets.ViewSet):
    """
    ViewSet para consultas agregadas de BI
    
    Endpoints:
    - GET /api/bi/producao/fabrica/ - Visão total da fábrica
    - GET /api/bi/producao/tecnologia/ - Visão por tecnologia/área
    - GET /api/bi/producao/linha/ - Visão por linha
    """
    
    @action(detail=False, methods=['get'])
    def fabrica(self, request):
        """
        Retorna métricas consolidadas da fábrica inteira
        
        Query params:
        - data_inicio: YYYY-MM-DD (opcional, padrão: último mês)
        - data_fim: YYYY-MM-DD (opcional, padrão: hoje)
        """
        data_fim = request.query_params.get('data_fim', datetime.now().date())
        data_inicio = request.query_params.get('data_inicio', datetime.now().date() - timedelta(days=30))
        
        if isinstance(data_fim, str):
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        if isinstance(data_inicio, str):
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        
        # Agregar dados
        agregado = RegistroProducaoTurno.objects.filter(
            data__gte=data_inicio,
            data__lte=data_fim
        ).aggregate(
            total_producao_unidades=Sum('producao_unidades'),
            total_producao_toneladas=Sum('producao_toneladas'),
            total_refugo_kg=Sum('refugo_kg'),
            oee_medio=Avg('oee'),
            disponibilidade_media=Avg('disponibilidade'),
            performance_media=Avg('performance'),
            qualidade_media=Avg('qualidade'),
            eficiencia_media=Avg('eficiencia'),
        )
        
        # Contar OPs
        ops_ativas = OrdemProducao.objects.filter(
            Q(status='PRODUZINDO') | Q(status='PAUSADA')
        ).count()
        
        ops_concluidas = OrdemProducao.objects.filter(
            status='CONCLUIDA',
            data_fim_real__gte=data_inicio,
            data_fim_real__lte=data_fim
        ).count()
        
        dados = {
            **agregado,
            'total_ops_ativas': ops_ativas,
            'total_ops_concluidas': ops_concluidas,
        }
        
        # Garantir valores padrão
        for key in dados:
            if dados[key] is None:
                dados[key] = 0
        
        serializer = ProducaoFabricaSerializer(dados)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def tecnologia(self, request):
        """
        Retorna métricas agregadas por tecnologia/área
        
        Query params:
        - data_inicio: YYYY-MM-DD (opcional)
        - data_fim: YYYY-MM-DD (opcional)
        - tecnologia_id: ID da área/tecnologia (opcional)
        """
        data_fim = request.query_params.get('data_fim', datetime.now().date())
        data_inicio = request.query_params.get('data_inicio', datetime.now().date() - timedelta(days=30))
        tecnologia_id = request.query_params.get('tecnologia_id')
        
        if isinstance(data_fim, str):
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        if isinstance(data_inicio, str):
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        
        # Filtrar áreas
        areas = Area.objects.all()
        if tecnologia_id:
            areas = areas.filter(id=tecnologia_id)
        
        resultados = []
        
        for area in areas:
            # Agregar dados das linhas desta área
            agregado = RegistroProducaoTurno.objects.filter(
                linha__area=area,
                data__gte=data_inicio,
                data__lte=data_fim
            ).aggregate(
                total_producao_unidades=Sum('producao_unidades'),
                total_producao_toneladas=Sum('producao_toneladas'),
                oee_medio=Avg('oee'),
                eficiencia_media=Avg('eficiencia'),
            )
            
            # Contar linhas e OPs
            total_linhas = LinhaProducao.objects.filter(area=area, ativa=True).count()
            total_ops_ativas = OrdemProducao.objects.filter(
                linha__area=area,
                status__in=['PRODUZINDO', 'PAUSADA']
            ).count()
            
            resultados.append({
                'tecnologia_nome': area.nome,
                'total_producao_unidades': agregado['total_producao_unidades'] or 0,
                'total_producao_toneladas': agregado['total_producao_toneladas'] or 0,
                'oee_medio': agregado['oee_medio'] or 0,
                'eficiencia_media': agregado['eficiencia_media'] or 0,
                'total_linhas': total_linhas,
                'total_ops_ativas': total_ops_ativas,
            })
        
        serializer = ProducaoTecnologiaSerializer(resultados, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def linha(self, request):
        """
        Retorna métricas agregadas por linha
        
        Query params:
        - data_inicio: YYYY-MM-DD (opcional)
        - data_fim: YYYY-MM-DD (opcional)
        - linha_id: ID da linha (opcional)
        """
        data_fim = request.query_params.get('data_fim', datetime.now().date())
        data_inicio = request.query_params.get('data_inicio', datetime.now().date() - timedelta(days=30))
        linha_id = request.query_params.get('linha_id')
        
        if isinstance(data_fim, str):
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        if isinstance(data_inicio, str):
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        
        # Filtrar linhas
        linhas = LinhaProducao.objects.filter(ativa=True)
        if linha_id:
            linhas = linhas.filter(id=linha_id)
        
        resultados = []
        
        for linha in linhas:
            # Agregar dados desta linha
            agregado = RegistroProducaoTurno.objects.filter(
                linha=linha,
                data__gte=data_inicio,
                data__lte=data_fim
            ).aggregate(
                total_producao_unidades=Sum('producao_unidades'),
                total_producao_toneladas=Sum('producao_toneladas'),
                oee_medio=Avg('oee'),
                eficiencia_media=Avg('eficiencia'),
                total_turnos=Count('id'),
            )
            
            # OPs ativas
            ops_ativas = OrdemProducao.objects.filter(
                linha=linha,
                status__in=['PRODUZINDO', 'PAUSADA']
            ).values_list('codigo', flat=True)
            
            resultados.append({
                'linha_codigo': linha.codigo,
                'linha_nome': linha.nome,
                'total_producao_unidades': agregado['total_producao_unidades'] or 0,
                'total_producao_toneladas': agregado['total_producao_toneladas'] or 0,
                'oee_medio': agregado['oee_medio'] or 0,
                'eficiencia_media': agregado['eficiencia_media'] or 0,
                'total_turnos': agregado['total_turnos'] or 0,
                'ops_ativas': list(ops_ativas),
            })
        
        serializer = ProducaoLinhaSerializer(resultados, many=True)
        return Response(serializer.data)
