import influx_data_provider

def calcular_tph_real(velocidade, formato_gramas, qualidade):
    """
    Calculates Real TPH (Tonnes Per Hour).
    Formula: (Speed (units/min) * 60 * Weight (g) / 1,000,000) * (Quality / 100)
    """
    try:
        velocidade = float(velocidade or 0)
        formato_gramas = float(formato_gramas or 0)
        qualidade = float(qualidade or 0)
        
        # Theoretical production in tons per hour
        tph_teorico = (velocidade * 60 * formato_gramas) / 1_000_000
        
        # Real production considering quality
        tph_real = tph_teorico * (qualidade / 100.0)
        
        return round(tph_real, 3)
    except Exception:
        return 0.0

def calcular_kpis_linha(line):
    """
    Calculates all KPIs for a given line, including equipment ranking and bottleneck.
    """
    # Get raw data from provider
    raw_data = influx_data_provider.get_last_points_by_equipment(line)
    
    equipamentos = []
    total_availability = 0
    total_performance = 0
    total_quality = 0
    count = 0
    
    # Process raw data
    # influx_client.query returns a ResultSet. items() yields ((name, tags), generator)
    for ((name, tags), points) in raw_data.items():
        equipment_name = tags.get('equipment', 'Unknown')
        
        # Get the last point
        point = list(points)[0] if points else {}
        
        velocidade = point.get('velocidade', 0)
        formato = point.get('formato', 0)
        qualidade = point.get('qualidade', 0)
        oee = point.get('oee', 0)
        disponibilidade = point.get('disponibilidade', 0)
        performance = point.get('performance', 0)
        estado = point.get('estado', 0)
        
        tph = calcular_tph_real(velocidade, formato, qualidade)
        
        eq_data = {
            "nome": equipment_name,
            "tph_real": tph,
            "oee": float(oee or 0),
            "disponibilidade": float(disponibilidade or 0),
            "performance": float(performance or 0),
            "qualidade": float(qualidade or 0),
            "estado": int(estado or 0),
            "velocidade": float(velocidade or 0),
            "formato": float(formato or 0)
        }
        equipamentos.append(eq_data)
        
        if tph > 0: # Only consider active/relevant equipment for averages if needed, or all?
            # Usually averages include all, but if TPH is 0 it might be stopped.
            # For OEE metrics, we usually average all.
            pass
            
        total_availability += float(disponibilidade or 0)
        total_performance += float(performance or 0)
        total_quality += float(qualidade or 0)
        count += 1

    # Calculate Line Averages
    avg_avail = round(total_availability / count, 2) if count > 0 else 0
    avg_perf = round(total_performance / count, 2) if count > 0 else 0
    avg_qual = round(total_quality / count, 2) if count > 0 else 0
    
    # Determine Bottleneck (Lowest TPH among running equipment, or just lowest TPH)
    # If all 0, then N/A.
    # We filter for equipment that "should" be running or just take the min.
    # Let's take the one with lowest TPH but > 0 if possible, or just lowest.
    # If we define bottleneck as the constraint, it's the one with lowest capacity/throughput.
    
    # Sorting by TPH for ranking
    ranking = sorted(equipamentos, key=lambda x: x['tph_real'], reverse=True)
    
    # Bottleneck is the last one in ranking (lowest TPH)
    gargalo = ranking[-1] if ranking else None
    
    # Calculate TPH Medio of the line (this might be the bottleneck's TPH or the output of the last machine)
    # Usually line TPH is determined by the bottleneck.
    tph_line = gargalo['tph_real'] if gargalo else 0
    
    return {
        "linha": line,
        "gargalo": gargalo,
        "ranking": ranking,
        "equipamentos": equipamentos,
        "kpis": {
            "disponibilidade": avg_avail,
            "performance": avg_perf,
            "qualidade": avg_qual,
            "tph_medio": tph_line
        }
    }

def calcular_ranking_e_gargalo(line):
    """
    Returns just the ranking and bottleneck for the line.
    """
    kpis = calcular_kpis_linha(line)
    return {
        "ranking": kpis["ranking"],
        "gargalo": kpis["gargalo"]
    }

def calcular_kpis_equipamento(equipment):
    """
    Calculates KPIs for a specific equipment.
    """
    raw_data = influx_data_provider.get_last_metrics_for_equipment(equipment)
    points = list(raw_data.get_points())
    
    if not points:
        return {}
        
    point = points[0]
    
    velocidade = point.get('velocidade', 0)
    formato = point.get('formato', 0)
    qualidade = point.get('qualidade', 0)
    oee = point.get('oee', 0)
    disponibilidade = point.get('disponibilidade', 0)
    performance = point.get('performance', 0)
    estado = point.get('estado', 0)
    
    tph = calcular_tph_real(velocidade, formato, qualidade)
    
    return {
        "equipamento": equipment,
        "kpis": {
            "tph_real": tph,
            "oee": float(oee or 0),
            "disponibilidade": float(disponibilidade or 0),
            "performance": float(performance or 0),
            "qualidade": float(qualidade or 0),
            "estado": int(estado or 0),
            "velocidade": float(velocidade or 0),
            "formato": float(formato or 0)
        }
    }

