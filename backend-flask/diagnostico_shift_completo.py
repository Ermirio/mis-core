"""
DIAGNÓSTICO COMPLETO E DEFINITIVO
Vamos entender EXATAMENTE o que está sendo salvo e lido do InfluxDB
"""
from influxdb import InfluxDBClient
from datetime import datetime
import sys
sys.path.insert(0, '.')
from production_engine import get_engine

print("="*80)
print("DIAGNÓSTICO COMPLETO - POR QUE TURNO RETORNA N/A?")
print(f"Hora atual: {datetime.now()}")
print("="*80)

client = InfluxDBClient('localhost', 8086, 'admin', 'ixvq10A@10', 'industrial_db')

# 1. O QUE O PRODUCTION ENGINE DETECTA?
print("\n" + "="*80)
print("1. PRODUCTION ENGINE - O que detecta agora?")
print("="*80)
engine = get_engine(client, 'http://localhost:8000/api')
turno_engine = engine.shift_manager.get_turno_atual()
print(f"   Turno detectado: '{turno_engine}'")

# 2. O QUE ESTÁ SENDO SALVO NO INFLUXDB?
print("\n" + "="*80)
print("2. INFLUXDB - Últimos 5 pontos salvos (TAGS e FIELDS)")
print("="*80)

# Mostrar a estrutura completa do último ponto
query = "SELECT * FROM production WHERE equipment='E001' ORDER BY time DESC LIMIT 1"
result = client.query(query)
points = list(result.get_points())

if points:
    print("\n   ESTRUTURA DO ÚLTIMO PONTO:")
    ponto = points[0]
    print(f"   Total de campos: {len(ponto.keys())}")
    print(f"\n   Campos disponíveis:")
    for key in sorted(ponto.keys()):
        value = ponto[key]
        if isinstance(value, str) and len(value) > 50:
            value = value[:50] + "..."
        print(f"     {key:30} = {value}")
else:
    print("   NENHUM ponto encontrado!")

# 3. TESTAR QUERY COM SHIFT
print("\n" + "="*80)
print("3. TESTANDO QUERIES DIFERENTES PARA BUSCAR SHIFT")
print("="*80)

# Query 3a: SELECT shift (campo direto)
print("\n   3a. SELECT shift FROM production WHERE equipment='E001' ORDER BY time DESC LIMIT 1")
result = client.query("SELECT shift FROM production WHERE equipment='E001' ORDER BY time DESC LIMIT 1")
points = list(result.get_points())
if points:
    shift_value = points[0].get('shift', 'NÃO ENCONTRADO')
    print(f"      Resultado: shift = '{shift_value}'")
else:
    print("      Sem resultados")

# Query 3b: Buscar tags via show tag values
print("\n   3b. SHOW TAG VALUES FROM production WITH KEY = shift WHERE equipment='E001'")
try:
    result = client.query("SHOW TAG VALUES FROM production WITH KEY = shift WHERE equipment='E001'")
    points = list(result.get_points())
    if points:
        print(f"      Valores de shift encontrados: {[p.get('value') for p in points]}")
    else:
        print("      Sem resultados")
except Exception as e:
    print(f"      Erro: {e}")

# Query 3c: SELECT com GROUP BY tags
print("\n   3c. SELECT time, shift FROM production WHERE equipment='E001' ORDER BY time DESC LIMIT 3")
result = client.query("SELECT time, shift FROM production WHERE equipment='E001' ORDER BY time DESC LIMIT 3")
points = list(result.get_points())
if points:
    print(f"      Últimos 3 valores:")
    for i, p in enumerate(points, 1):
        shift = p.get('shift', 'vazio')
        time = p.get('time', '?')
        print(f"      [{i}] time={time} | shift='{shift}'")
else:
    print("      Sem resultados")

# 4. TESTAR A QUERY EXATA DA API
print("\n" + "="*80)
print("4. QUERY EXATA QUE A API USA AGORA")
print("="*80)

eq_code = 'E001'

# Query 1: Fields
print("\n   Query 1: SELECT last(*) FROM production WHERE equipment='E001'")
result_fields = client.query(f"SELECT last(*) FROM production WHERE \"equipment\" = '{eq_code}'")
points_fields = list(result_fields.get_points())

if points_fields:
    data = points_fields[0]
    print(f"   ✓ Retornou {len(data.keys())} campos")
    print(f"   Campos com 'shift': {[k for k in data.keys() if 'shift' in k.lower()]}")
else:
    print("   ✗ Sem resultados")

# Query 2: Tag shift
print("\n   Query 2: SELECT shift FROM production WHERE equipment='E001' ORDER BY time DESC LIMIT 1")
result_shift = client.query(f"SELECT shift FROM production WHERE \"equipment\" = '{eq_code}' ORDER BY time DESC LIMIT 1")
points_shift = list(result_shift.get_points())

if points_shift:
    turno_api = points_shift[0].get('shift', 'NÃO ENCONTRADO')
    print(f"   ✓ shift = '{turno_api}'")
else:
    print("   ✗ Sem resultados")
    turno_api = 'N/A'

# 5. CONCLUSÃO
print("\n" + "="*80)
print("5. CONCLUSÃO E DIAGNÓSTICO")
print("="*80)

print(f"\n   ProductionEngine detecta: '{turno_engine}'")
print(f"   API deveria retornar: '{turno_api}'")

if turno_api == 'N/A' or turno_api == 'NÃO ENCONTRADO':
    print("\n   ❌ PROBLEMA CONFIRMADO: shift não está sendo salvo corretamente!")
    print("\n   POSSÍVEIS CAUSAS:")
    print("   1. O coletor não está enviando dados")
    print("   2. A rota /api/dados/inserir não está salvando o campo 'shift'")
    print("   3. O campo shift está sendo salvo com outro nome")
    print("   4. engine_result['turno_atual_nome'] está retornando 'N/A'")
elif turno_api == turno_engine:
    print("\n   ✅ TUDO CORRETO! Shift está sendo salvo e lido corretamente")
else:
    print(f"\n   ⚠️  INCONSISTÊNCIA: Engine='{turno_engine}' vs InfluxDB='{turno_api}'")

print("\n" + "="*80)
