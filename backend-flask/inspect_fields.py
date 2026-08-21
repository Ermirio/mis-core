from influxdb import InfluxDBClient
import os

host = 'influxdb'
port = 8086
db = 'industrial_db'
client = InfluxDBClient(host=host, port=port, username='admin', password='admin123', database=db)

# Metric to inspect
eq = 'E001' # or whatever was in the log
print(f"--- Inspecting Fields for {eq} ---")

# Get *latest* point with ALL fields
rs = client.query(f"SELECT * FROM production WHERE equipment = '{eq}' ORDER BY time DESC LIMIT 1")
points = list(rs.get_points())

if not points:
    print("No data found.")
else:
    p = points[0]
    print("Latest Point Keys:")
    for k, v in p.items():
        if v is not None:
            print(f" - {k}: {v}")
