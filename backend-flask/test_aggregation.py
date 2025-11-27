import sys
import logging
from datetime import datetime
from app import agregar_metricas_turno, app

# Configure logging to stdout
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
app.logger.handlers = []
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.INFO)

print("--- Testing Aggregation ---")
print(f"Current Time (Local): {datetime.now()}")
print(f"Current Time (UTC): {datetime.utcnow()}")

try:
    agregar_metricas_turno()
    print("--- Aggregation Finished ---")
except Exception as e:
    print(f"Error: {e}")
