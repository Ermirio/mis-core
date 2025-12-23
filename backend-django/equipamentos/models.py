from django.db import models, transaction
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# ===== HIERARQUIA: FÁBRICA E ÁREA =====

class Fabrica(models.Model):
    """Fábrica (unidade fabril)"""
    nome = models.CharField(max_length=100, verbose_name='Nome da Fábrica')
    codigo = models.CharField(max_length=20, unique=True, verbose_name='Código', blank=True)
    localizacao = models.CharField(max_length=200, blank=True, verbose_name='Localização')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Fábrica'
        verbose_name_plural = 'Fábricas'
        ordering = ['nome']

    def save(self, *args, **kwargs):
        """Auto-gera código sequencial se não fornecido"""
        if not self.codigo:
            with transaction.atomic():
                # Busca o último código F existente
                last_fabrica = Fabrica.objects.select_for_update().filter(
                    codigo__startswith='F'
                ).order_by('-codigo').first()
                
                if last_fabrica and last_fabrica.codigo[1:].isdigit():
                    # Extrai o número e incrementa
                    last_num = int(last_fabrica.codigo[1:])
                    new_num = last_num + 1
                else:
                    # Primeira fábrica
                    new_num = 1
                
                self.codigo = f'F{new_num:03d}'
                logger.info(f"✓ Gerado código {self.codigo} para fábrica '{self.nome}'")
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.nome} ({self.codigo})'

class Area(models.Model):
    """Área dentro de uma fábrica (ex: Envase, Preparação, Utilidades)"""
    fabrica = models.ForeignKey(Fabrica, on_delete=models.CASCADE, related_name='areas', verbose_name='Fábrica')
    nome = models.CharField(max_length=100, verbose_name='Nome da Área')
    codigo = models.CharField(max_length=20, unique=True, verbose_name='Código')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Área'
        verbose_name_plural = 'Áreas'
        ordering = ['fabrica', 'nome']

    def __str__(self):
        return f'{self.nome} - {self.fabrica.codigo}'

# ===== PRODUTOS (SKU) =====

class Produto(models.Model):
    """Produto / SKU"""
    codigo = models.CharField(max_length=50, unique=True, verbose_name='Código SKU')
    descricao = models.CharField(max_length=200, verbose_name='Descrição')
    peso_unitario = models.DecimalField(
        max_digits=10, 
        decimal_places=3, 
        verbose_name='Peso Unitário (g)',
        help_text='Peso do produto em gramas'
    )
    fator_conversao = models.FloatField(
        default=1.0, 
        verbose_name='Fator de Conversão',
        help_text='Fator para converter unidades em caixas/fardos se necessário'
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Produto (SKU)'
        verbose_name_plural = 'Produtos (SKUs)'
        ordering = ['codigo']

    def __str__(self):
        return f'{self.codigo} - {self.descricao}'

# ===== LINHAS DE PRODUÇÃO =====

class LinhaProducao(models.Model):
    """Linha de produção completa"""
    codigo = models.CharField(max_length=20, unique=True, verbose_name='Código da Linha')
    nome = models.CharField(max_length=100, verbose_name='Nome da Linha')
    area = models.ForeignKey(
        Area, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='linhas', 
        verbose_name='Área'
    )
    descricao = models.TextField(blank=True, verbose_name='Descrição')
    localizacao = models.CharField(max_length=200, verbose_name='Localização')
    ativa = models.BooleanField(default=True, verbose_name='Linha Ativa')
    velocidade_planejada = models.FloatField(
        validators=[MinValueValidator(0)],
        verbose_name='Velocidade Planejada (unid/min)',
        help_text='Velocidade planejada da linha completa'
    )
    meta_producao_hora = models.IntegerField(
        validators=[MinValueValidator(0)],
        verbose_name='Meta Produção/Hora'
    )
    meta_producao_turno = models.IntegerField(
        validators=[MinValueValidator(0)],
        verbose_name='Meta Produção/Turno (8h)'
    )
    meta_oee = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=85.0,
        verbose_name='Meta OEE (%)',
        help_text='Meta de OEE para a linha'
    )
    
    # Metas de tonelagem
    meta_toneladas_hora = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name='Meta Toneladas/Hora',
        help_text='Meta de produção em toneladas por hora'
    )
    meta_toneladas_turno = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name='Meta Toneladas/Turno',
        help_text='Meta de produção em toneladas por turno (8h)'
    )
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Linha de Produção'
        verbose_name_plural = 'Linhas de Produção'
        ordering = ['codigo']
    
    def __str__(self):
        return f'{self.codigo} - {self.nome}'
    
    # ===== ALIASES PARA CONSULTAS DE BI =====
    @property
    def site(self):
        """Alias para fabrica (via area) - facilita queries de BI"""
        return self.area.fabrica if self.area else None
    
    @property
    def tecnologia(self):
        """Alias para area - facilita queries de BI"""
        return self.area

class HistoricoSKU(models.Model):
    """Histórico de SKUs rodando na linha"""
    linha = models.ForeignKey(LinhaProducao, on_delete=models.CASCADE, related_name='historico_skus', verbose_name='Linha')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='historico_linhas', verbose_name='Produto (SKU)')
    ordem_producao = models.CharField(max_length=50, blank=True, verbose_name='Ordem de Produção')
    meta_producao = models.IntegerField(default=0, verbose_name='Meta de Produção')
    producao_realizada = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0.0,
        verbose_name='Produção Realizada (ton)'
    )
    data_inicio = models.DateTimeField(verbose_name='Data Início', db_index=True)
    data_fim = models.DateTimeField(null=True, blank=True, verbose_name='Data Fim')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Histórico de SKU'
        verbose_name_plural = 'Histórico de SKUs'
        ordering = ['-data_inicio']
        indexes = [
            models.Index(fields=['linha', 'data_inicio']),
        ]

    def __str__(self):
        return f'{self.linha.codigo} - {self.produto.codigo} ({self.data_inicio})'

