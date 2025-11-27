"""
Quick test to verify production tracking by OP and SKU is working
"""
import time
from influxdb import InfluxDBClient
from decouple import config

# InfluxDB configuration
INFLUX_HOST = config('INFLUXDB_HOST', default='127.0.0.1')
INFLUX_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUX_DB = config('INFLUXDB_DATABASE', default='industrial_db')

client = InfluxDBClient(
    host=INFLUX_HOST,
    port=INFLUX_PORT,
    database=INFLUX_DB
)

print("=" * 80)
print("QUICK TEST: PRODUCTION BY OP AND SKU")
print("=" * 80)

print("\nWaiting 10 seconds for new data to be collected...")
time.sleep(10)

# Check recent data
query = "SELECT * FROM producao ORDER BY time DESC LIMIT 3"
result = client.query(query)
points = list(result.get_points())

if points:
    print("\n✓ Recent data found:")
    for i, p in enumerate(points, 1):
        print(f"\nPoint {i}:")
        print(f"  OP: '{p.get('ordem_producao')}'")
        print(f"  SKU: '{p.get('sku_codigo')}'")
        print(f"  Contagem Saída: {p.get('contagem_saida')}")
        print(f"  Formato: {p.get('formato_gramas')}g")
        print(f"  ✓ Produção Acum OP: {p.get('producao_acumulada_op')} ton")
        print(f"  ✓ Produção Acum SKU: {p.get('producao_acumulada_sku')} ton")
        
    # Check if fields exist
    if points[0].get('producao_acumulada_op') is not None:
        print("\n✓ SUCCESS: producao_acumulada_op field is being saved!")
    else:
        print("\n✗ FAIL: producao_acumulada_op field is missing")
        
    if points[0].get('producao_acumulada_sku') is not None:
        print("✓ SUCCESS: producao_acumulada_sku field is being saved!")
    else:
        print("✗ FAIL: producao_acumulada_sku field is missing")
else:
    print("\n⚠ No data found - waiting for collection...")

print("\n" + "=" * 80)
