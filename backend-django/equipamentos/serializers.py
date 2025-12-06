from rest_framework import serializers
from .models import (
    LinhaProducao, Equipamento, Sensor, MetricaProducao, 
    Defeito, ConexaoOPC, TagColeta,
    TurnoProducao, CalendarioProducao, EventoEstadoEquipamento, EventoParada,
    StrategicInitiative
)

class ConexaoOPCSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConexaoOPC
        fields = '__all__'


class TagColetaSerializer(serializers.ModelSerializer):
    conexao_detalhes = ConexaoOPCSerializer(source='conexao', read_only=True)
    
    class Meta:
        model = TagColeta
        fields = '__all__'


class SensorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sensor
        fields = '__all__'


class DefeitoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Defeito
        fields = '__all__'


class EquipamentoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    linha_nome = serializers.CharField(source='linha.nome', read_only=True)
    linha_codigo = serializers.CharField(source='linha.codigo', read_only=True)
    sensores = SensorSerializer(many=True, read_only=True)
    formato_padrao = serializers.SerializerMethodField()
    
    class Meta:
        model = Equipamento
        fields = [
            'id', 'nome', 'codigo', 'tipo', 'tipo_display', 'status', 'status_display',
            'velocidade_nominal', 'velocidade_maxima', 'meta_oee',
            'temperatura_min', 'temperatura_max', 'pressao_min', 'pressao_max',
            'observacoes', 'linha', 'linha_nome', 'linha_codigo', 'sensores',
            'ordem_na_linha', 'formato_padrao',
            'criado_em', 'atualizado_em'
        ]

    def get_formato_padrao(self, obj):
        """Retorna o formato (peso) da tag de produção principal"""
        tag = obj.tags_coleta.filter(nome_metrica__in=['contagem_saida', 'producao', 'contador']).first()
        return tag.formato if tag else None


