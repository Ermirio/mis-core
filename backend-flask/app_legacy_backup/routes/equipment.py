"""
Equipment Technical Data Routes
Provides technical equipment data (sensors, state, velocity).
"""
import logging
from flask import Blueprint, jsonify, current_app
from datetime import datetime

equipment_bp = Blueprint('equipment', __name__)
logger = logging.getLogger('[FLASK:EQUIPMENT]')

# Machine state translations
ESTADOS_MAQUINA = {
    0: "Online", 1: "Produzindo", 2: "Aguardando Anterior", 3: "Bloqueado Próximo",
    4: "Parado/Falha", 5: "Setup", 6: "Teste/Projeto", 7: "Aguardando Manutenção",
    8: "Manutenção", 9: "Falta de Material"
}

@equipment_bp.route('/api/equipamento/dados/<eq_code>', methods=['GET'])
def get_equipment_data(eq_code):
    """
    Returns technical data for an equipment (speed, state, sensors).
    Used by EquipamentoCard.tsx component.
    """
    try:
        influx_client = current_app.influx_client
        if not influx_client:
            return jsonify({'error': 'InfluxDB not available'}), 503

        # Query latest data from InfluxDB
        result_set = influx_client.query(
            f"SELECT last(*) FROM production WHERE \"equipment\" = '{eq_code}'"
        )
        points = list(result_set.get_points())
        
        if not points:
            return jsonify({'status': 'Sem dados disponíveis'}), 200

        data = points[0]

        # Fields to ignore (operational data, handled in production route)
        ignore_fields = [
            'time', 'last_producao_op_acumulada', 'last_producao_turno_acumulada',
            'last_toneladas_op', 'last_toneladas_turno', 'last_diferenca_op',
            'last_contagem_saida', 'last_contagem_entrada', 'last_velocidade_atual',
            'last_estado_maquina', 'last_ordem_producao_field', 'last_sku_codigo_field',
            'last_descricao', 'last_planejado_op', 'last_formato_gramas', 'last_formato',
            'last_cuc', 'last_shift'
        ]

        # Extract sensor data
        sensores = []
        for key, value in data.items():
            if key not in ignore_fields and value is not None:
                name = key.replace('last_', '').replace('_', ' ').capitalize()
                # Additional filtering
                if name.lower() not in ['estado', 'cuc', 'formato', 'ordem producao field']:
                    sensores.append({
                        "nome": name,
                        "valor": round(value, 2) if isinstance(value, float) else value,
                        "unidade": ""
                    })

        estado = int(data.get('last_estado_maquina', 0) or 0)

        response = {
            "equipamento": eq_code,
            "velocidade_atual": int(data.get('last_velocidade_atual', 0) or 0),
            "pecas_produzidas": int(data.get('last_producao_op_acumulada', 0) or 0),
            "refugos": int(data.get('last_descarte', 0) or 0),
            "estado_atual": ESTADOS_MAQUINA.get(estado, str(estado)),
            "sensores": sensores,
            "timestamp": datetime.now().isoformat()
        }

        logger.debug(f"[EQUIPMENT] {eq_code}: estado={estado}, vel={response['velocidade_atual']}")
        return jsonify(response)

    except Exception as e:
        logger.error(f"[EQUIPMENT ERROR] {eq_code}: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500
