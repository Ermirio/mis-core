import logging
from .diagnostic_rules import MicroStopsRule, StarvationRule, GoldenStateDeviationRule
from .diagnostics import get_latest_golden_state
from influxdb import InfluxDBClient
import os
from datetime import datetime

from decouple import config

logger = logging.getLogger('DiagnosticsEngine')

# InfluxDB 1.8 Configuration
INFLUXDB_HOST = config('INFLUXDB_HOST', default='127.0.0.1')
INFLUXDB_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUXDB_DB = config('INFLUXDB_DATABASE', default='industrial_db')
INFLUXDB_USER = config('INFLUXDB_USER', default='admin')
INFLUXDB_PASS = config('INFLUXDB_USER_PASSWORD', default='ixvq10A@10')

client = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT, username=INFLUXDB_USER, password=INFLUXDB_PASS, database=INFLUXDB_DB)

from constants import ESTADOS_MAQUINA

def get_equipment_history(equipamento_codigo, minutes=120):
    """
    Fetches state history for the equipment using InfluxQL.
    Queries 'machine_status' and calculates duration between events.
    """
    try:
        # Query state changes in the last window
        query = f"""
        SELECT * FROM machine_status 
        WHERE equipment = '{equipamento_codigo}' AND time > now() - {minutes}m 
        ORDER BY time ASC
        """
        result = client.query(query)
        points = list(result.get_points())
        
        history = []
        if not points:
            return history

        # Calculate durations
        for i in range(len(points) - 1):
            current_point = points[i]
            next_point = points[i+1]
            
            start_time = datetime.fromisoformat(current_point['time'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(next_point['time'].replace('Z', '+00:00'))
            duration = (end_time - start_time).total_seconds()
            
            state_code = int(current_point.get('estado_maquina', 0))
            state_name = ESTADOS_MAQUINA.get(state_code, 'Desconhecido')
            
            # Map to internal names used by rules if necessary
            # Rules use: 'PARADO', 'FALTA_MAT', 'MANUTENCAO', 'WAIT_PREV', 'BLOCK_NEXT'
            # ESTADOS_MAQUINA: 4: "Parado/Falha", 9: "Falta de Material", 8: "Manutenção", 2: "Aguardando Anterior", 3: "Bloqueado Próximo"
            
            internal_state = state_name
            if state_code == 4: internal_state = 'PARADO'
            elif state_code == 9: internal_state = 'FALTA_MAT'
            elif state_code == 8: internal_state = 'MANUTENCAO'
            elif state_code == 2: internal_state = 'WAIT_PREV'
            elif state_code == 3: internal_state = 'BLOCK_NEXT'
            elif state_code == 1: internal_state = 'PRODUZINDO'

            history.append({
                'estado': internal_state,
                'inicio': current_point['time'],
                'duracao_segundos': duration
            })
            
        # Handle the last (current) state
        last_point = points[-1]
        start_time = datetime.fromisoformat(last_point['time'].replace('Z', '+00:00'))
        duration = (datetime.utcnow().replace(tzinfo=None) - start_time.replace(tzinfo=None)).total_seconds()
        
        state_code = int(last_point.get('estado_maquina', 0))
        state_name = ESTADOS_MAQUINA.get(state_code, 'Desconhecido')
        
        internal_state = state_name
        if state_code == 4: internal_state = 'PARADO'
        elif state_code == 9: internal_state = 'FALTA_MAT'
        elif state_code == 8: internal_state = 'MANUTENCAO'
        elif state_code == 2: internal_state = 'WAIT_PREV'
        elif state_code == 3: internal_state = 'BLOCK_NEXT'
        elif state_code == 1: internal_state = 'PRODUZINDO'

        history.append({
            'estado': internal_state,
            'inicio': last_point['time'],
            'duracao_segundos': duration
        })
        
        # Reverse to have newest first (as expected by some logic, though rules iterate all)
        history.reverse()
        
        return history
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return []

def run_diagnostics(equipamento_codigo, realtime_data):
    """
    Runs all configured diagnostic rules for the equipment.
    """
    alerts = []
    
    # 1. Fetch Context Data
    history_data = get_equipment_history(equipamento_codigo)
    golden_state = get_latest_golden_state(equipamento_codigo)
    
    # 2. Define Rules
    rules = [
        MicroStopsRule(window_minutes=60, max_stops=4),
        StarvationRule(threshold_minutes=10),
        GoldenStateDeviationRule(metric='velocidade_atual', threshold_percent=15)
    ]
    
    # 3. Evaluate Rules
    for rule in rules:
        try:
            alert = rule.evaluate(equipamento_codigo, realtime_data, history_data, golden_state)
            if alert:
                alerts.append({
                    'rule': alert.rule_name,
                    'severity': alert.severity,
                    'message': alert.message,
                    'details': alert.details,
                    'timestamp': alert.timestamp
                })
        except Exception as e:
            logger.error(f"Error evaluating rule {type(rule).__name__}: {e}")
            
    return alerts

def check_continuous_optimization(equipamento_codigo):
    """
    Implements 'Hill Climbing' optimization for Golden State.
    Checks if current performance (last 5 min) is better than previous window.
    If yes, captures the current sensor settings as the new Golden State.
    """
    try:
        # Window A: Last 5 minutes
        query_a = f"SELECT mean(oee_realtime) FROM production WHERE \"equipment\" = '{equipamento_codigo}' AND time > now() - 5m"
        
        # Window B: 5 minutes before that (10m to 5m ago)
        query_b = f"SELECT mean(oee_realtime) FROM production WHERE \"equipment\" = '{equipamento_codigo}' AND time > now() - 10m AND time < now() - 5m"
        
        rs_a = client.query(query_a)
        rs_b = client.query(query_b)
        
        val_a = 0.0
        val_b = 0.0
        
        points_a = list(rs_a.get_points())
        if points_a: val_a = float(points_a[0]['mean'] or 0)
        
        points_b = list(rs_b.get_points())
        if points_b: val_b = float(points_b[0]['mean'] or 0)
        
        if val_a > 0.1: # Minimum meaningful activity
             # If Current is better than Previous (with 2% hysteresis to verify stability)
            if val_a > (val_b * 1.02):
                from .diagnostics import capture_golden_state
                logger.info(f"🚀 OEE Improved: {val_a:.1f}% (was {val_b:.1f}%). Capturing Golden State...")
                capture_golden_state(equipamento_codigo, capture_type='AUTO')
                return True
                
        return False
        
    except Exception as e:
        logger.error(f"Error in continuous optimization: {e}")
        return False
