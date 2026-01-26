from equipamentos.influx_helpers import get_influx_client

def list_measurements():
    client = get_influx_client()
    print("Measurements no DB:")
    rs = client.query("SHOW MEASUREMENTS")
    points = list(rs.get_points())
    for p in points:
        print(p['name'])

list_measurements()
