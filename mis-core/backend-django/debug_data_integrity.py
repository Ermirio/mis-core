import requests
import json
import sys

BASE_URL = "http://localhost:3000"

def check_endpoint(name, url):
    print(f"\n--- Checking {name} ---")
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            # Se for lista, pega o primeiro item para exemplo
            if isinstance(data, list) and len(data) > 0:
                print(f"Data Type: List [{len(data)} items]")
                print(json.dumps(data[0], indent=2))
            else:
                print(json.dumps(data, indent=2))
            return data
        else:
            print(f"Error {r.status_code}: {r.text}")
    except Exception as e:
        print(f"Exception: {e}")

# 1. Checar FLask Operacao para E001 (ACMA) e E002 (Zuchinni - provavel)
d1 = check_endpoint("Flask ACMA (E001)", f"{BASE_URL}/flask-api/operacao/dados/E001")
d2 = check_endpoint("Flask ZUCHINNI (E002)", f"{BASE_URL}/flask-api/operacao/dados/E002")

# 2. Checar Metricas Consolidadas (Django)
d3 = check_endpoint("Django Consolidated", f"{BASE_URL}/mis-core/metricas_fabrica_consolidadas/")

# 3. Analise de Discrepancia
print("\n=== ANALISE DE INTEGRIDADE ===")
if d1:
    print(f"ACMA (E001):")
    print(f"  Produzido OP: {d1.get('produzido_op')} (Bruto)")
    print(f"  Pecas Ruins: {d1.get('pecas_ruins')} (Bruto)")
    print(f"  Pecas Boas: {d1.get('pecas_boas')} (Calc)")
    print(f"  Toneladas OP: {d1.get('toneladas_op')}")
    print(f"  Formato: {d1.get('formato_gramas')}")

if d2:
    print(f"ZUC (E002):")
    print(f"  Produzido OP: {d2.get('produzido_op')} (Bruto)")
    print(f"  Pecas Ruins: {d2.get('pecas_ruins')} (Bruto)")
    print(f"  Pecas Boas: {d2.get('pecas_boas')} (Calc)")
    print(f"  Toneladas OP: {d2.get('toneladas_op')}")
    print(f"  Formato: {d2.get('formato_gramas')}")
