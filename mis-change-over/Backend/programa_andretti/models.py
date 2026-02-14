from django.db import models
from ips.models import Linha
from django.core.validators import MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

# Configura logging para depuração
logger = logging.getLogger(__name__)

class Formato(models.Model):
    gramas = models.PositiveIntegerField(
        unique=True,
        help_text="Peso em gramas do formato (ex.: 400, 800, 1600, 2400)",
        validators=[MinValueValidator(1)]
    )
    velocidade_std = models.FloatField(
        help_text="Velocidade padrão (Std) para este formato (pacotes por minuto)",
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]  # Velocidade não pode ser negativa
    )
    capacidade_hora = models.FloatField(
        help_text="Capacidade em toneladas por hora com base na velocidade padrão",
        null=True,
        blank=True
    )
    capacidade_mes = models.FloatField(
        help_text="Capacidade em toneladas por mês com base na velocidade padrão",
        null=True,
        blank=True
    )

    def save(self, *args, **kwargs):
        def calcular_ton_hora(velocidade, gramas):
            if velocidade and gramas:
                kg_por_minuto = (velocidade * gramas) / 1000
                ton_por_hora = (kg_por_minuto * 60) / 1000
                return round(ton_por_hora, 3)
            return 0.0

        def calcular_ton_mes(velocidade, gramas):
            ton_hora = calcular_ton_hora(velocidade, gramas)
            return round(ton_hora * 720, 3) if ton_hora else 0.0

        self.capacidade_hora = calcular_ton_hora(self.velocidade_std, self.gramas)
        self.capacidade_mes = calcular_ton_mes(self.velocidade_std, self.gramas)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.gramas}g"

class StartBortoletto(models.Model):
    linha = models.ForeignKey(Linha, on_delete=models.CASCADE, related_name='start_bortoletto')
    formato = models.ForeignKey(Formato, on_delete=models.CASCADE, related_name='start_bortoletto')
    data_inicio = models.DateField(
        help_text="Data de início do programa Bortoletto/Andretti",
        default=None,
        null=True,
        blank=True
    )
    velocidade_std = models.FloatField(
        help_text="Velocidade padrão (Std) do formato (copiada do Formato)",
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]  # Velocidade não pode ser negativa
    )
    velocidade_planejada = models.FloatField(
        help_text="Velocidade planejada (meta) do programa (pacotes por minuto)",
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]  # Velocidade não pode ser negativa
    )
    percentual_ganho_planejado = models.FloatField(
        help_text="Percentual de ganho da velocidade planejada em relação à velocidade padrão (%)",
        null=True,
        blank=True
    )

    def save(self, *args, **kwargs):
        if self.formato and self.formato.velocidade_std:
            self.velocidade_std = self.formato.velocidade_std
        if self.velocidade_std and self.velocidade_planejada:
            self.percentual_ganho_planejado = ((self.velocidade_planejada - self.velocidade_std) /
                                             self.velocidade_std) * 100
            self.percentual_ganho_planejado = round(self.percentual_ganho_planejado, 2)
        elif self.velocidade_planejada is None:
            self.percentual_ganho_planejado = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.linha.nome} - {self.formato.gramas}g - {self.velocidade_planejada}"

