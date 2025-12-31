
import requests
import json
import time
import random
from datetime import datetime, timedelta

FLASK_API_URL = "http://localhost:5001/api" # Port 5001 mapped to host
EQUIPMENT = "E001"
LINE = "L01"

def send_packet(state, duration_sec):
    # Sends a packet representing 'state' at current time
    timestamp = datetime.utcnow().isoformat() + 'Z'
    
    payload = {
        "equipamento_codigo": EQUIPMENT,
        "linha_codigo": LINE,
        "timestamp": timestamp,
        "medicoes": {
            "estado_maquina": state,
            "velocidade_atual": 100 if state == 1 else 0,
            "contagem_saida": 1000,
            "descarte": 0,
            "ordem_producao": "OP-TEST-01",
            "sku_codigo": "SKU-999",
            "planejado_op": 2000,
            "connection_status": "ONLINE"
        }
    }
    
    try:
        r = requests.post(f"{FLASK_API_URL}/dados/inserir", json=payload, timeout=2)
        print(f"Sent State {state} at {timestamp}: Status {r.status_code}")
    except Exception as e:
        print(f"Error sending: {e}")

print("--- Starting Micro-Stop Simulation ---")

# Sequence: Run -> Stop (40s) -> Run -> Stop (30s) -> Run -> Stop (50s) -> Run -> Stop (20s) -> Run
# This creates 4 micro-stops within minutes.

sequence = [
    (1, 2),   # Run 2s
    (4, 40),  # STOP 40s (Micro)
    (1, 2),
    (4, 30),  # STOP 30s (Micro)
    (1, 2),
    (4, 50),  # STOP 50s (Micro)
    (1, 2),
    (4, 20),  # STOP 20s (Micro)
    (1, 2)
]

# We can't actually 'wait' the real duration otherwise this script takes minutes.
# But we are sending 'live' data (timestamp = now). 
# So to simulate history, we should either:
# 1. Wait locally (slow)
# 2. Forge timestamps in the past (fast)

# Let's forge timestamps in the past 10 minutes to populate history instantly.
base_time = datetime.utcnow() - timedelta(minutes=10)

current_time = base_time
for state, duration in sequence:
    # Packet at start of state
    ts = current_time.isoformat() + 'Z'
    
    payload = {
        "equipamento_codigo": EQUIPMENT,
        "linha_codigo": LINE,
        "timestamp": ts,
        "medicoes": {
            "estado_maquina": state,
            "velocidade_atual": 100 if state == 1 else 0,
            "contagem_saida": 1000,
            "ordem_producao": "OP-TEST-01",
            "sku_codigo": "SKU-999"
        }
    }
    requests.post(f"{FLASK_API_URL}/dados/inserir", json=payload)
    print(f"Forged {state} at {ts} (Duration {duration}s)")
    
    current_time += timedelta(seconds=duration)

print("Simulation sent. Now checking diagnostics endpoint...")
time.sleep(2)

# Check diagnostics
try:
    r = requests.get(f"{FLASK_API_URL}/diagnostics/alerts/{EQUIPMENT}")
    print("\n--- Diagnostics Response ---")
    print(json.dumps(r.json(), indent=2))
except Exception as e:
    print(f"Error checking diagnostics: {e}")
