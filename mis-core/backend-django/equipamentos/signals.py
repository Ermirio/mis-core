# equipamentos/signals.py
import requests
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from decouple import config
from .models import TurnoProducao

logger = logging.getLogger(__name__)

# URL do Flask (deve ser a mesma que você usa no coletor)
FLASK_API_URL = config('FLASK_API_URL', default='http://127.0.0.1:5000/api')

@receiver([post_save, post_delete], sender=TurnoProducao)
def notificar_flask_mudanca_turno(sender, instance, **kwargs):
    """
    Sempre que um Turno for Criado, Editado ou Deletado,
    avisa o Flask para recarregar a configuração imediatamente.
    """
    webhook_url = f"{FLASK_API_URL}/system/refresh-shifts"
    
    try:
        logger.info(f"📢 Notificando Flask sobre alteração no turno: {instance.nome}")
        # Timeout curto (1s) para não travar o Django se o Flask estiver fora
        response = requests.post(webhook_url, timeout=1)
        
        if response.status_code == 200:
            logger.info("✅ Flask atualizado com sucesso!")
        else:
            logger.warning(f"⚠️ Flask respondeu com erro: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        logger.warning("❌ Não foi possível conectar ao Flask (Ele pode estar desligado).")
    except Exception as e:
        logger.error(f"❌ Erro ao notificar Flask: {e}")