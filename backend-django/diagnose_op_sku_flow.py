"""
DIAGNOSTIC TOOL: Complete Data Flow Tracer for OP/SKU Production
==================================================================

This script traces the entire data flow from collection to display:
1. Coletor → Flask (payload check)
2. Flask → InfluxDB (write verification)
3. InfluxDB storage (tag/field verification)
4. Django queries (read verification)

It compares with the working shift logic to identify differences.
"""

import sys
import os
sys.path.append('C:\\Users\\ermir\\Documents\\GitHub\\projeto-monitoramento-industrial-completo\\backend-django')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from influxdb import InfluxDBClient
from decouple import config
from equipamentos.models import Equipamento
from equipamentos.influx_helpers import get_influx_client, get_production_by_op, get_production_by_sku
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# InfluxDB config
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

print("=" * 100)
print("DIAGNOSTIC: COMPLETE DATA FLOW TRACE FOR OP/SKU PRODUCTION")
print("=" * 100)

# ===== STEP 1: CHECK INFLUXDB RAW DATA =====
print("\n" + "=" * 100)
print("STEP 1: CHECKING RAW DATA IN INFLUXDB")
print("=" * 100)

query = "SELECT * FROM producao ORDER BY time DESC LIMIT 5"
result = client.query(query)
points = list(result.get_points())

if not points:
    print("\n✗ CRITICAL: No data in InfluxDB!")
    print("  → Check if coletor is running")
    print("  → Check if Flask is receiving data")
    sys.exit(1)

print(f"\n✓ Found {len(points)} recent points")

# Analyze first point in detail
p = points[0]
print("\n" + "-" * 100)
print("MOST RECENT DATA POINT:")
print("-" * 100)

# Tags (should be indexed)
print("\nTAGS (for filtering):")
print(f"  equipamento_codigo: '{p.get('equipamento_codigo')}'")
print(f"  linha_codigo: '{p.get('linha_codigo')}'")
print(f"  ordem_producao: '{p.get('ordem_producao')}' (type: {type(p.get('ordem_producao')).__name__})")
print(f"  sku_codigo: '{p.get('sku_codigo')}' (type: {type(p.get('sku_codigo')).__name__})")
print(f"  formato_gramas: '{p.get('formato_gramas')}' (type: {type(p.get('formato_gramas')).__name__})")
print(f"  descricao: '{p.get('descricao')}'")

# Fields (metrics)
print("\nFIELDS (metrics):")
print(f"  contagem_entrada: {p.get('contagem_entrada')}")
print(f"  contagem_saida: {p.get('contagem_saida')}")
print(f"  descarte: {p.get('descarte')}")
print(f"  velocidade_atual: {p.get('velocidade_atual')}")

# CRITICAL: Check production accumulation fields
print("\nPRODUCTION ACCUMULATION FIELDS (CRITICAL):")
prod_op = p.get('producao_acumulada_op')
prod_sku = p.get('producao_acumulada_sku')

if prod_op is not None:
    print(f"  ✓ producao_acumulada_op: {prod_op} ton")
else:
    print(f"  ✗ producao_acumulada_op: MISSING!")
    print(f"     → This field should be calculated by Flask")
    print(f"     → Check Flask logs for [OP ACUM] messages")

if prod_sku is not None:
    print(f"  ✓ producao_acumulada_sku: {prod_sku} ton")
else:
    print(f"  ✗ producao_acumulada_sku: MISSING!")
    print(f"     → This field should be calculated by Flask")
    print(f"     → Check Flask logs for [SKU ACUM] messages")

# Extract current values for testing
equipamento_codigo = p.get('equipamento_codigo')
ordem_producao = p.get('ordem_producao')
sku_codigo = p.get('sku_codigo')
formato_gramas = p.get('formato_gramas')

# ===== STEP 2: VERIFY TAG STRUCTURE =====
print("\n" + "=" * 100)
print("STEP 2: VERIFYING TAG STRUCTURE")
print("=" * 100)

