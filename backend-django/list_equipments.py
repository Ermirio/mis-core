import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from equipamentos.models import Equipamento

print("--- LISTA DE EQUIPAMENTOS ---")
equipamentos = Equipamento.objects.all()

for eq in equipamentos:
    print(f"ID: {eq.id} | Nome: '{eq.nome}' | Código: '{eq.codigo}'")
