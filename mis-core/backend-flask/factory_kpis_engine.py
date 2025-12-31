import logging
import requests
from datetime import datetime, timedelta, time
from flask import current_app
from decouple import config
import calendar
from constants import ESTADOS_MAQUINA

logger = logging.getLogger(__name__)

DJANGO_API_URL = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')

def calculate_instantaneous_tph(client, line_code):
    """
    Calculates Instantaneous TPH based on current speed and format.
    Formula: (RPM * 60 * Format(g)) / 1,000,000
    """
    try:
        q = f"SELECT last(velocidade_atual) as vel, last(formato_gramas) as fmt, last(formato) as fmt_fallback FROM production WHERE \"line\" = '{line_code}'"
        rs = client.query(q)
        points = list(rs.get_points())
        if points:
            p = points[0]
            vel = float(p.get('vel', 0) or 0)
            fmt = float(p.get('fmt') or p.get('fmt_fallback') or 0)
            
            # TPH = (RPM * 60 * Grams) / 1,000,000
            tph = (vel * 60 * fmt) / 1000000.0
            return tph
    except Exception as e:
        logger.error(f"Error calc instantaneous TPH for {line_code}: {e}")
    return 0.0

def calculate_day_metrics(client, line_code, start_dt, end_dt):
    """
    Calculates Day Metrics by summing the max production of each shift in the day.
    """
    total_prod = 0.0
    try:
        # Query max production per shift within the day window
        # We group by shift tag to get the peak of each shift
        s_str = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        e_str = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        q = f"SELECT max(toneladas_turno) as val FROM production WHERE \"line\" = '{line_code}' AND time >= '{s_str}' AND time <= '{e_str}' GROUP BY shift"
        rs = client.query(q)
        
        # rs.items() returns (tags, generator)
        for (tags, points) in rs.items():
            for p in points:
                total_prod += float(p.get('val', 0) or 0)
                
    except Exception as e:
        logger.error(f"Error calc day metrics for {line_code}: {e}")
        
    return total_prod