query_tags = "SHOW TAG KEYS FROM producao"
result_tags = client.query(query_tags)
tag_keys = [t['tagKey'] for t in result_tags.get_points()]

print(f"\nTag keys in database: {tag_keys}")

required_tags = ['equipamento_codigo', 'linha_codigo', 'ordem_producao', 'sku_codigo', 'formato_gramas']
for tag in required_tags:
    if tag in tag_keys:
        print(f"  ✓ {tag}")
    else:
        print(f"  ✗ {tag} MISSING!")

# ===== STEP 3: TEST QUERY BY OP (TAG FILTERING) =====
print("\n" + "=" * 100)
print("STEP 3: TESTING QUERY BY ORDEM_PRODUCAO TAG")
print("=" * 100)

if ordem_producao:
    print(f"\nQuerying for OP: '{ordem_producao}'")
    
    # Test 1: Simple filter
    query_op = f"SELECT * FROM producao WHERE ordem_producao = '{ordem_producao}' LIMIT 5"
    print(f"\nQuery: {query_op}")
    
    result_op = client.query(query_op)
    points_op = list(result_op.get_points())
    
    if points_op:
        print(f"  ✓ Found {len(points_op)} points for OP '{ordem_producao}'")
        print(f"    First contagem_saida: {points_op[0].get('contagem_saida')}")
        print(f"    Last contagem_saida: {points_op[-1].get('contagem_saida')}")
    else:
        print(f"  ✗ NO RESULTS for OP '{ordem_producao}'!")
        print(f"     → Tag filtering is not working")
        print(f"     → Check if ordem_producao is stored as TAG (not field)")
    
    # Test 2: Aggregation (min/max for production calculation)
    query_agg = f"""
        SELECT min("contagem_saida") as primeira, max("contagem_saida") as ultima
        FROM producao
        WHERE ordem_producao = '{ordem_producao}'
    """
    print(f"\nAggregation query:")
    print(f"  {query_agg.strip()}")
    
    result_agg = client.query(query_agg)
    points_agg = list(result_agg.get_points())
    
    if points_agg and points_agg[0].get('primeira') is not None:
        primeira = points_agg[0].get('primeira')
        ultima = points_agg[0].get('ultima')
        delta = ultima - primeira
        
        print(f"\n  ✓ Aggregation successful:")
        print(f"    Primeira contagem: {primeira}")
        print(f"    Última contagem: {ultima}")
        print(f"    Delta (produção): {delta} peças")
        
        if formato_gramas:
            try:
                formato_float = float(formato_gramas)
                toneladas = (delta * formato_float) / 1000000.0
                print(f"    Toneladas: {toneladas:.3f} ton")
            except:
                pass
    else:
        print(f"  ✗ Aggregation failed!")
else:
    print("\n✗ No ordem_producao in data - cannot test")

# ===== STEP 4: TEST QUERY BY SKU (TAG FILTERING) =====
print("\n" + "=" * 100)
print("STEP 4: TESTING QUERY BY SKU_CODIGO TAG")
print("=" * 100)

if sku_codigo:
    print(f"\nQuerying for SKU: '{sku_codigo}'")
    
    query_sku = f"SELECT * FROM producao WHERE sku_codigo = '{sku_codigo}' LIMIT 5"
    print(f"\nQuery: {query_sku}")
    
    result_sku = client.query(query_sku)
    points_sku = list(result_sku.get_points())
    
    if points_sku:
        print(f"  ✓ Found {len(points_sku)} points for SKU '{sku_codigo}'")
    else:
        print(f"  ✗ NO RESULTS for SKU '{sku_codigo}'!")
else:
    print("\n✗ No sku_codigo in data - cannot test")

# ===== STEP 5: TEST DJANGO HELPER FUNCTIONS =====
print("\n" + "=" * 100)
print("STEP 5: TESTING DJANGO HELPER FUNCTIONS")
print("=" * 100)

