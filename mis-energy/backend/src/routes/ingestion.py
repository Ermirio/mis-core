from flask import Blueprint, request, jsonify
from src.services.influxdb_client import influxdb_service
import logging

ingestion_bp = Blueprint('ingestion', __name__)
logger = logging.getLogger(__name__)

@ingestion_bp.route('/dados/inserir', methods=['POST'])
def receive_data():
    """
    Recebe dados do Coletor e salva no InfluxDB.
    Payload: List of dicts
    [{ "equipamento_codigo": "...", "medicoes": {...}, "timestamp": "..." }]
    """
    try:
        data = request.get_json()
        if not isinstance(data, list):
            data = [data]
            
        success = influxdb_service.write_batch_data(data)
        
        if success:
            return jsonify({'success': True, 'message': 'Dados processados'}), 201
        else:
            return jsonify({'success': False, 'error': 'Falha na escrita InfluxDB'}), 500

    except Exception as e:
        logger.error(f"Erro na ingestão: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
