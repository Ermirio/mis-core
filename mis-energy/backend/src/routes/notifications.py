"""
Notification System Routes
Gera e retorna notificações baseadas em desvios do sistema.
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from src.models.equipment import Equipment
from src.services.opc_client import opc_client_service

notifications_bp = Blueprint('notifications', __name__)


def get_equipment_status(equipment):
    """Calcula o status de um equipamento baseado nos valores atuais vs padrão."""
    alerts = []
    
    gateway = equipment.gateway
    if not gateway or gateway.protocol_type != 'opc':
        return alerts
    
    # Helper para leitura segura
    def safe_read(node_id, scale=1.0):
        if not node_id:
            return None
        try:
            res = opc_client_service.read_value(gateway.opc_url, node_id, gateway.timeout or 5)
            return res.get('converted_value') * scale if res.get('success') and res.get('converted_value') is not None else None
        except:
            return None
    
    standard = equipment.standard_consumption
    
    if equipment.meter_type == 'production':
        # Production meter checks
        prod_rate_node = equipment.parameters.get('production_rate_node')
        current_rate = safe_read(prod_rate_node, 1.0)
        
        if current_rate is not None and standard:
            percent = (current_rate / standard) * 100
            if percent < 80:
                alerts.append({
                    'type': 'production_low',
                    'severity': 'critical',
                    'title': 'Produção Crítica',
                    'message': f'{equipment.name}: {current_rate:.1f} {equipment.unit}/h ({percent:.0f}% do padrão)',
                    'equipment_id': equipment.id,
                    'equipment_name': equipment.name,
                    'value': current_rate,
                    'target': standard,
                    'percent': percent
                })
            elif percent < 100:
                alerts.append({
                    'type': 'production_low',
                    'severity': 'warning',
                    'title': 'Produção Abaixo do Esperado',
                    'message': f'{equipment.name}: {current_rate:.1f} {equipment.unit}/h ({percent:.0f}% do padrão)',
                    'equipment_id': equipment.id,
                    'equipment_name': equipment.name,
                    'value': current_rate,
                    'target': standard,
                    'percent': percent
                })
        
        # Efficiency check
        efficiency_target = equipment.parameters.get('efficiency_target')
        if efficiency_target:
            # Get power from associated energy meter
            energy_meter = Equipment.query.filter(
                Equipment.hierarchy_id == equipment.hierarchy_id,
                Equipment.meter_type == 'energy',
                Equipment.is_entry_point == True,
                Equipment.id != equipment.id
            ).first()
            
            if energy_meter and current_rate and current_rate > 0:
                power_kw = safe_read(energy_meter.opc_node_power_kw, energy_meter.scale_factor)
                if power_kw:
                    efficiency = power_kw / current_rate
                    if efficiency > efficiency_target:
                        alerts.append({
                            'type': 'efficiency_high',
                            'severity': 'warning',
                            'title': 'Eficiência Acima do Target',
                            'message': f'{equipment.name}: {efficiency:.2f} kWh/Ton (target: {efficiency_target} kWh/Ton)',
                            'equipment_id': equipment.id,
                            'equipment_name': equipment.name,
                            'value': efficiency,
                            'target': efficiency_target
                        })
    
    else:
        # Energy meter checks  
        power_kw = safe_read(equipment.opc_node_power_kw, equipment.scale_factor)
        
        if power_kw is not None and standard:
            percent = (power_kw / standard) * 100
            if percent > 120:
                alerts.append({
                    'type': 'consumption_high',
                    'severity': 'critical',
                    'title': 'Consumo Crítico',
                    'message': f'{equipment.name}: {power_kw:.1f} kW ({percent:.0f}% do padrão)',
                    'equipment_id': equipment.id,
                    'equipment_name': equipment.name,
                    'value': power_kw,
                    'target': standard,
                    'percent': percent
                })
            elif percent > 100:
                alerts.append({
                    'type': 'consumption_high',
                    'severity': 'warning',
                    'title': 'Consumo Acima do Padrão',
                    'message': f'{equipment.name}: {power_kw:.1f} kW ({percent:.0f}% do padrão)',
                    'equipment_id': equipment.id,
                    'equipment_name': equipment.name,
                    'value': power_kw,
                    'target': standard,
                    'percent': percent
                })
        
        # Power factor check
        pf = safe_read(equipment.opc_node_power_factor)
        if pf is not None and pf < 0.92:
            alerts.append({
                'type': 'power_factor_low',
                'severity': 'warning',
                'title': 'Fator de Potência Baixo',
                'message': f'{equipment.name}: FP = {pf:.2f} (mínimo recomendado: 0.92)',
                'equipment_id': equipment.id,
                'equipment_name': equipment.name,
                'value': pf,
                'target': 0.92
            })
    
    return alerts


@notifications_bp.route('/notifications', methods=['GET'])
def get_notifications():
    """
    Retorna todas as notificações de desvio ativas.
    """
    try:
        equipments = Equipment.query.filter(Equipment.is_active == True).all()
        
        all_alerts = []
        for eq in equipments:
            try:
                alerts = get_equipment_status(eq)
                all_alerts.extend(alerts)
            except Exception as e:
                continue  # Skip failed equipment
        
        # Sort by severity (critical first)
        severity_order = {'critical': 0, 'warning': 1, 'info': 2}
        all_alerts.sort(key=lambda x: severity_order.get(x.get('severity', 'info'), 99))
        
        return jsonify({
            'success': True,
            'data': {
                'notifications': all_alerts,
                'count': len(all_alerts),
                'critical_count': len([a for a in all_alerts if a.get('severity') == 'critical']),
                'warning_count': len([a for a in all_alerts if a.get('severity') == 'warning']),
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