class EstatisticasDiarias(models.Model):
    start_bortoletto = models.ForeignKey(StartBortoletto, on_delete=models.CASCADE, related_name='estatisticas_diarias')
    data = models.DateField(
        help_text="Data do registro",
        default=None,
        null=True,
        blank=True
    )
    velocidade_real = models.FloatField(
        help_text="Velocidade real registrada naquele dia (pacotes por minuto)",
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]  # Velocidade não pode ser negativa
    )
    percentual_ganho_real_std = models.FloatField(
        help_text="Percentual de ganho da velocidade real em relação à velocidade padrão (%)",
        null=True,
        blank=True
    )
    percentual_ganho_real_planejada = models.FloatField(
        help_text="Percentual de progresso da velocidade real em relação ao ganho planejado (%)",
        null=True,
        blank=True
    )
    ton_hora_std = models.FloatField(
        help_text="Toneladas por hora com velocidade padrão",
        null=True,
        blank=True
    )
    ton_hora_planejada = models.FloatField(
        help_text="Toneladas por hora com velocidade planejada",
        null=True,
        blank=True
    )
    ton_hora_real = models.FloatField(
        help_text="Toneladas por hora com velocidade real",
        null=True,
        blank=True
    )
    ton_mes_std = models.FloatField(
        help_text="Toneladas por mês com velocidade padrão",
        null=True,
        blank=True
    )
    ton_mes_planejada = models.FloatField(
        help_text="Toneladas por mês com velocidade planejada",
        null=True,
        blank=True
    )
    ton_mes_real = models.FloatField(
        help_text="Toneladas por mês com velocidade real",
        null=True,
        blank=True
    )
    ganho_ton_hora_real_vs_std = models.FloatField(
        help_text="Ganho em toneladas por hora (real vs padrão)",
        null=True,
        blank=True
    )
    ganho_ton_hora_real_vs_planejada = models.FloatField(
        help_text="Ganho em toneladas por hora (real vs planejada)",
        null=True,
        blank=True
    )
    ganho_ton_mes_real_vs_std = models.FloatField(
        help_text="Ganho em toneladas por mês (real vs padrão)",
        null=True,
        blank=True
    )
    ganho_ton_mes_real_vs_planejada = models.FloatField(
        help_text="Ganho em toneladas por mês (real vs planejada)",
        null=True,
        blank=True
    )

    def save(self, *args, **kwargs):
        start = self.start_bortoletto
        gramas = start.formato.gramas

        def calcular_ton_hora(velocidade, gramas):
            if velocidade and gramas:
                kg_por_minuto = (velocidade * gramas) / 1000
                ton_por_hora = (kg_por_minuto * 60) / 1000
                return round(ton_por_hora, 3)
            return 0.0

        def calcular_ton_mes(velocidade, gramas):
            ton_hora = calcular_ton_hora(velocidade, gramas)
            return round(ton_hora * 720, 3) if ton_hora else 0.0

        self.ton_hora_std = calcular_ton_hora(start.velocidade_std, gramas) if start.velocidade_std else 0.0
        self.ton_hora_planejada = calcular_ton_hora(start.velocidade_planejada, gramas) if start.velocidade_planejada else 0.0
        self.ton_hora_real = calcular_ton_hora(self.velocidade_real, gramas) if self.velocidade_real else 0.0
        self.ton_mes_std = calcular_ton_mes(start.velocidade_std, gramas) if start.velocidade_std else 0.0
        self.ton_mes_planejada = calcular_ton_mes(start.velocidade_planejada, gramas) if start.velocidade_planejada else 0.0
        self.ton_mes_real = calcular_ton_mes(self.velocidade_real, gramas) if self.velocidade_real else 0.0

        # Percentual de ganho real vs padrão
        if self.velocidade_real and start.velocidade_std and start.velocidade_std != 0:
            diferenca = self.velocidade_real - start.velocidade_std
            if diferenca > 0:
                self.percentual_ganho_real_std = (diferenca / start.velocidade_std) * 100
            else:
                self.percentual_ganho_real_std = 0.0
            self.percentual_ganho_real_std = round(self.percentual_ganho_real_std, 2)
        else:
            self.percentual_ganho_real_std = None

        # Percentual de progresso em relação ao ganho planejado
        if (self.velocidade_real and start.velocidade_planejada and start.velocidade_std and 
            (start.velocidade_planejada - start.velocidade_std) != 0):
            progresso_diferenca = self.velocidade_real - start.velocidade_std
            meta_diferenca = start.velocidade_planejada - start.velocidade_std
            if self.velocidade_real >= start.velocidade_planejada:
                self.percentual_ganho_real_planejada = 100.0
            elif self.velocidade_real <= start.velocidade_std:
                self.percentual_ganho_real_planejada = 0.0
            else:
                self.percentual_ganho_real_planejada = (progresso_diferenca / meta_diferenca) * 100
                self.percentual_ganho_real_planejada = round(self.percentual_ganho_real_planejada, 2)
        else:
            self.percentual_ganho_real_planejada = None

        # Ganhos em toneladas
        self.ganho_ton_hora_real_vs_std = (self.ton_hora_real - self.ton_hora_std) if self.ton_hora_real and self.ton_hora_std else None
        self.ganho_ton_mes_real_vs_std = (self.ton_mes_real - self.ton_mes_std) if self.ton_mes_real and self.ton_mes_std else None

        ganho_total_possivel_ton_hora = self.ton_hora_planejada - self.ton_hora_std if self.ton_hora_planejada and self.ton_hora_std else 0.0
        ganho_total_possivel_ton_mes = self.ton_mes_planejada - self.ton_mes_std if self.ton_mes_planejada and self.ton_mes_std else 0.0

        if self.percentual_ganho_real_planejada is not None:
            self.ganho_ton_hora_real_vs_planejada = (self.percentual_ganho_real_planejada / 100) * ganho_total_possivel_ton_hora
            self.ganho_ton_hora_real_vs_planejada = round(self.ganho_ton_hora_real_vs_planejada, 3)
            self.ganho_ton_mes_real_vs_planejada = (self.percentual_ganho_real_planejada / 100) * ganho_total_possivel_ton_mes
            self.ganho_ton_mes_real_vs_planejada = round(self.ganho_ton_mes_real_vs_planejada, 3)
        else:
            self.ganho_ton_hora_real_vs_planejada = None
            self.ganho_ton_mes_real_vs_planejada = None

        super().save(*args, **kwargs)

    class Meta:
        unique_together = ('start_bortoletto', 'data')
        verbose_name = "Estatísticas Diárias"
        verbose_name_plural = "Estatísticas Diárias"
        indexes = [
            models.Index(fields=['data']),  # Índice para melhorar consultas por data
        ]

    def __str__(self):
        return f"Estatísticas Diárias - {self.start_bortoletto} - {self.data}"

