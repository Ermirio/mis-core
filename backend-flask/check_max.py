from services.watcher import get_max_historical
from services.diagnostics import client
print("--- Checking Max Historic for E001 / SKU 555555550 ---")
m = get_max_historical('E001', '555555550.0', 'oee_atual')
print(f"Max OEE: {m}")

# Check if any profile exists
q = "SELECT * FROM golden_state_profile WHERE equipamento='E001' AND sku='555555550.0'"
p = list(client.query(q).get_points())
print(f"Existing Profiles: {len(p)}")
