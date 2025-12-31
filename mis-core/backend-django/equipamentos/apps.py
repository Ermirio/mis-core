# -*- coding: utf-8 -*-
"""
Django App Configuration for Equipamentos

Inicializa o scheduler de sincronização de OPs automaticamente
quando o Django inicia.
"""

from django.apps import AppConfig
import threading
import time
import logging

logger = logging.getLogger(__name__)


class EquipamentosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'equipamentos'
    verbose_name = 'Equipamentos e Produção'

    def ready(self):
        """
        Executado quando o Django termina de carregar o app.
        Inicia o scheduler de sincronização em background.
        """
        # Evita iniciar o scheduler duas vezes (Django recarrega em desenvolvimento)
        import os
        if os.environ.get('RUN_MAIN') != 'true':
            return
        
        logger.info("[SCHEDULER] Iniciando scheduler de sincronização de OPs...")
        
        # Inicia thread do scheduler
        scheduler_thread = threading.Thread(
            target=self.run_scheduler,
            daemon=True,  # Thread morre quando Django para
            name='OPSyncScheduler'
        )
        scheduler_thread.start()
        
        logger.info("[SCHEDULER] ✓ Scheduler iniciado em background")

    def run_scheduler(self):
        """
        Loop do scheduler que roda a cada 5 minutos.
        """
        from influxdb import InfluxDBClient
        from decimal import Decimal
        from decouple import config
        from equipamentos.models import OrdemProducao
        
        # Configurações InfluxDB
        INFLUX_HOST = config('INFLUXDB_HOST', default='127.0.0.1')
        INFLUX_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
        INFLUX_DB = config('INFLUXDB_DATABASE', default='industrial_db')
        INFLUX_USER = config('INFLUXDB_USER', default=None)
        INFLUX_PASS = config('INFLUXDB_USER_PASSWORD', default=None)
        
        SYNC_INTERVAL = 300  # 5 minutos
        
        # Aguarda 30s para Django terminar de inicializar
        time.sleep(30)
        
        while True:
            try:
                logger.info("[SCHEDULER] Executando sincronização de OPs...")
                
                # Conectar ao InfluxDB
                client = InfluxDBClient(
                    host=INFLUX_HOST,
                    port=INFLUX_PORT,
                    username=INFLUX_USER,
                    password=INFLUX_PASS,
                    database=INFLUX_DB
                )
                
                # Buscar OPs em produção
                ops = OrdemProducao.objects.filter(status='PRODUZINDO')
                
                if ops.count() == 0:
                    logger.info("[SCHEDULER] Nenhuma OP em produção para sincronizar")
                else:
                    synced_count = 0
                    
                    for op in ops:
                        try:
                            # Buscar último valor no InfluxDB
                            query = f'''
                                SELECT last("producao_acumulada_op") as final_value
                                FROM "producao" 
                                WHERE "ordem_producao" = '{op.codigo}'
                            '''
                            
                            result = client.query(query)
                            points = list(result.get_points())
                            
                            if points and points[0].get('final_value') is not None:
                                influx_value = Decimal(str(points[0]['final_value']))
                                current_value = op.producao_realizada or Decimal(0)
                                
                                # Atualizar se diferente (margem de 0.001 ton)
                                if abs(influx_value - current_value) > Decimal('0.001'):
                                    op.producao_realizada = influx_value
                                    op.save()
                                    logger.info(f"[SCHEDULER] OP {op.codigo}: {current_value:.3f} -> {influx_value:.3f} ton")
                                    synced_count += 1
                                    
                        except Exception as e:
                            logger.error(f"[SCHEDULER ERROR] OP {op.codigo}: {e}")
                    
                    if synced_count > 0:
                        logger.info(f"[SCHEDULER] ✓ {synced_count} OPs sincronizadas")
                logger.info("[SCHEDULER] Sincronização concluída")
                
                client.close()
                
            except Exception as e:
                logger.error(f"[SCHEDULER] Erro na sincronização: {e}")
            
            # ===== CONSOLIDAÇÃO AUTOMÁTICA (NOVO) =====
            # Consolida dados do InfluxDB para MySQL a cada 5 minutos
            try:
                logger.info("[CONSOLIDAÇÃO] Iniciando consolidação horária...")
                
                from django.core.management import call_command
                
                # Consolida última hora
                call_command('consolidar_metricas', '--periodo', 'HORA', '--horas', '1')
                
                logger.info("[CONSOLIDAÇÃO] Consolidação horária concluída")
                
            except Exception as e:
                logger.error(f"[CONSOLIDAÇÃO] Erro na consolidação: {e}")
            
            # Aguarda 5 minutos antes da próxima execução
            time.sleep(SYNC_INTERVAL)