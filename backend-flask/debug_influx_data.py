from influxdb import InfluxDBClient
from decouple import config
import json
from datetime import datetime

# Configuração manual para garantir
HOST = '127.0.0.1'
PORT = 8086
USER = 'admin'
PASS = 'admin123'
DB = 'industrial_db'

print(f"Conectando ao InfluxDB {HOST}:{PORT} ({DB})...")
client = InfluxDBClient(host=HOST, port=PORT, username=USER, password=PASS, database=DB)

def debug_query():
    print("\n--- ÚLTIMOS 5 PONTOS NA MEASUREMENT 'production' ---")
    try:
        # Query raw data
        result = client.query("SELECT * FROM production ORDER BY time DESC LIMIT 5")
        points = list(result.get_points())
        
        if not points:
            print("❌ NENHUM DADO ENCONTRADO na measurement 'production'")
            return

        print(f"✅ Encontrados {len(points)} pontos recentess:")
        for i, p in enumerate(points):
            print(f"\n[{i+1}] Time: {p.get('time')}")
            print(f"    Equipment: {p.get('equipment')} (Tag)")
            print(f"    Line: {p.get('line')} (Tag)")
            print(f"    Contagem Saída: {p.get('contagem_saida')}")
            print(f"    Formato: {p.get('formato_gramas')}")
            print(f"    OP: {p.get('order_id')}")
            
    except Exception as e:
        print(f"Erro ao consultar: {e}")

def check_equipment_002():
    print("\n--- VERIFICANDO ESPECIFICAMENTE EQUIPAMENTO '002' ---")
    try:
        query = "SELECT * FROM production WHERE equipment = '002' ORDER BY time DESC LIMIT 3"
        result = client.query(query)
        points = list(result.get_points())
        
        if not points:
            print("❌ NENHUM DADO para equipment='002'")
            
            # Tenta listar quais equipments existem
            print("\nListando equipamentos disponíveis:")
            res = client.query("SHOW TAG VALUES FROM production WITH KEY = equipment")
            for p in res.get_points():
                print(f" - {p['value']}")
    except Exception as e:
        print(f"Erro: {e}")

def check_equipment_003():
    print("\n--- VERIFICANDO EQUIPAMENTO '003' (Zuchinni) ---")
    EQUIPAMENTO_CODIGO = '003'
    
    # Query para verificar dados recentes com tags
    query = f"""
        SELECT * 
        FROM "production" 
        WHERE "equipment" = '{EQUIPAMENTO_CODIGO}' 
        GROUP BY *
        ORDER BY time DESC 
        LIMIT 5
    """
    
    print(f"\nExecutando query: {query}")
    
    try:
        result = client.query(query)
        points = list(result.get_points())
        
        print(f"\nEncontrados {len(points)} pontos:")
        for p in points:
            print(f"Time: {p.get('time')}")
            print(f"Keys: {list(p.keys())}")
            print(f"Estado: {p.get('estado_maquina')}")
            print("-" * 30)
            
    except Exception as e:
        print(f"Erro na query: {e}")

if __name__ == "__main__":
    check_equipment_003()