class ConsolidadoAndretti(models.Model):
    linha = models.CharField(max_length=10, help_text="Nome da linha")
    gramas = models.PositiveIntegerField(help_text="Peso em gramas do formato")
    data_inicio = models.DateField(null=True, blank=True, help_text="Data de início do programa")
    data_ultima_atualizacao = models.DateField(null=True, blank=True, help_text="Data da última estatística diária usada")
    velocidade_std = models.FloatField(null=True, blank=True, help_text="Velocidade padrão")
    velocidade_planejada = models.FloatField(null=True, blank=True, help_text="Velocidade planejada (meta)")
    velocidade_real = models.FloatField(null=True, blank=True, help_text="Velocidade real mais recente")
    percentual_ganho_planejado = models.FloatField(null=True, blank=True, help_text="Percentual de ganho planejado vs padrão")
    percentual_ganho_real_std = models.FloatField(null=True, blank=True, help_text="Percentual de ganho real vs padrão")
    percentual_ganho_real_planejada = models.FloatField(null=True, blank=True, help_text="Percentual de progresso real vs planejada")
    ton_hora_std = models.FloatField(null=True, blank=True, help_text="Toneladas por hora padrão")
    ton_hora_planejada = models.FloatField(null=True, blank=True, help_text="Toneladas por hora planejada")
    ton_hora_real = models.FloatField(null=True, blank=True, help_text="Toneladas por hora real")
    ton_mes_std = models.FloatField(null=True, blank=True, help_text="Toneladas por mês padrão")
    ton_mes_planejada = models.FloatField(null=True, blank=True, help_text="Toneladas por mês planejada")
    ton_mes_real = models.FloatField(null=True, blank=True, help_text="Toneladas por mês real")
    ganho_ton_hora_real_vs_std = models.FloatField(null=True, blank=True, help_text="Ganho ton/hora real vs padrão")
    ganho_ton_hora_real_vs_planejada = models.FloatField(null=True, blank=True, help_text="Ganho ton/hora real vs planejada")
    ganho_ton_mes_real_vs_std = models.FloatField(null=True, blank=True, help_text="Ganho ton/mês real vs padrão")
    ganho_ton_mes_real_vs_planejada = models.FloatField(null=True, blank=True, help_text="Ganho ton/mês real vs planejada")

    class Meta:
        verbose_name = "Consolidado Andretti"
        verbose_name_plural = "Consolidados Andretti"

    def __str__(self):
        return f"{self.linha} - {self.gramas}g - {self.data_inicio}"

