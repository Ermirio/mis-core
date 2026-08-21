"""
Flask-out Onda 6: portado de backend-flask/blueprints/analytics.py para
Django. Mesma lógica (pandas/scipy + OFF-mask + delta reset-tolerante
+ Cp/Cpk + Shewhart). Adaptações:
  - imports Flask -> Django REST Framework
  - current_app.extensions.get('influx_client') -> _influx_client()
  - http_requests para equipamentos -> ORM Django
"""
import pandas as pd
import numpy as np
from scipy import stats as scipy_stats
from datetime import datetime, timedelta
import pytz
import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .flask_replacement_views import _influx_client
from .models import Equipamento

logger = logging.getLogger(__name__)

# ==============================================================================
# [P0.3] OFF-MASK — Estados de equipamento que NÃO devem entrar em EDA/analytics
# ------------------------------------------------------------------------------
# Motivação: quando o equipamento está PARADO, em MANUTENÇÃO, TESTE, etc., as
# variáveis (velocidade, temperatura, pressão, contadores) ficam "congeladas" ou
# lendo valores espúrios do CLP. Se essas leituras entram no cálculo de média,
# desvio padrão, Cp/Cpk ou correlação, elas viram RUÍDO SISTEMÁTICO — o cientista
# de dados vê "a linha está estável" quando na verdade a linha está desligada.
#
# Regra (ISO 22400-2 + senso comum de WCM):
#   Para análise estatística/EDA, considerar apenas leituras capturadas enquanto
#   o equipamento está em estado PRODUTIVO (ou próximo disso).
#
# Códigos ESTADOS_MAQUINA (backend-flask/constants.py):
#   0   Online (idle, sem produzir)    1  Produzindo
#   2   Aguard. Anterior                3  Bloq. Próximo
#   4   Parado/Falha                    5  Setup
#   6   Teste/Projeto                   7  Aguard. Manut.
#   8   Manutenção                      9  Falta Material
#   11  Partindo                        12 Aguard. Condições
#   13  Parando                         999 OFFLINE (forçado pelo coletor)
#
# [BUG-4 fix] adicionados 0 e 999 ao default. Sem isso, períodos em que o PLC
# estava offline (estado=999) ou a máquina estava em idle (estado=0) entravam
# nas estatísticas com velocidade=0 → médias e desvios viesados pra baixo, e
# correlações espúrias perto de 1.0 entre variáveis "congeladas".
# Default razoável: excluir estados claramente "não-produtivos":
#   {0 idle, 4 Parado/Falha, 6 Teste, 7 Aguard. Manut., 8 Manutenção, 999 OFFLINE}
# ==============================================================================
DEFAULT_EXCLUDE_STATES = [0, 4, 6, 7, 8, 999]


# ==============================================================================
# CUMULATIVE_FIELDS — campos sabidamente cumulativos no schema "production".
#
# Usado pelo /analyze/timeseries para decidir quando converter série em DELTA
# por janela. ANTES, usávamos heurística `series.is_monotonic_increasing`,
# que falhava em casos comuns:
#   - reset de turno no meio da janela (série não-monotônica)
#   - oscilação minúscula de leitura ruidosa quebra a monotonicidade
#   - resultado: o usuário via curva sempre crescente porque o auto-delta
#     não disparava e o gráfico mostrava o contador acumulado puro.
#
# Agora é determinístico: se o `tag_influx` da variável estiver neste set
# E `apply_delta=True` (default), aplica delta reset-tolerante. Senão,
# devolve raw. Sem ambiguidade.
# ==============================================================================
CUMULATIVE_FIELDS = {
    'contagem_saida',
    'contagem_entrada',
    'descarte',
    'refugo_op_acumulado',
    'producao_op_acumulada',
    'producao_turno_acumulada',
}


def _influx_tag_value(value) -> str:
    """Escape one Influx tag value before interpolating an InfluxQL filter."""
    return str(value or '').replace('\\', '\\\\').replace("'", "\\'")


