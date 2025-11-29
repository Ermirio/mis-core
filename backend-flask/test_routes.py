import requests
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_routes():
    print("Testing Routes...")
    
    # 1. Test Health
    try:
        r = requests.get(f"{BASE_URL}/api/health")
        print(f"Health: {r.status_code} - {r.json()}")
        if r.status_code != 200: sys.exit(1)
    except Exception as e:
        print(f"Health Failed: {e}")
        sys.exit(1)

    # 2. Test OLE Route (The one that was 404ing)
    line_name = "L01" # Correct line name provided by user
    try:
        r = requests.get(f"{BASE_URL}/api/linha/{line_name}/realtime")
        print(f"OLE Route ({line_name}): {r.status_code}")
        if r.status_code == 200:
            print(f"Response: {r.json()}")
        else:
            print(f"Error: {r.text}")
            sys.exit(1)
    except Exception as e:
        print(f"OLE Route Failed: {e}")
        sys.exit(1)

    print("ALL ROUTES PASSED")

if __name__ == "__main__":
    test_routes()
