import requests
import time

API_BASE = "http://localhost:5005/api"
EQ_NAME = "KPI_TEST_EQ"

# 1. Get Equipment ID
print(f"Finding Equipment: {EQ_NAME}...")
try:
    res = requests.get(f"{API_BASE}/equipments")
    if res.status_code == 200:
        existing = next((e for e in res.json().get('data', []) if e['name'] == EQ_NAME), None)
        if existing:
            print(f"Equipment Found! ID: {existing['id']}, Type: {existing['meter_type']}")
            eq_id = existing['id']
            
            # 2. Call Metrics Endpoint
            print(f"Calling Metrics Endpoint: /equipments/{eq_id}/metrics")
            res_metrics = requests.get(f"{API_BASE}/equipments/{eq_id}/metrics")
            
            if res_metrics.status_code == 200:
                data = res_metrics.json()
                print("Metrics Response:", data)
                
                metrics = data['data']['metrics']
                cost = data['data']['cost']
                
                # Assertions
                errors = []
                if 'production_rate' not in metrics:
                    errors.append("Missing 'production_rate'")
                if 'efficiency_kwh_ton' not in metrics:
                    errors.append("Missing 'efficiency_kwh_ton'")
                if 'per_ton' not in cost:
                    errors.append("Missing cost 'per_ton'")
                    
                if not errors:
                    print("SUCCESS: All Production Metrics present in API response.")
                else:
                    print(f"FAILURE: Missing keys: {errors}")
            else:
                 print(f"Metrics Endpoint Failed: {res_metrics.status_code} {res_metrics.text}")

        else:
            print("Equipment not found. Run verify_metrics.py first to create it.")
    else:
        print("List equipments failed.")
except Exception as e:
    print(f"Error: {e}")
