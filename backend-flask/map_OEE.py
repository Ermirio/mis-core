from services.diagnostics import client

print("--- Mapping Equipments and OEE ---")
# Get all equipments
rs = client.query("SHOW TAG VALUES FROM production WITH KEY = \"equipment\"")
equips = [p['value'] for p in rs.get_points()]

for eq in equips:
    # Get latest data
    q = f"SELECT last(*) FROM production WHERE equipment = '{eq}'"
    p = list(client.query(q).get_points())
    if p:
        data = p[0]
        # Dynamically find keys starting with 'last_'
        name = next((v for k,v in data.items() if 'descricao' in k and v), 'Unknown')
        oee = next((v for k,v in data.items() if 'oee_realtime' in k and v is not None), 0)
        sku = next((v for k,v in data.items() if 'sku' in k and v), 'N/A')
        print(f"[{eq}] Name: {name} | SKU: {sku} | OEE: {oee}")
        # print keys if unknown
        if name == 'Unknown': print(f"Keys: {data.keys()}")
    else:
        print(f"[{eq}] No data")
