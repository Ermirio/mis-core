"""
SIMPLE DIAGNOSTIC: Check if production fields are being calculated
"""
from influxdb import InfluxDBClient
from decouple import config

INFLUX_HOST = config('INFLUXDB_HOST', default='127.0.0.1')
INFLUX_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUX_DB = config('INFLUXDB_DATABASE', default='industrial_db')
INFLUX_USER = config('INFLUXDB_USER', default=None)
INFLUX_PASS = config('INFLUXDB_USER_PASSWORD', default=None)

client = InfluxDBClient(
    host=INFLUX_HOST,
    port=INFLUX_PORT,
    username=INFLUX_USER,
    password=INFLUX_PASS,
    database=INFLUX_DB
)

print("=" * 80)
print("SIMPLE CHECK: Are production fields being saved?")
print("=" * 80)

# Get latest point
query = "SELECT * FROM producao ORDER BY time DESC LIMIT 1"
result = client.query(query)
points = list(result.get_points())

if not points:
    print("\n✗ No data in InfluxDB!")
    exit(1)

p = points[0]

print("\nLATEST DATA POINT:")
print(f"  Time: {p.get('time')}")
print(f"  Equipamento: {p.get('equipamento_codigo')}")
print(f"  OP (tag): '{p.get('ordem_producao')}'")
print(f"  SKU (tag): '{p.get('sku_codigo')}'")
print(f"  Formato (tag): '{p.get('formato_gramas')}'")
print(f"  Contagem Saída (field): {p.get('contagem_saida')}")

print("\nPRODUCTION FIELDS:")
prod_op = p.get('producao_acumulada_op')
prod_sku = p.get('producao_acumulada_sku')

if prod_op is not None:
    print(f"  ✓ producao_acumulada_op: {prod_op} ton")
else:
    print(f"  ✗ producao_acumulada_op: MISSING")
    print(f"     Flask is NOT calculating this field!")
    print(f"     Check Flask logs for [OP ACUM] messages")

if prod_sku is not None:
    print(f"  ✓ producao_acumulada_sku: {prod_sku} ton")
else:
    print(f"  ✗ producao_acumulada_sku: MISSING")
    print(f"     Flask is NOT calculating this field!")

# Manual calculation to verify
if p.get('contagem_saida') and p.get('formato_gramas'):
    try:
        contagem = float(p.get('contagem_saida'))
        formato = float(p.get('formato_gramas'))
        expected_prod = (contagem * formato) / 1000000.0
        print(f"\nEXPECTED CALCULATION:")
        print(f"  ({contagem} * {formato}) / 1000000 = {expected_prod:.3f} ton")
        
        if prod_op is not None:
            if abs(prod_op - expected_prod) < 0.001:
                print(f"  ✓ Calculation matches!")
            else:
                print(f"  ⚠ Calculation mismatch: {prod_op} vs {expected_prod}")
    except:
        pass

print("\n" + "=" * 80)
print("DIAGNOSIS:")
print("=" * 80)

if prod_op is None or prod_sku is None:
    print("\n✗ PROBLEM: Production fields are NOT being saved")
    print("\nPOSSIBLE CAUSES:")
    print("  1. Flask backend not restarted after code fix")
    print("  2. Flask code still has bug (tags extracted before calculation)")
    print("  3. Coletor not sending ordem_producao/sku_codigo/formato_gramas")
    
    print("\nSOLUTIONS:")
    print("  1. RESTART Flask: Ctrl+C and run 'py app.py' again")
    print("  2. Check Flask logs for [OP ACUM] and [SKU ACUM] messages")
    print("  3. Verify coletor is sending all required fields")
else:
    print("\n✓ Production fields are being saved correctly!")
    print("\nIf frontend still not showing data:")
    print("  1. Check Django views.py query logic")
    print("  2. Verify frontend is calling correct API endpoint")
    print("  3. Check browser console for errors")

print("=" * 80)
