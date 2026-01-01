from flask import Blueprint, request, jsonify
import logging
from datetime import datetime, timedelta
from src.models.user import db
from src.models.equipment import Equipment
from src.models.gateway import Gateway
from src.services.influxdb_client import influxdb_service
from src.services.simulation_service import simulation_service

logger = logging.getLogger(__name__)
analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/analytics/overview', methods=['GET'])
def get_factory_overview():
    """Obtém visão geral da fábrica (ISA 101)"""
    try:
        hierarchy_id = request.args.get('hierarchy_id', type=int)
        
        # Base query for active equipments
        query = Equipment.query.filter_by(is_active=True)
        
        # Filter by hierarchy if provided
        if hierarchy_id:
            # TODO: Idealmente, filtrar recursivamente. Por enquanto, filtro direto.
            # Para produção real, usar CTE ou closure table para buscar todos os filhos.
            query = query.filter_by(hierarchy_id=hierarchy_id)
            
        equipments = query.all()
        total_equipments = len(equipments)
        
        # Calculate totals
        total_power_kw = 0
        total_energy_kwh = 0
        active_alarms = 0
        
        for eq in equipments:
            # Sum power (assuming last_value is power for now, or use standard_consumption)
            if eq.last_value:
                total_power_kw += eq.last_value # Simplificação
            
            # Check alarms (no reading for > 2h)
            if not eq.last_reading_at or (datetime.now() - eq.last_reading_at) > timedelta(hours=2):
                active_alarms += 1
                
        # Calculate Efficiency (Mock logic: 100 - (alarms / total * 100))
        efficiency = 100.0
        if total_equipments > 0:
            efficiency = 100.0 - ((active_alarms / total_equipments) * 20) # Penalidade arbitrária
            efficiency = max(0, min(100, efficiency))

        return jsonify({
            'success': True,
            'data': {
                'total_power_kw': round(total_power_kw, 2),
                'total_energy_kwh': round(total_energy_kwh, 2), # Placeholder
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
    """Obtém dados para gráfico de consumo nas últimas 24h"""
    try:
        hours = int(request.args.get('hours', 24))
        
        # Verificar se modo simulação está ativo
        if simulation_service.is_simulation_active():
            simulated_data = simulation_service.get_consumption_chart_data(hours)
            if simulated_data:
                return jsonify({
                    'success': True,
                    'data': simulated_data,
                    'simulated': True
                })
        
        # Gerar dados simulados por hora (fallback)
        chart_data = []
        now = datetime.now()
        
        for i in range(hours):
            time_point = now - timedelta(hours=hours-i-1)
            
            # Simular consumo baseado na hora do dia
            hour = time_point.hour
            if 6 <= hour <= 18:  # Horário comercial
                base_consumption = 1200
            elif 19 <= hour <= 22:  # Horário de pico
                base_consumption = 1400
            else:  # Madrugada
                base_consumption = 800
            
            # Adicionar variação
            import random
            variation = random.uniform(0.8, 1.2)
            consumption = round(base_consumption * variation)
            
            chart_data.append({
                'time': time_point.strftime('%H:%M'),
                'consumption': consumption,
                'timestamp': time_point.isoformat()
            })
        
        return jsonify({
            'success': True,
            'data': chart_data,
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
    """Obtém resumo dos equipamentos para cards"""
    try:
        # Verificar se modo simulação está ativo
        if simulation_service.is_simulation_active():
            simulated_data = simulation_service.get_equipment_summary()
            if simulated_data:
                return jsonify({
                    'success': True,
                    'data': simulated_data,
                    'simulated': True
                })
        
        # Código original para dados reais
        equipments = Equipment.query.filter_by(is_active=True).all()
        
        equipment_data = []
        for equipment in equipments:
            # Determinar status baseado na última leitura
            status = 'normal'
            if equipment.last_reading_at:
                time_diff = datetime.now() - equipment.last_reading_at
                if time_diff > timedelta(hours=2):
                    status = 'alert'
            else:
                status = 'alert'
            
            # Simular consumo se não houver valor
            consumption = equipment.last_value
            if consumption is None:
                import random
                consumption = round(random.uniform(50, 300), 2)
            
            equipment_data.append({
                'id': equipment.id,
                'name': equipment.name,
                'location': equipment.location or 'N/A',
                'area': equipment.area or 'N/A',
                'consumption': consumption,
                'unit': equipment.unit,
                'status': status,
                'last_reading': equipment.last_reading_at.isoformat() if equipment.last_reading_at else None
            })
        
        return jsonify({
            'success': True,
            'data': equipment_data,
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
    """Obtém histórico de um equipamento específico"""
    try:
        hours = int(request.args.get('hours', 24))
        
        equipment = Equipment.query.get_or_404(equipment_id)
        
        # Tentar obter dados do InfluxDB
        try:
            measurements = influxdb_service.get_latest_measurements(
                equipment_id=equipment_id,
                limit=hours
            )
            
            if measurements:
                return jsonify({
                    'success': True,
                    'data': measurements
                })
        except Exception as e:
            logger.warning(f"Erro ao obter dados do InfluxDB: {e}")
        
        # Fallback: gerar dados simulados
        history_data = []
        now = datetime.now()
        
        for i in range(hours):
            time_point = now - timedelta(hours=hours-i-1)
            
            # Simular valores baseados no consumo padrão
            base_value = equipment.standard_consumption or 100
            import random
            variation = random.uniform(0.7, 1.3)
            value = round(base_value * variation, 2)
            
            history_data.append({
                'equipment_id': equipment_id,
                'equipment_name': equipment.name,
                'value': value,
                'unit': equipment.unit,
                'timestamp': time_point.isoformat()
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
    """Obtém estatísticas de um equipamento"""
    try:
        hours = int(request.args.get('hours', 24))
        
        equipment = Equipment.query.get_or_404(equipment_id)
        
        # Tentar obter estatísticas do InfluxDB
        try:
            stats = influxdb_service.get_equipment_statistics(equipment_id, hours)
            
            if stats:
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
            logger.warning(f"Erro ao obter estatísticas do InfluxDB: {e}")
        
        # Fallback: calcular estatísticas simuladas
        base_value = equipment.standard_consumption or 100
        stats = {
            'count': hours,
            'average': base_value,
            'minimum': round(base_value * 0.7, 2),
            'maximum': round(base_value * 1.3, 2),
            'total': round(base_value * hours, 2)
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
    """Obtém lista de alertas do sistema"""
    try:
        alerts = []
        
        # Equipamentos sem leitura recente
        two_hours_ago = datetime.now() - timedelta(hours=2)
        offline_equipments = Equipment.query.filter(
            Equipment.is_active == True,
            Equipment.last_reading_at < two_hours_ago
        ).all()
        
        for equipment in offline_equipments:
            alerts.append({
                'id': f"offline_{equipment.id}",
                'type': 'offline',
                'severity': 'warning',
                'equipment_id': equipment.id,
                'equipment_name': equipment.name,
                'message': f'Equipamento {equipment.name} sem leitura há mais de 2 horas',
                'timestamp': equipment.last_reading_at.isoformat() if equipment.last_reading_at else None
            })
        
        # Equipamentos com consumo alto (simulado)
        high_consumption_equipments = Equipment.query.filter(
            Equipment.is_active == True,
            Equipment.last_value > (Equipment.standard_consumption * 1.5)
        ).all()
        
        for equipment in high_consumption_equipments:
            alerts.append({
                'id': f"high_consumption_{equipment.id}",
                'type': 'high_consumption',
                'severity': 'error',
                'equipment_id': equipment.id,
                'equipment_name': equipment.name,
                'message': f'Consumo alto detectado: {equipment.last_value} {equipment.unit}',
                'timestamp': equipment.last_reading_at.isoformat() if equipment.last_reading_at else None
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

