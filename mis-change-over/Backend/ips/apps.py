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