# Novo modelo para registrar dados diários por linha
class RegistroDiarioLinha(models.Model):
    linha = models.ForeignKey(Linha, on_delete=models.CASCADE, related_name='registros_diarios')
    data = models.DateField(
        help_text="Data do registro",
        default=None,
        null=True,
        blank=True
    )
    gramas = models.PositiveIntegerField(
        help_text="Peso em gramas do formato",
        null=True,
        blank=True
    )
    velocidade_std = models.FloatField(
        help_text="Velocidade padrão (Std) do formato",
        null=True,
        blank=True
    )
    velocidade_planejada = models.FloatField(
        help_text="Velocidade planejada (meta) do programa",
        null=True,
        blank=True
    )
    velocidade_real = models.FloatField(
        help_text="Velocidade real registrada naquele dia",
        null=True,
        blank=True
    )
    percentual_ganho_real_std = models.FloatField(
        help_text="Percentual de ganho da velocidade real em relação à velocidade padrão (%)",
        null=True,
        blank=True
    )
    percentual_ganho_real_planejada = models.FloatField(
        help_text="Percentual de progresso da velocidade real em relação ao ganho planejado (%)",
        null=True,
        blank=True
    )
    ganho_ton_hora_real_vs_std = models.FloatField(
        help_text="Ganho em toneladas por hora (real vs padrão)",
        null=True,
        blank=True
    )
    ganho_ton_mes_real_vs_std = models.FloatField(
        help_text="Ganho em toneladas por mês (real vs padrão)",
        null=True,
        blank=True
    )

    class Meta:
        unique_together = ('linha', 'data', 'gramas')
        verbose_name = "Registro Diário de Linha"
        verbose_name_plural = "Registros Diários de Linha"
        indexes = [
            models.Index(fields=['data']),  # Índice para melhorar consultas por data
            models.Index(fields=['linha', 'data']),  # Índice composto para consultas por linha e data
        ]

    def __str__(self):
        return f"{self.linha.nome} - {self.gramas}g - {self.data}"

# Função para atualizar os registros diários de linha
def atualizar_registro_diario_linha(estatistica_diaria):
    start = estatistica_diaria.start_bortoletto
    linha = start.linha
    data = estatistica_diaria.data
    gramas = start.formato.gramas

    # Criar ou atualizar o registro diário
    registro, created = RegistroDiarioLinha.objects.get_or_create(
        linha=linha,
        data=data,
        gramas=gramas,
        defaults={
            'velocidade_std': start.velocidade_std,
            'velocidade_planejada': start.velocidade_planejada,
            'velocidade_real': estatistica_diaria.velocidade_real,
            'percentual_ganho_real_std': estatistica_diaria.percentual_ganho_real_std,
            'percentual_ganho_real_planejada': estatistica_diaria.percentual_ganho_real_planejada,
            'ganho_ton_hora_real_vs_std': estatistica_diaria.ganho_ton_hora_real_vs_std,
            'ganho_ton_mes_real_vs_std': estatistica_diaria.ganho_ton_mes_real_vs_std,
        }
    )

    if not created:
        registro.velocidade_std = start.velocidade_std
        registro.velocidade_planejada = start.velocidade_planejada
        registro.velocidade_real = estatistica_diaria.velocidade_real
        registro.percentual_ganho_real_std = estatistica_diaria.percentual_ganho_real_std
        registro.percentual_ganho_real_planejada = estatistica_diaria.percentual_ganho_real_planejada
        registro.ganho_ton_hora_real_vs_std = estatistica_diaria.ganho_ton_hora_real_vs_std
        registro.ganho_ton_mes_real_vs_std = estatistica_diaria.ganho_ton_mes_real_vs_std
        registro.save()

    logger.info(f"RegistroDiarioLinha atualizado para {linha.nome} em {data}")

