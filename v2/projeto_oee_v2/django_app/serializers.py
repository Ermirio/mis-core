from rest_framework import serializers
from .models import (
    LinhaProducao, Equipamento, Sensor, MetricaProducao, 
    Defeito, ConexaoOPC, TagColeta,
    TurnoProducao, CalendarioProducao, EventoEstadoEquipamento
)


class ConexaoOPCSerializer(serializers.ModelSerializer):
    """Serializer para conexões OPC"""
    class Meta:
        model = ConexaoOPC
        fields = ['id', 'nome', 'url_servidor', 'namespace_prefix', 'usuario', 'timeout', 'ativa']
        extra_kwargs = {
            'senha': {'write_only': True}  # Não expor senha na API
        }


class TagColetaSerializer(serializers.ModelSerializer):
    """Serializer para tags de coleta"""
    conexao_detalhes = ConexaoOPCSerializer(source='conexao', read_only=True)
    
    class Meta:
        model = TagColeta
        fields = [
            'id', 'nome_metrica', 'node_id', 'tipo_dado', 'unidade', 
            'fator_conversao', 'ativa', 'conexao', 'conexao_detalhes'
        ]


class SensorSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    
    class Meta:
        model = Sensor
        fields = '__all__'


class EquipamentoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    sensores = SensorSerializer(many=True, read_only=True)
    linha_nome = serializers.CharField(source='linha.nome', read_only=True)
    linha_codigo = serializers.CharField(source='linha.codigo', read_only=True)
    
    class Meta:
        model = Equipamento
        fields = '__all__'


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
    
    class Meta:
        model = MetricaProducao
        fields = '__all__'


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
    
    # Contadores
    contagem_entrada = serializers.IntegerField(default=0)
    contagem_saida = serializers.IntegerField(default=0)
    
    # Velocidades
    velocidade_planejada = serializers.FloatField(default=0.0)
    velocidade_real = serializers.FloatField(default=0.0)
    
    # Tempos (em minutos)
    tempo_programado = serializers.FloatField(default=60.0)  # Padrão 1 hora
    tempo_disponivel = serializers.FloatField(required=False)
    tempo_producao = serializers.FloatField(default=0.0)
    tempo_parada = serializers.FloatField(default=0.0)
    tempo_setup = serializers.FloatField(default=0.0)
    tempo_nao_programado = serializers.FloatField(default=0.0)
    
    # KPIs (podem vir calculados ou serão calculados no save)
    disponibilidade = serializers.FloatField(required=False)
    performance = serializers.FloatField(required=False)
    qualidade = serializers.FloatField(required=False)
    oee = serializers.FloatField(required=False)


class DefeitoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Defeito
        fields = '__all__'
