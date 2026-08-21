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

    # Descobre projetos novos do Node-RED e captura snapshot INITIAL
    # automaticamente. Sem isso, projeto criado mas nunca deployado
    # ficaria invisível no Django até o 1º deploy.
    def _sync_projetos_nodered():
        try:
            from .nodered_history_views import sincronizar_projetos
            stats = sincronizar_projetos()
            if stats.get('novos') or stats.get('sem_flow'):
                logger.info('Node-RED sync: novos=%s, sem_flow=%s, já_existiam=%d',
                            stats.get('novos'), stats.get('sem_flow'),
                            len(stats.get('ja_existiam', [])))
        except Exception:
            logger.exception('Falha no auto-sync de projetos Node-RED')

    scheduler.add_job(
        _sync_projetos_nodered,
        CronTrigger(minute='*/5'),  # a cada 5 min
        id='nodered_projects_sync',
        name='Sync projetos Node-RED',
        replace_existing=True,
    )

    scheduler.start()
    logger.info("✓ Scheduler iniciado com sucesso")


def parar_scheduler():
    """Para o scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("✓ Scheduler parado")