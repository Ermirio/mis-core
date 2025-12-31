from flask import Blueprint, jsonify
import kpis_engine

kpis_bp = Blueprint('kpis', __name__)


# Helper para normalizar nome da linha (Linha 01 -> L01 -> Linha 01 normalized for Influx)
# NOTE: Routes.py uses L01 internally but Influx might use "Linha 01".
# Let's check routes.py again. Routes.py uses normalize_line_name to get "L01".
# But wait, earlier investigation showed that "L01" returned stale data and "Linha 01" might be the correct tag in Influx?
# Let's look at a previous turn.
# "This change assumes that "Linha 01" is the active line tag in InfluxDB and "L01" contains stale data."
# Wait, routes.py normalize_line_name returns L01.
# If routes.py uses L01 and works for "Realtime" (which displays 75% OLE), then L01 should be correct IF usage is consistent.
# The user said "gargalo" returns 105%.
# If I use normalize_line_name from routes.py, it converts "Linha 01" -> "L01".
# So if I apply it here, I ensure I use "L01".
# Maybe the issue is that "L01" IS the correct normalized name, but the kpis_route was receiving "L01" (already normalized) or "Linha 01" and passing it raw?
# If the route receives "L01", and I pass "L01", it should work.
# If the route receives "Linha 01" (unlikely from URL L01), it queries "Linha 01".
# Let's paste the helper anyway to be consistent with routes.py

def normalize_line_name(linha_nome):
    if not linha_nome: return linha_nome
    nome_upper = linha_nome.upper()
    if nome_upper.startswith("L") and len(nome_upper) <= 3 and nome_upper[1:].isdigit():
        return nome_upper.replace("l", "L")
    if "LINHA" in nome_upper:
        parts = nome_upper.split()
        if len(parts) > 1 and parts[1].isdigit():
             return f"L{parts[1].zfill(2)}"
    return nome_upper.replace("LINHA ", "L").replace("LINHA", "L")

@kpis_bp.route('/api/linha/<linha>/kpis', methods=['GET'])
def kpis_linha(linha):
    """
    Returns KPIs for a specific line.
    """
    try:
        # Normalize line name to ensure consistency (e.g. Linha 01 -> L01)
        linha_norm = normalize_line_name(linha)
        resultado = kpis_engine.calcular_kpis_linha(linha_norm)
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
