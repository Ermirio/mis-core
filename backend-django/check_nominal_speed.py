import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from equipamentos.models import Equipamento

print("--- CONFIGURAÇÃO DE VELOCIDADE NOMINAL ---")
equipamentos = Equipamento.objects.all()

for eq in equipamentos:
    print(f"Nome: '{eq.nome}' | Código: '{eq.codigo}' | Vel. Nominal: {eq.velocidade_nominal}")
