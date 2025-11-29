"""
Data Ingestion Routes
Handles incoming production data from the OPC UA collector.
"""
import logging
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime

ingestion_bp = Blueprint('ingestion', __name__)
logger = logging.getLogger('[FLASK:INGESTION]')

# State caches for calculations
_last_counts = {}
_last_states = {}

def calc_speed_rpm(eq, current):
    """Calculate RPM from counter difference"""
    prev = _last_counts.get(eq)
    _last_counts[eq] = current
    if prev is None or current < prev:
        return 0
    return int((current - prev) * 12)

def changed_state(eq, state):
    """Check if machine state changed"""
    prev = _last_states.get(eq)
    if prev != state:
        _last_states[eq] = state
        return True
    return False

@ingestion_bp.route('/api/dados/inserir', methods=['POST'])
def inserir():
    """
    Receives production data from the OPC UA collector.
    Processes data through ProductionEngine and stores in InfluxDB.
    """
    try:
        data = request.json
        eq = data.get('equipamento_codigo') or data.get('equipamento')
        line = data.get('linha_codigo', '')
        ts = data.get('timestamp')
        medicoes = data.get('medicoes', {})

        if not eq or not medicoes:
            return jsonify({'error': 'Dados incompletos'}), 400

        # Extract measurements
        estado = int(medicoes.get('estado_maquina', 0) or 0)
        contagem = int(float(medicoes.get('contagem_saida', 0)))
        descarte = int(float(medicoes.get('descarte', 0)))
        op = str(medicoes.get('ordem_producao', 'N/A'))
        sku = str(medicoes.get('sku_codigo', 'N/A'))
        planejado = int(float(medicoes.get('planejado_op', 0)))
        formato = float(medicoes.get('formato_gramas') or medicoes.get('formato') or 0)

        # Process through Production Engine
        engine = current_app.production_engine
        if not engine:
            logger.warning("Production Engine not available, storing raw data only")
            engine_result = {
                'producao_op': contagem,
                'toneladas_op': 0.0,
                'diferenca_op': 0,
                'producao_turno': contagem,
                'toneladas_turno': 0.0,
                'turno_atual_nome': 'N/A'
            }
        else:
            engine_result = engine.processar_dados(
                equipamento=eq,
                op_atual=op,
                contagem_bruta=contagem,
                descarte=descarte,
                formato_gramas=formato,
                planejado=planejado
            )

        # Build InfluxDB fields
        fields = {
            "velocidade_atual": calc_speed_rpm(eq, contagem),
            "estado_maquina": estado,
            "ordem_producao_field": op,
            "sku_codigo_field": sku,
            "producao_op_acumulada": engine_result['producao_op'],
            "toneladas_op": engine_result['toneladas_op'],
            "diferenca_op": engine_result['diferenca_op'],
            "producao_turno_acumulada": engine_result['producao_turno'],
            "toneladas_turno": engine_result['toneladas_turno']
        }

        # Add other measurements
        for key, value in medicoes.items():
            if key not in ['estado_maquina', 'velocidade_atual', 'ordem_producao', 'sku_codigo', 'planejado_op']:
                if key == 'cuc':
                    fields[key] = str(value)
                elif key in ['formato', 'formato_gramas']:
                    fields[key] = float(value)
                else:
                    fields[key] = value

        # Prepare InfluxDB points
        points = [{
            "measurement": "production",
            "tags": {
                "line": line,
                "equipment": eq,
                "shift": engine_result['turno_atual_nome'],
                "order_id": op,
                "sku": sku
            },
            "fields": fields
        }]

        if ts:
            points[0]["time"] = ts

        # Add machine state change event
        if changed_state(eq, estado):
            points.append({
                "measurement": "machine_status",
                "tags": {
                    "line": line,
                    "equipment": eq,
                    "estado_maquina": str(estado)
                },
                "fields": {"value": 1},
                "time": ts if ts else None
            })

        # Write to InfluxDB
        influx_client = current_app.influx_client
        if influx_client:
            influx_client.write_points(points)
        else:
            logger.warning("InfluxDB client not available, data not stored")

        logger.info(f"[INGESTION] {eq}: saída={contagem}, OP={op}, turno={engine_result['turno_atual_nome']}")
        return jsonify({'status': 'success', 'data': engine_result})

    except Exception as e:
        logger.error(f"[INGESTION ERROR] {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500