# Sinal ajustado para garantir sincronização
@receiver(post_save, sender=Formato)
@receiver(post_save, sender=StartBortoletto)
@receiver(post_save, sender=EstatisticasDiarias)
def atualizar_consolidado(sender, instance, **kwargs):
    from django.db import transaction

    with transaction.atomic():
        start_bortoletos_to_update = set()

        if sender == Formato:
            # Quando Formato é atualizado, atualizamos todos os StartBortoletto relacionados
            logger.info(f"Formato {instance} atualizado. Sincronizando StartBortoletto.")
            start_bortoletos = StartBortoletto.objects.filter(formato=instance)
            for sb in start_bortoletos:
                sb.velocidade_std = instance.velocidade_std
                sb.save()  # Isso disparará o sinal de StartBortoletto
                start_bortoletos_to_update.add(sb)

        elif sender == StartBortoletto:
            logger.info(f"StartBortoletto {instance} atualizado.")
            start_bortoletos_to_update.add(instance)

        elif sender == EstatisticasDiarias:
            logger.info(f"EstatisticasDiarias {instance} atualizado.")
            start_bortoletos_to_update.add(instance.start_bortoletto)
            # Atualizar RegistroDiarioLinha
            atualizar_registro_diario_linha(instance)

        # Atualizar ConsolidadoAndretti para cada StartBortoletto afetado
        for start in start_bortoletos_to_update:
            logger.info(f"Atualizando ConsolidadoAndretti para StartBortoletto {start}")
            atualizar_registro_consolidado(start)

