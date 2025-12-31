from run import app
from services.watcher import check_5min_triggers, check_waste_backoff
import logging

# Configure logging to show info/debug
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('Watcher')
logger.setLevel(logging.INFO)

print("--- Running 5min Triggers ---")
from services.diagnostics import client
rs = client.query("SHOW TAG VALUES FROM production WITH KEY = \"equipment\"")
equipments = [p['value'] for p in rs.get_points()]
print(f"Found Equipments: {equipments}")

check_5min_triggers(app)

print("\n--- Running Waste Triggers ---")
check_waste_backoff(app)
