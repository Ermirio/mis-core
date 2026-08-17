# models.py

from django.db import models
from django.contrib.auth.models import User
from datetime import datetime

# ==================== MODELOS BASE ====================

class ConexaoOPCUAServidor(models.Model):
    """Configurações de conexão OPC UA"""
    nome = models.CharField(max_length=100)
    url = models.CharField(max_length=200)
    caminho_plc = models.CharField(max_length=100, blank=True)
    timeout = models.IntegerField(default=15)
    
    def __str__(self):
        return f"{self.nome} ({self.url})"
    
    class Meta:
        verbose_name = "Conexão OPC UA"
        verbose_name_plural = "Conexões OPC UA"

class Equipamento(models.Model):
    """Equipamentos unificados da linha de produção (inclui antigas enchedoras)"""
    TIPO_EQUIPAMENTO_CHOICES = [
        ('ENCHEDORA', 'Enchedora'),
        ('VINCADORA', 'Vincadora'),
        ('ENCAIXOTADORA', 'Encaixotadora'),
        ('PALETIZADORA', 'Paletizadora'),
        ('BALANCA', 'Balança'),
        ('EMPACOTADORA', 'Empacotadora'),
        ('TRANSPORTADOR', 'Tranportador'),
        ('ROBO', 'Robo'),
    ]
    
    nome = models.CharField(max_length=100)
    tipo_equipamento = models.CharField(max_length=20, choices=TIPO_EQUIPAMENTO_CHOICES, default='OUTRO_PLC')
    conexao_opcua = models.ForeignKey(ConexaoOPCUAServidor, on_delete=models.SET_NULL, null=True, blank=True)
    ativa = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.nome} ({self.get_tipo_equipamento_display()})"
    
    class Meta:
        verbose_name = "Equipamento"
        verbose_name_plural = "Equipamentos"

class Variavel(models.Model):
    """Variáveis mestras de processo (conceitos abstratos como 'Pressão', 'Temperatura', 'Volume')"""
    TIPO_CHOICES = [
        ('REAL', 'Real'),
        ('DINT', 'Double Integer'),
        ('UDINT', 'Unsigned Double Integer (UDINT)'),
        ('INT', 'Integer'),
        ('UINT', 'Unsigned Integer (UINT)'),
        ('BOOL', 'Boolean'),
        ('STRING', 'String'),
    ]
    
    nome = models.CharField(max_length=100, unique=True) # Nome único para a variável mestra
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    descricao = models.CharField(max_length=200, blank=True)

    # ── Recipe Monitor (mis-recipe-intelligent) ─────────────────────────
    # Usados pelo serviço externo de monitoramento em tempo real para
    # classificar leituras OPC contra o valor de receita (FormatoVariavel).
    # Opcionais: variáveis sem tolerância caem em "normal | alarme" só
    # (igual / diferente), sem zona de atenção.
    unidade = models.CharField(
        max_length=20, blank=True,
        help_text="Unidade de engenharia (rpm, bar, L, °C...). Vazio para BOOL/STRING."
    )
    tolerancia = models.FloatField(
        null=True, blank=True,
        help_text=(
            "Tolerância aceitável (na mesma unidade da variável). "
            "Usada pelo Recipe Monitor: |atual - receita| <= tol → NORMAL, "
            "<= 2*tol → ATENÇÃO, > 2*tol → ALARME. "
            "Aplicável apenas a tipos numéricos (REAL/DINT/UDINT/INT/UINT)."
        )
    )

    # Este ManyToMany pode ser redundante ou utilizado para fins informativos,
    # já que o mapeamento real se dará via ConfiguracaoEquipamentoTag.
    # Vou mantê-lo, mas é importante entender seu propósito.
    equipamentos_que_usam = models.ManyToManyField(
        Equipamento,
        blank=True,
        related_name='variaveis_utilizadas',
        help_text="Equipamentos que utilizam esta variável mestra conceitual"
    )
    
    def __str__(self):
        return f"{self.nome} ({self.tipo})"
    
    class Meta:
        verbose_name = "Variável Mestra"
        verbose_name_plural = "Variáveis Mestras"


class InkjetPrinter(models.Model):
    """Impressoras Inkjet da linha de produção"""
    nome = models.CharField(max_length=100, unique=True)
    ip_address = models.GenericIPAddressField()
    port = models.IntegerField()
    format_name = models.CharField(max_length=100)
    ativa = models.BooleanField(default=True)
    
    def __str__(self):
        return self.nome
    
    class Meta:
        verbose_name = "Impressora Inkjet"
        verbose_name_plural = "Impressoras Inkjet"

class Impressora(models.Model):
    """Impressoras 3M da linha de produção"""
    nome = models.CharField(max_length=100)
    ip = models.GenericIPAddressField(null=True, blank=True)
    pasta_destino = models.CharField(max_length=200, blank=True)
    ativa = models.BooleanField(default=True)
    
    def __str__(self):
        return self.nome
    
    class Meta:
        verbose_name = "Impressora"
        verbose_name_plural = "Impressoras"

# ==================== NOVOS MODELOS DE FORMATO ====================

class Formato(models.Model):
    """Formato de produto (ex: '800g-L21', 'Caixa de 6 Latas-L01')"""
    nome = models.CharField(max_length=100, unique=True, help_text="Nome do formato. Use um sufixo como '-L21' para indicar a linha.")
    descricao = models.TextField(blank=True)
    # Andretti: peso em gramas para identificação via OPC (ex: 4000 = 4kg)
    gramas = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Peso em gramas do formato (ex: 4000 = 4kg). Usado pelo módulo Andretti para identificar o formato via OPC UA."
    )

    # Vazão nominal para cálculo de toneladas nos insights (kg/h)
    vazao_kg_hora = models.FloatField(
        default=0.0,
        help_text=(
            "Vazão nominal deste formato em kg/h. "
            "Usado nos Insights de Formatos para estimar toneladas produzidas "
            "com base no tempo acumulado em que este formato esteve ativo. "
            "Ex: 2400 = 2.4 ton/h."
        )
    )

    # Campos de auditoria
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='formatos_criados')
    atualizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='formatos_atualizados')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.gramas:
            return f"{self.nome} ({self.gramas}g)"
        return self.nome

    class Meta:
        verbose_name = "Formato"
        verbose_name_plural = "Formatos"

