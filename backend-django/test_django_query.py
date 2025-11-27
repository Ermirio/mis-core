"""
Test Django query directly
"""
import sys
import os
sys.path.append('C:\\Users\\ermir\\Documents\\GitHub\\projeto-monitoramento-industrial-completo\\backend-django')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from equipamentos.influx_helpers import get_influx_client

client = get_influx_client()

print("=" * 80)
print("TESTING DJANGO QUERY FOR EQUIPMENT 002")
print("=" * 80)

# Query exactly as Django does
query = """
    SELECT last("producao_acumulada_op") as producao_op,
           last("producao_acumulada_sku") as producao_sku
    FROM "producao"
    WHERE "equipamento_codigo" = '002'
"""

print(f"\nQuery:\n{query}")

result = client.query(query)
points = list(result.get_points())

print(f"\nResults: {len(points)} points")

if points:
    p = points[0]
    print(f"\nData:")
    print(f"  producao_op: {p.get('producao_op')}")
    print(f"  producao_sku: {p.get('producao_sku')}")
    
    if p.get('producao_op'):
        print(f"\n✓ SUCCESS! Query returned data: {p.get('producao_op')} ton")
    else:
        print(f"\n✗ Query returned None/0")
else:
    print("\n✗ No results")

print("\n" + "=" * 80)
