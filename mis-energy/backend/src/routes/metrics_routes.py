# backend/src/routes/metrics_routes.py
from flask import Blueprint, request, jsonify
import logging
from src.models.user import db
from src.models.metrics_config import MetricsConfig

logger = logging.getLogger(__name__)
metrics_bp = Blueprint('metrics', __name__)

@metrics_bp.route('/config/metrics', methods=['GET'])
def get_metrics_config():
    """Retorna configurações de métricas"""
    try:
        config = MetricsConfig.get_instance()
        return jsonify({
            'success': True,
            'data': config.to_dict()
        })
    except Exception as e:
        logger.error(f"Erro ao obter config de métricas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@metrics_bp.route('/config/metrics', methods=['PUT'])
def update_metrics_config():
    """Atualiza configurações de métricas"""
    try:
        data = request.get_json()
        config = MetricsConfig.get_instance()
        
        # Atualizar campos
        if 'kwh_cost_brl' in data:
            config.kwh_cost_brl = float(data['kwh_cost_brl'])
        
        if 'usd_brl_rate' in data:
            config.usd_brl_rate = float(data['usd_brl_rate'])
            
        if 'eur_brl_rate' in data:
            config.eur_brl_rate = float(data['eur_brl_rate'])
            
        if 'production_unit' in data:
            config.production_unit = data['production_unit']
            
        if 'production_unit_label' in data:
            config.production_unit_label = data['production_unit_label']
            
        if 'simulation_enabled' in data:
            config.simulation_enabled = bool(data['simulation_enabled'])
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': config.to_dict(),
            'message': 'Configurações atualizadas com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao atualizar config de métricas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@metrics_bp.route('/config/simulation/toggle', methods=['POST'])
def toggle_simulation():
    """Alterna modo de simulação"""
    try:
        config = MetricsConfig.get_instance()
        config.simulation_enabled = not config.simulation_enabled
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': {
                'simulation_enabled': config.simulation_enabled
            },
            'message': f"Simulação {'ativada' if config.simulation_enabled else 'desativada'}"
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao alternar simulação: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
