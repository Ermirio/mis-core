"""
System Management Routes
Handles system webhooks, health checks, and configuration refresh.
"""
import logging
from flask import Blueprint, jsonify, current_app

system_bp = Blueprint('system', __name__)
logger = logging.getLogger('[FLASK:SYSTEM]')

@system_bp.route('/api/system/refresh-shifts', methods=['POST'])
def refresh_shifts():
    """
    Webhook called by Django when shifts are created/edited/deleted.
    Forces Flask to reload shift rules immediately without restart.
    """
    try:
        engine = current_app.production_engine
        if not engine:
            logger.error("[SYSTEM] Production Engine not available")
            return jsonify({'error': 'Production Engine not initialized'}), 500

        success = engine.recarregar_configuracoes()
        if success:
            logger.info("[SYSTEM] ✓ Shift configurations reloaded from Django")
            return jsonify({
                'status': 'success',
                'message': 'Turnos recarregados do Django'
            }), 200
        else:
            logger.warning("[SYSTEM] ✗ Failed to connect to Django API")
            return jsonify({
                'status': 'error',
                'message': 'Falha ao conectar ao Django'
            }), 500

    except Exception as e:
        logger.error(f"[SYSTEM ERROR] Refresh shifts failed: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@system_bp.route('/api/health', methods=['GET'])
def health():
    """
    Health check endpoint.
    Returns status of all system components.
    """
    influx_status = 'ok' if current_app.influx_client else 'unavailable'
    engine_status = 'ok' if current_app.production_engine else 'unavailable'

    overall_status = 'ok' if (influx_status == 'ok' and engine_status == 'ok') else 'degraded'

    response = {
        'status': overall_status,
        'components': {
            'influxdb': influx_status,
            'production_engine': engine_status
        }
    }

    logger.debug(f"[SYSTEM] Health check: {overall_status}")
    return jsonify(response), 200 if overall_status == 'ok' else 503
