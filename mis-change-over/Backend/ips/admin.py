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
    AssociacaoProdutoLinha,
    Controle, IntertravamentoLinha, HistoricoIntertravamento,
    LiberacaoSAP, ValidacaoQualidade, HistoricoStatusLinha,
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
        ('Andretti — Tags OPC', {
            'fields': ('tag_velocidade_opc', 'tag_formato_opc'),
            'description': (
                'tag_velocidade_opc: Ex: ns=2;s=Program:MainProgram.VelocidadeAtual | '
                'tag_formato_opc: retorna o formato atual em gramas (ex: 4000 para 4kg)'
            ),
            'classes': ('collapse',),
        }),
        ('Status do Produto — Tags OPC (v9.0)', {
            'fields': (
                'conexao_opc_status',
                'tag_status_linha_opc',
                'tag_sku_atual_opc',
                'tag_giveaway_opc',
                'tag_descarte_turno_opc',
                'tag_peso_medio_opc',
                'tag_caixas_turno_opc',
                'tag_aguardando_validacao_opc',
            ),
            'description': (
                'conexao_opc_status: servidor OPC UA usado para leitura/escrita das tags abaixo | '
                'tag_status_linha_opc: inteiro OPC — 10=Rodando, 20=Aguardando, 30=Bloqueado, 40=Falha | '
                'tag_sku_atual_opc: string OPC com o SKU em operação | '
                'tag_caixas_turno_opc: usado com Formato.gramas para calcular toneladas/turno | '
                'tag_aguardando_validacao_opc: escrita bool → CLP (fail-safe de qualidade)'
            ),
            'classes': ('collapse',),
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
            'fields': ('nome', 'descricao', 'gramas', 'vazao_kg_hora')
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

# ==================== ADMIN PARA INTERTRAVAMENTOS ====================

class HistoricoInline(admin.TabularInline):
    model = HistoricoIntertravamento
    readonly_fields = ['campo', 'valor_anterior', 'valor_novo', 
                       'origem', 'usuario', 'observacao', 'timestamp']
    extra = 0
    can_delete = False
    ordering = ['-timestamp']
    max_num = 20  # mostra últimas 20 entradas

class IntertravamentoLinhaInline(admin.TabularInline):
    model = IntertravamentoLinha
    extra = 1
    fields = ['linha', 'conexao_opcua', 'node_id_tag', 
              'estado_opc', 'habilitado_software', 'modificado_por']
    readonly_fields = ['estado_opc', 'modificado_por']

@admin.register(Controle)
class ControleAdmin(admin.ModelAdmin):
    inlines = [IntertravamentoLinhaInline]
    list_display = ['nome', 'area', 'critico', 'ativo']
    list_filter = ['area', 'critico', 'ativo']
    search_fields = ['nome', 'descricao']

@admin.register(IntertravamentoLinha)
class IntertravamentoLinhaAdmin(admin.ModelAdmin):
    inlines = [HistoricoInline]
    list_display  = ['controle', 'linha', 'get_bypass_detectado', 'estado_opc', 'habilitado_software', 'modificado_por', 'modificado_em']
    list_filter   = ['controle__area', 'linha', 'estado_opc', 'habilitado_software']
    search_fields = ['controle__nome', 'linha__nome', 'node_id_tag']
    readonly_fields = ['estado_opc', 'modificado_por']

    def get_bypass_detectado(self, obj):
        return obj.bypass_detectado
    get_bypass_detectado.boolean = True
    get_bypass_detectado.short_description = "Bypass Detectado?"


# ==================== VALIDAÇÕES v9.0 ====================

@admin.register(LiberacaoSAP)
class LiberacaoSAPAdmin(admin.ModelAdmin):
    list_display  = ('produto', 'linha', 'liberado_por', 'liberado_em', 'observacao_resumida')
    list_filter   = ('linha',)
    search_fields = ('produto__sku', 'produto__descricao', 'linha__nome', 'liberado_por__username')
    readonly_fields = ('liberado_em', 'liberado_por')
    autocomplete_fields = ('produto',)

    fieldsets = (
        ('Liberação', {
            'fields': ('produto', 'linha', 'observacao'),
        }),
        ('Auditoria', {
            'fields': ('liberado_por', 'liberado_em'),
            'classes': ('collapse',),
        }),
    )

    def observacao_resumida(self, obj):
        return obj.observacao[:60] + '…' if len(obj.observacao) > 60 else obj.observacao
    observacao_resumida.short_description = 'Observação'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.liberado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(ValidacaoQualidade)
class ValidacaoQualidadeAdmin(admin.ModelAdmin):
    list_display  = (
        'produto', 'linha', 'status', 'prazo_minutos',
        'tempo_producao_acumulado_s', 'percentual_consumido_display',
        'opc_sinal_enviado', 'aprovado_por', 'aprovado_em', 'criada_em',
    )
    list_filter   = ('status', 'linha', 'opc_sinal_enviado')
    search_fields = ('produto__sku', 'produto__descricao', 'linha__nome')
    readonly_fields = (
        'troca', 'produto', 'linha', 'criada_em', 'atualizada_em',
        'tempo_producao_acumulado_s', 'ultima_leitura_opc', 'opc_sinal_enviado',
        'percentual_consumido_display',
    )

    fieldsets = (
        ('Identificação', {
            'fields': ('troca', 'produto', 'linha', 'status'),
        }),
        ('Timer de Produção', {
            'fields': (
                'prazo_minutos', 'tempo_producao_acumulado_s',
                'percentual_consumido_display', 'ultima_leitura_opc',
            ),
        }),
        ('OPC', {
            'fields': ('opc_sinal_enviado',),
        }),
        ('Aprovação', {
            'fields': ('aprovado_por', 'aprovado_em'),
        }),
        ('Auditoria', {
            'fields': ('criada_em', 'atualizada_em'),
            'classes': ('collapse',),
        }),
    )

    def percentual_consumido_display(self, obj):
        return f'{obj.percentual_consumido}%'
    percentual_consumido_display.short_description = '% prazo consumido'

    def has_add_permission(self, request):
        # Criada exclusivamente pelo worker/view, nunca manualmente
        return False


@admin.register(HistoricoStatusLinha)
class HistoricoStatusLinhaAdmin(admin.ModelAdmin):
    list_display  = (
        'linha', 'get_status_label', 'sku_em_operacao',
        'iniciado_em', 'encerrado_em', 'duracao_formatada',
    )
    list_filter   = ('linha', 'status_codigo')
    search_fields = ('linha__nome', 'sku_em_operacao')
    readonly_fields = (
        'linha', 'status_codigo', 'sku_em_operacao',
        'iniciado_em', 'encerrado_em', 'duracao_s',
    )
    date_hierarchy = 'iniciado_em'

    def get_status_label(self, obj):
        return obj.get_status_codigo_display()
    get_status_label.short_description = 'Status'

    def duracao_formatada(self, obj):
        if obj.duracao_s is None:
            return '— em andamento'
        m, s = divmod(int(obj.duracao_s), 60)
        h, m = divmod(m, 60)
        return f'{h:02d}h {m:02d}m {s:02d}s'
    duracao_formatada.short_description = 'Duração'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ==================== RECIPE MONITOR v10.0 ====================

from .models import HistoricoSincronismoReceita


@admin.register(HistoricoSincronismoReceita)
class HistoricoSincronismoReceitaAdmin(admin.ModelAdmin):
    """
    Auditoria de sincronismos CLP → FormatoVariavel feitos pelo Recipe Monitor.
    Read-only para qualquer usuário (auditoria não pode ser alterada). Delete
    apenas para superuser.
    """
    list_display = (
        'data_hora', 'formato', 'variavel', 'linha', 'usuario',
        'valor_anterior', 'valor_novo', 'origem_servico', 'lote_uuid',
    )
    list_filter = ('formato', 'linha', 'usuario', 'origem_servico', 'data_hora')
    search_fields = (
        'formato__nome', 'variavel__nome',
        'usuario__username', 'lote_uuid', 'observacao',
    )
    date_hierarchy = 'data_hora'
    ordering = ('-data_hora',)
    list_per_page = 50
    readonly_fields = (
        'lote_uuid', 'formato', 'variavel', 'linha',
        'valor_anterior', 'valor_novo', 'usuario', 'ip_origem',
        'origem_servico', 'data_hora', 'observacao',
    )

    def has_add_permission(self, request):
        # Auditoria só é criada pelo endpoint /api/recipe-monitor/.../sincronizar/
        return False

    def has_delete_permission(self, request, obj=None):
        # Auditoria protegida — só superuser pode apagar
        return request.user.is_superuser


# ==================== GESTÃO DE USUÁRIOS (item 3) ====================

from .models import ContaUsuarioExpiracao


@admin.register(ContaUsuarioExpiracao)
class ContaUsuarioExpiracaoAdmin(admin.ModelAdmin):
    """
    Validade de contas. VISÍVEL/EDITÁVEL SOMENTE POR SUPERUSER.

    Isso impede que o time que apenas CRIA usuários (staff, mas não superuser)
    consiga estender a própria validade ou de terceiros sem aprovação. A
    renovação de prazo é uma prerrogativa exclusiva do administrador.
    """
    list_display = ('user', 'validade_ate', 'status_calc', 'renovado_em', 'renovado_por')
    search_fields = ('user__username',)
    list_filter = ('validade_ate', 'renovado_em')
    readonly_fields = ('criado_em', 'renovado_em', 'renovado_por')
    actions = ['renovar_contas']

    # ── Trava total: só superuser vê e mexe neste modelo ──────────────
    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        # Registros são criados por signal ao criar o usuário. Ninguém cria à mão.
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def status_calc(self, obj):
        motivo = obj.motivo_expiracao()
        if not obj.user.is_active:
            return 'BLOQUEADO'
        return f'expira ({motivo})' if motivo else 'ativo'
    status_calc.short_description = 'Status'

    @admin.action(description='Renovar contas selecionadas (+5 meses)')
    def renovar_contas(self, request, queryset):
        # Reforço: apenas superuser executa a ação (o menu já é oculto, mas
        # protegemos contra chamada direta).
        if not request.user.is_superuser:
            self.message_user(request, 'Apenas superusuários podem renovar contas.', level='error')
            return
        n = 0
        for exp in queryset:
            exp.renovar(por_usuario=request.user)
            n += 1
        self.message_user(request, f'{n} conta(s) renovada(s).')


# ==================== VALIDAÇÃO DE QUALIDADE POR CAIXAS (v11.0) ====================

from .models import (
    ConfiguracaoValidacaoQualidade, CriterioValidacaoQualidade,
    HistoricoValidacaoQualidade,
)


@admin.register(ConfiguracaoValidacaoQualidade)
class ConfiguracaoValidacaoQualidadeAdmin(admin.ModelAdmin):
    """Singleton — configuração global da validação por caixas."""
    list_display = ('__str__', 'ativo', 'caixas_default', 'atualizado_em')

    def has_add_permission(self, request):
        # Singleton: só permite adicionar se ainda não existe.
        return not ConfiguracaoValidacaoQualidade.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CriterioValidacaoQualidade)
class CriterioValidacaoQualidadeAdmin(admin.ModelAdmin):
    """Meta de caixas por Formato×Linha."""
    list_display = ('formato', 'linha', 'quantidade_caixas', 'ativo', 'atualizado_em', 'criado_por')
    list_filter = ('linha', 'ativo', 'formato')
    search_fields = ('formato__nome', 'linha__nome')
    autocomplete_fields = ('formato', 'linha')
    list_editable = ('quantidade_caixas', 'ativo')
    readonly_fields = ('criado_por', 'criado_em', 'atualizado_em')

    def save_model(self, request, obj, form, change):
        if not change and not obj.criado_por_id:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(HistoricoValidacaoQualidade)
class HistoricoValidacaoQualidadeAdmin(admin.ModelAdmin):
    """Auditoria (read-only) dos eventos de validação de qualidade."""
    list_display = ('timestamp', 'validacao', 'evento', 'caixas_no_momento',
                    'meta_caixas', 'usuario')
    list_filter = ('evento', 'timestamp')
    search_fields = ('validacao__produto__sku', 'validacao__linha__nome', 'usuario__username')
    date_hierarchy = 'timestamp'
    readonly_fields = ('validacao', 'evento', 'caixas_no_momento', 'meta_caixas',
                       'usuario', 'observacao', 'timestamp')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# ==================== HARDENING DO ADMIN DE USUÁRIOS ====================
# Impede que usuários NÃO-superuser promovam contas a superuser (ou concedam
# staff/permissões/grupos), mesmo que tenham a permissão auth.change_user.
# Fecha o vetor de auto-promoção a superuser via admin padrão do Django.

from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User as AuthUser

# Campos de privilégio que só superuser pode alterar.
_CAMPOS_PRIVILEGIO = ('is_superuser', 'is_staff', 'groups', 'user_permissions')


class UserAdminSeguro(DjangoUserAdmin):
    """
    UserAdmin com trava de escalonamento de privilégio:
      - Campos is_superuser/is_staff/groups/user_permissions ficam READ-ONLY
        para quem não é superuser.
      - Não-superuser não pode editar contas que JÁ são superuser.
      - No form de criação, não-superuser não vê os campos de privilégio.
    """

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            for campo in _CAMPOS_PRIVILEGIO:
                if campo not in ro:
                    ro.append(campo)
        return tuple(ro)

    def has_change_permission(self, request, obj=None):
        # Não-superuser não edita contas que já são superuser.
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Não-superuser não apaga superusers.
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)


# Re-registra o User com a versão segura.
try:
    admin.site.unregister(AuthUser)
except admin.sites.NotRegistered:
    pass
admin.site.register(AuthUser, UserAdminSeguro)


# Configurações adicionais do admin
admin.site.site_header = "Administração do Sistema de Produção"
admin.site.site_title = "Sistema de Produção"
admin.site.index_title = "Painel de Administração"