import requests
from datetime import datetime, timedelta

DJANGO_API_URL = "http://localhost:8000/api"

def get_planned_production_from_django(start_date, end_date):
    """
    Fetches aggregated planned production from Django API.
    Returns a dictionary {line_code: planned_tons}.
    """
    try:
        # We need to query the calendar for each line within the date range.
        # Since we don't have a direct aggregation endpoint, we might need to fetch all and sum.
        # Optimization: Fetch for all lines in one go if possible, or iterate.
        # Let's assume we iterate over lines later, or fetch all calendar entries for the period.
        
        # Using the existing 'calendario' endpoint with date filtering if supported.
        # If not supported, we might need to fetch day by day or use a custom endpoint.
        # Let's try to fetch by date range if the API supports it (e.g. Django Filter).
        # Based on views.py, it supports 'data' exact match.
        # We need to support range.
        # If range not supported, we can loop dates (inefficient for months).
        # BETTER: Use the 'metricas_fabrica_consolidadas' logic? No, that's for real-time.
        
        # Hack: If period is 'dia', we query for that specific date.
        # If 'semana' or 'mes', we might need to loop or just accept we need a new endpoint.
        # But I can't change Django easily right now without restarting it and risking stability.
        # So I will loop for 'semana' (7 requests) which is fine.
        # For 'mes' (30 requests) it's borderline but maybe acceptable for a prototype.
        
        planned_per_line = {}
        
        # Generate list of dates
        delta = end_date - start_date
        dates = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(delta.days + 1)]
        
        for date_str in dates:
            response = requests.get(f"{DJANGO_API_URL}/calendario/", params={"data": date_str})
            if response.ok:
                entries = response.json()
                for entry in entries:
                    # entry has 'linha' (id), 'turno', 'meta_producao_turno'
                    # We need line CODE, but entry might only have ID.
                    # Let's check serializer. If it returns ID, we need a map.
                    # Assuming we can map ID to Code or it returns nested object.
                    # If it returns nested 'linha': {'codigo': ...}, great.
                    # If just ID, we need a cache of lines.
                    
                    # For now, let's assume we can match by ID if we have the list of lines.
                    # But kpis_engine uses line CODES (strings) from Influx.
                    # We need to map.
                    pass
                    
        return {} # Placeholder until we verify response structure
    except Exception as e:
        print(f"Error fetching planned production: {e}")
        return {}

