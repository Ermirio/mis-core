from rest_framework import serializers

from .opc_urls import normalize_opc_tcp_url
from .models import (
    LinhaProducao, Equipamento, Sensor, MetricaProducao,
    Defeito, ConexaoOPC, TagColeta,
    TurnoProducao, CalendarioProducao, EventoEstadoEquipamento, EventoParada,
    StrategicInitiative, Produto, OrdemProducao, DEFAULT_TAGS_BY_NAME
)

class ConexaoOPCSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConexaoOPC
        fields = '__all__'


class TagColetaSerializer(serializers.ModelSerializer):
    nome_metrica_label = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TagColeta
        fields = '__all__'
        validators = []

    def get_nome_metrica_label(self, obj):
        defaults = DEFAULT_TAGS_BY_NAME.get(obj.nome_metrica)
        return defaults['label'] if defaults else obj.nome_metrica

    def create(self, validated_data):
        equipamento = validated_data.get('equipamento')
        nome_metrica = validated_data.get('nome_metrica')
        existing = TagColeta.objects.filter(
            equipamento=equipamento,
            nome_metrica=nome_metrica,
        ).first()
        if existing:
            for attr, value in validated_data.items():
                setattr(existing, attr, value)
            existing.save()
            return existing
        return super().create(validated_data)

    def update(self, instance, validated_data):
        equipamento = validated_data.get('equipamento', instance.equipamento)
        nome_metrica = validated_data.get('nome_metrica', instance.nome_metrica)
        existing = TagColeta.objects.filter(
            equipamento=equipamento,
            nome_metrica=nome_metrica,
        ).exclude(pk=instance.pk).first()
        if existing:
            for attr, value in validated_data.items():
                setattr(existing, attr, value)
            existing.save()
            instance.delete()
            return existing
        return super().update(instance, validated_data)


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
    tags_coleta = TagColetaSerializer(many=True, read_only=True)
    estado_configurado = serializers.SerializerMethodField(read_only=True)
    fonte_estado = serializers.SerializerMethodField(read_only=True)
    tags_estado = serializers.SerializerMethodField(read_only=True)

    def _estado_source(self, obj):
        cache_attr = '_serializer_estado_source'
        cached = getattr(obj, cache_attr, None)
        if cached is not None:
            return cached

        tags = {
            tag.nome_metrica: tag
            for tag in obj.tags_coleta.all()
            if tag.ativa and str(tag.node_id or '').strip()
        }
        dedicadas = [name for name in ('estado_maquina', 'estado') if name in tags]
        booleanas = ['StatusRunning', 'StatusWaiting', 'StatusBlocked', 'StatusFault']
        if dedicadas:
            result = (True, 'TAG_DEDICADA', dedicadas)
        elif all(name in tags for name in booleanas):
            result = (True, 'SINAIS_BOOLEANOS', booleanas)
        else:
            result = (False, 'NAO_CONFIGURADA', [])
        setattr(obj, cache_attr, result)
        return result

    def get_estado_configurado(self, obj):
        return self._estado_source(obj)[0]

    def get_fonte_estado(self, obj):
        return self._estado_source(obj)[1]

    def get_tags_estado(self, obj):
        return self._estado_source(obj)[2]

    class Meta:
        model = Equipamento
        fields = [
            'id', 'nome', 'codigo', 'tipo', 'tipo_display', 'status', 'status_display',
            'velocidade_nominal', 'velocidade_maxima', 'meta_oee',
            'temperatura_min', 'temperatura_max', 'pressao_min', 'pressao_max',
            'observacoes', 'linha', 'linha_nome', 'linha_codigo', 'sensores',
            'tags_coleta', 'ordem_na_linha',
            'estado_configurado', 'fonte_estado', 'tags_estado',
            'criado_em', 'atualizado_em'
        ]


