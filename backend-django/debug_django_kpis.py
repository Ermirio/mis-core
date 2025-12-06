import os
import sys
import django
from django.utils import timezone
from django.db.models import Sum

# Setup Django environment
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from equipamentos.models import LinhaProducao, CalendarioProducao, TurnoProducao
from equipamentos.turno_helpers import obter_turno_atual, calcular_inicio_turno
from equipamentos.views import FactoryProductionView

def debug_kpis():
    print("=== DEBUG FACTORY KPIS ===")
    
    # 1. Check Active Shift
    turno = obter_turno_atual()
    print(f"Turno Atual: {turno}")
    
    if not turno:
        print("WARNING: No active shift found! This will cause 0 planned production.")
        # List all shifts
        print("Available Shifts:")
        for t in TurnoProducao.objects.all():
            print(f"  - {t.nome} ({t.inicio} - {t.fim}) Ativo: {t.ativo}")
            
    # 2. Check CalendarioProducao for Today
    now = timezone.localtime(timezone.now())
    today = now.date()
    print(f"Date: {today}")
    
    agendamentos = CalendarioProducao.objects.filter(data=today)
    print(f"Calendario Entries for Today: {agendamentos.count()}")
    
    total_meta = 0
    for a in agendamentos:
        print(f"  - Linha: {a.linha.codigo}, Turno: {a.turno.nome}, Meta: {a.meta_producao_turno} (Prog: {a.programado})")
        if a.programado and (not turno or a.turno == turno):
            total_meta += a.meta_producao_turno
            
    print(f"Total Meta Calculated (Manual): {total_meta}")
    
    # 3. Check Lines Configuration (Fallback)
    print("Lines Configuration:")
    for linha in LinhaProducao.objects.filter(ativa=True):
        print(f"  - {linha.codigo}: Meta Turno={linha.meta_producao_turno}")

    # 4. Simulate View Logic
    print("\n=== SIMULATING VIEW LOGIC ===")
    try:
        # Mock request
        from rest_framework.request import Request
        from django.http import HttpRequest
        
        request = HttpRequest()
        request.GET['granularity'] = 'shift'
        
        # Wrap in DRF Request
        drf_request = Request(request)
        
        view = FactoryProductionView()
        view.request = drf_request
        view.format_kwarg = None
        
        response = view.throughput(drf_request)
        print("API Response Data (Filtered):")
        data = response.data
        print(f"  - Planned Tons: {data.get('planned_tons')}")
        print(f"  - Min Required TPH: {data.get('min_required_tph')}")
        print(f"  - Actual Tons: {data.get('actual_tons')}")
        print(f"  - Actual TPH: {data.get('actual_tph')}")
        print(f"  - Remaining Hours: {data.get('meta', {}).get('hoursRemaining')}")
        
    except Exception as e:
        print(f"Error simulating view: {e}")

if __name__ == "__main__":
    debug_kpis()
