from influxdb import InfluxDBClient
import sys

# Configuração
host = 'localhost'
port = 8086
dbname = 'industrial_db'

client = InfluxDBClient(host, port, 'root', 'root', dbname)

print("=" * 80)
print("DEBUG: INVESTIGANDO PRODUÇÃO POR OP")
print("=" * 80)

# 1. Verificar se há dados com ordem_producao
print("\n1. ÚLTIMOS 10 PONTOS COM ORDEM_PRODUCAO:")
print("-" * 80)
query1 = """
SELECT * FROM producao 
WHERE "ordem_producao" != '' 
ORDER BY time DESC 
LIMIT 10
"""
result1 = client.query(query1)
points1 = list(result1.get_points())
print(f"Total de pontos encontrados: {len(points1)}")
for i, p in enumerate(points1[:3], 1):  # Mostra apenas os 3 primeiros
    print(f"\n{i}. Time: {p.get('time')}")
    print(f"   Equipamento: {p.get('equipamento_codigo')}")
    print(f"   OP: {p.get('ordem_producao')}")
    print(f"   SKU: {p.get('sku_codigo')}")
    print(f"   Contagem: {p.get('contagem_saida')}")
    print(f"   Formato: {p.get('formato_gramas')}")

# 2. Testar query FIRST/LAST para OP 2222222
print("\n" + "=" * 80)
print("2. TESTE FIRST/LAST PARA OP 2222222 NO EQUIPAMENTO 003:")
print("-" * 80)
query2 = """
SELECT first("contagem_saida") as primeira, last("contagem_saida") as ultima
FROM "producao"
WHERE "equipamento_codigo" = '003'
AND "ordem_producao" = '2222222'
"""
result2 = client.query(query2)
points2 = list(result2.get_points())
print(f"Resultado da query: {points2}")

if points2:
    primeira = points2[0].get('primeira')
    ultima = points2[0].get('ultima')
    print(f"\nPrimeira contagem: {primeira}")
    print(f"Última contagem: {ultima}")
    
    if primeira is not None and ultima is not None:
        delta = float(ultima) - float(primeira)
        print(f"Delta: {delta}")
        
        # Assumindo formato 2200g
        formato = 2200.0
        toneladas = (delta * formato) / 1000000.0
        print(f"Toneladas (com formato {formato}g): {toneladas:.3f} ton")
    else:
        print("PROBLEMA: primeira ou ultima é None!")
else:
    print("PROBLEMA: Query não retornou resultados!")

# 3. Verificar quantos pontos existem para esta OP
print("\n" + "=" * 80)
print("3. CONTAGEM DE PONTOS PARA OP 2222222:")
print("-" * 80)
query3 = """
SELECT COUNT("contagem_saida") FROM "producao"
WHERE "ordem_producao" = '2222222'
AND "equipamento_codigo" = '003'
"""
result3 = client.query(query3)
points3 = list(result3.get_points())
print(f"Total de pontos: {points3}")

# 4. Verificar se o problema é com aspas/tipo
print("\n" + "=" * 80)
print("4. TESTANDO DIFERENTES FORMATOS DE QUERY:")
print("-" * 80)

# Teste sem aspas
query4a = """
SELECT first(contagem_saida) as primeira, last(contagem_saida) as ultima
FROM producao
WHERE equipamento_codigo = '003'
AND ordem_producao = '2222222'
"""
print("\nTeste SEM aspas nos campos:")
try:
    result4a = client.query(query4a)
    points4a = list(result4a.get_points())
    print(f"Resultado: {points4a}")
except Exception as e:
    print(f"Erro: {e}")

print("\n" + "=" * 80)
