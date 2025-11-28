import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from equipamentos.models import Equipamento, TagColeta

print("--- VERIFICAÇÃO DE TAGS (FORMATO E PLANEJADO_OP) ---")
equipamentos = Equipamento.objects.filter(linha__id=1)

for eq in equipamentos:
    print(f"\nEquipamento: {eq.nome}")
    
    # Check Formato Tag
    tag_formato = eq.tags_coleta.filter(nome_metrica='formato').first()
    if tag_formato:
        print(f"  [FORMATO] Tipo: {tag_formato.tipo_dado}, Node: {tag_formato.node_id}")
    else:
        print("  [FORMATO] ❌ Tag não encontrada")

    # Check Planejado OP Tag
    tag_planejado = eq.tags_coleta.filter(nome_metrica='planejado_op').first()
    if tag_planejado:
        print(f"  [PLANEJADO] Tipo: {tag_planejado.tipo_dado}, Node: {tag_planejado.node_id}")
    else:
        print("  [PLANEJADO] ❌ Tag não encontrada")
