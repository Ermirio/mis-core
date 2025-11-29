import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from influxdb import InfluxDBClient
from decouple import config
from datetime import datetime

from production_engine import get_engine

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===== CONFIGS =====
INFLUX_HOST = config('INFLUXDB_HOST', default='127.0.0.1')
INFLUX_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUX_DB = config('INFLUXDB_DATABASE', default='industrial_db')
INFLUX_USER = config('INFLUXDB_USER', default='admin')
INFLUX_PASS = config('INFLUXDB_USER_PASSWORD', default='ixvq10A@10')
DJANGO_API_URL = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')

ESTADOS_MAQUINA = {
    0: "Online", 1: "Produzindo", 2: "Aguardando Anterior", 3: "Bloqueado Próximo",
    4: "Parado/Falha", 5: "Setup", 6: "Teste/Projeto", 7: "Aguardando Manutenção",
    8: "Manutenção", 9: "Falta de Material"
}

# Inicializa Engine
try:
    influx_client = InfluxDBClient(host=INFLUX_HOST, port=INFLUX_PORT, username=INFLUX_USER, password=INFLUX_PASS, database=INFLUX_DB)
    # Passamos a URL do Django para o motor se conectar
    production_engine = get_engine(influx_client, DJANGO_API_URL)
    logger.info(f"✓ Engine Iniciado (Conectado ao Django: {DJANGO_API_URL})")
except Exception as e:
    logger.error(f"✗ Erro Crítico: {e}")
    influx_client = None
    production_engine = None

