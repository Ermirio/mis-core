from django.apps import AppConfig



class IpsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ips'
    verbose_name = 'MIS'

    def ready(self):
        from django.contrib.admin import AdminSite
        AdminSite.site_header = "Digital Factory Admin"
        AdminSite.site_title = "Digital Factory Portal"
        AdminSite.index_title = "Bem-vindo ao Digital Factory Admin"

        import os
        import sys

        # Pula comandos de gestão que não devem iniciar o worker OPC
        _SKIP_CMDS = {'migrate', 'makemigrations', 'collectstatic', 'shell', 'test', 'check', 'showmigrations'}
        _is_mgmt_cmd = any(c in _SKIP_CMDS for c in sys.argv)

        # No dev-server do Django, ready() é chamado duas vezes (reloader + main).
        # RUN_MAIN=='true' identifica o processo principal do dev-server.
        _is_dev_reload = 'runserver' in sys.argv and os.environ.get('RUN_MAIN') != 'true'

        if not _is_mgmt_cmd and not _is_dev_reload:
            try:
                from .services import start_opc_service
                start_opc_service()
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Erro ao iniciar OPC Worker: {e}")