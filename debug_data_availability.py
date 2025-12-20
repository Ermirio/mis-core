import requests
import json
from datetime import datetime

# Direct InfluxDB Query via requests (assuming InfluxDB default port 8086)
# Or better: use the Flask App context if possible? No, stand-alone script is cleaner if I can reach Influx.
# But I don't know the Influx credentials offhand (usually in .env).
# Let's try hitting the Flask endpoint that DUMPS data first, it's easier.

# I'll hit /api/linha/Linha 01/status and Linha 02/status to see keys.
try:
    print("--- Linha 01 Status ---")
    r = requests.get("http://localhost:5000/api/linha/Linha%2001/status")
    if r.status_code == 200:
        data = r.json()
        for eq in data.get('equipamentos', []):
            med = eq.get('medicoes', {})
            print(f"EQ: {eq['nome']} | OP: {med.get('ordem_producao')} | SKU: {med.get('sku_codigo')} | Desc: {med.get('descricao')}")
    else:
        print(f"Error: {r.status_code}")

    print("\n--- Linha 02 Status ---")
    r = requests.get("http://localhost:5000/api/linha/Linha%2002/status")
    if r.status_code == 200:
        data = r.json()
        found_data = False
        for eq in data.get('equipamentos', []):
            med = eq.get('medicoes', {})
            op = med.get('ordem_producao')
            sku = med.get('sku_codigo')
            print(f"EQ: {eq['nome']} | OP: {op} | SKU: {sku} | Desc: {med.get('descricao')}")
            if op != 'N/A' and sku != 'N/A':
                found_data = True
                
        if not found_data:
            print("\nWARNING: No valid OP/SKU found in ANY equipment for Linha 02?")
            # If no data found via status, let's try reading the 'operacao' endpoint for a known equipment if we can guess one.
            # Usually 'E01', 'E02', etc. or names.
    else:
        print(f"Error: {r.status_code}")

except Exception as e:
    print(e)
