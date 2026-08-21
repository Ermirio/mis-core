from flask import current_app
from datetime import datetime

def get_client():
    """
    Helper to get the InfluxDB client from the current Flask app context.
    """
    client = current_app.extensions.get('influx_client')
    if not client:
        raise RuntimeError("InfluxDB client not initialized in Flask app extensions.")
    return client

def get_last_points_by_equipment(line):
    """
    Retrieves the last data points for all equipment in a specific line.
    """
    client = get_client()
    # Querying last values for relevant fields
    query = f'''
        SELECT last(velocidade_atual) as velocidade, 
               last(formato_gramas) as formato,
               last(quality_realtime) as qualidade, 
               last(oee_realtime) as oee,
               last(availability_realtime) as disponibilidade,
               last(performance_realtime) as performance,
               last(estado_maquina) as estado,
               last(toneladas_turno) as toneladas_turno,
               last(producao_turno_acumulada) as producao_turno
        FROM production
        WHERE "line" = '{line}'
        GROUP BY equipment
    '''
    return client.query(query)

def get_equipment_timeseries(equipment, start, end):
    """
    Retrieves time series data for a specific equipment within a time range.
    """
    client = get_client()
    query = f'''
        SELECT mean(velocidade_atual) as velocidade_media,
               max(estado_maquina) as estado_max
        FROM production
        WHERE "equipment" = '{equipment}' 
        AND time >= '{start}' AND time <= '{end}'
        GROUP BY time(1m)
    '''
    return client.query(query)

def get_line_timeseries(line, start, end):
    """
    Retrieves aggregated time series data for a line.
    """
    client = get_client()
    query = f'''
        SELECT sum(toneladas_turno) as total_producao
        FROM production
        WHERE "line" = '{line}'
        AND time >= '{start}' AND time <= '{end}'
        GROUP BY time(1h)
    '''
    return client.query(query)

def get_last_shift_production(line):
    """
    Retrieves the last production metrics for the shift.
    """
    client = get_client()
    query = f'''
        SELECT last(toneladas_turno) as toneladas,
               last(producao_turno_acumulada) as pecas
        FROM production
        WHERE "line" = '{line}'
        GROUP BY equipment
    '''
    return client.query(query)

def get_last_metrics_for_equipment(equipment):
    """
    Retrieves the last metrics for a specific equipment.
    """
    client = get_client()
    query = f'''
        SELECT last(velocidade_atual) as velocidade, 
               last(formato_gramas) as formato,
               last(quality_realtime) as qualidade, 
               last(oee_realtime) as oee,
               last(availability_realtime) as disponibilidade,
               last(performance_realtime) as performance,
               last(estado_maquina) as estado,
               last(toneladas_turno) as toneladas_turno,
               last(producao_turno_acumulada) as producao_turno
        FROM production
        WHERE "equipment" = '{equipment}'
    '''
    return client.query(query)

def get_all_lines():
    """
    Retrieves all available lines.
    """
    client = get_client()
    query = 'SHOW TAG VALUES FROM production WITH KEY = "line"'
    return client.query(query)

def get_last_quality_metrics(line):
    """
    Retrieves the last quality metrics.
    """
    client = get_client()
    query = f'''
        SELECT last(quality_realtime) as quality,
               last(descarte) as descarte
        FROM production
        WHERE "line" = '{line}'
        GROUP BY equipment
    '''
    return client.query(query)

def get_line_production_metrics(line):
    """
    Retrieves aggregated production metrics for a line to be used in factory KPIs.
    """
    client = get_client()
    # We need to get the max production of the line (usually the bottleneck or end of line).
    # Since we don't know which equipment is the end, we take the max of all equipment.
    # Also fetching planned production if available (meta_producao_turno).
    query = f'''
        SELECT last(toneladas_turno) as toneladas_real,
               last(meta_producao_turno) as toneladas_planejadas,
               last(oee_realtime) as oee_real,
               last(oee_planejado) as oee_planejado,
               last(velocidade_atual) as velocidade
        FROM production
        WHERE "line" = '{line}'
        GROUP BY equipment
    '''
    return client.query(query)

def get_factory_production_metrics_by_period(line, start_time, end_time):
    """
    Retrieves aggregated production metrics for a line within a specific time range.
    Used for Day, Week, Month filters.
    """
    client = get_client()
    # For longer periods, we need to sum the production.
    # Assuming 'contagem_saida' is a counter that might reset, using spread or difference might be safer if we had raw data.
    # However, 'toneladas_turno' resets every shift.
    # So, SUM(toneladas_turno) over time? No, that would sum every point.
    # We need the max value of each shift, then sum those max values?
    # Or better: use the 'production' measurement's 'toneladas_produzidas_op' if available?
    # Let's try to sum the differences of 'contagem_saida' (output count) converted to tons.
    # But we don't have the conversion factor easily here without querying metadata.
    
    # Alternative: Use 'toneladas_turno' but we need to be careful not to sum duplicates.
    # If we group by shift (e.g. 8h), we can take the MAX of each shift and SUM them.
    # InfluxDB 1.8 doesn't support subqueries easily in this way.
    
    # Simplified approach for now:
    # 1. Get the spread of 'contagem_saida' (max - min) for the period.
    # 2. Get the last 'formato_gramas'.
    # 3. Calculate tons.
    
    query = f'''
        SELECT spread(contagem_saida) as producao_total_pecas,
               last(formato_gramas) as formato,
               mean(oee_realtime) as oee_medio,
               mean(velocidade_atual) as velocidade_media
        FROM production
        WHERE "line" = '{line}'
        AND time >= '{start_time}' AND time <= '{end_time}'
        GROUP BY equipment
    '''
    return client.query(query)
