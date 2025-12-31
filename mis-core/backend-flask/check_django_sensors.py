import requests
from decouple import config

DJANGO_API = "http://django:8000/api"

def check_sensors():
    try:
        url = f"{DJANGO_API}/linhas/"
        print(f"Fetching from {url}...")
        res = requests.get(url)
        if not res.ok:
            print(f"Error: {res.status_code}")
            return
            
        linhas = res.json()
        if 'results' in linhas: linhas = linhas['results']
        
        for l in linhas:
            print(f"\nLinha: {l['nome']}")
            for eq in l['equipamentos']:
                print(f"  Equipamento: {eq['nome']} ({eq['codigo']})")
                
                # Check sensors in equipment or fetch via endpoint if not detailed
                # The frontend uses /linhas/ and expects nested sensors? 
                # Let's check if 'sensores' key exists
                if 'sensores' in eq:
                    for s in eq['sensores']:
                         print(f"    - Sensor: {s['nome']} | Tag: {s['tag_influxdb']}")
                else:
                    print("    (No sensors nested, checking separate endpoint...)")
                    # Try fetching sensors for this eq
                    s_url = f"{DJANGO_API}/sensores/?equipamento={eq['id']}"
                    s_res = requests.get(s_url)
                    if s_res.ok:
                        sensors = s_res.json()
                        if 'results' in sensors: sensors = sensors['results']
                        for s in sensors:
                            print(f"    - Sensor: {s['nome']} | Tag: {s['tag_influxdb']}")

    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    check_sensors()
