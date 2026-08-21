from django.contrib import admin, messages
from django import forms
from django.core.exceptions import PermissionDenied
from django.forms.models import BaseInlineFormSet
from django.db.models import Case, IntegerField, When
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import slugify
from .models import (
    LinhaProducao, Equipamento, Sensor, MetricaProducao,
    Defeito, ConexaoOPC, TagColeta, DEFAULT_TAGS_COLETA,
    DEFAULT_TAGS_BY_NAME,
    ensure_default_tags_for_equipment,
    TurnoProducao, CalendarioProducao, EventoEstadoEquipamento,
    Fabrica, Area, Produto, HistoricoSKU, OrdemProducao, RegistroProducaoTurno,
    StrategicInitiative, EventoParada,
    GoldenStateRun, GoldenStateVarSnapshot,
    NodeRedSnapshot, NodeRedUser,
)

from import_export.admin import ImportExportModelAdmin
from .resources import (
    EquipamentoResource, FabricaResource, AreaResource, ProdutoResource,
    LinhaProducaoResource, TagColetaResource, SensorResource, ConexaoOPCResource,
    OrdemProducaoResource, TurnoProducaoResource, EquipamentoVariaveisWorkbook,
) 

# --- PERSONALIZAÇÃO DO ADMIN ---
admin.site.site_header = "MIS - Sistema de Monitoramento Industrial"
admin.site.site_title = "MIS - Core"
admin.site.index_title = "Painel de Gestão do MIS"


# ==============================
# HIERARQUIA
# ==============================

@admin.register(Fabrica)
class FabricaAdmin(ImportExportModelAdmin):
    resource_class = FabricaResource
    list_display = ['nome', 'codigo', 'localizacao']
    search_fields = ['nome', 'codigo']

    def get_readonly_fields(self, request, obj=None):
        # Em novo cadastro, o código é gerado no save() — exibir readonly para deixar claro
        if obj is None:
            return ('codigo',)
        return super().get_readonly_fields(request, obj)

@admin.register(Area)
class AreaAdmin(ImportExportModelAdmin):
    resource_class = AreaResource
    list_display = ['nome', 'codigo', 'fabrica']
    list_filter = ['fabrica']
    search_fields = ['nome', 'codigo']
    autocomplete_fields = ['fabrica']

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ('codigo',)
        return super().get_readonly_fields(request, obj)

@admin.register(Produto)
class ProdutoAdmin(ImportExportModelAdmin):
    resource_class = ProdutoResource
    list_display = ['codigo', 'descricao', 'peso_unitario', 'ativo']
    list_filter = ['ativo']
    search_fields = ['codigo', 'descricao']

@admin.register(HistoricoSKU)
class HistoricoSKUAdmin(admin.ModelAdmin):
    list_display = ['linha', 'produto', 'data_inicio', 'data_fim']
    list_filter = ['linha', 'produto']
    date_hierarchy = 'data_inicio'
    autocomplete_fields = ['linha', 'produto']

# ==============================
# LINHA DE PRODUÇÃO
# ==============================

