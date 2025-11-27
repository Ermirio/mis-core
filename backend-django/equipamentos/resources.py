from import_export import resources
from .models import Equipamento

class EquipamentoResource(resources.ModelResource):
    class Meta:
        model = Equipamento
        import_id_fields = ('codigo', )
        fields = (
            'codigo',
            'nome',
            'linha',
            'tipo',
            'velocidade_nominal',
            'velocidade_maxima',
            'meta_oee',
            'temperatura_min',
            'temperatura_max',
            'pressao_min',
            'pressao_max',
        )