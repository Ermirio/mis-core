"""
Scheduler - Executa agregações em intervalos regulares
====================================================
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings

from .agregador import agregador

logger = logging.getLogger('Scheduler')

scheduler = BackgroundScheduler()


def iniciar_scheduler():
    """Inicia o scheduler de agregações"""
    
    if scheduler.running:
        logger.warning("Scheduler já está rodando")
        return
    
    logger.info("Iniciando scheduler de agregações...")
    
    # Agrega última hora a cada hora (no minuto 5)
    scheduler.add_job(
        agregador.agregar_ultima_hora,
        CronTrigger(minute=5),
        id='agregar_hora',
        name='Agregar última hora',
        replace_existing=True
    )
    
    # Agrega último turno a cada 1 hora (no minuto 10)
    scheduler.add_job(
        agregador.agregar_ultimo_turno,
        CronTrigger(minute=10),
        id='agregar_turno',
        name='Agregar último turno',
        replace_existing=True
    )
    
    # Agrega dia anterior todos os dias às 00:30
    scheduler.add_job(
        agregador.agregar_dia_anterior,
        CronTrigger(hour=0, minute=30),
        id='agregar_dia',
        name='Agregar dia anterior',
        replace_existing=True
    )

    # Agrega turno ATUAL a cada 1 minuto (Real-time History)
    scheduler.add_job(
        agregador.agregar_turno_atual,
        CronTrigger(minute='*'), # Todo minuto
        id='agregar_turno_atual',
        name='Agregar turno atual',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("✓ Scheduler iniciado com sucesso")


def parar_scheduler():
    """Para o scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("✓ Scheduler parado")