if equipamento_codigo and ordem_producao and formato_gramas:
    print(f"\nTesting get_production_by_op()...")
    print(f"  Equipamento: {equipamento_codigo}")
    print(f"  OP: {ordem_producao}")
    print(f"  Formato: {formato_gramas}g")
    
    try:
        formato_float = float(formato_gramas)
        result_helper = get_production_by_op(equipamento_codigo, ordem_producao, formato_float, client)
        
        print(f"\n  Result from helper function:")
        print(f"    toneladas_op: {result_helper['toneladas_op']}")
        print(f"    contagem_op: {result_helper['contagem_op']}")
        print(f"    primeira_contagem: {result_helper['primeira_contagem']}")
        print(f"    ultima_contagem: {result_helper['ultima_contagem']}")
        
        if result_helper['toneladas_op'] > 0:
            print(f"\n  ✓ Helper function working!")
        else:
            print(f"\n  ⚠ Helper function returned 0 - check query")
            
    except Exception as e:
        print(f"\n  ✗ Helper function failed: {e}")
        import traceback
        traceback.print_exc()

# ===== STEP 6: COMPARE WITH SHIFT LOGIC =====
print("\n" + "=" * 100)
print("STEP 6: COMPARING WITH WORKING SHIFT LOGIC")
print("=" * 100)

print("\nHow shift production works (REFERENCE):")
print("  1. Coletor sends: contagem_saida, formato_gramas")
print("  2. Flask calculates: toneladas_turno = contagem_saida * formato_gramas / 1000000")
print("  3. InfluxDB stores: contagem_saida (field), formato_gramas (tag)")
print("  4. Django reads: last(contagem_saida) and multiplies by formato")

print("\nHow OP/SKU production SHOULD work:")
print("  1. Coletor sends: contagem_saida, ordem_producao, sku_codigo, formato_gramas")
print("  2. Flask calculates: producao_acumulada_op = contagem_saida * formato_gramas / 1000000")
print("  3. Flask stores: producao_acumulada_op (field), ordem_producao (tag)")
print("  4. Django reads: last(producao_acumulada_op) WHERE ordem_producao = 'X'")

# ===== STEP 7: DIAGNOSIS SUMMARY =====
print("\n" + "=" * 100)
print("DIAGNOSIS SUMMARY")
print("=" * 100)

issues = []
fixes = []

if not points:
    issues.append("No data in InfluxDB")
    fixes.append("Check coletor and Flask are running")

if ordem_producao is None or str(ordem_producao).strip() == '':
    issues.append("ordem_producao is empty/None")
    fixes.append("Check coletor is sending ordem_producao from OPC")

if 'ordem_producao' not in tag_keys:
    issues.append("ordem_producao not stored as TAG")
    fixes.append("Check Flask app.py - should extract ordem_producao as tag")

if prod_op is None:
    issues.append("producao_acumulada_op field missing")
    fixes.append("Check Flask app.py - should calculate this field BEFORE extracting tags")

if ordem_producao and not points_op:
    issues.append("Query by ordem_producao returns no results")
    fixes.append("ordem_producao might not be stored as tag, or value mismatch")

if issues:
    print("\n✗ ISSUES FOUND:")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
    
    print("\n→ RECOMMENDED FIXES:")
    for i, fix in enumerate(fixes, 1):
        print(f"  {i}. {fix}")
else:
    print("\n✓ NO ISSUES FOUND - Data flow appears correct")
    print("  → If frontend still not showing data, check Django views.py")

print("\n" + "=" * 100)
print("NEXT STEPS:")
print("=" * 100)
print("1. Review Flask logs for [OP ACUM] and [INFLUX] messages")
print("2. Check coletor logs for ordem_producao values being sent")
print("3. Verify Flask app.py code order (calculate fields BEFORE extracting tags)")
print("4. Test Django endpoint: /api/metricas_fabrica_consolidadas/")
print("=" * 100)
