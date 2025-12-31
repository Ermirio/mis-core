from influxdb import InfluxDBClient

client = InfluxDBClient(host='influxdb', port=8086, username='admin', password='admin123', database='industrial_db')

def inspect_production():
    try:
        query = "SELECT * FROM production WHERE equipment = 'E001' ORDER BY time DESC LIMIT 1"
        print(f"Executing: {query}")
        rs = client.query(query)
        points = list(rs.get_points())
        if points:
            print("--- Latest Record Fields ---")
            for k, v in points[0].items():
                print(f"{k}: {v}")
        else:
            print("No data found for E001.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_production()
