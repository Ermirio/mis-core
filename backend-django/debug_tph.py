import os
import django
from django.conf import settings
from django.utils import timezone
import pytz
from datetime import datetime
from django.db.models import Sum

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from equipamentos.models import CalendarioProducao, TurnoProducao, RegistroProducaoTurno, LinhaProducao
from equipamentos.turno_helpers import obter_turno_atual, calcular_inicio_turno
from equipamentos.utils import get_window, calculate_time_metrics
from equipamentos.influx_helpers import get_realtime_metrics

def debug_tph():
    print("\n=== DEBUG TPH CALCULATION ===")
    
    now = timezone.localtime(timezone.now())
    print(f"Now: {now}")
    
    # 1. Window
    start_time, end_time = get_window('shift', now)
    print(f"Window: {start_time} -> {end_time}")
    
    elapsed_hours, hours_remaining = calculate_time_metrics(start_time, end_time, now)
    print(f"Elapsed Hours: {elapsed_hours}")
    print(f"Hours Remaining: {hours_remaining}")
    
    # 2. Actual Tons
    actual_tons = 0.0
    turno_atual = obter_turno_atual()
    
    if turno_atual:
        print(f"Turno Atual: {turno_atual}")
        linhas = LinhaProducao.objects.filter(ativa=True)
        for linha in linhas:
            equipamento = linha.equipamentos.filter(tipo__in=['PALETIZADOR', 'ENCHEDORA', 'ROTULADORA']).last()
            if not equipamento:
                equipamento = linha.equipamentos.last()
            
            if equipamento:
                tag_formato = equipamento.tags_coleta.filter(nome_metrica='formato').first()
                formato = float(tag_formato.formato) if tag_formato and tag_formato.formato else 1.0
                
                print(f"Querying Influx for {equipamento.codigo}...")
                metrics = get_realtime_metrics(equipamento.codigo, formato, calcular_inicio_turno(turno_atual))
                
                ton = metrics.get('toneladas_turno', 0)
                vazao_inst = metrics.get('vazao_ton_hora', 0)
                
                print(f"  - {equipamento.codigo}: Tons={ton}, VazaoInst={vazao_inst}")
                actual_tons += ton

    print(f"Total Actual Tons: {actual_tons}")
    
    # 3. TPH
    actual_tph = actual_tons / elapsed_hours if elapsed_hours > 0 else 0
    print(f"Calculated Average TPH: {actual_tph}")
    
    print("=== END DEBUG ===")

if __name__ == "__main__":
    debug_tph()
