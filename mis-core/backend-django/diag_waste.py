import requests
import json
from influxdb import InfluxDBClient

BASE_URL = "http://localhost:3000"

# 1. Flask API
print("="*60)
print("FLASK API (Memória)")
print("="*60)

flask_data = {}
for eq in ["E001", "E002"]:
    try:
        r = requests.get(f"{BASE_URL}/flask-api/operacao/dados/{eq}", timeout=5)
        if r.status_code == 200:
            d = r.json()
            flask_data[eq] = d
            print(f"\n{eq}:")
            print(f"  pecas_ruins: {d.get('pecas_ruins')}")
            print(f"  produzido_op: {d.get('produzido_op')}")
            print(f"  pecas_boas: {d.get('pecas_boas')}")
            print(f"  formato_gramas: {d.get('formato_gramas')}")
        else:
            print(f"{eq}: HTTP {r.status_code}")
    except Exception as e:
        print(f"{eq}: ERROR {e}")

# 2. InfluxDB Query
print("\n" + "="*60)
print("INFLUXDB (Persistência)")
print("="*60)

influx_data = {}
try:
    client = InfluxDBClient(host='localhost', port=8087, username='admin', password='admin123', database='industrial_db')
    
    for eq in ["E001", "E002"]:
        # Query dos últimos 10 pontos para ver evolução
        query = f"SELECT descarte, contagem_saida, contagem_entrada, refugo_op_acumulado, producao_op_acumulada FROM production WHERE \"equipment\" = '{eq}' ORDER BY time DESC LIMIT 5"
        rs = client.query(query)
        points = list(rs.get_points())
        print(f"\n{eq} (últimos 5 pontos):")
        if points:
            for i, p in enumerate(points):
                print(f"  [{i}] descarte={p.get('descarte')}, saida={p.get('contagem_saida')}, entrada={p.get('contagem_entrada')}, refugo_op={p.get('refugo_op_acumulado')}, prod_op={p.get('producao_op_acumulada')}")
            influx_data[eq] = points
        else:
            print("  NO DATA")
            
except Exception as e:
    print(f"InfluxDB ERROR: {e}")

# 3. Django API
print("\n" + "="*60)
print("DJANGO API (Agregação)")
print("="*60)

try:
    r = requests.get(f"{BASE_URL}/api/linhas/1/waste-analysis/?periodo=TURNO", timeout=10)
    if r.status_code == 200:
        d = r.json()
        print(f"total_waste: {d.get('total_waste')} (unidade: provável toneladas)")
        print(f"total_production: {d.get('total_production')}")
        print(f"waste_percentage: {d.get('waste_percentage')}%")
        print(f"\nby_equipment:")
        for eq in d.get('by_equipment', []):
            print(f"  - {eq['name']}: {eq['value']} ton ({eq['share']}%)")
        print(f"\nby_state:")
        for st in d.get('by_state', []):
            print(f"  - {st['label']}: {st['value']} ton")
    else:
        print(f"HTTP {r.status_code}: {r.text}")
except Exception as e:
    print(f"Django ERROR: {e}")

# 4. Análise de Discrepância
print("\n" + "="*60)
print("ANÁLISE COMPARATIVA")
print("="*60)

for eq in ["E001", "E002"]:
    flask_waste = flask_data.get(eq, {}).get('pecas_ruins', 0)
    flask_fmt = flask_data.get(eq, {}).get('formato_gramas', 0)
    flask_waste_ton = (flask_waste * flask_fmt) / 1000000 if flask_fmt else 0
    
    influx_pts = influx_data.get(eq, [])
    influx_last_descarte = influx_pts[0].get('descarte', 0) if influx_pts else 0
    influx_last_refugo = influx_pts[0].get('refugo_op_acumulado', 0) if influx_pts else 0
    
    print(f"\n{eq}:")
    print(f"  Flask pecas_ruins: {flask_waste}")
    print(f"  Flask formato: {flask_fmt}g")
    print(f"  Flask calc tons: {flask_waste_ton:.6f}")
    print(f"  InfluxDB descarte (raw): {influx_last_descarte}")
    print(f"  InfluxDB refugo_op_acum: {influx_last_refugo}")
    
    # Comparação
    if flask_waste > 0 and influx_last_refugo == 0:
        print(f"  >>> PROBLEMA: Flask tem refugo, InfluxDB não!")
    elif flask_waste > 0 and influx_last_descarte == 0:
        print(f"  >>> ALERTA: descarte raw=0, mas refugo_op_acum pode estar correto")

