from django.apps import AppConfig
import os
import logging
from threading import Thread
import time

logger = logging.getLogger('EquipamentosApp')


class EquipamentosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'equipamentos'
    
    def ready(self):
        """Executado quando o Django carrega o app"""
        # Evita execução dupla durante reload do development server
        if os.environ.get('RUN_MAIN') != 'true':
            return
        
        logger.info("🔧 Equipamentos App iniciado")
        
        # Inicia o scheduler de consolidação automática
        try:
            from .schedulers import start_scheduler
            start_scheduler()
            logger.info("✅ Scheduler de consolidação automática iniciado")
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar scheduler: {e}")

    
    def start_agregador_thread(self):
        """Inicia thread do agregador em background"""
        def run_agregador_loop():
            # Importar aqui para evitar circular imports
            from equipamentos.agregador_service import agregar_tudo
            
            logger.info("🚀 Agregador automático iniciado")
            logger.info("⏰ Executará a cada 1 hora")
            
            # Aguardar 30 segundos antes da primeira execução
            time.sleep(30)
            
            while True:
                try:
                    logger.info("="*60)
                    logger.info("🔄 Executando agregação automática...")
                    resultado = agregar_tudo()
                    logger.info(f"✅ Agregação concluída: {resultado}")
                except Exception as e:
                    logger.error(f"❌ Erro na agregação: {e}", exc_info=True)
                
                # Aguardar 1 hora (3600 segundos)
                logger.info("😴 Próxima execução em 1 hora...")
                time.sleep(3600)
        
        # Criar thread daemon (morre quando processo principal morre)
        thread = Thread(target=run_agregador_loop, daemon=True, name="AgregadorThread")
        thread.start()
        logger.info("✅ Thread do agregador iniciada")