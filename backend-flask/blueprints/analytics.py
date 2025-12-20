from flask import Blueprint, request, jsonify, current_app
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

analytics_bp = Blueprint('analytics', __name__)
logger = logging.getLogger(__name__)

def query_influx_to_df(client, tags, start_time, end_time):
    """
    Queries InfluxDB for multiple tags and returns a single aligned DataFrame.
    Assumes tags are in 'production' or 'machine_status' measurements?
    Actually, tags map to Fields in 'production' usually.
    OR 'tags' arg might be a list of dicts: {'measurement': 'production', 'field': 'velocidade'}
    
    For simplicity, assuming all process variables are fields in 'production'.
    """
    try:
        # Build query
        # We need to query each field. If they are in the same measurement, we can query together?
        # InfluxQL is tricky with multiple fields if they have different timestamps (which they might).
        # Best to query individually and merge in Pandas.
        
        dfs = []
        
        for tag_info in tags:
            # tag_info: { 'tag_influx': 'velocidade_atual', 'equipamento_code': 'E001', 'alias': 'Velocidade Enchedora' }
            field = tag_info.get('tag_influx')
            eq_code = tag_info.get('equipamento_code')
            alias = tag_info.get('alias', field)
            
            # Construct Query: SELECT mean("field") FROM "production" WHERE "equipment"='...' AND time > ... GROUP BY time(1m) FILL(null)
            # Using mean/resample in Influx is efficient for long ranges.
            # But for Histogram we want RAW data?
            # If range is huge, raw data is too big.
            # Let's try raw data if range < 24h, else aggregate?
            
            # For correlation, we NEED aligned timestamps.
            # Let's allow resample_interval param.
            
            query = f"SELECT \"{field}\" FROM \"production\" WHERE \"equipment\" = '{eq_code}' AND time >= '{start_time}' AND time <= '{end_time}'"
            
            rs = client.query(query)
            points = list(rs.get_points())
            
            if points:
                df = pd.DataFrame(points)
                df['time'] = pd.to_datetime(df['time'])
                df.set_index('time', inplace=True)
                df.rename(columns={field: alias}, inplace=True)
                # Ensure numeric
                df[alias] = pd.to_numeric(df[alias], errors='coerce')
                dfs.append(df)
        
        if not dfs:
            return pd.DataFrame()
            
        # Merge all DFs on index (outer join to keep all timestamps initially)
        # For correlation, we often need 'inner' or forward fill.
        # concat axis=1 matches indexes
        full_df = pd.concat(dfs, axis=1)
        
        return full_df

    except Exception as e:
        logger.error(f"Error querying influx: {e}")
        return pd.DataFrame()

@analytics_bp.route('/analyze/stats', methods=['POST'])
def analyze_stats():
    """
    Calculates Descriptive Statistics + Cp/Cpk for a SINGLE variable (or list, returning stats for each).
    Payload:
    {
        "variables": [
             { "tag_influx": "...", "equipamento_code": "...", "lsl": 10, "usl": 20, "nominal": 15, "alias": "..." }
        ],
        "start_time": "ISO...",
        "end_time": "ISO...",
        "resample": "1m" (optional)
    }
    """
    data = request.json
    variables = data.get('variables', [])
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    
    influx_client = current_app.extensions.get('influx_client')
    if not influx_client:
        return jsonify({'error': 'DB not connected'}), 500

    results = []

    # Optimize: Query all at once? Or loop?
    # Stats are usually per-variable.
    
    for var in variables:
        df = query_influx_to_df(influx_client, [var], start_time, end_time)
        
        col_name = var.get('alias', var.get('tag_influx'))
        
        if df.empty or col_name not in df.columns:
            results.append({
                'variable': col_name,
                'error': 'No data found'
            })
            continue
            
        series = df[col_name].dropna()
        
        if series.empty:
             results.append({'variable': col_name, 'error': 'Empty data'})
             continue

        # Stats
        mean = float(series.mean())
        std = float(series.std())
        min_val = float(series.min())
        max_val = float(series.max())
        median = float(series.median())
        count = int(series.count())
        
        # Cp/Cpk
        lsl = var.get('lsl')
        usl = var.get('usl')
        
        cp = None
        cpk = None
        
        if lsl is not None and usl is not None and std > 0:
            cp = (usl - lsl) / (6 * std)
            cpu = (usl - mean) / (3 * std)
            cpl = (mean - lsl) / (3 * std)
            cpk = min(cpu, cpl)
            
        # Histogram
        # Numpy histogram
        hist, bin_edges = np.histogram(series, bins='auto') # or 20 bins? 'auto' is good
        
        results.append({
            'variable': col_name,
            'stats': {
                'mean': mean,
                'std': std,
                'min': min_val,
                'max': max_val,
                'median': median,
                'count': count,
                'cp': cp,
                'cpk': cpk
            },
            'histogram': {
                'counts': hist.tolist(),
                'bins': bin_edges.tolist() # Edges has length N+1
            },
            'raw_data_head': series.head(100).tolist() # Optional preview
        })

    return jsonify(results)