# ===== ORDEM DE PRODUÇÃO (PLANEJAMENTO) =====

class OrdemProducao(models.Model):
    """Ordem de Produção - Planejamento e Controle"""
    
    STATUS_CHOICES = [
        ('PLANEJADA', 'Planejada'),
        ('PRODUZINDO', 'Em Produção'),
        ('PAUSADA', 'Pausada'),
        ('CONCLUIDA', 'Concluída'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    # Identificação
    codigo = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name='Código da OP',
        db_index=True
    )
    
    # Relacionamentos
    linha = models.ForeignKey(
        LinhaProducao,
        on_delete=models.CASCADE,
        related_name='ordens_producao',
        verbose_name='Linha de Produção'
    )
    produto = models.ForeignKey(
        Produto,
        on_delete=models.CASCADE,
        related_name='ordens_producao',
        verbose_name='Produto (SKU)'
    )
    
    # Planejamento
    meta_total = models.IntegerField(
        validators=[MinValueValidator(0)],
        verbose_name='Meta Total',
        help_text='Meta total de produção para esta OP'
    )
    # meta_turno removido conforme solicitação (vem do calendário)
    
    # Formato e Custos
    formato_gramas = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Formato (gramas)',
        help_text='Peso unitário do produto em gramas'
    )
    cuc = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name='CUC',
        help_text='Custo Unitário de Conversão'
    )
    eficiencia_planejada = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=85.0,
        verbose_name='Eficiência Planejada (%)'
    )
    
    # Status e Controle
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PLANEJADA',
        verbose_name='Status'
    )
    
    # Datas
    data_planejada_inicio = models.DateTimeField(
        verbose_name='Data Planejada de Início'
    )
    data_inicio_real = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data Real de Início'
    )
    data_fim_real = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data Real de Término'
    )
    
    # Produção Realizada (Materializada)
    producao_realizada = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0.0,
        verbose_name='Produção Realizada (ton)',
        help_text='Total produzido acumulado para esta OP'
    )
    
    # Informações adicionais
    descricao = models.TextField(
        blank=True,
        verbose_name='Descrição'
    )
    observacoes = models.TextField(
        blank=True,
        verbose_name='Observações'
    )
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Ordem de Produção'
        verbose_name_plural = 'Ordens de Produção'
        ordering = ['-data_planejada_inicio']
        indexes = [
            models.Index(fields=['codigo']),
            models.Index(fields=['status']),
            models.Index(fields=['linha', 'status']),
        ]
    
    def __str__(self):
        return f'{self.codigo} - {self.produto.codigo} ({self.get_status_display()})'
    
    @property
    def producao_total_realizada(self):
        """Soma da produção de todos os turnos desta OP"""
        return self.registros_turno.aggregate(
            total=models.Sum('producao_unidades')
        )['total'] or 0
    
    @property
    def percentual_conclusao(self):
        """Percentual de conclusão da OP"""
        if self.meta_total > 0:
            return min(100, (self.producao_total_realizada / self.meta_total) * 100)
        return 0

# ===== CONEXÕES OPC =====

class ConexaoOPC(models.Model):
    """Configuração de conexão OPC UA"""
    nome = models.CharField(max_length=100, unique=True, verbose_name='Nome da Conexão')
    url_servidor = models.CharField(
        max_length=255,
        verbose_name='URL do Servidor OPC',
        help_text='Ex: opc.tcp://192.168.1.10:4840'
    )
    namespace_prefix = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Prefixo do Namespace',
        help_text='Ex: ns=2;s='
    )
    usuario = models.CharField(max_length=100, blank=True, verbose_name='Usuário')
    senha = models.CharField(max_length=100, blank=True, verbose_name='Senha')
    timeout = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1)],
        verbose_name='Timeout (segundos)'
    )
    ativa = models.BooleanField(default=True, verbose_name='Conexão Ativa')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Conexão OPC'
        verbose_name_plural = 'Conexões OPC'
        ordering = ['nome']
    
    def __str__(self):
        return f'{self.nome} ({self.url_servidor})'

# ===== EQUIPAMENTOS =====

class TipoEquipamento(models.TextChoices):
    """Tipos comuns de equipamento (sugestões)"""
    ENCHEDORA = 'ENCHEDORA', 'Enchedora'
    PALETIZADOR = 'PALETIZADOR', 'Paletizador'
    BALANCA = 'BALANCA', 'Balança'
    ENCAIXOTADORA = 'ENCAIXOTADORA', 'Encaixotadora'
    ENVOLVEDORA = 'ENVOLVEDORA', 'Envolvedora'
    CODIFICADORA = 'CODIFICADORA', 'Codificadora'
    TRANSPORTADOR = 'TRANSPORTADOR', 'Transportador/Esteira'
    OUTRO = 'OUTRO', 'Outro'

class StatusEquipamento(models.TextChoices):
    ATIVO = 'ATIVO', 'Ativo'
    INATIVO = 'INATIVO', 'Inativo'
    MANUTENCAO = 'MANUTENCAO', 'Em Manutenção'

# ===== NOVO: ESTADOS INDUSTRIAIS =====

class EstadoEquipamento(models.TextChoices):
    """Estados industriais para cálculo de OEE"""
    RUN = 'RUN', 'Produzindo'
    PARTINDO = 'PARTINDO', 'Partindo'
    PARANDO = 'PARANDO', 'Parando'
    WAIT_PREV = 'WAIT_PREV', 'Aguardando equipamento anterior'
    BLOCK_NEXT = 'BLOCK_NEXT', 'Equipamento seguinte bloqueado'
    FAULT = 'FAULT', 'Falha'
    SETUP = 'SETUP', 'Setup / Troca SKU'
    TESTE_PROJ = 'TESTE_PROJ', 'Teste de Projeto'
    AGUARD_MNT = 'AGUARD_MNT', 'Aguardando Manutenção'
    MANUTENCAO = 'MANUTENCAO', 'Em Manutenção'
    FALTA_MAT = 'FALTA_MAT', 'Falta de Material'
    OUTRO = 'OUTRO', 'Outro'

