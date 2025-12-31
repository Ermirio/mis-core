"""
Schedulers automáticos para consolidação de dados
Roda automaticamente quando o Django inicia
"""

import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from django_apscheduler import util

from equipamentos.models import (
    OrdemProducao, RegistroProducaoTurno, TurnoProducao,
    LinhaProducao, EventoEstadoEquipamento
)
from influxdb import InfluxDBClient

logger = logging.getLogger(__name__)


def consolidar_turnos_automatico():
    """
    Consolida dados de produção do InfluxDB para MySQL
    Detecta automaticamente turnos concluídos e consolida
    """
    logger.info("[SCHEDULER] Iniciando consolidação automática de turnos...")
    
    # Conectar ao InfluxDB
    try:
        influx_client = InfluxDBClient(
            host='127.0.0.1',
            port=8086,
            database='industrial_db',
            username='admin',
            password='admin123'
        )
    except Exception as e:
        logger.error(f"[SCHEDULER] Erro ao conectar InfluxDB: {e}")
        return
    
    # Buscar turnos ativos
    turnos = TurnoProducao.objects.filter(ativo=True)
    linhas = LinhaProducao.objects.filter(ativa=True)
    
    # Buscar OPs ativas
    ops_ativas = OrdemProducao.objects.filter(
        status__in=['PRODUZINDO', 'PAUSADA']
    )
    
    if not ops_ativas.exists():
        logger.info("[SCHEDULER] Nenhuma OP ativa encontrada")
        influx_client.close()
        return
    
    consolidados = 0
    hoje = timezone.now().date()
    
    # Para cada OP ativa, verificar se há turnos não consolidados
    for op in ops_ativas:
        linha = op.linha
        
        for turno in turnos:
            # Verificar se já foi consolidado (hoje)
            ja_consolidado = RegistroProducaoTurno.objects.filter(
                ordem_producao=op,
                data=hoje,
                turno=turno
            ).exists()
            
            if ja_consolidado:
                continue
            
            # Verificar se o turno já passou
            agora = timezone.now().time()
            
            # Se turno já passou, consolidar
            if agora > turno.hora_fim or (turno.hora_fim < turno.hora_inicio and agora < turno.hora_inicio):
                try:
                    logger.info(f"[SCHEDULER] Consolidando OP {op.codigo} - Turno {turno.codigo} - Data {hoje}")
                    
                    # Calcular intervalo do turno
                    inicio_turno = datetime.combine(hoje, turno.hora_inicio)
                    
                    if turno.hora_fim < turno.hora_inicio:
                        # Turno cruza meia-noite
                        fim_turno = datetime.combine(hoje + timedelta(days=1), turno.hora_fim)
                    else:
                        fim_turno = datetime.combine(hoje, turno.hora_fim)
                    
                    # Buscar dados do InfluxDB
                    query = f"""
                    SELECT 
                        SUM(contagem_saida) as producao_unidades,
                        SUM(descarte) as refugo_unidades
                    FROM producao
                    WHERE 
                        linha_codigo = '{linha.codigo}'
                        AND ordem_producao = '{op.codigo}'
                        AND time >= '{inicio_turno.isoformat()}Z'
                        AND time < '{fim_turno.isoformat()}Z'
                    """
                    
                    result = influx_client.query(query)
                    points = list(result.get_points())
                    
                    if points and points[0].get('producao_unidades'):
                        dados = points[0]
                        producao_un = int(dados.get('producao_unidades') or 0)
                        refugo_un = int(dados.get('refugo_unidades') or 0)
                        
                        # Calcular toneladas
                        producao_ton = (producao_un * op.formato_gramas) / 1000000.0
                        refugo_kg = (refugo_un * op.formato_gramas) / 1000.0
                        
                        # Calcular tempos (simplificado)
                        tempo_programado = turno.duracao_horas * 60
                        
                        # Criar registro
                        registro = RegistroProducaoTurno.objects.create(
                            ordem_producao=op,
                            linha=linha,
                            produto=op.produto,
                            data=hoje,
                            turno=turno,
                            producao_unidades=producao_un,
                            producao_toneladas=producao_ton,
                            refugo_unidades=refugo_un,
                            refugo_kg=refugo_kg,
                            tempo_programado_min=tempo_programado,
                            tempo_disponivel_min=tempo_programado,  # Simplificado
                            tempo_producao_min=tempo_programado * 0.8,  # Estimado
                            tempo_parado_min=tempo_programado * 0.1,  # Estimado
                            tempo_setup_min=tempo_programado * 0.1,  # Estimado
                            velocidade_planejada=linha.velocidade_planejada or 0,
                            observacoes='Auto-consolidado pelo scheduler'
                        )
                        
                        logger.info(
                            f"[SCHEDULER] ✓ Consolidado: {op.codigo} - "
                            f"Turno {turno.codigo} - {producao_un} un - OEE {registro.oee:.1f}%"
                        )
                        consolidados += 1
                    else:
                        logger.debug(f"[SCHEDULER] Sem dados para {op.codigo} - Turno {turno.codigo}")
                        
                except Exception as e:
                    logger.error(f"[SCHEDULER] Erro ao consolidar {op.codigo}: {e}")
    
    influx_client.close()
    logger.info(f"[SCHEDULER] Consolidação concluída: {consolidados} registros criados")


@util.close_old_connections
def delete_old_job_executions(max_age=604_800):
    """
    Remove execuções antigas de jobs (padrão: 7 dias)
    Mantém o banco limpo
    """
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


def start_scheduler():
    """
    Inicia o scheduler automático
    Chamado pelo AppConfig quando o Django sobe
    """
    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")
    
    # Job: Consolidar a cada 15 minutos
    scheduler.add_job(
        consolidar_turnos_automatico,
        trigger=IntervalTrigger(minutes=15),
        id="consolidar_turnos",
        max_instances=1,
        replace_existing=True,
        name="Consolidar turnos automaticamente"
    )
    
    # Job: Limpar execuções antigas (1x por dia)
    scheduler.add_job(
        delete_old_job_executions,
        trigger=IntervalTrigger(days=1),
        id="limpar_jobs_antigos",
        max_instances=1,
        replace_existing=True,
        name="Limpar jobs antigos"
    )
    
    try:
        logger.info("[SCHEDULER] Iniciando scheduler automático...")
        scheduler.start()
        logger.info("[SCHEDULER] ✓ Scheduler ativo - Consolidação a cada 15min")
    except Exception as e:
        logger.error(f"[SCHEDULER] Erro ao iniciar: {e}")
        scheduler.shutdown()
