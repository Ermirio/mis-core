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
    
    # Campos de auditoria
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='formatos_criados')
    atualizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='formatos_atualizados')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    def __str__(self):
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

