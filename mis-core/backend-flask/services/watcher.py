from datetime import datetime, timedelta
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from services.diagnostics import client, capture_golden_state, get_equipment_sensors

logger = logging.getLogger('Watcher')

def get_current_metrics(equipment):
    """Fetches real-time metrics for triggers."""
    try:
        query = f"SELECT last(*) FROM production WHERE equipment = '{equipment}'"
        rs = client.query(query)
        points = list(rs.get_points())
        if not points: return None
        return points[0]
    except Exception as e:
        logger.error(f"Error getting metrics for {equipment}: {e}")
        return None

def get_max_historical(equipment, sku, metric):
    """Finds the max recorded value for this SKU in Validated Profiles."""
    try:
        # We look at previous Golden States to see if we beat the record
        query = f"SELECT max({metric}) FROM golden_state_profile WHERE equipamento = '{equipment}' AND sku = '{sku}'"
        rs = client.query(query)
        points = list(rs.get_points())
        if points and points[0]['max']:
            return float(points[0]['max'])
        return 0.0
    except:
        return 0.0

def count_stops(equipment, minutes):
    """Counts machine stops in the last X minutes."""
    try:
        # Assuming State 0 or > 2 is stop? Let's use simpler logic: 
        # If 'estado_maquina' was NOT '1' (RUN) at any point? 
        # Better: Query count of points where state != 1? 
        # Or use events_estado if available. 
        # Let's assume 'production' table has 'estado_maquina'.
        # RUN = 1.
        start_time = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
        
        # Count points where state is NOT 1 (RUN)
        # Note: InfluxQL is tricky with "count where val != 1".
        # Let's count TOTAL points and points where STATE=1. If diff > 0, we had stops?
        # No, that depends on sampling.
        # Let's query "SELECT count(estado_maquina) FROM production WHERE equipment='...' AND estado_maquina != 1 AND time > '{start_time}Z'"
        
        query = f"SELECT count(estado_maquina) FROM production WHERE equipment = '{equipment}' AND estado_maquina != 1 AND time > '{start_time}Z'"
        rs = client.query(query)
        points = list(rs.get_points())
        if points:
            return points[0]['count']
        return 0 # No non-run states found
    except:
        return 0

def has_recent_capture(equipment, trigger_type, minutes=5):
    """Prevents spamming captures."""
    try:
        time_threshold = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
        query = f"SELECT * FROM golden_state_profile WHERE equipamento = '{equipment}' AND capture_type = '{trigger_type}' AND time > '{time_threshold}Z'"
        rs = client.query(query)
        return len(list(rs.get_points())) > 0
    except:
        return False

def check_5min_triggers(app):
    """
    Velocity & OEE Watcher (Runs every 5 min)
    """
    with app.app_context():
        # Get active equipments from somewhere, or just hardcode for MVP, or query unique equipments from Influx
        # Let's query influx for active equipments in last 5 min
        try:
            rs = client.query("SHOW TAG VALUES FROM production WITH KEY = \"equipment\"")
            equipments = [p['value'] for p in rs.get_points()]
            
            for eq in equipments:
                curr = get_current_metrics(eq)
                if not curr: continue
                
                sku = curr.get('last_sku_codigo_field')
                vel = float(curr.get('last_velocidade_atual') or 0)
                oee = float(curr.get('last_oee_realtime') or 0)
                state = int(curr.get('last_estado_maquina') or 0)
                
                if not sku or sku == 'N/A': continue
                if state != 1: continue # Only capture if running
                
                # 1. Check Velocity trigger
                max_vel = get_max_historical(eq, sku, 'velocidade_atual')
                print(f"[DEBUG] Check Vel for {eq}: {vel} vs Max {max_vel} (SKU: {sku})")  # FORCE PRINT
                
                if vel > max_vel and vel > 0:
                    if not has_recent_capture(eq, 'AUTO_VELOCITY', 10):
                        logger.info(f"🚀 Trigger Velocity! {vel} > {max_vel} for {sku}")
                        capture_golden_state(eq, 'AUTO_VELOCITY')
                        continue # Prioritize one capture per cycle
                
                # 2. Check OEE Trigger
                max_oee = get_max_historical(eq, sku, 'oee_atual')
                if oee > max_oee and oee > 0:
                     if not has_recent_capture(eq, 'AUTO_OEE', 10):
                        logger.info(f"💎 Trigger OEE! {oee}% > {max_oee}% for {sku}")
                        capture_golden_state(eq, 'AUTO_OEE')
        except Exception as e:
            logger.error(f"Error in 5min watcher: {e}")

def check_30min_triggers(app):
    """
    Stability Watcher (Runs every 30 min)
    """
    with app.app_context():
        try:
            rs = client.query("SHOW TAG VALUES FROM production WITH KEY = \"equipment\"")
            equipments = [p['value'] for p in rs.get_points()]
            
            for eq in equipments:
                stops = count_stops(eq, 30)
                if stops == 0:
                    # Verify if running now
                    curr = get_current_metrics(eq)
                    if not curr or curr.get('last_estado_maquina') != 1: continue
                    
                    if not has_recent_capture(eq, 'AUTO_STABILITY', 40):
                        logger.info(f"🛡️ Trigger Stability! 0 stops in 30min for {eq}")
                        capture_golden_state(eq, 'AUTO_STABILITY')
        except Exception as e:
            logger.error(f"Error in 30min watcher: {e}")


