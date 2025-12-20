"""
Turno Helpers
=============
Funções para gerenciamento de turnos de produção
"""

from typing import Optional
from datetime import datetime, time, timedelta
from django.utils import timezone
from equipamentos.models import TurnoProducao


def obter_turno_atual() -> Optional[TurnoProducao]:
    """
    Retorna o turno de produção em andamento no momento atual
    
    Returns:
        TurnoProducao ativo ou None se não houver turno ativo
    """
    agora = timezone.localtime(timezone.now())
    hora_atual = agora.time()
    
    turnos = TurnoProducao.objects.filter(ativo=True)
    
    for turno in turnos:
        if turno.hora_inicio <= turno.hora_fim:
            # Turno não vira o dia (ex: 06:00 às 14:00)
            if turno.hora_inicio <= hora_atual <= turno.hora_fim:
                return turno
        else:
            # Turno vira o dia (ex: 22:00 às 06:00)
            if hora_atual >= turno.hora_inicio or hora_atual <= turno.hora_fim:
                return turno
    
    return None


def calcular_inicio_turno(turno: Optional[TurnoProducao] = None) -> datetime:
    """
    Calcula o timestamp de início do turno atual
    
    Args:
        turno: Turno de produção (opcional, busca turno atual se não fornecido)
    
    Returns:
        Datetime aware do início do turno
    """
    if turno is None:
        turno = obter_turno_atual()
    
    if not turno:
        # Fallback: início do dia atual
        return timezone.localtime(timezone.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    
    agora = timezone.localtime(timezone.now())
    inicio_turno = agora.replace(
        hour=turno.hora_inicio.hour,
        minute=turno.hora_inicio.minute,
        second=0,
        microsecond=0
    )
    
    # Se o turno vira o dia e já passou da meia-noite
    if turno.hora_inicio > turno.hora_fim and agora.time() < turno.hora_fim:
        # Início foi ontem
        inicio_turno -= timedelta(days=1)
    
    # Se o início calculado está no futuro, foi ontem
    if inicio_turno > agora:
        inicio_turno -= timedelta(days=1)
    
    return inicio_turno


def calcular_fim_turno(turno: Optional[TurnoProducao] = None) -> datetime:
    """
    Calcula o timestamp de fim do turno atual
    
    Args:
        turno: Turno de produção (opcional, busca turno atual se não fornecido)
    
    Returns:
        Datetime aware do fim do turno
    """
    if turno is None:
        turno = obter_turno_atual()
    
    if not turno:
        # Fallback: fim do dia atual
        return timezone.localtime(timezone.now()).replace(hour=23, minute=59, second=59, microsecond=999999)
    
    inicio_turno = calcular_inicio_turno(turno)
    
    fim_turno = inicio_turno.replace(
        hour=turno.hora_fim.hour,
        minute=turno.hora_fim.minute,
        second=0,
        microsecond=0
    )
    
    # Se o turno vira o dia
    if turno.hora_inicio > turno.hora_fim:
        fim_turno += timedelta(days=1)
    
    return fim_turno


def detectar_turno_encerrado() -> Optional[TurnoProducao]:
    """
    Detecta se algum turno acabou de encerrar (nos últimos 5 minutos)
    Útil para trigger de consolidação
    
    Returns:
        TurnoProducao que acabou de encerrar ou None
    """
    agora = timezone.localtime(timezone.now())
    
    turnos = TurnoProducao.objects.filter(ativo=True)
    
    for turno in turnos:
        fim_turno = calcular_fim_turno(turno)
        
        # Verifica se o fim do turno foi nos últimos 5 minutos
        delta = agora - fim_turno
        if timedelta(minutes=0) <= delta <= timedelta(minutes=5):
            return turno
    
    return None


def get_turno_info(turno: Optional[TurnoProducao] = None) -> dict:
    """
    Retorna informações completas sobre um turno
    
    Args:
        turno: Turno de produção (opcional, busca turno atual se não fornecido)
    
    Returns:
        Dict com informações do turno: {
            'turno': TurnoProducao,
            'nome': str,
            'inicio': datetime,
            'fim': datetime,
            'duracao_horas': float,
            'em_andamento': bool
        }
    """
    if turno is None:
        turno = obter_turno_atual()
    
    if not turno:
        return {
            'turno': None,
            'nome': 'Sem turno',
            'inicio': None,
            'fim': None,
            'duracao_horas': 0.0,
            'em_andamento': False
        }
    
    inicio = calcular_inicio_turno(turno)
    fim = calcular_fim_turno(turno)
    duracao = (fim - inicio).total_seconds() / 3600.0
    
    agora = timezone.localtime(timezone.now())
    em_andamento = inicio <= agora <= fim
    
    return {
        'turno': turno,
        'nome': turno.nome,
        'inicio': inicio,
        'fim': fim,
        'duracao_horas': duracao,
        'em_andamento': em_andamento
    }