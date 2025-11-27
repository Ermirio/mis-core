from django.contrib import admin
from django.utils.html import format_html
from .models import (
    LinhaProducao, Equipamento, Sensor, MetricaProducao, 
    Defeito, ConexaoOPC, TagColeta,
    TurnoProducao, CalendarioProducao, EventoEstadoEquipamento
)


# --- PERSONALIZAÇÃO DO ADMIN ---
admin.site.site_header = "MIS - Sistema de Monitoramento Industrial"
admin.site.site_title = "MIS - Core"
admin.site.index_title = "Painel de Gestão do MIS"


@admin.register(LinhaProducao)
class LinhaProducaoAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nome', 'ativa_badge', 'velocidade_planejada', 'meta_producao_hora', 'meta_oee', 'num_equipamentos']
    list_filter = ['ativa', 'criado_em']
    search_fields = ['codigo', 'nome', 'localizacao']
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo', 'nome', 'descricao', 'localizacao', 'ativa')
        }),
        ('Metas e Velocidades', {
            'fields': ('velocidade_planejada', 'meta_producao_hora', 'meta_producao_turno', 'meta_oee')
        }),
    )
    
    def ativa_badge(self, obj):
        if obj.ativa:
            return format_html('<span style="color: green;">✓ Ativa</span>')
        return format_html('<span style="color: red;">✗ Inativa</span>')
    ativa_badge.short_description = 'Status'
    
    def num_equipamentos(self, obj):
        return obj.equipamentos.count()
    num_equipamentos.short_description = 'Equipamentos'


@admin.register(ConexaoOPC)
class ConexaoOPCAdmin(admin.ModelAdmin):
    list_display = ['nome', 'url_servidor', 'ativa_badge', 'timeout', 'num_tags']
    list_filter = ['ativa', 'criado_em']
    search_fields = ['nome', 'url_servidor']
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'url_servidor', 'namespace_prefix', 'ativa')
        }),
        ('Autenticação', {
            'fields': ('usuario', 'senha'),
            'classes': ('collapse',)
        }),
        ('Configurações Avançadas', {
            'fields': ('timeout',)
        }),
    )
    
    def ativa_badge(self, obj):
        if obj.ativa:
            return format_html('<span style="color: green;">✓ Ativa</span>')
        return format_html('<span style="color: red;">✗ Inativa</span>')
    ativa_badge.short_description = 'Status'
    
    def num_tags(self, obj):
        return obj.tags.count()
    num_tags.short_description = 'Tags'


class TagColetaInline(admin.TabularInline):
    """Inline para adicionar tags de coleta diretamente no equipamento"""
    model = TagColeta
    extra = 1
    fields = ['conexao', 'nome_metrica', 'node_id', 'tipo_dado', 'unidade', 'fator_conversao', 'ativa']
    autocomplete_fields = ['conexao']


class SensorInline(admin.TabularInline):
    model = Sensor
    extra = 1
    fields = ['codigo', 'nome', 'tipo', 'tag_influxdb', 'unidade', 'ativo']


