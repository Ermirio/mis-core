# admin.py

from django.contrib import admin, messages
from django import forms
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from .models import (
    ConexaoOPCUAServidor, Variavel, Linha, Equipamento, Impressora, InkjetPrinter,
    Produto, Formato, FormatoVariavel, ConfiguracaoEquipamentoVariavel,
    DiscrepanciaSKU, TrocaSKU, LogEquipamentoTroca, StatusLinha,
    AssociacaoProdutoLinha
)


# ==================== FORM: DUPLICAR FORMATO ====================

class DuplicarFormatoForm(forms.Form):
    novo_nome = forms.CharField(
        max_length=100,
        label="Novo nome do formato",
        help_text="Deve ser único. Ex.: '800g-L21 — Cópia'",
        widget=forms.TextInput(attrs={'size': '60'}),
    )

    def clean_novo_nome(self):
        nome = self.cleaned_data['novo_nome'].strip()
        if not nome:
            raise forms.ValidationError("O nome não pode ser vazio.")
        if Formato.objects.filter(nome=nome).exists():
            raise forms.ValidationError(f"Já existe um formato com o nome \"{nome}\".")
        return nome

# ==================== ADMIN PARA MODELOS BASE ====================

@admin.register(ConexaoOPCUAServidor)
class ConexaoOPCUAServidorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'url', 'caminho_plc', 'timeout')
    search_fields = ('nome', 'url')
    list_filter = ('nome',)
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'url')
        }),
        ('Configurações', {
            'fields': ('caminho_plc', 'timeout')
        }),
    )

@admin.register(Variavel)
class VariavelAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'descricao', 'get_equipamentos_que_usam')
    search_fields = ('nome', 'descricao')
    list_filter = ('tipo',)
    filter_horizontal = ('equipamentos_que_usam',)
    fieldsets = (
        ('Informações da Variável', {
            'fields': ('nome', 'tipo', 'descricao')
        }),
        ('Equipamentos', {
            'fields': ('equipamentos_que_usam',),
            'description': 'Selecione os equipamentos que utilizam esta variável'
        }),
    )

    def get_equipamentos_que_usam(self, obj):
        """Retorna os equipamentos que usam esta variável"""
        equipamentos = obj.equipamentos_que_usam.all()
        if equipamentos:
            return ", ".join([f"{eq.nome} ({eq.get_tipo_equipamento_display()})" for eq in equipamentos])
        return "Nenhum equipamento"
    get_equipamentos_que_usam.short_description = "Equipamentos que usam"

@admin.register(Equipamento)
class EquipamentoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo_equipamento', 'conexao_opcua', 'ativa', 'get_linhas', 'get_variaveis_count')
    search_fields = ('nome',)
    list_filter = ('tipo_equipamento', 'ativa', 'conexao_opcua')
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'tipo_equipamento', 'ativa')
        }),
        ('Conexão', {
            'fields': ('conexao_opcua',)
        }),
    )

    def get_linhas(self, obj):
        """Retorna as linhas associadas ao equipamento"""
        return ", ".join([linha.nome for linha in obj.linhas.all()])
    get_linhas.short_description = "Linhas"

    def get_variaveis_count(self, obj):
        """Retorna a quantidade de variáveis utilizadas"""
        return obj.variaveis_utilizadas.count()
    get_variaveis_count.short_description = "Qtd. Variáveis"

@admin.register(Impressora)
class ImpressoraAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ip', 'pasta_destino', 'ativa', 'get_linhas')
    search_fields = ('nome', 'ip')
    list_filter = ('ativa',)
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'ativa')
        }),
        ('Configurações de Rede', {
            'fields': ('ip', 'pasta_destino')
        }),
    )

    def get_linhas(self, obj):
        """Retorna as linhas associadas à impressora"""
        return ", ".join([linha.nome for linha in obj.linhas.all()])
    get_linhas.short_description = "Linhas"

@admin.register(InkjetPrinter)
class InkjetPrinterAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ip_address', 'port', 'format_name', 'ativa', 'get_linhas')
    search_fields = ('nome', 'ip_address', 'format_name')
    list_filter = ('ativa',)
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'ativa')
        }),
        ('Configurações de Rede', {
            'fields': ('ip_address', 'port')
        }),
        ('Configurações de Formato', {
            'fields': ('format_name',)
        }),
    )

    def get_linhas(self, obj):
        """Retorna as linhas associadas à impressora Inkjet"""
        return ", ".join([linha.nome for linha in obj.linhas.all()])
    get_linhas.short_description = "Linhas"

