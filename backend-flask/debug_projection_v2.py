
from influxdb import InfluxDBClient
from datetime import datetime

host = 'localhost'
port = 8086
username = 'admin'
password = 'admin123'
database = 'industrial_db'

client = InfluxDBClient(host, port, username, password, database)


print("--- CHECKING AVAILABLE LINES ---")
rs_lines = client.query('SHOW TAG VALUES FROM production WITH KEY = "line"')
print("Available Lines in Influx 'production':")
for p in rs_lines.get_points():
    print(f"  > {p['value']}")



LINE_NORM = 'DEBUG_LINE'





print(f"--- DEBUG PRODUCTION DUMP FOR {LINE_NORM} ---")

# Query ALL equipments for this line
# Using a broad query to catch everything
query = f"SELECT last(toneladas_turno) FROM production WHERE \"line\" = '{LINE_NORM}' GROUP BY \"equipment\""
rs = client.query(query)

# Collect results
results = []
for (name, tags), pts in rs.items():
    eq_name = tags.get('equipment', 'Unknown')
    val = 0.0
    time_str = "N/A"
    for p in pts:
        val = float(p.get('last', 0) or 0)
        time_str = p.get('time', 'N/A')
        
    results.append({'eq': eq_name, 'val': val, 'time': time_str})

# Sort by Value Descending
results.sort(key=lambda x: x['val'], reverse=True)

print(f"{'EQUIPMENT':<20} | {'TONS':<15} | {'TIME (UTC)':<25}")
print("-" * 65)
for r in results:
    print(f"{r['eq']:<20} | {r['val']:<15.3f} | {r['time']:<25}")

print("-" * 65)
print("Analysis Suggestions:")
print("1. If '12000' appears here, check why it wasn't selected.")
print("2. If '489' appears, that is what the system likely picked.")
print("3. If nothing matches 12000, verify if user meant Units or KG.")
