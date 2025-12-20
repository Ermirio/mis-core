
import os
import time
from influxdb import InfluxDBClient
from decouple import config

INFLUXDB_HOST = config('INFLUXDB_HOST', default='localhost')
INFLUXDB_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUXDB_USER = config('INFLUXDB_USER', default='admin')
INFLUXDB_PASSWORD = config('INFLUXDB_USER_PASSWORD', default='admin')
INFLUXDB_DATABASE = config('INFLUXDB_DATABASE', default='industria_db')

def normalize_line_name(linha_nome):
    if not linha_nome: return linha_nome
    if linha_nome.startswith("L") and len(linha_nome) <= 3 and linha_nome[1:].isdigit():
        return linha_nome
    if "Linha" in linha_nome:
        parts = linha_nome.split()
        if len(parts) > 1 and parts[1].isdigit():
             return f"L{parts[1].zfill(2)}"
    return linha_nome.replace("Linha ", "L")

try:
    client = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT, username=INFLUXDB_USER, password=INFLUXDB_PASSWORD, database=INFLUXDB_DATABASE)
    
    print("--- Checking Series in 'production' measurement ---")
    rs = client.query("SHOW SERIES FROM production")
    series_list = list(rs.get_points())
    
    print(f"Total Series found: {len(series_list)}")
    
    equipment_line_map = {}
    
    for series in series_list:
        # Key format: production,equipment=E001,line=L01
        key = series['key']
        parts = key.split(',')
        tags = {}
        for p in parts[1:]:
            if '=' in p:
                k, v = p.split('=')
                tags[k] = v
        
        eq = tags.get('equipment')
        ln = tags.get('line')
        
        if eq and ln:
            print(f"Equipment: {eq} -> Line Tag: {ln}")
            if eq in equipment_line_map and equipment_line_map[eq] != ln:
                print(f"WARNING: Equipment {eq} found with MULTIPLE lines: {equipment_line_map[eq]} and {ln}")
            equipment_line_map[eq] = ln
            
    print("\n--- Verifying Normalization ---")
    l1 = normalize_line_name("Linha 01")
    l2 = normalize_line_name("Linha 02")
    print(f"Linha 01 normalizes to: {l1}")
    print(f"Linha 02 normalizes to: {l2}")
    
    print("\n--- Query Test ---")
    for ln in [l1, l2]:
        q = f"SELECT last(sku_codigo_field) as sku FROM production WHERE \"line\" = '{ln}'"
        rs_q = client.query(q)
        pts = list(rs_q.get_points())
        print(f"Query for line='{ln}': Found {len(pts)} points. Data: {pts[0] if pts else 'None'}")

except Exception as e:
    print(f"Error: {e}")
