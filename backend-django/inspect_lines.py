import os
import django
from django.conf import settings
from django.db.models import Sum

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from equipamentos.models import LinhaProducao, CalendarioProducao
from equipamentos.turno_helpers import obter_turno_atual
from django.utils import timezone

def inspect_lines():
    print("\n=== INSPECT LINES ===")
    
    # 1. Active Lines
    linhas = LinhaProducao.objects.filter(ativa=True)
    print(f"Active Lines: {linhas.count()}")
    for l in linhas:
        print(f"  - {l.codigo} (ID: {l.id})")
        
    # 2. Calendario Duplicates?
    now = timezone.localtime(timezone.now())
    turno = obter_turno_atual()
    
    if turno:
        print(f"\nTurno Atual: {turno.nome}")
        cals = CalendarioProducao.objects.filter(
            data=now.date(),
            turno=turno,
            programado=True
        )
        print(f"Calendario Entries (Shift): {cals.count()}")
        total = 0
        for c in cals:
            print(f"  - Line {c.linha.codigo}: {c.meta_producao_turno} kg")
            total += c.meta_producao_turno
        print(f"Total Planned (Shift): {total} kg")
        
    # 3. Day Total
    cals_day = CalendarioProducao.objects.filter(
        data=now.date(),
        programado=True
    )
    print(f"\nCalendario Entries (Day): {cals_day.count()}")
    total_day = 0
    for c in cals_day:
        print(f"  - Line {c.linha.codigo} ({c.turno.nome}): {c.meta_producao_turno} kg")
        total_day += c.meta_producao_turno
    print(f"Total Planned (Day): {total_day} kg")

    print("=== END ===")

if __name__ == "__main__":
    inspect_lines()