# ==================== ADMIN PARA LINHA ====================

@admin.register(Linha)
class LinhaAdmin(admin.ModelAdmin):
    list_display = (
        'nome', 'descricao', 'ativa', 
        'get_equipamentos_plc', 'get_impressoras_3m', 'get_impressoras_inkjet'
    )
    search_fields = ('nome', 'descricao')
    list_filter = ('ativa',)
    filter_horizontal = ('equipamentos', 'impressoras_3m', 'impressoras_inkjet')
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'descricao', 'ativa')
        }),
        ('Equipamentos PLC', {
            'fields': ('equipamentos',),
            'description': 'Equipamentos PLC (enchedoras, dosadoras, seladoras, etc.)'
        }),
        ('Impressoras', {
            'fields': ('impressoras_3m', 'impressoras_inkjet'),
            'description': 'Impressoras 3M e Inkjet associadas à linha'
        }),
    )

    def get_equipamentos_plc(self, obj):
        """Retorna os equipamentos PLC da linha"""
        equipamentos = obj.equipamentos.all()
        if equipamentos:
            return ", ".join([f"{eq.nome} ({eq.get_tipo_equipamento_display()})" for eq in equipamentos])
        return "Nenhum equipamento"
    get_equipamentos_plc.short_description = "Equipamentos PLC"

    def get_impressoras_3m(self, obj):
        """Retorna as impressoras 3M da linha"""
        impressoras = obj.impressoras_3m.all()
        if impressoras:
            return ", ".join([f"{imp.nome} ({imp.ip})" for imp in impressoras])
        return "Nenhuma impressora 3M"
    get_impressoras_3m.short_description = "Impressoras 3M"

    def get_impressoras_inkjet(self, obj):
        """Retorna as impressoras Inkjet da linha"""
        impressoras = obj.impressoras_inkjet.all()
        if impressoras:
            return ", ".join([f"{ink.nome} ({ink.ip_address}:{ink.port})" for ink in impressoras])
        return "Nenhuma impressora Inkjet"
    get_impressoras_inkjet.short_description = "Impressoras Inkjet"

# ==================== ADMIN PARA FORMATO ====================

class FormatoVariavelInline(admin.TabularInline):
    model = FormatoVariavel
    extra = 1
    fields = ('variavel', 'valor')
    autocomplete_fields = ['variavel']  # Melhora a usabilidade