def get_primeiro_equipamento_por_linha():
    """
    Retorna um dict { 'L10': 'L10_Enchedora', 'L06': 'L06_Enchedora', ... }
    usando Django /equipamentos/por_linha/ e ordenando por ordem_na_linha.
    """
    mapping = {}
    try:
        resp = requests.get(f"{DJANGO_API_URL}/linhas/", timeout=3)
        if not resp.ok:
            return mapping
        data = resp.json()
        linhas = data.get('results', data) if isinstance(data, dict) else data

        for linha in linhas:
            line_code = linha.get('codigo')
            line_id = linha.get('id')
            if not line_code or not line_id:
                continue

            # Usa a action por_linha que você já tem ou filtra equipamentos
            # Assumindo que /equipamentos/?linha=<id> funciona
            r_eq = requests.get(
                f"{DJANGO_API_URL}/equipamentos/",
                params={"linha": line_id},
                timeout=3
            )
            if not r_eq.ok:
                continue

            eqs_data = r_eq.json()
            eqs_list = eqs_data.get('results', eqs_data) if isinstance(eqs_data, dict) else eqs_data

            # Garante ordenação pelo campo ordem_na_linha
            eqs_ordenados = sorted(
                eqs_list,
                key=lambda e: e.get('ordem_na_linha') or 999
            )

            if eqs_ordenados:
                mapping[line_code] = eqs_ordenados[0].get('codigo')
    except Exception as e:
        logger.error(f"Erro ao montar mapa primeiro equipamento por linha: {e}")
    return mapping

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
        
        # Define Production Day Start (usually 06:00)
        # If we are before 06:00, we belong to the previous day's production cycle?
        # For simplicity, let's assume standard day 00:00-23:59 for "Dia" filter unless specified otherwise.
        # User said "terceiro turno da 00 até a hora atual", implying calendar day logic for "Dia".
        
        if period == 'turno':
            turno_info = shift_manager.get_turno_info()
            if turno_info:
                start_time = turno_info['inicio']
                end_time = turno_info['fim']
                
                start_dt = datetime.combine(today, start_time)
                end_dt = datetime.combine(today, end_time)
                
                if start_time > now.time(): # Started yesterday
                     start_dt -= timedelta(days=1)
                
                if end_time < start_time: # Ends next day
                    if now.time() < start_time: # We are in the "next day" part
                        pass 
                    else:
                        end_dt += timedelta(days=1)
                
                remaining_seconds = (end_dt - now).total_seconds()
                remaining_hours = max(0, remaining_seconds / 3600.0)
                
        elif period == 'dia':
            # User logic: "produção total é os 3 turnos do dia... pegando terceiro turno da 00 até a hora atual"
            # This implies we start at 00:00 today.
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

        # 3. Layout Configuration
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
        
        django_lines_map = {l.get('codigo'): l for l in active_lines if l.get('codigo')}
        all_line_codes = set(layout_config.keys()).union(django_lines_map.keys())
        
        # Load 1st Equipment Map
        primeiro_eq_map = get_primeiro_equipamento_por_linha()
        
        for line_code in all_line_codes:
            line_data = django_lines_map.get(line_code)
            line_id = line_data.get('id') if line_data else None
            
            # --- PLANNED (Django) ---
            line_planned = 0.0
            if line_id:
                try:
                    curr_d = start_dt.date()
                    end_d = end_dt.date()
                    
                    while curr_d <= end_d:
                        # FIX: Use 'linha_id' instead of 'linha'
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
            estado_primeiro_codigo = None
            estado_primeiro_texto = None
            
            try:
                if period == 'turno':
                    # Shift View: Realtime Production + Instantaneous TPH
                    q_real = f"SELECT last(toneladas_turno) as val, last(oee_realtime) as oee, last(estado_maquina) as state FROM production WHERE \"line\" = '{line_code}' GROUP BY equipment"
                    rs = client.query(q_real)
                    points = list(rs.get_points())
                    if points:
                        line_real = max([p['val'] for p in points if p['val'] is not None] or [0])
                        line_oee = max([p['oee'] for p in points if p['oee'] is not None] or [0])
                        
                        # Instantaneous TPH for Shift View
                        line_tph = calculate_instantaneous_tph(client, line_code)
                        
                        # --- NEW STATUS LOGIC: 1st Equipment ---
                        # ESTADOS_MAQUINA imported from constants
                        
                        estado_primeiro_codigo = None
                        estado_primeiro_texto = "Sem Dados"
                        
                        primeiro_eq = primeiro_eq_map.get(line_code)
                        if primeiro_eq:
                            try:
                                q_state = f"SELECT last(estado_maquina) as state FROM production WHERE \"equipment\" = '{primeiro_eq}'"
                                rs_state = client.query(q_state)
                                pts_state = list(rs_state.get_points())
                                if pts_state:
                                    estado_primeiro_codigo = int(pts_state[0].get('state', 0) or 0)
                                    estado_primeiro_texto = ESTADOS_MAQUINA.get(estado_primeiro_codigo, str(estado_primeiro_codigo))
                            except Exception as e:
                                logger.error(f"Erro lendo estado 1o eq {primeiro_eq}: {e}")

                        if estado_primeiro_codigo is not None:
                            line_status = estado_primeiro_texto
                            logger.info(f"[{line_code}] Status via 1o Eq ({primeiro_eq}): {line_status} ({estado_primeiro_codigo})")
                        else:
                            # Fallback to old logic
                            states = [p['state'] for p in points if p.get('state') is not None]
                            logger.warning(f"[{line_code}] Fallback triggered. 1o Eq: {primeiro_eq}, States: {states}, TPH: {line_tph}")
                            if any(s == 1 for s in states) or line_tph > 0:
                                line_status = "Rodando"
                            else:
                                line_status = "Parada"
                else:
                    # Day/Week/Month View: Aggregated Production + Average TPH
                    line_real = calculate_day_metrics(client, line_code, start_dt, end_dt)
                    
                    # OEE (Mean)
                    s_str = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                    e_str = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                    q_oee = f"SELECT mean(oee_realtime) as oee FROM production WHERE \"line\" = '{line_code}' AND time >= '{s_str}' AND time <= '{e_str}'"
                    rs_oee = client.query(q_oee)
                    points_oee = list(rs_oee.get_points())
                    if points_oee:
                        line_oee = points_oee[0].get('oee', 0) or 0
                        
                    # Average TPH = Total Produced / Elapsed Time
                    elapsed_seconds = (now - start_dt).total_seconds()
                    elapsed_hours = max(0.016, elapsed_seconds / 3600.0)
                    line_tph = line_real / elapsed_hours if elapsed_hours > 0 else 0.0
                    
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
                "status": line_status,
                "estado_primeiro_equipamento_codigo": estado_primeiro_codigo if period == 'turno' else None,
                "estado_primeiro_equipamento": estado_primeiro_texto if period == 'turno' else None
            })
            
            total_planned += line_planned
            total_real += line_real
            total_flow_real += line_tph
            
            if line_oee > 0 or line_status == "Rodando":
                total_oee_real += line_oee
                active_line_count += 1

        # 6. Factory Totals
        avg_oee = (total_oee_real / active_line_count) if active_line_count > 0 else 0.0
        
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

