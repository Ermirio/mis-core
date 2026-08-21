from influxdb import InfluxDBClient
import os

host = 'influxdb'
port = 8086
db = 'industrial_db'
user = 'admin'
passwd = 'admin123'

try:
    client = InfluxDBClient(host=host, port=port, username=user, password=passwd, database=db)
    print(f"Connected to {host}")
    
    rs = client.query("SHOW TAG VALUES FROM production WITH KEY = \"equipment\"")
    points = list(rs.get_points())
    print(f"Equipments: {points}")

    for p in points:
        eq = p['value']
        print(f"\nScanning {eq}...")
        
        # Get Current
        q_curr = f"SELECT last(velocidade_atual), last(sku_codigo_field), last(estado_maquina) FROM production WHERE equipment = '{eq}'"
        rs_curr = client.query(q_curr)
        curr = list(rs_curr.get_points())
        print(f"Current Raw: {curr}")
        
        if not curr: continue
        
        sku = curr[0].get('last_sku_codigo_field', 'N/A')
        vel = curr[0].get('last_velocidade_atual', 0)
        
        # Get Max
        q_max = f"SELECT max(velocidade_atual) FROM golden_state_profile WHERE equipamento = '{eq}' AND sku = '{sku}'"
        rs_max = client.query(q_max)
        pts_max = list(rs_max.get_points())
        max_v = pts_max[0]['max'] if pts_max else 0
        
        print(f"Comparison: Current {vel} vs Max {max_v} (SKU: {sku})")

except Exception as e:
    print(f"Error: {e}")
