"""
Production Operational Data Routes
Provides operational production data (OP, SKU, targets, production).
"""
import logging
from flask import Blueprint, jsonify, current_app
from datetime import datetime

production_bp = Blueprint('production', __name__)
logger = logging.getLogger('[FLASK:PRODUCTION]')

@production_bp.route('/api/operacao/dados/<eq_code>', methods=['GET'])
def get_production_data(eq_code):
    """
    Returns operational data for equipment (OP, SKU, targets, production).
    Used by Home.tsx component for production monitoring.
    """
    try:
        influx_client = current_app.influx_client
        if not influx_client:
            return jsonify({'error': 'InfluxDB not available'}), 503

        # Query latest production data
        result_set = influx_client.query(
            f"SELECT last(*) FROM production WHERE \"equipment\" = '{eq_code}'"
        )
        points = list(result_set.get_points())
        
        if not points:
            return jsonify({'status': 'Aguardando dados...'}), 200

        data = points[0]

        # Extract production metrics
        prod_op = int(data.get('last_producao_op_acumulada', 0) or 0)
        planejado = int(data.get('last_planejado_op', 0) or 0)

        response = {
            "equipamento": eq_code,
            "cuc": data.get('last_cuc', 'N/A'),
            "ordem_producao": data.get('last_ordem_producao_field', 'N/A'),
            "sku": data.get('last_sku_codigo_field', 'N/A'),
            "descricao": data.get('last_descricao', 'Produto não identificado'),
            "formato_gramas": int(data.get('last_formato_gramas') or data.get('last_formato') or 0),
            "planejado_op": planejado,
            "produzido_op": prod_op,
            "diferenca_op": int(data.get('last_diferenca_op', 0) or (prod_op - planejado)),
            "toneladas_op": float(data.get('last_toneladas_op', 0) or 0),
            "produzido_turno": int(data.get('last_producao_turno_acumulada', 0) or 0),
            "toneladas_turno": float(data.get('last_toneladas_turno', 0) or 0),
            "turno_atual": data.get('last_shift', 'N/A'),
            "pecas_boas": prod_op,
            "pecas_ruins": int(data.get('last_descarte', 0) or 0),
            "timestamp": datetime.now().isoformat()
        }

        logger.debug(f"[PRODUCTION] {eq_code}: OP={response['ordem_producao']}, prod={prod_op}/{planejado}")
        return jsonify(response)

    except Exception as e:
        logger.error(f"[PRODUCTION ERROR] {eq_code}: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@production_bp.route('/api/realtime/status/<eq>', methods=['GET'])
def realtime_status(eq):
    """Alias route for backward compatibility"""
    return get_production_data(eq)