class FormatoVariavel(models.Model):
    """Associa um valor a uma Variável Mestra para um Formato específico.
    Ex: Para o Formato 'Garrafa 1L', a Variável Mestra 'Volume_SetPoint' tem o valor '1000'.
    """
    formato = models.ForeignKey(Formato, on_delete=models.CASCADE, related_name='variaveis')
    variavel = models.ForeignKey(Variavel, on_delete=models.CASCADE, related_name='valores_por_formato') # Variável Mestra
    valor = models.CharField(max_length=100) # O valor que essa variável mestra terá para este formato
    
    # Campos de auditoria
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='formato_variaveis_criadas')
    atualizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='formato_variaveis_atualizadas')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.formato.nome} - {self.variavel.nome}: {self.valor}"
    
    class Meta:
        verbose_name = "Formato Variável"
        verbose_name_plural = "Formato Variáveis"
        unique_together = ['formato', 'variavel'] # Um formato só pode ter um valor para uma dada variável mestra

class ConfiguracaoEquipamentoVariavel(models.Model): # MANTIDO E REFORÇADO O PROPÓSITO
    """Mapeamento entre uma Variável Mestra (conceitual) e a tag PLC real em um Equipamento específico.
    Esta é a tabela que define 'onde' no CLP de um equipamento uma variável conceitual é escrita.
    """
    equipamento = models.ForeignKey(Equipamento, on_delete=models.CASCADE, related_name='configuracoes_variaveis')
    variavel_mestra = models.ForeignKey(Variavel, on_delete=models.CASCADE, related_name='mapeamentos_equipamentos')
    tag_plc = models.CharField(max_length=100, help_text="Nome da tag/endereço no CLP (ex: 'Program:MainProgram.Setpoint_Velocidade')")
    
    # Campos de auditoria
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='config_equip_var_criadas')
    atualizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='config_equip_var_atualizadas')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.equipamento.nome} - {self.variavel_mestra.nome} -> {self.tag_plc}"
    
    class Meta:
        verbose_name = "Mapeamento Variável-Equipamento"
        verbose_name_plural = "Mapeamentos Variáveis-Equipamentos"
        # Garante que para um dado equipamento, uma variável mestra só pode ser mapeada para uma tag PLC
        unique_together = ['equipamento', 'variavel_mestra'] 

# ==================== MODELOS DE LINHA E PRODUTO ====================

class Linha(models.Model):
    """Linhas de produção"""
    nome = models.CharField(max_length=10, unique=True)
    descricao = models.CharField(max_length=200, blank=True)
    ativa = models.BooleanField(default=True)

    # Andretti: tag OPC para leitura de velocidade da linha
    tag_velocidade_opc = models.CharField(
        max_length=300, blank=True, null=True,
        help_text=(
            "Tag OPC UA para leitura de velocidade. "
            "Ex: ns=2;s=Program:MainProgram.VelocidadeAtual"
        )
    )
    # Andretti: tag OPC para leitura do formato atual em gramas (ex: 4000 = 4kg)
    tag_formato_opc = models.CharField(
        max_length=300, blank=True, null=True,
        help_text=(
            "Tag OPC UA que retorna o formato atual em gramas. "
            "Ex: ns=2;s=Program:MainProgram.FormatoAtualGramas — valor esperado: 4000 para 4kg."
        )
    )

    # ── Status do Produto — Tags OPC (v9.0) ─────────────────────────────
    tag_status_linha_opc = models.CharField(
        max_length=300, blank=True, null=True,
        help_text=(
            "Tag OPC UA que retorna o status operacional da linha como inteiro. "
            "Valores esperados: 10=Rodando, 20=Aguardando, 30=Bloqueado, 40=Falha."
        )
    )
    tag_sku_atual_opc = models.CharField(
        max_length=300, blank=True, null=True,
        help_text="Tag OPC UA que retorna o SKU atual em operação na linha (string)."
    )
    tag_giveaway_opc = models.CharField(
        max_length=300, blank=True, null=True,
        help_text="Tag OPC UA para leitura do giveaway (g ou %). Ex: ns=2;s=Program:MainProgram.Giveaway"
    )
    tag_descarte_turno_opc = models.CharField(
        max_length=300, blank=True, null=True,
        help_text="Tag OPC UA para contador de descartes no turno atual."
    )
    tag_peso_medio_opc = models.CharField(
        max_length=300, blank=True, null=True,
        help_text="Tag OPC UA para peso médio do produto em gramas."
    )
    tag_caixas_turno_opc = models.CharField(
        max_length=300, blank=True, null=True,
        help_text=(
            "Tag OPC UA para quantidade de caixas produzidas no turno. "
            "Usado em conjunto com Formato.gramas para calcular toneladas/turno."
        )
    )
    tag_aguardando_validacao_opc = models.CharField(
        max_length=300, blank=True, null=True,
        help_text=(
            "Tag OPC UA (escrita, bool) para sinalizar ao CLP que o SKU aguarda "
            "validação de qualidade. CLP age com lógica fail-safe: para a linha se "
            "receber True ou se não conseguir ler a tag."
        )
    )
    # ── Validação de Qualidade por CAIXAS (v11.0) ──────────────────────
    tag_caixas_sku_opc = models.CharField(
        max_length=300, blank=True, null=True,
        help_text=(
            "Tag OPC UA (leitura, inteiro) com a quantidade de caixas produzidas "
            "DESDE A TROCA do SKU atual. O CLP zera este contador quando um SKU "
            "novo é escrito na linha. Usada pela validação de qualidade por caixas: "
            "ao atingir a meta, o MIS escreve True em tag_aguardando_validacao_opc."
        )
    )
    # Servidor OPC UA usado para leitura das tags de status da linha (v9.0)
    conexao_opc_status = models.ForeignKey(
        ConexaoOPCUAServidor,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='linhas_status',
        help_text=(
            "Servidor OPC UA de onde as tags de status da linha são lidas "
            "(tag_status_linha_opc, tag_sku_atual_opc, etc.)."
        )
    )

    # Relacionamentos many-to-many atualizados
    equipamentos = models.ManyToManyField(Equipamento, blank=True, related_name='linhas')
    impressoras_3m = models.ManyToManyField(Impressora, blank=True, related_name='linhas')
    impressoras_inkjet = models.ManyToManyField(InkjetPrinter, blank=True, related_name='linhas')
    
    def __str__(self):
        return self.nome
    
    def get_ultimo_sku_enviado(self):
        """Retorna o último SKU enviado para esta linha"""
        try:
            ultima_troca = TrocaSKU.objects.filter(linha=self.nome).order_by('-data_hora').first()
            if ultima_troca:
                return {
                    'sku': ultima_troca.sku_trocado,
                    'descricao': ultima_troca.descricao,
                    'data_hora': ultima_troca.data_hora,
                    'sucesso': ultima_troca.sucesso,
                    'tem_erros': bool(ultima_troca.logs_equipamentos.exclude(status='sucesso').exists()),
                }
            return None
        except Exception:
            return None
    
    def get_status_equipamentos(self):
        """Retorna status dos equipamentos da linha"""
        status = {
            'equipamentos': [],
            'impressoras_3m': [],
            'impressoras_inkjet': []
        }
        
        # Pode ser mais eficiente buscar o status da linha uma vez
        status_linha_obj = StatusLinha.objects.filter(linha=self).first()
        ultimo_sku_info = None
        if status_linha_obj:
            # Aqui, idealmente você buscaria os logs mais recentes para cada equipamento individualmente
            # para ter o status atualizado, ou se basearia no StatusLinha para um resumo geral
            ultimo_sku_info = {
                'sku': status_linha_obj.sku_atual,
                'descricao': status_linha_obj.descricao_sku_atual,
                'data_hora': status_linha_obj.data_ultima_troca,
                # 'sucesso' e 'tem_erros' teriam que vir de uma análise mais profunda ou do próprio StatusLinha
                'sucesso': True if status_linha_obj.equipamentos_ativos == status_linha_obj.equipamentos_total else False,
                'tem_erros': True if status_linha_obj.equipamentos_ativos < status_linha_obj.equipamentos_total else False,
            }


        for equipamento in self.equipamentos.all():
            status['equipamentos'].append({
                'nome': equipamento.nome,
                'tipo': equipamento.get_tipo_equipamento_display(),
                'ultimo_sku': ultimo_sku_info['sku'] if ultimo_sku_info else 'Aguardando SKU',
                'data_ultima_troca': ultimo_sku_info['data_hora'] if ultimo_sku_info else None,
                'status': 'ativo' if ultimo_sku_info and ultimo_sku_info['sucesso'] else 'aguardando'
            })
        
        for impressora in self.impressoras_3m.all():
            status['impressoras_3m'].append({
                'nome': impressora.nome,
                'ultimo_sku': ultimo_sku_info['sku'] if ultimo_sku_info else 'Aguardando SKU',
                'data_ultima_troca': ultimo_sku_info['data_hora'] if ultimo_sku_info else None,
                'status': 'ativo' if ultimo_sku_info and ultimo_sku_info['sucesso'] else 'aguardando'
            })
        
        for inkjet_printer in self.impressoras_inkjet.all():
            status['impressoras_inkjet'].append({
                'nome': inkjet_printer.nome,
                'ultimo_sku': ultimo_sku_info['sku'] if ultimo_sku_info else 'Aguardando SKU',
                'data_ultima_troca': ultimo_sku_info['data_hora'] if ultimo_sku_info else None,
                'status': 'ativo' if ultimo_sku_info and ultimo_sku_info['sucesso'] else 'aguardando'
            })
        
        return status
    
    class Meta:
        verbose_name = "Linha"
        verbose_name_plural = "Linhas"

