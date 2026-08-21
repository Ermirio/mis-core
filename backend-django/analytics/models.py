from django.db import models


class AnalyticsProfile(models.Model):
    """
    Perfil de visualização salvo para tela Analytics.
    Armazena configuração completa de análises (variáveis, período, tipo de gráfico).
    """
    # Metadata
    nome = models.CharField(
        max_length=100,
        help_text="Nome descritivo do perfil (ex: 'Análise OEE Velocidade')"
    )
    descricao = models.TextField(
        blank=True,
        help_text="Descrição opcional do objetivo da análise"
    )
    linha = models.ForeignKey(
        'equipamentos.LinhaProducao',
        on_delete=models.CASCADE,
        related_name='analytics_profiles',
        help_text="Linha a qual este perfil pertence"
    )
    
    # Configuração (JSON)
    config = models.JSONField(
        help_text="Configuração completa do estado Analytics"
    )
    # Estrutura esperada do config:
    # {
    #   "selectedTags": [{"id": 1, "nome": "Velocidade", "tag_influxdb": "...", ...}],
    #   "hoursBack": "8",
    #   "activeTab": "trend",
    #   "trendCharts": [{"id": 1, "name": "Painel 1", "selectedAliases": [...]}],
    #   "scatterX": "...",
    #   "scatterY": "..."
    # }
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_por = models.CharField(
        max_length=50,
        blank=True,
        help_text="Usuário que criou o perfil (opcional)"
    )
    
    class Meta:
        ordering = ['-atualizado_em']  # Mais recentes primeiro
        unique_together = [('linha', 'nome')]  # Nome único por linha
        verbose_name = "Perfil de Analytics"
        verbose_name_plural = "Perfis de Analytics"
    
    def __str__(self):
        return f"{self.nome} ({self.linha.codigo})"
