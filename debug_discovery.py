import requests
import json
try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote

INFLUX = "http://localhost:8086"
USER = 'admin'
PASS = 'admin123'
DB = 'industrial_db'

print("--- DIAGNOSTIC START ---")

def query(q):
    try:
        r = requests.get(
            f"{INFLUX}/query", 
            params={'db': DB, 'q': q, 'u': USER, 'p': PASS}, 
            timeout=5
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}

print(f"--- TAGS in {DB} ---")
# Check 'line' tag
res = query("SHOW TAG VALUES FROM production WITH KEY = line")
print(f"KEY 'line': {json.dumps(res, indent=2)}")

# Check 'equipment' tag
res = query("SHOW TAG VALUES FROM production WITH KEY = equipment")
print(f"KEY 'equipment': {json.dumps(res, indent=2)}")

print(f"--- SAMPLE DATA (Limit 3) ---")
res = query("SELECT * FROM production LIMIT 3")
print(json.dumps(res, indent=2))

print("--- DIAGNOSTIC END ---")
