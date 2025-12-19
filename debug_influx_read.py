
from influxdb import InfluxDBClient
import os
from dotenv import load_dotenv

load_dotenv()

host = os.getenv('INFLUXDB_HOST', 'localhost')
port = int(os.getenv('INFLUXDB_PORT', 8086))
user = os.getenv('INFLUXDB_USER', 'admin')
password = os.getenv('INFLUXDB_USER_PASSWORD', 'admin')
dbname = os.getenv('INFLUXDB_DATABASE', 'industria_db')

print(f"Connecting to {host}:{port} db={dbname}...")
client = InfluxDBClient(host, port, user, password, dbname)

try:
    # Query last 5 points from production for 'Line 01' or similar
    # First, list series to see line names
    print("\n--- Series in production ---")
    rs = client.query("SHOW SERIES FROM production LIMIT 5")
    print(list(rs.get_points()))

    print("\n--- Recent Data for 'Linha 01' (or similar) ---")
    # Try to find a line name
    rs = client.query("SELECT * FROM production ORDER BY time DESC LIMIT 3")
    points = list(rs.get_points())
    for p in points:
        print(p)
        print("-" * 20)
        
    print("\n--- Checking specific tags/fields ---")
    if points:
        p = points[0]
        print(f"SKU keys: {[k for k in p.keys() if 'sku' in k.lower()]}")
        print(f"OP keys: {[k for k in p.keys() if 'ordem' in k.lower() or 'op' in k.lower()]}")
        print(f"Desc keys: {[k for k in p.keys() if 'desc' in k.lower() or 'prod' in k.lower()]}")
        
except Exception as e:
    print(f"Error: {e}")
