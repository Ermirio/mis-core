import logging
from datetime import timedelta

from decouple import config
from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import GoldenStateRun, MetricaProducao, TurnoProducao, UserAccessPolicy

logger = logging.getLogger(__name__)

GOLDEN_AUTO_SCORE_MIN = int(config('GOLDEN_AUTO_SCORE_MIN', default=80))


@receiver([post_save, post_delete], sender=TurnoProducao)
def recarregar_engine_mudanca_turno(sender, instance, **kwargs):
    """Refresh the in-process ingestion engine after shift changes."""
    try:
        from .flask_replacement_views import _get_production_engine

        _get_production_engine().recarregar_configuracoes()
        logger.info("Engine de ingestao recarregado apos mudanca no turno: %s", instance.nome)
    except Exception as exc:
        logger.warning("Falha ao recarregar engine de ingestao apos mudanca no turno: %s", exc)


@receiver(post_save, sender=MetricaProducao)
def auto_capturar_golden_state(sender, instance: MetricaProducao, created, **kwargs):
    """Capture a Golden State run when a line shift closes with high OEE."""
    if instance.periodo != 'TURNO':
        return
    if instance.equipamento_id is not None:
        return

    oee = float(instance.oee or 0)
    if oee < GOLDEN_AUTO_SCORE_MIN:
        return

    fim = instance.data_hora
    inicio = fim - timedelta(hours=8)

    from .golden_state_views import _capturar_run, _golden_variables

    if not _golden_variables(instance.linha):
        return

    try:
        _capturar_run(
            instance.linha,
            inicio,
            fim,
            fonte=GoldenStateRun.Fonte.AUTO,
            nome=f"Turno {fim.strftime('%d/%m %H:%M')} (auto)",
            sku_codigo=None,
            observacoes=f"Detectado automaticamente - OEE {oee:.1f}%",
            criado_por='sistema',
        )
        logger.info("Golden State AUTO capturado para %s (OEE %.1f%%)", instance.linha.codigo, oee)
    except Exception as exc:
        if 'unique' in str(exc).lower() or 'duplicate' in str(exc).lower():
            logger.debug("AUTO ja existia para %s; ignorando.", instance.linha.codigo)
        else:
            logger.warning("Falha ao auto-capturar Golden State: %s", exc)


@receiver(post_save, sender=get_user_model())
def maintain_user_access_policy(sender, instance, **kwargs):
    policy, _ = UserAccessPolicy.objects.get_or_create(user=instance)
    if (instance.is_staff or instance.is_superuser) and policy.expires_at is not None:
        policy.expires_at = None
        policy.save(update_fields=['expires_at', 'updated_at'])
