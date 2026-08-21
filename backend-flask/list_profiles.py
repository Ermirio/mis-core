from services.diagnostics import client
q = "SELECT * FROM golden_state_profile WHERE equipamento='E001' AND sku='555555550.0'"
rs = client.query(q)
points = list(rs.get_points())
print(f"--- Profiles for SKU 555555550 ---")
for p in points:
    print(f"Type: {p.get('capture_type')} | Vel: {p.get('velocidade_atual')} | OEE: {p.get('oee_atual')} | Time: {p.get('time')}")
