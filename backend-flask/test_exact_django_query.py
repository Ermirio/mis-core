"""
Direct test of the exact query Django uses
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
print("DIRECT TEST: Exact Django Query")
print("=" * 80)

# Test for equipment 002 (ACMA - the one with data)
equipamento_codigo = '002'

query = f"""
    SELECT last("producao_acumulada_op") as producao_op,
           last("producao_acumulada_sku") as producao_sku
    FROM "producao"
    WHERE "equipamento_codigo" = '{equipamento_codigo}'
"""

print(f"\nQuery for equipment {equipamento_codigo}:")
print(query)

result = client.query(query)
points = list(result.get_points())

print(f"\nResults: {len(points)} points")

if points:
    print(f"\nRaw point data:")
    print(points[0])
    
    prod_op = points[0].get('producao_op')
    prod_sku = points[0].get('producao_sku')
    
    print(f"\nExtracted values:")
    print(f"  producao_op: {prod_op} (type: {type(prod_op).__name__})")
    print(f"  producao_sku: {prod_sku} (type: {type(prod_sku).__name__})")
    
    if prod_op is not None:
        print(f"\n✓ prod_op has value: {float(prod_op)} ton")
    else:
        print(f"\n✗ prod_op is None!")
        print("\nPossible causes:")
        print("  1. Field 'producao_acumulada_op' doesn't exist in InfluxDB")
        print("  2. All values are NULL")
        print("  3. Field name mismatch")
        
        # Test if field exists
        print("\nChecking if field exists...")
        query_fields = "SHOW FIELD KEYS FROM producao"
        result_fields = client.query(query_fields)
        fields = [f['fieldKey'] for f in result_fields.get_points()]
        print(f"Available fields: {fields}")
        
        if 'producao_acumulada_op' in fields:
            print("✓ Field exists!")
            
            # Try to get ANY value
            query_any = f'SELECT "producao_acumulada_op" FROM "producao" WHERE "equipamento_codigo" = \'{equipamento_codigo}\' LIMIT 5'
            print(f"\nTrying to get any values:\n{query_any}")
            result_any = client.query(query_any)
            points_any = list(result_any.get_points())
            print(f"Found {len(points_any)} points with producao_acumulada_op")
            for i, p in enumerate(points_any[:3], 1):
                print(f"  Point {i}: {p.get('producao_acumulada_op')}")
        else:
            print("✗ Field does NOT exist in InfluxDB!")
else:
    print("\n✗ Query returned no points!")

print("\n" + "=" * 80)