class Produto(models.Model):
    """Produtos/SKUs (antigo CadastroProdutoFlex)"""
    sku = models.CharField(max_length=50, unique=True)
    descricao = models.CharField(max_length=200)
    dun14 = models.CharField(max_length=50, blank=True)
    ean = models.CharField(max_length=50, blank=True)
    filme = models.CharField(max_length=100, blank=True)
    validade = models.CharField(max_length=50, blank=True)
    id_ordem_prod = models.CharField(max_length=50, blank=True)
    numero_op = models.CharField(max_length=50, blank=True)
    quantidade_por_pallet = models.CharField(max_length=50, blank=True)
    status_op = models.CharField(max_length=50, blank=True)
    dataop_str = models.CharField(max_length=50, blank=True)
    
    # REMOVIDO: formato = models.ForeignKey(Formato, on_delete=models.SET_NULL, null=True, blank=True, related_name='produtos')
    # REMOVIDO: linhas = models.ManyToManyField(Linha, related_name='produtos')
    # Agora a associação com linhas e formatos é feita através do modelo AssociacaoProdutoLinha
    
    # Campos de auditoria
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='produtos_criados')
    atualizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='produtos_atualizados')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.sku} - {self.descricao}"
    
    def get_variaveis_formato(self, linha=None):
        """Retorna as variáveis do formato associado para uma linha específica"""
        if linha:
            try:
                associacao = self.associacoes_linha.get(linha=linha)
                return associacao.formato.variaveis.all()
            except AssociacaoProdutoLinha.DoesNotExist:
                return []
        return []
    
    def get_linhas_associadas(self):
        """Retorna as linhas associadas a este produto"""
        return [assoc.linha for assoc in self.associacoes_linha.all()]
    
    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"

# NO SEU ARQUIVO models.py

# NOVO MODELO DE ASSOCIAÇÃO
class AssociacaoProdutoLinha(models.Model):
    """
    Tabela intermediária que associa um Produto a uma Linha e especifica qual Formato usar.
    Esta é a chave para permitir que um SKU tenha múltiplos formatos, um para cada linha.
    """
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='associacoes_linha')
    linha = models.ForeignKey(Linha, on_delete=models.CASCADE, related_name='associacoes_produto')
    
    # <<< CORREÇÃO 1: O campo 'formato' foi tornado opcional no banco de dados.
    formato = models.ForeignKey(
        Formato, 
        on_delete=models.CASCADE, 
        help_text="O formato que este produto usará nesta linha específica.",
        null=True,  # Permite que o valor seja NULO no banco de dados
        blank=True  # Permite que o campo fique em branco nos formulários do Django
    )
    
    # Campos de auditoria
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    # <<< CORREÇÃO 2: O método __str__ foi ajustado para evitar erro se o formato for nulo.
    def __str__(self):
        """Retorna uma representação em string do objeto."""
        if self.formato:
            return f"{self.produto.sku} na {self.linha.nome} (Formato: {self.formato.nome})"
        else:
            return f"{self.produto.sku} na {self.linha.nome} (Formato: AINDA NÃO DEFINIDO)"

    def clean(self):
        """Validação personalizada para verificar se o formato corresponde à linha."""
        from django.core.exceptions import ValidationError
        if self.formato and self.linha:
            # Esta validação só será executada se um formato for selecionado.
            if not self.formato.nome.upper().endswith(f'-{self.linha.nome.upper()}'):
                raise ValidationError(
                    f"O formato '{self.formato.nome}' não corresponde ao padrão esperado para a linha '{self.linha.nome}'. "
                    f"O formato deve terminar com '-{self.linha.nome.upper()}'."
                )

    class Meta:
        verbose_name = "Associação Produto-Linha-Formato"
        verbose_name_plural = "Associações Produto-Linha-Formato"
        # Garante que um produto só pode ter uma configuração por linha
        unique_together = ('produto', 'linha')

