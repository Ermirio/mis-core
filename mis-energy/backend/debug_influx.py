import requests
from datetime import datetime, timedelta

# Config constants (matching backend)
INFLUX_HOST = 'localhost'
INFLUX_PORT = 8087
DATABASE = 'db_energy'
USERNAME = 'admin'
PASSWORD = 'admin123'

def debug_influx_query():
    print("=== Debugging InfluxDB Query ===")
    
    # 1. Define Time Range (Last 24h)
    start_time = datetime.utcnow() - timedelta(hours=24)
    print(f"Query Start Time (UTC): {start_time.isoformat()}Z")
    
    # 2. Construct Query (Matching backend logic)
    # TAG comes from Equipment 13 (Motor Core). Assuming tag is 'MOTOR CORE' based on name fallback
    # But wait, looking at force_read.py, name is 'MOTOR CORE'.
    # In routes/equipment.py: eq_tag = equipment.tag or equipment.name
    # Backend saves: tag_code=tag_code (where tag_code = eq.tag or eq.name)
    # So if tag is None, it used 'MOTOR CORE'.
    
    target_tag = 'MOTOR CORE' 
    metric = 'power_kw'
    
    query = f'''
        SELECT * 
        FROM "energy_consumption" 
        ORDER BY time DESC
        LIMIT 10
    '''
    
    print(f"Query: {query}")
    
    try:
        response = requests.get(
            f'http://{INFLUX_HOST}:{INFLUX_PORT}/query',
            params={'db': DATABASE, 'q': query, 'u': USERNAME, 'p': PASSWORD}
        )
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [{}])[0]
            if 'series' in results:
                print(f"Data Found! Series count: {len(results['series'])}")
                for s in results['series']:
                    print(f"Measurement: {s['name']}")
                    print(f"Tags: {s.get('tags', {})}")
                    print(f"Columns: {s['columns']}")
                    # Print last 3 values
                    values = s['values']
                    print(f"Total Points: {len(values)}")
                    print("Last 3 points:")
                    for v in values[-3:]:
                        print(v)
            else:
                print("NO DATA FOUND in query result (Clean 200 OK)")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    debug_influx_query()
