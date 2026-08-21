"""
Factory/Line Aggregated Metrics Routes
Provides consolidated metrics and KPIs for lines and factory overview.
"""
import logging
from flask import Blueprint, jsonify, current_app, request

factory_bp = Blueprint('factory', __name__)
logger = logging.getLogger('[FLASK:FACTORY]')

@factory_bp.route('/api/factory/metrics', methods=['GET'])
@factory_bp.route('/api/factory/metrics/<line_code>', methods=['GET'])
def get_factory_metrics(line_code=None):
    """
    Returns consolidated metrics/KPIs for entire factory or specific line.
    Aggregates data from all equipment in the line/factory.
    
    Query Parameters:
    - period: 'hour', 'shift', 'day' (optional)
    - shift: shift code (optional)
    """
    try:
        influx_client = current_app.influx_client
        if not influx_client:
            return jsonify({'error': 'InfluxDB not available'}), 503

        period = request.args.get('period', 'current')
        shift = request.args.get('shift', None)

        # Build query based on parameters
        if line_code:
            where_clause = f"\"line\" = '{line_code}'"
            logger.debug(f"[FACTORY] Querying metrics for line: {line_code}")
        else:
            where_clause = "1=1"  # All lines
            logger.debug(f"[FACTORY] Querying metrics for entire factory")

        # Query for aggregated metrics
        # This is a placeholder - actual implementation depends on data structure
        query = f"""
            SELECT 
                SUM(last_producao_op_acumulada) as total_production,
                SUM(last_planejado_op) as total_target,
                MEAN(last_oee) as avg_oee,
                COUNT(DISTINCT equipment) as equipment_count
            FROM production 
            WHERE {where_clause}
            AND time > now() - 1h
        """

        result_set = influx_client.query(query)
        points = list(result_set.get_points())

        if not points or not points[0]:
            return jsonify({
                'line': line_code or 'ALL',
                'total_production': 0,
                'total_target': 0,
                'avg_oee': 0.0,
                'equipment_count': 0,
                'status': 'No data available'
            }), 200

        data = points[0]

        response = {
            'line': line_code or 'ALL',
            'period': period,
            'shift': shift or 'current',
            'total_production': int(data.get('total_production', 0) or 0),
            'total_target': int(data.get('total_target', 0) or 0),
            'avg_oee': round(float(data.get('avg_oee', 0) or 0), 2),
            'equipment_count': int(data.get('equipment_count', 0) or 0),
            'efficiency': round((data.get('total_production', 0) / data.get('total_target', 1)) * 100, 2) if data.get('total_target', 0) > 0 else 0
        }

        logger.info(f"[FACTORY] {line_code or 'ALL'}: prod={response['total_production']}, OEE={response['avg_oee']}%")
        return jsonify(response)

    except Exception as e:
        logger.error(f"[FACTORY ERROR] {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500