# ==================== MODELOS DE TROCA E LOGS ====================

class TrocaSKU(models.Model):
    """Modelo principal para registrar trocas de SKU com logs detalhados"""
    linha = models.CharField(max_length=10, db_index=True)
    sku_trocado = models.CharField(max_length=50, db_index=True)
    descricao = models.CharField(max_length=200)
    data_hora = models.DateTimeField(auto_now_add=True, db_index=True)
    sucesso = models.BooleanField(default=False) # Default para False, será calculado no save()
    
    # Campos para logs detalhados
    detalhes = models.TextField(blank=True)
    equipamentos_processados = models.IntegerField(default=0)
    equipamentos_sucesso = models.IntegerField(default=0)
    equipamentos_falha = models.IntegerField(default=0)
    
    # Dados do SKU
    dun14 = models.CharField(max_length=50, blank=True)
    validade = models.CharField(max_length=50, blank=True)
    numero_op = models.CharField(max_length=50, blank=True)
    
    # Metadados
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    tempo_execucao = models.FloatField(null=True, blank=True)  # em segundos
    primeira_rodada = models.BooleanField(default=False, help_text='Indica se este foi o primeiro registro bem-sucedido deste SKU nesta linha.')
    
    def __str__(self):
        return f"Troca {self.linha} - {self.sku_trocado} ({self.data_hora.strftime('%Y-%m-%d %H:%M:%S')})"
    
    def get_resumo_execucao(self):
        """Retorna um resumo da execução da troca com base nos logs associados."""
        logs = self.logs_equipamentos.all()
        total_equipamentos = logs.count()
        sucessos = logs.filter(status='sucesso').count()
        falhas = total_equipamentos - sucessos
        
        taxa_sucesso = round((sucessos / total_equipamentos * 100), 1) if total_equipamentos > 0 else 0
        tem_erros = falhas > 0

        # Calcula o tempo de execução total somando os tempos dos logs
        tempo_total = sum(log.tempo_execucao for log in logs if log.tempo_execucao is not None)
        
        return {
            'total_equipamentos': total_equipamentos,
            'sucessos': sucessos,
            'falhas': falhas,
            'taxa_sucesso': taxa_sucesso,
            'tem_erros': tem_erros,
            'tempo_execucao': round(tempo_total, 2)
        }
    
    def get_status_visual(self):
        """
        Retorna o status visual ('success', 'warning', 'danger', 'secondary')
        com base no resumo da execução.
        """
        resumo = self.get_resumo_execucao()
        if resumo['total_equipamentos'] == 0:
            return 'secondary'  # Nenhum equipamento processado ou configurado
        elif resumo['taxa_sucesso'] == 100:
            return 'success'    # Todos os equipamentos bem-sucedidos
        elif resumo['taxa_sucesso'] > 0:
            return 'warning'    # Alguns sucessos, mas com falhas
        else:
            return 'danger'     # Todas as tentativas falharam
    
    @property
    def concluida(self):
        """Propriedade para compatibilidade com frontend"""
        return self.sucesso
    
    def save(self, *args, **kwargs):
        """
        Sobrescreve o método save para calcular os campos de resumo
        após os logs de equipamentos serem criados.
        """
        super().save(*args, **kwargs)
        
        # Recalcular os campos de resumo com base nos logs
        logs = self.logs_equipamentos.all()
        self.equipamentos_processados = logs.count()
        self.equipamentos_sucesso = logs.filter(status='sucesso').count()
        self.equipamentos_falha = self.equipamentos_processados - self.equipamentos_sucesso
        
        # Determinar sucesso geral
        self.sucesso = self.equipamentos_falha == 0 and self.equipamentos_processados > 0
        
        # Salvar novamente apenas se houve mudanças nos campos calculados
        if self.pk:  # Evita recursão infinita
            TrocaSKU.objects.filter(pk=self.pk).update(
                equipamentos_processados=self.equipamentos_processados,
                equipamentos_sucesso=self.equipamentos_sucesso,
                equipamentos_falha=self.equipamentos_falha,
                sucesso=self.sucesso
            )
    
    class Meta:
        verbose_name = "Troca SKU"
        verbose_name_plural = "Trocas SKU"
        ordering = ['-data_hora']
        indexes = [
            models.Index(fields=['linha', '-data_hora']),
            models.Index(fields=['sku_trocado', '-data_hora']),
            models.Index(fields=['sucesso', '-data_hora']),
        ]

class LogEquipamentoTroca(models.Model):
    """Log detalhado de cada equipamento em uma troca"""
    TIPO_EQUIPAMENTO_CHOICES = [
        ('equipamento', 'Equipamento'),
        ('impressora_3m', 'Impressora 3M'),
        ('impressora_inkjet', 'Impressora Inkjet'),
    ]
    
    STATUS_CHOICES = [
        ('sucesso', 'Sucesso'),
        ('falha', 'Falha'),
        ('timeout', 'Timeout'),
        ('nao_configurado', 'Não Configurado'),
    ]
    
    troca = models.ForeignKey(TrocaSKU, on_delete=models.CASCADE, related_name='logs_equipamentos')
    tipo_equipamento = models.CharField(max_length=20, choices=TIPO_EQUIPAMENTO_CHOICES)
    nome_equipamento = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    mensagem = models.TextField(blank=True)
    erro_detalhado = models.TextField(blank=True)
    variaveis_escritas = models.IntegerField(default=0)
    variaveis_total = models.IntegerField(default=0)
    variaveis_detalhes = models.JSONField(
        default=list, blank=True,
        help_text='Detalhe de cada variável: [{nome, tag_plc, valor, sucesso}]'
    )
    tempo_execucao = models.FloatField(null=True, blank=True)
    
    ip_equipamento = models.GenericIPAddressField(null=True, blank=True)
    conexao_opcua = models.CharField(max_length=200, blank=True)
    
    data_hora = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.tipo_equipamento} {self.nome_equipamento} - {self.status}"

    def get_taxa_sucesso_variaveis(self):
        """Retorna a taxa de sucesso das variáveis em porcentagem"""
        if self.variaveis_total == 0:
            return 0
        return round((self.variaveis_escritas / self.variaveis_total) * 100, 1)

    class Meta:
        verbose_name = "Log de Equipamento da Troca"
        verbose_name_plural = "Logs de Equipamentos da Troca"
        ordering = ['tipo_equipamento', 'nome_equipamento']

# ==================== MODELOS AUXILIARES ====================

