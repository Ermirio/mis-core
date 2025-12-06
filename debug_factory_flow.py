import requests
import json
import time

FLASK_URL = "http://localhost:5005/api"
DJANGO_URL = "http://localhost:8001/api"

def check_factory_kpis():
    print("\n=== FLASK FACTORY KPIS ===")
    try:
        resp = requests.get(f"{FLASK_URL}/fabrica/kpis", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f"Vazão Total (tph): {data.get('vazao_total_tph')}")
            print(f"Produção Real (t): {data.get('producao_real_t')}")
            
            lines = data.get('linhas', [])
            for line in lines:
                tph = line.get('tph_real', 0)
                if tph > 0:
                    print(f"Line {line.get('linha')}: {tph} tph (Status: {line.get('status')})")
        else:
            print(f"FAILED ({resp.status_code})")
    except Exception as e:
        print(f"ERROR: {e}")

def check_django_metrics():
    print("\n=== DJANGO CONSOLIDATED METRICS ===")
    try:
        resp = requests.get(f"{DJANGO_URL}/metricas_fabrica_consolidadas/", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            # It returns a list of lines
            for line in data:
                name = line.get('linha_nome') or line.get('linha_codigo')
                if 'L01' in name or 'Linha 01' in name:
                    vazao = line.get('vazao_real_ton_hora')
                    ton = line.get('toneladas_produzidas')
                    print(f"Line {name}: Vazão={vazao} tph, Toneladas={ton} t")
                    print(json.dumps(line, indent=2))
        else:
            print(f"FAILED ({resp.status_code}) - {resp.text}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    check_factory_kpis()
    check_django_metrics()
