"""
Comando: python manage.py expirar_contas

Desativa contas de usuários comuns expiradas (inatividade 60d ou validade 5m).
Pode ser agendado via cron, alternativa ao worker diário do apps.py.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Desativa contas de usuários comuns expiradas (inatividade/validade)."

    def handle(self, *args, **options):
        from ips.services import expirar_contas_vencidas
        desativados = expirar_contas_vencidas()
        if not desativados:
            self.stdout.write(self.style.SUCCESS("Nenhuma conta expirada."))
            return
        for username, motivo in desativados:
            self.stdout.write(self.style.WARNING(f"  {username}: desativado por {motivo}"))
        self.stdout.write(self.style.SUCCESS(f"{len(desativados)} conta(s) desativada(s)."))
