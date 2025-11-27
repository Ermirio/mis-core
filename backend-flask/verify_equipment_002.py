"""
Verify production data for equipment 002 (ACMA - the one with OP/SKU)
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
print("CHECKING EQUIPMENT 002 (ACMA) - Should have OP/SKU production")
print("=" * 80)

# Get latest point for equipment 002
query = "SELECT * FROM producao WHERE equipamento_codigo = '002' ORDER BY time DESC LIMIT 1"
result = client.query(query)
points = list(result.get_points())

if not points:
    print("\n✗ No data for equipment 002!")
    exit(1)

p = points[0]

print("\nLATEST DATA FOR EQUIPMENT 002:")
print(f"  Time: {p.get('time')}")
print(f"  OP (tag): '{p.get('ordem_producao')}'")
print(f"  SKU (tag): '{p.get('sku_codigo')}'")
print(f"  Formato (tag): '{p.get('formato_gramas')}'")
print(f"  Contagem Saída: {p.get('contagem_saida')}")
print(f"  ✓ Produção Acum OP: {p.get('producao_acumulada_op')} ton")
print(f"  ✓ Produção Acum SKU: {p.get('producao_acumulada_sku')} ton")

# Test Django-style query
op = p.get('ordem_producao')
if op and str(op).strip() and str(op) != 'None':
    print(f"\n" + "=" * 80)
    print(f"TESTING DJANGO QUERY FOR OP: {op}")
    print("=" * 80)
    
    query_django = f"""
        SELECT last("producao_acumulada_op") as producao_op,
               last("producao_acumulada_sku") as producao_sku
        FROM "producao"
        WHERE "equipamento_codigo" = '002'
        AND "ordem_producao" = '{op}'
    """
    
    print(f"\nQuery:\n{query_django}")
    
    result_django = client.query(query_django)
    points_django = list(result_django.get_points())
    
    if points_django:
        prod_op = points_django[0].get('producao_op')
        prod_sku = points_django[0].get('producao_sku')
        
        print(f"\n✓ Query successful!")
        print(f"  Produção OP: {prod_op} ton")
        print(f"  Produção SKU: {prod_sku} ton")
        
        if prod_op and prod_op > 0:
            print(f"\n✓✓✓ SUCCESS! Django query is working correctly!")
            print(f"    The frontend should display: {prod_op} ton for OP {op}")
        else:
            print(f"\n⚠ Query returned 0 or None")
    else:
        print(f"\n✗ Query returned no results")
else:
    print(f"\n⚠ No valid OP in latest data point")

print("\n" + "=" * 80)
