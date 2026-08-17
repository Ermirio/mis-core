from django.db import models
from django.contrib.auth.models import User
from ips.models import Linha
import logging

logger = logging.getLogger(__name__)

# ===========================================================================
# MÓDULO ANDRETTI — Speed-Up Program
# ===========================================================================

class WaveAndretti(models.Model):
    """Define uma onda/campanha de speed-up (ex: Wave 1 — Q1 2026)"""
    nome = models.CharField(max_length=100, help_text="Ex: Wave 1 — Q1 2026")
    data_inicio = models.DateField()
    data_fim = models.DateField()
    descricao = models.TextField(blank=True)
    ativa = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Wave Andretti"
        verbose_name_plural = "Waves Andretti"
        ordering = ['-data_inicio']

    def __str__(self):
        return self.nome


class MetaVelocidadeLinha(models.Model):
    """Meta de velocidade por linha, wave e formato (em gramas)."""
    UNIDADE_CHOICES = [
        ('ppm', 'Pacotes por minuto'),
        ('cpm', 'Caixas por minuto'),
        ('kgh', 'kg/hora'),
    ]
    linha = models.ForeignKey(Linha, on_delete=models.CASCADE, related_name='metas_andretti')
    wave = models.ForeignKey(WaveAndretti, on_delete=models.CASCADE, related_name='metas')
    formato = models.ForeignKey(
        'ips.Formato',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='metas_andretti',
        help_text="Formato ao qual esta meta se aplica (identificado pelos gramas). Deixe em branco para meta geral.",
    )
    velocidade_padrao = models.DecimalField(max_digits=10, decimal_places=2,
        help_text="Velocidade baseline atual da linha para este formato")
    velocidade_meta = models.DecimalField(max_digits=10, decimal_places=2,
        help_text="Velocidade alvo Andretti para esta wave/formato")
    unidade = models.CharField(max_length=10, choices=UNIDADE_CHOICES, default='ppm')

    class Meta:
        unique_together = ('linha', 'wave', 'formato')
        verbose_name = "Meta de Velocidade"
        verbose_name_plural = "Metas de Velocidade"

    def __str__(self):
        if self.formato:
            fmt = f"{self.formato.gramas}g" if self.formato.gramas else self.formato.nome
        else:
            fmt = "Geral"
        return f"{self.linha.nome} [{fmt}] — {self.wave.nome}: {self.velocidade_padrao}→{self.velocidade_meta} {self.unidade}"

    @property
    def ganho_percentual(self):
        if self.velocidade_padrao and float(self.velocidade_padrao) > 0:
            return round(
                (float(self.velocidade_meta) - float(self.velocidade_padrao))
                / float(self.velocidade_padrao) * 100, 2
            )
        return 0.0


class LeituraVelocidade(models.Model):
    """
    Histórico de leituras de velocidade por linha e formato.

    Regra de dedup (aplicada no OPC worker e na view de leitura manual):
    Só insere novo registro se a velocidade for diferente da última leitura
    para a mesma (linha, formato_gramas).
    """
    FONTE_CHOICES = [
        ('OPC',    'OPC UA (automático)'),
        ('MANUAL', 'Inserção manual'),
    ]
    linha = models.ForeignKey(Linha, on_delete=models.CASCADE, related_name='leituras_velocidade')
    meta = models.ForeignKey(
        'MetaVelocidadeLinha',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leituras',
        help_text="Meta à qual esta leitura manual está vinculada (linha + formato + wave).",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    velocidade = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Obrigatório para fonte Manual. OPC preenche automaticamente.",
    )
    fonte = models.CharField(max_length=10, choices=FONTE_CHOICES, default='OPC')
    formato_gramas = models.IntegerField(
        null=True, blank=True,
        help_text="Formato em gramas (lido via OPC). Usado apenas para o gráfico de tendência.",
    )

    class Meta:
        verbose_name = "Leitura de Velocidade"
        verbose_name_plural = "Leituras de Velocidade"
        indexes = [
            models.Index(fields=['linha', 'timestamp']),
            models.Index(fields=['linha', 'formato_gramas', 'timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        fmt = f"{self.formato_gramas}g" if self.formato_gramas else "—"
        return f"{self.linha.nome} [{fmt}] — {self.velocidade} ({self.fonte}) @ {self.timestamp:%Y-%m-%d %H:%M}"


class CategoriaAcao(models.Model):
    """Sub-temas por área — cadastro no admin Django"""
    AREA_CHOICES = [
        ('manutencao',    'Manutenção'),
        ('qualidade',     'Qualidade'),
        ('eng_projetos',  'Engenharia Projetos'),
        ('eng_processos', 'Engenharia Processos'),
    ]
    nome = models.CharField(max_length=100)
    area = models.CharField(max_length=20, choices=AREA_CHOICES)

    class Meta:
        unique_together = ('nome', 'area')
        verbose_name = "Categoria de Ação"
        verbose_name_plural = "Categorias de Ações"
        ordering = ['area', 'nome']

    def __str__(self):
        return f"{self.get_area_display()} / {self.nome}"


class AcaoAndretti(models.Model):
    """Plano de ação multi-área para atingir a meta de velocidade"""
    STATUS_CHOICES = [
        ('aberta',       'Aberta'),
        ('em_andamento', 'Em Andamento'),
        ('concluida',    'Concluída'),
        ('cancelada',    'Cancelada'),
    ]
    AREA_CHOICES = CategoriaAcao.AREA_CHOICES

    linha = models.ForeignKey(Linha, on_delete=models.CASCADE, related_name='acoes_andretti')
    wave = models.ForeignKey(WaveAndretti, on_delete=models.CASCADE, related_name='acoes')
    area = models.CharField(max_length=20, choices=AREA_CHOICES)
    categoria = models.ForeignKey(CategoriaAcao, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='acoes')
    descricao = models.TextField()
    responsavel = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aberta')
    data_insercao = models.DateTimeField(auto_now_add=True)
    prazo_execucao = models.DateField()
    data_realizada = models.DateField(null=True, blank=True)
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='acoes_andretti')

    class Meta:
        verbose_name = "Ação Andretti"
        verbose_name_plural = "Ações Andretti"
        ordering = ['status', 'prazo_execucao']
        indexes = [
            models.Index(fields=['wave', 'area', 'status']),
            models.Index(fields=['linha', 'wave']),
        ]

    def __str__(self):
        return f"[{self.get_area_display()}] {self.descricao[:60]} — {self.get_status_display()}"

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if self.status == 'concluida' and not self.data_realizada:
            self.data_realizada = timezone.now().date()
        super().save(*args, **kwargs)
