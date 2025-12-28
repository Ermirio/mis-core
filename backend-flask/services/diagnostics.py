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
INFLUXDB_PASS = config('INFLUXDB_PASSWORD', default='admin123')

client = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT, username=INFLUXDB_USER, password=INFLUXDB_PASS, database=INFLUXDB_DB)

import requests
import json
from decouple import config

DJANGO_API_URL = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')

def get_equipment_sensors(equipamento_codigo):
    """Fetches sensor configuration for the equipment from Django."""
    try:
        # Find equipment ID first (assuming we have a way or just filter by code directly if API supports)
        # Assuming we need to look up by code
        url = f"{DJANGO_API_URL}/equipamentos/?codigo={equipamento_codigo}"
        resp = requests.get(url, timeout=5)
        if not resp.ok: return []
        
        results = resp.json().get('results', [])
        if not results: return []
        
        eq_id = results[0]['id']
        
        # Fetch sensors for this equipment
        url_sensors = f"{DJANGO_API_URL}/sensores/?equipamento={eq_id}"
        resp_s = requests.get(url_sensors, timeout=5)
        if resp_s.ok:
            return resp_s.json().get('results', [])
        return []
    except Exception as e:
        logger.error(f"Error fetching sensors: {e}")
        return []

def capture_golden_state(equipamento_codigo, capture_type='MANUAL'):
    """
    Captures the current state of the equipment as the 'Golden State'.
    Dynamically captures all configured sensors and their current limits.
    """
    try:
        # 1. Get current values from InfluxDB
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
        
        # 2. Get Sensor Configuration from Django
        sensors = get_equipment_sensors(equipamento_codigo)
        
        # 3. Build Dynamic Fields
        # We store metadata as fields or tags? Tags are indexed. 
        # For 'log' viewing, fields are fine, but filtering might need tags.
        # Let's put SKU and Type as tags for better querying if needed, or fields if high cardinality.
        # SKU as tag is good. Type as tag is good.
        
        fields = {
            "velocidade_atual": float(profile.get('last_velocidade_atual') or 0),
            "oee_atual": float(profile.get('last_oee_realtime') or 0),
            # Flatten sensors into fields for simplicity in simple display
        }
        
        # Add dynamic sensors
        for sensor in sensors:
            tag = sensor.get('tag_influxdb')
            if tag:
                # Influx return generic 'last_X' for fields
                val = profile.get(f'last_{tag}')
                if val is not None:
                    try:
                        fields[tag] = float(val)
                        # Capture Limits (Adjustment Snapshot)
                        if sensor.get('valor_min') is not None:
                            fields[f"{tag}_min"] = float(sensor['valor_min'])
                        if sensor.get('valor_max') is not None:
                            fields[f"{tag}_max"] = float(sensor['valor_max'])
                    except: pass

        # 4. Save to 'golden_state_profile' 
        point = {
            "measurement": "golden_state_profile",
            "tags": {
                "equipamento": equipamento_codigo,
                "sku": profile.get('last_sku_codigo_field', 'N/A'),
                "capture_type": capture_type
            },
            "time": datetime.utcnow().isoformat(),
            "fields": fields
        }
            
        client.write_points([point])
        
        logger.info(f"Golden State captured for {equipamento_codigo} ({capture_type}) with {len(fields)} metrics")
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

def get_golden_state_history(equipamento_codigo, limit=20, sku=None):
    """
    Retrieves the history of Golden State profiles for the equipment.
    """
    try:
        if sku:
            query = f"SELECT * FROM golden_state_profile WHERE equipamento = '{equipamento_codigo}' AND sku = '{sku}' ORDER BY time DESC LIMIT {limit}"
        else:
            query = f"SELECT * FROM golden_state_profile WHERE equipamento = '{equipamento_codigo}' ORDER BY time DESC LIMIT {limit}"
        
        result = client.query(query)
        points = list(result.get_points())
        
        return points

    except Exception as e:
        logger.error(f"Error getting Golden State history: {e}")
        return []
