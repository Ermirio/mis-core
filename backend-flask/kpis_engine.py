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

def calcular_kpis_fabrica():
    """
    Calculates aggregated KPIs for the entire factory.
    """
    lines_result = influx_data_provider.get_all_lines()
    lines = [p['value'] for p in lines_result.get_points()]
    
    factory_kpis = {
        "linhas": [],
        "total_linhas": len(lines),
        "media_oee": 0,
        "media_disponibilidade": 0,
        "media_performance": 0,
        "media_qualidade": 0
    }
    
    total_oee = 0
    total_avail = 0
    total_perf = 0
    total_qual = 0
    count = 0
    
    for line in lines:
        kpis = calcular_kpis_linha(line)
        factory_kpis["linhas"].append({
            "linha": line,
            "kpis": kpis["kpis"]
        })
        
        # Aggregate if valid
        if kpis["kpis"]["disponibilidade"] > 0 or kpis["kpis"]["performance"] > 0:
            total_avail += kpis["kpis"]["disponibilidade"]
            total_perf += kpis["kpis"]["performance"]
            total_qual += kpis["kpis"]["qualidade"]
            # OEE approximation
            oee = (kpis["kpis"]["disponibilidade"]/100) * (kpis["kpis"]["performance"]/100) * (kpis["kpis"]["qualidade"]/100) * 100
            total_oee += oee
            count += 1
            
    if count > 0:
        factory_kpis["media_oee"] = round(total_oee / count, 2)
        factory_kpis["media_disponibilidade"] = round(total_avail / count, 2)
        factory_kpis["media_performance"] = round(total_perf / count, 2)
        factory_kpis["media_qualidade"] = round(total_qual / count, 2)
        
    return factory_kpis
