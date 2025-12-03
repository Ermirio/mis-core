from influxdb import InfluxDBClient
from datetime import datetime

client = InfluxDBClient(host='localhost', port=8086, database='industrial_db')
rs = client.query("SELECT * FROM production WHERE equipment = 'E001' ORDER BY time DESC LIMIT 1")
points = list(rs.get_points())

if points:
    print(f"Latest point: {points[0]}")
    print(f"Time: {points[0]['time']}")
else:
    print("No data found for E001")
