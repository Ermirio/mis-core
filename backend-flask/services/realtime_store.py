from influxdb import InfluxDBClient
import os
import logging
from datetime import datetime

from decouple import config

logger = logging.getLogger('RealtimeStore')

# InfluxDB 1.8 Configuration
INFLUXDB_HOST = config('INFLUXDB_HOST', default='127.0.0.1')
INFLUXDB_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUXDB_DB = config('INFLUXDB_DATABASE', default='industrial_db')
INFLUXDB_USER = config('INFLUXDB_USER', default='admin')
INFLUXDB_PASS = config('INFLUXDB_USER_PASSWORD', default='ixvq10A@10')

client = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT, username=INFLUXDB_USER, password=INFLUXDB_PASS, database=INFLUXDB_DB)

def get_equipamento_realtime(equipamento_codigo):
    """
    Fetches the latest real-time data for the equipment using InfluxQL.
    Returns a dictionary with 'medicoes' and other relevant data.
    """
    try:
        # Query latest data from 'production'
        query = f"SELECT last(*) FROM production WHERE \"equipment\" = '{equipamento_codigo}'"
        result = client.query(query)
        points = list(result.get_points())
        
        medicoes = {}
        timestamp = None
        
        if points:
            latest = points[0]
            timestamp = latest.get('time')
            # Copy all fields, removing 'last_' prefix
            for k, v in latest.items():
                if k != 'time':
                    clean_key = k.replace('last_', '')
                    medicoes[clean_key] = v
        
        if not medicoes:
            return {}

        # Also get the latest state from 'machine_status' (or rely on state in production)
        # production measurement usually has 'estado_maquina' or 'estado'
        if 'estado_maquina' in medicoes:
             medicoes['estado'] = medicoes['estado_maquina']

        return {
            'medicoes': medicoes,
            'timestamp': timestamp
        }

    except Exception as e:
        logger.error(f"Error fetching realtime data for {equipamento_codigo}: {e}")
        return {}
