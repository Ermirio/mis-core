from influxdb import InfluxDBClient
import os

host = os.getenv('INFLUXDB_HOST', 'influxdb')
port = int(os.getenv('INFLUXDB_PORT', 8086))
username = os.getenv('INFLUXDB_USER', 'admin')
password = os.getenv('INFLUXDB_PASSWORD', 'admin')
dbname = os.getenv('INFLUXDB_DATABASE', 'mis')

client = InfluxDBClient(host=host, port=port, username=username, password=password, database=dbname)

try:
    # Query last 10 points SPECIFICALLY for line='L01'
    query = "SELECT time, oee_realtime, performance_realtime FROM production WHERE equipment = 'E002' AND line='L01' ORDER BY time DESC LIMIT 10"
    result = client.query(query)
    print("Last 10 points for E002 with line=L01:", result)
    
except Exception as e:
    print("Error:", e)
