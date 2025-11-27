from influxdb import InfluxDBClient
from datetime import datetime, timedelta

client = InfluxDBClient(host='127.0.0.1', port=8086, database='industrial_db', username='admin', password='admin123')

print("--- InfluxDB Diagnostic ---")
try:
    # Check measurements
    result = client.query('SHOW MEASUREMENTS')
    print(f"Measurements: {list(result.get_points())}")

    # Check recent data for L01_ENCH_01
    query = 'SELECT * FROM producao WHERE time > now() - 1h LIMIT 5'
    result = client.query(query)
    points = list(result.get_points())
    print(f"\nRecent Data (Last 1h): {len(points)} records")
    for p in points:
        print(p)

    if not points:
        print("\nNo recent data found! Checking any data...")
        query = 'SELECT * FROM producao LIMIT 1'
        result = client.query(query)
        print(f"Any data? {list(result.get_points())}")

except Exception as e:
    print(f"Error: {e}")