class EquipamentoColetorSerializer(serializers.ModelSerializer):
    """Serializer otimizado para o endpoint de configuração do coletor"""
    tags_coleta = serializers.SerializerMethodField()
    linha_codigo = serializers.CharField(source='linha.codigo', read_only=True)
    linha_nome = serializers.CharField(source='linha.nome', read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)

    # NOVO: Detalhes da Conexão Resolvida (Herança)
    conexao_detalhes = serializers.SerializerMethodField()

    class Meta:
        model = Equipamento
        fields = [
            'id', 'nome', 'codigo', 'tipo', 'tipo_display', 'linha', 'linha_codigo', 'linha_nome',
            'velocidade_nominal', 'velocidade_maxima', 'meta_oee',
            'temperatura_min', 'temperatura_max', 'pressao_min', 'pressao_max',
            'tags_coleta', 'conexao_detalhes'
        ]

    def get_tags_coleta(self, obj):
        """Usa tags pré-filtradas (ativas) se disponíveis, senão busca todas"""
        if hasattr(obj, 'tags_coleta_ativas'):
            return TagColetaSerializer(obj.tags_coleta_ativas, many=True).data
        return TagColetaSerializer(obj.tags_coleta.all(), many=True).data

    def get_conexao_detalhes(self, obj):
        """Resolve a conexão OPC (Linha > None)"""
        conexao = None
        if obj.linha:
            conexao = obj.linha.conexao_padrao

        if conexao:
            return {
                'url': normalize_opc_tcp_url(conexao.url_servidor),
                'tag_monitoramento': conexao.tag_monitoramento,
                'tipo_monitoramento': conexao.tipo_monitoramento,
                'nome': conexao.nome
            }
        return None


class LinhaProducaoSerializer(serializers.ModelSerializer):
    equipamentos = EquipamentoSerializer(many=True, read_only=True)
    sensores = SensorSerializer(many=True, read_only=True)
    # Campos derivados usados pelo Sidebar (PR 13) para agrupar
    # por fabrica/localizacao sem fazer round-trip extra.
    # SerializerMethodField em vez de CharField(source=) porque `area`
    # pode ser None (linha sem área); o atributo encadeado
    # `area.fabrica.codigo` estoura AttributeError sem este guard.
    area_nome = serializers.SerializerMethodField()
    fabrica_id = serializers.SerializerMethodField()
    fabrica_codigo = serializers.SerializerMethodField()
    fabrica_nome = serializers.SerializerMethodField()

    def get_area_nome(self, obj):
        return obj.area.nome if obj.area else None

    def get_fabrica_id(self, obj):
        return obj.area.fabrica.id if obj.area and obj.area.fabrica else None

    def get_fabrica_codigo(self, obj):
        return obj.area.fabrica.codigo if obj.area and obj.area.fabrica else None

    def get_fabrica_nome(self, obj):
        return obj.area.fabrica.nome if obj.area and obj.area.fabrica else None

    class Meta:
        model = LinhaProducao
        fields = '__all__'



# ===== NOVOS SERIALIZERS =====

class ProdutoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Produto
        fields = '__all__'


class OrdemProducaoSerializer(serializers.ModelSerializer):
    linha_nome = serializers.CharField(source='linha.nome', read_only=True)
    linha_codigo = serializers.CharField(source='linha.codigo', read_only=True)
    produto_codigo = serializers.CharField(source='produto.codigo', read_only=True)
    produto_descricao = serializers.CharField(source='produto.descricao', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    # Computed fields
    producao_total = serializers.DecimalField(
        source='producao_total_realizada',
        max_digits=12,
        decimal_places=3,
        read_only=True
    )
    percentual_conclusao = serializers.FloatField(read_only=True)

    class Meta:
        model = OrdemProducao
        fields = [
            'id', 'codigo', 'linha', 'linha_nome', 'linha_codigo',
            'produto', 'produto_codigo', 'produto_descricao',
            'meta_total', 'formato_gramas', 'cuc', 'eficiencia_planejada',
            'status', 'status_display',
            'data_planejada_inicio', 'data_inicio_real', 'data_fim_real',
            'producao_realizada', 'producao_total', 'percentual_conclusao',
            'descricao', 'observacoes',
            'criado_em', 'atualizado_em'
        ]

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