class EquipamentoColetorSerializer(serializers.ModelSerializer):
    """Serializer otimizado para o endpoint de configuração do coletor"""
    tags_coleta = TagColetaSerializer(many=True, read_only=True)
    linha_codigo = serializers.CharField(source='linha.codigo', read_only=True)
    linha_nome = serializers.CharField(source='linha.nome', read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    
    class Meta:
        model = Equipamento
        fields = [
            'id', 'nome', 'codigo', 'tipo', 'tipo_display', 'linha', 'linha_codigo', 'linha_nome',
            'velocidade_nominal', 'velocidade_maxima', 'meta_oee',
            'temperatura_min', 'temperatura_max', 'pressao_min', 'pressao_max',
            'tags_coleta'
        ]


class LinhaProducaoSerializer(serializers.ModelSerializer):
    equipamentos = EquipamentoSerializer(many=True, read_only=True)
    sensores = SensorSerializer(many=True, read_only=True)
    
    class Meta:
        model = LinhaProducao
        fields = '__all__'


# ===== NOVOS SERIALIZERS =====

class TurnoProducaoSerializer(serializers.ModelSerializer):
    """Serializer para turnos de produção"""
    class Meta:
        model = TurnoProducao
        fields = '__all__'


class CalendarioProducaoSerializer(serializers.ModelSerializer):
    """Serializer para calendário de produção"""
    linha_codigo = serializers.CharField(source='linha.codigo', read_only=True)
    linha_nome = serializers.CharField(source='linha.nome', read_only=True)
    turno_nome = serializers.CharField(source='turno.nome', read_only=True)
    turno_codigo = serializers.CharField(source='turno.codigo', read_only=True)
    
    class Meta:
        model = CalendarioProducao
        fields = '__all__'


class EventoEstadoEquipamentoSerializer(serializers.ModelSerializer):
    """Serializer para eventos de estado"""
    equipamento_nome = serializers.CharField(source='equipamento.nome', read_only=True)
    equipamento_codigo = serializers.CharField(source='equipamento.codigo', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    origem_display = serializers.CharField(source='get_origem_display', read_only=True)
    
    class Meta:
        model = EventoEstadoEquipamento
        fields = '__all__'
        read_only_fields = ['duracao_segundos', 'criado_em']


class EventoEstadoCreateSerializer(serializers.Serializer):
    """Serializer para criar eventos de estado via API (usado pelo Coletor)"""
    equipamento_codigo = serializers.CharField(required=True)
    estado = serializers.ChoiceField(choices=[choice[0] for choice in EventoEstadoEquipamento._meta.get_field('estado').choices])
    timestamp = serializers.DateTimeField(required=True)
    origem = serializers.ChoiceField(
        choices=['OPC', 'MANUAL', 'SISTEMA'],
        default='OPC'
    )
    observacao = serializers.CharField(required=False, allow_blank=True)


class MetricaProducaoSerializer(serializers.ModelSerializer):
    linha_codigo = serializers.CharField(source='linha.codigo', read_only=True)
    linha_nome = serializers.CharField(source='linha.nome', read_only=True)
    equipamento_nome = serializers.CharField(source='equipamento.nome', read_only=True, allow_null=True)
    equipamento_codigo = serializers.CharField(source='equipamento.codigo', read_only=True, allow_null=True)
    
    # Adicionar OP e Meta do HistoricoSKU
    ordem_producao = serializers.SerializerMethodField()
    meta_producao = serializers.SerializerMethodField()
    
    class Meta:
        model = MetricaProducao
        fields = '__all__'
    
    def get_ordem_producao(self, obj):
        """Busca OP do histórico SKU ativo no momento da métrica"""
        from .models import HistoricoSKU
        from django.db.models import Q
        
        historico = HistoricoSKU.objects.filter(
            linha=obj.linha,
            data_inicio__lte=obj.data_hora
        ).filter(
            Q(data_fim__gte=obj.data_hora) | Q(data_fim__isnull=True)
        ).first()
        
        return historico.ordem_producao if historico else None
    
    def get_meta_producao(self, obj):
        """Busca meta do histórico SKU ativo no momento da métrica"""
        from .models import HistoricoSKU
        from django.db.models import Q
        
        historico = HistoricoSKU.objects.filter(
            linha=obj.linha,
            data_inicio__lte=obj.data_hora
        ).filter(
            Q(data_fim__gte=obj.data_hora) | Q(data_fim__isnull=True)
        ).first()
        
        return historico.meta_producao if historico else None


class TonnageDataSerializer(serializers.Serializer):
    """Serializer para dados de tonelagem"""
    toneladas_produzidas = serializers.DecimalField(max_digits=12, decimal_places=3)
    vazao_real_ton_hora = serializers.DecimalField(max_digits=10, decimal_places=3)
    formato_gramas = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    contagem_saida = serializers.IntegerField()
    data_hora = serializers.DateTimeField()
    periodo = serializers.CharField()
    turno = serializers.CharField(allow_blank=True, allow_null=True)


class MetricaConsolidadaInputSerializer(serializers.Serializer):
    """Serializer para receber dados consolidados do Flask/Coletor"""
    equipamento_id = serializers.IntegerField(required=False, allow_null=True)
    linha_id = serializers.IntegerField(required=True)
    data_hora = serializers.DateTimeField(required=True)
    periodo = serializers.ChoiceField(
        choices=['HORA', 'TURNO', 'DIA', 'SEMANA', 'MES', 'ANO'],
        default='HORA'
    )
    turno = serializers.CharField(required=False, allow_blank=True)
    contagem_entrada = serializers.IntegerField(required=True)
    contagem_saida = serializers.IntegerField(required=True)
    velocidade_planejada = serializers.FloatField(required=True)
    velocidade_real = serializers.FloatField(required=True)
    tempo_programado = serializers.FloatField(required=False, default=60.0)
    tempo_producao = serializers.FloatField(required=True)
    tempo_parada = serializers.FloatField(required=True)
    tempo_setup = serializers.FloatField(required=True)
    tempo_nao_programado = serializers.FloatField(required=False, default=0.0)
    
    # KPIs opcionais (calculados se não fornecidos)
    disponibilidade = serializers.FloatField(required=False)
    performance = serializers.FloatField(required=False)
    qualidade = serializers.FloatField(required=False)
    oee = serializers.FloatField(required=False)

class EventoParadaSerializer(serializers.ModelSerializer):
    """Serializer para eventos de parada (Estratégico)"""
    categoria_display = serializers.CharField(source='get_categoria_clp_display', read_only=True)
    
    class Meta:
        model = EventoParada
        fields = '__all__'

class StrategicInitiativeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StrategicInitiative
        fields = '__all__'