class Equipamento(models.Model):
    """Equipamento individual dentro de uma linha"""
    linha = models.ForeignKey(
        LinhaProducao,
        on_delete=models.CASCADE,
        related_name='equipamentos',
        verbose_name='Linha de Produção'
    )
    nome = models.CharField(max_length=100, unique=True, verbose_name='Nome do Equipamento')
    codigo = models.CharField(max_length=50, unique=True, verbose_name='Código', blank=True)
    tipo = models.CharField(
        max_length=50, 
        verbose_name='Tipo',
        help_text='Tipo do equipamento. Sugestões: ENCHEDORA, PALETIZADOR, BALANCA, ENCAIXOTADORA, ENVOLVEDORA, CODIFICADORA, TRANSPORTADOR, ou crie um tipo personalizado'
    )
    ordem_na_linha = models.IntegerField(
        default=1,
        verbose_name='Ordem na Linha',
        help_text='Posição do equipamento na sequência da linha (1, 2, 3...)'
    )
    localizacao = models.CharField(max_length=200, verbose_name='Localização')
    status = models.CharField(
        max_length=20,
        choices=StatusEquipamento.choices,
        default=StatusEquipamento.ATIVO,
        verbose_name='Status'
    )
    velocidade_nominal = models.FloatField(
        validators=[MinValueValidator(0)],
        verbose_name='Velocidade Nominal (unid/min)',
        help_text='Velocidade nominal do equipamento'
    )
    velocidade_maxima = models.FloatField(
        validators=[MinValueValidator(0)],
        verbose_name='Velocidade Máxima (unid/min)'
    )
    meta_oee = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=85.0,
        verbose_name='Meta OEE (%)',
        help_text='Meta de OEE para o equipamento'
    )
    temperatura_min = models.FloatField(null=True, blank=True, verbose_name='Temp. Mínima (°C)')
    temperatura_max = models.FloatField(null=True, blank=True, verbose_name='Temp. Máxima (°C)')
    pressao_min = models.FloatField(null=True, blank=True, verbose_name='Pressão Mínima (PSI)')
    pressao_max = models.FloatField(null=True, blank=True, verbose_name='Pressão Máxima (PSI)')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    observacoes = models.TextField(blank=True, verbose_name='Observações')
    
    class Meta:
        verbose_name = 'Equipamento'
        verbose_name_plural = 'Equipamentos'
        ordering = ['linha', 'ordem_na_linha']
    
    def save(self, *args, **kwargs):
        """Auto-gera código sequencial se não fornecido"""
        if not self.codigo:
            with transaction.atomic():
                # Busca o último código E existente
                last_equipamento = Equipamento.objects.select_for_update().filter(
                    codigo__startswith='E'
                ).order_by('-codigo').first()
                
                if last_equipamento and last_equipamento.codigo[1:].isdigit():
                    # Extrai o número e incrementa
                    last_num = int(last_equipamento.codigo[1:])
                    new_num = last_num + 1
                else:
                    # Primeiro equipamento
                    new_num = 1
                
                self.codigo = f'E{new_num:03d}'
                logger.info(f"✓ Gerado código {self.codigo} para equipamento '{self.nome}' (Linha: {self.linha.codigo})")
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f'{self.nome} ({self.tipo})'

# ===== TAGS DE COLETA =====

class TipoDado(models.TextChoices):
    INT = 'INT', 'Inteiro'
    FLOAT = 'FLOAT', 'Decimal'
    STRING = 'STRING', 'Texto'
    BOOL = 'BOOL', 'Booleano'

class TagColeta(models.Model):
    """Tag OPC para coleta de dados de um equipamento"""
    equipamento = models.ForeignKey(
        Equipamento,
        on_delete=models.CASCADE,
        related_name='tags_coleta',
        verbose_name='Equipamento'
    )
    conexao = models.ForeignKey(
        ConexaoOPC,
        on_delete=models.CASCADE,
        related_name='tags',
        verbose_name='Conexão OPC'
    )
    nome_metrica = models.CharField(
        max_length=100,
        verbose_name='Nome da Métrica',
        help_text='Ex: velocidade_atual, contagem_entrada, contagem_saida, estado'
    )
    node_id = models.CharField(
        max_length=255,
        verbose_name='Node ID',
        help_text='Ex: ns=2;s=Linha1.Enchedora.Velocidade'
    )
    tipo_dado = models.CharField(
        max_length=20,
        choices=TipoDado.choices,
        default=TipoDado.INT,
        verbose_name='Tipo de Dado'
    )
    formato = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Formato (gramas)',
        help_text='Peso unitário do produto em gramas (ex: 2200, 1600). Usado para calcular toneladas produzidas.'
    )
    unidade = models.CharField(max_length=20, blank=True, verbose_name='Unidade')
    fator_conversao = models.FloatField(
        default=1.0,
        verbose_name='Fator de Conversão',
        help_text='Multiplicador aplicado ao valor lido'
    )
    ativa = models.BooleanField(default=True, verbose_name='Tag Ativa')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Tag de Coleta'
        verbose_name_plural = 'Tags de Coleta'
        ordering = ['equipamento', 'nome_metrica']
        unique_together = ['equipamento', 'nome_metrica']
    
    def __str__(self):
        return f'{self.equipamento.nome} - {self.nome_metrica}'

# ===== SENSORES =====

