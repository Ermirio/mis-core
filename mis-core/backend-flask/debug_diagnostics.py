
import sys
import os
from datetime import datetime
from influxdb import InfluxDBClient
from decouple import config

# Mock config to match environment
# Assuming running from backend-flask directory or similar context, 
# but need to set properly if running via docker exec.
# Easier to just hardcode standard defaults for the docker container context

INFLUXDB_HOST = 'influxdb' # Inside docker network this is the host
INFLUXDB_PORT = 8086
INFLUXDB_DB = 'industrial_db'
INFLUXDB_USER = 'admin'
INFLUXDB_PASS = 'admin123'

try:
    client = InfluxDBClient(host='localhost', port=8086, database='industrial_db', username=INFLUXDB_USER, password=INFLUXDB_PASS)
    client.ping()
except:
    # Fallback if running from host machine connecting to mapped port
    client = InfluxDBClient(host='127.0.0.1', port=8086, database='industrial_db', username=INFLUXDB_USER, password=INFLUXDB_PASS)

print(f"Connected to InfluxDB: {client.ping()}")

def get_equipment_history(equipamento_codigo, minutes=120):
    print(f"--- Fetching History for {equipamento_codigo} (last {minutes}m) ---")
    query = f"SELECT * FROM machine_status WHERE equipment = '{equipamento_codigo}' AND time > now() - {minutes}m ORDER BY time ASC"
    result = client.query(query)
    points = list(result.get_points())
    
    print(f"Found {len(points)} raw points.")
    for p in points:
        print(f"RAW: time={p['time']}, estado_maquina={p.get('estado_maquina')}")

    history = []
    if not points:
        return history

    from datetime import timedelta
    # Re-implement simplified logic from engine for debugging
    ESTADOS_MAQUINA = {
        1: "Produzindo",
        2: "Aguardando Anterior",
        3: "Bloqueado Próximo",
        4: "Parado/Falha",
        8: "Manutenção",
        9: "Falta de Material"
    }

    for i in range(len(points) - 1):
        current = points[i]
        next_p = points[i+1]
        
        start = datetime.fromisoformat(current['time'].replace('Z', '+00:00'))
        end = datetime.fromisoformat(next_p['time'].replace('Z', '+00:00'))
        duration = (end - start).total_seconds()
        
        code = int(current.get('estado_maquina', 0))
        internal_state = ESTADOS_MAQUINA.get(code, 'Unknown')
        
        # Mapping used in engine
        if code == 4: internal_state = 'PARADO'
        elif code == 9: internal_state = 'FALTA_MAT'
        elif code == 8: internal_state = 'MANUTENCAO'
        
        history.append({
            'estado': internal_state,
            'inicio': current['time'],
            'duracao_segundos': duration,
            'code': code
        })

    # Last point
    last = points[-1]
    code = int(last.get('estado_maquina', 0))
    internal_state = ESTADOS_MAQUINA.get(code, 'Unknown')
    if code == 4: internal_state = 'PARADO'
    elif code == 9: internal_state = 'FALTA_MAT'
    
    start = datetime.fromisoformat(last['time'].replace('Z', '+00:00'))
    duration = (datetime.utcnow().replace(tzinfo=None) - start.replace(tzinfo=None)).total_seconds()
    
    history.append({
        'estado': internal_state,
        'inicio': last['time'],
        'duracao_segundos': duration,
        'code': code,
        'is_last': True
    })
    
    history.reverse() # Newest first
    return history

def analyze(history):
    print("\n--- Analzying Micro-Stops (Refined Logic) ---")
    
    if not history or len(history) < 1:
        print("Not enough history.")
        return

    analyzable = history[1:] # Skip first (current)
    print(f"Skipping current/ongoing state: {history[0]}")
    
    window_minutes = 60
    limit_time = datetime.utcnow() - 60 * 60 # seconds (naive approximation for debug)
    # Actually robust check:
    from datetime import timedelta
    limit_dt = datetime.utcnow() - timedelta(minutes=60)
    
    stops = []
    
    for e in analyzable:
        print(f"Checking event: {e['estado']} | Duration: {e['duracao_segundos']:.1f}s | Time: {e['inicio']}")
        
        if e.get('estado') not in ['PARADO', 'FALTA_MAT']:
            print("  -> SKIPPED: Wrong State")
            continue
            
        if e.get('duracao_segundos', 0) >= 60:
            print("  -> SKIPPED: Duration >= 60s")
            continue
            
        # Timestamp check
        start_str = e.get('inicio', '').replace('Z', '+00:00')
        event_time = datetime.fromisoformat(start_str).replace(tzinfo=None)
        
        if event_time < limit_dt:
             print("  -> SKIPPED: Too old")
             continue
             
        print("  -> MATCH! Counted as Micro-Stop.")
        stops.append(e)
        
    print(f"\nTotal Micro-Stops detected: {len(stops)}")
    print(f"Threshold rqeuired: 4")

# RUN
# CHECK AVAILABLE EQUIPMENTS
print("--- Checking available equipments in machine_status ---")
try:
    res = client.query("SHOW TAG VALUES FROM machine_status WITH KEY = \"equipment\"")
    print("Tags found:", list(res.get_points()))
except Exception as e:
    print(f"Error querying tags: {e}")

# Try to find recent data
print("--- Checking recent data (last 3h) ---")
res = client.query("SELECT * FROM machine_status WHERE time > now() - 3h LIMIT 5")
print("Recent points:", list(res.get_points()))

