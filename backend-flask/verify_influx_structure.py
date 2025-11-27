"""
Verify InfluxDB Tag Structure
Checks that the new tag-based structure is working correctly
"""
from influxdb import InfluxDBClient
from decouple import config
import time

# InfluxDB configuration
INFLUX_HOST = config('INFLUXDB_HOST', default='127.0.0.1')
INFLUX_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUX_DB = config('INFLUXDB_DATABASE', default='industrial_db')
INFLUX_USER = config('INFLUXDB_USER', default=None)
INFLUX_PASS = config('INFLUXDB_USER_PASSWORD', default=None)

print("=" * 80)
print("VERIFYING INFLUXDB TAG STRUCTURE")
print("=" * 80)

try:
    # Connect to InfluxDB
    client = InfluxDBClient(
        host=INFLUX_HOST,
        port=INFLUX_PORT,
        username=INFLUX_USER,
        password=INFLUX_PASS,
        database=INFLUX_DB
    )
    
    print(f"\n✓ Connected to InfluxDB at {INFLUX_HOST}:{INFLUX_PORT}/{INFLUX_DB}")
    
    # Wait a moment for data to be collected
    print("\nWaiting 5 seconds for data collection...")
    time.sleep(5)
    
    # 1. Check tag keys
    print("\n" + "-" * 80)
    print("1. TAG KEYS IN 'producao' MEASUREMENT:")
    print("-" * 80)
    
    result = client.query("SHOW TAG KEYS FROM producao")
    tag_keys = list(result.get_points())
    
    if tag_keys:
        print("\n✓ Found tags:")
        for tag in tag_keys:
            print(f"  - {tag['tagKey']}")
        
        # Expected tags
        expected_tags = ['equipamento_codigo', 'linha_codigo', 'ordem_producao', 
                        'sku_codigo', 'formato_gramas', 'descricao']
        found_tags = [tag['tagKey'] for tag in tag_keys]
        
        print("\n✓ Expected tags:")
        for tag in expected_tags:
            status = "✓" if tag in found_tags else "✗"
            print(f"  {status} {tag}")
    else:
        print("\n⚠ No tags found yet. Data may not have been collected.")
    
    # 2. Check field keys
    print("\n" + "-" * 80)
    print("2. FIELD KEYS IN 'producao' MEASUREMENT:")
    print("-" * 80)
    
    result = client.query("SHOW FIELD KEYS FROM producao")
    field_keys = list(result.get_points())
    
    if field_keys:
        print("\n✓ Found fields:")
        for field in field_keys:
            print(f"  - {field['fieldKey']} ({field['fieldType']})")
    else:
        print("\n⚠ No fields found yet. Data may not have been collected.")
    
    # 3. Check recent data
    print("\n" + "-" * 80)
    print("3. RECENT DATA (Last 3 points):")
    print("-" * 80)
    
    result = client.query("SELECT * FROM producao ORDER BY time DESC LIMIT 3")
    points = list(result.get_points())
    
    if points:
        print(f"\n✓ Found {len(points)} recent points:")
        for i, point in enumerate(points, 1):
            print(f"\n  Point {i}:")
            print(f"    Time: {point.get('time')}")
            print(f"    Equipamento: {point.get('equipamento_codigo')}")
            print(f"    Linha: {point.get('linha_codigo')}")
            print(f"    OP: {point.get('ordem_producao')}")
            print(f"    SKU: {point.get('sku_codigo')}")
            print(f"    Formato: {point.get('formato_gramas')}g")
            print(f"    Contagem Saída: {point.get('contagem_saida')}")
    else:
        print("\n⚠ No data points found yet.")
        print("   Please wait a few minutes for the coletor to collect data.")
    
    # 4. Test query by OP
    print("\n" + "-" * 80)
    print("4. TEST QUERY BY ORDEM_PRODUCAO:")
    print("-" * 80)
    
    if points and points[0].get('ordem_producao'):
        op_test = points[0].get('ordem_producao')
        query = f"SELECT * FROM producao WHERE ordem_producao = '{op_test}' LIMIT 3"
        print(f"\nQuery: {query}")
        
        result = client.query(query)
        op_points = list(result.get_points())
        
        if op_points:
            print(f"✓ Query successful! Found {len(op_points)} points for OP '{op_test}'")
        else:
            print(f"✗ Query returned no results for OP '{op_test}'")
    else:
        print("\n⚠ Cannot test - no OP data available yet")
    
    # 5. Test query by SKU
    print("\n" + "-" * 80)
    print("5. TEST QUERY BY SKU_CODIGO:")
    print("-" * 80)
    
    if points and points[0].get('sku_codigo'):
        sku_test = points[0].get('sku_codigo')
        query = f"SELECT * FROM producao WHERE sku_codigo = '{sku_test}' LIMIT 3"
        print(f"\nQuery: {query}")
        
        result = client.query(query)
        sku_points = list(result.get_points())
        
        if sku_points:
            print(f"✓ Query successful! Found {len(sku_points)} points for SKU '{sku_test}'")
        else:
            print(f"✗ Query returned no results for SKU '{sku_test}'")
    else:
        print("\n⚠ Cannot test - no SKU data available yet")
    
    print("\n" + "=" * 80)
    print("✓ VERIFICATION COMPLETE")
    print("=" * 80)
    
    if tag_keys and field_keys and points:
        print("\n✓ SUCCESS: New tag structure is working correctly!")
        print("\nNext steps:")
        print("1. Check frontend (Home page) - production by OP should work")
        print("2. Check Line Details - all metrics should display")
        print("3. Monitor Flask logs for [INFLUX] tag messages")
    else:
        print("\n⚠ WAITING: Data collection in progress...")
        print("   Run this script again in 2-3 minutes")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