class TipoSensor(models.TextChoices):
    INPUT_BOOL = 'INPUT_BOOL', 'Input Digital (Booleano)'
    INPUT_FLOAT = 'INPUT_FLOAT', 'Input Analógico (Decimal)'
    INPUT_INT = 'INPUT_INT', 'Input Inteiro'
    TIMER = 'TIMER', 'Temporizador (Tempo)'
    COUNTER = 'COUNTER', 'Contador'
    SETPOINT = 'SETPOINT', 'Setpoint / Ajuste'
    LIMIT = 'LIMIT', 'Limite / Parâmetro'
    OUTRO = 'OUTRO', 'Outro'

class Sensor(models.Model):
    """Sensor associado a um equipamento ou linha"""
    equipamento = models.ForeignKey(
        Equipamento,
        on_delete=models.CASCADE,
        related_name='sensores',
        null=True,
        blank=True,
        verbose_name='Equipamento'
    )
    linha = models.ForeignKey(
        LinhaProducao,
        on_delete=models.CASCADE,
        related_name='sensores',
        null=True,
        blank=True,
        verbose_name='Linha de Produção',
        help_text='Para sensores de entrada/saída da linha inteira'
    )
    codigo = models.CharField(max_length=50, unique=True, verbose_name='Código do Sensor')
    nome = models.CharField(max_length=100, verbose_name='Nome do Sensor')
    tipo = models.CharField(max_length=20, choices=TipoSensor.choices, verbose_name='Tipo')
    tag_influxdb = models.CharField(
        max_length=100,
        verbose_name='Tag InfluxDB',
        help_text='Nome do campo no InfluxDB (ex: contagem_entrada, temperatura)'
    )
    unidade = models.CharField(max_length=20, blank=True, verbose_name='Unidade de Medida')
    ativo = models.BooleanField(default=True, verbose_name='Sensor Ativo')
    valor_min = models.FloatField(null=True, blank=True, verbose_name='Valor Mínimo (Gauge)')
    valor_max = models.FloatField(null=True, blank=True, verbose_name='Valor Máximo (Gauge)')
    
    # Campos para CEP (Controle Estatístico de Processo)
    lsl = models.FloatField(null=True, blank=True, verbose_name='LSL (Limite Inferior de Especificação)')
    usl = models.FloatField(null=True, blank=True, verbose_name='USL (Limite Superior de Especificação)')
    nominal = models.FloatField(null=True, blank=True, verbose_name='Valor Nominal (Target)')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    observacoes = models.TextField(blank=True, verbose_name='Observações')
    
    class Meta:
        verbose_name = 'Sensor'
        verbose_name_plural = 'Sensores'
        ordering = ['linha', 'equipamento', 'tipo']
    
    def __str__(self):
        if self.equipamento:
            return f'{self.codigo} - {self.nome} ({self.equipamento.nome})'
        elif self.linha:
            return f'{self.codigo} - {self.nome} (Linha {self.linha.codigo})'
        return f'{self.codigo} - {self.nome}'
    
    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.equipamento and not self.linha:
            raise ValidationError('Sensor deve estar associado a um equipamento ou linha')
        if self.equipamento and self.linha:
            raise ValidationError('Sensor não pode estar associado a equipamento e linha simultaneamente')

# ===== NOVO: TURNOS DE PRODUÇÃO =====

class TurnoProducao(models.Model):
    """Definição de turnos de produção"""
    nome = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Nome do Turno',
        help_text='Ex: Turno A, Turno B, Turno C'
    )
    codigo = models.CharField(
        max_length=10,
        unique=True,
        verbose_name='Código',
        help_text='Ex: A, B, C'
    )
    hora_inicio = models.TimeField(verbose_name='Hora de Início')
    hora_fim = models.TimeField(verbose_name='Hora de Fim')
    duracao_horas = models.FloatField(
        validators=[MinValueValidator(0)],
        verbose_name='Duração (horas)',
        help_text='Duração do turno em horas'
    )
    ativo = models.BooleanField(default=True, verbose_name='Turno Ativo')
    observacoes = models.TextField(blank=True, verbose_name='Observações')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Turno de Produção'
        verbose_name_plural = 'Turnos de Produção'
        ordering = ['hora_inicio']
    
    def __str__(self):
        return f'{self.nome} ({self.hora_inicio.strftime("%H:%M")} - {self.hora_fim.strftime("%H:%M")})'

# ===== NOVO: CALENDÁRIO DE PRODUÇÃO =====

class CalendarioProducao(models.Model):
    """Calendário de produção por linha e turno"""
    data = models.DateField(verbose_name='Data', db_index=True)
    linha = models.ForeignKey(
        LinhaProducao,
        on_delete=models.CASCADE,
        related_name='calendario',
        verbose_name='Linha de Produção'
    )
    turno = models.ForeignKey(
        TurnoProducao,
        on_delete=models.CASCADE,
        related_name='calendario',
        verbose_name='Turno'
    )
    programado = models.BooleanField(
        default=True,
        verbose_name='Programado',
        help_text='Se a linha deve produzir neste dia/turno'
    )
    meta_producao_turno = models.IntegerField(
        validators=[MinValueValidator(0)],
        verbose_name='Meta de Produção do Turno',
        help_text='Meta de produção para este turno específico'
    )
    observacoes = models.TextField(blank=True, verbose_name='Observações')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Calendário de Produção'
        verbose_name_plural = 'Calendários de Produção'
        ordering = ['-data', 'linha', 'turno']
        unique_together = ['data', 'linha', 'turno']
        indexes = [
            models.Index(fields=['data', 'turno']),
        ]
    
    def __str__(self):
        status = 'Programado' if self.programado else 'Não Programado'
        return f'{self.linha.codigo} - {self.data} - {self.turno.codigo} ({status})'

# ===== NOVO: TIPOS DE FALHA =====