class DiscrepanciaSKU(models.Model):
    """Registra discrepâncias entre SKU esperado e atual"""
    linha = models.CharField(max_length=10, db_index=True)
    sku_esperado = models.CharField(max_length=50)
    sku_atual = models.CharField(max_length=50)
    data_hora = models.DateTimeField(auto_now_add=True, db_index=True)
    resolvida = models.BooleanField(default=False)
    observacoes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Discrepância {self.linha} - Esperado: {self.sku_esperado}, Atual: {self.sku_atual}"
    
    class Meta:
        verbose_name = "Discrepância SKU"
        verbose_name_plural = "Discrepâncias SKU"
        ordering = ['-data_hora']

class StatusLinha(models.Model):
    """Status atual de cada linha de produção"""
    linha = models.OneToOneField(Linha, on_delete=models.CASCADE, related_name='status_atual')
    sku_atual = models.CharField(max_length=50, blank=True)
    descricao_sku_atual = models.CharField(max_length=200, blank=True)
    data_ultima_troca = models.DateTimeField(null=True, blank=True)
    equipamentos_ativos = models.IntegerField(default=0)
    equipamentos_total = models.IntegerField(default=0)
    
    def __str__(self):
        return f"Status {self.linha.nome} - SKU: {self.sku_atual}"
    
    def get_taxa_equipamentos_ativos(self):
        """Retorna a taxa de equipamentos ativos em porcentagem"""
        if self.equipamentos_total == 0:
            return 0
        return round((self.equipamentos_ativos / self.equipamentos_total) * 100, 1)
    
    class Meta:
        verbose_name = "Status da Linha"
        verbose_name_plural = "Status das Linhas"


# ==================== INTERTRAVAMENTOS ====================

class AreaControle(models.TextChoices):
    QUALIDADE  = 'QUALIDADE',  'Qualidade'
    MANUTENCAO = 'MANUTENCAO', 'Manutenção'
    PROCESSOS  = 'PROCESSOS',  'Processos'


class Controle(models.Model):
    """
    Catálogo de controles/intertravamentos.
    Define o QUE é o controle, independente de onde está instalado.
    """
    nome     = models.CharField(max_length=100)          # "Verificação Código de Barras"
    area     = models.CharField(max_length=20, choices=AreaControle.choices)
    descricao = models.TextField(blank=True)
    critico  = models.BooleanField(default=False)         # True = alerta crítico quando offline
    ativo    = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Controle'
        verbose_name_plural = 'Controles'
        ordering = ['area', 'nome']
        unique_together = [['nome', 'area']]

    def __str__(self):
        return f'[{self.area}] {self.nome}'


class IntertravamentoLinha(models.Model):
    """
    Instância de um Controle em uma linha específica.
    Define ONDE está instalado, como ler via OPC e o estado atual.
    """
    controle     = models.ForeignKey(Controle, on_delete=models.CASCADE, related_name='instancias')
    linha        = models.ForeignKey(Linha, on_delete=models.CASCADE, related_name='intertravamentos')
    conexao_opcua = models.ForeignKey(
        ConexaoOPCUAServidor,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text='Conexão OPC do equipamento onde a tag é lida'
    )
    node_id_tag  = models.CharField(
        max_length=200, blank=True,
        help_text='Endereço OPC UA único da tag de intertravamento (Leitura/Escrita)'
    )

    # ── Estado em tempo real ──
    estado_opc       = models.BooleanField(default=True)   # lido automaticamente do CLP
    habilitado_software = models.BooleanField(default=True)  # alterado por usuário na tela

    # ── Auditoria ──
    modificado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    modificado_em = models.DateTimeField(auto_now=True)
    criado_em     = models.DateTimeField(auto_now_add=True)

    @property
    def bypass_detectado(self):
        """
        Calcula se o usuário no software quer HABILITADO (True), 
        mas no CLP a tag física está DESABILITADO (False).
        Isso caracteriza desabilitação local por um técnico (bypass).
        """
        return self.habilitado_software and not self.estado_opc

    class Meta:
        verbose_name = 'Intertravamento de Linha'
        verbose_name_plural = 'Intertravamentos de Linha'
        ordering = ['linha', 'controle__area', 'controle__nome']
        unique_together = [['controle', 'linha']]

    def __str__(self):
        return f'{self.controle.nome} — {self.linha.nome}'


class HistoricoIntertravamento(models.Model):
    """
    Registro imutável de toda mudança de estado de um intertravamento.
    """
    ORIGEM_CHOICES = [
        ('OPC',    'Leitura OPC UA'),
        ('MANUAL', 'Alteração Manual'),
        ('SISTEMA','Sistema'),
    ]

    intertravamento = models.ForeignKey(
        IntertravamentoLinha,
        on_delete=models.CASCADE,
        related_name='historico'
    )
    campo          = models.CharField(max_length=20)   # 'estado_opc' | 'habilitado_software'
    valor_anterior = models.BooleanField()
    valor_novo     = models.BooleanField()
    origem         = models.CharField(max_length=10, choices=ORIGEM_CHOICES)
    usuario        = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    observacao     = models.TextField(blank=True)
    timestamp      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Histórico de Intertravamento'
        verbose_name_plural = 'Histórico de Intertravamentos'
        ordering = ['-timestamp']


# ==================== VALIDAÇÕES E HISTÓRICO — v9.0 ====================

class LiberacaoSAP(models.Model):
    """
    Pré-requisito obrigatório antes de qualquer troca de SKU.
    Um profissional do grupo 'SAP' valida a lista técnica no MIS,
    substituindo o processo atual de envio de e-mail.
    A liberação é sempre por SKU + linha (nunca global).
    """
    produto     = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name='liberacoes_sap')
    linha       = models.ForeignKey(Linha,   on_delete=models.PROTECT, related_name='liberacoes_sap')
    liberado_por = models.ForeignKey(User,   on_delete=models.PROTECT, related_name='liberacoes_sap_concedidas')
    liberado_em  = models.DateTimeField(auto_now_add=True)
    observacao   = models.TextField(blank=True, help_text='Observação opcional sobre a lista técnica validada.')

    class Meta:
        verbose_name = 'Liberação SAP'
        verbose_name_plural = 'Liberações SAP'
        constraints = [
            models.UniqueConstraint(fields=['produto', 'linha'], name='unique_liberacao_sap_produto_linha')
        ]
        ordering = ['-liberado_em']

    def __str__(self):
        return f'SAP {self.produto.sku} / {self.linha.nome} — {self.liberado_por.username}'


