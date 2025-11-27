import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from equipamentos.models import Equipamento
from equipamentos.agregador import AgregadorDados

def trigger_sync():
    print("Triggering sync...")
    agregador = AgregadorDados()
    
    # Get equipment 003
    eq = Equipamento.objects.get(codigo='003')
    print(f"Equipamento: {eq}")
    
    # Run calculation for current hour
    now = django.utils.timezone.now()
    print(f"Running calculation for {now}")
    agregador.calcular_metricas_hora(eq, now)
    
    print("Sync triggered.")

if __name__ == "__main__":
    trigger_sync()
