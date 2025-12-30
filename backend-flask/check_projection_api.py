
import requests
import json
import time



URL = "http://localhost:5001/api/linha/Linha 01/realtime"



try:
    print(f"Checking {URL}...")
    r = requests.get(URL, timeout=5)
    if r.status_code == 200:
        data = r.json()
        print(json.dumps(data, indent=2))
        
        proj = data.get('projecao', 0)
        real = data.get('producao_real', 0)
        taxa = data.get('taxa_instantanea', 0)
        
        print(f"\n--- Analysis ---")
        print(f"Real: {real}")
        print(f"Rate: {taxa}")
        print(f"Proj: {proj}")
        
        if taxa == 0 and proj == real:
            print("SUCCESS: Rate is 0 and Projection == Real (Stale data handled correctly).")
        elif taxa > 0:
            print("WARNING: Rate > 0. Is data fresh? Or fix failed?")
        else:
            print("Check logic.")
            
    else:
        print(f"Error: {r.status_code} - {r.text}")
except Exception as e:
    print(f"Exception: {e}")
