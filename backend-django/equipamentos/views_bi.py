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
    
    @action(detail=False, methods=['post'])
    def auto_create_or_get(self, request):
        """
        Auto-cria ou retorna OP existente
        
        Usado pelo Flask quando detecta nova OP nos dados do coletor.
        Se a OP já existe, retorna. Se não existe, cria automaticamente.
        
        Payload:
        {
            "codigo_op": "OP-123",
            "codigo_linha": "L1",
            "codigo_sku": "SKU-001",
            "formato_gramas": 2200.0,
            "descricao": "Produto Especial",
            "meta_producao": 5000
        }
        """
        from equipamentos.models import Produto
        from django.utils import timezone
        
        codigo_op = request.data.get('codigo_op')
        codigo_linha = request.data.get('codigo_linha')
        codigo_sku = request.data.get('codigo_sku')
        formato_gramas = request.data.get('formato_gramas', 0)
        descricao = request.data.get('descricao', '')
        meta_producao = request.data.get('meta_producao', 0)
        
        if not codigo_op or not codigo_linha:
            return Response(
                {'error': 'codigo_op e codigo_linha são obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar se OP já existe
        try:
            op = OrdemProducao.objects.get(codigo=codigo_op)
            return Response({
                'created': False,
                'op': OrdemProducaoSerializer(op).data
            })
        except OrdemProducao.DoesNotExist:
            pass
        
        # Buscar linha
        try:
            linha = LinhaProducao.objects.get(codigo=codigo_linha)
        except LinhaProducao.DoesNotExist:
            return Response(
                {'error': f'Linha {codigo_linha} não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Buscar ou criar produto
        produto = None
        if codigo_sku:
            produto_defaults = {
                'peso_unitario': formato_gramas or 0,
                'ativo': True
            }
            if descricao:
                produto_defaults['descricao'] = descricao
            else:
                produto_defaults['descricao'] = f'Produto {codigo_sku}'
                
            produto, _ = Produto.objects.get_or_create(
                codigo=codigo_sku,
                defaults=produto_defaults
            )
        
        # Definir metas (prioridade: payload > linha > default)
        meta_total = meta_producao if meta_producao and float(meta_producao) > 0 else 10000
        meta_turno = linha.meta_producao_turno if linha.meta_producao_turno else (meta_total / 3) # Estima turno como 1/3 do total se não tiver meta
        
        # Criar OP
        op = OrdemProducao.objects.create(
            codigo=codigo_op,
            linha=linha,
            produto=produto,
            meta_total=meta_total,
            meta_turno=meta_turno,
            formato_gramas=formato_gramas or (produto.peso_unitario if produto else 0),
            status='PRODUZINDO',
            data_planejada_inicio=timezone.now(),
            data_inicio_real=timezone.now(),
            descricao=descricao if descricao else f'OP auto-criada em {timezone.now().date()}'
        )
        
        return Response({
            'created': True,
            'op': OrdemProducaoSerializer(op).data
        }, status=status.HTTP_201_CREATED)



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
    - POST /api/bi/consolidar-turno/ - Consolidação reativa de turno
    """
    
    @action(detail=False, methods=['post'])
    def consolidar_turno(self, request):
        """
        Consolida um turno específico IMEDIATAMENTE (reativo)
        Chamado pelo Flask quando detecta mudança de turno
        
        Payload:
        {
            "linha_codigo": "L1",
            "turno_codigo": "A",
            "data": "2025-11-27"
        }
        """
        from influxdb import InfluxDBClient
        from equipamentos.models import TurnoProducao, Produto
        
        linha_codigo = request.data.get('linha_codigo')
        turno_codigo = request.data.get('turno_codigo')
        data_str = request.data.get('data')
        
        if not linha_codigo or not turno_codigo or not data_str:
            return Response(
                {'error': 'linha_codigo, turno_codigo e data são obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            data = datetime.strptime(data_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'data inválida (use YYYY-MM-DD)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Buscar linha e turno
        try:
            linha = LinhaProducao.objects.get(codigo=linha_codigo)
            turno = TurnoProducao.objects.get(codigo=turno_codigo)
        except (LinhaProducao.DoesNotExist, TurnoProducao.DoesNotExist) as e:
            return Response(
                {'error': f'Linha ou turno não encontrado: {e}'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Buscar OP ativa para esta linha
        op = OrdemProducao.objects.filter(
            linha=linha,
            status__in=['PRODUZINDO', 'PAUSADA']
        ).first()
        
        if not op:
            return Response(
                {'message': 'Nenhuma OP ativa encontrada para esta linha'},
                status=status.HTTP_200_OK
            )
        
        # Verificar se já foi consolidado
        if RegistroProducaoTurno.objects.filter(
            ordem_producao=op,
            data=data,
            turno=turno
        ).exists():
            return Response(
                {'message': 'Turno já consolidado'},
                status=status.HTTP_200_OK
            )
        
        # Conectar ao InfluxDB e buscar dados
        try:
            influx_client = InfluxDBClient(
                host='127.0.0.1',
                port=8086,
                database='industrial_db',
                username='admin',
                password='admin123'
            )
            
            # Calcular intervalo do turno
            inicio_turno = datetime.combine(data, turno.hora_inicio)
            if turno.hora_fim < turno.hora_inicio:
                fim_turno = datetime.combine(data + timedelta(days=1), turno.hora_fim)
            else:
                fim_turno = datetime.combine(data, turno.hora_fim)
            
            # Query para buscar dados
            query = f"""
            SELECT 
                SUM(contagem_saida) as producao_unidades,
                SUM(descarte) as refugo_unidades
            FROM producao
            WHERE 
                linha_codigo = '{linha.codigo}'
                AND ordem_producao = '{op.codigo}'
                AND time >= '{inicio_turno.isoformat()}Z'
                AND time < '{fim_turno.isoformat()}Z'
            """
            
            result = influx_client.query(query)
            points = list(result.get_points())
            
            if points and points[0].get('producao_unidades'):
                dados = points[0]
                producao_un = int(dados.get('producao_unidades') or 0)
                refugo_un = int(dados.get('refugo_unidades') or 0)
                
                # Calcular toneladas
                producao_ton = (producao_un * op.formato_gramas) / 1000000.0
                refugo_kg = (refugo_un * op.formato_gramas) / 1000.0
                
                # Criar registro
                registro = RegistroProducaoTurno.objects.create(
                    ordem_producao=op,
                    linha=linha,
                    produto=op.produto,
                    data=data,
                    turno=turno,
                    producao_unidades=producao_un,
                    producao_toneladas=producao_ton,
                    refugo_unidades=refugo_un,
                    refugo_kg=refugo_kg,
                    tempo_programado_min=turno.duracao_horas * 60,
                    tempo_disponivel_min=turno.duracao_horas * 60,
                    tempo_producao_min=turno.duracao_horas * 60 * 0.8,
                    tempo_parado_min=turno.duracao_horas * 60 * 0.1,
                    tempo_setup_min=turno.duracao_horas * 60 * 0.1,
                    velocidade_planejada=linha.velocidade_planejada or 0,
                    observacoes='Consolidação reativa (mudança de turno detectada)'
                )
                
                influx_client.close()
                
                return Response({
                    'message': 'Turno consolidado com sucesso',
                    'consolidado': {
                        'op': op.codigo,
                        'linha': linha.codigo,
                        'turno': turno.codigo,
                        'producao_unidades': producao_un,
                        'oee': registro.oee
                    }
                })
            else:
                influx_client.close()
                return Response(
                    {'message': 'Sem dados de produção para este turno'},
                    status=status.HTTP_200_OK
                )
                
        except Exception as e:
            return Response(
                {'error': f'Erro ao consolidar: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
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
