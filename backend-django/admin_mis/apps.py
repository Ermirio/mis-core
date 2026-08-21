from django.apps import AppConfig


class AdminMisConfig(AppConfig):
    """Aplicação que sobrescreve o frontend do Django admin com a identidade
    visual ISA-101 do MIS Core.

    Não registra modelos. Apenas templates e static files.
    Precisa estar listado em INSTALLED_APPS ANTES de django.contrib.admin
    para que o template loader ache `admin/base.html` deste app primeiro.
    """

    name = 'admin_mis'
    verbose_name = 'MIS Admin (skin)'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # Aplica os títulos do admin lendo do settings.
        from django.conf import settings
        from django.contrib import admin

        admin.site.site_header = getattr(settings, 'ADMIN_SITE_HEADER', 'MIS Core — Backend')
        admin.site.site_title = getattr(settings, 'ADMIN_SITE_TITLE', 'MIS Core Admin')
        admin.site.index_title = getattr(settings, 'ADMIN_INDEX_TITLE', 'Painel de gestão')
