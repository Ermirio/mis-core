from flask import Blueprint, request, jsonify, current_app
import pandas as pd
import numpy as np
from scipy import stats as scipy_stats
from datetime import datetime, timedelta
import pytz
import logging

analytics_bp = Blueprint('analytics', __name__)
logger = logging.getLogger(__name__)

def query_influx_to_df(client, tags, start_time, end_time, interval=None):
    """
    Queries InfluxDB for multiple tags and returns a single aligned DataFrame.

    interval: se fornecido (ex: '5s', '1m'), usa GROUP BY time(interval) LAST()
              diretamente no InfluxDB — preserva oscilações reais dos sensores.
              Se None, retorna dados raw sem agregação (para stats/correlação).
    """
    try:
        import requests as http_requests
        
        # Mapping for consolidated metrics: tag_influx -> influx field + aggregation
        # NOTA: 'descarte' no InfluxDB está sempre 0, o valor correto está em 'refugo_op_acumulado'
        CONSOLIDATED_METRICS = {
            'producao_linha_tons': {'field': 'contagem_saida', 'agg': 'sum', 'convert_tons': True},
            'descarte_linha_tons': {'field': 'refugo_op_acumulado', 'agg': 'last_diff', 'convert_tons': True},  # Usa refugo_op_acumulado
            'descarte_linha_perc': {'field': 'refugo_op_acumulado', 'agg': 'percent'},
            'oee_linha': {'field': 'oee_realtime', 'agg': 'mean'},
            'disponibilidade_linha': {'field': 'availability_realtime', 'agg': 'mean'},
            'performance_linha': {'field': 'performance_realtime', 'agg': 'mean'},
            'qualidade_linha': {'field': 'quality_realtime', 'agg': 'mean'},
            'vazao_linha_ton_h': {'field': 'velocidade_atual', 'agg': 'mean'}
        }
        
        dfs = []
        
        for tag_info in tags:
            field = tag_info.get('tag_influx')
            eq_code = tag_info.get('equipamento_code')
            alias = tag_info.get('alias', field)
            
            # Check if this is a consolidated metric
            # Check if this is a consolidated metric
            if field in CONSOLIDATED_METRICS:
                # Get all equipment codes for this line
                try:
                    django_url = f"http://mis-core-django:8000/api/equipamentos/?linha__codigo={eq_code}"
                    resp = http_requests.get(django_url, timeout=5)
                    if resp.status_code == 200:
                        eq_data = resp.json()
                        equipment_list = eq_data.get('results', eq_data) if isinstance(eq_data, dict) else eq_data
                        equipment_codes = [e.get('codigo') for e in equipment_list if e.get('codigo')]
                    else:
                        equipment_codes = []
                        equipment_list = []
                except Exception as e:
                    logger.warning(f"Could not fetch equipment list for line {eq_code}: {e}")
                    equipment_codes = []
                    equipment_list = []
                
                if not equipment_codes:
                    continue
                
                # Query each equipment and aggregate
                metric_config = CONSOLIDATED_METRICS[field]
                influx_field = metric_config['field']
                all_eq_dfs = []
                
                for eq in equipment_codes:
                    query = f"SELECT \"{influx_field}\" FROM \"production\" WHERE \"equipment\" = '{eq}' AND time >= '{start_time}' AND time <= '{end_time}'"
                    rs = client.query(query)
                    points = list(rs.get_points())
                    
                    if points:
                        df_eq = pd.DataFrame(points)
                        df_eq['time'] = pd.to_datetime(df_eq['time'], utc=True).dt.tz_convert('America/Sao_Paulo')
                        df_eq.set_index('time', inplace=True)
                        df_eq[influx_field] = pd.to_numeric(df_eq[influx_field], errors='coerce')
                        df_eq['equipment'] = eq  # Tag para identificar equipamento
                        all_eq_dfs.append(df_eq)
                
                if all_eq_dfs:
                    # Combine all equipment data
                    combined = pd.concat(all_eq_dfs, axis=0)
                    
                    # Resample and aggregate based on type
                    if metric_config['agg'] == 'sum':
                        agg_series = combined[influx_field].resample('1min').sum()
                    elif metric_config['agg'] == 'mean':
                        agg_series = combined[influx_field].resample('1min').mean()
                    elif metric_config['agg'] == 'last_diff':
                        # Para contadores acumulativos: pega o ÚLTIMO valor de cada equipamento por minuto
                        # e soma todos equipamentos
                        agg_series = combined.groupby('equipment')[influx_field].resample('1min').last().groupby(level=1).sum()
                    else:
                        agg_series = combined[influx_field].resample('1min').mean()
                    
                    # Convert to tons if needed
                    if metric_config.get('convert_tons'):
                        # Get format from first equipment (simplification)
                        try:
                            fmt_query = f"SELECT last(\"formato_gramas\") FROM \"production\" WHERE \"equipment\" = '{equipment_codes[0]}'"
                            fmt_rs = client.query(fmt_query)
                            fmt_pts = list(fmt_rs.get_points())
                            formato = float(fmt_pts[0].get('last', 500)) if fmt_pts else 500.0
                        except:
                            formato = 500.0
                        agg_series = agg_series * formato / 1000000.0
                    
                    df_agg = pd.DataFrame({alias: agg_series})
                    dfs.append(df_agg)

            # === GIVE AWAY (Calculated Series) ===
            elif field in ['giveaway_linha_kg', 'giveaway_linha_perc']:
                try:
                    # 1. Busca configs de equipamento
                    django_url = f"http://mis-core-django:8000/api/equipamentos/?linha__codigo={eq_code}"
                    resp = http_requests.get(django_url, timeout=5)
                    eq_list = []
                    if resp.status_code == 200:
                        data = resp.json()
                        eq_list = data.get('results', data) if isinstance(data, dict) else data
                    
                    # 2. Identifica Weighing Equipment (Enchedora > Balança > Ordem 1)
                    weighing_eq = next((e['codigo'] for e in eq_list if e.get('tipo') == 'ENCHEDORA'), None)
                    if not weighing_eq:
                        weighing_eq = next((e['codigo'] for e in eq_list if e.get('tipo') == 'BALANCA'), None)
                    if not weighing_eq:
                        weighing_eq = next((e['codigo'] for e in eq_list if e.get('ordem_na_linha') == 1), None)
                    
                    if weighing_eq:
                        # 3. Query Específica
                        # MEAN(peso), LAST(meta), DIFF(count)
                        q_ga = f"""
                            SELECT 
                                MEAN("ultimo_peso") as peso_medio, 
                                LAST("formato_gramas") as peso_alvo, 
                                NON_NEGATIVE_DIFFERENCE(LAST("contagem_saida")) as producao 
                            FROM "production" 
                            WHERE "equipment" = '{weighing_eq}' 
                            AND time >= '{start_time}' AND time <= '{end_time}' 
                            GROUP BY time(1m)
                        """
                        rs_ga = client.query(q_ga)
                        points_ga = list(rs_ga.get_points())
                        
                        if points_ga:
                            df_ga = pd.DataFrame(points_ga)
                            df_ga['time'] = pd.to_datetime(df_ga['time'], utc=True).dt.tz_convert('America/Sao_Paulo')
                            df_ga.set_index('time', inplace=True)
                            
                            df_ga['peso_medio'] = pd.to_numeric(df_ga['peso_medio'], errors='coerce')
                            df_ga['peso_alvo'] = pd.to_numeric(df_ga['peso_alvo'], errors='coerce')
                            df_ga['producao'] = pd.to_numeric(df_ga['producao'], errors='coerce').fillna(0)
                            
                            # Cálculo: (Medio - Alvo) * Prod / 1000
                            df_ga['_giveaway_kg'] = (df_ga['peso_medio'] - df_ga['peso_alvo']) * df_ga['producao'] / 1000.0
                            
                            if field == 'giveaway_linha_perc':
                                prod_ref = (df_ga['peso_alvo'] * df_ga['producao'] / 1000.0).replace(0, np.nan)
                                series_result = (df_ga['_giveaway_kg'] / prod_ref * 100).fillna(0)
                            else:
                                series_result = df_ga['_giveaway_kg']
                                
                            df_final = pd.DataFrame({alias: series_result})
                            dfs.append(df_final)

                except Exception as e:
                    logger.error(f"Erro calculando Give Away para {eq_code}: {e}")

            else:

                # Standard equipment-level query
                if interval:
                    # GROUP BY no InfluxDB: preserva resolução real dos dados
                    query = f"SELECT LAST(\"{field}\") AS \"{field}\" FROM \"production\" WHERE \"equipment\" = '{eq_code}' AND time >= '{start_time}' AND time <= '{end_time}' GROUP BY time({interval}) fill(none)"
                else:
                    query = f"SELECT \"{field}\" FROM \"production\" WHERE \"equipment\" = '{eq_code}' AND time >= '{start_time}' AND time <= '{end_time}'"
                
                rs = client.query(query)
                points = list(rs.get_points())
                
                if points:
                    df = pd.DataFrame(points)
                    df['time'] = pd.to_datetime(df['time'], utc=True).dt.tz_convert('America/Sao_Paulo')
                    df.set_index('time', inplace=True)
                    df.rename(columns={field: alias}, inplace=True)
                    df[alias] = pd.to_numeric(df[alias], errors='coerce')
                    dfs.append(df)
        
        if not dfs:
            return pd.DataFrame()
            
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
    Calculates Correlation Matrix (Pearson or Spearman) with p-values and Scatter Data.
    Payload:
    {
        "variables": [...],
        "start_time": "ISO...",
        "end_time": "ISO...",
        "method": "pearson" | "spearman"  (optional, default pearson)
    }
    """
    data = request.json
    variables = data.get('variables', [])
    start_time = data.get('start_time')
    end_time = data.get('end_time')

    # Validate correlation method — never trust user input directly
    method = data.get('method', 'pearson')
    if method not in ('pearson', 'spearman'):
        method = 'pearson'

    influx_client = current_app.extensions.get('influx_client')
    if not influx_client:
        return jsonify({'error': 'DB not connected'}), 500

    df = query_influx_to_df(influx_client, variables, start_time, end_time)

    if df.empty:
        return jsonify({'error': 'No data'}), 404

    # --- Resample dinâmico baseado no volume de dados ---
    # Calcula intervalo ideal para manter ~2000 pontos no resultado
    if len(df) > 2000:
        total_seconds = (df.index[-1] - df.index[0]).total_seconds()
        target_points = 2000
        interval_seconds = max(60, int(total_seconds / target_points))
        # Arredonda para intervalos amigáveis
        if interval_seconds < 120:
            resample_rule = '1min'
        elif interval_seconds < 300:
            resample_rule = '2min'
        elif interval_seconds < 600:
            resample_rule = '5min'
        elif interval_seconds < 1800:
            resample_rule = '10min'
        elif interval_seconds < 3600:
            resample_rule = '30min'
        else:
            resample_rule = '1h'
    else:
        resample_rule = '1min'

    df_resampled = df.resample(resample_rule).last()

    if df_resampled.dropna(how='all').empty:
        return jsonify({'error': 'Insufficient overlap data'}), 400

    # Remove colunas sem nenhum dado (variáveis deselectionadas ou sem dados no período)
    df_resampled = df_resampled.dropna(axis=1, how='all')

    if df_resampled.shape[1] < 2:
        return jsonify({'error': 'Insufficient variables with data'}), 400

    # --- Correlation Matrix (pairwise — cada par usa apenas as linhas onde ambos têm dados) ---
    corr_matrix = df_resampled.corr(method=method, min_periods=3).fillna(0)
    cols = corr_matrix.columns.tolist()
    n = len(df_resampled)

    # --- P-values matrix via scipy ---
    p_values = pd.DataFrame(np.ones((len(cols), len(cols))), index=cols, columns=cols)
    for i, c1 in enumerate(cols):
        for j, c2 in enumerate(cols):
            if i == j:
                p_values.loc[c1, c2] = 0.0
            elif i < j:
                s1 = df_resampled[c1].dropna()
                s2 = df_resampled[c2].dropna()
                common = s1.index.intersection(s2.index)
                if len(common) >= 3:
                    if method == 'spearman':
                        _, pv = scipy_stats.spearmanr(s1[common], s2[common])
                    else:
                        _, pv = scipy_stats.pearsonr(s1[common], s2[common])
                    p_values.loc[c1, c2] = float(pv)
                    p_values.loc[c2, c1] = float(pv)

    # --- Scatter Data (limita a 5000 pontos preservando a sequência temporal) ---
    limit = 5000
    if len(df_resampled) > limit:
        step = max(1, len(df_resampled) // limit)
        df_scatter = df_resampled.iloc[::step]
    else:
        df_scatter = df_resampled

    return jsonify({
        'correlation_matrix': {
            'columns': cols,
            'values': corr_matrix.values.tolist(),
            'p_values': p_values.values.tolist(),
            'method': method,
            'n_points': n,
            'resample_rule': resample_rule
        },
        'scatter_data': {
            'index': df_scatter.index.astype(str).tolist(),
            'data': {
                col: [None if (isinstance(v, float) and np.isnan(v)) else v for v in vals]
                for col, vals in df_scatter.to_dict(orient='list').items()
            }
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

    influx_client = current_app.extensions.get('influx_client')
    if not influx_client:
        return jsonify({'error': 'DB not connected'}), 500

    # Calcula intervalo ideal para o GROUP BY no InfluxDB.
    # Meta: máximo ~10000 pontos, resolução mínima de 5s.
    # O agrupamento acontece no banco — não no Python — para preservar oscilações reais.
    try:
        from datetime import datetime as _dt
        _start = _dt.fromisoformat(start_time.replace('Z', '+00:00'))
        _end   = _dt.fromisoformat(end_time.replace('Z', '+00:00'))
        total_seconds = abs((_end - _start).total_seconds())
    except Exception:
        total_seconds = 28800  # fallback 8h

    TARGET_MAX_POINTS = 10000
    MIN_INTERVAL_S    = 5
    ideal_s = max(MIN_INTERVAL_S, int(total_seconds / TARGET_MAX_POINTS))

    if   ideal_s <= 5:   influx_interval = '5s'
    elif ideal_s <= 10:  influx_interval = '10s'
    elif ideal_s <= 30:  influx_interval = '30s'
    elif ideal_s <= 60:  influx_interval = '1m'
    elif ideal_s <= 300: influx_interval = '5m'
    else:                influx_interval = '10m'

    df = query_influx_to_df(influx_client, variables, start_time, end_time, interval=influx_interval)

    if df.empty:
        return jsonify({'error': 'No data'}), 404

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
            'timestamps': series.index.strftime('%Y-%m-%dT%H:%M:%S').tolist(),
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