class TipoFalha(models.Model):
    """Tipos de falha para classificação de paradas"""
    CATEGORIAS = [
        ('MECANICA', 'Falha Mecânica'),
        ('ELETRICA', 'Falha Elétrica'),
        ('OPERACIONAL', 'Erro Operacional'),
        ('MATERIA_PRIMA', 'Problema Matéria-Prima'),
        ('QUALIDADE', 'Problema de Qualidade'),
        ('SETUP', 'Setup/Troca'),
        ('OUTROS', 'Outros'),
    ]
    
    codigo = models.CharField(max_length=50, unique=True, verbose_name='Código')
    nome = models.CharField(max_length=200, verbose_name='Nome')
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIAS,
        verbose_name='Categoria'
    )
    cor = models.CharField(
        max_length=7,
        default='#FF0000',
        verbose_name='Cor (Hex)',
        help_text='Cor para visualização em gráficos (ex: #FF0000)'
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Tipo de Falha'
        verbose_name_plural = 'Tipos de Falha'
        ordering = ['categoria', 'nome']
    
    def __str__(self):
        return f'{self.nome} ({self.get_categoria_display()})'

# ===== NOVO: EVENTOS DE ESTADO =====

class EventoEstadoEquipamento(models.Model):
    """Registro de mudanças de estado de equipamentos para cálculo de tempos"""
    equipamento = models.ForeignKey(
        Equipamento,
        on_delete=models.CASCADE,
        related_name='eventos_estado',
        verbose_name='Equipamento'
    )
    estado = models.CharField(
        max_length=20,
        choices=EstadoEquipamento.choices,
        verbose_name='Estado'
    )
    inicio = models.DateTimeField(verbose_name='Início', db_index=True)
    fim = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fim',
        help_text='Null enquanto o evento estiver aberto'
    )
    duracao_segundos = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Duração (segundos)',
        help_text='Calculado automaticamente ao fechar o evento'
    )
    origem = models.CharField(
        max_length=20,
        choices=[('OPC', 'OPC UA'), ('MANUAL', 'Manual'), ('SISTEMA', 'Sistema')],
        default='OPC',
        verbose_name='Origem'
    )
    
    # Análise de perdas
    tipo_falha = models.ForeignKey(
        'TipoFalha',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos',
        verbose_name='Tipo de Falha',
        help_text='Tipo de falha (se estado=FAULT ou parada)'
    )
    toneladas_perdidas = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name='Toneladas Perdidas',
        help_text='Toneladas perdidas durante este evento (calculado automaticamente)'
    )
    
    observacao = models.TextField(blank=True, verbose_name='Observação')
    criado_em = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Evento de Estado'
        verbose_name_plural = 'Eventos de Estado'
        ordering = ['-inicio']
        indexes = [
            models.Index(fields=['equipamento', 'inicio']),
            models.Index(fields=['equipamento', 'estado']),
        ]
    
    def __str__(self):
        if self.fim:
            return f'{self.equipamento.nome} - {self.get_estado_display()} ({self.duracao_segundos}s)'
        return f'{self.equipamento.nome} - {self.get_estado_display()} (Em andamento)'
    
    def save(self, *args, **kwargs):
        # Calcula duração automaticamente se fim estiver preenchido
        if self.fim and self.inicio:
            delta = self.fim - self.inicio
            self.duracao_segundos = int(delta.total_seconds())
        super().save(*args, **kwargs)
    
    @classmethod
    def fechar_evento_aberto(cls, equipamento):
        """Fecha o último evento aberto do equipamento"""
        evento_aberto = cls.objects.filter(
            equipamento=equipamento,
            fim__isnull=True
        ).first()
        
        if evento_aberto:
            evento_aberto.fim = timezone.now()
            evento_aberto.save()
            return evento_aberto
        return None
    
    @classmethod
    def calcular_tempos_por_estado(cls, equipamento, inicio, fim):
        """
        Calcula tempos por categoria de estado em um intervalo
        
        Retorna dict com:
        - tempo_producao (RUN)
        - tempo_parada (FAULT, FALTA_MAT, AGUARD_MNT, WAIT_PREV, BLOCK_NEXT)
        - tempo_setup (SETUP)
        - tempo_nao_programado (MANUTENCAO, TESTE_PROJ)
        """
        eventos = cls.objects.filter(
            equipamento=equipamento,
            inicio__lt=fim
        ).filter(
            models.Q(fim__gte=inicio) | models.Q(fim__isnull=True)
        )
        
        tempos = {
            'tempo_producao': 0,
            'tempo_parada': 0,
            'tempo_setup': 0,
            'tempo_nao_programado': 0,
        }
        
        # Mapeamento de estados para categorias
        estados_producao = [EstadoEquipamento.RUN]
        estados_parada = [
            EstadoEquipamento.FAULT,
            EstadoEquipamento.FALTA_MAT,
            EstadoEquipamento.AGUARD_MNT,
            EstadoEquipamento.WAIT_PREV,
            EstadoEquipamento.BLOCK_NEXT,
        ]
        estados_setup = [EstadoEquipamento.SETUP]
        estados_nao_programado = [
            EstadoEquipamento.MANUTENCAO,
            EstadoEquipamento.TESTE_PROJ,
        ]
        
        for evento in eventos:
            # Ajusta início e fim do evento para o intervalo solicitado
            evento_inicio = max(evento.inicio, inicio)
            # Se evento está aberto (fim=None), considera até o fim da janela
            evento_fim_real = evento.fim if evento.fim else fim
            evento_fim = min(evento_fim_real, fim)
            
            duracao = (evento_fim - evento_inicio).total_seconds()
            
            if duracao <= 0:
                continue
            
            # Classifica o tempo
            if evento.estado in estados_producao:
                tempos['tempo_producao'] += duracao
            elif evento.estado in estados_parada:
                tempos['tempo_parada'] += duracao
            elif evento.estado in estados_setup:
                tempos['tempo_setup'] += duracao
            elif evento.estado in estados_nao_programado:
                tempos['tempo_nao_programado'] += duracao
        
        # Converte para minutos
        for key in tempos:
            tempos[key] = tempos[key] / 60.0
        
        return tempos

