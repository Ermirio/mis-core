import os
import sys
import django

# Setup Django
sys.path.append('C:\\Users\\ermir\\Documents\\GitHub\\projeto-monitoramento-industrial-completo\\backend-django')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from influxdb import InfluxDBClient
from equipamentos.models import HistoricoSKU

# Configuração InfluxDB
host = 'localhost'
port = 8086
dbname = 'industrial_db'

client = InfluxDBClient(host, port, 'root', 'root', dbname)

print("=" * 80)
print("INVESTIGAÇÃO: PRODUÇÃO POR OP")
print("=" * 80)

# 1. Verificar OP atual no InfluxDB
print("\n1. OP ATUAL NO INFLUXDB (últimos 5 pontos):")
print("-" * 80)
query1 = """
SELECT "ordem_producao", "sku_codigo", "contagem_saida", "equipamento_codigo"
FROM "producao"
WHERE "equipamento_codigo" = '003'
ORDER BY time DESC
LIMIT 5
"""
result1 = client.query(query1)
points1 = list(result1.get_points())
for i, p in enumerate(points1, 1):
    print(f"{i}. OP: {p.get('ordem_producao')}, SKU: {p.get('sku_codigo')}, "
          f"Contagem: {p.get('contagem_saida')}, Equip: {p.get('equipamento_codigo')}")

# 2. Verificar dados da OP 2546582 (atual)
print("\n2. DADOS DA OP 2546582 (ATUAL):")
print("-" * 80)
query2 = """
SELECT first("contagem_saida") as primeira, last("contagem_saida") as ultima, count("contagem_saida") as total_pontos
FROM "producao"
WHERE "equipamento_codigo" = '003'
AND "ordem_producao" = '2546582'
"""
result2 = client.query(query2)
points2 = list(result2.get_points())
if points2:
    p = points2[0]
    print(f"Primeira contagem: {p.get('primeira')}")
    print(f"Última contagem: {p.get('ultima')}")
    print(f"Total de pontos: {p.get('total_pontos')}")
    if p.get('primeira') and p.get('ultima'):
        delta = float(p.get('ultima')) - float(p.get('primeira'))
        print(f"Delta: {delta}")
        toneladas = (delta * 2200.0) / 1000000.0
        print(f"Toneladas (formato 2200g): {toneladas:.3f} ton")
else:
    print("Nenhum dado encontrado!")

# 3. Verificar dados da OP 2222222 (anterior)
print("\n3. DADOS DA OP 2222222 (ANTERIOR):")
print("-" * 80)
query3 = """
SELECT first("contagem_saida") as primeira, last("contagem_saida") as ultima, count("contagem_saida") as total_pontos
FROM "producao"
WHERE "equipamento_codigo" = '003'
AND "ordem_producao" = '2222222'
"""
result3 = client.query(query3)
points3 = list(result3.get_points())
if points3:
    p = points3[0]
    print(f"Primeira contagem: {p.get('primeira')}")
    print(f"Última contagem: {p.get('ultima')}")
    print(f"Total de pontos: {p.get('total_pontos')}")
    if p.get('primeira') and p.get('ultima'):
        delta = float(p.get('ultima')) - float(p.get('primeira'))
        print(f"Delta: {delta}")
        toneladas = (delta * 2200.0) / 1000000.0
        print(f"Toneladas (formato 2200g): {toneladas:.3f} ton")
else:
    print("Nenhum dado encontrado!")

# 4. Verificar histórico no MySQL
print("\n4. HISTÓRICO NO MYSQL (HistoricoSKU):")
print("-" * 80)
historicos = HistoricoSKU.objects.filter(
    linha_id=1
).order_by('-data_inicio')[:5]

print(f"Total de registros na linha 1: {HistoricoSKU.objects.filter(linha_id=1).count()}")
print("\nÚltimos 5 registros:")
for i, h in enumerate(historicos, 1):
    print(f"\n{i}. OP: {h.ordem_producao}")
    print(f"   SKU: {h.produto.codigo if h.produto else 'N/A'}")
    print(f"   Meta: {h.meta_producao}")
    print(f"   Produção Realizada: {h.producao_realizada}")
    print(f"   Data Início: {h.data_inicio}")
    print(f"   Data Fim: {h.data_fim}")

print("\n" + "=" * 80)
