import os
import django
from django.conf import settings

# Configuração do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from equipamentos.models import Equipamento

def list_tags():
    try:
        eq = Equipamento.objects.get(codigo='003')
        print(f"Tags para {eq.nome} ({eq.codigo}):")
        for tag in eq.tags_coleta.all():
            print(f" - Nome: '{tag.nome_metrica}', Node: {tag.node_id}, Tipo: {tag.tipo_dado}")
            
    except Equipamento.DoesNotExist:
        print("Equipamento 003 não encontrado")

if __name__ == '__main__':
    list_tags()
