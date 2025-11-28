import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from equipamentos.models import Equipamento, TagColeta

print("--- CORREÇÃO DE TIPOS DE TAGS ---")
equipamento = Equipamento.objects.filter(nome__icontains='ACMA').first()

if equipamento:
    print(f"Equipamento: {equipamento.nome}")
    
    # Update Formato to INT
    tag_formato = equipamento.tags_coleta.filter(nome_metrica='formato').first()
    if tag_formato:
        print(f"  [FORMATO] Atual: {tag_formato.tipo_dado}")
        tag_formato.tipo_dado = 'INT'
        tag_formato.save()
        print(f"  [FORMATO] Novo: {tag_formato.tipo_dado} (Atualizado para Inteiro)")
    
    # Ensure Planejado OP is active
    tag_planejado = equipamento.tags_coleta.filter(nome_metrica='planejado_op').first()
    if tag_planejado:
         print(f"  [PLANEJADO] Tipo: {tag_planejado.tipo_dado} (OK)")
