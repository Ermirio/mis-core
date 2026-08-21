from django.db import models, transaction
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import logging
import uuid as _uuid_module

from .opc_urls import normalize_opc_tcp_url

logger = logging.getLogger(__name__)


def _next_sequential_code(model, prefix, width=3, scope=None):
    """Retorna o próximo código sequencial para um modelo dado prefixo/largura.

    Usa max(int(suffix)) em vez de ordering lexicográfico para tolerar mistura
    de larguras (ex.: L01..L99 + L100..L1001). `scope` é um dict opcional de
    filtros adicionais (ex.: {'linha': linha}) para sequenciar por escopo.
    Deve ser chamado dentro de um `transaction.atomic()` com `select_for_update`.
    """
    qs = model.objects.select_for_update().filter(codigo__startswith=prefix)
    if scope:
        qs = qs.filter(**scope)
    max_num = 0
    for codigo in qs.values_list('codigo', flat=True):
        suffix = codigo[len(prefix):]
        if suffix.isdigit():
            n = int(suffix)
            if n > max_num:
                max_num = n
    return f'{prefix}{max_num + 1:0{width}d}'


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
    codigo = models.CharField(max_length=20, unique=True, verbose_name='Código', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Área'
        verbose_name_plural = 'Áreas'
        ordering = ['fabrica', 'nome']

    def save(self, *args, **kwargs):
        if not self.codigo:
            with transaction.atomic():
                self.codigo = _next_sequential_code(Area, 'A', width=3)
                logger.info(f"✓ Gerado código {self.codigo} para área '{self.nome}'")
        super().save(*args, **kwargs)

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
        validators=[MinValueValidator(0)],
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
    codigo = models.CharField(max_length=20, unique=True, verbose_name='Código da Linha', blank=True)
    nome = models.CharField(max_length=100, verbose_name='Nome da Linha')
    area = models.ForeignKey(
        Area, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='linhas', 
        verbose_name='Área'
    )
    # NOVO: Conexão Padrão da Linha
    conexao_padrao = models.ForeignKey(
        'ConexaoOPC', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='linhas', 
        verbose_name="Conexão OPC Padrão"
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
    
    # Formato alvo padrao (g) usado pelo dashboard de Giveaway quando nao
    # vier do Influx (ex.: 'formato_gramas') e o SKU corrente nao tiver
    # peso_unitario cadastrado.
    formato_alvo_padrao = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name='Formato alvo padrão (g)',
        help_text='Usado como referência de peso nominal quando ausente do Influx/SKU.'
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
        ordering = ['area', 'nome']

    def save(self, *args, **kwargs):
        if not self.codigo:
            with transaction.atomic():
                self.codigo = _next_sequential_code(LinhaProducao, 'L', width=2)
                logger.info(f"✓ Gerado código {self.codigo} para linha '{self.nome}'")
        super().save(*args, **kwargs)

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
    # NOVOS CAMPOS PARA MONITORAMENTO DE SAÚDE
    tag_monitoramento = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="NodeID da tag de saúde (Ex: ns=2;s=Line1.Heartbeat ou Line1.Error)"
    )
    tipo_monitoramento = models.CharField(
        max_length=20,
        choices=[
            ('HEARTBEAT', 'Pulse (Heartbeat)'),
            ('ERROR_BOOL', 'Bit de Erro (True=Error)'),
        ],
        default='HEARTBEAT',
        verbose_name='Tipo de Monitoramento',
        help_text="Como interpretar a tag de monitoramento"
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

    def clean(self):
        super().clean()
        self.url_servidor = normalize_opc_tcp_url(self.url_servidor)

    def save(self, *args, **kwargs):
        # Importacoes e scripts nem sempre passam pelo ModelForm do admin.
        self.url_servidor = normalize_opc_tcp_url(self.url_servidor)
        super().save(*args, **kwargs)
    
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
    nome = models.CharField(max_length=100, verbose_name='Nome do Equipamento')
    codigo = models.CharField(max_length=50, verbose_name='Código', blank=True)
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
    localizacao = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Localização',
        help_text='Deixe em branco para herdar a localização da linha.'
    )
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
    
    # ===== Identidade global (padrão ISA-95 / MES) =====
    # Resolução do "E001 em qual linha?" — três identificadores:
    #   id:   PK Django, joins internos.
    #   uuid: UUIDv4 IMUTÁVEL, gerado uma vez. Integração externa, MQTT,
    #         IIoT, retenção de identidade entre exports/imports.
    #   slug: legível e estável. Default: "{linha.codigo}.{codigo}"
    #         (ex.: "L01.E001"). Gerado no primeiro save e CONGELADO
    #         depois — rename de linha não quebra integrações.
    #
    # Toda comunicação API/InfluxDB/log/URL profunda usa SLUG.
    # `codigo` continua existindo só para UI curta (chip "E001").
    slug = models.SlugField(
        max_length=80,
        unique=True,
        blank=True,
        db_index=True,
        verbose_name='Slug global (L01.E001)',
        help_text=(
            'Identificador legível e estável usado em APIs, InfluxDB, '
            'logs e URLs profundas. Gerado automaticamente no primeiro '
            'save a partir de {linha}.{codigo} e congelado depois.'
        ),
        allow_unicode=False,
    )
    uuid = models.UUIDField(
        default=_uuid_module.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name='UUID',
        help_text=(
            'Identificador único imutável (UUIDv4) — para integrações '
            'externas (ERP, IIoT, MQTT). Sobrevive a renomeações.'
        ),
    )

    class Meta:
        verbose_name = 'Equipamento'
        verbose_name_plural = 'Equipamentos'
        ordering = ['linha', 'ordem_na_linha']
        constraints = [
            models.UniqueConstraint(
                fields=['linha', 'codigo'],
                name='uniq_equipamento_linha_codigo',
            ),
            models.UniqueConstraint(
                fields=['linha', 'nome'],
                name='uniq_equipamento_linha_nome',
            ),
        ]

    def save(self, *args, **kwargs):
        """Auto-gera codigo sequencial (E###) escopado pela linha, herda
        a localizacao da linha quando vazia, e gera o slug global no
        primeiro save (depois CONGELADO — rename de linha NÃO altera)."""
        if not self.codigo:
            if not self.linha_id:
                raise ValueError(
                    "Equipamento.save: defina 'linha' antes de salvar para gerar o código."
                )
            with transaction.atomic():
                # Sequencia E### por linha usando o helper genérico do PR 1.
                self.codigo = _next_sequential_code(
                    Equipamento, 'E', width=3, scope={'linha_id': self.linha_id}
                )
                logger.info(
                    f"✓ Gerado código {self.codigo} para equipamento '{self.nome}' "
                    f"(Linha: {self.linha.codigo})"
                )

        if not self.localizacao and self.linha_id:
            # Herda a localização da linha quando não informada (PR 2).
            self.localizacao = self.linha.localizacao or ''

        # Slug global é gerado uma única vez e congelado.
        # Por que congelado: integrações externas (Influx historic, MQTT topics,
        # Node-RED flows, snapshots Golden State) referenciam o slug. Renomear
        # uma linha não pode quebrar histórico — quem precisa de "renomear de
        # fato" usa um endpoint dedicado de migração com audit.
        if not self.slug and self.linha_id and self.codigo:
            base_slug = f"{self.linha.codigo}.{self.codigo}"
            # Em teoria a constraint (linha, codigo) já garante unicidade,
            # mas defensivo contra colisão histórica (legacy data, etc.).
            candidate = base_slug
            n = 2
            while Equipamento.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate = f"{base_slug}-{n}"
                n += 1
            self.slug = candidate
            logger.info(
                f"✓ Slug global gerado: '{self.slug}' (equipamento '{self.nome}')"
            )

        super().save(*args, **kwargs)

        try:
            ensure_default_tags_for_equipment(self)
        except Exception as exc:
            logger.warning(
                "Nao foi possivel garantir tags padrao para equipamento %s: %s",
                self.codigo,
                exc,
            )
    
    def __str__(self):
        return f'{self.nome} ({self.tipo})'

# ===== TAGS DE COLETA =====

class TipoDado(models.TextChoices):
    INT = 'INT', 'Inteiro'
    FLOAT = 'FLOAT', 'Decimal'
    STRING = 'STRING', 'Texto'
    BOOL = 'BOOL', 'Booleano'


DEFAULT_TAGS_COLETA = [
    {'nome': 'contagem_entrada', 'label': 'Contagem de entrada', 'tipo_dado': TipoDado.INT, 'unidade': 'un', 'fator_conversao': 1.0},
    {'nome': 'contagem_saida', 'label': 'Contagem de saida', 'tipo_dado': TipoDado.INT, 'unidade': 'un', 'fator_conversao': 1.0},
    {'nome': 'estado_maquina', 'label': 'Estado da maquina', 'tipo_dado': TipoDado.INT, 'unidade': 'estado', 'fator_conversao': 1.0},
    {'nome': 'velocidade_atual', 'label': 'Velocidade atual', 'tipo_dado': TipoDado.FLOAT, 'unidade': 'un/min', 'fator_conversao': 1.0},
    {'nome': 'ordem_producao', 'label': 'Ordem de producao', 'tipo_dado': TipoDado.STRING, 'unidade': '', 'fator_conversao': 1.0},
    {'nome': 'sku_codigo', 'label': 'Codigo SKU', 'tipo_dado': TipoDado.STRING, 'unidade': '', 'fator_conversao': 1.0},
    {'nome': 'descricao', 'label': 'Descricao do produto', 'tipo_dado': TipoDado.STRING, 'unidade': '', 'fator_conversao': 1.0},
    {'nome': 'formato', 'label': 'Formato', 'tipo_dado': TipoDado.FLOAT, 'unidade': 'g', 'fator_conversao': 1.0},
    {'nome': 'planejado_op', 'label': 'Planejado OP', 'tipo_dado': TipoDado.INT, 'unidade': 'un', 'fator_conversao': 1.0},
    {'nome': 'cuc', 'label': 'CUC', 'tipo_dado': TipoDado.FLOAT, 'unidade': '', 'fator_conversao': 1.0},
    # 'descarte' foi removido das tags padrao (PR 5) - o valor e calculado
    # por delta entre 'contagem_entrada' e 'contagem_saida' em
    # MetricaProducao.save(). Se o CLP expuser um contador direto,
    # cadastre como tag customizada manualmente.
    {'nome': 'peso_real', 'label': 'Peso real medido', 'tipo_dado': TipoDado.FLOAT, 'unidade': 'g', 'fator_conversao': 1.0},
]

TAG_COLETA_CHOICES = [(item['nome'], item['label']) for item in DEFAULT_TAGS_COLETA]
DEFAULT_TAGS_BY_NAME = {item['nome']: item for item in DEFAULT_TAGS_COLETA}


class TagColeta(models.Model):
    """Tag OPC para coleta de dados de um equipamento"""
    equipamento = models.ForeignKey(
        Equipamento,
        on_delete=models.CASCADE,
        related_name='tags_coleta',
        verbose_name='Equipamento'
    )

    nome_metrica = models.CharField(
        max_length=100,
        verbose_name='Nome da Métrica',
        help_text='Variavel OPC. As variaveis padrao ja sao criadas automaticamente para preencher apenas o Node ID.'
    )
    node_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Node ID',
        help_text='Informe apenas o Node ID OPC. Ex: ns=2;s=Linha1.Enchedora.Velocidade'
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
    golden_state = models.BooleanField(
        default=False,
        verbose_name='Golden State',
        help_text=(
            'Marque quando esta variável define a "condição ótima" de operação '
            '(setpoints, parâmetros de receita). Variáveis de leitura pura como '
            'temperaturas ambiente NÃO devem ser marcadas.'
        ),
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tag de Coleta'
        verbose_name_plural = 'Tags de Coleta'
        ordering = ['equipamento', 'nome_metrica']
        unique_together = ['equipamento', 'nome_metrica']
    
    def __str__(self):
        return f'{self.equipamento.nome} - {self.nome_metrica}'

    def apply_default_metadata(self):
        defaults = DEFAULT_TAGS_BY_NAME.get(self.nome_metrica)
        if not defaults:
            return

        self.tipo_dado = defaults['tipo_dado']
        self.unidade = defaults['unidade']
        self.fator_conversao = defaults['fator_conversao']
        if not self.node_id:
            self.ativa = False

    def save(self, *args, **kwargs):
        self.apply_default_metadata()
        super().save(*args, **kwargs)


def ensure_default_tags_for_equipment(equipamento):
    for defaults in DEFAULT_TAGS_COLETA:
        TagColeta.objects.get_or_create(
            equipamento=equipamento,
            nome_metrica=defaults['nome'],
            defaults={
                'node_id': '',
                'tipo_dado': defaults['tipo_dado'],
                'unidade': defaults['unidade'],
                'fator_conversao': defaults['fator_conversao'],
                'ativa': False,
            },
        )

# ===== SENSORES =====

class TipoSensor(models.TextChoices):
    INPUT_BOOL = 'INPUT_BOOL', 'Input Digital (Booleano)'
    INPUT_FLOAT = 'INPUT_FLOAT', 'Input Analógico (Decimal)'
    INPUT_INT = 'INPUT_INT', 'Input Inteiro'
    TIMER = 'TIMER', 'Temporizador (Tempo)'
    COUNTER = 'COUNTER', 'Contador'
    SETPOINT = 'SETPOINT', 'Setpoint / Ajuste'
    LIMIT = 'LIMIT', 'Limite / Parâmetro'
    HEARTBEAT = 'HEARTBEAT', 'Health Check'
    COMM_ERROR = 'COMM_ERROR', 'Erro de Comunicação'
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
    codigo = models.CharField(max_length=50, verbose_name='Código do Sensor', blank=True)
    nome = models.CharField(max_length=100, verbose_name='Nome do Sensor')
    tipo = models.CharField(max_length=20, choices=TipoSensor.choices, verbose_name='Tipo')
    tag_influxdb = models.CharField(
        max_length=100,
        verbose_name='Tag InfluxDB',
        help_text='Nome do campo no InfluxDB (ex: contagem_entrada, temperatura)'
    )
    unidade = models.CharField(max_length=20, blank=True, verbose_name='Unidade de Medida')
    ativo = models.BooleanField(default=True, verbose_name='Sensor Ativo')
    golden_state = models.BooleanField(
        default=False,
        verbose_name='Golden State',
        help_text=(
            'Marque quando este sensor define a "condição ótima" de operação '
            '(setpoint de receita, parâmetro controlado). Leituras puras de '
            'ambiente NÃO devem ser marcadas.'
        ),
    )
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
        constraints = [
            models.UniqueConstraint(
                fields=['equipamento', 'codigo'],
                condition=models.Q(equipamento__isnull=False),
                name='uniq_sensor_equipamento_codigo',
            ),
            models.UniqueConstraint(
                fields=['linha', 'codigo'],
                condition=models.Q(equipamento__isnull=True, linha__isnull=False),
                name='uniq_sensor_linha_codigo',
            ),
        ]

    def save(self, *args, **kwargs):
        """Auto-gera código sequencial (S###) escopado pelo equipamento ou linha."""
        if not self.codigo:
            if not (self.equipamento_id or self.linha_id):
                raise ValueError(
                    "Sensor.save: defina 'equipamento' ou 'linha' antes de salvar para gerar o código."
                )
            with transaction.atomic():
                qs = Sensor.objects.select_for_update().filter(codigo__startswith='S')
                if self.equipamento_id:
                    qs = qs.filter(equipamento_id=self.equipamento_id)
                else:
                    qs = qs.filter(equipamento__isnull=True, linha_id=self.linha_id)
                max_num = 0
                for codigo in qs.values_list('codigo', flat=True):
                    suffix = codigo[1:]
                    if suffix.isdigit():
                        n = int(suffix)
                        if n > max_num:
                            max_num = n
                self.codigo = f'S{max_num + 1:03d}'
                logger.info(
                    f"✓ Gerado código {self.codigo} para sensor '{self.nome}' "
                    f"(escopo: equipamento={self.equipamento_id}, linha={self.linha_id})"
                )

        super().save(*args, **kwargs)

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
        ('SETPOINT', 'Set Point'),
        ('LIMIT', 'Limite de Processo'),
        ('HEARTBEAT', 'Health Check'),
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
        """
        Calcula KPIs automaticamente antes de salvar — ISO 22400-2.

        Correções aplicadas (diagnóstico técnico):
          1. Qualidade: retorna 0.0 quando contagem_entrada == 0 (equipamento parado).
             Antes retornava 0.0 mas o comentário indicava confusão — agora explícito.
          2. OEE: fórmula correta (A/100)*(P/100)*(Q/100)*100 = A*P*Q/10000.
             Verificamos que os componentes já estão em 0..100 antes de aplicar.
          3. Descarte: max(0, ...) para não ficar negativo por erro de counter.
        """
        # --- Descarte ---
        if self.contagem_entrada > 0:
            raw_descarte = self.contagem_entrada - self.contagem_saida
            self.descarte = max(0, raw_descarte)
            self.percentual_descarte = (self.descarte / self.contagem_entrada) * 100
        else:
            self.descarte = 0
            self.percentual_descarte = 0.0

        # --- Tempo disponível ---
        self.tempo_disponivel = max(0.0, self.tempo_programado - self.tempo_nao_programado)

        # --- Disponibilidade (A) ---
        if self.tempo_disponivel > 0:
            self.disponibilidade = min(100.0, (self.tempo_producao / self.tempo_disponivel) * 100)
        else:
            self.disponibilidade = 0.0

        # --- Performance (P) ---
        # Producao teórica = velocidade planejada (unid/min) × tempo de produção (min)
        if self.tempo_producao > 0 and self.velocidade_planejada > 0:
            producao_teorica = self.velocidade_planejada * self.tempo_producao
            if producao_teorica > 0:
                self.performance = min(100.0, (self.contagem_saida / producao_teorica) * 100)
            else:
                self.performance = 0.0
        else:
            self.performance = 0.0

        # --- Qualidade (Q) ---
        # CRÍTICO: quando equipamento está parado (contagem_entrada == 0),
        # Qualidade é INDEFINIDA — não deve ser 100% nem poluir o OEE.
        # Usamos 0.0 para que o OEE reflita a inatividade.
        if self.contagem_entrada > 0:
            self.qualidade = min(100.0, (self.contagem_saida / self.contagem_entrada) * 100)
        else:
            self.qualidade = 0.0

        # --- OEE (ISO 22400-2): A × P × Q (cada componente em 0..1) ---
        # Componentes já estão em 0..100, logo: OEE = A*P*Q / 10000
        self.oee = min(100.0, (self.disponibilidade * self.performance * self.qualidade) / 10000.0)

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
        """Calcula KPIs automaticamente antes de salvar — ISO 22400-2.

        Qualidade indefinida (total_producao == 0) → 0.0, não 100%.
        Evita OEE inflado quando não há produção no turno.
        """
        # Disponibilidade (A)
        if self.tempo_disponivel_min > 0:
            self.disponibilidade = min(100.0, (self.tempo_producao_min / self.tempo_disponivel_min) * 100)
        else:
            self.disponibilidade = 0.0

        # Performance (P)
        if self.tempo_producao_min > 0 and self.velocidade_planejada > 0:
            producao_teorica = self.velocidade_planejada * self.tempo_producao_min
            if producao_teorica > 0:
                self.performance = min(100.0, (self.producao_unidades / producao_teorica) * 100)
            else:
                self.performance = 0.0
        else:
            self.performance = 0.0

        # Qualidade (Q) — INDEFINIDA quando total == 0 → 0.0 (não inventa 100%)
        total_producao = self.producao_unidades + self.refugo_unidades
        if total_producao > 0:
            self.qualidade = min(100.0, (self.producao_unidades / total_producao) * 100)
        else:
            self.qualidade = 0.0

        # OEE = A × P × Q / 10000 (componentes em 0..100)
        self.oee = min(100.0, (self.disponibilidade * self.performance * self.qualidade) / 10000.0)
        
        # Calcula Eficiência (vs meta do Calendário, ou fallback meta padrão da linha)
        from .utils import get_meta_turno
        meta = get_meta_turno(self.linha, self.data, self.turno)

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
        return f"{self.titulo} ({self.get_status_display()})"


# ===== GOLDEN STATE =====
# Cataloga corridas de referência (a "receita de ouro" da linha).
# A aba Estado de Ouro consulta esses runs primeiro; só faz cálculo
# dinâmico do histórico bruto se não houver run salvo.

class GoldenStateRun(models.Model):
    """Uma 'corrida boa' catalogada — base de referência para comparar o
    momento atual contra um padrão conhecido.

    Pode ser criada de duas formas:
      - AUTO: signal pós-fechamento de turno detectou score alto e gravou.
      - MANUAL: coordenador clicou em 'Capturar momento como referência' na
        aba Estado de Ouro, escolhendo a janela.
    """
    class Fonte(models.TextChoices):
        AUTO = 'AUTO', 'Automático (turno bom detectado)'
        MANUAL = 'MANUAL', 'Capturado manualmente'

    linha = models.ForeignKey(
        LinhaProducao,
        on_delete=models.CASCADE,
        related_name='golden_state_runs',
        verbose_name='Linha',
    )
    nome = models.CharField(
        max_length=120,
        blank=True,
        verbose_name='Nome curto',
        help_text='Ex: "Turno A do dia 17/05" — usado em listas.',
    )
    sku_codigo = models.CharField(
        max_length=60, blank=True, null=True,
        verbose_name='SKU rodando',
        help_text='SKU rodando na janela. Vazio = qualquer SKU.',
    )
    formato_gramas = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Formato (g)',
        help_text='Peso unitário do produto na janela. Permite filtrar receita por formato (ex: SKUs diferentes mas mesmo formato compartilham receita).',
    )
    fonte = models.CharField(
        max_length=10, choices=Fonte.choices, default=Fonte.MANUAL,
        verbose_name='Fonte',
    )
    inicio = models.DateTimeField(verbose_name='Início da janela')
    fim = models.DateTimeField(verbose_name='Fim da janela')
    score = models.FloatField(
        null=True, blank=True,
        verbose_name='Score (0-100)',
        help_text='Score combinado de produção/qualidade/estabilidade.',
    )
    tph_medio = models.FloatField(null=True, blank=True, verbose_name='TPH médio')
    refugo_pct = models.FloatField(null=True, blank=True, verbose_name='% Refugo')
    oee_medio = models.FloatField(null=True, blank=True, verbose_name='OEE médio')
    observacoes = models.TextField(
        blank=True,
        verbose_name='Observações',
        help_text='Anotação livre do coordenador: "depois do ajuste de pressão", etc.',
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name='Ativo',
        help_text='Desmarque para excluir esta corrida do cálculo da receita.',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.CharField(
        max_length=120, blank=True,
        verbose_name='Criado por',
        help_text='Placeholder; preenchido com username quando houver auth.',
    )

    class Meta:
        verbose_name = 'Corrida de referência (Golden State)'
        verbose_name_plural = 'Corridas de referência (Golden State)'
        ordering = ['-criado_em']
        constraints = [
            # Deduplica AUTO: só 1 por linha+sku+dia para não inundar o banco.
            models.UniqueConstraint(
                fields=['linha', 'sku_codigo', 'inicio'],
                condition=models.Q(fonte='AUTO'),
                name='uniq_golden_auto_linha_sku_inicio',
            ),
        ]

    def __str__(self):
        return f"{self.linha.codigo} · {self.nome or self.inicio.date().isoformat()} ({self.get_fonte_display()})"


class NodeRedSnapshot(models.Model):
    """Versão histórica do fluxograma Node-RED.

    Capturado automaticamente toda vez que um usuário faz "Deploy" no
    editor — o nginx espelha o POST /flows para o Django, que grava aqui.

    Suporta:
      - Auditoria: quem mudou o quê e quando.
      - Rollback: restaurar versão clica botão no admin → POST /flows
        de volta no Node-RED com o conteúdo arquivado.
      - Encadeamento: cada snapshot referencia o anterior (`parent`),
        formando uma cadeia linear estilo Git, **por projeto**.
      - Multi-projeto: com a feature Projects do Node-RED ligada, cada
        projeto tem seu próprio `flow.json`. O campo `projeto` guarda
        qual projeto sofreu o deploy; snapshots sem projeto (legacy ou
        Projects desligado) ficam com string vazia e formam uma linha
        do tempo "global".
    """
    SEM_PROJETO = ''  # snapshot anterior ao Projects ou com feature desligada

    class Acao(models.TextChoices):
        DEPLOY = 'DEPLOY', 'Deploy (alteração do editor)'
        RESTORE = 'RESTORE', 'Restauração de versão anterior'
        INITIAL = 'INITIAL', 'Snapshot inicial'

    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    projeto = models.CharField(
        max_length=128, blank=True, default='', db_index=True,
        verbose_name='Projeto',
        help_text=(
            'Nome do projeto Node-RED (quando a feature Projects está '
            'habilitada). Em branco = snapshot global / Projects desligado.'
        ),
    )
    usuario = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='nodered_snapshots',
        verbose_name='Usuário responsável',
    )
    usuario_nome = models.CharField(
        max_length=150, blank=True,
        verbose_name='Username (cache)',
        help_text='Preservado mesmo se o usuário for deletado.',
    )
    acao = models.CharField(
        max_length=10, choices=Acao.choices, default=Acao.DEPLOY,
        verbose_name='Ação',
    )
    descricao = models.CharField(
        max_length=200, blank=True,
        verbose_name='Descrição',
        help_text='Mensagem opcional (ex.: "Adicionado fluxo de alarmes E001").',
    )
    flows_json = models.JSONField(
        verbose_name='Fluxograma completo (JSON)',
        help_text='Snapshot integral do flows.json no momento do deploy.',
    )
    hash_sha = models.CharField(
        max_length=64, db_index=True,
        verbose_name='SHA-256',
        help_text='Hash do flows_json — usado para detectar duplicatas.',
    )
    num_nodes = models.IntegerField(default=0, verbose_name='Nº de nós')
    size_bytes = models.IntegerField(default=0, verbose_name='Tamanho (bytes)')
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='filhos',
        verbose_name='Versão anterior',
        help_text='Cadeia linear por projeto: snapshot anterior do MESMO projeto.',
    )
    # Diff cache — calculado uma vez no save para acelerar a UI.
    nodes_adicionados = models.IntegerField(default=0)
    nodes_removidos = models.IntegerField(default=0)
    nodes_modificados = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Snapshot Node-RED'
        verbose_name_plural = 'Histórico Node-RED'
        ordering = ['-criado_em']
        indexes = [
            # Acelera a query "último snapshot do projeto X" — feita em
            # cada deploy para dedup + montagem de parent.
            models.Index(fields=['projeto', '-criado_em'], name='nrs_proj_ts_idx'),
        ]

    def __str__(self):
        proj = f'[{self.projeto}] ' if self.projeto else ''
        return f'#{self.pk} · {proj}{self.usuario_nome or "—"} · {self.criado_em:%d/%m %H:%M}'


