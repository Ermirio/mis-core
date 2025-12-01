from flask import Blueprint, jsonify
import kpis_engine

kpis_bp = Blueprint('kpis', __name__)

@kpis_bp.route('/api/linha/<linha>/kpis', methods=['GET'])
def kpis_linha(linha):
    """
    Returns KPIs for a specific line.
    """
    try:
        resultado = kpis_engine.calcular_kpis_linha(linha)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@kpis_bp.route('/api/equipamento/<eq>/kpis', methods=['GET'])
def kpis_equipamento(eq):
    """
    Returns KPIs for a specific equipment.
    """
    try:
        resultado = kpis_engine.calcular_kpis_equipamento(eq)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@kpis_bp.route('/api/fabrica/kpis/', methods=['GET'])
def get_factory_kpis_route():
    """
    Returns aggregated KPIs for the entire factory.
    Supports 'period' parameter: turno, dia, semana, mes.
    """
    try:
        from flask import request
        import factory_kpis_engine
        
        period = request.args.get('period', 'turno')
        data = factory_kpis_engine.get_factory_kpis(period)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@kpis_bp.route('/api/fabrica/kpis', methods=['GET'])
def kpis_fabrica():
    """
    Legacy endpoint redirecting to new logic for consistency.
    """
    return get_factory_kpis_route()