def _equipment_identity_where(eq_code: str, line_code: str = '', equipment_slug: str = '') -> str:
    """Build an Influx filter for one equipment without crossing line scope."""
    safe_eq_code = _influx_tag_value(eq_code)
    safe_line_code = _influx_tag_value(line_code)
    if not safe_eq_code or not safe_line_code:
        raise ValueError("Analytics exige equipamento_code e linha_codigo para consultar o Influx.")
    return f"\"equipment\" = '{safe_eq_code}' AND \"line\" = '{safe_line_code}'"


def _tag_equipment_identity_where(tag_info) -> str:
    return _equipment_identity_where(
        tag_info.get('equipamento_code', ''),
        tag_info.get('linha_codigo', ''),
        tag_info.get('equipamento_slug', ''),
    )


def _fetch_state_series(client, eq_code: str, start_time: str, end_time: str,
                        equipment_where: str = '') -> pd.Series:
    """
    Busca a série temporal de `estado_maquina` para um equipamento.
    Retorna pd.Series indexada por timestamp (tz America/Sao_Paulo).
    """
    try:
        where_clause = equipment_where or _equipment_identity_where(eq_code)
        q = (
            f"SELECT \"estado_maquina\" FROM \"production\" "
            f"WHERE {where_clause} "
            f"AND time >= '{start_time}' AND time <= '{end_time}'"
        )
        rs = client.query(q)
        points = list(rs.get_points())
        if not points:
            return pd.Series(dtype='float64')
        df_s = pd.DataFrame(points)
        df_s['time'] = pd.to_datetime(df_s['time'], utc=True).dt.tz_convert('America/Sao_Paulo')
        df_s.set_index('time', inplace=True)
        return pd.to_numeric(df_s['estado_maquina'], errors='coerce')
    except Exception as e:
        logger.warning(f"[off-mask] Não foi possível buscar estado_maquina para {eq_code}: {e}")
        return pd.Series(dtype='float64')


def _apply_off_mask(obj, state_series: pd.Series, exclude_states):
    """
    Marca como NaN as linhas em que o estado do equipamento está em `exclude_states`.
    Funciona para pd.Series e pd.DataFrame.

    O estado é propagado com forward-fill para cobrir timestamps entre transições.
    """
    if exclude_states is None or len(exclude_states) == 0:
        return obj
    if state_series is None or state_series.empty:
        return obj
    if obj is None or (hasattr(obj, 'empty') and obj.empty):
        return obj

    target_idx = obj.index
    # Alinha estado com os timestamps alvo via ffill — cobre buracos entre transições
    combined_idx = state_series.index.union(target_idx).sort_values()
    state_aligned = (
        state_series.reindex(combined_idx)
                    .sort_index()
                    .ffill()
                    .reindex(target_idx)
    )
    off_mask = state_aligned.isin(exclude_states).fillna(False)

    if not off_mask.any():
        return obj

    obj_masked = obj.copy()
    if isinstance(obj_masked, pd.DataFrame):
        obj_masked.loc[off_mask, :] = np.nan
    else:
        obj_masked[off_mask] = np.nan
    return obj_masked


def _parse_exclude_states(payload_value):
    """
    Normaliza o campo `exclude_states` do payload.
    Aceita:
      - None / ausente     -> usa DEFAULT_EXCLUDE_STATES
      - []                 -> sem filtro (explicitamente desligado)
      - [4, 8]             -> lista de códigos
      - ['PARADO', ...]    -> ignora strings (o frontend pode vir a mandar)
    """
    if payload_value is None:
        return DEFAULT_EXCLUDE_STATES
    if not isinstance(payload_value, list):
        return DEFAULT_EXCLUDE_STATES
    try:
        return [int(x) for x in payload_value if str(x).strip().lstrip('-').isdigit()]
    except Exception:
        return DEFAULT_EXCLUDE_STATES


