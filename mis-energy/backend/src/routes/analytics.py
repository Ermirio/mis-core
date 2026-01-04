from flask import Blueprint, request, jsonify
import logging
from datetime import datetime, timedelta
from src.models.user import db
from src.models.equipment import Equipment
from src.services.influxdb_client import influxdb_service

logger = logging.getLogger(__name__)
analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/analytics/overview', methods=['GET'])
def get_factory_overview():
    """Obtém visão geral da fábrica (ISA 101)"""
    try:
        hierarchy_id = request.args.get('hierarchy_id', type=int)
        
        # Obter todos equipamentos ativos
        query = Equipment.query.filter_by(is_active=True)
        if hierarchy_id:
            query = query.filter_by(hierarchy_id=hierarchy_id)
        
        equipments = query.all()
        total_equipments = len(equipments)
        
        # Buscar última leitura REAL do Influx para cada equipamento
        # Query otimizada: buscar LAST de power_kw para todos os tags
        if not equipments:
             return jsonify({
                'success': True,
                'data': {
                    'total_power_kw': 0,
                    'total_energy_kwh': 0,
                    'efficiency': 100,
                    'active_alarms': 0,
                    'total_equipments': 0,
                    'status': 'normal'
                }
            })

        # Construir filtro de tags
        tags = [eq.tag or eq.name for eq in equipments if (eq.tag or eq.name)]
        if not tags:
             # Fallback se não tiver tags
             return jsonify({
                'success': True,
                'data': {'total_power_kw': 0, 'status': 'normal'}
             })

        tag_filter = "OR".join([f"\"tag\" = '{t}'" for t in tags])
        influx_query = f'''
            SELECT last("value") 
            FROM "energy_consumption" 
            WHERE ("metric" = 'power_kw') AND ({tag_filter}) 
            AND time > now() - 2h 
            GROUP BY "tag"
        '''
        
        result = influxdb_service.execute_query(influx_query)
        
        total_power_kw = 0
        active_cnt = 0
        
        # Mapear resultados
        # Result structure: {'results': [{'series': [{'tags': {'tag': 'X'}, 'values': [[time, val]]}]}]}
        if result and 'results' in result:
            series = result['results'][0].get('series', [])
            for s in series:
                val = s['values'][0][1]
                if val:
                    total_power_kw += val
                    active_cnt += 1
        
        # Alarms = Total - Active (roughly, or logic based on timestamp age)
        # Mais preciso: Equipamentos que deveriam ter dado e não retornaram no query (pois filtramos time > 2h)
        active_alarms = total_equipments - active_cnt
        if active_alarms < 0: active_alarms = 0

        # Efficiency calculation (Simple placeholder logic)
        efficiency = 100.0
        if total_equipments > 0:
            efficiency = 100.0 - ((active_alarms / total_equipments) * 20)
            efficiency = max(0, min(100, efficiency))

        return jsonify({
            'success': True,
            'data': {
                'total_power_kw': round(total_power_kw, 2),
                'total_energy_kwh': 0, # TODO: Implementar integral se precisar
                'efficiency': round(efficiency, 1),
                'active_alarms': active_alarms,
                'total_equipments': total_equipments,
                'status': 'normal' if active_alarms == 0 else 'warning'
            }
        })

    except Exception as e:
        logger.error(f"Erro ao obter overview: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@analytics_bp.route('/analytics/consumption-chart', methods=['GET'])
def get_consumption_chart():
    """Obtém dados reais agregados para gráfico de consumo"""
    try:
        hours = int(request.args.get('hours', 24))
        hierarchy_id = request.args.get('hierarchy_id', type=int)

        # Filtro de Equipamentos
        query = Equipment.query.filter_by(is_active=True)
        if hierarchy_id:
             query = query.filter_by(hierarchy_id=hierarchy_id)
        equipments = query.all()
        
        tags = [eq.tag or eq.name for eq in equipments if (eq.tag or eq.name)]
        if not tags:
            return jsonify({'success': True, 'data': [], 'simulated': False})

        tag_filter = "OR".join([f"\"tag\" = '{t}'" for t in tags])

        # Query Agregada: Soma das médias por hora de todos os equipamentos
        # InfluxQL não faz JOIN, então agrupamos por tempo e somamos no Python ou usamos subqueries complexas
        # Melhor abordagem simples: MEAN por TAG e TEMPO, depois somar no Python
        
        influx_query = f'''
            SELECT mean("value") 
            FROM "energy_consumption" 
            WHERE ("metric" = 'power_kw') AND ({tag_filter}) 
            AND time > now() - {hours}h 
            GROUP BY time(1h), "tag" fill(0)
        '''
        
        data = influxdb_service.execute_query(influx_query)
        
        chart_data_map = {} # timestamp -> total_value
        
        if data and 'results' in data:
            series = data['results'][0].get('series', [])
            for s in series:
                values = s.get('values', [])
                for v in values:
                    ts = v[0]
                    val = v[1] if v[1] is not None else 0
                    
                    if ts not in chart_data_map:
                        chart_data_map[ts] = 0
                    chart_data_map[ts] += val
        
        # Formatar para frontend
        final_chart_data = []
        for ts in sorted(chart_data_map.keys()):
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            # Converter Potência Média (kW) em Energia (kWh) -> Multiplicar por 1h
            energy_kwh = chart_data_map[ts] * 1 
            
            final_chart_data.append({
                'time': dt.strftime('%H:%M'),
                'consumption': round(energy_kwh, 2),
                'timestamp': ts
            })

        return jsonify({
            'success': True,
            'data': final_chart_data,
            'simulated': False
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter dados do gráfico: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@analytics_bp.route('/analytics/equipment-summary', methods=['GET'])
def get_equipment_summary():
    """Obtém resumo dos equipamentos com dados reais"""
    try:
        equipments = Equipment.query.filter_by(is_active=True).all()
        
        # Buscar dados em batch para evitar N+1 queries
        tags = [eq.tag or eq.name for eq in equipments if (eq.tag or eq.name)]
        tag_map = {eq.tag or eq.name: eq for eq in equipments}
        
        equip_data_map = {} # tag -> {val, time}

        if tags:
            tag_filter = "OR".join([f"\"tag\" = '{t}'" for t in tags])
            query = f'''
                SELECT last("value") 
                FROM "energy_consumption" 
                WHERE ("metric" = 'power_kw') AND ({tag_filter}) 
                AND time > now() - 24h 
                GROUP BY "tag"
            '''
            result = influxdb_service.execute_query(query)
            
            if result and 'results' in result:
                series = result['results'][0].get('series', [])
                for s in series:
                    tag_name = s['tags']['tag']
                    if s['values']:
                        val = s['values'][0][1]
                        ts_str = s['values'][0][0]
                        equip_data_map[tag_name] = {'value': val, 'time': ts_str}

        # Montar resposta
        equipment_response = []
        for eq in equipments:
            tag = eq.tag or eq.name
            data = equip_data_map.get(tag)
            
            status = 'alert'
            consumption = None
            last_reading = None
            
            if data:
                consumption = round(data['value'], 2)
                last_reading = data['time']
                
                # Check stale data > 2h
                last_dt = datetime.fromisoformat(last_reading.replace('Z', '+00:00'))
                if (datetime.now(last_dt.tzinfo) - last_dt) < timedelta(hours=2):
                    status = 'normal'
            
            equipment_response.append({
                'id': eq.id,
                'name': eq.name,
                'location': eq.location or 'N/A',
                'area': eq.area or 'N/A',
                'consumption': consumption, # kW instantâneo (last)
                'unit': 'kW', # Last value is Power
                'status': status,
                'last_reading': last_reading
            })
        
        return jsonify({
            'success': True,
            'data': equipment_response,
            'simulated': False
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter resumo dos equipamentos: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@analytics_bp.route('/analytics/equipment/<int:equipment_id>/history', methods=['GET'])
def get_equipment_history(equipment_id):
    """Obtém histórico real de um equipamento"""
    try:
        hours = int(request.args.get('hours', 24))
        equipment = Equipment.query.get_or_404(equipment_id)
        tag = equipment.tag or equipment.name
        
        query = f'''
            SELECT mean("value") as value 
            FROM "energy_consumption" 
            WHERE "tag" = '{tag}' AND "metric" = 'power_kw'
            AND time > now() - {hours}h
            GROUP BY time(1h) fill(none)
        '''
        
        result = influxdb_service.execute_query(query)
        history_data = []
        
        if result and 'results' in result:
             series = result['results'][0].get('series', [])
             if series:
                 values = series[0].get('values', [])
                 for v in values:
                     if v[1] is not None:
                         history_data.append({
                             'equipment_id': equipment_id,
                             'equipment_name': equipment.name,
                             'value': round(v[1], 2),
                             'unit': 'kW',
                             'timestamp': v[0]
                         })

        return jsonify({
            'success': True,
            'data': history_data
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter histórico do equipamento: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@analytics_bp.route('/analytics/equipment/<int:equipment_id>/statistics', methods=['GET'])
def get_equipment_statistics(equipment_id):
    """Obtém estatísticas reais de um equipamento (Min, Max, Avg, Total)"""
    try:
        hours = int(request.args.get('hours', 24))
        equipment = Equipment.query.get_or_404(equipment_id)
        tag = equipment.tag or equipment.name
        
        # Query agregada stats
        # Integral para total energia (kWh) se for Power (kW)
        # Assumindo value = kW
        query = f'''
            SELECT mean("value") as avg, max("value") as max, min("value") as min 
            FROM "energy_consumption" 
            WHERE "tag" = '{tag}' AND "metric" = 'power_kw'
            AND time > now() - {hours}h
        '''
        
        result = influxdb_service.execute_query(query)
        stats = {'count': 0, 'average': 0, 'minimum': 0, 'maximum': 0, 'total': 0}
        
        if result and 'results' in result:
            series = result['results'][0].get('series', [])
            if series and series[0].get('values'):
                val = series[0]['values'][0] # [time, avg, max, min]
                # InfluxDB return order depends on SELECT columns, but usually matches
                # columns: ["time", "avg", "max", "min"]
                cols = series[0]['columns']
                
                # Construir dicionário seguro
                row = dict(zip(cols, val))
                
                avg_val = row.get('avg', 0) or 0
                max_val = row.get('max', 0) or 0
                min_val = row.get('min', 0) or 0
                
                # Total Energy Estimate: Avg Power * Hours
                total_energy = avg_val * hours
                
                stats = {
                    'count': hours, # Aproximação
                    'average': round(avg_val, 2),
                    'minimum': round(min_val, 2),
                    'maximum': round(max_val, 2),
                    'total': round(total_energy, 2)
                }

        return jsonify({
            'success': True,
            'data': {
                'equipment_id': equipment_id,
                'equipment_name': equipment.name,
                'period_hours': hours,
                'statistics': stats
            }
        })

    except Exception as e:
        logger.error(f"Erro ao obter estatísticas do equipamento: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@analytics_bp.route('/analytics/alerts', methods=['GET'])
def get_alerts():
    """Obtém lista de alertas (Baseado em leituras reais/estagnação)"""
    try:
        alerts = []
        
        # 1. Equipamentos Offline (Sem leitura > 2h) - Reusing logic
        # Idealmente, mover lógica para Service
        equipments = Equipment.query.filter_by(is_active=True).all()
        
        for eq in equipments:
             # Check last_reading_at from DB (updated by endpoints/collectors)
             # NOTE: Collectors might not update MySQL 'last_reading_at' frequently if only pushing to Influx
             # So we should rely on Influx check or ensure collector updates MySQL
             # For now, using MySQL field assuming collector updates it.
             if eq.last_reading_at:
                 if (datetime.now() - eq.last_reading_at) > timedelta(hours=2):
                     alerts.append({
                        'id': f"offline_{eq.id}",
                        'type': 'offline',
                        'severity': 'warning',
                        'equipment_id': eq.id,
                        'equipment_name': eq.name,
                        'message': f'Equipamento {eq.name} offline/sem dados',
                        'timestamp': eq.last_reading_at.isoformat()
                     })
             else:
                 # Nunca leu
                  alerts.append({
                        'id': f"never_read_{eq.id}",
                        'type': 'offline',
                        'severity': 'info',
                        'equipment_id': eq.id,
                        'equipment_name': eq.name,
                        'message': f'Equipamento {eq.name} aguardando primeira conexão',
                        'timestamp': datetime.now().isoformat()
                  })

        return jsonify({
            'success': True,
            'data': alerts
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter alertas: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@analytics_bp.route('/analytics/factory-view', methods=['GET'])
def get_factory_view():
    """
    Retorna visão consolidada da fábrica com totalizadores por nível hierárquico.
    - Total Fábrica (Entry Points)
    - Total Áreas (Soma de Áreas)
    - Total Linhas (Soma de Linhas)
    - Total Equipamentos (Soma de Equipamentos Finais)
    """
    try:
        # Obter todos os equipamentos ativos
        equipments = Equipment.query.filter_by(is_active=True).all()
        
        factory_total_kw = 0
        area_total_kw = 0
        line_total_kw = 0
        equipment_total_kw = 0
        
        factory_cost_hr = 0
        area_cost_hr = 0
        line_cost_hr = 0
        equipment_cost_hr = 0
        
        # Helper para calcular custo
        def calc_cost(kw, tariff):
            return (kw or 0) * (tariff or 0.5)

        for eq in equipments:
            val = eq.last_value or 0
            # Evitar somar valores negativos ou inválidos
            if val < 0: val = 0
            
            cost = calc_cost(val, eq.tariff_kwh)
            
            # Determinando o nível para agregação
            # Idealmente, usamos hierarchy_level. Se não tiver, tentamos inferir.
            level = eq._get_hierarchy_level()
            
            # Lógica de Agregação
            # 1. Se é Entry Point de Fábrica (nível mais alto)
            if eq.is_entry_point and (level == 'factory' or not level): 
                 # Se não tiver nível, mas é entry point, assumimos fábrica se não tiver pais?
                 # Simplificação: User disse "Total Fabrica", "Total Area", "Total Linha", "Total Equipamentos"
                 # Vamos agrupar puramente pelo nível hierárquico.
                 factory_total_kw += val
                 factory_cost_hr += cost
            
            # 2. Se é Entry Point de Área
            if level == 'area' and eq.is_entry_point:
                area_total_kw += val
                area_cost_hr += cost
                
            # 3. Se é Entry Point de Linha
            if level == 'line' and eq.is_entry_point:
                line_total_kw += val
                line_cost_hr += cost
                
            # 4. Se é Equipamento Final (Machine Group ou Generic, e NÃO é entry point de linha/area)
            # Ou simplesmente tudo que não é entry point?
            # O user disse "soma de todos equipamentos existentes de medição de energia excluindo os de entrada"
            if not eq.is_entry_point:
                equipment_total_kw += val
                equipment_cost_hr += cost

        return jsonify({
            'success': True,
            'data': {
                'factory': {
                    'power_kw': round(factory_total_kw, 2),
                    'cost_hour': round(factory_cost_hr, 2),
                    'label': 'Total Fábrica'
                },
                'areas': {
                    'power_kw': round(area_total_kw, 2),
                    'cost_hour': round(area_cost_hr, 2),
                    'label': 'Total Áreas'
                },
                'lines': {
                    'power_kw': round(line_total_kw, 2),
                    'cost_hour': round(line_cost_hr, 2),
                    'label': 'Total Linhas'
                },
                'equipments': {
                    'power_kw': round(equipment_total_kw, 2),
                    'cost_hour': round(equipment_cost_hr, 2),
                    'label': 'Total Equipamentos'
                },
                'timestamp': datetime.now().isoformat()
            }
        })

    except Exception as e:
        logger.error(f"Erro ao obter factory view: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

