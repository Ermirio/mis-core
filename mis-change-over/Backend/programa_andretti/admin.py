from django.contrib import admin
from django.utils.html import format_html
from .models import (
    WaveAndretti, MetaVelocidadeLinha, LeituraVelocidade,
    CategoriaAcao, AcaoAndretti,
)


# ── Módulo Andretti ──────────────────────────────────────────────────────────

class MetaVelocidadeLinhaInline(admin.TabularInline):
    model = MetaVelocidadeLinha
    extra = 1
    fields = ('linha', 'formato', 'velocidade_padrao', 'velocidade_meta', 'unidade')


class AcaoAndrettiInline(admin.TabularInline):
    model = AcaoAndretti
    extra = 0
    fields = ('linha', 'area', 'categoria', 'descricao', 'responsavel', 'prazo_execucao', 'status')
    show_change_link = True


@admin.register(WaveAndretti)
class WaveAndrettiAdmin(admin.ModelAdmin):
    list_display  = ('nome', 'data_inicio', 'data_fim', 'badge_ativa', 'total_metas', 'total_acoes')
    list_filter   = ('ativa',)
    search_fields = ('nome',)
    inlines       = [MetaVelocidadeLinhaInline, AcaoAndrettiInline]
    save_on_top   = True

    def badge_ativa(self, obj):
        if obj.ativa:
            return format_html('<span style="color:#22c55e;font-weight:700;">● Ativa</span>')
        return format_html('<span style="color:#6b7280;">○ Inativa</span>')
    badge_ativa.short_description = 'Status'

    def total_metas(self, obj):
        return obj.metas.count()
    total_metas.short_description = 'Metas'

    def total_acoes(self, obj):
        return obj.acoes.count()
    total_acoes.short_description = 'Ações'


@admin.register(MetaVelocidadeLinha)
class MetaVelocidadeLinhaAdmin(admin.ModelAdmin):
    list_display  = ('linha', 'wave', 'formato_display', 'velocidade_padrao',
                     'velocidade_meta', 'unidade', 'badge_ganho')
    list_filter   = ('wave', 'unidade', 'linha')
    search_fields = ('linha__nome', 'wave__nome', 'formato__nome')
    autocomplete_fields = ('linha',)

    def formato_display(self, obj):
        if obj.formato:
            return f"{obj.formato.gramas}g" if obj.formato.gramas else obj.formato.nome
        return '— Geral'
    formato_display.short_description = 'Formato'

    def badge_ganho(self, obj):
        g = obj.ganho_percentual
        cor = '#22c55e' if g >= 15 else '#f59e0b' if g >= 5 else '#ef4444'
        return format_html('<span style="color:{};font-weight:700;">+{}%</span>', cor, g)
    badge_ganho.short_description = 'Ganho Planejado'


@admin.register(LeituraVelocidade)
class LeituraVelocidadeAdmin(admin.ModelAdmin):
    list_display    = ('linha', 'meta', 'fonte', 'velocidade_display', 'timestamp')
    list_filter     = ('linha', 'fonte')
    search_fields   = ('linha__nome',)
    readonly_fields = ('timestamp',)
    date_hierarchy  = 'timestamp'
    autocomplete_fields = ('meta',)
    fields          = ('linha', 'meta', 'fonte', 'velocidade', 'formato_gramas', 'timestamp')

    def formato_display(self, obj):
        return f"{obj.formato_gramas}g" if obj.formato_gramas else '—'
    formato_display.short_description = 'Formato'

    def velocidade_display(self, obj):
        if obj.velocidade is None:
            return format_html('<span style="color:#6b7280;font-style:italic;">— aguardando OPC</span>')
        return f'{obj.velocidade} ppm'
    velocidade_display.short_description = 'Velocidade'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'velocidade' in form.base_fields:
            form.base_fields['velocidade'].required = False
            form.base_fields['velocidade'].help_text = (
                'Obrigatório apenas para fonte Manual. '
                'Para OPC, deixe em branco — o servidor preenche automaticamente.'
            )
        if 'formato_gramas' in form.base_fields:
            form.base_fields['formato_gramas'].help_text = (
                'Formato em gramas (ex: 4000 = 4kg). '
                'Para fonte OPC é lido automaticamente se tag_formato_opc estiver configurada.'
            )
        return form

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CategoriaAcao)
class CategoriaAcaoAdmin(admin.ModelAdmin):
    list_display  = ('nome', 'badge_area')
    list_filter   = ('area',)
    search_fields = ('nome',)

    CORES_AREA = {
        'manutencao':    '#f59e0b',
        'qualidade':     '#8b5cf6',
        'eng_projetos':  '#3b82f6',
        'eng_processos': '#10b981',
    }

    def badge_area(self, obj):
        cor = self.CORES_AREA.get(obj.area, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:10px;font-size:11px;font-weight:700;">{}</span>',
            cor, obj.get_area_display()
        )
    badge_area.short_description = 'Área'


CORES_STATUS = {
    'aberta':       '#3b82f6',
    'em_andamento': '#f59e0b',
    'concluida':    '#22c55e',
    'cancelada':    '#6b7280',
}

CORES_AREA_ACAO = {
    'manutencao':    '#f59e0b',
    'qualidade':     '#8b5cf6',
    'eng_projetos':  '#3b82f6',
    'eng_processos': '#10b981',
}


@admin.register(AcaoAndretti)
class AcaoAndrettiAdmin(admin.ModelAdmin):
    list_display   = ('linha', 'wave', 'badge_area', 'categoria',
                      'descricao_curta', 'responsavel', 'prazo_execucao',
                      'badge_status', 'data_realizada')
    list_filter    = ('wave', 'linha', 'area', 'status')
    search_fields  = ('descricao', 'responsavel', 'linha__nome')
    date_hierarchy = 'prazo_execucao'
    autocomplete_fields = ('linha',)
    readonly_fields = ('data_insercao', 'criado_por')
    save_on_top    = True
    list_select_related = ('linha', 'wave', 'categoria')

    fieldsets = (
        ('Identificação', {'fields': ('wave', 'linha', 'area', 'categoria')}),
        ('Ação', {'fields': ('descricao', 'responsavel', 'prazo_execucao', 'status', 'data_realizada')}),
        ('Auditoria', {'fields': ('data_insercao', 'criado_por'), 'classes': ('collapse',)}),
    )

    actions = ['marcar_concluida', 'marcar_em_andamento']

    def descricao_curta(self, obj):
        return obj.descricao[:70] + '…' if len(obj.descricao) > 70 else obj.descricao
    descricao_curta.short_description = 'Descrição'

    def badge_status(self, obj):
        cor = CORES_STATUS.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:10px;font-size:11px;font-weight:700;">{}</span>',
            cor, obj.get_status_display()
        )
    badge_status.short_description = 'Status'

    def badge_area(self, obj):
        cor = CORES_AREA_ACAO.get(obj.area, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:10px;font-size:11px;font-weight:700;">{}</span>',
            cor, obj.get_area_display()
        )
    badge_area.short_description = 'Área'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description='Marcar selecionadas como Concluídas')
    def marcar_concluida(self, request, queryset):
        from django.utils import timezone
        updated = queryset.exclude(status='concluida').update(
            status='concluida',
            data_realizada=timezone.now().date()
        )
        self.message_user(request, f'{updated} ação(ões) marcada(s) como concluída(s).')

    @admin.action(description='Marcar selecionadas como Em Andamento')
    def marcar_em_andamento(self, request, queryset):
        updated = queryset.exclude(status='em_andamento').update(status='em_andamento')
        self.message_user(request, f'{updated} ação(ões) marcada(s) como em andamento.')