def get_factory_map_data():
    """
    Retorna dados específicos para o mapa do chão de fábrica:
    - Status da linha (baseado no 1º equipamento)
    - OLE (OEE da linha)
    - Layout
    """
    try:
        # 1. Access Dependencies
        client = current_app.extensions.get('influx_client')
        if not client:
            raise RuntimeError("Influx Client not initialized")
            
        # 2. Layout Configuration (Same as get_factory_kpis)
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
        
        # 3. Load 1st Equipment Map
        primeiro_eq_map = get_primeiro_equipamento_por_linha()
        
        map_data = []
        
        for line_code, meta in layout_config.items():
            line_status = "Sem Dados"
            line_ole = 0.0
            estado_codigo = None
            
            # --- Status via 1st Equipment ---
            primeiro_eq = primeiro_eq_map.get(line_code)
            if primeiro_eq:
                try:
                    q_state = f"SELECT last(estado_maquina) as state FROM production WHERE \"equipment\" = '{primeiro_eq}'"
                    rs_state = client.query(q_state)
                    pts_state = list(rs_state.get_points())
                    if pts_state:
                        estado_codigo = int(pts_state[0].get('state', 0) or 0)
                        line_status = ESTADOS_MAQUINA.get(estado_codigo, str(estado_codigo))
                except Exception as e:
                    logger.error(f"Error fetching map status for {line_code}: {e}")
            
            # --- OLE (Realtime) ---
            try:
                q_oee = f"SELECT last(oee_realtime) as oee FROM production WHERE \"line\" = '{line_code}' GROUP BY equipment"
                rs_oee = client.query(q_oee)
                points_oee = list(rs_oee.get_points())
                if points_oee:
                    # Max OEE of equipments in line (simplification for realtime)
                    line_ole = max([p['oee'] for p in points_oee if p['oee'] is not None] or [0])
            except Exception as e:
                logger.error(f"Error fetching map OLE for {line_code}: {e}")

            map_data.append({
                "linha": line_code,
                "status": line_status,
                "ole": round(line_ole, 1),
                "layout": {
                    "area": meta["area"],
                    "pos_x": meta["pos_x"],
                    "pos_y": meta["pos_y"],
                    "w": meta.get("w", 1),
                    "h": meta.get("h", 1),
                    "critico": meta["critico"]
                }
            })
            
        return map_data

    except Exception as e:
        logger.error(f"Critical error in factory map data: {e}")
        return []