@analytics_bp.route('/analyze/correlation', methods=['POST'])
def analyze_correlation():
    """
    Calculates Correlation Matrix and Scatter Data.
    Payload: Same as stats.
    Requires resampling to align timestamps.
    """
    data = request.json
    variables = data.get('variables', [])
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    resample_rule = data.get('resample', '1min') # Default 1 min alignment
    
    influx_client = current_app.extensions.get('influx_client')
    if not influx_client:
        return jsonify({'error': 'DB not connected'}), 500

    df = query_influx_to_df(influx_client, variables, start_time, end_time)
    
    if df.empty:
        return jsonify({'error': 'No data'}), 404

    # Resample to align
    df_resampled = df.resample(resample_rule).mean().dropna() # Use mean for downsampling
    
    if df_resampled.empty:
        return jsonify({'error': 'Insufficient overlap data'}), 400
        
    # Correlation Matrix
    corr_matrix = df_resampled.corr(method='pearson').fillna(0)
    
    # Prepare Scatter Data (matrix of scatter plots? No, usually frontend requests pairs, or we return the full dataset for frontend to scatter?)
    # Return full dataset (JSON optimized) so Plotly can do Scatter Matrix gl
    # Limit rows if too huge
    
    limit = 5000
    if len(df_resampled) > limit:
        df_resampled = df_resampled.sample(n=limit).sort_index()

    return jsonify({
        'correlation_matrix': {
            'columns': corr_matrix.columns.tolist(),
            'values': corr_matrix.values.tolist() # List of lists
        },
        'scatter_data': {
            'index': df_resampled.index.astype(str).tolist(),
            'data': df_resampled.to_dict(orient='list') # { 'col1': [v1, v2...], 'col2': ... }
        }
    })

@analytics_bp.route('/analyze/timeseries', methods=['POST'])
def analyze_timeseries():
    """
    Returns aligned time-series data for Trend and SPC charts.
    Calculates Control Limits (UCL/LCL).
    Payload: Same as stats.
    """
    data = request.json
    variables = data.get('variables', [])
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    # Resample is optional here. For SPC we might want raw data points if count is low, 
    # but for visualization usually we want some alignment or limit.
    # Let's verify data density. If huge, we resample to '1min' or '5min'.
    # For now, let's use a dynamic resample if range > 24h.
    
    influx_client = current_app.extensions.get('influx_client')
    if not influx_client:
        return jsonify({'error': 'DB not connected'}), 500

    # Query without resampling first? Or query_influx_to_df handles it?
    # query_influx_to_df fetches raw points.
    df = query_influx_to_df(influx_client, variables, start_time, end_time)
    
    if df.empty:
        return jsonify({'error': 'No data'}), 404

    # If rows > 5000, resample to avoid frontend lag
    if len(df) > 5000:
        # Determine interval suitable for the range
        # Simple rule: limit to 2000 points?
        rule = '1min' 
        df = df.resample(rule).mean().dropna()

    results = {}
    
    for col in df.columns:
        series = df[col].dropna()
        if series.empty:
            continue
            
        mean = float(series.mean())
        std = float(series.std())
        
        # Search for limit info in request variables to find matching config
        # var config might provide alias
        var_config = next((v for v in variables if v.get('alias', v.get('tag_influx')) == col), None)
        
        ucl = mean + (3 * std)
        lcl = mean - (3 * std)
        
        results[col] = {
            'timestamps': series.index.astype(str).tolist(),
            'values': series.values.tolist(),
            'stats': {
                'mean': mean,
                'std': std,
                'ucl': ucl,
                'lcl': lcl,
                'lsl': var_config.get('lsl') if var_config else None,
                'usl': var_config.get('usl') if var_config else None,
                'nominal': var_config.get('nominal') if var_config else None
            }
        }
        
    return jsonify(results)