# ===== NOVO: ROTA DE WEBHOOK (GATILHO DO DJANGO) =====
@app.route('/api/system/refresh-shifts', methods=['POST'])
def refresh_shifts():
    """
    Rota chamada pelo Django quando um Turno é criado/editado/excluído.
    Força o Flask a recarregar as regras imediatamente.
    """
    if production_engine:
        sucesso = production_engine.recarregar_configuracoes()
        if sucesso:
            return jsonify({'status': 'success', 'message': 'Turnos recarregados do Django'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Falha ao conectar ao Django'}), 500
    return jsonify({'error': 'Engine não iniciado'}), 500

# ===== ROTAS DE DADOS =====

@app.route('/api/operacao/dados/<eq_code>', methods=['GET'])
def get_operacao(eq_code):
    try:
        rs = influx_client.query(f"SELECT last(*) FROM production WHERE \"equipment\" = '{eq_code}'")
        pts = list(rs.get_points())
        if not pts: return jsonify({'status': 'Aguardando...'}), 200
        d = pts[0]

        prod_op = int(d.get('last_producao_op_acumulada', 0) or 0)
        plan = int(d.get('last_planejado_op', 0) or 0)

        # Busca valores ou 0 se nulo
        return jsonify({
            "equipamento": eq_code,
            "cuc": d.get('last_cuc', 'N/A'),
            "ordem_producao": d.get('last_ordem_producao_field', 'N/A'),
            "sku": d.get('last_sku_codigo_field', 'N/A'),
            "descricao": d.get('last_descricao', 'Produto não identificado'),
            "formato_gramas": int(d.get('last_formato_gramas') or d.get('last_formato') or 0),
            "planejado_op": plan,
            "produzido_op": prod_op,
            "diferenca_op": int(d.get('last_diferenca_op', 0) or (prod_op - plan)),
            "toneladas_op": float(d.get('last_toneladas_op', 0) or 0),
            "produzido_turno": int(d.get('last_producao_turno_acumulada', 0) or 0),
            "toneladas_turno": float(d.get('last_toneladas_turno', 0) or 0),
            "turno_atual": d.get('last_shift', 'N/A'),
            "pecas_boas": prod_op, 
            "pecas_ruins": int(d.get('last_descarte', 0) or 0),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/equipamento/dados/<eq_code>', methods=['GET'])
def get_equipamento(eq_code):
    try:
        rs = influx_client.query(f"SELECT last(*) FROM production WHERE \"equipment\" = '{eq_code}'")
        pts = list(rs.get_points())
        if not pts: return jsonify({'status': 'Sem dados'}), 200
        d = pts[0]
        
        ignore = ['time', 'last_producao_op_acumulada', 'last_producao_turno_acumulada', 
                  'last_toneladas_op', 'last_toneladas_turno', 'last_diferenca_op',
                  'last_contagem_saida', 'last_contagem_entrada', 'last_velocidade_atual', 
                  'last_estado_maquina', 'last_ordem_producao_field', 'last_sku_codigo_field', 
                  'last_descricao', 'last_planejado_op', 'last_formato_gramas', 'last_formato', 
                  'last_cuc', 'last_shift']

        sensores = []
        for k, v in d.items():
            if k not in ignore and v is not None:
                name = k.replace('last_', '').replace('_', ' ').capitalize()
                if name.lower() not in ['estado', 'cuc', 'formato', 'ordem producao field']:
                    sensores.append({"nome": name, "valor": round(v, 2) if isinstance(v, float) else v, "unidade": ""})

        est = int(d.get('last_estado_maquina', 0) or 0)
        return jsonify({
            "equipamento": eq_code,
            "velocidade_atual": int(d.get('last_velocidade_atual', 0) or 0),
            "pecas_produzidas": int(d.get('last_producao_op_acumulada', 0) or 0),
            "refugos": int(d.get('last_descarte', 0) or 0),
            "estado_atual": ESTADOS_MAQUINA.get(est, str(est)),
            "sensores": sensores,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Cache simples para velocidade
_last_counts = {}
def calc_speed_rpm(eq, current):
    prev = _last_counts.get(eq)
    _last_counts[eq] = current
    if prev is None or current < prev: return 0
    return int((current - prev) * 12)

_last_states = {}
def changed_state(eq, state):
    prev = _last_states.get(eq)
    if prev != state:
        _last_states[eq] = state
        return True
    return False

@app.route('/api/dados/inserir', methods=['POST'])
def inserir():
    try:
        d = request.json
        eq = d.get('equipamento_codigo') or d.get('equipamento')
        line = d.get('linha_codigo', '')
        ts = d.get('timestamp')
        m = d.get('medicoes', {})

        if not eq or not m: return jsonify({'error': 'Dados incompletos'}), 400

        est = int(m.get('estado_maquina', 0) or 0)
        cont = int(float(m.get('contagem_saida', 0)))
        desc = int(float(m.get('descarte', 0)))
        op = str(m.get('ordem_producao', 'N/A'))
        sku = str(m.get('sku_codigo', 'N/A'))
        plan = int(float(m.get('planejado_op', 0)))
        fmt = float(m.get('formato_gramas') or m.get('formato') or 0)

        # O MOTOR CALCULA TUDO (incluindo o Turno baseado no Django)
        res = production_engine.processar_dados(
            equipamento=eq,
            op_atual=op,
            contagem_bruta=cont,
            descarte=desc,
            formato_gramas=fmt,
            planejado=plan
        )

        fields = {
            "velocidade_atual": calc_speed_rpm(eq, cont),
            "estado_maquina": est,
            "ordem_producao_field": op,
            "sku_codigo_field": sku,
            "producao_op_acumulada": res['producao_op'],
            "toneladas_op": res['toneladas_op'],
            "diferenca_op": res['diferenca_op'],
            "producao_turno_acumulada": res['producao_turno'],
            "toneladas_turno": res['toneladas_turno']
        }

        for k, v in m.items():
            if k not in ['estado_maquina', 'velocidade_atual', 'ordem_producao', 'sku_codigo', 'planejado_op']:
                if k == 'cuc': fields[k] = str(v)
                elif k in ['formato', 'formato_gramas']: fields[k] = float(v)
                else: fields[k] = v

        points = [{
            "measurement": "production",
            "tags": {
                "line": line, 
                "equipment": eq, 
                "shift": res['turno_atual_nome'], # Turno real vindo do Django
                "order_id": op, 
                "sku": sku
            },
            "fields": fields
        }]
        
        if ts: points[0]["time"] = ts

        if changed_state(eq, est):
            points.append({
                "measurement": "machine_status",
                "tags": {"line": line, "equipment": eq, "estado_maquina": str(est)},
                "fields": {"value": 1},
                "time": ts if ts else None
            })

        if influx_client: influx_client.write_points(points)
        
        return jsonify({'status': 'success', 'data': res})

    except Exception as e:
        logger.error(f"Erro: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/realtime/status/<eq>', methods=['GET'])
def rt(eq): return get_operacao(eq)
@app.route('/api/health', methods=['GET'])
def health(): return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)