@admin.register(Equipamento)
class EquipamentoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'codigo', 'tipo', 'linha', 'ordem_na_linha', 'status', 'velocidade_nominal', 'meta_oee']
    list_filter = ['tipo', 'status', 'linha']
    search_fields = ['nome', 'codigo']
    inlines = [TagColetaInline, SensorInline]
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('linha', 'nome', 'codigo', 'tipo', 'ordem_na_linha', 'localizacao', 'status')
        }),
        ('Velocidades e Metas', {
            'fields': ('velocidade_nominal', 'velocidade_maxima', 'meta_oee')
        }),
        ('Limites de Processo', {
            'fields': ('temperatura_min', 'temperatura_max', 'pressao_min', 'pressao_max'),
            'classes': ('collapse',)
        }),
        ('Observações', {
            'fields': ('observacoes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(TagColeta)
class TagColetaAdmin(admin.ModelAdmin):
    list_display = ['equipamento', 'nome_metrica', 'node_id', 'tipo_dado', 'conexao', 'ativa_badge']
    list_filter = ['tipo_dado', 'ativa', 'conexao', 'equipamento__linha']
    search_fields = ['nome_metrica', 'node_id', 'equipamento__nome']
    autocomplete_fields = ['equipamento', 'conexao']
    fieldsets = (
        ('Associação', {
            'fields': ('equipamento', 'conexao')
        }),
        ('Configuração da Tag', {
            'fields': ('nome_metrica', 'node_id', 'tipo_dado', 'unidade', 'fator_conversao', 'ativa')
        }),
    )
    
    def ativa_badge(self, obj):
        if obj.ativa:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    ativa_badge.short_description = 'Ativa'


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nome', 'tipo', 'get_local', 'tag_influxdb', 'ativo_badge']
    list_filter = ['tipo', 'ativo', 'linha', 'equipamento__linha']
    search_fields = ['codigo', 'nome', 'tag_influxdb']
    fieldsets = (
        ('Localização', {
            'fields': ('linha', 'equipamento'),
            'description': 'Associe o sensor a uma LINHA (para sensores de entrada/saída) OU a um EQUIPAMENTO'
        }),
        ('Informações do Sensor', {
            'fields': ('codigo', 'nome', 'tipo', 'tag_influxdb', 'unidade', 'ativo')
        }),
        ('Limites', {
            'fields': ('valor_min', 'valor_max'),
            'classes': ('collapse',)
        }),
        ('Observações', {
            'fields': ('observacoes',),
            'classes': ('collapse',)
        }),
    )
    
    def get_local(self, obj):
        if obj.equipamento:
            return f'{obj.equipamento.nome}'
        elif obj.linha:
            return f'Linha {obj.linha.codigo}'
        return '-'
    get_local.short_description = 'Localização'
    
    def ativo_badge(self, obj):
        if obj.ativo:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    ativo_badge.short_description = 'Ativo'


# ===== NOVOS ADMINS =====

@admin.register(TurnoProducao)
class TurnoProducaoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'codigo', 'hora_inicio', 'hora_fim', 'duracao_horas', 'ativo_badge']
    list_filter = ['ativo']
    search_fields = ['nome', 'codigo']
    fieldsets = (
        ('Informações do Turno', {
            'fields': ('nome', 'codigo', 'hora_inicio', 'hora_fim', 'duracao_horas', 'ativo')
        }),
        ('Observações', {
            'fields': ('observacoes',),
            'classes': ('collapse',)
        }),
    )
    
    def ativo_badge(self, obj):
        if obj.ativo:
            return format_html('<span style="color: green;">✓ Ativo</span>')
        return format_html('<span style="color: red;">✗ Inativo</span>')
    ativo_badge.short_description = 'Status'


@admin.register(CalendarioProducao)
class CalendarioProducaoAdmin(admin.ModelAdmin):
    list_display = ['data', 'linha', 'turno', 'programado_badge', 'meta_producao_turno']
    list_filter = ['programado', 'linha', 'turno', 'data']
    search_fields = ['linha__codigo', 'linha__nome']
    date_hierarchy = 'data'
    fieldsets = (
        ('Programação', {
            'fields': ('data', 'linha', 'turno', 'programado')
        }),
        ('Metas', {
            'fields': ('meta_producao_turno',)
        }),
        ('Observações', {
            'fields': ('observacoes',),
            'classes': ('collapse',)
        }),
    )
    
    def programado_badge(self, obj):
        if obj.programado:
            return format_html('<span style="color: green;">✓ Programado</span>')
        return format_html('<span style="color: gray;">✗ Não Programado</span>')
    programado_badge.short_description = 'Status'


@admin.register(EventoEstadoEquipamento)
class EventoEstadoEquipamentoAdmin(admin.ModelAdmin):
    list_display = ['equipamento', 'estado_badge', 'inicio', 'fim', 'duracao_formatada', 'origem']
    list_filter = ['estado', 'origem', 'equipamento__linha', 'equipamento']
    search_fields = ['equipamento__nome', 'equipamento__codigo', 'observacao']
    date_hierarchy = 'inicio'
    readonly_fields = ['duracao_segundos', 'criado_em']
    fieldsets = (
        ('Evento', {
            'fields': ('equipamento', 'estado', 'inicio', 'fim', 'duracao_segundos')
        }),
        ('Origem', {
            'fields': ('origem', 'observacao')
        }),
    )
    
    def estado_badge(self, obj):
        cores = {
            'RUN': 'green',
            'WAIT_PREV': 'orange',
            'BLOCK_NEXT': 'orange',
            'FAULT': 'red',
            'SETUP': 'blue',
            'TESTE_PROJ': 'purple',
            'AGUARD_MNT': 'pink',
            'MANUTENCAO': 'gray',
            'FALTA_MAT': 'brown',
            'OUTRO': 'gray',
        }
        cor = cores.get(obj.estado, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            cor,
            obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'
    
    def duracao_formatada(self, obj):
        if not obj.duracao_segundos:
            return format_html('<span style="color: orange;">Em andamento</span>')
        
        horas = obj.duracao_segundos // 3600
        minutos = (obj.duracao_segundos % 3600) // 60
        segundos = obj.duracao_segundos % 60
        
        if horas > 0:
            return f'{horas}h {minutos}m {segundos}s'
        elif minutos > 0:
            return f'{minutos}m {segundos}s'
        else:
            return f'{segundos}s'
    duracao_formatada.short_description = 'Duração'


@admin.register(MetricaProducao)
class MetricaProducaoAdmin(admin.ModelAdmin):
    list_display = ['get_local', 'data_hora', 'periodo', 'contagem_entrada', 'contagem_saida', 
                    'descarte', 'percentual_descarte', 'oee_badge', 'disponibilidade_badge', 
                    'performance_badge', 'qualidade_badge']
    list_filter = ['periodo', 'linha', 'equipamento', 'data_hora']
    date_hierarchy = 'data_hora'
    fieldsets = (
        ('Identificação', {
            'fields': ('linha', 'equipamento', 'data_hora', 'periodo', 'turno')
        }),
        ('Contadores', {
            'fields': ('contagem_entrada', 'contagem_saida', 'descarte', 'percentual_descarte')
        }),
        ('Velocidades', {
            'fields': ('velocidade_planejada', 'velocidade_real')
        }),
        ('Tempos (minutos)', {
            'fields': ('tempo_programado', 'tempo_disponivel', 'tempo_producao', 'tempo_parada', 
                      'tempo_setup', 'tempo_nao_programado')
        }),
        ('KPIs (%)', {
            'fields': ('disponibilidade', 'performance', 'qualidade', 'oee')
        }),
    )
    readonly_fields = ['descarte', 'percentual_descarte', 'tempo_disponivel', 
                      'disponibilidade', 'performance', 'qualidade', 'oee']
    
    def get_local(self, obj):
        if obj.equipamento:
            return f'{obj.equipamento.nome}'
        return f'Linha {obj.linha.codigo}'
    get_local.short_description = 'Local'
    
    def oee_badge(self, obj):
        if obj.oee >= 85:
            color = 'green'
        elif obj.oee >= 70:
            color = 'orange'
        else:
            color = 'red'
        return format_html('<span style="color: {}; font-weight: bold;">{:.1f}%</span>', color, obj.oee)
    oee_badge.short_description = 'OEE'
    
    def disponibilidade_badge(self, obj):
        return format_html('<span style="color: blue;">{:.1f}%</span>', obj.disponibilidade)
    disponibilidade_badge.short_description = 'A'
    
    def performance_badge(self, obj):
        return format_html('<span style="color: purple;">{:.1f}%</span>', obj.performance)
    performance_badge.short_description = 'P'
    
    def qualidade_badge(self, obj):
        return format_html('<span style="color: green;">{:.1f}%</span>', obj.qualidade)
    qualidade_badge.short_description = 'Q'


@admin.register(Defeito)
class DefeitoAdmin(admin.ModelAdmin):
    list_display = ['get_local', 'data_hora', 'tipo_defeito', 'quantidade', 'severidade', 'resolvido']
    list_filter = ['severidade', 'resolvido', 'linha', 'equipamento']
    search_fields = ['tipo_defeito', 'descricao']
    date_hierarchy = 'data_hora'
    
    def get_local(self, obj):
        if obj.equipamento:
            return f'{obj.equipamento.nome}'
        elif obj.linha:
            return f'Linha {obj.linha.codigo}'
        return '-'
    get_local.short_description = 'Local'
