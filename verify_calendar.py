import json
import urllib.request
import urllib.error
import datetime

API_BASE = "http://127.0.0.1:8001/api"

def get_first_id(endpoint):
    url = f"{API_BASE}/{endpoint}/"
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            results = data.get('results', data)
            if results and len(results) > 0:
                print(f"Found {endpoint}: {results[0]['id']} - {results[0].get('nome', 'N/A')}")
                return results[0]['id']
            else:
                print(f"No {endpoint} found on {url}")
                return None
    except Exception as e:
        print(f"Error fetching {endpoint}: {e}")
        return None

def verify_calendar_creation():
    print("--- Verifying Calendar Creation ---")
    
    linha_id = get_first_id("linhas")
    turno_id = get_first_id("turnos")

    if not linha_id or not turno_id:
        print("Skipping test: Missing prerequisites (Linhas or Turnos)")
        return

    # Payload matching Frontend structure
    payload = {
        "data": datetime.date.today().isoformat(),
        "linha": linha_id,
        "turno": turno_id,
        "programado": True,
        "meta_producao_turno": 100,
        "observacoes": "Teste automatizado via Agent"
    }

    url = f"{API_BASE}/calendario/"
    req = urllib.request.Request(url, method="POST")
    req.add_header('Content-Type', 'application/json')
    
    try:
        data_json = json.dumps(payload).encode()
        with urllib.request.urlopen(req, data=data_json) as response:
            print(f"POST {url} status: {response.status}")
            if response.status in [200, 201]:
                resp_data = json.loads(response.read().decode())
                print("Success! Created Entry ID:", resp_data.get('id'))
                print("Response:", json.dumps(resp_data, indent=2))
                return True
            else:
                print("Failed with status:", response.status)
                print(response.read().decode())
                return False

    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        print(e.read().decode())
        return False
    except Exception as e:
        print(f"Error Posting: {e}")
        return False

if __name__ == "__main__":
    verify_calendar_creation()