class ExternalTools(models.Model):
    """Model "virtual" só para registrar permissões de acesso às
    ferramentas externas. Não cria tabela — o coordenador atribui essas
    permissões a usuários ou grupos pelo admin Django.

    O nginx consulta /api/auth/check-node-red/ que valida estas perms
    contra request.user.
    """
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ('access_nodered', 'Pode acessar Node-RED'),
            ('access_grafana', 'Pode acessar Grafana'),
            ('access_chronograf', 'Pode acessar Chronograf'),
            ('access_emqx', 'Pode acessar EMQX Dashboard'),
        ]
        verbose_name = 'Ferramenta externa (permissão)'
        verbose_name_plural = 'Ferramentas externas (permissões)'


class GoldenStateVarSnapshot(models.Model):
    """Percentis de uma variável golden em uma janela de referência.
    Snapshot calculado uma vez na criação do run — não recalcula depois.
    """
    run = models.ForeignKey(
        GoldenStateRun, on_delete=models.CASCADE, related_name='variaveis',
    )
    # FK opcional. Quando o sensor é apagado, mantemos o snapshot com
    # o nome textual ('tag_influx' + 'nome_amigavel') para histórico.
    sensor = models.ForeignKey(
        'Sensor', on_delete=models.SET_NULL, null=True, blank=True,
    )
    tag = models.ForeignKey(
        'TagColeta', on_delete=models.SET_NULL, null=True, blank=True,
    )
    nome_amigavel = models.CharField(max_length=120)
    tag_influx = models.CharField(max_length=120)
    unidade = models.CharField(max_length=20, blank=True)
    equipamento_codigo = models.CharField(max_length=20, blank=True)
    p10 = models.FloatField()
    p50 = models.FloatField()
    p90 = models.FloatField()
    n_amostras = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Snapshot de variável (Golden State)'
        verbose_name_plural = 'Snapshots de variáveis (Golden State)'
        ordering = ['nome_amigavel']

    def __str__(self):
        return f"{self.run} · {self.nome_amigavel}"


