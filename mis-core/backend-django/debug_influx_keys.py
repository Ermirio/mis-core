from equipamentos.influx_helpers import get_influx_client

def list_keys():
    client = get_influx_client()
    print("Listando chaves do measurement 'production'...")
    
    rs = client.query('SHOW FIELD KEYS FROM "production"')
    points = list(rs.get_points())
    
    for p in points:
        print(f"Field Key: {p['fieldKey']} ({p['fieldType']})")

list_keys()
