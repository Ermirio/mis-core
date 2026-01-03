import requests
import json
import time

BASE_URL = "http://localhost:5005/api"

def trigger_read(eq_id):
    print(f"Triggering read for Equipment {eq_id}...")
    try:
        url = f"{BASE_URL}/equipments/{eq_id}/read"
        # Force real mode (not mock)
        headers = {'X-Mock-Mode': 'false'} 
        res = requests.post(url, headers=headers)
        
        print(f"Status: {res.status_code}")
        try:
            print(f"Response: {json.dumps(res.json(), indent=2)}")
        except:
            print(f"Raw: {res.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Motor Core ID (from prev list) seems to be... let's find it.
    # Assuming ID 57 based on user context or I'll list first to find "Motor Core" type
    
    # List to find ID
    try:
        list_res = requests.get(f"{BASE_URL}/equipments")
        equipments = list_res.json().get('data', [])
        target_id = None
        for eq in equipments:
            print(f"Checking: {eq['id']} - {eq['name']}")
            if "CORE" in eq['name'].upper() or "MOTOR" in eq['name'].upper():
                print(f"Found candidate: {eq['id']} - {eq['name']}")
                target_id = eq['id']
                if "CORE" in eq['name'].upper():
                    break
        
        if target_id:
            # Trigger multiple reads to generate points for graph
            print(f"Generating data for ID {target_id}...")
            for i in range(3):
                trigger_read(target_id)
                time.sleep(2)
        else:
            print("Motor Core not found in list")
            
    except Exception as e:
        print(f"List error: {e}")
