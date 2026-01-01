from flask import Blueprint, request, jsonify
import logging
from src.services.simulation_service import simulation_service

logger = logging.getLogger(__name__)
simulation_bp = Blueprint('simulation', __name__)

@simulation_bp.route('/simulation/status', methods=['GET'])
def get_simulation_status():
    """Obtém status do modo simulação"""
    try:
        return jsonify({
            'success': True,
            'data': {
                'simulation_active': simulation_service.is_simulation_active(),
                'last_generated': simulation_service.last_generated.isoformat() if simulation_service.last_generated else None
            }
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter status da simulação: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@simulation_bp.route('/simulation/toggle', methods=['POST'])
def toggle_simulation():
    """Alterna o modo simulação"""
    try:
        active = simulation_service.toggle_simulation_mode()
        
        return jsonify({
            'success': True,
            'data': {
                'simulation_active': active,
                'message': f'Modo simulação {"ativado" if active else "desativado"} com sucesso'
            }
        })
        
    except Exception as e:
        logger.error(f"Erro ao alternar simulação: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@simulation_bp.route('/simulation/enable', methods=['POST'])
def enable_simulation():
    """Ativa o modo simulação"""
    try:
        simulation_service.set_simulation_mode(True)
        
        return jsonify({
            'success': True,
            'data': {
                'simulation_active': True,
                'message': 'Modo simulação ativado com sucesso'
            }
        })
        
    except Exception as e:
        logger.error(f"Erro ao ativar simulação: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@simulation_bp.route('/simulation/disable', methods=['POST'])
def disable_simulation():
    """Desativa o modo simulação"""
    try:
        simulation_service.set_simulation_mode(False)
        
        return jsonify({
            'success': True,
            'data': {
                'simulation_active': False,
                'message': 'Modo simulação desativado com sucesso'
            }
        })
        
    except Exception as e:
        logger.error(f"Erro ao desativar simulação: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@simulation_bp.route('/simulation/regenerate', methods=['POST'])
def regenerate_data():
    """Regenera dados simulados"""
    try:
        if not simulation_service.is_simulation_active():
            return jsonify({
                'success': False,
                'error': 'Modo simulação não está ativo'
            }), 400
        
        simulation_service.generate_sample_data()
        
        return jsonify({
            'success': True,
            'data': {
                'message': 'Dados simulados regenerados com sucesso',
                'last_generated': simulation_service.last_generated.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Erro ao regenerar dados: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

