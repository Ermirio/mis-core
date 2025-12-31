
from influxdb import InfluxDBClient
from datetime import datetime
import time



host = 'localhost'
port = 8086
username = 'admin'
password = 'admin123'
database = 'industrial_db'



client = InfluxDBClient(host, port, username, password, database)

EQUIPMENT = 'E001' # Ex: Filler
LINE_NORM = 'Linha 01'

print(f"--- DEBUG PROJECTION FOR {EQUIPMENT} ---")

# 1. Fetch LAST PRODUCTION Data (Tons, Speed, Format)
query_last = f"SELECT last(toneladas_turno), last(velocidade_atual), last(formato_gramas) FROM production WHERE \"equipment\" = '{EQUIPMENT}'"
rs = client.query(query_last)
pts = list(rs.get_points())

if not pts:
    print("NO DATA for this equipment in 'production'.")
else:
    p = pts[0]
    prod_real = float(p.get('last') or 0)
    vel = float(p.get('last_1') or 0)
    fmt = float(p.get('last_2') or 0)
    
    print(f"RAW Influx Values:")
    print(f"  Producao Real (toneladas_turno): {prod_real}")
    print(f"  Velocidade (velocidade_atual): {vel}")
    print(f"  Formato (formato_gramas): {fmt}")
    
    # 2. Replicate Rate Calculation
    # taxa_instantanea = (vel * 60 * fmt) / 1_000_000
    taxa = (vel * 60 * fmt) / 1_000_000
    print(f"CALC Taxa Instantanea (ton/h): {taxa}")
    
    if taxa > 100:
        print("!!! PREDICTION SPIKE DETECTED !!! Taxa > 100 ton/h is normally impossible.")
        if fmt > 5000:
            print("  -> SUSPICION: Formato might be in GRAINS or incorrect unit?")
        if vel > 100000:
            print("  -> SUSPICION: Velocity might be outlier?")

# 3. Check Last 5 points for Formato stability
query_hist = f"SELECT formato_gramas FROM production WHERE \"equipment\" = '{EQUIPMENT}' ORDER BY time DESC LIMIT 5"
rs_h = client.query(query_hist)
print("\nRecent Formato Values:")
for p in rs_h.get_points():
    print(f"  {p['time']}: {p['formato_gramas']}")
