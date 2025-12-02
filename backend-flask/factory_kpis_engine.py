import logging
import requests
from datetime import datetime, timedelta, time
from flask import current_app
from decouple import config
import calendar

logger = logging.getLogger(__name__)

DJANGO_API_URL = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')

def get_factory_kpis(period='turno'):
    try:
        # 1. Access Dependencies
        engine = current_app.extensions.get('production_engine')
        client = current_app.extensions.get('influx_client')
        
        if not engine or not client:
            raise RuntimeError("Engine or Influx Client not initialized")
            
        shift_manager = engine.shift_manager
        
        # 2. Determine Time Range & Remaining Time
        now = datetime.now()
        today = now.date()
        
        start_dt = now
        end_dt = now
        remaining_hours = 0.0
        
        if period == 'turno':
            turno_info = shift_manager.get_turno_info()
            if turno_info:
                # Start is shift start (today or yesterday if night shift)
                # This is tricky without full shift logic, relying on ShiftManager to be correct
                # Assuming ShiftManager gives us the current shift's start/end times relative to today
                # For simplicity, let's use the 'inicio' and 'fim' times.
                
                # We need absolute datetimes for Influx
                # If current time is 07:00 and shift started at 06:00, start is today 06:00
                # If current time is 02:00 and shift started at 22:00 (yesterday), start is yesterday 22:00
                
                start_time = turno_info['inicio']
                end_time = turno_info['fim']
                
                start_dt = datetime.combine(today, start_time)
                end_dt = datetime.combine(today, end_time)
                
                if start_time > now.time(): # Started yesterday
                     start_dt -= timedelta(days=1)
                
                if end_time < start_time: # Ends next day
                    if now.time() < start_time: # We are in the "next day" part
                        pass # end_dt is today, start_dt was yesterday
                    else:
                        end_dt += timedelta(days=1) # end_dt is tomorrow
                
                remaining_seconds = (end_dt - now).total_seconds()
                remaining_hours = max(0, remaining_seconds / 3600.0)
                
        elif period == 'dia':
            start_dt = datetime.combine(today, time.min)
            end_dt = datetime.combine(today, time.max)
            remaining_hours = max(0, (end_dt - now).total_seconds() / 3600.0)
            
        elif period == 'semana':
            start_dt = datetime.combine(today - timedelta(days=today.weekday()), time.min) # Monday
            end_dt = datetime.combine(start_dt.date() + timedelta(days=6), time.max) # Sunday
            remaining_hours = max(0, (end_dt - now).total_seconds() / 3600.0)
            
        elif period == 'mes':
            start_dt = datetime.combine(today.replace(day=1), time.min)
            last_day = calendar.monthrange(today.year, today.month)[1]
            end_dt = datetime.combine(today.replace(day=last_day), time.max)
            remaining_hours = max(0, (end_dt - now).total_seconds() / 3600.0)

        # 3. Layout Configuration (Restored from legacy)
        layout_config = {
            "L20": {"area": "PREPARO", "pos_x": 0, "pos_y": 0, "w": 2, "h": 1, "critico": False},
            "L15": {"area": "PREPARO", "pos_x": 0, "pos_y": 1.2, "w": 2, "h": 1, "critico": False},
            "L19": {"area": "PREPARO", "pos_x": 0, "pos_y": 2.4, "w": 1.5, "h": 1.5, "critico": False},
            "L20_B": {"area": "PREPARO", "pos_x": 1.6, "pos_y": 2.4, "w": 1.5, "h": 1.5, "critico": False},
            "L16": {"area": "MISTURA", "pos_x": 3.5, "pos_y": 2.4, "w": 1, "h": 1.5, "critico": False},
            "L06": {"area": "ENVASE PÓS", "pos_x": 4.8, "pos_y": 2.4, "w": 1, "h": 1.5, "critico": False},
            "L18": {"area": "MISTURA", "pos_x": 6, "pos_y": 1.5, "w": 2, "h": 0.8, "critico": False},
            "L17": {"area": "MISTURA", "pos_x": 6, "pos_y": 2.5, "w": 2, "h": 1.2, "critico": False},
            "L10": {"area": "EMBALAGEM", "pos_x": 8.5, "pos_y": 0, "w": 1, "h": 4, "critico": True},
            "L02": {"area": "MISTURA", "pos_x": 9.8, "pos_y": 0, "w": 1, "h": 4, "critico": True},
            "L01": {"area": "ENVASE LÍQ", "pos_x": 11.1, "pos_y": 0, "w": 1, "h": 4, "critico": False},
            "L09": {"area": "ENVASE", "pos_x": 12.4, "pos_y": 0, "w": 1, "h": 4, "critico": False}
        }

        # 4. Fetch Active Lines
        active_lines = []
        try:
            resp = requests.get(f"{DJANGO_API_URL}/linhas/")
            if resp.ok:
                data = resp.json()
                active_lines = data.get('results', data) if isinstance(data, dict) else data
        except Exception as e:
            logger.error(f"Error fetching lines: {e}")

        # 5. Calculate KPIs per Line
        lines_kpi = []
        total_planned = 0.0
        total_real = 0.0
        total_flow_real = 0.0
        total_oee_real = 0.0
        active_line_count = 0
        
        # We need to process all lines in the layout, even if not in Django active_lines (ghosts)
        # But usually Django has the master list.
        # Let's map Django lines by code for easy access
        django_lines_map = {l.get('codigo'): l for l in active_lines if l.get('codigo')}
        
        # Combine layout keys and django keys
        all_line_codes = set(layout_config.keys()).union(django_lines_map.keys())
        
        for line_code in all_line_codes:
            line_data = django_lines_map.get(line_code)
            line_id = line_data.get('id') if line_data else None
            
            # --- PLANNED (Django) ---
            line_planned = 0.0
            if line_id:
                try:
                    curr_d = start_dt.date()
                    end_d = end_dt.date()
                    
                    # Optimization: Fetch range if possible, or loop.
                    # Given strict constraints, we loop.
                    while curr_d <= end_d:
                        # FIX: Use 'linha_id' instead of 'linha' to match Django ViewSet
                        r = requests.get(f"{DJANGO_API_URL}/calendario/", params={"data": curr_d.strftime('%Y-%m-%d'), "linha_id": line_id})
                        if r.ok:
                            res = r.json()
                            entries = res.get('results', []) if isinstance(res, dict) else res
                            for entry in entries:
                                # Filter by shift if period is 'turno'
                                if period == 'turno' and turno_info:
                                    entry_turno = str(entry.get('turno_nome') or '').strip().upper()
                                    current_turno = str(turno_info.get('nome') or '').strip().upper()
                                    
                                    if entry_turno and current_turno and entry_turno != current_turno:
                                        continue
                                
                                meta = float(entry.get('meta_producao_turno', 0) or 0)
                                # Smart conversion: If > 1000, assume KG and convert to Tons. Else assume Tons.
                                if meta > 1000:
                                    meta /= 1000.0
                                    
                                line_planned += meta
                        curr_d += timedelta(days=1)
                except Exception as e:
                    logger.error(f"Error fetching calendar for {line_code}: {e}")
            
            # --- REAL (InfluxDB) ---
            line_real = 0.0
            line_oee = 0.0
            line_tph = 0.0
            line_status = "Sem Dados"
            
            try:
                if period == 'turno':
                    q_real = f"SELECT last(toneladas_turno) as val, last(oee_realtime) as oee, last(velocidade_atual) as vel, last(formato) as fmt, last(estado_maquina) as state FROM production WHERE \"line\" = '{line_code}' GROUP BY equipment"
                    rs = client.query(q_real)
                    points = list(rs.get_points())
                    if points:
                        # Max of equipments
                        line_real = max([p['val'] for p in points if p['val'] is not None] or [0])
                        # OEE
                        line_oee = max([p['oee'] for p in points if p['oee'] is not None] or [0])
                        
                        # TPH Calculation: Average Throughput (Total Produced / Elapsed Time)
                        # This matches the logic in Django backend and user expectation
                        elapsed_seconds = (now - start_dt).total_seconds()
                        elapsed_hours = max(0.016, elapsed_seconds / 3600.0) # Min 1 min
                        
                        line_tph = line_real / elapsed_hours if elapsed_hours > 0 else 0.0
                        
                        states = [p['state'] for p in points if p['state']]
                        if any(s == 1 for s in states): # Assuming 1 is running
                             line_status = "Rodando"
                        elif line_tph > 0:
                             line_status = "Rodando"
                        else:
                             line_status = "Parada"
                else:
                    # Aggregation logic (Day/Week/Month)
                    # Ensure timestamps are in UTC format or compatible string
                    # InfluxDB prefers: 'YYYY-MM-DDTHH:MM:SSZ'
                    s_str = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                    e_str = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                    
                    # Real
                    q_agg = f"SELECT max(toneladas_turno) as val FROM production WHERE \"line\" = '{line_code}' AND time >= '{s_str}' AND time <= '{e_str}' GROUP BY time(4h)"
                    rs_agg = client.query(q_agg)
                    points_agg = list(rs_agg.get_points())
                    line_real = sum([p['val'] for p in points_agg if p['val'] is not None])
                    
                    # OEE (Mean)
                    q_oee = f"SELECT mean(oee_realtime) as oee FROM production WHERE \"line\" = '{line_code}' AND time >= '{s_str}' AND time <= '{e_str}'"
                    rs_oee = client.query(q_oee)
                    points_oee = list(rs_oee.get_points())
                    if points_oee:
                        line_oee = points_oee[0].get('oee', 0) or 0
                        
                    # TPH (Mean)
                    q_vel = f"SELECT mean(velocidade_atual) as vel FROM production WHERE \"line\" = '{line_code}' AND time >= '{s_str}' AND time <= '{e_str}'"
                    rs_vel = client.query(q_vel)
                    points_vel = list(rs_vel.get_points())
                    if points_vel:
                        line_tph = points_vel[0].get('vel', 0) or 0
                    
                    line_status = "Histórico"

            except Exception as e:
                logger.error(f"Error Influx for {line_code}: {e}")

            lines_kpi.append({
                "linha": line_code,
                "oee_real": round(line_oee, 1),
                "oee_planejado": 85.0,
                "producao_real_t": round(line_real, 1),
                "producao_planejada_t": round(line_planned, 1),
                "tph_real": round(line_tph, 1),
                "status": line_status
            })
            
            total_planned += line_planned
            total_real += line_real
            total_flow_real += line_tph
            
            # Only count OEE for active lines (Rodando or with data)
            if line_oee > 0 or line_status == "Rodando":
                total_oee_real += line_oee
                active_line_count += 1

        # 6. Factory Totals
        avg_oee = (total_oee_real / active_line_count) if active_line_count > 0 else 0.0
        
        # Required Flow Rate
        required_flow = 0.0
        if remaining_hours > 0 and total_planned > total_real:
            required_flow = (total_planned - total_real) / remaining_hours
            
        # 7. Construct Layout Response
        layout_fabrica = []
        for line_name, meta in layout_config.items():
            layout_fabrica.append({
                "linha": line_name,
                "area": meta["area"],
                "posicao_x": meta["pos_x"],
                "posicao_y": meta["pos_y"],
                "w": meta.get("w", 1),
                "h": meta.get("h", 1),
                "critico": meta["critico"]
            })
            
        return {
            "oee_fabril_real": round(avg_oee, 1),
            "oee_fabril_planejado": 85.0,
            "producao_real_t": round(total_real, 1),
            "producao_planejada_t": round(total_planned, 1),
            "vazao_total_tph": round(total_flow_real, 1),
            "vazao_necessaria_tph": round(required_flow, 1),
            "linhas": lines_kpi,
            "layout_fabrica": layout_fabrica
        }

    except Exception as e:
        logger.error(f"Critical error in factory KPIs: {e}")
        return {
            "oee_fabril_real": 0,
            "oee_fabril_planejado": 0,
            "producao_real_t": 0,
            "producao_planejada_t": 0,
            "vazao_total_tph": 0,
            "vazao_necessaria_tph": 0,
            "linhas": [],
            "layout_fabrica": []
        }
