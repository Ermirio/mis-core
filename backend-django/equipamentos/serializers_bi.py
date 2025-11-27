"""
Serializers para BI (Business Intelligence)
Novos serializers para endpoints de análise estratégica
"""

from rest_framework import serializers
from equipamentos.models import (
    OrdemProducao, RegistroProducaoTurno, LinhaProducao,
    Produto, TurnoProducao
)


class OrdemProducaoSerializer(serializers.ModelSerializer):
    """Serializer para Ordem de Produção"""
    
    linha_codigo = serializers.CharField(source='linha.codigo', read_only=True)
    linha_nome = serializers.CharField(source='linha.nome', read_only=True)
    produto_codigo = serializers.CharField(source='produto.codigo', read_only=True)
    produto_descricao = serializers.CharField(source='produto.descricao', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    site_nome = serializers.SerializerMethodField()
    tecnologia_nome = serializers.SerializerMethodField()
    producao_realizada = serializers.IntegerField(source='producao_total_realizada', read_only=True)
    percentual_conclusao = serializers.FloatField(read_only=True)
    
    class Meta:
        model = OrdemProducao
        fields = [
            'id', 'codigo', 'linha', 'linha_codigo', 'linha_nome',
            'produto', 'produto_codigo', 'produto_descricao',
            'site_nome', 'tecnologia_nome',
            'meta_total', 'meta_turno', 'formato_gramas', 'cuc',
            'eficiencia_planejada', 'status', 'status_display',
            'data_planejada_inicio', 'data_inicio_real', 'data_fim_real',
            'producao_realizada', 'percentual_conclusao',
            'descricao', 'observacoes', 'criado_em', 'atualizado_em'
        ]
    
    def get_site_nome(self, obj):
        return obj.linha.site.nome if obj.linha.site else None
    
    def get_tecnologia_nome(self, obj):
        return obj.linha.tecnologia.nome if obj.linha.tecnologia else None


class RegistroProducaoTurnoSerializer(serializers.ModelSerializer):
    """Serializer para Registro de Produção por Turno (BI)"""
    
    op_codigo = serializers.CharField(source='ordem_producao.codigo', read_only=True)
    linha_codigo = serializers.CharField(source='linha.codigo', read_only=True)
    linha_nome = serializers.CharField(source='linha.nome', read_only=True)
    produto_codigo = serializers.CharField(source='produto.codigo', read_only=True)
    produto_descricao = serializers.CharField(source='produto.descricao', read_only=True)
    turno_codigo = serializers.CharField(source='turno.codigo', read_only=True)
    turno_nome = serializers.CharField(source='turno.nome', read_only=True)
    site_nome = serializers.SerializerMethodField()
    tecnologia_nome = serializers.SerializerMethodField()
    
    class Meta:
        model = RegistroProducaoTurno
        fields = [
            'id', 'ordem_producao', 'op_codigo',
            'linha', 'linha_codigo', 'linha_nome',
            'produto', 'produto_codigo', 'produto_descricao',
            'site_nome', 'tecnologia_nome',
            'data', 'turno', 'turno_codigo', 'turno_nome',
            'producao_unidades', 'producao_toneladas',
            'refugo_unidades', 'refugo_kg',
            'tempo_programado_min', 'tempo_disponivel_min',
            'tempo_producao_min', 'tempo_parado_min', 'tempo_setup_min',
            'disponibilidade', 'performance', 'qualidade', 'oee', 'eficiencia',
            'velocidade_media', 'velocidade_planejada',
            'consolidado_em', 'observacoes'
        ]
    
    def get_site_nome(self, obj):
        return obj.linha.site.nome if obj.linha.site else None
    
    def get_tecnologia_nome(self, obj):
        return obj.linha.tecnologia.nome if obj.linha.tecnologia else None


class ProducaoFabricaSerializer(serializers.Serializer):
    """Serializer para visão agregada da fábrica"""
    
    total_producao_unidades = serializers.IntegerField()
    total_producao_toneladas = serializers.DecimalField(max_digits=12, decimal_places=3)
    total_refugo_kg = serializers.DecimalField(max_digits=10, decimal_places=3)
    oee_medio = serializers.FloatField()
    disponibilidade_media = serializers.FloatField()
    performance_media = serializers.FloatField()
    qualidade_media = serializers.FloatField()
    eficiencia_media = serializers.FloatField()
    total_ops_ativas = serializers.IntegerField()
    total_ops_concluidas = serializers.IntegerField()


class ProducaoTecnologiaSerializer(serializers.Serializer):
    """Serializer para visão agregada por tecnologia/área"""
    
    tecnologia_nome = serializers.CharField()
    total_producao_unidades = serializers.IntegerField()
    total_producao_toneladas = serializers.DecimalField(max_digits=12, decimal_places=3)
    oee_medio = serializers.FloatField()
    eficiencia_media = serializers.FloatField()
    total_linhas = serializers.IntegerField()
    total_ops_ativas = serializers.IntegerField()


class ProducaoLinhaSerializer(serializers.Serializer):
    """Serializer para visão agregada por linha"""
    
    linha_codigo = serializers.CharField()
    linha_nome = serializers.CharField()
    total_producao_unidades = serializers.IntegerField()
    total_producao_toneladas = serializers.DecimalField(max_digits=12, decimal_places=3)
    oee_medio = serializers.FloatField()
    eficiencia_media = serializers.FloatField()
    total_turnos = serializers.IntegerField()
    ops_ativas = serializers.ListField(child=serializers.CharField())
