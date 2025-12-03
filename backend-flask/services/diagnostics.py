from influxdb import InfluxDBClient
import os
from datetime import datetime
import logging
from decouple import config

logger = logging.getLogger('Diagnostics')

# InfluxDB 1.8 Configuration
INFLUXDB_HOST = config('INFLUXDB_HOST', default='127.0.0.1')
INFLUXDB_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUXDB_DB = config('INFLUXDB_DATABASE', default='industrial_db')
INFLUXDB_USER = config('INFLUXDB_USER', default='admin')
INFLUXDB_PASS = config('INFLUXDB_USER_PASSWORD', default='ixvq10A@10')

client = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT, username=INFLUXDB_USER, password=INFLUXDB_PASS, database=INFLUXDB_DB)

def capture_golden_state(equipamento_codigo):
    """
    Captures the current state of the equipment as the 'Golden State'.
    Calculates the average of key metrics over the last 5 minutes using InfluxQL.
    """
    try:
        # Query last 5 minutes of data
        query = f"""
        SELECT last(*) 
        FROM production 
        WHERE "equipment" = '{equipamento_codigo}'
        """
        
        result = client.query(query)
        points = list(result.get_points())
        
        if not points:
            logger.warning(f"No data found to capture Golden State for {equipamento_codigo}")
            return None

        profile = points[0]
        
        # Save to 'golden_state_profile' measurement
        # In InfluxDB 1.8, we write points as a list of dictionaries
        point = {
            "measurement": "golden_state_profile",
            "tags": {
                "equipamento": equipamento_codigo
            },
            "time": datetime.utcnow().isoformat(),
            "fields": {
                "velocidade_atual": float(profile.get('last_velocidade_atual') or 0),
                "temperatura": float(profile.get('last_temperatura') or 0),
                "pressao": float(profile.get('last_pressao') or 0)
            }
        }
            
        client.write_points([point])
        
        logger.info(f"Golden State captured for {equipamento_codigo}: {profile}")
        return profile

    except Exception as e:
        logger.error(f"Error capturing Golden State: {e}")
        return None

def get_latest_golden_state(equipamento_codigo):
    """
    Retrieves the latest Golden State profile for the equipment using InfluxQL.
    """
    try:
        query = f"SELECT * FROM golden_state_profile WHERE equipamento = '{equipamento_codigo}' ORDER BY time DESC LIMIT 1"
        
        result = client.query(query)
        points = list(result.get_points())
        
        if points:
            return points[0]
        return None

    except Exception as e:
        logger.error(f"Error getting Golden State: {e}")
        return None