def atualizar_registro_consolidado(start_bortoletto):
    from django.db import connection
    logger.info(f"Iniciando atualização para StartBortoletto: {start_bortoletto}")

    if not start_bortoletto.linha or not start_bortoletto.formato:
        logger.warning(f"StartBortoletto {start_bortoletto} sem linha ou formato. Pulando.")
        return

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id FROM programa_andretti_consolidadoandretti
            WHERE linha = %s AND gramas = %s AND data_inicio = %s
        """, [start_bortoletto.linha.nome, start_bortoletto.formato.gramas, start_bortoletto.data_inicio])
        row = cursor.fetchone()
        logger.info(f"Registro existente no ConsolidadoAndretti: {row}")

        estatistica = start_bortoletto.estatisticas_diarias.order_by('-data').first()
        if not estatistica:
            logger.info(f"Sem EstatisticasDiarias para StartBortoletto {start_bortoletto}. Pulando.")
            return

        gramas = start_bortoletto.formato.gramas
        logger.info(f"Dados de entrada: gramas={gramas}, velocidade_std={start_bortoletto.velocidade_std}, "
                    f"velocidade_planejada={start_bortoletto.velocidade_planejada}, "
                    f"velocidade_real={estatistica.velocidade_real}")

        def calcular_ton_hora(velocidade, gramas):
            if velocidade and gramas:
                kg_por_minuto = (velocidade * gramas) / 1000
                ton_por_hora = (kg_por_minuto * 60) / 1000
                ton_por_hora = round(ton_por_hora, 3)
                logger.info(f"Calculando ton_hora para velocidade={velocidade}, gramas={gramas}: {ton_por_hora}")
                return ton_por_hora
            logger.info(f"ton_hora não calculado: velocidade={velocidade}, gramas={gramas}")
            return 0.0

        def calcular_ton_mes(velocidade, gramas):
            ton_hora = calcular_ton_hora(velocidade, gramas)
            ton_mes = round(ton_hora * 720, 3) if ton_hora else 0.0
            logger.info(f"Calculando ton_mes para ton_hora={ton_hora}: {ton_mes}")
            return ton_mes

        ton_hora_std = calcular_ton_hora(start_bortoletto.velocidade_std, gramas)
        ton_hora_planejada = calcular_ton_hora(start_bortoletto.velocidade_planejada, gramas)
        ton_hora_real = calcular_ton_hora(estatistica.velocidade_real, gramas)
        ton_mes_std = calcular_ton_mes(start_bortoletto.velocidade_std, gramas)
        ton_mes_planejada = calcular_ton_mes(start_bortoletto.velocidade_planejada, gramas)
        ton_mes_real = calcular_ton_mes(estatistica.velocidade_real, gramas)

        percentual_ganho_real_std = None
        if estatistica.velocidade_real and start_bortoletto.velocidade_std and start_bortoletto.velocidade_std != 0:
            diferenca = estatistica.velocidade_real - start_bortoletto.velocidade_std
            if diferenca > 0:
                percentual_ganho_real_std = (diferenca / start_bortoletto.velocidade_std) * 100
            else:
                percentual_ganho_real_std = 0.0
            percentual_ganho_real_std = round(percentual_ganho_real_std, 2)
            logger.info(f"percentual_ganho_real_std calculado: {percentual_ganho_real_std}")
        else:
            logger.info(f"percentual_ganho_real_std não calculado: "
                        f"velocidade_real={estatistica.velocidade_real}, "
                        f"velocidade_std={start_bortoletto.velocidade_std}")

        percentual_ganho_real_planejada = None
        if (estatistica.velocidade_real and start_bortoletto.velocidade_planejada and start_bortoletto.velocidade_std and 
            (start_bortoletto.velocidade_planejada - start_bortoletto.velocidade_std) != 0):
            progresso_diferenca = estatistica.velocidade_real - start_bortoletto.velocidade_std
            meta_diferenca = start_bortoletto.velocidade_planejada - start_bortoletto.velocidade_std
            if estatistica.velocidade_real >= start_bortoletto.velocidade_planejada:
                percentual_ganho_real_planejada = 100.0
            elif estatistica.velocidade_real <= start_bortoletto.velocidade_std:
                percentual_ganho_real_planejada = 0.0
            else:
                percentual_ganho_real_planejada = (progresso_diferenca / meta_diferenca) * 100
                percentual_ganho_real_planejada = round(percentual_ganho_real_planejada, 2)
            logger.info(f"percentual_ganho_real_planejada calculado: {percentual_ganho_real_planejada}, "
                        f"meta_diferenca={meta_diferenca}, progresso_diferenca={progresso_diferenca}")
        else:
            logger.info(f"percentual_ganho_real_planejada não calculado: "
                        f"velocidade_real={estatistica.velocidade_real}, "
                        f"velocidade_std={start_bortoletto.velocidade_std}, "
                        f"velocidade_planejada={start_bortoletto.velocidade_planejada}")

        ganho_ton_hora_real_vs_std = (ton_hora_real - ton_hora_std) if ton_hora_real and ton_hora_std else None
        ganho_ton_mes_real_vs_std = (ton_mes_real - ton_mes_std) if ton_mes_real and ton_mes_std else None

        ganho_total_possivel_ton_hora = ton_hora_planejada - ton_hora_std if ton_hora_planejada and ton_hora_std else 0.0
        ganho_total_possivel_ton_mes = ton_mes_planejada - ton_mes_std if ton_mes_planejada and ton_mes_std else 0.0

        ganho_ton_hora_real_vs_planejada = None
        ganho_ton_mes_real_vs_planejada = None
        if percentual_ganho_real_planejada is not None:
            ganho_ton_hora_real_vs_planejada = (percentual_ganho_real_planejada / 100) * ganho_total_possivel_ton_hora
            ganho_ton_hora_real_vs_planejada = round(ganho_ton_hora_real_vs_planejada, 3)
            ganho_ton_mes_real_vs_planejada = (percentual_ganho_real_planejada / 100) * ganho_total_possivel_ton_mes
            ganho_ton_mes_real_vs_planejada = round(ganho_ton_mes_real_vs_planejada, 3)
            logger.info(f"ganho_ton_hora_real_vs_planejada calculado: {ganho_ton_hora_real_vs_planejada}, "
                        f"ganho_ton_mes_real_vs_planejada calculado: {ganho_ton_mes_real_vs_planejada}")
        else:
            logger.info(f"Ganhos em toneladas vs planejada não calculados")

        logger.info(f"Valores calculados: ton_hora_real={ton_hora_real}, ton_mes_real={ton_mes_real}, "
                    f"percentual_ganho_real_std={percentual_ganho_real_std}, "
                    f"percentual_ganho_real_planejada={percentual_ganho_real_planejada}, "
                    f"ganho_ton_hora_real_vs_std={ganho_ton_hora_real_vs_std}, "
                    f"ganho_ton_hora_real_vs_planejada={ganho_ton_hora_real_vs_planejada}, "
                    f"ganho_ton_mes_real_vs_std={ganho_ton_mes_real_vs_std}, "
                    f"ganho_ton_mes_real_vs_planejada={ganho_ton_mes_real_vs_planejada}")

        if row:
            logger.info(f"Atualizando registro existente no ConsolidadoAndretti: {row}")
            cursor.execute("""
                UPDATE programa_andretti_consolidadoandretti
                SET velocidade_std = %s,
                    velocidade_planejada = %s,
                    velocidade_real = %s,
                    percentual_ganho_planejado = %s,
                    percentual_ganho_real_std = %s,
                    percentual_ganho_real_planejada = %s,
                    ton_hora_std = %s,
                    ton_hora_planejada = %s,
                    ton_hora_real = %s,
                    ton_mes_std = %s,
                    ton_mes_planejada = %s,
                    ton_mes_real = %s,
                    ganho_ton_hora_real_vs_std = %s,
                    ganho_ton_hora_real_vs_planejada = %s,
                    ganho_ton_mes_real_vs_std = %s,
                    ganho_ton_mes_real_vs_planejada = %s,
                    data_ultima_atualizacao = %s
                WHERE linha = %s AND gramas = %s AND data_inicio = %s
            """, [
                start_bortoletto.velocidade_std,
                start_bortoletto.velocidade_planejada,
                estatistica.velocidade_real,
                start_bortoletto.percentual_ganho_planejado,
                percentual_ganho_real_std,
                percentual_ganho_real_planejada,
                ton_hora_std,
                ton_hora_planejada,
                ton_hora_real,
                ton_mes_std,
                ton_mes_planejada,
                ton_mes_real,
                ganho_ton_hora_real_vs_std,
                ganho_ton_hora_real_vs_planejada,
                ganho_ton_mes_real_vs_std,
                ganho_ton_mes_real_vs_planejada,
                estatistica.data,
                start_bortoletto.linha.nome,
                start_bortoletto.formato.gramas,
                start_bortoletto.data_inicio
            ])
        else:
            logger.info("Inserindo novo registro no ConsolidadoAndretti")
            cursor.execute("""
                INSERT INTO programa_andretti_consolidadoandretti (
                    linha, gramas, data_inicio, data_ultima_atualizacao, velocidade_std, velocidade_planejada,
                    velocidade_real, percentual_ganho_planejado, percentual_ganho_real_std, 
                    percentual_ganho_real_planejada, ton_hora_std, ton_hora_planejada, ton_hora_real, 
                    ton_mes_std, ton_mes_planejada, ton_mes_real, ganho_ton_hora_real_vs_std,
                    ganho_ton_hora_real_vs_planejada, ganho_ton_mes_real_vs_std, ganho_ton_mes_real_vs_planejada
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, [
                start_bortoletto.linha.nome,
                start_bortoletto.formato.gramas,
                start_bortoletto.data_inicio,
                estatistica.data,
                start_bortoletto.velocidade_std,
                start_bortoletto.velocidade_planejada,
                estatistica.velocidade_real,
                start_bortoletto.percentual_ganho_planejado,
                percentual_ganho_real_std,
                percentual_ganho_real_planejada,
                ton_hora_std,
                ton_hora_planejada,
                ton_hora_real,
                ton_mes_std,
                ton_mes_planejada,
                ton_mes_real,
                ganho_ton_hora_real_vs_std,
                ganho_ton_hora_real_vs_planejada,
                ganho_ton_mes_real_vs_std,
                ganho_ton_mes_real_vs_planejada
            ])
        logger.info("Atualização concluída com sucesso")