# ===== MÉTRICAS E PRODUÇÃO (ATUALIZADO) =====

class MetricaProducao(models.Model):
    """Métricas agregadas de produção com cálculo real de OEE"""
    linha = models.ForeignKey(
        LinhaProducao,
        on_delete=models.CASCADE,
        related_name='metricas',
        verbose_name='Linha'
    )
    equipamento = models.ForeignKey(
        Equipamento,
        on_delete=models.CASCADE,
        related_name='metricas',
        null=True,
        blank=True,
        verbose_name='Equipamento',
        help_text='Deixe em branco para métricas da linha inteira'
    )
    data_hora = models.DateTimeField(verbose_name='Data/Hora', db_index=True)
    periodo = models.CharField(
        max_length=20,
        choices=[
            ('HORA', 'Hora'),
            ('TURNO', 'Turno'),
            ('DIA', 'Dia'),
            ('SEMANA', 'Semana'),
            ('MES', 'Mês'),
            ('ANO', 'Ano'),
        ],
        default='HORA',
        verbose_name='Período'
    )
    turno = models.CharField(max_length=20, blank=True, verbose_name='Turno')
    
    # SKU
    produto = models.ForeignKey(
        Produto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='metricas',
        verbose_name='Produto (SKU)'
    )
    
    # Ordem de Produção
    ordem_producao = models.CharField(max_length=50, blank=True, verbose_name='Ordem de Produção')
    meta_producao = models.IntegerField(default=0, verbose_name='Meta de Produção')
    
    # Contadores de entrada/saída
    contagem_entrada = models.IntegerField(default=0, verbose_name='Contagem Entrada')
    contagem_saida = models.IntegerField(default=0, verbose_name='Contagem Saída')
    descarte = models.IntegerField(default=0, verbose_name='Descarte')
    percentual_descarte = models.FloatField(default=0.0, verbose_name='% Descarte')
    
    # Velocidades
    velocidade_planejada = models.FloatField(default=0.0, verbose_name='Velocidade Planejada')
    velocidade_real = models.FloatField(default=0.0, verbose_name='Velocidade Real')
    
    # Tonelagem (produção em peso)
    toneladas_produzidas = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0,
        verbose_name='Toneladas Produzidas',
        help_text='Total de toneladas de produto bom (contagem_saida × formato / 1.000.000)'
    )
    vazao_real_ton_hora = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        verbose_name='Vazão Real (ton/h)',
        help_text='Toneladas por hora efetiva de produção'
    )
    toneladas_hora = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        verbose_name='Toneladas/Hora (Absoluto)',
        help_text='Toneladas produzidas na hora cheia'
    )
    formato_gramas = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Formato (g)',
        help_text='Peso unitário usado no cálculo de toneladas'
    )
    
    # Tempos (em minutos)
    tempo_programado = models.FloatField(default=0.0, verbose_name='Tempo Programado (min)')
    tempo_disponivel = models.FloatField(default=0.0, verbose_name='Tempo Disponível (min)')
    tempo_producao = models.FloatField(default=0.0, verbose_name='Tempo Produção (min)')
    tempo_parada = models.FloatField(default=0.0, verbose_name='Tempo Parada (min)')
    tempo_setup = models.FloatField(default=0.0, verbose_name='Tempo Setup (min)')
    tempo_nao_programado = models.FloatField(default=0.0, verbose_name='Tempo Não Programado (min)')
    
    # KPIs
    disponibilidade = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Disponibilidade (%)'
    )
    performance = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Performance (%)'
    )
    qualidade = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Qualidade (%)'
    )
    oee = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='OEE (%)'
    )
    
    calculado_em = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Métrica de Produção'
        verbose_name_plural = 'Métricas de Produção'
        ordering = ['-data_hora']
        unique_together = ['linha', 'equipamento', 'data_hora', 'periodo']
    
    def __str__(self):
        if self.equipamento:
            return f'{self.equipamento.nome} - {self.data_hora} - OEE: {self.oee:.1f}%'
        return f'{self.linha.codigo} - {self.data_hora} - OEE: {self.oee:.1f}%'
    
    def save(self, *args, **kwargs):
        """Calcula KPIs automaticamente antes de salvar"""
        # Calcula descarte
        if self.contagem_entrada > 0:
            self.descarte = self.contagem_entrada - self.contagem_saida
            self.percentual_descarte = (self.descarte / self.contagem_entrada) * 100
        else:
            self.descarte = 0
            self.percentual_descarte = 0.0
        
        # Calcula tempo disponível
        self.tempo_disponivel = self.tempo_programado - self.tempo_nao_programado
        
        # Calcula Disponibilidade (A)
        if self.tempo_disponivel > 0:
            self.disponibilidade = min(100, (self.tempo_producao / self.tempo_disponivel) * 100)
        else:
            self.disponibilidade = 0.0
        
        # Calcula Performance (P)
        if self.tempo_producao > 0 and self.velocidade_planejada > 0:
            producao_teorica = self.velocidade_planejada * self.tempo_producao
            if producao_teorica > 0:
                self.performance = min(100, (self.contagem_saida / producao_teorica) * 100)
            else:
                self.performance = 0.0
        else:
            self.performance = 0.0
        
        # Calcula Qualidade (Q)
        if self.contagem_entrada > 0:
            self.qualidade = min(100, (self.contagem_saida / self.contagem_entrada) * 100)
        else:
            self.qualidade = 0.0
        
        # Calcula OEE
        self.oee = (self.disponibilidade * self.performance * self.qualidade) / 10000
        
        super().save(*args, **kwargs)

# ===== REGISTRO DE PRODUÇÃO POR TURNO (TABELA DE BI) =====

