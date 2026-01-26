from influxdb import InfluxDBClient
from django.conf import settings
import os
import django

# Setup Django standalone
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

client = InfluxDBClient(
    host=settings.INFLUXDB_HOST,
    port=settings.INFLUXDB_PORT,
    username=settings.INFLUXDB_USER,
    password=settings.INFLUXDB_PASSWORD,
    database=settings.INFLUXDB_DATABASE
)

print("--- DIAGNÓSTICO INFLUXDB ---")
print(f"Conectado a: {settings.INFLUXDB_HOST}:{settings.INFLUXDB_PORT} / DB: {settings.INFLUXDB_DATABASE}")

# 1. Verificar se a measurement existe
measurements = client.get_list_measurements()
print(f"\nMeasurements encontradas: {[m['name'] for m in measurements]}")

# 2. Listar quais equipamentos têm 'ultimo_peso' nas últimas 24h
query = """
    SHOW TAG VALUES FROM "production" WITH KEY = "equipment" WHERE "ultimo_peso" != 0
"""
# Nota: 'WHERE field != 0' não funciona bem em SHOW TAG VALUES em versões antigas.
# Vamos tentar uma query bruta limitada.

query_raw = """
    SELECT "ultimo_peso", "equipment" 
    FROM "production" 
    WHERE time > now() - 1h 
    LIMIT 10
"""

print("\n--- AMOSTRA DE DADOS (Última 1h) ---")
try:
    result = list(client.query(query_raw).get_points())
    if not result:
        print("NENHUM dado de 'ultimo_peso' encontrado na última hora.")
        # Tenta 24h
        print("Tentando últimas 24h...")
        query_24h = """
            SELECT "ultimo_peso", "equipment" 
            FROM "production" 
            WHERE time > now() - 24h 
            LIMIT 10
        """
        result = list(client.query(query_24h).get_points())
    
    for p in result:
        print(f"Equipamento: {p.get('equipment')} | Peso: {p.get('ultimo_peso')}")

    # 3. Listar Equipamentos Únicos que enviaram peso
    print("\n--- EQUIPAMENTOS ATIVOS (Com Peso) ---")
    query_equip = """
        SELECT count("ultimo_peso") 
        FROM "production" 
        WHERE time > now() - 24h 
        GROUP BY "equipment"
    """
    result_equip = list(client.query(query_equip).get_points())
    for p in result_equip:
        print(f"Equipamento: {p.get('equipment')} | Pontos: {p.get('count')}")

except Exception as e:
    print(f"ERRO: {e}")
