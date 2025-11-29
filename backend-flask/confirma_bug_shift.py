"""
Script para confirmar que shift está como TAG e não como FIELD
"""
from influxdb import InfluxDBClient

client = InfluxDBClient('localhost', 8086, 'admin', 'ixvq10A@10', 'industrial_db')

print("="*70)
print("CONFIRMAÇÃO DO BUG: shift como TAG vs FIELD")
print("="*70)

# Query 1: SELECT last(*) - NÃO retorna tags!
print("\n1. Query: SELECT last(*) FROM production (como a API faz)")
result = client.query("SELECT last(*) FROM production WHERE equipment='E001'")
points = list(result.get_points())
if points:
    data = points[0]
    print(f"   Campos retornados: {len(data.keys())}")
    has_shift = 'last_shift' in data
    print(f"   'last_shift' existe? {has_shift}")
    if not has_shift:
        print(f"   ✗ Campo NÃO EXISTE! Por isso API retorna N/A")
else:
    print("   Sem dados")

# Query 2: SELECT com tag shift - Mostra a tag!
print("\n2. Query: SELECT shift,* FROM production (acessando a TAG)")
result = client.query("SELECT shift,producao_turno_acumulada FROM production WHERE equipment='E001' ORDER BY time DESC LIMIT 1")
points = list(result.get_points())
if points:
    data = points[0]
    shift_tag = data.get('shift', 'vazio')
    prod_turno = data.get('producao_turno_acumulada', 0)
    print(f"   shift (TAG) = '{shift_tag}'")
    print(f"   producao_turno = {prod_turno}")
    if shift_tag != 'N/A':
        print(f"   ✓ TAG shift TEM VALOR CORRETO!")
    else:
        print(f"   ✗ TAG shift também é N/A")
else:
    print("   Sem dados")

print("\n" + "="*70)
print("CONCLUSÃO:")
print("="*70)
print("O turno está sendo salvo como TAG no InfluxDB.")
print("A query 'SELECT last(*)' NÃO retorna tags, apenas fields.")
print("Por isso 'last_shift' não existe e a API retorna 'N/A'.")
print("\nSOLUÇÃO: Mudar 'shift' de TAG para FIELD no código de ingestão.")
print("="*70)
