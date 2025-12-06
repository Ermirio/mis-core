import requests
import time
import json
import random

# Configuration
BASE_URL = "http://localhost:5005/api"
LINE_CODE = "L01"
EQUIPMENT_CODE = "L01_Enchedora"

def inject_data(counter, speed=100, format_g=500):
    payload = {
        "equipamento_codigo": EQUIPMENT_CODE,
        "linha_codigo": LINE_CODE,
        "timestamp": time.time(),
        "medicoes": {
            "estado_maquina": 1, # Produzindo
            "velocidade_atual": speed,
            "contagem_saida": counter,
            "descarte": 0,
            "formato_gramas": format_g,
            "ordem_producao": "OP-DEBUG-001",
            "sku_codigo": "SKU-DEBUG-001",
            "planejado_op": 10000
        }
    }
    
    try:
        print(f"Injecting: Speed={speed}, Format={format_g}g, Counter={counter}...", end=" ")
        resp = requests.post(f"{BASE_URL}/dados/inserir", json=payload, timeout=2)
        if resp.status_code == 200:
            print("OK")
            data = resp.json()
            if 'data' in data:
                print(f"  Response: Turno={data['data'].get('turno_atual_nome')}, "
                      f"AccOp={data['data'].get('producao_op')}, "
                      f"AccShift={data['data'].get('producao_turno')}, "
                      f"Tons={data['data'].get('toneladas_turno')}")
            return True
        else:
            print(f"FAILED ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def check_realtime_metrics():
    try:
        print(f"Checking Realtime Metrics for {LINE_CODE}...", end=" ")
        resp = requests.get(f"{BASE_URL}/linha/{LINE_CODE}/realtime", timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            print("OK")
            print(json.dumps(data, indent=2))
            return data
        else:
            print(f"FAILED ({resp.status_code})")
            return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None

def check_factory_map():
    try:
        print(f"Checking Factory Map...", end=" ")
        resp = requests.get(f"{BASE_URL}/fabrica/mapa", timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            print("OK")
            
            # Find our line
            line_data = None
            if isinstance(data, list):
                line_data = next((l for l in data if l.get('linha') == LINE_CODE), None)
            elif isinstance(data, dict) and 'linhas' in data:
                 line_data = next((l for l in data['linhas'] if l.get('linha') == LINE_CODE), None)

            if line_data:
                print(f"Line {LINE_CODE} Data:")
                print(json.dumps(line_data, indent=2))
            else:
                print(f"Line {LINE_CODE} not found in map data!")
                
            if isinstance(data, dict):
                print("Factory Totals:")
                print(f"  Produção Real: {data.get('producao_real_t')}")
                print(f"  Vazão Total: {data.get('vazao_total_tph')}")
            else:
                print("Factory Totals: Not available in list format")
            
            return data
        else:
            print(f"FAILED ({resp.status_code})")
            return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None

def main():
    print("=== DEBUG DATA FLOW ===")
    
    # 1. Inject a sequence of data to simulate production
    # We need to inject enough points to calculate a delta
    current_counter = 1000
    
    for i in range(5):
        inject_data(current_counter, speed=120, format_g=500)
        current_counter += 10 # 10 units per iteration
        time.sleep(1) # Wait a bit
        
    # 2. Check APIs
    print("\n--- Verifying APIs ---")
    check_realtime_metrics()
    check_factory_map()
    
    print("\n=== DONE ===")

if __name__ == "__main__":
    main()
