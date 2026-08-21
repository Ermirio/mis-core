import requests
import json
from datetime import datetime, timedelta

def test_analytics():
    url = "http://localhost:5000/api/analyze/stats"
    
    # Payload simulating frontend request for Velocidade
    payload = {
        "variables": [
            {
                "tag_influx": "velocidade_atual", 
                "equipamento_code": "E001", 
                "alias": "Velocidade E001"
            },
            {
                "tag_influx": "oee", 
                "equipamento_code": "E001", 
                "alias": "OEE E001"
            }
        ],
        "start_time": (datetime.utcnow() - timedelta(hours=4)).isoformat() + "Z",
        "end_time": datetime.utcnow().isoformat() + "Z"
    }
    
    print(f"Testing {url} with payload...")
    try:
        res = requests.post(url, json=payload)
        print(f"Status: {res.status_code}")
        if res.ok:
            print("Response JSON Sample:")
            print(json.dumps(res.json(), indent=2)[:500] + "...")
        else:
            print(f"Error: {res.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_analytics()