class ValidacaoQualidade(models.Model):
    """
    Controle de qualidade para a primeira rodada de um SKU em uma linha.
    Criada automaticamente quando TrocaSKU.primeira_rodada=True.

    O timer acumula apenas o tempo em que tag_status_linha_opc == 10 (rodando)
    com o SKU desta validação em operação. Ao esgotar o prazo sem aprovação,
    o worker escreve True em tag_aguardando_validacao_opc, sinalizando ao CLP
    que deve parar a linha (lógica fail-safe no CLP).
    """
    class StatusValidacao(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente'
        APROVADO = 'aprovado', 'Aprovado'
        EXPIRADO = 'expirado', 'Expirado — aguardando qualidade'
        CANCELADO = 'cancelado', 'Cancelado — SKU trocado antes do prazo'

    troca   = models.OneToOneField(
        TrocaSKU, on_delete=models.PROTECT,
        related_name='validacao_qualidade',
        null=True, blank=True,
        help_text='Troca que originou esta validação. Null quando aprovado diretamente por engenheiro (bypass).'
    )
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name='validacoes_qualidade')
    linha   = models.ForeignKey(Linha,   on_delete=models.PROTECT, related_name='validacoes_qualidade')

    status        = models.CharField(max_length=20, choices=StatusValidacao.choices, default=StatusValidacao.PENDENTE)
    prazo_minutos = models.PositiveIntegerField(default=30, help_text='[LEGADO] Prazo por tempo. Substituído por meta de caixas na v11.0.')

    # ── Critério por CAIXAS (v11.0) — substitui o timer por tempo ──────
    quantidade_caixas_meta = models.PositiveIntegerField(
        default=0,
        help_text='Meta de caixas a produzir antes de parar para validação. '
                  '0 = não valida (não para a linha). Copiada do CriterioValidacaoQualidade na criação.'
    )
    caixas_produzidas = models.PositiveIntegerField(
        default=0,
        help_text='Última leitura do contador de caixas desde a troca (tag_caixas_sku_opc).'
    )

    # Timer legado (mantido para compatibilidade de dados; não mais usado)
    tempo_producao_acumulado_s = models.FloatField(default=0.0)
    ultima_leitura_opc         = models.DateTimeField(null=True, blank=True,
                                    help_text='Timestamp da última leitura OPC pelo worker.')

    # Escrita OPC
    opc_sinal_enviado = models.BooleanField(default=False,
                            help_text='True quando o worker já escreveu True em tag_aguardando_validacao_opc.')
    parada_em = models.DateTimeField(null=True, blank=True,
                            help_text='Quando a meta de caixas foi atingida e a linha foi sinalizada para parar.')

    # Aprovação
    aprovado_por = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name='validacoes_qualidade_aprovadas')
    aprovado_em  = models.DateTimeField(null=True, blank=True)
    caixas_na_aprovacao = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Quantidade de caixas produzidas no momento da aprovação (amostra avaliada).'
    )
    observacao_qualidade = models.TextField(blank=True,
                            help_text='Observação da qualidade sobre a amostra avaliada.')

    criada_em    = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Validação de Qualidade'
        verbose_name_plural = 'Validações de Qualidade'
        ordering = ['-criada_em']
        indexes = [
            models.Index(fields=['linha', 'status']),
            models.Index(fields=['status', '-criada_em']),
        ]

    def __str__(self):
        return f'Qualidade {self.produto.sku} / {self.linha.nome} — {self.get_status_display()}'

    @property
    def prazo_segundos(self):
        return self.prazo_minutos * 60

    @property
    def tempo_restante_s(self):
        """Segundos restantes. Negativo significa prazo já estourado."""
        return self.prazo_segundos - self.tempo_producao_acumulado_s

    @property
    def percentual_consumido(self):
        if self.prazo_segundos == 0:
            return 100
        return min(100, round((self.tempo_producao_acumulado_s / self.prazo_segundos) * 100, 1))

    # ── Progresso por CAIXAS (v11.0) ──────────────────────────────────
    @property
    def caixas_restantes(self):
        return max(0, self.quantidade_caixas_meta - self.caixas_produzidas)

    @property
    def percentual_caixas(self):
        if not self.quantidade_caixas_meta:
            return 0
        return min(100, round((self.caixas_produzidas / self.quantidade_caixas_meta) * 100, 1))

    @property
    def meta_atingida(self):
        return (self.quantidade_caixas_meta > 0
                and self.caixas_produzidas >= self.quantidade_caixas_meta)