class RegistroProducaoTurno(models.Model):
    """
    Fotografia consolidada de produção por turno - TABELA DE BI
    
    Esta tabela é populada por um script de consolidação que lê dados
    do InfluxDB ao fim de cada turno e grava aqui para análises estratégicas.
    """
    
    # Chaves (Relacionamentos)
    ordem_producao = models.ForeignKey(
        'OrdemProducao',
        on_delete=models.CASCADE,
        related_name='registros_turno',
        verbose_name='Ordem de Produção'
    )
    linha = models.ForeignKey(
        LinhaProducao,
        on_delete=models.CASCADE,
        related_name='registros_turno',
        verbose_name='Linha',
        help_text='Redundante mas útil para performance de queries'
    )
    produto = models.ForeignKey(
        Produto,
        on_delete=models.CASCADE,
        related_name='registros_turno',
        verbose_name='Produto'
    )
    
    # Período
    data = models.DateField(
        db_index=True,
        verbose_name='Data (Dia Contábil)'
    )
    turno = models.ForeignKey(
        TurnoProducao,
        on_delete=models.CASCADE,
        related_name='registros_producao',
        verbose_name='Turno'
    )
    
    # Produção Realizada
    producao_unidades = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Produção (unidades)',
        help_text='Total de unidades produzidas no turno'
    )
    producao_toneladas = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0,
        verbose_name='Produção (toneladas)',
        help_text='Total de toneladas produzidas no turno'
    )
    
    # Refugo
    refugo_unidades = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Refugo (unidades)'
    )
    refugo_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        verbose_name='Refugo (kg)'
    )
    
    # Tempos (em minutos)
    tempo_programado_min = models.FloatField(
        validators=[MinValueValidator(0)],
        verbose_name='Tempo Programado (min)',
        help_text='Tempo total programado para o turno'
    )
    tempo_disponivel_min = models.FloatField(
        validators=[MinValueValidator(0)],
        verbose_name='Tempo Disponível (min)',
        help_text='Tempo programado - tempo não programado'
    )
    tempo_producao_min = models.FloatField(
        validators=[MinValueValidator(0)],
        verbose_name='Tempo Produção (min)',
        help_text='Tempo efetivo em produção (estado RUN)'
    )
    tempo_parado_min = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Tempo Parado (min)',
        help_text='Tempo de paradas não planejadas'
    )
    tempo_setup_min = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Tempo Setup (min)',
        help_text='Tempo de setup/troca de SKU'
    )
    
    # KPIs Consolidados
    disponibilidade = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Disponibilidade (%)',
        help_text='A = (Tempo Produção / Tempo Disponível) × 100'
    )
    performance = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Performance (%)',
        help_text='P = (Produção Real / Produção Planejada) × 100'
    )
    qualidade = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Qualidade (%)',
        help_text='Q = (Produção Boa / Produção Total) × 100'
    )
    oee = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='OEE (%)',
        help_text='OEE = (A × P × Q) / 10000'
    )
    eficiencia = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Eficiência (%)',
        help_text='Razão entre produção real e meta'
    )
    
    # Velocidades
    velocidade_media = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Velocidade Média (unid/min)',
        help_text='Velocidade média durante o turno'
    )
    velocidade_planejada = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Velocidade Planejada (unid/min)'
    )
    
    # Metadados
    consolidado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Consolidado em',
        help_text='Timestamp de quando este registro foi criado'
    )
    observacoes = models.TextField(
        blank=True,
        verbose_name='Observações'
    )
    
    class Meta:
        verbose_name = 'Registro de Produção por Turno'
        verbose_name_plural = 'Registros de Produção por Turno'
        ordering = ['-data', 'turno']
        unique_together = ['ordem_producao', 'data', 'turno']
        indexes = [
            models.Index(fields=['data', 'turno']),
            models.Index(fields=['linha', 'data']),
            models.Index(fields=['ordem_producao']),
            models.Index(fields=['data', 'linha', 'turno']),
        ]
    
    def __str__(self):
        return f'OP {self.ordem_producao.codigo} - {self.data} - Turno {self.turno.codigo}'
    
    def save(self, *args, **kwargs):
        """Calcula KPIs automaticamente antes de salvar"""
        
        # Calcula Disponibilidade (A)
        if self.tempo_disponivel_min > 0:
            self.disponibilidade = min(100, (self.tempo_producao_min / self.tempo_disponivel_min) * 100)
        else:
            self.disponibilidade = 0.0
        
        # Calcula Performance (P)
        if self.tempo_producao_min > 0 and self.velocidade_planejada > 0:
            producao_teorica = self.velocidade_planejada * self.tempo_producao_min
            if producao_teorica > 0:
                self.performance = min(100, (self.producao_unidades / producao_teorica) * 100)
            else:
                self.performance = 0.0
        else:
            self.performance = 0.0
        
        # Calcula Qualidade (Q)
        total_producao = self.producao_unidades + self.refugo_unidades
        if total_producao > 0:
            self.qualidade = min(100, (self.producao_unidades / total_producao) * 100)
        else:
            self.qualidade = 100.0  # Se não há produção, considera qualidade perfeita
        
        # Calcula OEE
        self.oee = (self.disponibilidade * self.performance * self.qualidade) / 10000
        
        # Calcula Eficiência (vs meta do Calendário)
        meta = 0
        try:
            cal = CalendarioProducao.objects.filter(
                linha=self.linha, 
                turno=self.turno, 
                data=self.data
            ).first()
            if cal:
                meta = cal.meta_producao_turno
        except Exception:
            pass
            
        if meta > 0:
            self.eficiencia = min(100, (self.producao_unidades / meta) * 100)
        else:
            self.eficiencia = 0.0

        # Calcula Velocidade Média
        if self.tempo_producao_min > 0:
            self.velocidade_media = self.producao_unidades / self.tempo_producao_min
        else:
            self.velocidade_media = 0.0
        
        super().save(*args, **kwargs)
    
    @classmethod
    def criar_de_influxdb(cls, ordem_producao, data, turno, dados_influx):
        """
        Método auxiliar para criar registro a partir de dados do InfluxDB
        
        Args:
            ordem_producao: instância de OrdemProducao
            data: date do turno
            turno: instância de TurnoProducao
            dados_influx: dict com dados agregados do InfluxDB
        
        Returns:
            instância de RegistroProducaoTurno criada
        """
        registro = cls(
            ordem_producao=ordem_producao,
            linha=ordem_producao.linha,
            produto=ordem_producao.produto,
            data=data,
            turno=turno,
            producao_unidades=dados_influx.get('producao_unidades', 0),
            producao_toneladas=dados_influx.get('producao_toneladas', 0),
            refugo_unidades=dados_influx.get('refugo_unidades', 0),
            refugo_kg=dados_influx.get('refugo_kg', 0),
            tempo_programado_min=dados_influx.get('tempo_programado_min', turno.duracao_horas * 60),
            tempo_disponivel_min=dados_influx.get('tempo_disponivel_min', 0),
            tempo_producao_min=dados_influx.get('tempo_producao_min', 0),
            tempo_parado_min=dados_influx.get('tempo_parado_min', 0),
            tempo_setup_min=dados_influx.get('tempo_setup_min', 0),
            velocidade_planejada=ordem_producao.linha.velocidade_planejada,
        )
        registro.save()
        return registro


