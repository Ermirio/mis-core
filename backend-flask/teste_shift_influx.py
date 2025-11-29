"""
Teste simples: O que está sendo salvo REALMENTE no InfluxDB?
"""
from influxdb import InfluxDBClient

client = InfluxDBClient('localhost', 8086, 'admin', 'ixvq10A@10', 'industrial_db')

print("="*70)
print("TESTE DEFINITIVO: O que shift contém no InfluxDB?")
print("="*70)

# Pegar dados crus sem filtros
query = """
SELECT time, "shift", "producao_op_acumulada", "ordem_producao_field"
FROM "production" 
WHERE "equipment" = 'E001'
ORDER BY time DESC 
LIMIT 5
"""

print(f"\nQuery:\n{query}\n")

try:
    result = client.query(query)
    points = list(result.get_points())
    
    print(f"Pontos retornados: {len(points)}\n")
    
    if points:
        for i, p in enumerate(points, 1):
            time_val = p.get('time', 'sem time')
            shift_val = p.get('shift', 'CAMPO NÃO EXISTE')
            prod = p.get('producao_op_acumulada', 0)
            op = p.get('ordem_producao_field', '?')
            
            print(f"[{i}] time: {time_val}")
            print(f"    shift: '{shift_val}'")
            print(f"    producao_op: {prod}")
            print(f"    OP: {op}")
            print()
    else:
        print("NENHUM ponto retornado!")
        
except Exception as e:
    print(f"ERRO: {e}")

# Agora teste direto com tag
print("\n" + "="*70)
print("Teste 2: Buscar shift diretamente")
print("="*70)

try:
    # Tentar buscar shift como field
    result = client.query("SELECT shift FROM production WHERE equipment='E001' ORDER BY time DESC LIMIT 1")
    points = list(result.get_points())
    
    if points:
        shift = points[0].get('shift', 'NÃO RETORNOU')
        print(f"shift retornado: '{shift}'")
        
        # Ver TODOS os campos retornados
        print(f"\nTodos os campos: {list(points[0].keys())}")
    else:
        print("Sem resultados")
except Exception as e:
    print(f"ERRO: {e}")
