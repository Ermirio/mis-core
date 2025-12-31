from import_export import resources
from .models import (
    Equipamento, Fabrica, Area, Produto, LinhaProducao,
    TagColeta, Sensor, ConexaoOPC, OrdemProducao, TurnoProducao
)

class EquipamentoResource(resources.ModelResource):
    class Meta:
        model = Equipamento
        import_id_fields = ('codigo', )
        fields = (
            'codigo', 'nome', 'linha', 'tipo', 'ordem_na_linha', 'localizacao',
            'status', 'velocidade_nominal', 'velocidade_maxima', 'meta_oee',
            'temperatura_min', 'temperatura_max', 'pressao_min', 'pressao_max',
        )

class FabricaResource(resources.ModelResource):
    class Meta:
        model = Fabrica
        import_id_fields = ('codigo',)
        fields = ('codigo', 'nome', 'localizacao')

class AreaResource(resources.ModelResource):
    class Meta:
        model = Area
        import_id_fields = ('codigo',)
        fields = ('codigo', 'nome', 'fabrica')

class ProdutoResource(resources.ModelResource):
    class Meta:
        model = Produto
        import_id_fields = ('codigo',)
        fields = ('codigo', 'descricao', 'peso_unitario', 'ativo')

class LinhaProducaoResource(resources.ModelResource):
    class Meta:
        model = LinhaProducao
        import_id_fields = ('codigo',)
        fields = (
            'codigo', 'nome', 'area', 'descricao', 'localizacao', 'ativa',
            'velocidade_planejada', 'meta_producao_hora', 'meta_producao_turno', 'meta_oee'
        )

class TagColetaResource(resources.ModelResource):
    class Meta:
        model = TagColeta
        import_id_fields = ('equipamento', 'node_id')
        fields = (
            'equipamento', 'conexao', 'nome_metrica', 'node_id',
            'tipo_dado', 'unidade', 'fator_conversao', 'ativa'
        )

class SensorResource(resources.ModelResource):
    class Meta:
        model = Sensor
        import_id_fields = ('codigo',)
        fields = (
            'codigo', 'nome', 'tipo', 'tag_influxdb', 'unidade',
            'linha', 'equipamento', 'valor_min', 'valor_max', 'ativo'
        )

class ConexaoOPCResource(resources.ModelResource):
    class Meta:
        model = ConexaoOPC
        import_id_fields = ('nome',)
        fields = (
            'nome', 'url_servidor', 'namespace_prefix', 'ativa', 'timeout'
        )

class OrdemProducaoResource(resources.ModelResource):
    class Meta:
        model = OrdemProducao
        import_id_fields = ('codigo',)
        fields = (
            'codigo', 'linha', 'produto', 'status', 'meta_total',
            'formato_gramas', 'cuc', 'eficiencia_planejada',
            'data_planejada_inicio', 'data_inicio_real', 'data_fim_real',
            'descricao'
        )

class TurnoProducaoResource(resources.ModelResource):
    class Meta:
        model = TurnoProducao
        import_id_fields = ('codigo',)
        fields = (
            'codigo', 'nome', 'hora_inicio', 'hora_fim', 'duracao_horas', 'ativo'
        )