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
