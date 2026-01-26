from equipamentos.influx_helpers import get_influx_client

def debug_dump_point():
    client = get_influx_client()
    query = "SELECT * FROM production ORDER BY time DESC LIMIT 1"
    rs = client.query(query)
    points = list(rs.get_points())
    
    if points:
        p = points[0]
        print("--- DUMP PONTO RECENTE ---")
        for k, v in p.items():
            print(f"{k}: {v} (Type: {type(v)})")
    else:
        print("Nenhum ponto encontrado.")

debug_dump_point()
