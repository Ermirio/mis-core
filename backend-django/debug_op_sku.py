"""
Debug script to check OP and SKU production tracking
"""
from influxdb import InfluxDBClient
from decouple import config
import sys
import os

# Add Django to path
sys.path.append('C:\\Users\\ermir\\Documents\\GitHub\\projeto-monitoramento-industrial-completo\\backend-django')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from equipamentos.influx_helpers import get_production_by_op, get_production_by_sku

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
print("DEBUG: PRODUCTION TRACKING BY OP AND SKU")
print("=" * 80)

# 1. Check recent data
print("\n1. RECENT DATA (Last 5 points):")
print("-" * 80)
query = "SELECT * FROM producao ORDER BY time DESC LIMIT 5"
result = client.query(query)
points = list(result.get_points())

if points:
    for i, p in enumerate(points, 1):
        print(f"\nPoint {i}:")
        print(f"  Time: {p.get('time')}")
        print(f"  Equipamento: {p.get('equipamento_codigo')}")
        print(f"  OP: '{p.get('ordem_producao')}'")
        print(f"  SKU: '{p.get('sku_codigo')}'")
        print(f"  Formato: {p.get('formato_gramas')}g")
        print(f"  Contagem Saída: {p.get('contagem_saida')}")
        print(f"  Produção Acum OP: {p.get('producao_acumulada_op')}")
        print(f"  Produção Acum SKU: {p.get('producao_acumulada_sku')}")
else:
    print("⚠ No data found!")
    sys.exit(1)

# Get current OP and SKU
current_op = points[0].get('ordem_producao')
current_sku = points[0].get('sku_codigo')
current_formato = points[0].get('formato_gramas')
equipamento = points[0].get('equipamento_codigo')

print(f"\n2. CURRENT VALUES:")
print("-" * 80)
print(f"  Equipamento: {equipamento}")
print(f"  OP: '{current_op}' (type: {type(current_op).__name__})")
print(f"  SKU: '{current_sku}' (type: {type(current_sku).__name__})")
print(f"  Formato: {current_formato}g")

# 3. Test query by OP (raw)
print(f"\n3. RAW QUERY BY OP:")
print("-" * 80)
if current_op:
    query = f"SELECT * FROM producao WHERE ordem_producao = '{current_op}' LIMIT 5"
    print(f"Query: {query}")
    result = client.query(query)
    op_points = list(result.get_points())
    print(f"Results: {len(op_points)} points")
    if op_points:
        print(f"  First contagem_saida: {op_points[0].get('contagem_saida')}")
        print(f"  Last contagem_saida: {op_points[-1].get('contagem_saida')}")
else:
    print("⚠ OP is empty/None!")

# 4. Test query by SKU (raw)
print(f"\n4. RAW QUERY BY SKU:")
print("-" * 80)
if current_sku:
    query = f"SELECT * FROM producao WHERE sku_codigo = '{current_sku}' LIMIT 5"
    print(f"Query: {query}")
    result = client.query(query)
    sku_points = list(result.get_points())
    print(f"Results: {len(sku_points)} points")
    if sku_points:
        print(f"  First contagem_saida: {sku_points[0].get('contagem_saida')}")
        print(f"  Last contagem_saida: {sku_points[-1].get('contagem_saida')}")
else:
    print("⚠ SKU is empty/None!")

# 5. Test helper function
print(f"\n5. HELPER FUNCTION TEST:")
print("-" * 80)
if current_op and current_formato:
    try:
        formato_float = float(current_formato) if current_formato else 0
        result = get_production_by_op(equipamento, current_op, formato_float, client)
        print(f"get_production_by_op() result:")
        print(f"  Toneladas OP: {result['toneladas_op']}")
        print(f"  Contagem OP: {result['contagem_op']}")
        print(f"  Primeira: {result['primeira_contagem']}")
        print(f"  Última: {result['ultima_contagem']}")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if current_sku and current_formato:
    try:
        formato_float = float(current_formato) if current_formato else 0
        result = get_production_by_sku(equipamento, current_sku, formato_float, client)
        print(f"\nget_production_by_sku() result:")
        print(f"  Toneladas SKU: {result['toneladas_sku']}")
        print(f"  Contagem SKU: {result['contagem_sku']}")
        print(f"  Primeira: {result['primeira_contagem']}")
        print(f"  Última: {result['ultima_contagem']}")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

# 6. Check tag values
print(f"\n6. TAG VALUES CHECK:")
print("-" * 80)
query = "SHOW TAG VALUES FROM producao WITH KEY = ordem_producao"
result = client.query(query)
tag_values = list(result.get_points())
print(f"Distinct OP values in database: {len(tag_values)}")
for tv in tag_values[:5]:
    print(f"  - '{tv.get('value')}'")

query = "SHOW TAG VALUES FROM producao WITH KEY = sku_codigo"
result = client.query(query)
tag_values = list(result.get_points())
print(f"\nDistinct SKU values in database: {len(tag_values)}")
for tv in tag_values[:5]:
    print(f"  - '{tv.get('value')}'")

print("\n" + "=" * 80)