def query_influx_to_df(client, tags, start_time, end_time, interval=None,
                       exclude_states=None, apply_delta=True):
    """
    Queries InfluxDB for multiple tags and returns a single aligned DataFrame.

    interval: se fornecido (ex: '5s', '1m'), usa GROUP BY time(interval) LAST()
              diretamente no InfluxDB — preserva oscilações reais dos sensores.
              Se None, retorna dados raw sem agregação (para stats/correlação).

    apply_delta (GAP-1): controla se contadores acumulativos (CONSOLIDATED_METRICS
              com agg='last_diff') são convertidos em delta por janela. Default
              True (comportamento correto). Quando False, retorna a série bruta
              acumulada — útil para diagnóstico raro do contador puro.
    """
    try:
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
                # Get all equipment codes for this line (ORM, sem HTTP round-trip)
                try:
                    equipment_list = list(
                        Equipamento.objects.select_related('linha').filter(linha__codigo=eq_code)
                    )
                    equipment_codes = [e.codigo for e in equipment_list if e.codigo]
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
                
                for eq in equipment_list:
                    equipment_where = _equipment_identity_where(
                        eq.codigo,
                        eq.linha.codigo if eq.linha else '',
                        eq.slug,
                    )
                    query = f"SELECT \"{influx_field}\" FROM \"production\" WHERE {equipment_where} AND time >= '{start_time}' AND time <= '{end_time}'"
                    rs = client.query(query)
                    points = list(rs.get_points())

                    if points:
                        df_eq = pd.DataFrame(points)
                        df_eq['time'] = pd.to_datetime(df_eq['time'], utc=True).dt.tz_convert('America/Sao_Paulo')
                        df_eq.set_index('time', inplace=True)
                        df_eq[influx_field] = pd.to_numeric(df_eq[influx_field], errors='coerce')

                        # [P0.3] OFF-mask por equipamento ANTES de agregar a linha.
                        # Para contadores acumulativos (last_diff) o NaN é tolerado pelo
                        # _window_delta (que usa diff().clip). Para mean/sum, NaN é
                        # ignorado pelo resample (pandas skipna=True).
                        if exclude_states:
                            state_s = _fetch_state_series(
                                client, eq.codigo, start_time, end_time, equipment_where
                            )
                            df_eq[[influx_field]] = _apply_off_mask(
                                df_eq[[influx_field]], state_s, exclude_states
                            )

                        df_eq['equipment'] = eq.slug or f"{eq.linha.codigo}.{eq.codigo}"
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
                        # [P0.1 FIX] Contadores acumulativos precisam de DELTA por janela,
                        # não o último valor. A implementação anterior (groupby→last→sum)
                        # produzia séries MONOTONICAMENTE CRESCENTES porque somava valores
                        # cumulativos. Fix: (max - min) por equipamento+janela → delta real
                        # da janela; depois soma entre equipamentos.
                        # Compatível com reset do contador: usa diff().clip(lower=0).sum()
                        # que ignora quedas (reset do PLC/início de turno).
                        # [GAP-1] apply_delta=False bypassa a transformação e devolve a
                        # série bruta (último valor por janela) — caso de uso raro de debug.
                        if apply_delta:
                            def _window_delta(s: pd.Series) -> float:
                                if len(s) < 2:
                                    return 0.0
                                d = s.sort_index().diff().clip(lower=0).sum()
                                return float(d)
                            agg_series = (
                                combined.groupby('equipment')[influx_field]
                                .resample('1min')
                                .apply(_window_delta)
                                .groupby(level=1)
                                .sum()
                            )
                        else:
                            agg_series = (
                                combined.groupby('equipment')[influx_field]
                                .resample('1min')
                                .last()
                                .groupby(level=1)
                                .sum()
                            )
                    else:
                        agg_series = combined[influx_field].resample('1min').mean()
                    
                    # Convert to tons if needed
                    if metric_config.get('convert_tons'):
                        # Get format from first equipment (simplification)
                        try:
                            first_eq = equipment_list[0]
                            first_eq_where = _equipment_identity_where(
                                first_eq.codigo,
                                first_eq.linha.codigo if first_eq.linha else '',
                                first_eq.slug,
                            )
                            fmt_query = f"SELECT last(\"formato_gramas\") FROM \"production\" WHERE {first_eq_where}"
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
                    # 1. Busca configs de equipamento (ORM) — agora inclui slug
                    eq_list = list(
                        Equipamento.objects.filter(linha__codigo=eq_code)
                        .values('codigo', 'slug', 'tipo', 'ordem_na_linha')
                    )

                    # 2. Identifica Weighing Equipment (Enchedora > Balança > Ordem 1)
                    weighing_eq = next((e for e in eq_list if e.get('tipo') == 'ENCHEDORA'), None)
                    if not weighing_eq:
                        weighing_eq = next((e for e in eq_list if e.get('tipo') == 'BALANCA'), None)
                    if not weighing_eq:
                        weighing_eq = next((e for e in eq_list if e.get('ordem_na_linha') == 1), None)

                    if weighing_eq:
                        # 3. Query: prefere slug (sem ambiguidade); fallback line+equipment.
                        slug = weighing_eq.get('slug')
                        codigo = weighing_eq.get('codigo')
                        if slug:
                            _where_eq = (
                                f"(\"equipment_slug\" = '{slug}' "
                                f"OR (\"equipment\" = '{codigo}' AND \"line\" = '{eq_code}'))"
                            )
                        else:
                            _where_eq = f"\"equipment\" = '{codigo}' AND \"line\" = '{eq_code}'"
                        q_ga = f"""
                            SELECT
                                MEAN("ultimo_peso") as peso_medio,
                                LAST("formato_gramas") as peso_alvo,
                                NON_NEGATIVE_DIFFERENCE(LAST("contagem_saida")) as producao
                            FROM "production"
                            WHERE {_where_eq}
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
                equipment_where = _tag_equipment_identity_where(tag_info)
                if interval:
                    # GROUP BY no InfluxDB: preserva resolução real dos dados
                    query = f"SELECT LAST(\"{field}\") AS \"{field}\" FROM \"production\" WHERE {equipment_where} AND time >= '{start_time}' AND time <= '{end_time}' GROUP BY time({interval}) fill(none)"
                else:
                    query = f"SELECT \"{field}\" FROM \"production\" WHERE {equipment_where} AND time >= '{start_time}' AND time <= '{end_time}'"
                
                rs = client.query(query)
                points = list(rs.get_points())

                if points:
                    df = pd.DataFrame(points)
                    df['time'] = pd.to_datetime(df['time'], utc=True).dt.tz_convert('America/Sao_Paulo')
                    df.set_index('time', inplace=True)
                    df.rename(columns={field: alias}, inplace=True)
                    df[alias] = pd.to_numeric(df[alias], errors='coerce')

                    # [P0.3] OFF-mask — só aplica quando o campo NÃO é o próprio estado
                    # (do contrário mascararíamos a variável que define a máscara).
                    if exclude_states and field != 'estado_maquina':
                        state_s = _fetch_state_series(
                            client, eq_code, start_time, end_time, equipment_where
                        )
                        df = _apply_off_mask(df, state_s, exclude_states)

                    dfs.append(df)
        
        if not dfs:
            return pd.DataFrame()

        full_df = pd.concat(dfs, axis=1).sort_index()
        return full_df

    except Exception as e:
        logger.error(f"Error querying influx: {e}")
        return pd.DataFrame()


@api_view(['POST'])
def analyze_stats(request):
    """POST /api/analyze/stats — Descriptive Statistics + Cp/Cpk."""
    data = request.data or {}
    variables = data.get('variables', [])
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    if data.get('ignore_off') is False:
        exclude_states = []
    else:
        exclude_states = _parse_exclude_states(data.get('exclude_states'))
    apply_delta = bool(data.get('apply_delta', True))

    influx_client = _influx_client()
    if not influx_client:
        return Response({'error': 'DB not connected'}, status=500)

    results = []

    # Optimize: Query all at once? Or loop?
    # Stats are usually per-variable.

    for var in variables:
        df = query_influx_to_df(
            influx_client, [var], start_time, end_time,
            exclude_states=exclude_states,
            apply_delta=apply_delta,
        )
        
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

        # Delta DETERMINÍSTICO via catálogo (mesma lógica do analyze_timeseries).
        # Substitui heurística is_monotonic_increasing que falhava em resets.
        tag_influx_stats = var.get('tag_influx', '')
        if apply_delta and tag_influx_stats in CUMULATIVE_FIELDS and len(series) > 1:
            series = series.diff().clip(lower=0).dropna()
            if series.empty:
                results.append({'variable': col_name, 'error': 'Empty data after delta'})
                continue

        # Stats
        mean = float(series.mean())
        std = float(series.std())
        min_val = float(series.min())
        max_val = float(series.max())
        median = float(series.median())
        count = int(series.count())
        
        n_unique = int(series.nunique())
        # Heurística: se tem poucos valores únicos (<= 15) em relação ao total, consideramos discreta
        is_discrete = bool(n_unique <= 15 or n_unique < (count * 0.05))
        
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
        if is_discrete:
            # Para variáveis discretas, contamos as ocorrências de cada valor
            val_counts = series.value_counts().sort_index()
            histogram_data = {
                'counts': val_counts.tolist(),
                'bins': val_counts.index.tolist()
            }
        else:
            hist, bin_edges = np.histogram(series, bins='auto')
            histogram_data = {
                'counts': hist.tolist(),
                'bins': bin_edges.tolist()
            }
        
        results.append({
            'variable': col_name,
            'n_unique': n_unique,
            'is_discrete': is_discrete,
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
            'histogram': histogram_data,
            'raw_data_head': series.head(100).tolist() # Optional preview
        })

    return Response(results)


@api_view(['POST'])
def analyze_correlation(request):
    """POST /api/analyze/correlation — Correlation matrix + p-values + scatter."""
    data = request.data or {}
    variables = data.get('variables', [])
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    # [P0.3] OFF-mask — correlação é especialmente sensível a ruído de estados
    # parados (gera correlações espúrias perto de 1.0 entre variáveis congeladas).
    # [GAP-1] mesmas flags do /analyze/stats.
    if data.get('ignore_off') is False:
        exclude_states = []
    else:
        exclude_states = _parse_exclude_states(data.get('exclude_states'))
    apply_delta = bool(data.get('apply_delta', True))

    # Validate correlation method — never trust user input directly
    method = data.get('method', 'pearson')
    if method not in ('pearson', 'spearman'):
        method = 'pearson'

    influx_client = _influx_client()
    if not influx_client:
        return Response({'error': 'DB not connected'}, status=500)

    df = query_influx_to_df(
        influx_client, variables, start_time, end_time,
        exclude_states=exclude_states,
        apply_delta=apply_delta,
    )

    if df.empty:
        return Response({'error': 'No data'}, status=404)

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
        return Response({'error': 'Insufficient overlap data'}, status=400)

    # Remove colunas sem nenhum dado (variáveis deselectionadas ou sem dados no período)
    df_resampled = df_resampled.dropna(axis=1, how='all')

    if df_resampled.shape[1] < 2:
        return Response({'error': 'Insufficient variables with data'}, status=400)

    # --- Correlation Matrix (pairwise — cada par usa apenas as linhas onde ambos têm dados) ---
    corr_matrix = df_resampled.corr(method=method, min_periods=3).fillna(0)
    # Garante que inf também seja eliminado (fillna só cobre NaN)
    corr_matrix = corr_matrix.replace([float('inf'), float('-inf')], 0.0)
    cols = corr_matrix.columns.tolist()
    n = len(df_resampled)

    # --- P-values matrix via scipy ---
    # BUG-FIX: scipy.pearsonr/spearmanr retorna NaN quando uma das séries é constante
    # (ConstantInputWarning). float('nan') não é JSON-serializável → 500.
    # Fallback seguro: p=1.0 (sem significância estatística) para pares indefinidos.
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
                    try:
                        if method == 'spearman':
                            _, pv = scipy_stats.spearmanr(s1[common], s2[common])
                        else:
                            _, pv = scipy_stats.pearsonr(s1[common], s2[common])
                        pv_safe = float(pv) if (pv is not None and np.isfinite(pv)) else 1.0
                    except Exception:
                        pv_safe = 1.0
                    p_values.loc[c1, c2] = pv_safe
                    p_values.loc[c2, c1] = pv_safe

    # --- Scatter Data (limita a 5000 pontos preservando a sequência temporal) ---
    limit = 5000
    if len(df_resampled) > limit:
        step = max(1, len(df_resampled) // limit)
        df_scatter = df_resampled.iloc[::step]
    else:
        df_scatter = df_resampled

    def _sanitize_matrix(mat):
        """Converte NaN/inf para None — JSON-safe para o frontend tratar como N/A."""
        return [
            [None if (v is None or not np.isfinite(v)) else v for v in row]
            for row in mat
        ]

    return Response({
        'correlation_matrix': {
            'columns': cols,
            'values': _sanitize_matrix(corr_matrix.values.tolist()),
            'p_values': _sanitize_matrix(p_values.values.tolist()),
            'method': method,
            'n_points': n,
            'resample_rule': resample_rule
        },
        'scatter_data': {
            'index': df_scatter.index.astype(str).tolist(),
            'data': {
                col: [None if (v is None or (isinstance(v, float) and not np.isfinite(v))) else v
                      for v in vals]
                for col, vals in df_scatter.to_dict(orient='list').items()
            }
        }
    })

@api_view(['POST'])
def analyze_timeseries(request):
    """POST /api/analyze/timeseries — Trend + SPC com UCL/LCL Shewhart."""
    data = request.data or {}
    variables = data.get('variables', [])
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    if data.get('ignore_off') is False:
        exclude_states = []
    else:
        exclude_states = _parse_exclude_states(data.get('exclude_states'))
    apply_delta = bool(data.get('apply_delta', True))
    user_gran = (data.get('granularity') or 'auto').lower()

    influx_client = _influx_client()
    if not influx_client:
        return Response({'error': 'DB not connected'}, status=500)

    # Calcula intervalo ideal para o GROUP BY no InfluxDB quando granularity=auto.
    # Meta: máximo ~10000 pontos, resolução mínima de 5s.
    # O agrupamento acontece no banco — não no Python — para preservar oscilações reais.
    try:
        from datetime import datetime as _dt
        _start = _dt.fromisoformat(start_time.replace('Z', '+00:00'))
        _end   = _dt.fromisoformat(end_time.replace('Z', '+00:00'))
        total_seconds = abs((_end - _start).total_seconds())
    except Exception:
        total_seconds = 28800  # fallback 8h

    if user_gran in ('5s', '10s', '30s', '1m', '5m', '10m', '15m', '30m', '1h', '1d'):
        influx_interval = user_gran
    else:
        # Auto-cálculo (mantido)
        TARGET_MAX_POINTS = 10000
        MIN_INTERVAL_S    = 5
        ideal_s = max(MIN_INTERVAL_S, int(total_seconds / TARGET_MAX_POINTS))
        if   ideal_s <= 5:   influx_interval = '5s'
        elif ideal_s <= 10:  influx_interval = '10s'
        elif ideal_s <= 30:  influx_interval = '30s'
        elif ideal_s <= 60:  influx_interval = '1m'
        elif ideal_s <= 300: influx_interval = '5m'
        else:                influx_interval = '10m'

    df = query_influx_to_df(
        influx_client, variables, start_time, end_time,
        interval=influx_interval,
        exclude_states=exclude_states,
        apply_delta=apply_delta,
    )

    if df.empty:
        return Response({'error': 'No data'}, status=404)

    # Mapa alias -> tag_influx para decidir delta DETERMINISTICAMENTE
    # (sem heurística is_monotonic_increasing que falha em resets de turno).
    alias_to_tag = {
        v.get('alias', v.get('tag_influx')): v.get('tag_influx')
        for v in variables
    }

    results = {}

    for col in df.columns:
        # [FIX trend/SPC] sort_index() defensivo. Garante DatetimeIndex crescente
        # antes do plot — Plotly não reordena por X mesmo com type:'date'.
        series = df[col].dropna().sort_index()
        if series.empty:
            continue

        # Delta DETERMINÍSTICO baseado em catálogo. Substitui a heurística antiga
        # (`series.is_monotonic_increasing`) que falhava em dois casos:
        #   1) reset de turno no meio da janela → série não-monotônica → auto-delta
        #      não disparava → user via série acumulada cumulativa "sempre subindo".
        #   2) oscilação ruidosa de 1-2 unidades em contador "calmo" também quebra.
        # Solução: se o tag_influx está em CUMULATIVE_FIELDS, aplica delta reset-tolerante.
        tag_influx = alias_to_tag.get(col, '')
        is_cumulative = tag_influx in CUMULATIVE_FIELDS
        if apply_delta and is_cumulative and len(series) > 1:
            # diff().clip(lower=0) ignora quedas (reset do PLC ou virada de turno).
            # Equivale ao counter_delta do FastAPI (formulas.py).
            series = series.diff().clip(lower=0).dropna()
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
        
    return Response(results)
