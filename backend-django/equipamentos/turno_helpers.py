"""
Turno Helpers
=============
Funções para gerenciamento de turnos de produção
"""

from dataclasses import dataclass
from typing import Optional, Union
from datetime import datetime, time, timedelta
from django.utils import timezone
from equipamentos.models import TurnoProducao


@dataclass(frozen=True)
class TurnoFallback:
    """Definição operacional usada somente quando o cadastro está vazio.

    Mantém o MIS Core funcional sem persistir ou inventar registros no banco.
    Os limites seguem a janela industrial já usada pelo FastAPI/coletor.
    """

    nome: str
    codigo: str
    hora_inicio: time
    hora_fim: time
    duracao_horas: float = 8.0
    ativo: bool = True


TurnoLike = Union[TurnoProducao, TurnoFallback]

TURNOS_FALLBACK = (
    TurnoFallback('Turno 1', 'T1', time(6, 0), time(14, 0)),
    TurnoFallback('Turno 2', 'T2', time(14, 0), time(22, 0)),
    TurnoFallback('Turno 3', 'T3', time(22, 0), time(6, 0)),
)


def _turno_em_horario(turno: TurnoLike, hora_atual: time) -> bool:
    """Intervalo semiaberto [início, fim), sem sobreposição nas trocas."""
    if turno.hora_inicio < turno.hora_fim:
        return turno.hora_inicio <= hora_atual < turno.hora_fim
    return hora_atual >= turno.hora_inicio or hora_atual < turno.hora_fim


def obter_turno_atual() -> TurnoLike:
    """
    Retorna o turno de produção em andamento no momento atual
    
    Returns:
        TurnoProducao ativo ou None se não houver turno ativo
    """
    agora = timezone.localtime(timezone.now())
    hora_atual = agora.time()
    
    turnos = TurnoProducao.objects.filter(ativo=True)
    
    for turno in turnos:
        if _turno_em_horario(turno, hora_atual):
            return turno

    # Sem turno ativo no banco: usa o padrão industrial em memória. Não grava
    # nada e evita que "TURNO" seja silenciosamente tratado como dia civil.
    return next(
        turno for turno in TURNOS_FALLBACK
        if _turno_em_horario(turno, hora_atual)
    )


def calcular_inicio_turno(turno: Optional[TurnoLike] = None) -> datetime:
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


def calcular_fim_turno(turno: Optional[TurnoLike] = None) -> datetime:
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


def get_turno_info(turno: Optional[TurnoLike] = None) -> dict:
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