@admin.register(Formato)
class FormatoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'descricao', 'get_variaveis_count', 'get_produtos_count', 'criado_em', 'atualizado_em')
    search_fields = ('nome', 'descricao')
    list_filter = ('criado_em', 'atualizado_em')
    readonly_fields = ('criado_por', 'atualizado_por', 'criado_em', 'atualizado_em')
    inlines = [FormatoVariavelInline]
    fieldsets = (
        ('Informações do Formato', {
            'fields': ('nome', 'descricao')
        }),
        ('Auditoria', {
            'fields': ('criado_por', 'atualizado_por', 'criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )

    # ---- métodos de exibição ----

    def get_variaveis_count(self, obj):
        return obj.variaveis.count()
    get_variaveis_count.short_description = "Qtd. Variáveis"

    def get_produtos_count(self, obj):
        return AssociacaoProdutoLinha.objects.filter(formato=obj).count()
    get_produtos_count.short_description = "Qtd. Produtos"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.criado_por = request.user
        obj.atualizado_por = request.user
        super().save_model(request, obj, form, change)

    # ---- duplicar formato ----

    def get_urls(self):
        custom_urls = [
            path(
                '<int:pk>/duplicar/',
                self.admin_site.admin_view(self.duplicar_view),
                name='ips_formato_duplicar',
            ),
        ]
        return custom_urls + super().get_urls()

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['duplicar_url'] = reverse('admin:ips_formato_duplicar', args=[object_id])
        return super().change_view(request, object_id, form_url, extra_context)

    def duplicar_view(self, request, pk):
        formato_original = get_object_or_404(Formato, pk=pk)

        if not self.has_add_permission(request):
            self.message_user(request, "Sem permissão para criar formatos.", messages.ERROR)
            return redirect(reverse('admin:ips_formato_change', args=[pk]))

        if request.method == 'POST':
            form = DuplicarFormatoForm(request.POST)
            if form.is_valid():
                novo_nome = form.cleaned_data['novo_nome']
                with transaction.atomic():
                    novo_formato = Formato.objects.create(
                        nome=novo_nome,
                        descricao=formato_original.descricao,
                        criado_por=request.user,
                        atualizado_por=request.user,
                    )
                    FormatoVariavel.objects.bulk_create([
                        FormatoVariavel(
                            formato=novo_formato,
                            variavel=fv.variavel,
                            valor=fv.valor,
                            criado_por=request.user,
                            atualizado_por=request.user,
                        )
                        for fv in formato_original.variaveis.select_related('variavel').all()
                    ])
                n = novo_formato.variaveis.count()
                self.message_user(
                    request,
                    f'Formato "{novo_formato.nome}" criado com {n} variável(is) copiada(s).',
                    messages.SUCCESS,
                )
                return redirect(reverse('admin:ips_formato_change', args=[novo_formato.pk]))
        else:
            form = DuplicarFormatoForm(
                initial={'novo_nome': f'{formato_original.nome} — Cópia'}
            )

        context = {
            **self.admin_site.each_context(request),
            'title': f'Duplicar Formato: {formato_original.nome}',
            'form': form,
            'formato': formato_original,
            'opts': self.model._meta,
            'has_view_permission': self.has_view_permission(request),
        }
        return TemplateResponse(request, 'admin/ips/formato/duplicar.html', context)

@admin.register(FormatoVariavel)
class FormatoVariavelAdmin(admin.ModelAdmin):
    list_display = (
        'formato', 'get_variavel_nome', 'get_variavel_tipo', 'valor', 
        'criado_em', 'atualizado_em'
    )
    search_fields = ('formato__nome', 'variavel__nome', 'valor')
    list_filter = ('variavel__tipo', 'criado_em', 'atualizado_em')
    readonly_fields = ('criado_por', 'atualizado_por', 'criado_em', 'atualizado_em')
    fieldsets = (
        ('Configuração da Variável', {
            'fields': ('formato', 'variavel', 'valor')
        }),
        ('Auditoria', {
            'fields': ('criado_por', 'atualizado_por', 'criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )

    def get_variavel_nome(self, obj):
        """Retorna o nome da variável"""
        return obj.variavel.nome
    get_variavel_nome.short_description = "Variável"

    def get_variavel_tipo(self, obj):
        """Retorna o tipo da variável"""
        return obj.variavel.get_tipo_display()
    get_variavel_tipo.short_description = "Tipo"

    def save_model(self, request, obj, form, change):
        """Salva o modelo com informações de auditoria"""
        if not change:
            obj.criado_por = request.user
        obj.atualizado_por = request.user
        super().save_model(request, obj, form, change)

# ==================== ADMIN PARA CONFIGURAÇÃO EQUIPAMENTO VARIÁVEL ====================

@admin.register(ConfiguracaoEquipamentoVariavel)
class ConfiguracaoEquipamentoVariavelAdmin(admin.ModelAdmin):
    list_display = (
        'get_equipamento_nome', 'get_equipamento_tipo', 'get_variavel_nome', 
        'get_variavel_tipo', 'tag_plc', 'criado_em', 'atualizado_em'
    )
    search_fields = ('equipamento__nome', 'variavel_mestra__nome', 'tag_plc')
    list_filter = ('equipamento__tipo_equipamento', 'variavel_mestra__tipo', 'criado_em')
    readonly_fields = ('criado_por', 'atualizado_por', 'criado_em', 'atualizado_em')
    fieldsets = (
        ('Configuração', {
            'fields': ('equipamento', 'variavel_mestra', 'tag_plc')
        }),
        ('Auditoria', {
            'fields': ('criado_por', 'atualizado_por', 'criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )

    def get_equipamento_nome(self, obj):
        """Retorna o nome do equipamento"""
        return obj.equipamento.nome
    get_equipamento_nome.short_description = "Equipamento"

    def get_equipamento_tipo(self, obj):
        """Retorna o tipo do equipamento"""
        return obj.equipamento.get_tipo_equipamento_display()
    get_equipamento_tipo.short_description = "Tipo Equipamento"

    def get_variavel_nome(self, obj):
        """Retorna o nome da variável mestra"""
        return obj.variavel_mestra.nome
    get_variavel_nome.short_description = "Variável Mestra"

    def get_variavel_tipo(self, obj):
        """Retorna o tipo da variável mestra"""
        return obj.variavel_mestra.get_tipo_display()
    get_variavel_tipo.short_description = "Tipo Variável"

    def save_model(self, request, obj, form, change):
        """Salva o modelo com informações de auditoria"""
        if not change:
            obj.criado_por = request.user
        obj.atualizado_por = request.user
        super().save_model(request, obj, form, change)

# ==================== ADMIN PARA PRODUTO (COM A NOVA LÓGICA) ====================

# Inline para gerenciar as associações de linha e formato diretamente no Produto
class AssociacaoProdutoLinhaInline(admin.TabularInline):
    model = AssociacaoProdutoLinha
    extra = 1
    # Usar autocomplete_fields para facilitar a seleção
    autocomplete_fields = ['linha', 'formato']
    verbose_name = "Associação com Linha e Formato"
    verbose_name_plural = "Associações com Linhas e Formatos"
    fields = ('linha', 'formato', 'criado_em', 'atualizado_em')
    readonly_fields = ('criado_em', 'atualizado_em')

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = (
        'sku', 'descricao', 'dun14', 'validade', 
        'numero_op', 'status_op', 'get_linhas_associadas'
    )
    search_fields = ('sku', 'descricao', 'dun14', 'numero_op')
    list_filter = ('status_op', 'criado_em', 'atualizado_em')
    readonly_fields = ('criado_por', 'atualizado_por', 'criado_em', 'atualizado_em')
    
    # Adicionar o inline de associação
    inlines = [AssociacaoProdutoLinhaInline]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('sku', 'descricao')
        }),
        ('Códigos e Identificação', {
            'fields': ('dun14', 'ean', 'filme')
        }),
        ('Informações de Produção', {
            'fields': ('validade', 'id_ordem_prod', 'numero_op', 'quantidade_por_pallet', 'status_op', 'dataop_str')
        }),
        # A seção de associações agora é gerenciada pelo inline
        ('Auditoria', {
            'fields': ('criado_por', 'atualizado_por', 'criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )

    def get_linhas_associadas(self, obj):
        """Retorna as linhas associadas ao produto através do novo modelo."""
        linhas = [assoc.linha.nome for assoc in obj.associacoes_linha.all()]
        return ", ".join(linhas) if linhas else "Nenhuma"
    get_linhas_associadas.short_description = "Linhas Associadas"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.criado_por = request.user
        obj.atualizado_por = request.user
        super().save_model(request, obj, form, change)

# Registrar o modelo de associação separadamente para visualização
@admin.register(AssociacaoProdutoLinha)
class AssociacaoProdutoLinhaAdmin(admin.ModelAdmin):
    list_display = ('produto', 'linha', 'formato', 'criado_em', 'atualizado_em')
    search_fields = ('produto__sku', 'produto__descricao', 'linha__nome', 'formato__nome')
    list_filter = ('linha', 'formato', 'criado_em')
    readonly_fields = ('criado_em', 'atualizado_em')
    fieldsets = (
        ('Associação', {
            'fields': ('produto', 'linha', 'formato')
        }),
        ('Auditoria', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )

# ==================== ADMIN PARA LOGS E TROCAS ====================

class LogEquipamentoTrocaInline(admin.TabularInline):
    model = LogEquipamentoTroca
    extra = 0
    readonly_fields = (
        'tipo_equipamento', 'nome_equipamento', 'status', 'mensagem', 
        'variaveis_escritas', 'variaveis_total', 'tempo_execucao', 'data_hora'
    )
    fields = (
        'tipo_equipamento', 'nome_equipamento', 'status', 'mensagem',
        'variaveis_escritas', 'variaveis_total', 'tempo_execucao'
    )
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(TrocaSKU)
class TrocaSKUAdmin(admin.ModelAdmin):
    list_display = (
        'linha', 'sku_trocado', 'descricao', 'data_hora', 'sucesso',
        'equipamentos_processados', 'equipamentos_sucesso', 'equipamentos_falha',
        'tempo_execucao'
    )
    search_fields = ('linha', 'sku_trocado', 'descricao')
    list_filter = ('linha', 'sucesso', 'data_hora')
    readonly_fields = (
        'data_hora', 'equipamentos_processados', 'equipamentos_sucesso', 
        'equipamentos_falha', 'tempo_execucao'
    )
    inlines = [LogEquipamentoTrocaInline]
    fieldsets = (
        ('Informações da Troca', {
            'fields': ('linha', 'sku_trocado', 'descricao', 'data_hora', 'sucesso')
        }),
        ('Dados do SKU', {
            'fields': ('dun14', 'validade', 'numero_op')
        }),
        ('Resumo da Execução', {
            'fields': (
                'equipamentos_processados', 'equipamentos_sucesso', 
                'equipamentos_falha', 'tempo_execucao'
            )
        }),
        ('Metadados', {
            'fields': ('usuario', 'ip_origem', 'detalhes'),
            'classes': ('collapse',)
        }),
    )

@admin.register(LogEquipamentoTroca)
class LogEquipamentoTrocaAdmin(admin.ModelAdmin):
    list_display = (
        'troca', 'tipo_equipamento', 'nome_equipamento', 'status',
        'variaveis_escritas', 'variaveis_total', 'get_taxa_sucesso', 'tempo_execucao'
    )
    search_fields = ('nome_equipamento', 'troca__sku_trocado', 'troca__linha')
    list_filter = ('tipo_equipamento', 'status', 'data_hora')
    readonly_fields = ('data_hora',)
    fieldsets = (
        ('Informações do Log', {
            'fields': ('troca', 'tipo_equipamento', 'nome_equipamento', 'status', 'data_hora')
        }),
        ('Detalhes da Execução', {
            'fields': ('mensagem', 'erro_detalhado', 'tempo_execucao')
        }),
        ('Variáveis', {
            'fields': ('variaveis_escritas', 'variaveis_total')
        }),
        ('Dados Técnicos', {
            'fields': ('ip_equipamento', 'conexao_opcua'),
            'classes': ('collapse',)
        }),
    )

    def get_taxa_sucesso(self, obj):
        """Retorna a taxa de sucesso das variáveis"""
        return f"{obj.get_taxa_sucesso_variaveis()}%"
    get_taxa_sucesso.short_description = "Taxa Sucesso"

@admin.register(DiscrepanciaSKU)
class DiscrepanciaSKUAdmin(admin.ModelAdmin):
    list_display = ('linha', 'sku_esperado', 'sku_atual', 'data_hora', 'resolvida')
    search_fields = ('linha', 'sku_esperado', 'sku_atual')
    list_filter = ('linha', 'resolvida', 'data_hora')
    readonly_fields = ('data_hora',)
    fieldsets = (
        ('Informações da Discrepância', {
            'fields': ('linha', 'sku_esperado', 'sku_atual', 'data_hora')
        }),
        ('Status', {
            'fields': ('resolvida', 'observacoes')
        }),
    )

@admin.register(StatusLinha)
class StatusLinhaAdmin(admin.ModelAdmin):
    list_display = (
        'linha', 'sku_atual', 'descricao_sku_atual', 'data_ultima_troca',
        'equipamentos_ativos', 'equipamentos_total', 'get_taxa_equipamentos_ativos'
    )
    search_fields = ('linha__nome', 'sku_atual', 'descricao_sku_atual')
    list_filter = ('linha', 'data_ultima_troca')
    readonly_fields = ('data_ultima_troca',)
    fieldsets = (
        ('Informações da Linha', {
            'fields': ('linha', 'sku_atual', 'descricao_sku_atual', 'data_ultima_troca')
        }),
        ('Status dos Equipamentos', {
            'fields': ('equipamentos_ativos', 'equipamentos_total')
        }),
    )

    def get_taxa_equipamentos_ativos(self, obj):
        """Retorna a taxa de equipamentos ativos"""
        return f"{obj.get_taxa_equipamentos_ativos()}%"
    get_taxa_equipamentos_ativos.short_description = "Taxa Equipamentos Ativos"

# Configurações adicionais do admin
admin.site.site_header = "Administração do Sistema de Produção"
admin.site.site_title = "Sistema de Produção"
admin.site.index_title = "Painel de Administração"