def calcular_kpis_fabrica(periodo='turno'):
    """
    Calculates aggregated KPIs for the entire factory using weighted averages.
    Supports periods: 'turno', 'dia', 'semana', 'mes'.
    """
    lines_result = influx_data_provider.get_all_lines()
    lines = [p['value'] for p in lines_result.get_points()]
    
    factory_kpis = {
        "oee_fabril_real": 0.0,
        "oee_fabril_planejado": 0.0,
        "producao_real_t": 0.0,
        "producao_planejada_t": 0.0,
        "vazao_total_tph": 0.0,
        "linhas": [],
        "layout_fabrica": []
    }
    
    total_prod_real_weighted_oee = 0.0
    total_prod_real = 0.0
    
    total_prod_plan_weighted_oee = 0.0
    total_prod_plan = 0.0
    
    total_tph = 0.0
    
    # Determine time range
    now = datetime.now()
    if periodo == 'turno':
        # Logic remains similar to before (current shift)
        start_time = None # Handled by provider
        end_time = None
    elif periodo == 'dia':
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = now
    elif periodo == 'semana':
        start_time = now - timedelta(days=now.weekday()) # Start of week (Monday)
        start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = now
    elif periodo == 'mes':
        start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_time = now
    else:
        start_time = None
        end_time = None

    # Fetch planned production map if not 'turno'
    planned_map = {}
    if periodo != 'turno' and start_time:
        # We need to implement the fetch logic properly.
        # Since we can't easily map IDs to Codes without fetching lines from Django,
        # let's fetch lines first.
        try:
            r_lines = requests.get(f"{DJANGO_API_URL}/linhas/")
            if r_lines.ok:
                lines_data = r_lines.json()
                # Map ID -> Code
                id_to_code = {l['id']: l['codigo'] for l in lines_data}
                
                # Now fetch calendar
                delta = end_time - start_time
                dates = [(start_time + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(delta.days + 1)]
                
                for date_str in dates:
                    r_cal = requests.get(f"{DJANGO_API_URL}/calendario/", params={"data": date_str})
                    if r_cal.ok:
                        cal_entries = r_cal.json()
                        for entry in cal_entries:
                            # entry['linha'] is likely an ID or object depending on serializer.
                            # Standard ModelSerializer with depth=0 uses ID.
                            line_id = entry.get('linha')
                            # If it's an object
                            if isinstance(line_id, dict):
                                line_code = line_id.get('codigo')
                            else:
                                line_code = id_to_code.get(line_id)
                                
                            if line_code:
                                meta = entry.get('meta_producao_turno', 0)
                                planned_map[line_code] = planned_map.get(line_code, 0) + meta
        except Exception as e:
            print(f"Error fetching Django data: {e}")

    # Static Layout Configuration
    # Grid System: x (0-12), y (0-6)
    # Dimensions: w (width), h (height)
    layout_config = {
        # Left Column (Horizontal/Boxy)
        "L20": {"area": "PREPARO", "pos_x": 0, "pos_y": 0, "w": 2, "h": 1, "critico": False},
        "L15": {"area": "PREPARO", "pos_x": 0, "pos_y": 1.2, "w": 2, "h": 1, "critico": False},
        "L19": {"area": "PREPARO", "pos_x": 0, "pos_y": 2.4, "w": 1.5, "h": 1.5, "critico": False},
        
        # Middle-Left
        "L20_B": {"area": "PREPARO", "pos_x": 1.6, "pos_y": 2.4, "w": 1.5, "h": 1.5, "critico": False}, # Assuming L20 appears twice or split
        
        # Middle Column
        "L16": {"area": "MISTURA", "pos_x": 3.5, "pos_y": 2.4, "w": 1, "h": 1.5, "critico": False},
        "L06": {"area": "ENVASE PÓS", "pos_x": 4.8, "pos_y": 2.4, "w": 1, "h": 1.5, "critico": False},
        
        # Middle-Right (Horizontal)
        "L18": {"area": "MISTURA", "pos_x": 6, "pos_y": 1.5, "w": 2, "h": 0.8, "critico": False},
        "L17": {"area": "MISTURA", "pos_x": 6, "pos_y": 2.5, "w": 2, "h": 1.2, "critico": False},

        # Right Column (Vertical Lines)
        "L10": {"area": "EMBALAGEM", "pos_x": 8.5, "pos_y": 0, "w": 1, "h": 4, "critico": True},
        "L02": {"area": "MISTURA", "pos_x": 9.8, "pos_y": 0, "w": 1, "h": 4, "critico": True},
        "L01": {"area": "ENVASE LÍQ", "pos_x": 11.1, "pos_y": 0, "w": 1, "h": 4, "critico": False},
        "L09": {"area": "ENVASE", "pos_x": 12.4, "pos_y": 0, "w": 1, "h": 4, "critico": False}
    }
    
    for line in lines:
        # Initialize line aggregates
        line_prod_real = 0.0
        line_prod_plan = 0.0
        line_oee_real = 0.0
        line_oee_plan = 0.0
        line_tph = 0.0
        line_status = "Parada"
        
        if periodo == 'turno':
            # Use existing logic for Turno
            raw_metrics = influx_data_provider.get_line_production_metrics(line)
            
            points_list = []
            for ((name, tags), points) in raw_metrics.items():
                for p in points:
                    points_list.append(p)
                    
            if points_list:
                line_prod_real = max([float(p.get('toneladas_real') or 0) for p in points_list], default=0.0)
                line_prod_plan = max([float(p.get('toneladas_planejadas') or 0) for p in points_list], default=0.0)
                
                oees = [float(p.get('oee_real') or 0) for p in points_list]
                line_oee_real = sum(oees) / len(oees) if oees else 0.0
                
                oees_plan = [float(p.get('oee_planejado') or 0) for p in points_list]
                line_oee_plan = sum(oees_plan) / len(oees_plan) if oees_plan else 0.0
                
                detailed_kpis = calcular_kpis_linha(line)
                line_tph = detailed_kpis['kpis']['tph_medio']
                line_status = "Rodando" if line_tph > 0 else "Parada"
                
        else:
            # Logic for Day/Week/Month
            # 1. Get Real Production from Influx (Aggregated)
            # We use the new function
            start_str = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
            end_str = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            raw_metrics = influx_data_provider.get_factory_production_metrics_by_period(line, start_str, end_str)
            
            points_list = []
            for ((name, tags), points) in raw_metrics.items():
                for p in points:
                    points_list.append(p)
            
            if points_list:
                # We used 'spread(contagem_saida)' -> 'producao_total_pecas'
                total_pecas = sum([float(p.get('producao_total_pecas') or 0) for p in points_list])
                # We need format to convert to tons.
                # Assuming format is constant or taking the last one.
                formato = max([float(p.get('formato') or 0) for p in points_list], default=0.0)
                
                if formato > 0:
                    line_prod_real = (total_pecas * formato) / 1_000_000
                else:
                    line_prod_real = 0.0
                
                # OEE Real (Average over period)
                oees = [float(p.get('oee_medio') or 0) for p in points_list]
                line_oee_real = sum(oees) / len(oees) if oees else 0.0
                
                # TPH (Average over period)
                vels = [float(p.get('velocidade_media') or 0) for p in points_list]
                avg_vel = sum(vels) / len(vels) if vels else 0.0
                # Approx TPH
                line_tph = (avg_vel * 60 * formato) / 1_000_000 if formato > 0 else 0.0
                
                line_status = "Rodando" if line_tph > 0 else "Parada" # Status at end of period? Or general?
                # For historical view, status might be less relevant, or "Active" if it produced anything.
            
            # 2. Get Planned Production from Map
            # planned_map has 'meta_producao_turno' (units). We need tons?
            # The model says 'meta_producao_turno' is Integer (units).
            # We need to convert to tons using the format.
            # We have 'formato' from Influx.
            # If we don't have format from Influx (no production), we can't convert easily without querying product DB.
            # Fallback: If format > 0, convert. Else 0.
            
            planned_units = planned_map.get(line, 0)
            # We need format. If we found it in Influx, use it.
            # If not, we might be missing it.
            # Let's use the one found in Influx points.
            formato_plan = max([float(p.get('formato') or 0) for p in points_list], default=0.0) if points_list else 0.0
            
            if formato_plan > 0:
                line_prod_plan = (planned_units * formato_plan) / 1_000_000
            else:
                # Try to get format from last known point if possible?
                # For now, 0.
                line_prod_plan = 0.0

        # Aggregation for Factory
        total_prod_real += line_prod_real
        total_prod_plan += line_prod_plan
        total_tph += line_tph
        
        # Weighted OEE Real
        if line_prod_real > 0:
            total_prod_real_weighted_oee += (line_oee_real * line_prod_real)
            
        # Weighted OEE Planned
        if line_prod_plan > 0 and line_oee_plan > 0:
            total_prod_plan_weighted_oee += (line_oee_plan * line_prod_plan)
            
        # Add to list
        factory_kpis["linhas"].append({
            "linha": line,
            "oee_real": round(line_oee_real, 1),
            "oee_planejado": round(line_oee_plan, 1) if line_oee_plan > 0 else None,
            "producao_real_t": round(line_prod_real, 3),
            "producao_planejada_t": round(line_prod_plan, 3),
            "tph_real": round(line_tph, 1),
            "status": line_status
        })

    # Add Layout Metadata (Iterate over config to ensure all mapped lines appear)
    # Also add "ghost" lines (lines in layout but not in current data) to the lines list with empty data
    existing_lines = set([l['linha'] for l in factory_kpis["linhas"]])
    
    for line_name, meta in layout_config.items():
        # Add layout info
        factory_kpis["layout_fabrica"].append({
            "linha": line_name,
            "area": meta["area"],
            "posicao_x": meta["pos_x"],
            "posicao_y": meta["pos_y"],
            "w": meta.get("w", 1),
            "h": meta.get("h", 1),
            "critico": meta["critico"]
        })
        
        # Add ghost line if missing
        if line_name not in existing_lines:
            factory_kpis["linhas"].append({
                "linha": line_name,
                "oee_real": 0.0,
                "oee_planejado": None,
                "producao_real_t": 0.0,
                "producao_planejada_t": 0.0,
                "tph_real": 0.0,
                "status": "Sem Dados"
            })

    # Final Calculations
    if total_prod_real > 0:
        factory_kpis["oee_fabril_real"] = round(total_prod_real_weighted_oee / total_prod_real, 1)
    
    # For Planned OEE, we need a separate denominator of lines that had planned OEE
    denom_plan = sum([l["producao_planejada_t"] for l in factory_kpis["linhas"] if l["oee_planejado"] is not None])
    if denom_plan > 0:
        factory_kpis["oee_fabril_planejado"] = round(total_prod_plan_weighted_oee / denom_plan, 1)

    factory_kpis["producao_real_t"] = round(total_prod_real, 3)
    factory_kpis["producao_planejada_t"] = round(total_prod_plan, 3)
    factory_kpis["vazao_total_tph"] = round(total_tph, 1)
        
    return factory_kpis