# ===== DEFEITOS =====

class Defeito(models.Model):
    """Registro de defeitos"""
    linha = models.ForeignKey(
        LinhaProducao,
        on_delete=models.CASCADE,
        related_name='defeitos',
        null=True,
        blank=True,
        verbose_name='Linha'
    )
    equipamento = models.ForeignKey(
        Equipamento,
        on_delete=models.CASCADE,
        related_name='defeitos',
        null=True,
        blank=True,
        verbose_name='Equipamento'
    )
    data_hora = models.DateTimeField(default=timezone.now, verbose_name='Data/Hora')
    tipo_defeito = models.CharField(max_length=100, verbose_name='Tipo de Defeito')
    descricao = models.TextField(verbose_name='Descrição')
    quantidade = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    severidade = models.CharField(
        max_length=20,
        choices=[('BAIXA', 'Baixa'), ('MEDIA', 'Média'), ('ALTA', 'Alta'), ('CRITICA', 'Crítica')],
        default='MEDIA',
        verbose_name='Severidade'
    )
    resolvido = models.BooleanField(default=False, verbose_name='Resolvido')
    
    class Meta:
        verbose_name = 'Defeito'
        verbose_name_plural = 'Defeitos'
        ordering = ['-data_hora']
    
    def __str__(self):
        if self.equipamento:
            return f'{self.equipamento.nome} - {self.tipo_defeito}'
        return f'Linha {self.linha.codigo} - {self.tipo_defeito}'

# ===== NOVO: EVENTOS DE PARADA (ESTRATÉGICO) =====

class EventoParada(models.Model):
    # As 9 Categorias que vêm do CLP
    CATEGORIAS_CLP = [
        ('RUN', 'Produzindo'),
        ('STOP_MANUAL', 'Parada Manual'),
        ('FAIL_MEC', 'Falha Mecânica'),
        ('FAIL_ELE', 'Falha Elétrica'),
        ('STARVED', 'Falta de Entrada (Starved)'),
        ('BLOCKED', 'Bloqueio de Saída (Blocked)'),
        ('SETUP', 'Setup/Troca'),
        ('QUALIDADE', 'Problema de Qualidade'),
        ('OUTRO', 'Outro'),
    ]

    maquina = models.CharField(max_length=50) # ou ForeignKey
    op = models.CharField(max_length=50)
    turno = models.CharField(max_length=1)
    sku = models.CharField(max_length=50)

    # Tempos
    inicio = models.DateTimeField()
    fim = models.DateTimeField(null=True, blank=True) # Null enquanto está acontecendo
    duracao_segundos = models.IntegerField(default=0)
    
    # Impacto (Calculado pelo Python ao fechar o evento)
    toneladas_perdidas = models.FloatField(default=0.0)

    # Classificação Automática (Vem do CLP)
    categoria_clp = models.CharField(max_length=20, choices=CATEGORIAS_CLP)

    # Classificação Manual (Onde o operador vai atuar depois)
    detalhe_operador = models.TextField(blank=True, null=True) # Ex: "Sensor sujo"
    justificado = models.BooleanField(default=False) # Para controlar pendências

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'eventos_parada'
        indexes = [
            models.Index(fields=['inicio', 'fim']),
            models.Index(fields=['op']),
        ]
    
    def __str__(self):
        return f'{self.maquina} - {self.categoria_clp} ({self.inicio})'

# ===== INICIATIVAS ESTRATÉGICAS =====

class StrategicInitiative(models.Model):
    """Iniciativas estratégicas para melhoria da fábrica"""
    STATUS_CHOICES = [
        ("NAO_INICIADO", "Não Iniciado"),
        ("EM_ANDAMENTO", "Em Andamento"),
        ("CONCLUIDO", "Concluído"),
        ("CANCELADO", "Cancelado"),
    ]

    titulo = models.CharField(max_length=200, verbose_name="Título da Iniciativa")
    descricao = models.TextField(verbose_name="Descrição")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="NAO_INICIADO", verbose_name="Status")
    responsavel = models.CharField(max_length=100, blank=True, verbose_name="Responsável")
    data_inicio = models.DateField(null=True, blank=True, verbose_name="Data de Início")
    data_fim = models.DateField(null=True, blank=True, verbose_name="Data de Fim")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Iniciativa Estratégica"
        verbose_name_plural = "Iniciativas Estratégicas"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.titulo
