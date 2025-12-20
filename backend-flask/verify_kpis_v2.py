import requests
import json
from datetime import datetime

API_URL = "http://localhost:5000/api/fabrica/kpis/"

def verify_kpis_v2():
    periods = ['turno', 'dia', 'semana', 'mes']
    
    for period in periods:
        print(f"\n--- Testing Period: {period} ---")
        try:
            response = requests.get(API_URL, params={'period': period})
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                # print(json.dumps(data, indent=2))
                
                # Verify Structure
                expected_keys = [
                    "oee_fabril_real",
                    "oee_fabril_planejado",
                    "producao_real_t",
                    "producao_planejada_t",
                    "vazao_total_tph",
                    "vazao_necessaria_tph",
                    "linhas",
                    "layout_fabrica"
                ]
                
                missing = [k for k in expected_keys if k not in data]
                if missing:
                    print(f"❌ Missing keys: {missing}")
                else:
                    print("✅ Structure OK")
                    
                print(f"  Planned: {data['producao_planejada_t']} t")
                print(f"  Real: {data['producao_real_t']} t")
                print(f"  Required Flow: {data['vazao_necessaria_tph']} t/h")
                
                if data['producao_planejada_t'] >= 0:
                    print("✅ Planned >= 0")
                
                if data['vazao_necessaria_tph'] >= 0:
                     print("✅ Required Flow >= 0")
                
            else:
                print(f"❌ Error: {response.text}")
                
        except Exception as e:
            print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    verify_kpis_v2()