class NodeRedUser(models.Model):
    """Usuário Node-RED gerenciado a partir do admin Django.

    O `settings.js` do Node-RED tem `adminAuth` configurado com `authenticate`
    e `users` que fazem HTTP contra o Django (`/api/auth/nodered/{authenticate,
    user}/`). Esta tabela é a fonte de verdade: criar/editar/desativar usuários
    do Node-RED é feito 100% pelo admin Django, sem editar `settings.js` nem
    rodar `node-red-admin hash-pw`.

    A senha é armazenada com `django.contrib.auth.hashers.make_password`
    (PBKDF2-SHA256 por default — bcrypt opcional se a app instalar bcrypt).
    O endpoint de autenticação usa `check_password` para validar.

    `permissoes` aceita os valores documentados pelo Node-RED:
      - `"*"`         → admin total (criar/editar/deploy)
      - `"read"`      → somente leitura (não pode salvar/deploy)
      - `"flows.read,flows.write,nodes.read"` → granular (separado por vírgula)
    """

    NIVEL_ADMIN = '*'
    NIVEL_LEITURA = 'read'
    NIVEL_CUSTOM = 'custom'
    NIVEL_CHOICES = [
        (NIVEL_ADMIN, 'Administrador (total)'),
        (NIVEL_LEITURA, 'Somente leitura'),
        (NIVEL_CUSTOM, 'Customizado (use o campo permissoes)'),
    ]

    username = models.CharField(
        max_length=150,
        unique=True,
        verbose_name='Usuário',
        help_text='Login que o operador digita na tela do Node-RED.',
    )
    password_hash = models.CharField(
        max_length=256,
        verbose_name='Senha (hash)',
        help_text='Hash gerado automaticamente quando você grava uma nova senha.',
    )
    nivel = models.CharField(
        max_length=10,
        choices=NIVEL_CHOICES,
        default=NIVEL_LEITURA,
        verbose_name='Nível de acesso',
    )
    permissoes = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Permissões granulares',
        help_text=(
            'Apenas usado quando `nivel = Customizado`. Lista separada por '
            'vírgula. Ex.: "flows.read,flows.write,nodes.read,settings.read". '
            'Se vazio com nivel != Customizado, o nível define tudo.'
        ),
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name='Ativo',
        help_text='Desmarque para bloquear o login sem perder o usuário.',
    )
    observacoes = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Observações',
        help_text='Quem é, qual fábrica/linha responde, contato — livre.',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    ultimo_login_em = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Último login bem-sucedido',
    )

    class Meta:
        verbose_name = 'Usuário Node-RED'
        verbose_name_plural = 'Usuários Node-RED'
        ordering = ['username']

    def __str__(self):
        marca = '' if self.ativo else ' (inativo)'
        return f'{self.username} [{self.get_nivel_display()}]{marca}'

    def set_password(self, raw_password):
        """Hasheia e armazena uma nova senha. NÃO chama save()."""
        from django.contrib.auth.hashers import make_password
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password_hash)

    def get_permissions(self):
        """Retorna o valor que vai para `permissions` do Node-RED."""
        if self.nivel == self.NIVEL_CUSTOM and self.permissoes.strip():
            # Node-RED aceita tanto string com vírgulas quanto array.
            # Devolvemos array para evitar ambiguidade.
            return [p.strip() for p in self.permissoes.split(',') if p.strip()]
        return self.nivel  # "*" ou "read"



