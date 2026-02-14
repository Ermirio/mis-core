# programa_andretti/admin.py
from django.contrib import admin
from .models import StartBortoletto, Formato, EstatisticasDiarias, RegistroDiarioLinha

@admin.register(Formato)
class FormatoAdmin(admin.ModelAdmin):
    list_display = ('gramas', 'velocidade_std', 'capacidade_hora', 'capacidade_mes')
    search_fields = ('gramas',)

@admin.register(StartBortoletto)
class StartBortolettoAdmin(admin.ModelAdmin):
    list_display = ('linha', 'formato', 'data_inicio', 'velocidade_std', 'velocidade_planejada', 'percentual_ganho_planejado')
    list_filter = ('linha', 'formato', 'data_inicio')
    search_fields = ('linha__nome', 'formato__gramas')

@admin.register(EstatisticasDiarias)
class EstatisticasDiariasAdmin(admin.ModelAdmin):
    list_display = ('start_bortoletto', 'data', 'velocidade_real', 'percentual_ganho_real_std', 'percentual_ganho_real_planejada')
    list_filter = ('start_bortoletto__linha', 'data')
    search_fields = ('start_bortoletto__linha__nome',)

@admin.register(RegistroDiarioLinha)
class RegistroDiarioLinhaAdmin(admin.ModelAdmin):
    list_display = (
        'linha',
        'gramas',
        'data',
        'velocidade_std',
        'velocidade_planejada',
        'velocidade_real',
        'percentual_ganho_real_std',
        'percentual_ganho_real_planejada',
        'ganho_ton_hora_real_vs_std',
        'ganho_ton_mes_real_vs_std',
    )
    list_filter = ('linha', 'data', 'gramas')
    search_fields = ('linha__nome', 'gramas')
    date_hierarchy = 'data'  # Permite navegação por data

# Removido o admin para Estatisticas, pois o modelo foi excluído