class ConfiguracaoValidacaoQualidade(models.Model):
    """
    Configuração global (singleton) da validação de qualidade por caixas.

    Define a quantidade padrão de caixas usada quando um Formato×Linha não tem
    um CriterioValidacaoQualidade específico. Permite ativar/desativar a
    validação globalmente sem mexer em cada critério (útil no rollout).
    """
    caixas_default = models.PositiveIntegerField(
        default=50,
        help_text='Meta de caixas padrão quando não há critério específico para o Formato×Linha. '
                  '0 = não valida por padrão (linhas sem critério não param).'
    )
    ativo = models.BooleanField(
        default=True,
        help_text='Chave geral: se desmarcado, NENHUMA validação por caixas é criada/aplicada '
                  '(nenhuma linha é parada). Útil para pausar o recurso durante manutenção.'
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração da Validação de Qualidade'
        verbose_name_plural = 'Configuração da Validação de Qualidade'

    def __str__(self):
        estado = 'ativo' if self.ativo else 'INATIVO'
        return f'Validação por caixas: {estado} (default {self.caixas_default} caixas)'

    @classmethod
    def get_solo(cls):
        """Retorna (criando se preciso) a configuração única."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CriterioValidacaoQualidade(models.Model):
    """
    Critério de validação por caixas para um cruzamento Formato × Linha.

    Quando um SKU roda pela primeira vez numa linha, a meta de caixas vem do
    critério correspondente ao formato do produto naquela linha. Se não houver
    critério cadastrado, usa ConfiguracaoValidacaoQualidade.caixas_default.
    """
    formato = models.ForeignKey('Formato', on_delete=models.CASCADE, related_name='criterios_validacao')
    linha   = models.ForeignKey(Linha,     on_delete=models.CASCADE, related_name='criterios_validacao')
    quantidade_caixas = models.PositiveIntegerField(
        help_text='Caixas a produzir antes de parar para validação de qualidade. '
                  '0 = não valida este Formato×Linha (não para a linha).'
    )
    ativo = models.BooleanField(default=True)
    observacao = models.CharField(max_length=200, blank=True)

    criado_por    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='criterios_validacao_criados')
    criado_em     = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Critério de Validação (Formato×Linha)'
        verbose_name_plural = 'Critérios de Validação (Formato×Linha)'
        constraints = [
            models.UniqueConstraint(fields=['formato', 'linha'], name='unique_criterio_formato_linha')
        ]
        ordering = ['linha__nome', 'formato__nome']

    def __str__(self):
        return f'{self.formato.nome} / {self.linha.nome} → {self.quantidade_caixas} caixas'

    @staticmethod
    def resolver_meta(formato, linha):
        """
        Resolve a meta de caixas para um formato+linha, aplicando a hierarquia:
          1. Se a config global estiver inativa → 0 (não valida)
          2. CriterioValidacaoQualidade ativo específico → sua quantidade
          3. Senão → ConfiguracaoValidacaoQualidade.caixas_default
        """
        cfg = ConfiguracaoValidacaoQualidade.get_solo()
        if not cfg.ativo:
            return 0
        if formato is not None and linha is not None:
            crit = CriterioValidacaoQualidade.objects.filter(
                formato=formato, linha=linha, ativo=True
            ).first()
            if crit is not None:
                return crit.quantidade_caixas
        return cfg.caixas_default


class HistoricoValidacaoQualidade(models.Model):
    """
    Tracking imutável dos eventos de cada validação de qualidade — mesmo espírito
    do histórico de trocas. Registra o ciclo de vida: criada → produzindo →
    meta atingida (parou) → aprovada/cancelada, com quem, quantas caixas e quando.
    """
    class Evento(models.TextChoices):
        CRIADA        = 'criada',         'Criada (SKU novo na linha)'
        META_ATINGIDA = 'meta_atingida',  'Meta atingida — linha parada'
        APROVADA      = 'aprovada',       'Aprovada pela qualidade'
        CANCELADA     = 'cancelada',      'Cancelada (SKU trocado antes)'
        LIBERADA_OPC  = 'liberada_opc',   'Liberação OPC enviada ao CLP'
        FALHA_OPC     = 'falha_opc',      'Falha ao escrever no CLP'

    validacao = models.ForeignKey(
        ValidacaoQualidade, on_delete=models.CASCADE, related_name='historico'
    )
    evento = models.CharField(max_length=20, choices=Evento.choices)
    caixas_no_momento = models.PositiveIntegerField(
        default=0, help_text='Contador de caixas no instante do evento.'
    )
    meta_caixas = models.PositiveIntegerField(default=0)

    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='eventos_validacao_qualidade',
                                help_text='Quem disparou o evento (ex.: quem aprovou). Null para eventos do worker.')
    observacao = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Histórico de Validação de Qualidade'
        verbose_name_plural = 'Histórico de Validações de Qualidade'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['validacao', 'timestamp'], name='ips_histvq_val_ts_idx'),
            models.Index(fields=['evento', '-timestamp'], name='ips_histvq_evt_ts_idx'),
        ]

    def __str__(self):
        return f'{self.get_evento_display()} — VQ#{self.validacao_id} @ {self.timestamp:%Y-%m-%d %H:%M}'


class HistoricoStatusLinha(models.Model):
    """
    Registro imutável de cada intervalo de status da linha lido via OPC.
    O worker fecha o registro anterior (preenche encerrado_em e duracao_s)
    ao detectar mudança no valor de tag_status_linha_opc.
    Alimenta futuros insights de OEE, tempo parado, falhas por SKU, etc.
    """
    class StatusCodigo(models.IntegerChoices):
        RODANDO  = 10, 'Rodando'
        WAITING  = 20, 'Aguardando'
        BLOCK    = 30, 'Bloqueado'
        FALHA    = 40, 'Falha'

    linha          = models.ForeignKey(Linha, on_delete=models.PROTECT, related_name='historico_status')
    status_codigo  = models.IntegerField(choices=StatusCodigo.choices)
    sku_em_operacao = models.CharField(max_length=50, blank=True,
                          help_text='Snapshot do SKU atual no momento do registro.')
    iniciado_em    = models.DateTimeField(db_index=True)
    encerrado_em   = models.DateTimeField(null=True, blank=True,
                          help_text='Null enquanto este status ainda está ativo.')
    duracao_s      = models.FloatField(null=True, blank=True,
                          help_text='Duração em segundos. Calculado ao fechar o registro.')

    class Meta:
        verbose_name = 'Histórico de Status da Linha'
        verbose_name_plural = 'Histórico de Status das Linhas'
        ordering = ['-iniciado_em']
        indexes = [
            models.Index(fields=['linha', '-iniciado_em']),
            models.Index(fields=['linha', 'status_codigo', '-iniciado_em']),
        ]

    def __str__(self):
        label = self.get_status_codigo_display()
        return f'{self.linha.nome} — {label} desde {self.iniciado_em:%Y-%m-%d %H:%M}'


# ==================== COMUNICAÇÃO POR LINHA — v9.2 ====================

def _turno_atual():
    """Retorna A, B ou C com base no horário UTC+0 (turnos em horário local BRT -3)."""
    from django.utils import timezone as tz
    hora = tz.localtime(tz.now()).hour   # usa TIME_ZONE do settings
    if 6 <= hora < 14:
        return 'A'
    elif 14 <= hora < 22:
        return 'B'
    else:
        return 'C'


class MensagemLinha(models.Model):
    """
    Mensagem de chat associada a uma linha de produção.
    Suporta @menções a outros usuários.
    """
    TURNO_CHOICES = [('A', 'Turno A (06-14h)'), ('B', 'Turno B (14-22h)'), ('C', 'Turno C (22-06h)')]

    linha     = models.ForeignKey(Linha, on_delete=models.CASCADE, related_name='mensagens')
    autor     = models.ForeignKey(User, on_delete=models.PROTECT, related_name='mensagens_linha')
    texto     = models.TextField(max_length=1000)
    turno     = models.CharField(max_length=1, choices=TURNO_CHOICES, default=_turno_atual)
    criada_em = models.DateTimeField(auto_now_add=True, db_index=True)
    editada   = models.BooleanField(default=False)
    tags      = models.JSONField(default=list, blank=True,
                                  help_text='Hashtags extraídas do texto (#manutenção, #qualidade...)')

    class Meta:
        verbose_name = 'Mensagem de Linha'
        verbose_name_plural = 'Mensagens de Linha'
        ordering = ['criada_em']
        indexes = [
            models.Index(fields=['linha', '-criada_em']),
            models.Index(fields=['linha', 'turno', '-criada_em']),
        ]

    def __str__(self):
        return f'[{self.linha.nome}] {self.autor.username}: {self.texto[:50]}'


class MencaoMensagem(models.Model):
    """
    Registro de @menção: uma mensagem menciona um usuário.
    Controla leitura para exibir badge de notificação.
    """
    mensagem   = models.ForeignKey(MensagemLinha, on_delete=models.CASCADE, related_name='mencoes')
    mencionado = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mencoes_recebidas')
    lida       = models.BooleanField(default=False)
    lida_em    = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Menção'
        verbose_name_plural = 'Menções'
        unique_together = ('mensagem', 'mencionado')

    def __str__(self):
        return f'@{self.mencionado.username} em msg#{self.mensagem_id}'


# ==================== RECIPE MONITOR — Sincronismo CLP → Receita ====================

class ContaUsuarioExpiracao(models.Model):
    """
    Controle de validade de contas de usuários comuns (não-superuser).

    Duas travas de expiração (a que ocorrer primeiro bloqueia o login):
      1. Inatividade: sem login há mais de DIAS_INATIVIDADE (60 dias / 2 meses)
      2. Validade: passou de `validade_ate` (criação + VALIDADE_MESES = 5 meses)

    Só superuser pode renovar (reseta validade_ate = agora + 5 meses e
    reativa is_active). Superusers NÃO têm conta de expiração — nunca expiram.
    """
    DIAS_INATIVIDADE = 60      # 2 meses
    VALIDADE_MESES = 5         # renovação a cada 5 meses
    VALIDADE_DIAS = 150        # ~5 meses em dias (usado nos cálculos)

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='expiracao'
    )
    validade_ate = models.DateTimeField(
        help_text='Conta expira nesta data (criação/renovação + 5 meses).'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    renovado_em = models.DateTimeField(null=True, blank=True)
    renovado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='renovacoes_concedidas'
    )

    class Meta:
        verbose_name = 'Validade de Conta de Usuário'
        verbose_name_plural = 'Validades de Contas de Usuários'
        ordering = ['validade_ate']

    def __str__(self):
        return f'{self.user.username} — válido até {self.validade_ate:%Y-%m-%d}'

    # ── Lógica de expiração ───────────────────────────────────────────

    def dias_ate_validade(self):
        from django.utils import timezone
        delta = self.validade_ate - timezone.now()
        return delta.days

    def dias_inativo(self):
        """Dias desde o último login. None se nunca logou."""
        from django.utils import timezone
        if not self.user.last_login:
            return None
        return (timezone.now() - self.user.last_login).days

    def motivo_expiracao(self):
        """
        Retorna 'validade', 'inatividade' ou None se a conta ainda é válida.
        Superuser nunca expira.
        """
        from django.utils import timezone
        if self.user.is_superuser:
            return None
        if self.validade_ate < timezone.now():
            return 'validade'
        inativo = self.dias_inativo()
        if inativo is not None and inativo >= self.DIAS_INATIVIDADE:
            return 'inatividade'
        return None

    def expirada(self):
        return self.motivo_expiracao() is not None

    def renovar(self, por_usuario=None):
        """
        Reseta validade por +5 meses, zera o contador de inatividade e reativa.

        IMPORTANTE: também atualiza last_login. Sem isso, uma conta bloqueada
        por INATIVIDADE (60 dias sem login) continuaria sendo bloqueada no
        próximo login mesmo após a renovação, porque motivo_expiracao() ainda
        veria o last_login antigo. Renovar = "vale mais 5 meses e conta como
        se tivesse acabado de logar".
        """
        from django.utils import timezone
        from datetime import timedelta
        agora = timezone.now()
        self.validade_ate = agora + timedelta(days=self.VALIDADE_DIAS)
        self.renovado_em = agora
        self.renovado_por = por_usuario
        self.save()

        update_fields = []
        if not self.user.is_active:
            self.user.is_active = True
            update_fields.append('is_active')
        # Zera a inatividade (destrava contas bloqueadas por 60 dias sem login)
        self.user.last_login = agora
        update_fields.append('last_login')
        self.user.save(update_fields=update_fields)


class HistoricoSincronismoReceita(models.Model):
    """
    Registro imutável de cada sincronismo "valores do CLP → FormatoVariavel"
    feito pelo Recipe Monitor (serviço externo mis-recipe-intelligent).

    Cada linha aqui representa UMA variável atualizada dentro de UM
    sincronismo. Um único clique em "Atualizar receita" pode gerar N linhas
    (uma por variável que mudou). O campo `lote_uuid` agrupa as variáveis
    de um mesmo sincronismo.

    NÃO altera nem depende do fluxo de TrocaSKU / LogEquipamentoTroca —
    é um histórico paralelo, focado em receituário.
    """
    lote_uuid = models.UUIDField(
        db_index=True,
        help_text='Agrupa as variáveis atualizadas em um único clique de sincronismo.'
    )
    formato = models.ForeignKey(
        Formato, on_delete=models.PROTECT,
        related_name='historico_sincronismos'
    )
    variavel = models.ForeignKey(
        Variavel, on_delete=models.PROTECT,
        related_name='historico_sincronismos'
    )
    linha = models.ForeignKey(
        Linha, on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='historico_sincronismos_receita',
        help_text='Linha de onde o valor foi lido no momento do sincronismo (informativo).'
    )

    valor_anterior = models.CharField(max_length=100, blank=True)
    valor_novo = models.CharField(max_length=100)

    usuario = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='sincronismos_receita'
    )
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    origem_servico = models.CharField(
        max_length=50, default='recipe-monitor',
        help_text='Serviço que originou o sincronismo. Default: recipe-monitor.'
    )
    observacao = models.TextField(blank=True)

    data_hora = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Histórico de Sincronismo de Receita'
        verbose_name_plural = 'Histórico de Sincronismos de Receita'
        ordering = ['-data_hora']
        indexes = [
            models.Index(fields=['formato', '-data_hora']),
            models.Index(fields=['lote_uuid']),
        ]

    def __str__(self):
        return (f'Sync {self.formato.nome} / {self.variavel.nome}: '
                f'{self.valor_anterior} → {self.valor_novo} '
                f'({self.usuario.username} em {self.data_hora:%Y-%m-%d %H:%M})')


class UltimaVisualizacaoChat(models.Model):
    """
    Registra quando um usuário visualizou pela última vez o chat de uma linha.
    Usado para calcular mensagens não lidas por linha no sidebar.
    """
    usuario    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='visualizacoes_chat')
    linha      = models.ForeignKey(Linha, on_delete=models.CASCADE, related_name='visualizacoes_chat')
    visualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Última Visualização de Chat'
        verbose_name_plural = 'Últimas Visualizações de Chat'
        unique_together = ('usuario', 'linha')

    def __str__(self):
        return f'{self.usuario.username} — {self.linha.nome} em {self.visualizado_em}'