# Global State for Waste Backoff
# Key: (equipment_code, sku) -> Value: {'interval': 1, 'last_check': datetime}
WASTE_STATE = {}

def get_waste_sum(equipment, start_time_iso, end_time_iso=None):
    """Calculates SUM(descarte) in a time window."""
    try:
        # InfluxQL time range query
        # end_time_iso is optional (defaults to now)
        time_clause = f"time > '{start_time_iso}Z'"
        if end_time_iso:
            time_clause += f" AND time < '{end_time_iso}Z'"
            
        # Count sum of 'descarte'
        # Note: 'descarte' is a field in 'production'? Coletor sends it.
        # Coletor sends 'descarte' as a field in the packet.
        query = f"SELECT sum(descarte) FROM production WHERE equipment = '{equipment}' AND {time_clause}"
        rs = client.query(query)
        points = list(rs.get_points())
        if points:
            return float(points[0]['sum'] or 0)
        return 0.0
    except:
        return 0.0

def check_waste_backoff(app):
    """
    Waste Trigger with Exponential Backoff (Runs every 1 min)
    """
    with app.app_context():
        try:
            rs = client.query("SHOW TAG VALUES FROM production WITH KEY = \"equipment\"")
            equipments = [p['value'] for p in rs.get_points()]
            
            for eq in equipments:
                curr = get_current_metrics(eq)
                if not curr: continue
                
                sku = curr.get('last_sku_codigo_field')
                state = int(curr.get('last_estado_maquina') or 0)
                
                if not sku or sku == 'N/A': continue
                if state != 1: continue # Only if running
                
                key = (eq, sku)
                
                # Init State if needed
                if key not in WASTE_STATE:
                    WASTE_STATE[key] = {'interval': 1, 'last_check': datetime.utcnow()}
                
                state_data = WASTE_STATE[key]
                interval = state_data['interval']
                last_check = state_data['last_check']
                
                # Check if it's time (with 5s buffer)
                now = datetime.utcnow()
                if (now - last_check).total_seconds() / 60 < (interval - 0.1):
                    continue # Not time yet
                
                # Logic: Compare Current Window vs Previous Window
                # Current Window: [now - interval, now]
                # Previous Window: [now - 2*interval, now - interval]
                
                t_minus_1 = (now - timedelta(minutes=interval)).isoformat()
                t_minus_2 = (now - timedelta(minutes=interval*2)).isoformat()
                
                waste_curr = get_waste_sum(eq, t_minus_1)
                waste_prev = get_waste_sum(eq, t_minus_2, t_minus_1)
                
                # Validation Logic
                improved = False
                if waste_curr < waste_prev: improved = True
                if waste_curr == 0 and waste_prev > 0: improved = True
                if waste_curr == 0 and waste_prev == 0: improved = True # Sustained Perfection
                
                if improved:
                    # Capture Golden State
                    logger.info(f"♻️ Trigger WASTE! Interval {interval}m. Curr {waste_curr} <= Prev {waste_prev}")
                    capture_golden_state(eq, f'AUTO_WASTE_{interval}M')
                    
                    # Backoff (Double interval, max 60)
                    new_interval = min(interval * 2, 60)
                    # Only update if we haven't reached max or if we want to confirm 60m again
                    if interval < 60:
                        logger.info(f"📈 Waste Interval Increased: {interval}m -> {new_interval}m for {eq}")
                    
                    WASTE_STATE[key] = {'interval': new_interval, 'last_check': now}
                    
                else:
                    # Reset (Punishment)
                    if interval > 1:
                        logger.warning(f"📉 Waste Interval Reset: {interval}m -> 1m. Curr {waste_curr} > Prev {waste_prev}")
                    WASTE_STATE[key] = {'interval': 1, 'last_check': now}

        except Exception as e:
            logger.error(f"Error in Waste watcher: {e}")

def check_hourly_master(app):
    """
    Golden Master (Runs every 60 min)
    """
    with app.app_context():
        try:
            rs = client.query("SHOW TAG VALUES FROM production WITH KEY = \"equipment\"")
            equipments = [p['value'] for p in rs.get_points()]
            
            for eq in equipments:
                # 1. Zero Stops
                if count_stops(eq, 60) > 0: continue
                
                # 2. Zero Waste (New Requirement)
                start_hour = (datetime.utcnow() - timedelta(hours=1)).isoformat()
                waste_sum = get_waste_sum(eq, start_hour)
                if waste_sum > 0: continue 

                # 3. Compare vs 1h ago
                curr = get_current_metrics(eq)
                if not curr: continue
                
                time_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
                q_avg = f"SELECT mean(velocidade_atual) as vel, mean(oee_realtime) as oee FROM production WHERE equipment='{eq}' AND time > '{time_ago}Z'"
                rs_avg = client.query(q_avg)
                pt_avg = list(rs_avg.get_points())
                
                if not pt_avg: continue
                avg_vel = pt_avg[0]['vel'] or 0
                avg_oee = pt_avg[0]['oee'] or 0
                
                curr_vel = float(curr.get('last_velocidade_atual') or 0)
                curr_oee = float(curr.get('last_oee_realtime') or 0)
                
                if curr_vel > avg_vel and curr_oee > avg_oee:
                     logger.info(f"👑 Trigger MASTER! Vel {curr_vel}>{avg_vel}, OEE {curr_oee}>{avg_oee}, 0 Stops, 0 Waste.")
                     capture_golden_state(eq, 'GOLDEN_MASTER')
                     
        except Exception as e:
            logger.error(f"Error in Master watcher: {e}")
