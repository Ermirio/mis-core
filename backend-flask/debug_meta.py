import requests
import logging
from datetime import datetime
from production_engine import ShiftManager

# Config
DJANGO_API_URL = "http://127.0.0.1:8000/api"
LINHA_NOME = "L01"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_meta():
    print(f"--- Debugging Meta for {LINHA_NOME} ---")
    
    # 1. Shift Manager
    print("\n1. Testing ShiftManager...")
    sm = ShiftManager(DJANGO_API_URL)
    turno_info = sm.get_turno_info()
    print(f"Shift Info: {turno_info}")
    
    # 2. Get Line ID
    print(f"\n2. Fetching Line ID for code='{LINHA_NOME}'...")
    try:
        resp_linha = requests.get(f"{DJANGO_API_URL}/linhas/?codigo={LINHA_NOME}", timeout=2)
        print(f"Status: {resp_linha.status_code}")
        data_linha = resp_linha.json()
        results_linha = data_linha.get('results', data_linha)
        print(f"Line Results: {results_linha}")
        
        if not results_linha:
            print("ERROR: Line not found!")
            return

        linha_id = results_linha[0]['id']
        print(f"Line ID: {linha_id}")
        
        # 3. Get Calendar
        # Simulate routes.py logic: Use shift start date
        if turno_info and 'inicio_timestamp' in turno_info:
             dt_inicio = datetime.fromtimestamp(turno_info['inicio_timestamp'])
             query_date = dt_inicio.strftime('%Y-%m-%d')
        else:
             query_date = datetime.now().strftime('%Y-%m-%d')

        print(f"\n3. Fetching Calendar for line_id={linha_id} date={query_date} (Current Time: {datetime.now()})...")
        resp_cal = requests.get(f"{DJANGO_API_URL}/calendario/?linha_id={linha_id}&data={query_date}", timeout=2)
        print(f"Status: {resp_cal.status_code}")
        data_cal = resp_cal.json()
        results_cal = data_cal.get('results', data_cal)
        print(f"Calendar Results: {results_cal}")
        
        if not results_cal:
            print("WARNING: No calendar entries found.")
        
        # 4. Logic Simulation
        print("\n4. Simulating Logic...")
        meta_toneladas = 0.0
        
        for entry in results_cal:
            print(f"Checking entry: {entry}")
            if entry.get('programado') and entry.get('meta_producao_turno'):
                val = float(entry.get('meta_producao_turno'))
                if val > 1000: val /= 1000.0
                print(f"  -> Found valid target: {val}t (Shift: {entry.get('turno_nome')})")
                
                # Match Shift
                if turno_info and entry.get('turno_nome') == turno_info.get('nome'):
                    print("  -> MATCHED Current Shift!")
                    meta_toneladas = val
                    break
                else:
                    print(f"  -> Did not match current shift '{turno_info.get('nome') if turno_info else 'None'}'")
                
                # Fallback
                if meta_toneladas == 0:
                    print("  -> Setting as Fallback")
                    meta_toneladas = val
        
        print(f"\nFINAL RESULT: meta_toneladas = {meta_toneladas}")

    except Exception as e:
        print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    debug_meta()
