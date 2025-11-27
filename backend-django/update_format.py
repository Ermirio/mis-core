import os
import sys
import django

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from equipamentos.models import Equipamento, TagColeta

def update_format_value():
    print("--- UPDATING FORMAT VALUE ---")
    
    # Find ACMA (which had 500g)
    acma = Equipamento.objects.filter(nome__icontains="ACMA").first()
    if not acma:
        print("ACMA not found.")
        return

    tags = acma.tags_coleta.filter(formato__gt=0)
    if tags.exists():
        for tag in tags:
            print(f"Updating tag {tag.nome_metrica} from {tag.formato} to 2200.0")
            tag.formato = 2200.0
            tag.save()
            print("Updated.")
    else:
        print("No format tag found on ACMA to update.")

if __name__ == "__main__":
    update_format_value()
