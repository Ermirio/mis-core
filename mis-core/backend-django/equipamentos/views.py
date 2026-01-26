from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.db.models import Q, Sum, Avg, Max, Min, Count, F
from django.utils import timezone
from datetime import datetime, timedelta
import pytz
import logging
import sys
import os
from rest_framework.pagination import PageNumberPagination

# Paginação flexível para aceitar page_size via query param
class FlexiblePageNumberPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 10000
from .models import (
    LinhaProducao, Equipamento, Sensor, MetricaProducao, 
    Defeito, ConexaoOPC, TagColeta,
    TurnoProducao, CalendarioProducao, EventoEstadoEquipamento, EventoParada,
    Produto, HistoricoSKU, StrategicInitiative, RegistroProducaoTurno
)
from .serializers import (
    LinhaProducaoSerializer, EquipamentoSerializer, SensorSerializer,
    MetricaProducaoSerializer, DefeitoSerializer, ConexaoOPCSerializer,
    TagColetaSerializer, EquipamentoColetorSerializer, MetricaConsolidadaInputSerializer,
    TurnoProducaoSerializer, CalendarioProducaoSerializer,
    EventoEstadoEquipamentoSerializer, EventoEstadoCreateSerializer, EventoParadaSerializer,
    StrategicInitiativeSerializer
)
from .influx_helpers import get_influx_client
from .projections import calculate_projection

