"""
Helpers para cálculo de vazão necessária (throughput required)

A vazão necessária é calculada como:
vazao_necessaria = (planejado_total - produzido_total) / horas_restantes

Onde:
- planejado_total: soma do que foi planejado produzir no período
- produzido_total: soma do que foi efetivamente produzido no período
- horas_restantes: horas que faltam até o fim do período (turno/dia/semana/mês)
"""

from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Sum, Q
from decimal import Decimal
import logging

from .models import (
    CalendarioProducao, RegistroProducaoTurno, LinhaProducao,
    TurnoProducao, OrdemProducao
)

logger = logging.getLogger(__name__)


class VazaoCalculator:
    """Calculador de vazão necessária para diferentes períodos"""

    @staticmethod
    def get_turno_atual():
        """Retorna o turno atual baseado na hora do sistema"""
        agora = timezone.now()
        hora_atual = agora.time()

        turnos = TurnoProducao.objects.filter(ativo=True).order_by('hora_inicio')

        for turno in turnos:
            if turno.hora_inicio <= hora_atual < turno.hora_fim:
                return turno

        # Se não encontrar turno no horário, retorna o primeiro turno
        return turnos.first()

    @staticmethod
    def calcular_horas_restantes_turno(turno: TurnoProducao) -> float:
        """
        Calcula quantas horas faltam para o fim do turno atual
        """
        agora = timezone.now()
        hora_atual = agora.time()

        # Converter horas para datetime para cálculo
        agora_dt = datetime.combine(agora.date(), hora_atual)
        fim_turno_dt = datetime.combine(agora.date(), turno.hora_fim)

        # Se o turno passou para o dia seguinte
        if turno.hora_fim < turno.hora_inicio:
            if hora_atual < turno.hora_inicio:
                # Ainda está no turno anterior
                fim_turno_dt = datetime.combine(agora.date(), turno.hora_fim)
            else:
                # Turno passou para o dia seguinte
                fim_turno_dt = datetime.combine(
                    agora.date() + timedelta(days=1), turno.hora_fim
                )

        diferenca = fim_turno_dt - agora_dt
        horas_restantes = max(0, diferenca.total_seconds() / 3600)

        return horas_restantes

    @staticmethod
    def calcular_horas_restantes_dia() -> float:
        """
        Calcula quantas horas faltam para o fim do dia (23:59:59)
        """
        agora = timezone.now()
        fim_dia = agora.replace(hour=23, minute=59, second=59)

        diferenca = fim_dia - agora
        horas_restantes = max(0, diferenca.total_seconds() / 3600)

        return horas_restantes

    @staticmethod
    def calcular_horas_restantes_semana() -> float:
        """
        Calcula quantas horas faltam para o fim da semana (domingo 23:59:59)
        """
        agora = timezone.now()
        dias_ate_domingo = (6 - agora.weekday()) % 7
        if dias_ate_domingo == 0:
            dias_ate_domingo = 7

        fim_semana = agora + timedelta(days=dias_ate_domingo)
        fim_semana = fim_semana.replace(hour=23, minute=59, second=59)

        diferenca = fim_semana - agora
        horas_restantes = max(0, diferenca.total_seconds() / 3600)

        return horas_restantes

    @staticmethod
    def calcular_horas_restantes_mes() -> float:
        """
        Calcula quantas horas faltam para o fim do mês
        """
        agora = timezone.now()

        # Próximo dia 1º
        if agora.month == 12:
            proximo_mes = agora.replace(year=agora.year + 1, month=1, day=1)
        else:
            proximo_mes = agora.replace(month=agora.month + 1, day=1)

        fim_mes = proximo_mes - timedelta(seconds=1)

        diferenca = fim_mes - agora
        horas_restantes = max(0, diferenca.total_seconds() / 3600)

        return horas_restantes

    @staticmethod
    def get_planejado_turno(linha: LinhaProducao, turno: TurnoProducao, data: datetime.date = None) -> int:
        """
        Retorna o total planejado para um turno específico
        """
        if data is None:
            data = timezone.now().date()

        calendario = CalendarioProducao.objects.filter(
            linha=linha,
            turno=turno,
            data=data,
            programado=True
        ).first()

        return calendario.meta_producao_turno if calendario else 0

    @staticmethod
    def get_produzido_turno(linha: LinhaProducao, turno: TurnoProducao, data: datetime.date = None) -> Decimal:
        """
        Retorna o total produzido em um turno específico
        """
        if data is None:
            data = timezone.now().date()

        registros = RegistroProducaoTurno.objects.filter(
            linha=linha,
            turno=turno,
            data=data
        ).aggregate(total=Sum('producao_toneladas'))

        return registros['total'] or Decimal(0)

    @staticmethod
    def get_planejado_dia(linha: LinhaProducao, data: datetime.date = None) -> int:
        """
        Retorna o total planejado para um dia (soma de todos os turnos)
        """
        if data is None:
            data = timezone.now().date()

        total = CalendarioProducao.objects.filter(
            linha=linha,
            data=data,
            programado=True
        ).aggregate(total=Sum('meta_producao_turno'))

        return total['total'] or 0

    @staticmethod
    def get_produzido_dia(linha: LinhaProducao, data: datetime.date = None) -> Decimal:
        """
        Retorna o total produzido em um dia (soma de todos os turnos)
        """
        if data is None:
            data = timezone.now().date()

        registros = RegistroProducaoTurno.objects.filter(
            linha=linha,
            data=data
        ).aggregate(total=Sum('producao_toneladas'))

        return registros['total'] or Decimal(0)

    @staticmethod
    def get_planejado_semana(linha: LinhaProducao, data: datetime.date = None) -> int:
        """
        Retorna o total planejado para a semana (segunda a domingo)
        """
        if data is None:
            data = timezone.now().date()

        # Encontrar segunda-feira da semana
        dias_desde_segunda = data.weekday()
        segunda = data - timedelta(days=dias_desde_segunda)
        domingo = segunda + timedelta(days=6)

        total = CalendarioProducao.objects.filter(
            linha=linha,
            data__gte=segunda,
            data__lte=domingo,
            programado=True
        ).aggregate(total=Sum('meta_producao_turno'))

        return total['total'] or 0

    @staticmethod
    def get_produzido_semana(linha: LinhaProducao, data: datetime.date = None) -> Decimal:
        """
        Retorna o total produzido na semana
        """
        if data is None:
            data = timezone.now().date()

        # Encontrar segunda-feira da semana
        dias_desde_segunda = data.weekday()
        segunda = data - timedelta(days=dias_desde_segunda)
        domingo = segunda + timedelta(days=6)

        registros = RegistroProducaoTurno.objects.filter(
            linha=linha,
            data__gte=segunda,
            data__lte=domingo
        ).aggregate(total=Sum('producao_toneladas'))

        return registros['total'] or Decimal(0)

    @staticmethod
    def get_planejado_mes(linha: LinhaProducao, data: datetime.date = None) -> int:
        """
        Retorna o total planejado para o mês
        """
        if data is None:
            data = timezone.now().date()

        primeiro_dia = data.replace(day=1)

        # Próximo mês
        if data.month == 12:
            proximo_mes = data.replace(year=data.year + 1, month=1, day=1)
        else:
            proximo_mes = data.replace(month=data.month + 1, day=1)

        ultimo_dia = proximo_mes - timedelta(days=1)

        total = CalendarioProducao.objects.filter(
            linha=linha,
            data__gte=primeiro_dia,
            data__lte=ultimo_dia,
            programado=True
        ).aggregate(total=Sum('meta_producao_turno'))

        return total['total'] or 0

    @staticmethod
    def get_produzido_mes(linha: LinhaProducao, data: datetime.date = None) -> Decimal:
        """
        Retorna o total produzido no mês
        """
        if data is None:
            data = timezone.now().date()

        primeiro_dia = data.replace(day=1)

        # Próximo mês
        if data.month == 12:
            proximo_mes = data.replace(year=data.year + 1, month=1, day=1)
        else:
            proximo_mes = data.replace(month=data.month + 1, day=1)

        ultimo_dia = proximo_mes - timedelta(days=1)

        registros = RegistroProducaoTurno.objects.filter(
            linha=linha,
            data__gte=primeiro_dia,
            data__lte=ultimo_dia
        ).aggregate(total=Sum('producao_toneladas'))

        return registros['total'] or Decimal(0)

    @staticmethod
    def calcular_vazao_necessaria_turno(linha: LinhaProducao) -> dict:
        """
        Calcula vazão necessária para o turno atual
        
        Retorna:
        {
            'periodo': 'TURNO',
            'turno': 'Turno A',
            'data': '2024-12-01',
            'planejado': 1000,
            'produzido': 500,
            'falta_produzir': 500,
            'horas_restantes': 4.5,
            'vazao_necessaria': 111.11,  # ton/hora ou unidades/hora
            'status': 'OK' ou 'CRÍTICO'
        }
        """
        agora = timezone.now()
        data = agora.date()
        turno = VazaoCalculator.get_turno_atual()

        planejado = VazaoCalculator.get_planejado_turno(linha, turno, data)
        produzido = VazaoCalculator.get_produzido_turno(linha, turno, data)
        horas_restantes = VazaoCalculator.calcular_horas_restantes_turno(turno)

        falta_produzir = float(planejado) - float(produzido)
        falta_produzir = max(0, falta_produzir)

        vazao_necessaria = 0
        if horas_restantes > 0:
            vazao_necessaria = falta_produzir / horas_restantes

        # Determinar status
        meta_vazao = linha.meta_toneladas_hora or 0
        status = 'OK' if vazao_necessaria <= float(meta_vazao) else 'CRÍTICO'

        return {
            'periodo': 'TURNO',
            'turno': turno.nome if turno else 'N/A',
            'turno_codigo': turno.codigo if turno else 'N/A',
            'data': data.isoformat(),
            'planejado': planejado,
            'produzido': float(produzido),
            'falta_produzir': falta_produzir,
            'horas_restantes': round(horas_restantes, 2),
            'vazao_necessaria': round(vazao_necessaria, 2),
            'meta_vazao': float(meta_vazao) if meta_vazao else 0,
            'status': status
        }

    @staticmethod
    def calcular_vazao_necessaria_dia(linha: LinhaProducao) -> dict:
        """
        Calcula vazão necessária para o dia atual
        """
        agora = timezone.now()
        data = agora.date()

        planejado = VazaoCalculator.get_planejado_dia(linha, data)
        produzido = VazaoCalculator.get_produzido_dia(linha, data)
        horas_restantes = VazaoCalculator.calcular_horas_restantes_dia()

        falta_produzir = float(planejado) - float(produzido)
        falta_produzir = max(0, falta_produzir)

        vazao_necessaria = 0
        if horas_restantes > 0:
            vazao_necessaria = falta_produzir / horas_restantes

        # Determinar status
        meta_vazao = linha.meta_toneladas_hora or 0
        status = 'OK' if vazao_necessaria <= float(meta_vazao) else 'CRÍTICO'

        return {
            'periodo': 'DIA',
            'data': data.isoformat(),
            'planejado': planejado,
            'produzido': float(produzido),
            'falta_produzir': falta_produzir,
            'horas_restantes': round(horas_restantes, 2),
            'vazao_necessaria': round(vazao_necessaria, 2),
            'meta_vazao': float(meta_vazao) if meta_vazao else 0,
            'status': status
        }

    @staticmethod
    def calcular_vazao_necessaria_semana(linha: LinhaProducao) -> dict:
        """
        Calcula vazão necessária para a semana atual
        """
        agora = timezone.now()
        data = agora.date()

        planejado = VazaoCalculator.get_planejado_semana(linha, data)
        produzido = VazaoCalculator.get_produzido_semana(linha, data)
        horas_restantes = VazaoCalculator.calcular_horas_restantes_semana()

        falta_produzir = float(planejado) - float(produzido)
        falta_produzir = max(0, falta_produzir)

        vazao_necessaria = 0
        if horas_restantes > 0:
            vazao_necessaria = falta_produzir / horas_restantes

        # Determinar status
        meta_vazao = linha.meta_toneladas_hora or 0
        status = 'OK' if vazao_necessaria <= float(meta_vazao) else 'CRÍTICO'

        return {
            'periodo': 'SEMANA',
            'data': data.isoformat(),
            'planejado': planejado,
            'produzido': float(produzido),
            'falta_produzir': falta_produzir,
            'horas_restantes': round(horas_restantes, 2),
            'vazao_necessaria': round(vazao_necessaria, 2),
            'meta_vazao': float(meta_vazao) if meta_vazao else 0,
            'status': status
        }

    @staticmethod
    def calcular_vazao_necessaria_mes(linha: LinhaProducao) -> dict:
        """
        Calcula vazão necessária para o mês atual
        """
        agora = timezone.now()
        data = agora.date()

        planejado = VazaoCalculator.get_planejado_mes(linha, data)
        produzido = VazaoCalculator.get_produzido_mes(linha, data)
        horas_restantes = VazaoCalculator.calcular_horas_restantes_mes()

        falta_produzir = float(planejado) - float(produzido)
        falta_produzir = max(0, falta_produzir)

        vazao_necessaria = 0
        if horas_restantes > 0:
            vazao_necessaria = falta_produzir / horas_restantes

        # Determinar status
        meta_vazao = linha.meta_toneladas_hora or 0
        status = 'OK' if vazao_necessaria <= float(meta_vazao) else 'CRÍTICO'

        return {
            'periodo': 'MÊS',
            'data': data.isoformat(),
            'planejado': planejado,
            'produzido': float(produzido),
            'falta_produzir': falta_produzir,
            'horas_restantes': round(horas_restantes, 2),
            'vazao_necessaria': round(vazao_necessaria, 2),
            'meta_vazao': float(meta_vazao) if meta_vazao else 0,
            'status': status
        }

    @staticmethod
    def calcular_todas_vazoes(linha: LinhaProducao) -> dict:
        """
        Calcula vazão necessária para todos os períodos (turno, dia, semana, mês)
        """
        return {
            'linha_id': linha.id,
            'linha_codigo': linha.codigo,
            'linha_nome': linha.nome,
            'turno': VazaoCalculator.calcular_vazao_necessaria_turno(linha),
            'dia': VazaoCalculator.calcular_vazao_necessaria_dia(linha),
            'semana': VazaoCalculator.calcular_vazao_necessaria_semana(linha),
            'mes': VazaoCalculator.calcular_vazao_necessaria_mes(linha),
        }
