from influxdb import InfluxDBClient
from decouple import config
import time

# Configuração manual
HOST = '127.0.0.1'
PORT = 8086
USER = 'admin'
PASS = 'admin123' # Password from .env
DB = 'industrial_db'

print(f"Conectando ao InfluxDB {HOST}:{PORT} ({DB})...")
client = InfluxDBClient(host=HOST, port=PORT, username=USER, password=PASS, database=DB)

def check_e001():
    print("\n--- VERIFICANDO EQUIPAMENTO 'E001' ---")
    
    query = """
        SELECT time, oee_realtime, performance_realtime, availability_realtime, quality_realtime, velocidade_atual, estado_maquina
        FROM "production"
        WHERE "equipment" = 'E001'
        ORDER BY time DESC
        LIMIT 10
    """
    
    print(f"Executando query...")
    try:
        result = client.query(query)
        points = list(result.get_points())
        
        if not points:
            print("❌ NENHUM DADO ENCONTRADO para E001")
            return

        print(f"\n✅ Encontrados {len(points)} pontos recentes:")
        print(f"{'Time':<20} | {'OEE':<6} | {'Perf':<6} | {'Avail':<6} | {'Qual':<6} | {'Vel':<6} | {'Est':<3}")
        print("-" * 80)
        
        for p in points:
            time_str = p.get('time', '')[11:19] # HH:MM:SS
            oee = float(p.get('oee_realtime', 0) or 0)
            perf = float(p.get('performance_realtime', 0) or 0)
            avail = float(p.get('availability_realtime', 0) or 0)
            qual = float(p.get('quality_realtime', 0) or 0)
            vel = int(p.get('velocidade_atual', 0) or 0)
            est = int(p.get('estado_maquina', 0) or 0)
            
            print(f"{time_str:<20} | {oee:>6.1f} | {perf:>6.1f} | {avail:>6.1f} | {qual:>6.1f} | {vel:>6} | {est:>3}")

    except Exception as e:
        print(f"Erro na query: {e}")

if __name__ == "__main__":
    check_e001()
