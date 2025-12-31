from django.contrib import admin
from .models import AnalyticsProfile


@admin.register(AnalyticsProfile)
class AnalyticsProfileAdmin(admin.ModelAdmin):
    """Admin para gerenciar perfis de Analytics"""
    list_display = ['nome', 'linha', 'criado_em', 'atualizado_em', 'criado_por']
    list_filter = ['linha', 'criado_em']
    search_fields = ['nome', 'descricao']
    readonly_fields = ['criado_em', 'atualizado_em']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'descricao', 'linha', 'criado_por')
        }),
        ('Configuração', {
            'fields': ('config',),
            'classes': ('collapse',)
        }),
        ('Metadados', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