@admin.register(LinhaProducao)
class LinhaProducaoAdmin(ImportExportModelAdmin):
    resource_class = LinhaProducaoResource
    list_display = [
        'codigo', 'nome', 'ativa_badge',
        'velocidade_planejada', 'meta_producao_hora', 'meta_oee',
        'num_equipamentos'
    ]
    list_filter = ['ativa', 'criado_em']
    search_fields = ['codigo', 'nome', 'localizacao']
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo', 'nome', 'area', 'conexao_padrao', 'descricao', 'localizacao', 'ativa')
        }),
        ('Metas e Velocidades', {
            'fields': ('velocidade_planejada', 'meta_producao_hora', 'meta_producao_turno', 'meta_oee')
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ('codigo',)
        return super().get_readonly_fields(request, obj)
    
    def ativa_badge(self, obj):
        if obj.ativa:
            return format_html('<span style="color: green;">✓ Ativa</span>')
        return format_html('<span style="color: red;">✗ Inativa</span>')
    ativa_badge.short_description = 'Status'
    
    def num_equipamentos(self, obj):
        return obj.equipamentos.count()
    num_equipamentos.short_description = 'Equipamentos'


# ==============================
# CONEXÃO OPC
# ==============================

@admin.register(ConexaoOPC)
class ConexaoOPCAdmin(ImportExportModelAdmin):
    resource_class = ConexaoOPCResource
    list_display = ['nome', 'url_servidor', 'ativa_badge', 'timeout', 'num_tags']
    list_filter = ['ativa', 'criado_em']
    search_fields = ['nome', 'url_servidor']
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'url_servidor', 'namespace_prefix', 'ativa')
        }),
        ('Monitoramento de Saúde', {
            'fields': ('tag_monitoramento', 'tipo_monitoramento'),
            'description': 'Configure a tag para monitorar a saúde da conexão (Heartbeat ou Error Bit)'
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
        # Fix for AttributeError: 'ConexaoOPC' object has no attribute 'tags'
        # Counts tags linked to equipments in lines that use this connection
        # Access via: TagColeta -> Equipamento -> Linha -> ConexaoOPC
        return TagColeta.objects.filter(equipamento__linha__conexao_padrao=obj).count()
    num_tags.short_description = 'Tags'


# ==============================
# INLINES (usados em Equipamento)
# ==============================

DEFAULT_TAG_HELP = {
    'contagem_entrada': 'Contabiliza as pecas que entram no equipamento. Usada para perdas e descarte.',
    'contagem_saida': 'Contabiliza as pecas boas/saida do equipamento. Usada para producao do turno e cards.',
    'estado_maquina': 'Estado operacional do equipamento vindo do CLP. Usado em timeline, OEE/OLE e parada.',
    'velocidade_atual': 'Velocidade real do equipamento. Usada em cards, performance e tendencia.',
    'ordem_producao': 'Ordem de producao ativa informada pelo CLP.',
    'sku_codigo': 'Codigo do SKU/produto em producao.',
    'descricao': 'Descricao do produto em producao.',
    'formato': 'Formato ou peso unitario do produto, usado para conversao de toneladas.',
    'planejado_op': 'Quantidade planejada da ordem de producao.',
    'cuc': 'Custo unitario de conversao usado nas visoes economicas.',
}


class TagColetaPadraoForm(forms.ModelForm):
    variavel_padrao = forms.CharField(
        disabled=True,
        label='Variavel',
        required=False,
        help_text='Nome padrao do sistema. Preencha apenas a configuracao OPC.',
    )

    class Meta:
        model = TagColeta
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nome = (
            getattr(self.instance, 'nome_metrica', None)
            or self.initial.get('nome_metrica')
            or self.data.get(self.add_prefix('nome_metrica'))
        )
        defaults = DEFAULT_TAGS_BY_NAME.get(nome)
        self.fields['variavel_padrao'].initial = defaults['label'] if defaults else nome


class TagColetaPadraoFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance is not None and not instance.pk:
            kwargs.setdefault('initial', [
                {
                    'nome_metrica': defaults['nome'],
                    'tipo_dado': defaults['tipo_dado'],
                    'unidade': defaults['unidade'],
                    'fator_conversao': defaults['fator_conversao'],
                    'ativa': False,
                }
                for defaults in DEFAULT_TAGS_COLETA
            ])
        super().__init__(*args, **kwargs)

    def save_new(self, form, commit=True):
        obj = form.save(commit=False)
        obj.equipamento = self.instance
        obj.nome_metrica = form.initial.get('nome_metrica') or obj.nome_metrica
        existing = TagColeta.objects.filter(
            equipamento=self.instance,
            nome_metrica=obj.nome_metrica,
        ).first()
        if existing:
            existing.node_id = obj.node_id
            existing.ativa = obj.ativa
            existing.formato = obj.formato
            if commit:
                existing.save()
            return existing
        if commit:
            obj.save()
        return obj


class TagColetaPadraoInline(admin.TabularInline):
    """Variaveis obrigatorias para cards, metricas e operacao."""
    model = TagColeta
    form = TagColetaPadraoForm
    formset = TagColetaPadraoFormSet
    verbose_name = 'Variavel padrao'
    verbose_name_plural = 'Variaveis padrao do equipamento'
    extra = 0
    can_delete = False
    fields = [
        'variavel_padrao', 'dica_padrao', 'node_id', 'ativa', 'tipo_dado',
        'unidade', 'fator_conversao'
    ]
    readonly_fields = ['dica_padrao', 'tipo_dado', 'unidade', 'fator_conversao']
    classes = ('mis-default-tags-inline',)

    class Media:
        css = {'all': ('admin_mis/css/admin-inline-fixes.css',)}

    def get_queryset(self, request):
        nomes_padrao = list(DEFAULT_TAGS_BY_NAME.keys())
        order_expr = Case(
            *[When(nome_metrica=name, then=idx) for idx, name in enumerate(nomes_padrao)],
            default=len(nomes_padrao),
            output_field=IntegerField(),
        )
        return super().get_queryset(request).filter(nome_metrica__in=nomes_padrao).order_by(order_expr)

    def get_extra(self, request, obj=None, **kwargs):
        return len(DEFAULT_TAGS_COLETA) if obj is None else 0

    def dica_padrao(self, obj):
        help_text = DEFAULT_TAG_HELP.get(getattr(obj, 'nome_metrica', ''), '')
        if not help_text:
            return '-'
        return format_html('<span title="{}">Ver dica</span>', help_text)
    dica_padrao.short_description = 'Ajuda'


class TagColetaCustomInline(admin.TabularInline):
    """Variaveis livres usadas para historico e analises."""
    model = TagColeta
    verbose_name = 'Variavel livre'
    verbose_name_plural = 'Variaveis livres para analise/historico'
    extra = 1
    fields = [
        'nome_metrica', 'node_id', 'tipo_dado',
        'unidade', 'fator_conversao', 'ativa', 'golden_state'
    ]

    def get_queryset(self, request):
        nomes_padrao = list(DEFAULT_TAGS_BY_NAME.keys())
        return super().get_queryset(request).exclude(nome_metrica__in=nomes_padrao)


class EquipamentoVariaveisImportForm(forms.Form):
    arquivo = forms.FileField(
        label='Arquivo',
        help_text='Use o arquivo .xlsx exportado na tela deste mesmo equipamento.',
    )

    def clean_arquivo(self):
        arquivo = self.cleaned_data['arquivo']
        if not arquivo.name.lower().endswith('.xlsx'):
            raise forms.ValidationError('Use um arquivo .xlsx exportado pelo sistema.')
        if arquivo.size > 10 * 1024 * 1024:
            raise forms.ValidationError('O arquivo excede o limite de 10 MB.')
        return arquivo



class SensorInline(admin.TabularInline):
    model = Sensor
    extra = 1
    fields = ['codigo', 'nome', 'tipo', 'tag_influxdb', 'unidade', 'ativo', 'golden_state']
    readonly_fields = ['codigo']
    classes = ['sensor-inline-auto-codigo']

    def get_formset(self, request, obj=None, **kwargs):
        # Sinaliza ao usuário que o código é gerado automaticamente.
        # Antes a coluna ficava editável e vazia, induzindo o usuário a
        # digitar S001 manualmente — agora é readonly e mostra "(auto)".
        formset = super().get_formset(request, obj=obj, **kwargs)
        if 'codigo' in formset.form.base_fields:
            formset.form.base_fields['codigo'].help_text = (
                'Gerado automaticamente ao salvar (S001, S002, ...).'
            )
        return formset


# ==============================
# EQUIPAMENTO (ÚNICA DEFINIÇÃO)
# ==============================

@admin.register(Equipamento)
class EquipamentoAdmin(ImportExportModelAdmin):
    """
    Admin de Equipamento com:
    - Import/Export via EquipamentoResource
    - Inlines de TagColeta e Sensor
    - Todos os fieldsets e campos que você já tinha
    """
    resource_class = EquipamentoResource
    change_form_template = 'admin/equipamentos/equipamento/change_form.html'

    list_display = [
        'nome', 'codigo', 'slug', 'tipo', 'linha',
        'ordem_na_linha', 'status',
        'velocidade_nominal', 'meta_oee'
    ]
    list_filter = ['tipo', 'status', 'linha']
    search_fields = ['nome', 'codigo', 'slug', 'uuid']

    inlines = [TagColetaPadraoInline, TagColetaCustomInline, SensorInline]
    actions = ['criar_tags_padrao']

    fieldsets = (
        ('Identidade', {
            'fields': ('slug', 'uuid'),
            'description': (
                '<strong>Slug global:</strong> identificador legível "{linha}.{codigo}" '
                '(ex.: L01.E001). Gerado uma única vez no primeiro save e <em>imutável</em> — '
                'renomear a linha não altera o slug. Usado em APIs, InfluxDB, logs e URLs.<br>'
                '<strong>UUID:</strong> identificador único para integrações externas (ERP, MQTT). '
                'Sobrevive a qualquer renomeação.'
            ),
            'classes': ('collapse',),
        }),
        ('Informações Básicas', {
            'fields': (
                'linha', 'nome', 'codigo', 'tipo',
                'ordem_na_linha', 'localizacao', 'status'
            ),
            'description': (
                '<strong>Código:</strong> deixe em branco para gerar automaticamente '
                '(E001, E002, ...) sequencial por linha. '
                '<strong>Localização:</strong> deixe em branco para herdar da linha selecionada.'
            ),
        }),
        ('Velocidades e Metas', {
            'fields': ('velocidade_nominal', 'velocidade_maxima', 'meta_oee')
        }),
        ('Limites de Processo', {
            'fields': (
                'temperatura_min', 'temperatura_max',
                'pressao_min', 'pressao_max'
            ),
            'classes': ('collapse',)
        }),
        ('Observações', {
            'fields': ('observacoes',),
            'classes': ('collapse',)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        # slug e uuid SEMPRE readonly (gerados no save, imutáveis).
        # Em criação, código também fica readonly (vazio) para evidenciar
        # que será gerado no save(). Em edição, código permanece editável.
        base = ('slug', 'uuid')
        if obj is None:
            return base + ('codigo',)
        return base

    def save_model(self, request, obj, form, change):
        # Garante que Equipamento.save() rode mesmo via admin (import_export
        # ou um form customizado podem pular). Localização vazia + linha
        # selecionada → herda. Código vazio + linha selecionada → auto-gera.
        super().save_model(request, obj, form, change)

    @admin.action(description='Criar variaveis padrao OPC faltantes')
    def criar_tags_padrao(self, request, queryset):
        total = 0
        for equipamento in queryset:
            antes = equipamento.tags_coleta.count()
            ensure_default_tags_for_equipment(equipamento)
            total += max(0, equipamento.tags_coleta.count() - antes)
        self.message_user(request, f'{total} variaveis padrao criadas.')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        equipamento = self.get_object(request, object_id)
        if equipamento:
            ensure_default_tags_for_equipment(equipamento)
        return super().change_view(request, object_id, form_url, extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<path:object_id>/variaveis/exportar/',
                self.admin_site.admin_view(self.export_variables_view),
                name='equipamentos_equipamento_variables_export',
            ),
            path(
                '<path:object_id>/variaveis/importar/',
                self.admin_site.admin_view(self.import_variables_view),
                name='equipamentos_equipamento_variables_import',
            ),
        ]
        return custom + urls

    def export_variables_view(self, request, object_id):
        equipamento = self.get_object(request, object_id)
        if equipamento is None:
            return redirect('admin:equipamentos_equipamento_changelist')
        if not self.has_view_or_change_permission(request, equipamento):
            raise PermissionDenied

        content = EquipamentoVariaveisWorkbook().export(equipamento)
        timestamp = timezone.localtime().strftime('%Y%m%d-%H%M%S')
        identity = slugify(f'{equipamento.linha.codigo}-{equipamento.codigo}')
        response = HttpResponse(
            content,
            content_type=(
                'application/vnd.openxmlformats-officedocument.'
                'spreadsheetml.sheet'
            ),
        )
        response['Content-Disposition'] = (
            f'attachment; filename="variaveis-{identity}-{timestamp}.xlsx"'
        )
        return response

    def import_variables_view(self, request, object_id):
        equipamento = self.get_object(request, object_id)
        if equipamento is None:
            return redirect('admin:equipamentos_equipamento_changelist')
        if not self.has_change_permission(request, equipamento):
            raise PermissionDenied

        summary = None
        if request.method == 'POST':
            form = EquipamentoVariaveisImportForm(request.POST, request.FILES)
            if form.is_valid():
                dry_run = 'importar' not in request.POST
                try:
                    summary = EquipamentoVariaveisWorkbook().import_data(
                        form.cleaned_data['arquivo'],
                        equipamento,
                        dry_run=dry_run,
                    )
                except Exception as exc:
                    messages.error(request, f'Falha ao ler/importar arquivo: {exc}')
                else:
                    if summary['errors']:
                        messages.error(
                            request,
                            (
                                'Planilha possui erros. Nada foi salvo. '
                                'Corrija as linhas indicadas e tente novamente.'
                            ),
                        )
                    elif dry_run:
                        messages.success(
                            request,
                            'Validação concluída sem erros. Nada foi salvo ainda.',
                        )
                    else:
                        messages.success(
                            request,
                            self._variables_import_message(summary),
                        )
                        return redirect(
                            'admin:equipamentos_equipamento_change',
                            equipamento.pk,
                        )
        else:
            form = EquipamentoVariaveisImportForm()

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': f'Importar variaveis de {equipamento.nome}',
            'form': form,
            'summary': summary,
            'equipamento': equipamento,
            'changelist_url': reverse('admin:equipamentos_equipamento_changelist'),
            'change_url': reverse(
                'admin:equipamentos_equipamento_change',
                args=[equipamento.pk],
            ),
            'export_url': reverse(
                'admin:equipamentos_equipamento_variables_export',
                args=[equipamento.pk],
            ),
        }
        return TemplateResponse(
            request,
            'admin/equipamentos/equipamento/import_variables.html',
            context,
        )

    def _variables_import_message(self, summary):
        return (
            'Variaveis importadas: '
            f'{summary["tags_created"]} variavel(is) criada(s), '
            f'{summary["tags_updated"]} variavel(is) atualizada(s), '
            f'{summary["sensors_created"]} sensor(es) criado(s) e '
            f'{summary["sensors_updated"]} sensor(es) atualizado(s).'
        )


# ==============================
# TAG DE COLETA
# ==============================

@admin.register(TagColeta)
class TagColetaAdmin(ImportExportModelAdmin):
    resource_class = TagColetaResource
    list_display = [
        'equipamento', 'nome_metrica', 'node_id',
        'tipo_dado', 'ativa_badge', 'golden_state'
    ]
    list_filter = ['tipo_dado', 'ativa', 'golden_state', 'equipamento__linha']
    search_fields = ['nome_metrica', 'node_id', 'equipamento__nome']
    autocomplete_fields = ['equipamento']
    fieldsets = (
        ('Associação', {
            'fields': ('equipamento',)
        }),
        ('Configuração da Tag', {
            'fields': (
                'nome_metrica', 'node_id', 'ativa', 'tipo_dado',
                'unidade', 'fator_conversao', 'golden_state'
            )
        }),
    )
    readonly_fields = ['tipo_dado', 'unidade', 'fator_conversao']
    
    def ativa_badge(self, obj):
        if obj.ativa:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    ativa_badge.short_description = 'Ativa'


# ==============================
# SENSOR
# ==============================

@admin.register(Sensor)
class SensorAdmin(ImportExportModelAdmin):
    resource_class = SensorResource
    list_display = ['codigo', 'nome', 'tipo', 'get_local', 'tag_influxdb', 'ativo_badge', 'golden_state']
    list_filter = ['tipo', 'ativo', 'golden_state', 'linha', 'equipamento__linha']
    search_fields = ['codigo', 'nome', 'tag_influxdb']
    fieldsets = (
        ('Localização', {
            'fields': ('linha', 'equipamento'),
            'description': 'Associe o sensor a uma LINHA (para sensores de entrada/saída) OU a um EQUIPAMENTO'
        }),
        ('Informações do Sensor', {
            'fields': ('codigo', 'nome', 'tipo', 'tag_influxdb', 'unidade', 'ativo', 'golden_state'),
            'description': (
                '<strong>Código:</strong> deixe em branco para gerar S001, S002, ... '
                'sequencial por escopo (equipamento ou linha). '
                '<strong>Golden State:</strong> marque apenas variáveis controladas '
                '(setpoints, parâmetros de receita). Leituras de ambiente NÃO entram.'
            ),
        }),
        ('Limites', {
            'fields': ('valor_min', 'valor_max', 'lsl', 'usl', 'nominal'),
            'classes': ('collapse',)
        }),
        ('Observações', {
            'fields': ('observacoes',),
            'classes': ('collapse',)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        # Código readonly em criação para evidenciar a geração automática.
        if obj is None:
            return ('codigo',)
        return super().get_readonly_fields(request, obj)

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


# ==============================
# TURNO DE PRODUÇÃO
# ==============================

@admin.register(TurnoProducao)
class TurnoProducaoAdmin(ImportExportModelAdmin):
    resource_class = TurnoProducaoResource
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


# ==============================
# CALENDÁRIO DE PRODUÇÃO
# ==============================

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


# ==============================
# EVENTOS DE ESTADO
# ==============================

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


# ==============================
# MÉTRICAS DE PRODUÇÃO
# ==============================

@admin.register(MetricaProducao)
class MetricaProducaoAdmin(admin.ModelAdmin):
    list_display = [
        'get_local', 'data_hora', 'periodo',
        'contagem_entrada', 'contagem_saida',
        'descarte', 'percentual_descarte',
        'oee_badge', 'disponibilidade_badge',
        'performance_badge', 'qualidade_badge'
    ]
    list_filter = ['periodo', 'linha', 'equipamento', 'data_hora']
    date_hierarchy = 'data_hora'
    fieldsets = (
        ('Identificação', {
            'fields': ('linha', 'equipamento', 'data_hora', 'periodo', 'turno', 'produto')
        }),
        ('Contadores', {
            'fields': ('contagem_entrada', 'contagem_saida', 'descarte', 'percentual_descarte')
        }),
        ('Velocidades e Produção', {
            'fields': ('velocidade_planejada', 'velocidade_real', 'toneladas_produzidas', 'toneladas_hora', 'vazao_real_ton_hora')
        }),
        ('Tempos (minutos)', {
            'fields': (
                'tempo_programado', 'tempo_disponivel',
                'tempo_producao', 'tempo_parada',
                'tempo_setup', 'tempo_nao_programado'
            )
        }),
        ('KPIs (%)', {
            'fields': ('disponibilidade', 'performance', 'qualidade', 'oee')
        }),
    )
    readonly_fields = [
        'descarte', 'percentual_descarte', 'tempo_disponivel',
        'disponibilidade', 'performance', 'qualidade', 'oee'
    ]
    
    def get_local(self, obj):
        if obj.equipamento:
            return f'{obj.equipamento.nome}'
        return f'Linha {obj.linha.codigo}'
    get_local.short_description = 'Local'
    
    def oee_badge(self, obj):
        try:
            val = float(str(obj.oee).replace(',', '.'))
        except (ValueError, TypeError):
            val = 0.0
            
        if val >= 85:
            color = 'green'
        elif val >= 70:
            color = 'orange'
        else:
            color = 'red'
            
        val_formatted = f"{val:.1f}"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, val_formatted
        )
    oee_badge.short_description = 'OEE'
    
    def disponibilidade_badge(self, obj):
        try:
            val = float(str(obj.disponibilidade).replace(',', '.'))
        except (ValueError, TypeError):
            val = 0.0
        return format_html('<span style="color: blue;">{}%</span>', f"{val:.1f}")
    disponibilidade_badge.short_description = 'A'
    
    def performance_badge(self, obj):
        try:
            val = float(str(obj.performance).replace(',', '.'))
        except (ValueError, TypeError):
            val = 0.0
        return format_html('<span style="color: purple;">{}%</span>', f"{val:.1f}")
    performance_badge.short_description = 'P'
    
    def qualidade_badge(self, obj):
        try:
            val = float(str(obj.qualidade).replace(',', '.'))
        except (ValueError, TypeError):
            val = 0.0
        return format_html('<span style="color: green;">{}%</span>', f"{val:.1f}")
    qualidade_badge.short_description = 'Q'


# ==============================
# DEFEITOS
# ==============================

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


# ==============================
# ORDEM DE PRODUÇÃO
# ==============================

@admin.register(OrdemProducao)
class OrdemProducaoAdmin(ImportExportModelAdmin):
    resource_class = OrdemProducaoResource
    list_display = [
        'codigo', 'linha', 'produto', 'status_badge',
        'meta_total', 'producao_realizada_display', 'percentual_display',
        'data_planejada_inicio'
    ]
    list_filter = ['status', 'linha', 'criado_em']
    search_fields = ['codigo', 'produto__codigo', 'descricao']
    date_hierarchy = 'data_planejada_inicio'
    autocomplete_fields = ['linha', 'produto']
    
    fieldsets = (
        ('Identificação', {
            'fields': ('codigo', 'linha', 'produto', 'status')
        }),
        ('Planejamento', {
            'fields': ('meta_total', 'eficiencia_planejada')
        }),
        ('Formato e Custos', {
            'fields': ('formato_gramas', 'cuc')
        }),
        ('Datas', {
            'fields': ('data_planejada_inicio', 'data_inicio_real', 'data_fim_real')
        }),
        ('Informações Adicionais', {
            'fields': ('descricao', 'observacoes'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['criado_em', 'atualizado_em']
    
    def status_badge(self, obj):
        cores = {
            'PLANEJADA': 'blue',
            'PRODUZINDO': 'green',
            'PAUSADA': 'orange',
            'CONCLUIDA': 'gray',
            'CANCELADA': 'red',
        }
        cor = cores.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            cor,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def producao_realizada_display(self, obj):
        return f'{obj.producao_total_realizada:,}'
    producao_realizada_display.short_description = 'Produzido'
    
    def percentual_display(self, obj):
        perc = obj.percentual_conclusao
        if perc >= 100:
            color = 'green'
        elif perc >= 80:
            color = 'blue'
        elif perc >= 50:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, perc
        )
    percentual_display.short_description = 'Conclusão'


# ==============================
# REGISTRO DE PRODUÇÃO POR TURNO (BI)
# ==============================

@admin.register(RegistroProducaoTurno)
class RegistroProducaoTurnoAdmin(admin.ModelAdmin):
    list_display = [
        'ordem_producao', 'linha', 'data', 'turno',
        'producao_unidades', 'producao_toneladas',
        'oee_badge', 'eficiencia_badge',
        'consolidado_em'
    ]
    list_filter = ['data', 'turno', 'linha', 'ordem_producao__status']
    search_fields = ['ordem_producao__codigo', 'linha__codigo', 'produto__codigo']
    date_hierarchy = 'data'
    autocomplete_fields = ['ordem_producao', 'linha', 'produto', 'turno']
    
    fieldsets = (
        ('Identificação', {
            'fields': ('ordem_producao', 'linha', 'produto', 'data', 'turno')
        }),
        ('Produção', {
            'fields': ('producao_unidades', 'producao_toneladas', 'refugo_unidades', 'refugo_kg')
        }),
        ('Tempos (minutos)', {
            'fields': (
                'tempo_programado_min', 'tempo_disponivel_min',
                'tempo_producao_min', 'tempo_parado_min', 'tempo_setup_min'
            )
        }),
        ('KPIs (%)', {
            'fields': ('disponibilidade', 'performance', 'qualidade', 'oee', 'eficiencia')
        }),
        ('Velocidades', {
            'fields': ('velocidade_media', 'velocidade_planejada')
        }),
        ('Metadados', {
            'fields': ('consolidado_em', 'observacoes'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = [
        'disponibilidade', 'performance', 'qualidade', 'oee',
        'eficiencia', 'velocidade_media', 'consolidado_em'
    ]
    
    def oee_badge(self, obj):
        val = obj.oee
        if val >= 85:
            color = 'green'
        elif val >= 70:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, val
        )
    oee_badge.short_description = 'OEE'
    
    def eficiencia_badge(self, obj):
        val = obj.eficiencia
        if val >= 100:
            color = 'green'
        elif val >= 80:
            color = 'blue'
        elif val >= 60:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, val
        )
    eficiencia_badge.short_description = 'Eficiência'


# ===== EVENTOS DE PARADA & ESTRATÉGIA =====

@admin.register(EventoParada)
class EventoParadaAdmin(admin.ModelAdmin):
    list_display = ['inicio', 'maquina', 'categoria_clp', 'duracao_segundos', 'justificado']
    list_filter = ['categoria_clp', 'maquina', 'justificado']
    search_fields = ['maquina', 'op', 'sku']
    date_hierarchy = 'inicio'

@admin.register(StrategicInitiative)
class StrategicInitiativeAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'status', 'responsavel', 'data_fim', 'percentual_conclusao_badge']
    list_filter = ['status', 'responsavel']
    search_fields = ['titulo', 'descricao']
    date_hierarchy = 'data_inicio'

    def percentual_conclusao_badge(self, obj):
        # Placeholder se não houver lógica
        return obj.get_status_display()
    percentual_conclusao_badge.short_description = 'Status'


# ==============================
# GOLDEN STATE
# ==============================

class GoldenStateVarSnapshotInline(admin.TabularInline):
    model = GoldenStateVarSnapshot
    extra = 0
    fields = ['nome_amigavel', 'tag_influx', 'unidade', 'p10', 'p50', 'p90', 'n_amostras']
    readonly_fields = fields
    can_delete = False


@admin.register(GoldenStateRun)
class GoldenStateRunAdmin(admin.ModelAdmin):
    list_display = [
        'nome', 'linha', 'sku_codigo', 'fonte',
        'score', 'tph_medio', 'refugo_pct', 'oee_medio',
        'inicio', 'ativo', 'criado_por',
    ]
    list_filter = ['fonte', 'ativo', 'linha', 'sku_codigo']
    search_fields = ['nome', 'observacoes', 'linha__codigo']
    date_hierarchy = 'inicio'
    readonly_fields = ['criado_em', 'criado_por', 'score', 'tph_medio',
                       'refugo_pct', 'oee_medio']
    fieldsets = (
        ('Identificação', {
            'fields': ('linha', 'nome', 'sku_codigo', 'fonte', 'ativo'),
        }),
        ('Janela', {
            'fields': ('inicio', 'fim'),
        }),
        ('Métricas calculadas', {
            'fields': ('score', 'tph_medio', 'refugo_pct', 'oee_medio'),
            'description': 'Calculadas automaticamente na captura.',
        }),
        ('Observações', {
            'fields': ('observacoes', 'criado_por', 'criado_em'),
        }),
    )
    inlines = [GoldenStateVarSnapshotInline]


# ==============================
# NODE-RED HISTORY (versionamento estilo Git)
# ==============================

from django.urls import path, reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseRedirect
import json as _json


@admin.register(NodeRedSnapshot)
class NodeRedSnapshotAdmin(admin.ModelAdmin):
    """Linha do tempo dos deploys do Node-RED.

    Cada entrada é uma versão imutável do flows.json, capturada via
    nginx mirror toda vez que um usuário clica Deploy no editor.

    Funcionalidades:
      - Lista cronológica com autor, ação, diff resumido.
      - Botão "Ver diff" abre página de comparação com versão anterior.
      - Botão "Restaurar" reescreve essa versão no Node-RED via API
        admin (com confirmação).
    """
    list_display = [
        'id', 'criado_em_br', 'projeto_badge', 'usuario_nome', 'acao_badge',
        'diff_resumo', 'num_nodes', 'hash_curto', 'acoes_botoes',
    ]
    list_filter = ['projeto', 'acao', 'usuario']
    search_fields = ['usuario_nome', 'descricao', 'hash_sha', 'projeto']
    date_hierarchy = 'criado_em'
    readonly_fields = [
        'criado_em', 'projeto', 'usuario', 'usuario_nome', 'acao', 'hash_sha',
        'num_nodes', 'size_bytes', 'parent', 'nodes_adicionados',
        'nodes_removidos', 'nodes_modificados', 'flows_json_preview',
    ]
    exclude = ['flows_json']
    actions = None  # remove "Excluir selecionados" — versões são imutáveis

    def has_add_permission(self, request):
        return False  # snapshots só são criados via mirror nginx

    def has_delete_permission(self, request, obj=None):
        # Apaga histórico só superuser, e mesmo assim com cautela.
        return request.user.is_superuser

    def criado_em_br(self, obj):
        return obj.criado_em.strftime('%d/%m/%Y %H:%M:%S')
    criado_em_br.short_description = 'Quando'
    criado_em_br.admin_order_field = 'criado_em'

    def acao_badge(self, obj):
        cores = {
            'DEPLOY': ('#1565c0', '#e3f2fd'),
            'RESTORE': ('#a06200', '#fbe9c8'),
            'INITIAL': ('#1f7a3b', '#dff4e3'),
        }
        fg, bg = cores.get(obj.acao, ('#212121', '#f0f2f5'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:10px;font-size:11px;font-weight:600;">{}</span>',
            bg, fg, obj.get_acao_display(),
        )
    acao_badge.short_description = 'Ação'

    def projeto_badge(self, obj):
        """Mostra o projeto Node-RED; vazio (legacy) aparece como '—' cinza."""
        if not obj.projeto:
            return format_html(
                '<span style="color:#888;font-size:11px;" '
                'title="Snapshot anterior à feature Projects ou capturado com '
                'Projects desligado">— global —</span>'
            )
        return format_html(
            '<span style="background:#eef3ff;color:#1a4a8c;padding:2px 8px;'
            'border-radius:10px;font-size:11px;font-weight:600;" '
            'title="Projeto Node-RED">📁 {}</span>',
            obj.projeto,
        )
    projeto_badge.short_description = 'Projeto'
    projeto_badge.admin_order_field = 'projeto'
    acao_badge.admin_order_field = 'acao'

    def diff_resumo(self, obj):
        if obj.acao == 'INITIAL':
            return format_html('<span style="color:#1f7a3b;">📦 snapshot inicial</span>')
        parts = []
        if obj.nodes_adicionados:
            parts.append(f'<span style="color:#1f7a3b;">+{obj.nodes_adicionados}</span>')
        if obj.nodes_removidos:
            parts.append(f'<span style="color:#b53a2b;">−{obj.nodes_removidos}</span>')
        if obj.nodes_modificados:
            parts.append(f'<span style="color:#a06200;">~{obj.nodes_modificados}</span>')
        return format_html('&nbsp;'.join(parts) or '—')
    diff_resumo.short_description = 'Diff'

    def hash_curto(self, obj):
        return format_html('<code style="font-size:11px;">{}</code>', obj.hash_sha[:10])
    hash_curto.short_description = 'Hash'

    def acoes_botoes(self, obj):
        diff_url = reverse('admin:nodered-snapshot-diff', args=[obj.id])
        restore_url = reverse('admin:nodered-snapshot-restore', args=[obj.id])
        return format_html(
            '<a href="{}" style="margin-right:8px;font-size:12px;">🔍 Diff</a>'
            '<a href="{}" style="font-size:12px;color:#a06200;font-weight:600;" '
            'onclick="return confirm(\'Restaurar esta versão no Node-RED? '
            'Esta ação substitui o fluxograma atual.\');">↩ Restaurar</a>',
            diff_url, restore_url,
        )
    acoes_botoes.short_description = 'Ações'

    def flows_json_preview(self, obj):
        try:
            preview = _json.dumps(obj.flows_json, indent=2, ensure_ascii=False)[:2000]
        except Exception:
            preview = '(não foi possível serializar)'
        return format_html(
            '<pre style="background:#f7f8fa;border:1px solid #d8dee5;'
            'padding:10px;border-radius:4px;max-height:400px;overflow:auto;'
            'font-size:11px;">{}</pre>',
            preview + ('\n...' if len(preview) >= 2000 else ''),
        )
    flows_json_preview.short_description = 'Conteúdo (preview)'

    # ---- URLs customizadas no admin ----
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<int:snap_id>/diff/',
                self.admin_site.admin_view(self.view_diff),
                name='nodered-snapshot-diff',
            ),
            path(
                '<int:snap_id>/restore/',
                self.admin_site.admin_view(self.view_restore),
                name='nodered-snapshot-restore',
            ),
            path(
                'projects/',
                self.admin_site.admin_view(self.view_projects),
                name='nodered-projects',
            ),
            path(
                'projects/sync/',
                self.admin_site.admin_view(self.view_projects_sync),
                name='nodered-projects-sync',
            ),
            path(
                'projects/<str:nome>/capture/',
                self.admin_site.admin_view(self.view_project_capture),
                name='nodered-project-capture',
            ),
        ]
        return custom + urls

    # ---- Tela "Projetos Node-RED" ----
    def changelist_view(self, request, extra_context=None):
        """Injeta no topo da changelist um link rápido para a tela de Projetos."""
        extra_context = extra_context or {}
        extra_context['nodered_projects_url'] = reverse('admin:nodered-projects')
        return super().changelist_view(request, extra_context=extra_context)

    def view_projects(self, request):
        """Lista live de projetos do Node-RED + contagem de snapshots Django.

        Mostra projetos que existem no /data/projects/ ainda que nunca
        tenham sido deployados; com botões para "Capturar agora" (cria
        um snapshot INITIAL com o estado atual) e "Sincronizar tudo".
        """
        from django.template.response import TemplateResponse
        from .nodered_history_views import _listar_projetos
        from django.db.models import Count, Max

        info = _listar_projetos()
        nomes = info['projetos']
        active = info['active']

        stats = {
            s['projeto']: s for s in
            NodeRedSnapshot.objects
            .filter(projeto__in=nomes)
            .values('projeto')
            .annotate(total=Count('id'), ultimo_id=Max('id'))
        }
        ult_ids = [s['ultimo_id'] for s in stats.values() if s.get('ultimo_id')]
        ult_map = {s.projeto: s for s in NodeRedSnapshot.objects.filter(id__in=ult_ids)}

        items = []
        for nome in nomes:
            st = stats.get(nome, {'total': 0})
            ult = ult_map.get(nome)
            items.append({
                'nome': nome,
                'ativo': nome == active,
                'snapshots_total': st.get('total', 0),
                'ultimo': ult,  # objeto NodeRedSnapshot ou None
                'capture_url': reverse('admin:nodered-project-capture', args=[nome]),
            })

        ctx = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Projetos Node-RED',
            'projetos': items,
            'active': active,
            'projects_enabled': bool(nomes),
            'sync_url': reverse('admin:nodered-projects-sync'),
            'changelist_url': reverse('admin:equipamentos_noderedsnapshot_changelist'),
        }
        return TemplateResponse(request, 'admin/nodered_projects.html', ctx)

    def view_projects_sync(self, request):
        from .nodered_history_views import sincronizar_projetos
        stats = sincronizar_projetos()
        partes = []
        if stats['novos']:
            partes.append(f'{len(stats["novos"])} novo(s): {", ".join(stats["novos"])}')
        if stats['ja_existiam']:
            partes.append(f'{len(stats["ja_existiam"])} já estavam sincronizados')
        if stats['sem_flow']:
            partes.append(f'{len(stats["sem_flow"])} sem flow acessível: {", ".join(stats["sem_flow"])}')
        if not partes:
            messages.info(request, 'Nenhum projeto encontrado no Node-RED.')
        else:
            messages.success(request, 'Sincronização: ' + ' · '.join(partes))
        return redirect('admin:nodered-projects')

    def view_project_capture(self, request, nome):
        """Captura snapshot do projeto. Se request tem ?trocar=1, autoriza
        trocar o projeto ativo do Node-RED (intencionalmente disruptivo).
        """
        from .nodered_history_views import (
            _capturar_snapshot_projeto, _projeto_ativo,
        )
        permitir = request.GET.get('trocar') == '1' or request.POST.get('trocar') == '1'
        ativo = _projeto_ativo(use_cache=False)
        if nome != ativo and not permitir:
            messages.warning(
                request,
                f'O projeto "{nome}" não está ativo (atual: "{ativo}"). '
                f'Para capturar agora, use o botão "Trocar e capturar" '
                f'(isso interrompe os flows de "{ativo}" durante a troca).'
            )
            return redirect('admin:nodered-projects')
        snap = _capturar_snapshot_projeto(
            nome,
            usuario_nome=request.user.username,
            acao=NodeRedSnapshot.Acao.INITIAL,
            permitir_trocar=permitir,
        )
        if snap is None:
            messages.error(
                request,
                f'Não consegui ler o flow.json do projeto "{nome}". '
                'Verifique se o projeto existe e tem conteúdo deployado.'
            )
        else:
            extra = ' (projeto ativo trocado!)' if permitir and nome != ativo else ''
            messages.success(
                request,
                f'Snapshot #{snap.id} capturado para "{nome}" '
                f'({snap.num_nodes} nós, hash {snap.hash_sha[:8]}){extra}.'
            )
        return redirect('admin:nodered-projects')

    def view_diff(self, request, snap_id):
        from django.template.response import TemplateResponse
        snap = NodeRedSnapshot.objects.filter(pk=snap_id).first()
        if not snap:
            messages.error(request, 'Snapshot não encontrado')
            return redirect('admin:equipamentos_noderedsnapshot_changelist')

        def por_id(lst):
            return {n.get('id'): n for n in (lst or []) if isinstance(n, dict) and n.get('id')}

        # Normaliza cada nó para um dict com TODAS as chaves esperadas — o
        # Django 5 levanta VariableDoesNotExist se o template acessar uma
        # chave inexistente, então o template fica simples com este shape.
        def fmt_node(n):
            return {
                'id': n.get('id', '?'),
                'type': n.get('type') or '?',
                'name': n.get('name') or n.get('label') or '(sem nome)',
                'z': n.get('z', ''),
                'json_pretty': _json.dumps(n, indent=2, ensure_ascii=False, sort_keys=True),
            }

        novos = por_id(snap.flows_json)
        antigos = por_id(snap.parent.flows_json) if snap.parent else {}
        adicionados = [fmt_node(novos[i]) for i in (set(novos) - set(antigos))]
        removidos = [fmt_node(antigos[i]) for i in (set(antigos) - set(novos))]
        modificados = []
        for nid in (set(novos) & set(antigos)):
            if novos[nid] != antigos[nid]:
                campos = sorted(
                    k for k in (set(novos[nid]) | set(antigos[nid]))
                    if novos[nid].get(k) != antigos[nid].get(k)
                )
                modificados.append({
                    'antes': fmt_node(antigos[nid]),
                    'depois': fmt_node(novos[nid]),
                    'campos': campos,
                })

        ctx = {
            **self.admin_site.each_context(request),
            'snap': snap,
            'parent': snap.parent,
            'adicionados': adicionados,
            'removidos': removidos,
            'modificados': modificados,
            'opts': self.model._meta,
            'title': f'Diff do snapshot #{snap.id}',
        }
        return TemplateResponse(request, 'admin/nodered_diff.html', ctx)

    def view_restore(self, request, snap_id):
        # Reutiliza a lógica pura (sem decorators DRF)
        from .nodered_history_views import restore_snapshot_internal
        result = restore_snapshot_internal(snap_id, request.user)
        if result['ok']:
            messages.success(request, result.get('mensagem', 'Restaurado.'))
        else:
            messages.error(request, result.get('detail', 'Falha ao restaurar.'))
        return redirect('admin:equipamentos_noderedsnapshot_changelist')


# ==============================
# USUÁRIOS DO NODE-RED
# ==============================
#
# settings.js do Node-RED consulta /api/auth/nodered/{authenticate,user}/
# para validar login. Tudo gerenciado aqui: criar/editar usuário + senha
# vira hash automaticamente, sem nenhum hash-pw nem reinício.


class NodeRedUserForm(forms.ModelForm):
    """Formulário do NodeRedUser:
    - Senha é digitada em texto puro (campo PasswordInput) e armazenada
      como hash via `user.set_password()`.
    - Em modo edição, a senha fica opcional — vazio significa "manter".
    """

    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        label='Senha',
        help_text='Em criação: obrigatória. Em edição: deixe vazio para manter a senha atual.',
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        label='Confirmar senha',
    )

    class Meta:
        model = NodeRedUser
        # password_hash é gerado a partir de `password` no save() — não aparece
        # como campo editável aqui.
        fields = [
            'username', 'nivel', 'permissoes', 'ativo', 'observacoes',
            'password', 'password_confirm',
        ]

    def clean(self):
        cleaned = super().clean()
        pwd = cleaned.get('password') or ''
        confirm = cleaned.get('password_confirm') or ''
        # Em criação (sem id), senha é obrigatória.
        creating = self.instance.pk is None
        if creating and not pwd:
            self.add_error('password', 'Senha obrigatória ao criar um usuário.')
        if pwd and pwd != confirm:
            self.add_error('password_confirm', 'Confirmação não confere com a senha.')
        if pwd and len(pwd) < 6:
            self.add_error('password', 'Senha muito curta (mínimo 6 caracteres).')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        pwd = self.cleaned_data.get('password') or ''
        if pwd:
            user.set_password(pwd)
        if commit:
            user.save()
        return user


@admin.register(NodeRedUser)
class NodeRedUserAdmin(admin.ModelAdmin):
    form = NodeRedUserForm
    list_display = ['username', 'nivel', 'ativo', 'ultimo_login_em', 'observacoes']
    list_filter = ['nivel', 'ativo']
    search_fields = ['username', 'observacoes']
    readonly_fields = ['criado_em', 'atualizado_em', 'ultimo_login_em']

    # O service-user `_mis_internal_` é gerenciado pelo próprio Django para
    # falar com a admin API do Node-RED. Esconder do admin evita que alguém
    # apague/desative por engano e quebre snapshots/restore. Superusuário
    # consegue ver passando ?show_system=1.
    SYSTEM_USERNAMES = ('_mis_internal_',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.GET.get('show_system') == '1' and request.user.is_superuser:
            return qs
        return qs.exclude(username__in=self.SYSTEM_USERNAMES)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.username in self.SYSTEM_USERNAMES:
            return False
        return super().has_delete_permission(request, obj)
    fieldsets = (
        ('Identificação', {
            'fields': ('username', 'ativo', 'observacoes'),
        }),
        ('Senha', {
            'fields': ('password', 'password_confirm'),
            'description': (
                'A senha é armazenada apenas como hash. Em uma edição, deixe '
                'os campos vazios para manter a senha atual.'
            ),
        }),
        ('Permissões no Node-RED', {
            'fields': ('nivel', 'permissoes'),
            'description': (
                'Use <b>Administrador</b> para deploy/edição, <b>Somente leitura</b> '
                'para operadores de visualização. Use <b>Customizado</b> + lista '
                'em "Permissões granulares" para casos específicos.'
            ),
        }),
        ('Auditoria', {
            'fields': ('criado_em', 'atualizado_em', 'ultimo_login_em'),
            'classes': ('collapse',),
        }),
    )
