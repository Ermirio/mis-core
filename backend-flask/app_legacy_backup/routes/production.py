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

        # CORREÇÃO: Usar SELECT * ORDER BY time DESC LIMIT 1 ao invés de SELECT last(*)
        # Isso permite ler TAGs (shift, order_id) junto com os FIELDs
        # Mesma abordagem usada em production_engine.py _load_state_from_db
        result_set = influx_client.query(
            f"SELECT * FROM production WHERE \"equipment\" = '{eq_code}' ORDER BY time DESC LIMIT 1"
        )
        points = list(result_set.get_points())
        
        if not points:
            return jsonify({'status': 'Aguardando dados...'}), 200

        data = points[0]

        # Extract production metrics (SEM o prefixo 'last_' porque não usamos last())
        prod_op = int(data.get('producao_op_acumulada', 0) or 0)
        planejado = int(data.get('planejado_op', 0) or 0)
        
        # Buscar a tag shift (agora disponível diretamente!)
        turno_atual = data.get('shift', 'N/A')

        response = {
            "equipamento": eq_code,
            "cuc": data.get('cuc', 'N/A'),
            "ordem_producao": data.get('ordem_producao_field', 'N/A'),
            "sku": data.get('sku_codigo_field', 'N/A'),
            "descricao": data.get('descricao', 'Produto não identificado'),
            "formato_gramas": int(data.get('formato_gramas') or data.get('formato') or 0),
            "planejado_op": planejado,
            "produzido_op": prod_op,
            "diferenca_op": int(data.get('diferenca_op', 0) or (prod_op - planejado)),
            "toneladas_op": float(data.get('toneladas_op', 0) or 0),
            "produzido_turno": int(data.get('producao_turno_acumulada', 0) or 0),
            "toneladas_turno": float(data.get('toneladas_turno', 0) or 0),
            "turno_atual": turno_atual,  # Agora lê a tag shift corretamente!
            "pecas_boas": prod_op,
            "pecas_ruins": int(data.get('descarte', 0) or 0),
            "timestamp": datetime.now().isoformat()
        }

        logger.debug(f"[PRODUCTION] {eq_code}: OP={response['ordem_producao']}, prod={prod_op}/{planejado}, turno={turno_atual}")
        return jsonify(response)

    except Exception as e:
        logger.error(f"[PRODUCTION ERROR] {eq_code}: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@production_bp.route('/api/realtime/status/<eq>', methods=['GET'])
def realtime_status(eq):
    """Alias route for backward compatibility"""
    return get_production_data(eq)
