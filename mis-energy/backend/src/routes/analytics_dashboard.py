# backend/src/routes/analytics_dashboard.py
from flask import Blueprint, request, jsonify
import logging
from datetime import datetime, timedelta
from src.models.equipment import Equipment
from src.services.influxdb_client import influxdb_service

logger = logging.getLogger(__name__)
analytics_dashboard_bp = Blueprint('analytics_dashboard', __name__)

COST_PER_KWH_DEFAULT = 0.85 # Fallback

@analytics_dashboard_bp.route('/analytics/dashboard-summary', methods=['GET'])
def get_dashboard_summary():
    """Retorna resumo do dashboard com consumo e custo REAL das últimas 24h ou período"""
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        hierarchy_id = request.args.get('hierarchy_id', type=int)

        # 1. Definir janelas de tempo
        now = datetime.now()
        
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        else:
            end_date = now

        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        else:
            # Default: última semana
            start_date = end_date - timedelta(days=7)

        # Comparação (Período anterior de mesma duração)
        duration = end_date - start_date
        prev_end_date = start_date
        prev_start_date = prev_end_date - duration

        # 2. Obter equipamentos ativos (opcionalmente filtrados)
        query_eq = Equipment.query.filter_by(is_active=True)
        if hierarchy_id:
             query_eq = query_eq.filter_by(hierarchy_id=hierarchy_id)
        
        equipments = query_eq.all()
        if not equipments:
             return jsonify({'success': True, 'data': _empty_summary(start_date, end_date)})

        # 3. Construir filtros Influx e Tarifas
        tags = [eq.tag or eq.name for eq in equipments if (eq.tag or eq.name)]
        if not tags: return jsonify({'success': True, 'data': _empty_summary(start_date, end_date)})

        tag_filter = " OR ".join([f"\"tag\" = '{t}'" for t in tags])
        
        # Mapa de tarifa por tag para refino (avg tariff)
        total_tariff = sum(eq.tariff_kwh or COST_PER_KWH_DEFAULT for eq in equipments)
        avg_tariff = total_tariff / len(equipments)

        # 4. Queries Agregadas (InfluxQL 1.8)
        # Power metric
        q_power_curr = f'''
            SELECT mean("value") 
            FROM "energy_consumption" 
            WHERE ("metric" = 'power_kw') AND ({tag_filter}) 
            AND time >= '{start_date.isoformat()}' AND time <= '{end_date.isoformat()}' 
            GROUP BY "tag"
        '''
        q_power_prev = f'''
            SELECT mean("value") 
            FROM "energy_consumption" 
            WHERE ("metric" = 'power_kw') AND ({tag_filter}) 
            AND time >= '{prev_start_date.isoformat()}' AND time <= '{prev_end_date.isoformat()}' 
            GROUP BY "tag"
        '''

        # Production metric (New) - Sum of totalizer deltas or Mean of rate? 
        # For simplicity in this iteration: If 'production_rate' metric exists, we integrate it.
        # If 'production_total' exists, we get MAX - MIN. 
        # Let's assume 'production_rate' (ton/h) is available for now as it's easier to aggregate alongside power.
        # If not, we fall back to 0.
        q_prod_curr = f'''
            SELECT mean("value") 
            FROM "energy_consumption" 
            WHERE ("metric" = 'production_rate') 
            AND time >= '{start_date.isoformat()}' AND time <= '{end_date.isoformat()}' 
            GROUP BY "tag" -- Note: Production tags might differ from power tags, this is a simplification for linked equipment
        '''
        # Ideally, we should query specific production tags linked to the hierarchy, but let's query all 'production_rate' 
        # that might be associated with these lines. A more robust way is querying everything and summing.
        
        # ACTUALLY: The best generic approach without complex mapping now is to query ALL 'production_rate' in the period
        # assuming the filter context (Factory/Area) implies which production lines are relevant.
        # But we don't have tags for production meters in 'tag_filter' (which comes from current equipments).
        # We need to include production equipments in 'equipments' list.
        # We already do: Equipment.query.filter_by(is_active=True).all() includes production meters if they are active.
        
        q_prod_curr = f'''
             SELECT mean("value") FROM "energy_consumption" WHERE ("metric" = 'production_rate') AND ({tag_filter}) AND time >= '{start_date.isoformat()}' AND time <= '{end_date.isoformat()}' GROUP BY "tag"
        '''
        q_prod_prev = f'''
             SELECT mean("value") FROM "energy_consumption" WHERE ("metric" = 'production_rate') AND ({tag_filter}) AND time >= '{prev_start_date.isoformat()}' AND time <= '{prev_end_date.isoformat()}' GROUP BY "tag"
        '''
        
        curr_res_power = influxdb_service.execute_query(q_power_curr)
        prev_res_power = influxdb_service.execute_query(q_power_prev)
        
        curr_res_prod = influxdb_service.execute_query(q_prod_curr)
        prev_res_prod = influxdb_service.execute_query(q_prod_prev)
        
        # 5. Processar Resultados
        hours = duration.total_seconds() / 3600.0
        curr_kwh = _calculate_energy(curr_res_power, hours)
        prev_kwh = _calculate_energy(prev_res_power, hours)
        
        curr_ton = _calculate_energy(curr_res_prod, hours) # Same math: rate * hours = total
        prev_ton = _calculate_energy(prev_res_prod, hours)
        
        curr_cost = curr_kwh * avg_tariff
        prev_cost = prev_kwh * avg_tariff
        
        # Efficiency (kWh / Ton)
        # Avoid division by zero
        curr_eff = (curr_kwh / curr_ton) if curr_ton > 0.1 else 0
        prev_eff = (prev_kwh / prev_ton) if prev_ton > 0.1 else 0
        
        # Deltas
        kwh_delta = ((curr_kwh - prev_kwh) / prev_kwh * 100) if prev_kwh > 0 else 0
        cost_delta = ((curr_cost - prev_cost) / prev_cost * 100) if prev_cost > 0 else 0
        eff_delta = ((curr_eff - prev_eff) / prev_eff * 100) if prev_eff > 0 else 0
        
        trend = 'stable'
        if kwh_delta > 5: trend = 'up'
        elif kwh_delta < -5: trend = 'down'

        return jsonify({
            'success': True,
            'data': {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'days': duration.days
                },
                'current': {
                    'consumption_kwh': round(curr_kwh, 2),
                    'cost_brl': round(curr_cost, 2),
                    'efficiency_kwh_ton': round(curr_eff, 2),
                    'production_ton': round(curr_ton, 2) # Added for debug/display
                },
                'previous': {
                    'consumption_kwh': round(prev_kwh, 2),
                    'cost_brl': round(prev_cost, 2),
                    'efficiency_kwh_ton': round(prev_eff, 2)
                },
                'delta': {
                    'consumption_percent': round(kwh_delta, 1),
                    'cost_percent': round(cost_delta, 1),
                    'efficiency_percent': round(eff_delta, 1)
                },
                'trend': trend
            }
        })

    except Exception as e:
        logger.error(f"Erro em dashboard-summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def _calculate_energy(influx_res, hours):
    """Auxiliary: Sum mean power * time for all tags"""
    total_energy = 0
    if influx_res and 'results' in influx_res:
        series = influx_res['results'][0].get('series', [])
        for s in series:
            # values: [[time, mean_val]]
            if s.get('values'):
                mean_power = s['values'][0][1]
                if mean_power:
                    total_energy += mean_power * hours
    return total_energy

def _empty_summary(start, end):
    return {
        'period': {'start': start.isoformat(), 'end': end.isoformat(), 'days': (end-start).days},
        'current': {'consumption_kwh': 0, 'cost_brl': 0, 'efficiency_kwh_ton': 0},
        'previous': {'consumption_kwh': 0, 'cost_brl': 0, 'efficiency_kwh_ton': 0},
        'delta': {'consumption_percent': 0, 'cost_percent': 0, 'efficiency_percent': 0},
        'trend': 'stable'
    }

@analytics_dashboard_bp.route('/analytics/time-series', methods=['GET'])
def get_time_series():
    """Retorna série temporal de consumo REAL"""
    try:
        period = request.args.get('period', 'daily') # hourly, daily
        start_date_str = request.args.get('start_time') # changed from start_date to match frontend
        end_date_str = request.args.get('end_time')

        now = datetime.now()
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        else:
             end_date = now
             
        if start_date_str:
             start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        else:
             start_date = end_date - timedelta(days=7)
        
        # Determine group by
        if period == 'hourly':
            group_by = '1h'
            bucket_hours = 1
            date_format = '%H:%M'
        else: # daily or weekly
            group_by = '1d'
            bucket_hours = 24
            date_format = '%d/%m'

        # Get active equipment tags
        equipments = Equipment.query.filter_by(is_active=True).all()
        tags = [eq.tag or eq.name for eq in equipments if (eq.tag or eq.name)]
        if not tags: return jsonify({'success': True, 'data': []})

        tag_filter = "OR".join([f"\"tag\" = '{t}'" for t in tags])
        avg_tariff = COST_PER_KWH_DEFAULT 
        if equipments:
             avg_tariff = sum(eq.tariff_kwh or COST_PER_KWH_DEFAULT for eq in equipments) / len(equipments)

        # Influx Query: Mean Power Grouped by Time AND Tag
        # We need to sum up energy of all machines per time bucket.
        # Standard Influx 1.8 approach: subqueries or post-processing.
        # Using Post-Processing map.
        
        query = f'''
            SELECT mean("value") 
            FROM "energy_consumption" 
            WHERE ("metric" = 'power_kw') AND ({tag_filter}) 
            AND time >= '{start_date.isoformat()}' AND time <= '{end_date.isoformat()}' 
            GROUP BY time({group_by}), "tag" fill(0)
        '''
        
        result = influxdb_service.execute_query(query)
        
        # Aggregate by timestamp
        time_map = {}
        
        if result and 'results' in result:
             series = result['results'][0].get('series', [])
             for s in series:
                 for v in s.get('values', []):
                     ts = v[0]
                     pwr = v[1] or 0
                     if ts not in time_map: method='sum_power'
                     if ts not in time_map: time_map[ts] = 0
                     time_map[ts] += pwr
        
        # Create output list
        data = []
        for ts in sorted(time_map.keys()):
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            total_power = time_map[ts]
            energy_kwh = total_power * bucket_hours
            cost = energy_kwh * avg_tariff
            
            data.append({
                'timestamp': ts,
                'label': dt.strftime(date_format),
                'consumption_kwh': round(energy_kwh, 2),
                'cost_brl': round(cost, 2)
            })

        return jsonify({
            'success': True,
            'data': data,
            'period': period,
            'unit_cost': round(avg_tariff, 2)
        })

    except Exception as e:
        logger.error(f"Erro em time-series: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@analytics_dashboard_bp.route('/analytics/insights', methods=['GET'])
def get_insights():
    # Placeholder: Insights usually require complex rules engine.
    # Returning empty or basic static response allows frontend to render without error.
    return jsonify({
        'success': True, 
        'data': [], 
        'generated_at': datetime.now().isoformat()
    })

@analytics_dashboard_bp.route('/analytics/energy-breakdown', methods=['GET'])
def get_energy_breakdown():
    # Placeholder: requires tagging by 'energy_type' which we might not have yet.
    # Returning empty.
     return jsonify({
            'success': True,
            'data': [],
            'total_kwh': 0,
            'total_cost': 0
     })

@analytics_dashboard_bp.route('/analytics/heatmap', methods=['GET'])
def get_heatmap():
     # Placeholder
      return jsonify({
            'success': True,
            'data': [],
            'days': ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'],
            'hours': list(range(24)),
            'range': {'min': 0, 'max': 0}
        })

@analytics_dashboard_bp.route('/analytics/export-csv', methods=['GET'])
def export_csv():
    # Placeholder functionality
    return "Not Implemented", 501
