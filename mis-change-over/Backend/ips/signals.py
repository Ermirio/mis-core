"""
Signals do app ips.

ContaUsuarioExpiracao: cria automaticamente o registro de validade quando um
usuário comum (não-superuser) é criado. Superusers nunca expiram, então não
ganham registro.
"""
import logging
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def criar_expiracao_usuario(sender, instance, created, **kwargs):
    """
    Ao criar um usuário NÃO-superuser, cria a ContaUsuarioExpiracao com
    validade de 5 meses. Idempotente: usa get_or_create.

    Importado tardiamente para evitar problemas de app loading.
    """
    if not created:
        return
    if instance.is_superuser:
        return
    try:
        from .models import ContaUsuarioExpiracao
        ContaUsuarioExpiracao.objects.get_or_create(
            user=instance,
            defaults={
                'validade_ate': timezone.now() + timedelta(
                    days=ContaUsuarioExpiracao.VALIDADE_DIAS
                ),
            },
        )
    except Exception as e:
        # Não bloquear a criação do usuário se algo falhar aqui.
        logger.warning("Falha ao criar ContaUsuarioExpiracao para %s: %s",
                       instance.username, e)
