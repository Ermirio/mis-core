import logging
import sys
from flask import Flask
from factory_kpis_engine import get_factory_kpis, get_primeiro_equipamento_por_linha
from production_engine import ProductionEngine
from influxdb import InfluxDBClient
from decouple import config

# Configurar Logging para stdout
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger("factory_kpis_engine")
logger.setLevel(logging.INFO)

app = Flask(__name__)

# Mock Extensions
class MockExtensions:
    def get(self, key):
        if key == 'production_engine':
            return MockEngine()
        if key == 'influx_client':
            return InfluxDBClient(
                host=config('INFLUXDB_HOST', default='localhost'),
                port=config('INFLUXDB_PORT', default=8086, cast=int),
                username=config('INFLUXDB_USER', default='admin'),
                password=config('INFLUXDB_USER_PASSWORD', default=''),
                database=config('INFLUXDB_DATABASE', default='industrial_db')
            )
        return None

class MockEngine:
    def __init__(self):
        self.shift_manager = MockShiftManager()

class MockShiftManager:
    def get_turno_info(self):
        return {'nome': 'A', 'inicio': datetime.time(6, 0), 'fim': datetime.time(14, 0)}

import datetime

# Patch current_app
with app.app_context():
    app.extensions = MockExtensions()
    
    print("--- Testing get_primeiro_equipamento_por_linha ---")
    mapping = get_primeiro_equipamento_por_linha()
    print(f"Mapping: {mapping}")
    
    print("\n--- Testing get_factory_kpis ---")
    kpis = get_factory_kpis(period='turno')
    
    for linha in kpis['linhas']:
        if linha['linha'] == 'L01':
            print(f"\nL01 Result: {linha}")
