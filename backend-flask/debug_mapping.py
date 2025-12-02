import requests
from decouple import config
import json

DJANGO_API_URL = config('DJANGO_API_URL', default='http://localhost:8000/api')

def get_primeiro_equipamento_por_linha():
    mapping = {}
    print(f"Fetching lines from {DJANGO_API_URL}/linhas/...")
    try:
        resp = requests.get(f"{DJANGO_API_URL}/linhas/", timeout=3)
        if not resp.ok:
            print(f"Error fetching lines: {resp.status_code}")
            return mapping
        data = resp.json()
        linhas = data.get('results', data) if isinstance(data, dict) else data

        print(f"Found {len(linhas)} lines.")

        for linha in linhas:
            line_code = linha.get('codigo')
            line_id = linha.get('id')
            
            print(f"Processing Line: {line_code} (ID: {line_id})")
            
            if not line_code or not line_id:
                continue

            r_eq = requests.get(
                f"{DJANGO_API_URL}/equipamentos/",
                params={"linha": line_id},
                timeout=3
            )
            if not r_eq.ok:
                print(f"  Error fetching equipments for line {line_id}")
                continue

            eqs_data = r_eq.json()
            eqs_list = eqs_data.get('results', eqs_data) if isinstance(eqs_data, dict) else eqs_data
            
            print(f"  Found {len(eqs_list)} equipments.")

            eqs_ordenados = sorted(
                eqs_list,
                key=lambda x: (x.get('ordem_na_linha') is None, x.get('ordem_na_linha'))
            )
            
            print("  Equipments:")
            for eq in eqs_ordenados:
                print(f"    - {eq.get('codigo')} (ID: {eq.get('id')}, Ordem: {eq.get('ordem_na_linha')})")

            if eqs_ordenados:
                first_eq = eqs_ordenados[0]
                print(f"  First Equipment: {first_eq.get('codigo')} (Ordem: {first_eq.get('ordem_na_linha')})")
                mapping[line_code] = first_eq.get('codigo')
            else:
                print("  No equipments found.")
                
    except Exception as e:
        print(f"Exception: {e}")
        
    return mapping

if __name__ == "__main__":
    mapping = get_primeiro_equipamento_por_linha()
    print("\nFinal Mapping:")
    print(json.dumps(mapping, indent=2))
