from influxdb import InfluxDBClient

# Configuração
host = 'localhost'
port = 8086
dbname = 'industrial_db'

client = InfluxDBClient(host, port, 'root', 'root', dbname)

# Query 1: Ver últimos dados da OP 2222222
print("=" * 60)
print("ÚLTIMOS 5 PONTOS DA OP 2222222:")
print("=" * 60)
query1 = """
SELECT * FROM producao 
WHERE "ordem_producao" = '2222222' 
ORDER BY time DESC 
LIMIT 5
"""
result1 = client.query(query1)
points1 = list(result1.get_points())
for i, p in enumerate(points1, 1):
    print(f"\n{i}. Time: {p.get('time')}")
    print(f"   Equipamento: {p.get('equipamento_codigo')}")
    print(f"   Contagem Saída: {p.get('contagem_saida')}")
    print(f"   Formato: {p.get('formato_gramas')}")
    print(f"   Planejado OP: {p.get('planejado_op')}")

# Query 2: Delta de contagem
print("\n" + "=" * 60)
print("DELTA DE CONTAGEM (MAX - MIN) PARA OP 2222222 NO EQUIPAMENTO 003:")
print("=" * 60)
query2 = """
SELECT max("contagem_saida") - min("contagem_saida") as delta_contagem
FROM "producao"
WHERE "ordem_producao" = '2222222' 
AND "equipamento_codigo" = '003'
"""
result2 = client.query(query2)
points2 = list(result2.get_points())
if points2:
    delta = points2[0].get('delta_contagem')
    print(f"Delta: {delta}")
    if delta:
        print(f"Delta (float): {float(delta)}")
else:
    print("Nenhum resultado")

# Query 3: Último formato
print("\n" + "=" * 60)
print("ÚLTIMO FORMATO DO EQUIPAMENTO 003:")
print("=" * 60)
query3 = """
SELECT last("formato_gramas") as formato
FROM "producao"
WHERE "equipamento_codigo" = '003'
"""
result3 = client.query(query3)
points3 = list(result3.get_points())
if points3:
    formato = points3[0].get('formato')
    print(f"Formato: {formato}")
else:
    print("Nenhum resultado")

print("\n" + "=" * 60)