class LinhaProducaoViewSet(viewsets.ModelViewSet):
    queryset = LinhaProducao.objects.all()
    serializer_class = LinhaProducaoSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        codigo = self.request.query_params.get('codigo')
        if codigo:
            queryset = queryset.filter(codigo=codigo)
        return queryset

    @action(detail=False, methods=['get'])
    def ativas(self, request):
        """Retorna apenas linhas ativas"""
        ativas = self.queryset.filter(ativa=True)
        serializer = self.get_serializer(ativas, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def projection(self, request, pk=None):
        """Retorna projeção de produção para a linha"""
        projection = calculate_projection(pk)
        if not projection:
            return Response({'error': 'Linha não encontrada ou erro ao calcular'}, status=status.HTTP_404_NOT_FOUND)
        return Response(projection)

    @action(detail=True, methods=['get'])
    def active_op(self, request, pk=None):
        """Retorna a Ordem de Produção (HistóricoSKU) ativa na linha"""
        try:
            linha = self.get_object()
            historico = HistoricoSKU.objects.filter(
                linha=linha,
                data_fim__isnull=True
            ).order_by('-data_inicio').first()
            
            if not historico:
                # Tenta pegar o último fechado se não tiver aberto
                historico = HistoricoSKU.objects.filter(linha=linha).order_by('-data_inicio').first()
                
            if historico:
                 return Response({
                     'ordem_producao': historico.ordem_producao,
                     'sku_codigo': historico.produto.codigo,
                     'descricao': historico.produto.descricao,
                     'meta': historico.meta_producao
                 })
            return Response({'error': 'Nenhuma OP encontrada avu'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class EquipamentoViewSet(viewsets.ModelViewSet):
    queryset = Equipamento.objects.select_related('linha').prefetch_related('sensores')
    serializer_class = EquipamentoSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        linha = self.request.query_params.get('linha')
        if linha:
            queryset = queryset.filter(linha_id=linha)
        return queryset
    
    @action(detail=False, methods=['post'])
    def sync_metadata(self, request):
        """
        Sincroniza metadados (OP, SKU, Formato) vindos do Coletor.
        Torna o Django a fonte da verdade atualizada pelo chão de fábrica.
        """
        try:
            data = request.data
            equipamento_codigo = data.get('equipamento_codigo')
            
            if not equipamento_codigo:
                return Response({'error': 'equipamento_codigo é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)
                
            try:
                equipamento = Equipamento.objects.get(codigo=equipamento_codigo)
            except Equipamento.DoesNotExist:
                return Response({'error': f'Equipamento {equipamento_codigo} não encontrado'}, status=status.HTTP_404_NOT_FOUND)
            
            updates = []
            
            # 1. Atualizar Formato (Peso da Peça)
            formato = data.get('formato')
            if formato and float(formato) > 0:
                # Atualiza tags de contagem (saída/entrada) com o novo formato
                tags_afetadas = equipamento.tags_coleta.filter(
                    nome_metrica__icontains='contagem',
                    ativa=True
                )
                for tag in tags_afetadas:
                    if float(tag.formato or 0) != float(formato):
                        tag.formato = formato
                        tag.save()
                        updates.append(f"Formato atualizado para {formato}g na tag {tag.nome_metrica}")
            
            # 2. Atualizar OP e SKU (Histórico)
            op_codigo = data.get('op_codigo')
            sku_codigo = data.get('sku_codigo')
            meta_producao = data.get('meta_producao')
            
            if op_codigo and sku_codigo:
                # Verifica se precisa criar novo histórico
                # Lógica: Se a OP mudou em relação ao último histórico ativo
                ultimo_historico = HistoricoSKU.objects.filter(
                    linha=equipamento.linha
                ).order_by('-data_inicio').first()
                
                criar_novo = False
                if not ultimo_historico:
                    criar_novo = True
                elif str(ultimo_historico.ordem_producao) != str(op_codigo):
                    criar_novo = True
                    # Fecha o anterior
                    if not ultimo_historico.data_fim:
                        ultimo_historico.data_fim = timezone.now()
                        ultimo_historico.save()
                
                if criar_novo:
                    # Busca ou cria o Produto (SKU)
                    produto, _ = Produto.objects.get_or_create(
                        codigo=sku_codigo,
                        defaults={'descricao': data.get('descricao', f'SKU {sku_codigo}'), 'peso_unitario': 0}
                    )
                    
                    # Cria novo histórico
                    HistoricoSKU.objects.create(
                        linha=equipamento.linha,
                        produto=produto,
                        ordem_producao=op_codigo,
                        data_inicio=timezone.now(),
                        meta_producao=int(meta_producao) if meta_producao else 0
                    )
                    updates.append(f"Novo histórico criado: OP {op_codigo}, SKU {sku_codigo}, Meta {meta_producao}")
                elif meta_producao and ultimo_historico:
                     # Se não criou novo, mas tem meta e é a mesma OP, atualiza a meta
                     if ultimo_historico.meta_producao != int(meta_producao):
                         ultimo_historico.meta_producao = int(meta_producao)
                         ultimo_historico.save()
                         updates.append(f"Meta atualizada para {meta_producao} na OP {op_codigo}")
            
            return Response({
                'status': 'success',
                'message': 'Metadados sincronizados',
                'updates': updates
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            
        # Filtro por turno com suporte a "atual"
        turno = self.request.query_params.get('turno')
        if turno:
            if turno == 'atual':
                # Busca turno em andamento agora
                try:
                    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    from agregador import agregador
                    turno_atual = agregador.obter_turno_atual()
                    if turno_atual:
                        queryset = queryset.filter(turno=turno_atual.nome)
                except ImportError:
                    pass
            elif turno != 'todos':
                queryset = queryset.filter(turno=turno)
        
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
    
    pagination_class = FlexiblePageNumberPagination
    
    def get_queryset(self):
        """Permite filtrar por equipamento, linha e período"""
        queryset = super().get_queryset()
        
        equipamento_id = self.request.query_params.get('equipamento_id')
        if equipamento_id:
            queryset = queryset.filter(equipamento_id=equipamento_id)
        
        equipamento_codigo = self.request.query_params.get('equipamento_codigo')
        if equipamento_codigo:
            queryset = queryset.filter(equipamento__codigo=equipamento_codigo)
        
        # Filtro por linha (via equipamento -> linha)
        linha_id = self.request.query_params.get('linha_id')
        if linha_id:
            queryset = queryset.filter(equipamento__linha_id=linha_id)
        
        # Filtro por período (suporta inicio/fim e data_inicio/data_fim)
        inicio = self.request.query_params.get('inicio') or self.request.query_params.get('data_inicio')
        if inicio:
            # Filtra eventos que começaram APÓS a data OU que ainda estavam abertos (fim >= inicio ou fim nulo)
            queryset = queryset.filter(
                Q(inicio__gte=inicio) | 
                (Q(inicio__lt=inicio) & (Q(fim__gte=inicio) | Q(fim__isnull=True)))
            )
        
        fim = self.request.query_params.get('fim') or self.request.query_params.get('data_fim')
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
            'tags_coleta'
        ).order_by('linha__codigo', 'ordem_na_linha')
        
        # Filtra apenas tags ativas
        for eq in equipamentos:
            eq.tags_coleta_ativas = eq.tags_coleta.filter(ativa=True)
        
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



from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import HttpResponse
from tablib import Dataset
from .resources import EquipamentoResource


@api_view(['GET'])
def exportar_excel(request):
    resource = EquipamentoResource()
    dataset = resource.export()
    response = HttpResponse(
        dataset.xlsx,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="equipamentos.xlsx"'
    return response


@api_view(['POST'])
def importar_excel(request):
    if 'file' not in request.FILES:
        return Response({'erro': 'Nenhum arquivo enviado'}, status=400)

    excel_file = request.FILES['file']
    dataset = Dataset().load(excel_file.read(), format='xlsx')

    resource = EquipamentoResource()
    resultado = resource.import_data(dataset, dry_run=False)

    return Response({
        'status': 'importado',
        'erros': resultado.has_errors()
    })


@api_view(['GET'])
def metricas_fabrica_consolidadas(request):
    """
    Retorna métricas consolidadas da fábrica em TEMPO REAL
    
    ARQUITETURA:
    - Tonelagem/Vazão: Busca direto do InfluxDB (tempo real, sem lag)
    - OEE/Disponibilidade/Performance/Qualidade: Busca do MySQL (consolidado do último turno fechado)
    
    Isso separa métricas em tempo real (InfluxDB) de métricas consolidadas (MySQL)
    """
    try:
        from .influx_helpers import get_realtime_metrics
        from .turno_helpers import obter_turno_atual, calcular_inicio_turno
        
        # Busca todas as linhas ativas
        linhas = LinhaProducao.objects.filter(ativa=True)
        
        resultados = []
        
        for linha in linhas:
            # 1. Identificar equipamento final da linha (para contagem)
            # Busca todos os equipamentos da linha ordenados
            equipamentos_linha_asc = Equipamento.objects.filter(
                linha=linha
            ).order_by('ordem_na_linha')
            
            # Busca Equipamento Final Efetivo (último com tags ativas)
            equipamento_final = equipamentos_linha_asc.filter(tags_coleta__ativa=True).distinct().last()
            
            # Busca Formato
            # ESTRATÉGIA: Prioriza o formato do equipamento final. Se não tiver, busca o primeiro disponível.
            formato = None
            
            # 1. Tenta pegar do final
            if equipamento_final:
                tag_formato_final = equipamento_final.tags_coleta.filter(nome_metrica='formato').first()
                if tag_formato_final and tag_formato_final.formato and float(tag_formato_final.formato) > 0:
                    formato = float(tag_formato_final.formato)
            
            # 2. Fallback: Busca na sequência (1º que encontrar)
            if not formato:
                for eq in equipamentos_linha_asc:
                    tag_formato = eq.tags_coleta.filter(formato__gt=0).first()
                    if tag_formato:
                        formato = float(tag_formato.formato)
                        break
            
            # Dados base da linha
            dados_linha = {
                'linha_id': linha.id,
                'linha_codigo': linha.codigo,
                'linha_nome': linha.nome,
                'status': 'Online' if linha.ativa else 'Offline',
            }
            
            # 2. TEMPO REAL: Buscar tonelagem e vazão do InfluxDB
            toneladas = 0.0
            vazao = 0.0
            contagem_saida = 0
            
            if equipamento_final and formato:
                try:
                    # Obter turno atual e início
                    turno_atual = obter_turno_atual()
                    inicio_turno = calcular_inicio_turno(turno_atual)
                    
                    # Buscar métricas em tempo real do InfluxDB
                    metricas_rt = get_realtime_metrics(
                        equipamento_codigo=equipamento_final.codigo,
                        formato_gramas=formato,
                        inicio_turno=inicio_turno
                    )
                    
                    toneladas = metricas_rt['toneladas_turno']
                    vazao = metricas_rt['vazao_ton_hora']
                    contagem_saida = int(metricas_rt['contagem_atual'])
                    
                except Exception as e:
                    # Log erro mas continua (fallback para 0.0)
                    logging.error(f"Erro ao buscar métricas tempo real para {linha.nome}: {e}")
            
            # 3. CONSOLIDADO: Buscar OEE do MySQL (último turno fechado)
            metrica_consolidada = MetricaProducao.objects.filter(
                linha=linha,
                equipamento__isnull=True,
                periodo='TURNO'
            ).order_by('-data_hora').first()
            
            # 4. Montar resposta combinando tempo real + consolidado
            dados_linha.update({
                # TEMPO REAL (InfluxDB)
                'toneladas_produzidas': toneladas,
                'vazao_real_ton_hora': vazao,
                'formato_gramas': formato,
                'contagem_saida': contagem_saida,
                # CONSOLIDADO (MySQL - último turno fechado)
                'oee': metrica_consolidada.oee if metrica_consolidada else 0.0,
                'disponibilidade': metrica_consolidada.disponibilidade if metrica_consolidada else 0.0,
                'performance': metrica_consolidada.performance if metrica_consolidada else 0.0,
                'qualidade': metrica_consolidada.qualidade if metrica_consolidada else 0.0,
                'descarte': metrica_consolidada.descarte if metrica_consolidada else 0,
                'percentual_descarte': metrica_consolidada.percentual_descarte if metrica_consolidada else 0.0,
                'velocidade_real': metrica_consolidada.velocidade_real if metrica_consolidada else 0.0,
                'data_hora': metrica_consolidada.data_hora if metrica_consolidada else None
            })
            
            # 5. SKU e Descrição: Buscar do InfluxDB
            try:
                # Busca SKU e OP em tempo real do InfluxDB
                sku_realtime = None
                op_realtime = None
                desc_realtime = None
                meta_realtime = None
                toneladas_op = 0.0
                
                try:
                    # Itera sobre equipamentos para encontrar tags
                    for eq in equipamentos_linha_asc:
                        try:
                            client = get_influx_client()
                            
                            # ESTRATÉGIA ROBUSTA PARA INFLUXDB 1.8:
                            # 1. Busca o timestamp do último ponto (usando um field que sempre existe)
                            # 2. Busca as tags específicas desse timestamp
                            
                            # Passo 1: Pega último timestamp
                            # Usamos last("contagem_saida") pois é um field garantido
                            query_time = f"""
                                SELECT last("contagem_saida") 
                                FROM "production" 
                                WHERE "equipment" = '{eq.codigo}'
                            """
                            result_time = client.query(query_time)
                            points_time = list(result_time.get_points())
                            
                            if points_time:
                                last_time = points_time[0]['time']
                                
                                # Passo 2: Pega tags e fields desse timestamp exato
                                # O GROUP BY * força o retorno das tags na estrutura de séries
                                query_details = f"""
                                    SELECT * 
                                    FROM "production" 
                                    WHERE "equipment" = '{eq.codigo}' 
                                    AND time = '{last_time}' 
                                    GROUP BY *
                                """
                                result_details = client.query(query_details)
                                
                                # Extrai dados da série retornada
                                series_list = list(result_details.raw.get('series', []))
                                if series_list:
                                    # Pega a primeira série (deve ser única para este timestamp/equipamento)
                                    serie = series_list[0]
                                    tags = serie.get('tags', {})
                                    values = serie.get('values', [[]])[0]
                                    columns = serie.get('columns', [])
                                    
                                    # Extrai TAGS (Indexadas)
                                    if tags.get('order_id'):
                                        op_realtime = tags.get('order_id')
                                    if tags.get('sku'):
                                        sku_realtime = tags.get('sku')
                                    
                                    # Extrai FIELDS (Não indexados)
                                    data_dict = dict(zip(columns, values))
                                    
                                    if data_dict.get('descricao'):
                                        desc_realtime = data_dict.get('descricao')

                                    if data_dict.get('planejado_op'):
                                        try:
                                            meta_realtime = float(data_dict.get('planejado_op'))
                                        except:
                                            pass
                                    
                                    # Se achou SKU, considera que achou a fonte de dados principal
                                    if sku_realtime:
                                        # Calcular produção da OP
                                        if op_realtime and formato:
                                            from .influx_helpers import get_production_by_op
                                            prod_op = get_production_by_op(
                                                equipamento_codigo=eq.codigo,
                                                ordem_producao=op_realtime,
                                                formato_gramas=formato
                                            )
                                            toneladas_op = prod_op['toneladas_op']
                                        break
                                        
                        except Exception as e:
                            logging.error(f"Erro ao buscar dados realtime do equipamento {eq.codigo}: {e}")
                            continue

                except Exception as e:
                    logging.error(f"Erro geral ao buscar dados realtime do Influx: {e}")

                # Se encontrou no InfluxDB, usa. Senão, busca no histórico SQL.
                if sku_realtime:
                    dados_linha['sku_codigo'] = str(sku_realtime)
                    
                    # Remove .0 se for float
                    op_str = str(op_realtime)
                    if op_str.endswith('.0'):
                        op_str = op_str[:-2]
                    dados_linha['ordem_producao'] = op_str
                    dados_linha['toneladas_produzidas_op'] = toneladas_op
                    
                    # Descrição: Realtime > Histórico > '-'
                    if desc_realtime:
                        dados_linha['sku_descricao'] = str(desc_realtime)
                    else:
                        try:
                            if op_realtime:
                                historico_associado = HistoricoSKU.objects.filter(ordem_producao=op_realtime).first()
                                if historico_associado:
                                    dados_linha['sku_descricao'] = historico_associado.produto.descricao
                                else:
                                    dados_linha['sku_descricao'] = 'Produto não cadastrado'
                            else:
                                dados_linha['sku_descricao'] = '-'
                        except:
                            dados_linha['sku_descricao'] = '-'
                    
                    # Meta: Realtime > Histórico > 0
                    if meta_realtime:
                        dados_linha['meta_producao'] = meta_realtime
                    elif op_realtime:
                        try:
                             historico_associado = HistoricoSKU.objects.filter(ordem_producao=op_realtime).first()
                             if historico_associado:
                                 dados_linha['meta_producao'] = float(historico_associado.meta_producao)
                             else:
                                 dados_linha['meta_producao'] = 0.0
                        except:
                             dados_linha['meta_producao'] = 0.0

                    # ===== PRODUÇÃO ACUMULADA (SIMPLIFICADO) =====
                    # Lê diretamente os valores calculados pelo Flask (ProductionCounter)
                    # O Flask agora gerencia o estado, resume de OPs antigas e reseta OPs novas.
                    
                    producao_op_atual = toneladas_op
                    producao_sku_atual = 0.0

                    dados_linha['toneladas_produzidas_op'] = round(producao_op_atual, 3)
                    dados_linha['toneladas_produzidas_sku'] = round(producao_sku_atual, 3)
                    
                    # Atualiza histórico no MySQL se tiver OP e produção
                    if producao_op_atual > 0 and op_realtime:
                        try:
                            historico_op, created = HistoricoSKU.objects.get_or_create(
                                ordem_producao=str(op_realtime),
                                linha=linha,
                                defaults={
                                    'produto_id': (Produto.objects.filter(codigo=sku_realtime).first().id if (sku_realtime and Produto.objects.filter(codigo=sku_realtime).exists()) else None),
                                    'data_inicio': timezone.now(),
                                    'meta_producao': int(dados_linha.get('meta_producao', 0))
                                }
                            )
                            # Só atualiza se mudou significativamente
                            from decimal import Decimal
                            prod_atual_dec = Decimal(str(producao_op_atual))
                            if abs(historico_op.producao_realizada - prod_atual_dec) > Decimal('0.001'):
                                historico_op.producao_realizada = prod_atual_dec
                                historico_op.save()
                        except Exception as e:
                            logging.error(f"Erro ao atualizar histórico: {e}")
                    
                    # Calcula diferença (Produzido OP - Meta)
                    dados_linha['diff_toneladas'] = producao_op_atual - dados_linha.get('meta_producao', 0.0)
                else:
                    # Fallback: Histórico SQL
                    agora = timezone.now()
                    historico_sku = HistoricoSKU.objects.filter(
                        linha=linha,
                        data_inicio__lte=agora
                    ).filter(
                        Q(data_fim__gte=agora) | Q(data_fim__isnull=True)
                    ).order_by('-data_inicio').first()
                    
                    if historico_sku:
                        dados_linha['sku_codigo'] = historico_sku.produto.codigo
                        dados_linha['sku_descricao'] = historico_sku.produto.descricao
                        dados_linha['ordem_producao'] = historico_sku.ordem_producao
                        dados_linha['meta_producao'] = historico_sku.meta_producao
                    else:
                        dados_linha['sku_codigo'] = '-'
                        dados_linha['sku_descricao'] = '-'
                        dados_linha['ordem_producao'] = '-'
            
            except Exception as e:
                logging.error(f"Erro ao buscar SKU/Descrição para {linha.nome}: {e}")
                dados_linha['sku_codigo'] = 'Erro'
                dados_linha['sku_descricao'] = '-'
            
            # 6. Projeção Inteligente
            try:
                projection = calculate_projection(linha.id, produzido_realtime=contagem_saida, formato_gramas=formato)
                if projection:
                    # Converter para toneladas se houver formato
                    if formato and formato > 0:
                        fator_ton = formato / 1_000_000.0
                        projection['produzido'] = round(projection['produzido'] * fator_ton, 3)
                        projection['meta'] = round(projection['meta'] * fator_ton, 3)
                        projection['meta_atual'] = round(projection['meta_atual'] * fator_ton, 3)
                        projection['projecao_realista'] = round(projection['projecao_realista'] * fator_ton, 3)
                        projection['projecao_otimista'] = round(projection['projecao_otimista'] * fator_ton, 3)
                    
                    dados_linha['projecao'] = projection
            except Exception as e:
                logging.error(f"Erro ao calcular projeção para {linha.nome}: {e}")

            # 7. Contagem de Equipamentos Online e Cálculo de OEE Realtime
            total_equipamentos = len(equipamentos_linha_asc)
            equipamentos_online = 0
            soma_performance = 0.0
            
            try:
                # Verifica status de cada equipamento (considera online se teve dados nos últimos 2 min)
                for eq in equipamentos_linha_asc:
                    query_status = f"""
                        SELECT last("contagem_saida"), last("velocidade_atual") 
                        FROM "producao" 
                        WHERE "equipamento_codigo" = '{eq.codigo}' 
                        AND time > now() - 2m
                    """
                    result_status = client.query(query_status)
                    points = list(result_status.get_points())
                    
                    if points:
                        equipamentos_online += 1
                        
                        # Cálculo de Performance para OEE (Igual Home.tsx)
                        velocidade_atual = float(points[0].get('last_1', 0.0)) # last_1 é velocidade_atual
                        velocidade_nominal = float(eq.velocidade_nominal) if eq.velocidade_nominal and eq.velocidade_nominal > 0 else 1.0
                        
                        performance = min(100.0, (velocidade_atual / velocidade_nominal) * 100.0)
                        soma_performance += performance
            except Exception as e:
                logging.error(f"Erro ao verificar status/OEE equipamentos: {e}")

            # OEE da Linha = Média da Performance dos Equipamentos Online
            oee_linha = 0.0
            if equipamentos_online > 0:
                oee_linha = soma_performance / equipamentos_online

            dados_linha['total_equipamentos'] = total_equipamentos
            dados_linha['equipamentos_online'] = equipamentos_online
            dados_linha['oee'] = round(oee_linha, 1) # Atualiza OEE com valor realtime

            resultados.append(dados_linha)
            
        return Response(resultados)
        

    except Exception as e:
        logging.error(f"Erro em metricas_fabrica_consolidadas: {e}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)







# ===== NOVOS ENDPOINTS PARA CONSOLIDAÇÃO =====

@api_view(['GET'])
def get_full_equipment_status(request):
    """
    Endpoint para obter o status completo de todos os equipamentos
    Retorna: estado numerico, velocidade, OEE, e outras metricas em tempo real
    """
    try:
        equipamentos = Equipamento.objects.all().select_related('linha')
        resultado = []
        
        for eq in equipamentos:
            ultima_metrica = MetricaProducao.objects.filter(
                equipamento=eq
            ).order_by('-data_hora').first()
            
            ultimo_evento = EventoEstadoEquipamento.objects.filter(
                equipamento=eq
            ).order_by('-inicio').first()
            
            resultado.append({
                'id': eq.id,
                'codigo': eq.codigo,
                'nome': eq.nome,
                'linha_id': eq.linha.id,
                'linha_nome': eq.linha.nome,
                'estado': ultimo_evento.estado if ultimo_evento else 0,
                'velocidade_nominal': eq.velocidade_nominal,
                'velocidade_atual': ultima_metrica.velocidade_atual if ultima_metrica else 0,
                'oee': ultima_metrica.oee if ultima_metrica else 0,
                'disponibilidade': ultima_metrica.disponibilidade if ultima_metrica else 0,
                'performance': ultima_metrica.performance if ultima_metrica else 0,
                'qualidade': ultima_metrica.qualidade if ultima_metrica else 0,
                'status': eq.status,
            })
        
        return Response(resultado)
    except Exception as e:
        logging.error(f"Erro ao buscar status dos equipamentos: {e}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def metricas_linha_consolidadas(request):
    """
    Endpoint GET /api/metricas_linha_consolidadas/
    
    Retorna produção consolidada de uma linha (soma de todos os equipamentos)
    
    Query params:
    - linha_id: ID da linha (obrigatório)
    - periodo: HORA, TURNO, DIA (default: TURNO)
    - turno: nome do turno ou 'atual' (opcional)
    - data_inicio: data inicial (opcional)
    - data_fim: data final (opcional)
    """
    try:
        linha_id = request.query_params.get('linha_id')
        if not linha_id:
            return Response({
                'error': 'linha_id é obrigatório'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        periodo = request.query_params.get('periodo', 'TURNO')
        turno = request.query_params.get('turno')
        data_inicio = request.query_params.get('data_inicio')
        data_fim = request.query_params.get('data_fim')
        
        # Busca métricas da linha
        queryset = MetricaProducao.objects.filter(
            linha_id=linha_id,
            equipamento__isnull=True,
            periodo=periodo
        )
        
        # Aplica filtros opcionais
        if turno:
            if turno == 'atual':
                try:
                    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    from agregador import agregador
                    turno_atual = agregador.obter_turno_atual()
                    if turno_atual:
                        queryset = queryset.filter(turno=turno_atual.nome)
                except ImportError:
                    pass
            else:
                queryset = queryset.filter(turno=turno)
        
        if data_inicio:
            queryset = queryset.filter(data_hora__gte=data_inicio)
        
        if data_fim:
            queryset = queryset.filter(data_hora__lte=data_fim)
        
        # Ordena por data decrescente
        metricas = queryset.order_by('-data_hora')
        
        serializer = MetricaProducaoSerializer(metricas, many=True)
        metricas_data = serializer.data
        
        # ADICIONAR: Buscar OP e Meta em tempo real do InfluxDB (como no Home)
        try:
            linha = LinhaProducao.objects.get(id=linha_id)
            equipamentos_linha = Equipamento.objects.filter(linha=linha, status='ATIVO').order_by('ordem_na_linha')
            
            # Busca OP e meta do InfluxDB
            sku_realtime = None
            op_realtime = None
            desc_realtime = None
            meta_realtime = None
            
            for eq in equipamentos_linha:
                try:
                    client = get_influx_client()
                    query_realtime = f"""
                        SELECT last("sku_codigo") as sku, last("ordem_producao") as op, last("descricao") as descricao_val, last("planejado_op") as meta_val
                        FROM "producao"
                        WHERE "equipamento_codigo" = '{eq.codigo}'
                    """
                    result = client.query(query_realtime)
                    points = list(result.get_points())
                    
                    if points:
                        if points[0].get('sku'):
                            sku_realtime = points[0].get('sku')
                        if points[0].get('op'):
                            op_realtime = points[0].get('op')
                        if points[0].get('descricao_val'):
                            desc_realtime = points[0].get('descricao_val')
                        if points[0].get('meta_val'):
                            meta_realtime = points[0].get('meta_val')
                        
                        if sku_realtime:
                            break
                except Exception as e:
                    logging.error(f"Erro ao buscar dados realtime do Influx para {eq.nome}: {e}")
                    continue
            
            # Se encontrou OP, busca meta do histórico
            if op_realtime:
                historico_associado = HistoricoSKU.objects.filter(ordem_producao=op_realtime).first()
                if historico_associado:
                    meta_realtime = historico_associado.meta_producao
            
            # Adiciona OP e meta real-time à primeira métrica (mais recente)
            if metricas_data and len(metricas_data) > 0:
                if op_realtime:
                    # Remove .0 se for float
                    try:
                        op_val = float(op_realtime)
                        if op_val.is_integer():
                            op_realtime = int(op_val)
                    except:
                        pass
                        
                    metricas_data[0]['ordem_producao'] = str(op_realtime)
                if meta_realtime:
                    try:
                        metricas_data[0]['meta_producao'] = float(meta_realtime)
                    except:
                        pass
                elif op_realtime:
                     historico_associado = HistoricoSKU.objects.filter(ordem_producao=op_realtime).first()
                     if historico_associado:
                         metricas_data[0]['meta_producao'] = historico_associado.meta_producao
                    
        except Exception as e:
            logging.error(f"Erro ao buscar OP/Meta em tempo real: {e}")
        
            # --- INJEÇÃO DE GIVE AWAY (On-the-fly) ---
            try:
                # 1. Identificar Equipamento de Pesagem (Enchedora > Balança > Ordem 1)
                eq_peso = equipamentos_linha.filter(tipo='ENCHEDORA').first()
                if not eq_peso:
                    eq_peso = equipamentos_linha.filter(tipo='BALANCA').first()
                if not eq_peso:
                    eq_peso = equipamentos_linha.filter(ordem_na_linha=1).first()
                
                if eq_peso:
                    # Preparar limites de data para Influx (UTC)
                    now_utc = timezone.now().astimezone(pytz.UTC)
                    start_dt = metricas.last().data_hora.astimezone(pytz.UTC) if metricas.exists() else (now_utc - timedelta(hours=24))
                    end_dt = metricas.first().data_hora.astimezone(pytz.UTC) + timedelta(hours=1) if metricas.exists() else now_utc
                    
                    time_start_str = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                    time_end_str = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

                    # Query Influx agrupada por Hora (compatível com granularidade base)
                    # Nota: Se o período for TURNO, ideal seria agrupar diferente, mas HORA funciona como base para lookup
                    client_influx = get_influx_client()
                    query_ga = f"""
                        SELECT MEAN("ultimo_peso") as "peso_medio", LAST("formato_gramas") as "peso_alvo"
                        FROM "production"
                        WHERE "equipment" = '{eq_peso.codigo}'
                        AND time >= '{time_start_str}' AND time <= '{time_end_str}'
                        GROUP BY time(1h)
                    """
                    result_ga = client_influx.query(query_ga)
                    points_ga = list(result_ga.get_points())
                    
                    # Indexar pontos Influx por timestamp (Hora cheia str) para lookup rápido
                    # Influx retorna strings como '2026-01-26T14:00:00Z'
                    ga_map = {}
                    for p in points_ga:
                        try:
                            # Chave: 'YYYY-MM-DDTHH'
                            ts_key = p['time'][:13] 
                            ga_map[ts_key] = p
                        except:
                            pass

                    # Cruzar dados e injetar nos itens
                    for item in metricas_data:
                        try:
                            # item['data_hora'] é string ISO do DRF
                            # Extrai YYYY-MM-DDTHH para match
                            ts_iso = item.get('data_hora', '')
                            if ts_iso:
                                # Normaliza para UTC se vier com offset (ex: -03:00)
                                # Mas o match simples de string pode falhar se fusos diferentes.
                                # DRF usually outputs ISO. Vamos tentar match flexível.
                                key_lookup = ts_iso[:13] 
                                
                                # Ajuste de Fuso: Influx é UTC (Z). Metricas pode ser Local (-03).
                                # Se Metrica for 14:00 Local, é 17:00 UTC.
                                # Precisamos converter item['data_hora'] para UTC para buscar no map.
                                dt_item = datetime.fromisoformat(ts_iso.replace('Z', '+00:00'))
                                if dt_item.tzinfo:
                                    dt_item_utc = dt_item.astimezone(pytz.UTC)
                                else:
                                    dt_item_utc = pytz.timezone('America/Sao_Paulo').localize(dt_item).astimezone(pytz.UTC)
                                
                                key_utc = dt_item_utc.strftime('%Y-%m-%dT%H')
                                
                                point = ga_map.get(key_utc)
                                if point and point.get('peso_medio') and point.get('peso_alvo'):
                                    peso_medio = point['peso_medio']
                                    peso_alvo = point['peso_alvo']
                                    producao = item.get('contagem_saida') or 0
                                    
                                    diff_g = peso_medio - peso_alvo
                                    giveaway_kg = (diff_g * producao) / 1000.0
                                    
                                    prod_ref_kg = (peso_alvo * producao) / 1000.0
                                    percent = (giveaway_kg / prod_ref_kg * 100) if prod_ref_kg > 0 else 0.0
                                    
                                    item['giveaway_kg'] = round(giveaway_kg, 3)
                                    item['giveaway_percent'] = round(percent, 2)
                                else:
                                    item['giveaway_kg'] = 0.0
                                    item['giveaway_percent'] = 0.0
                        except Exception as inner_e:
                             # Falha pontual de calculo não deve parar o loop
                             pass

            except Exception as e:
                logging.error(f"Erro ao injetar Give Away nas métricas consolidadas: {e}")
                # Não quebra a resposta principal
            
        return Response({
            'status': 'success',
            'total': metricas.count(),
            'periodo': periodo,
            'metricas': metricas_data
        })
    
    except Exception as e:
        logging.error(f"Erro ao buscar métricas consolidadas: {e}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def metricas_equipamento_consolidadas(request):
    """
    Endpoint GET /api/metricas_equipamento_consolidadas/
    
    Retorna produção de um equipamento específico
    
    Query params:
    - equipamento_id: ID do equipamento (obrigatório)
    - periodo: HORA, TURNO, DIA (default: TURNO)
    - turno: nome do turno ou 'atual' (opcional)
    - data_inicio: data inicial (opcional)
    - data_fim: data final (opcional)
    """
    try:
        equipamento_id = request.query_params.get('equipamento_id')
        if not equipamento_id:
            return Response({
                'error': 'equipamento_id é obrigatório'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        periodo = request.query_params.get('periodo', 'TURNO')
        turno = request.query_params.get('turno')
        data_inicio = request.query_params.get('data_inicio')
        data_fim = request.query_params.get('data_fim')
        
        # Busca métricas do equipamento
        queryset = MetricaProducao.objects.filter(
            equipamento_id=equipamento_id,
            periodo=periodo
        )
        
        # Aplica filtros opcionais
        if turno:
            if turno == 'atual':
                try:
                    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    from agregador import agregador
                    turno_atual = agregador.obter_turno_atual()
                    if turno_atual:
                        queryset = queryset.filter(turno=turno_atual.nome)
                except ImportError:
                    pass
            else:
                queryset = queryset.filter(turno=turno)
        
        if data_inicio:
            queryset = queryset.filter(data_hora__gte=data_inicio)
        
        if data_fim:
            queryset = queryset.filter(data_hora__lte=data_fim)
        
        # Ordena por data decrescente
        metricas = queryset.order_by('-data_hora')
        
        serializer = MetricaProducaoSerializer(metricas, many=True)
        
        return Response({
            'status': 'success',
            'total': metricas.count(),
            'periodo': periodo,
            'metricas': serializer.data
        })
    
    except Exception as e:
        logging.error(f"Erro ao buscar métricas do equipamento: {e}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== VIEWS DE ANÁLISE AVANÇADA =====

@api_view(['GET'])
def linha_analise_producao(request, linha_id):
    """
    Retorna dados de produção para análise gráfica
    
    Query params:
    - data_inicio: ISO datetime
    - data_fim: ISO datetime  
    - granularidade: 'hora' | 'turno' | 'dia' | 'semana'
    """
    try:
        linha = LinhaProducao.objects.get(id=linha_id)
        
        data_inicio = request.query_params.get('data_inicio')
        data_fim = request.query_params.get('data_fim')
        granularidade = request.query_params.get('granularidade', 'turno')
        
        # Define período padrão se não fornecido
        if not data_fim:
            data_fim = timezone.now()
        else:
            data_fim = timezone.datetime.fromisoformat(data_fim.replace('Z', '+00:00'))
            
        if not data_inicio:
            # Padrão: últimas 24h
            data_inicio = data_fim - timedelta(hours=24)
        else:
            data_inicio = timezone.datetime.fromisoformat(data_inicio.replace('Z', '+00:00'))
        
        # Mapeia granularidade para período do modelo
        periodo_map = {
            'hora': 'HORA',
            'turno': 'TURNO',
            'dia': 'DIA',
            'semana': 'DIA'  # Semana usa dados diários
        }
        periodo = periodo_map.get(granularidade, 'TURNO')
        
        # Busca métricas
        metricas = MetricaProducao.objects.filter(
            linha=linha,
            equipamento__isnull=True,
            periodo=periodo,
            data_hora__gte=data_inicio,
            data_hora__lte=data_fim
        ).order_by('data_hora')
        
        # Formata dados
        dados = []
        for m in metricas:
            # Calcula toneladas baseado na contagem e formato
            toneladas_real = (m.contagem_saida * linha.velocidade_planejada) / 1000000  # Conversão aproximada
            
            # Meta baseada na velocidade planejada e tempo
            if periodo == 'HORA':
                toneladas_meta = linha.meta_producao_hora
            elif periodo == 'TURNO':
                toneladas_meta = linha.meta_producao_turno
            else:
                toneladas_meta = linha.meta_producao_turno * 3  # Aproximação para dia (3 turnos)
            
            dados.append({
                'timestamp': m.data_hora.isoformat(),
                'toneladas_real': round(toneladas_real, 3),
                'toneladas_meta': toneladas_meta,
                'contagem': m.contagem_saida
            })
        
        return Response({
            'status': 'success',
            'linha_id': linha_id,
            'periodo': {
                'inicio': data_inicio.isoformat(),
                'fim': data_fim.isoformat(),
                'granularidade': granularidade
            },
            'dados': dados
        })
        
    except LinhaProducao.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Linha não encontrada'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logging.error(f"Erro em linha_analise_producao: {e}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def linha_analise_velocidade(request, linha_id):
    """
    Retorna dados de velocidade para análise gráfica
    """
    try:
        linha = LinhaProducao.objects.get(id=linha_id)
        
        data_inicio = request.query_params.get('data_inicio')
        data_fim = request.query_params.get('data_fim')
        granularidade = request.query_params.get('granularidade', 'turno')
        
        if not data_fim:
            data_fim = timezone.now()
        else:
            data_fim = timezone.datetime.fromisoformat(data_fim.replace('Z', '+00:00'))
            
        if not data_inicio:
            data_inicio = data_fim - timedelta(hours=24)
        else:
            data_inicio = timezone.datetime.fromisoformat(data_inicio.replace('Z', '+00:00'))
        
        periodo_map = {
            'hora': 'HORA',
            'turno': 'TURNO',
            'dia': 'DIA',
            'semana': 'DIA'
        }
        periodo = periodo_map.get(granularidade, 'TURNO')
        
        metricas = MetricaProducao.objects.filter(
            linha=linha,
            equipamento__isnull=True,
            periodo=periodo,
            data_hora__gte=data_inicio,
            data_hora__lte=data_fim
        ).order_by('data_hora')
        
        dados = []
        for m in metricas:
            velocidade_ideal = m.velocidade_planejada or linha.velocidade_planejada
            eficiencia = (m.velocidade_real / velocidade_ideal * 100) if velocidade_ideal > 0 else 0
            
            dados.append({
                'timestamp': m.data_hora.isoformat(),
                'velocidade_real': round(m.velocidade_real, 2),
                'velocidade_ideal': round(velocidade_ideal, 2),
                'eficiencia': round(eficiencia, 2)
            })
        
        return Response({
            'status': 'success',
            'linha_id': linha_id,
            'periodo': {
                'inicio': data_inicio.isoformat(),
                'fim': data_fim.isoformat(),
                'granularidade': granularidade
            },
            'dados': dados
        })
        
    except LinhaProducao.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Linha não encontrada'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logging.error(f"Erro em linha_analise_velocidade: {e}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def linha_analise_sku(request, linha_id):
    """
    Retorna produção agrupada por SKU
    """
    try:
        linha = LinhaProducao.objects.get(id=linha_id)
        
        data_inicio = request.query_params.get('data_inicio')
        data_fim = request.query_params.get('data_fim')
        
        if not data_fim:
            data_fim = timezone.now()
        else:
            data_fim = timezone.datetime.fromisoformat(data_fim.replace('Z', '+00:00'))
            
        if not data_inicio:
            data_inicio = data_fim - timedelta(hours=24)
        else:
            data_inicio = timezone.datetime.fromisoformat(data_inicio.replace('Z', '+00:00'))
        
        # Busca histórico de SKU no período
        historicos = HistoricoSKU.objects.filter(
            linha=linha,
            data_inicio__lte=data_fim
        ).filter(
            Q(data_fim__gte=data_inicio) | Q(data_fim__isnull=True)
        ).select_related('produto')
        
        # Agrupa produção por SKU
        dados_sku = {}
        
        for hist in historicos:
            sku_codigo = hist.produto.codigo
            sku_descricao = hist.produto.descricao
            
            # Busca métricas no período do SKU
            periodo_inicio = max(hist.data_inicio, data_inicio)
            periodo_fim = min(hist.data_fim or data_fim, data_fim)
            
            metricas = MetricaProducao.objects.filter(
                linha=linha,
                equipamento__isnull=True,
                data_hora__gte=periodo_inicio,
                data_hora__lte=periodo_fim
            )
            
            # Soma contagens
            total_saida = metricas.aggregate(Sum('contagem_saida'))['contagem_saida__sum'] or 0
            
            # Converte para toneladas (aproximação)
            toneladas = (total_saida * linha.velocidade_planejada) / 1000000
            
            if sku_codigo in dados_sku:
                dados_sku[sku_codigo]['toneladas'] += toneladas
            else:
                dados_sku[sku_codigo] = {
                    'sku_codigo': sku_codigo,
                    'sku_descricao': sku_descricao,
                    'toneladas': toneladas
                }
        
        # Calcula percentuais
        total_toneladas = sum(d['toneladas'] for d in dados_sku.values())
        
        dados = []
        for sku_data in dados_sku.values():
            percentual = (sku_data['toneladas'] / total_toneladas * 100) if total_toneladas > 0 else 0
            dados.append({
                **sku_data,
                'toneladas': round(sku_data['toneladas'], 3),
                'percentual': round(percentual, 2)
            })
        
        # Ordena por toneladas (maior primeiro)
        dados.sort(key=lambda x: x['toneladas'], reverse=True)
        
        return Response({
            'status': 'success',
            'linha_id': linha_id,
            'periodo': {
                'inicio': data_inicio.isoformat(),
                'fim': data_fim.isoformat()
            },
            'total_toneladas': round(total_toneladas, 3),
            'dados': dados
        })
        
    except LinhaProducao.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Linha não encontrada'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logging.error(f"Erro em linha_analise_sku: {e}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
        
        # Busca métricas da linha
        queryset = MetricaProducao.objects.filter(
            linha_id=linha_id,
            equipamento__isnull=True,
            periodo=periodo
        ).select_related('linha')
        
        # Aplica filtros de data
        if data_inicio:
            queryset = queryset.filter(data_hora__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data_hora__lte=data_fim)
        
        # Ordena e limita
        metricas = queryset.order_by('-data_hora')[:limit]
        
        # Serializa com OP e meta (já incluídos no serializer)
        serializer = MetricaProducaoSerializer(metricas, many=True)
        
        # Adiciona informações de SKU para cada métrica
        resultado = []
        for metrica_data in serializer.data:
            # Busca SKU do histórico para o período da métrica
            try:
                metrica_obj = MetricaProducao.objects.get(id=metrica_data['id'])
                historico_sku = HistoricoSKU.objects.filter(
                    linha_id=linha_id,
                    data_inicio__lte=metrica_obj.data_hora
                ).filter(
                    Q(data_fim__gte=metrica_obj.data_hora) | Q(data_fim__isnull=True)
                ).select_related('produto').first()
                
                if historico_sku:
                    metrica_data['sku_codigo'] = historico_sku.produto.codigo
                    metrica_data['sku_descricao'] = historico_sku.produto.descricao
                else:
                    metrica_data['sku_codigo'] = None
                    metrica_data['sku_descricao'] = None
                    
            except Exception as e:
                logging.error(f"Erro ao buscar SKU para métrica {metrica_data['id']}: {e}")
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
        logging.error(f"Erro ao buscar histórico detalhado: {e}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EventoParadaViewSet(viewsets.ModelViewSet):
    """
    API para Gestão de Eventos de Parada (Estratégico)
    Permite criar, listar e fechar eventos de parada.
    """
    queryset = EventoParada.objects.all().order_by('-inicio')
    serializer_class = EventoParadaSerializer
    
    @action(detail=False, methods=['get'])
    def abertos(self, request):
        """Retorna eventos abertos (sem data fim)"""
        maquina = request.query_params.get('maquina')
        queryset = self.queryset.filter(fim__isnull=True)
        
        if maquina:
            queryset = queryset.filter(maquina=maquina)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
        
    @action(detail=False, methods=['get'])
    def por_turno(self, request):
        """Retorna eventos de um turno específico"""
        turno = request.query_params.get('turno')
        data = request.query_params.get('data') # YYYY-MM-DD
        
        queryset = self.queryset
        if turno:
            queryset = queryset.filter(turno=turno)
        if data:
            queryset = queryset.filter(inicio__date=data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class StrategicInitiativeViewSet(viewsets.ModelViewSet):
    """
    API para Gestão de Iniciativas Estratégicas
    Permite criar, listar, atualizar e deletar iniciativas de melhoria.
    """
    queryset = StrategicInitiative.objects.all().order_by('-criado_em')
    serializer_class = StrategicInitiativeSerializer
    
    @action(detail=False, methods=['get'])
    def ativas(self, request):
        """Retorna apenas iniciativas ativas"""
        queryset = self.queryset.filter(status='ATIVA')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def por_linha(self, request):
        """Retorna iniciativas de uma linha específica"""
        linha_id = request.query_params.get('linha_id')
        if linha_id:
            queryset = self.queryset.filter(linha_id=linha_id)
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return Response({'error': 'linha_id é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)


# --- ENDPOINTS DE IMPORTAR/EXPORTAR EXCEL ---

@api_view(['GET'])
def exportar_linhas_excel(request):
    """Exporta todas as linhas de produção para Excel."""
    try:
        from .excel_utils import ExcelExporter
        queryset = LinhaProducao.objects.all()
        return ExcelExporter.export_model_to_excel(
            queryset,
            LinhaProducao,
            filename="linhas_producao.xlsx"
        )
    except Exception as e:
        logging.error(f"Erro ao exportar linhas: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def importar_linhas_excel(request):
    """Importa linhas de produção de um arquivo Excel."""
    try:
        from .excel_utils import ExcelImporter
        if "file" not in request.FILES:
            return Response(
                {"error": "Nenhum arquivo fornecido"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES["file"]
        imported, errors = ExcelImporter.import_excel_to_model(
            file,
            LinhaProducao,
            skip_errors=True
        )
        
        return Response({
            "status": "success",
            "imported": imported,
            "errors": errors
        })
    except Exception as e:
        logging.error(f"Erro ao importar linhas: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def exportar_equipamentos_excel(request):
    """Exporta todos os equipamentos para Excel."""
    try:
        from .excel_utils import ExcelExporter
        queryset = Equipamento.objects.all()
        return ExcelExporter.export_model_to_excel(
            queryset,
            Equipamento,
            filename="equipamentos.xlsx"
        )
    except Exception as e:
        logging.error(f"Erro ao exportar equipamentos: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def importar_equipamentos_excel(request):
    """Importa equipamentos de um arquivo Excel."""
    try:
        from .excel_utils import ExcelImporter
        if "file" not in request.FILES:
            return Response(
                {"error": "Nenhum arquivo fornecido"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES["file"]
        imported, errors = ExcelImporter.import_excel_to_model(
            file,
            Equipamento,
            skip_errors=True
        )
        
        return Response({
            "status": "success",
            "imported": imported,
            "errors": errors
        })
    except Exception as e:
        logging.error(f"Erro ao importar equipamentos: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def exportar_produtos_excel(request):
    """Exporta todos os produtos para Excel."""
    try:
        from .excel_utils import ExcelExporter
        queryset = Produto.objects.all()
        return ExcelExporter.export_model_to_excel(
            queryset,
            Produto,
            filename="produtos.xlsx"
        )
    except Exception as e:
        logging.error(f"Erro ao exportar produtos: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def importar_produtos_excel(request):
    """Importa produtos de um arquivo Excel."""
    try:
        from .excel_utils import ExcelImporter
        if "file" not in request.FILES:
            return Response(
                {"error": "Nenhum arquivo fornecido"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES["file"]
        imported, errors = ExcelImporter.import_excel_to_model(
            file,
            Produto,
            skip_errors=True
        )
        
        return Response({
            "status": "success",
            "imported": imported,
            "errors": errors
        })
    except Exception as e:
        logging.error(f"Erro ao importar produtos: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def exportar_metricas_excel(request):
    """Exporta todas as métricas de produção para Excel."""
    try:
        from .excel_utils import ExcelExporter
        queryset = MetricaProducao.objects.all()
        return ExcelExporter.export_model_to_excel(
            queryset,
            MetricaProducao,
            filename="metricas_producao.xlsx"
        )
    except Exception as e:
        logging.error(f"Erro ao exportar métricas: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def importar_metricas_excel(request):
    """Importa métricas de produção de um arquivo Excel."""
    try:
        from .excel_utils import ExcelImporter
        if "file" not in request.FILES:
            return Response(
                {"error": "Nenhum arquivo fornecido"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES["file"]
        imported, errors = ExcelImporter.import_excel_to_model(
            file,
            MetricaProducao,
            skip_errors=True
        )
        
        return Response({
            "status": "success",
            "imported": imported,
            "errors": errors
        })
    except Exception as e:
        logging.error(f"Erro ao importar métricas: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def exportar_ordens_producao_excel(request):
    """Exporta todas as ordens de produção para Excel."""
    try:
        from .excel_utils import ExcelExporter
        from .models import OrdemProducao
        queryset = OrdemProducao.objects.all()
        return ExcelExporter.export_model_to_excel(
            queryset,
            OrdemProducao,
            filename="ordens_producao.xlsx"
        )
    except Exception as e:
        logging.error(f"Erro ao exportar ordens de produção: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def importar_ordens_producao_excel(request):
    """Importa ordens de produção de um arquivo Excel."""
    try:
        from .excel_utils import ExcelImporter
        from .models import OrdemProducao
        if "file" not in request.FILES:
            return Response(
                {"error": "Nenhum arquivo fornecido"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES["file"]
        imported, errors = ExcelImporter.import_excel_to_model(
            file,
            OrdemProducao,
            skip_errors=True
        )
        
        return Response({
            "status": "success",
            "imported": imported,
            "errors": errors
        })
    except Exception as e:
        logging.error(f"Erro ao importar ordens de produção: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ===== FACTORY PRODUCTION KPIS (NEW) =====

class FactoryProductionView(viewsets.ViewSet):
    """
    ViewSet para KPIs de Produção da Fábrica (Planejado vs Real vs Vazão Necessária)
    """
    
    @action(detail=False, methods=['get'])
    def throughput(self, request):
        """
        GET /api/production/window/throughput?granularity=shift|day|week|month
        
        API Contract:
        {
          "planned_tons": number,          // in Tons
          "actual_tons": number,           // in Tons
          "actual_tph": number,            // Tons/Hour
          "min_required_tph": number|null, // Tons/Hour or null if window closed
          "window": { "from": ISO, "to": ISO, "elapsedHours": number, "hoursRemaining": number, "tz": "America/Sao_Paulo" },
          "notes": [string]
        }
        """
        granularity = request.query_params.get('granularity', 'shift')
        notes = []
        
        # 1. Time Window & Metrics
        from .utils import get_window, calculate_time_metrics
        from .turno_helpers import obter_turno_atual, calcular_inicio_turno
        from .influx_helpers import get_realtime_metrics
        
        now = timezone.localtime(timezone.now())
        start_time, end_time = get_window(granularity, now)
        
        if not start_time or not end_time:
            return Response({
                'planned_tons': 0, 'actual_tons': 0, 'actual_tph': 0, 'min_required_tph': 0,
                'window': None, 'notes': ['no_shift_config']
            })

        elapsed_hours, hours_remaining = calculate_time_metrics(start_time, end_time, now)
        
        # 2. Planned Tons (CalendarioProducao)
        # Unit: KG -> Divide by 1000 to get Tons
        # Aggregation: Sum of all lines in the window
        
        planned_kg = 0
        
        if granularity == 'shift':
            turno_atual = obter_turno_atual()
            if turno_atual:
                # Use data contabil logic if needed, but here we filter by turno and date range
                # Assuming Calendario data matches the shift start date
                agendamentos = CalendarioProducao.objects.filter(
                    data=start_time.date(),
                    turno=turno_atual,
                    programado=True
                ).aggregate(total=Sum('meta_producao_turno'))
                planned_kg = agendamentos['total'] or 0
            else:
                notes.append('no_active_shift')
        else:
            # Day/Week/Month: Sum all shifts within the date range
            # Note: This simplifies to Date range. 
            # Ideally we should filter by exact timestamps if shifts cross days, 
            # but Calendario is by Date. 
            # For "Day", it's all shifts of that date.
            agendamentos = CalendarioProducao.objects.filter(
                data__gte=start_time.date(),
                data__lte=end_time.date(),
                programado=True
            ).aggregate(total=Sum('meta_producao_turno'))
            planned_kg = agendamentos['total'] or 0
            
        planned_tons = float(planned_kg) / 1000.0
        
        # 3. Actual Tons (History + Realtime)
        # Unit: Tons (RegistroProducaoTurno is already Tons, Realtime is Tons)
        # Deduplication: History (closed shifts) + Realtime (current shift)
        
        actual_tons = 0.0
        
        # 3.1 History: Closed shifts strictly before the current shift (or just closed in window)
        # We filter RegistroProducaoTurno by date range AND exclude current shift if it's in the list
        # But simpler: RegistroProducaoTurno is only for CLOSED shifts (usually).
        # However, to be safe against double counting with realtime:
        # We sum History for all shifts EXCEPT the current active one (if any).
        
        turno_atual = obter_turno_atual()
        
        history_query = RegistroProducaoTurno.objects.filter(
            data__gte=start_time.date(),
            data__lte=end_time.date()
        )
        
        if turno_atual and granularity == 'shift':
             # For shift view, we only want history if it's NOT the current shift 
             # (which shouldn't happen for active shift, but safety first)
             history_query = history_query.exclude(turno=turno_atual)
        elif turno_atual:
             # For day/week, exclude current shift from history to use realtime for it
             # Need to be careful: RegistroProducaoTurno might exist for current shift if it was manually closed?
             # Assuming Realtime is always better for current shift.
             history_query = history_query.exclude(turno=turno_atual, data=now.date())

        history_sum = history_query.aggregate(total=Sum('producao_toneladas'))
        actual_tons += float(history_sum['total'] or 0)
        
        # 3.2 Realtime: Current Shift ONLY
        # Only add if current shift is within the requested window
        # Shift view: Always add. Day view: Add if today.
        
        add_realtime = False
        if granularity == 'shift':
            add_realtime = True
        elif granularity == 'day' and start_time.date() == now.date():
            add_realtime = True
        elif granularity in ['week', 'month'] and start_time.date() <= now.date() <= end_time.date():
            add_realtime = True
            
        if add_realtime and turno_atual:
             # Sum realtime for all active lines
             # We need to iterate lines to get realtime
             linhas = LinhaProducao.objects.filter(ativa=True)
             for linha in linhas:
                 # Find main equipment (usually last one or specific type)
                 # Reusing logic from metricas_fabrica_consolidadas
                 equipamento = linha.equipamentos.filter(tipo__in=['PALETIZADOR', 'ENCHEDORA', 'ROTULADORA']).last()
                 if not equipamento:
                     equipamento = linha.equipamentos.last()
                 
                 if equipamento:
                     # Find 'formato' tag
                     tag_formato = equipamento.tags_coleta.filter(nome_metrica='formato').first()
                     formato = float(tag_formato.formato) if tag_formato and tag_formato.formato else 1.0
                     
                     metrics = get_realtime_metrics(equipamento.codigo, formato, calcular_inicio_turno(turno_atual))
                     actual_tons += metrics.get('toneladas_turno', 0)

        # 4. TPH Calculations
        actual_tph = actual_tons / elapsed_hours
        
        saldo = planned_tons - actual_tons
        min_required_tph = 0.0
        
        if saldo <= 0:
            min_required_tph = 0.0
            notes.append('goal_exceeded')
        elif hours_remaining == 0:
            min_required_tph = None
            notes.append('deadline_passed')
        else:
            min_required_tph = saldo / hours_remaining

        status_flag = 'NORMAL'
        if 'goal_exceeded' in notes:
            status_flag = 'SUPERADO'
        elif 'deadline_passed' in notes:
            status_flag = 'ATRASADO'

        return Response({
            'planned_tons': round(planned_tons, 2),
            'actual_tons': round(actual_tons, 2),
            'actual_tph': round(actual_tph, 2),
            'min_required_tph': round(min_required_tph, 2) if min_required_tph is not None else None,
            'status_flag': status_flag,
            'window': {
                'from': start_time.isoformat(),
                'to': end_time.isoformat(),
                'elapsedHours': round(elapsed_hours, 2),
                'hoursRemaining': round(hours_remaining, 2),
                'granularity': granularity,
                'tz': 'America/Sao_Paulo'
            },
            'notes': notes
        })

