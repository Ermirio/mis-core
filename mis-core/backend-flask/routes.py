import logging
import time
import requests
from decouple import config
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, current_app

# Helper para normalizar nome da linha (Linha 01 -> L01)
def normalize_line_name(linha_nome):
    if not linha_nome: return linha_nome
    
    # Normaliza para lidar com LINHA, Linha, linha
    nome_upper = linha_nome.upper()
    
    # Se ja for L01, L02...
    if nome_upper.startswith("L") and len(nome_upper) <= 3 and nome_upper[1:].isdigit():
        return nome_upper.replace("l", "L") # Garante L maiusculo
        
    if "LINHA" in nome_upper:
        parts = nome_upper.split()
        if len(parts) > 1 and parts[1].isdigit():
             return f"L{parts[1].zfill(2)}" # Ensure L01, L02
             
    # Fallback genérico
    return nome_upper.replace("LINHA ", "L").replace("LINHA", "L")

DJANGO_API_URL = config('DJANGO_API_URL', default='http://localhost:8000/api')

api_bp = Blueprint('api', __name__)

from auth import jwt_required_cookie
@api_bp.before_request
def check_jwt():
    # Rotas isentas de validação de token (healthcheck, reset do turno interno)
    if request.path in ['/api/health', '/api/shift/reset'] or request.method == 'OPTIONS':
        return None
        
    @jwt_required_cookie
    def validate():
        return None
        
    return validate()

logger = logging.getLogger(__name__)

from constants import ESTADOS_MAQUINA
from services.diagnostics import capture_golden_state, get_latest_golden_state, get_golden_state_history
from services.diagnostics_engine import run_diagnostics
from services.realtime_store import get_equipamento_realtime


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
    try:
        influx_client = current_app.extensions.get('influx_client')
        if not influx_client:
            return jsonify({'error': 'DB not initialized'}), 500

        # Query otimizada: pega o último ponto de cada equipamento
        query = "SELECT last(estado_maquina) as estado_maquina, last(velocidade_atual) as velocidade_atual, last(ordem_producao) as ordem_producao, last(sku_codigo) as sku_codigo, last(descricao) as descricao, last(cuc) as cuc, last(oee_realtime) as oee, last(formato_gramas) as formato_gramas, last(contagem_saida) as contagem_saida, last(descarte) as descarte, last(temperatura) as temperatura, last(pressao) as pressao FROM production GROUP BY \"equipment\""
        rs = influx_client.query(query)
        
        equipamentos = {}
        # rs.items() retorna ((nome_serie, tags), gerador_pontos)
        for (name, tags), points in rs.items():
            equipment_code = tags.get('equipment')
            if not equipment_code: continue
            
            # Pega o último ponto
            for point in points:
                equipamentos[equipment_code] = {
                    'medicoes': {
                        'estado_maquina': int(point.get('estado_maquina', 0) or 0),
                        'velocidade_atual': float(point.get('velocidade_atual', 0) or 0),
                        'ordem_producao': point.get('ordem_producao', 'N/A'),
                        'sku_codigo': point.get('sku_codigo', 'N/A'),
                        'descricao': point.get('descricao', 'N/A'),
                        'cuc': point.get('cuc', 'N/A'),
                        'oee': float(point.get('oee', 0) or 0),
                        'formato_gramas': float(point.get('formato_gramas', 0) or 0),
                        'contagem_saida': float(point.get('contagem_saida', 0) or 0),
                        'descarte': float(point.get('descarte', 0) or 0),
                        'temperatura': float(point.get('temperatura', 0) or 0),
                        'pressao': float(point.get('pressao', 0) or 0)
                    },
                    'timestamp': point.get('time')
                }
                break 

        return jsonify(equipamentos)

    except Exception as e:
        logger.error(f"Error getting all realtime: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api/shift/reset', methods=['POST'])
def reset_shift():
    """
    Endpoint para resetar contadores de turno.
    Chamado pelo scheduler no fim do turno.
    Body: {"equipment_code": "E01"} ou {} para todos
    """
    try:
        production_engine = current_app.extensions.get('production_engine')
        if not production_engine:
            return jsonify({'error': 'Engine not initialized'}), 500
        
        data = request.get_json() or {}
        equipment_code = data.get('equipment_code')
        
        result = production_engine.reset_shift_counters(equipment_code)
        
        if result:
            return jsonify({
                'success': True,
                'message': f'Reset de turno executado para {equipment_code or "todos equipamentos"}',
                'count': result if isinstance(result, int) else 1
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Nenhum equipamento encontrado para reset'
            }), 404
    
    except Exception as e:
        logger.error(f"Erro no reset de turno: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api/health/system', methods=['GET'])
def system_health():
    """
    Check connectivity: Flask -> InfluxDB, Flask -> Django, and Coletor Status
    """
    status = {
        'influxdb': False,
        'django': False,
        'coletor': False,
        'details': {}
    }
    
    # 1. InfluxDB (Ping)
    try:
        influx = current_app.extensions.get('influx_client')
        if influx:
            influx.ping()
            status['influxdb'] = True
    except Exception as e:
        status['details']['influxdb_error'] = str(e)

    # 2. Django (Ping)
    try:
        from decouple import config
        import requests
        django_url = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')
        # Tenta endpoint leve (ex: turnos)
        r = requests.get(f"{django_url}/turnos/?ativo=true", timeout=2)
        if r.status_code == 200:
            status['django'] = True
    except Exception as e:
        status['details']['django_error'] = str(e)

    # 3. Coletor (Check Heartbeats)
    engine = current_app.extensions.get('production_engine')
    if engine and hasattr(engine, 'heartbeats') and engine.heartbeats:
        # Se algum equipamento reportou nos ultimos 30s
        now = time.time()
        recent = [t for t in engine.heartbeats.values() if (now - t) < 30]
        if recent:
            status['coletor'] = True
        else:
             status['details']['coletor_error'] = "Sem dados nos últimos 30s"
    else:
        status['details']['coletor_error'] = "Nenhum dado recebido desde startup"

    return jsonify(status)

@api_bp.route('/api/realtime/all', methods=['GET'])
def get_all_realtime():
    """
    Retorna o ultimo estado conhecido de TODOS os equipamentos.
    Usado pela tela de Diagnosticos.
    """
    try:
        influx_client = current_app.extensions.get('influx_client')
        if not influx_client:
            return jsonify({'error': 'DB not initialized'}), 500

        # Query otimizada: pega o último ponto de cada equipamento
        query = "SELECT last(estado_maquina) as estado_maquina, last(velocidade_atual) as velocidade_atual, last(ordem_producao) as ordem_producao, last(sku_codigo) as sku_codigo, last(descricao) as descricao, last(cuc) as cuc, last(oee_realtime) as oee, last(formato_gramas) as formato_gramas, last(contagem_saida) as contagem_saida, last(descarte) as descarte, last(temperatura) as temperatura, last(pressao) as pressao FROM production WHERE time > now() - 1h GROUP BY \"equipment\""
        rs = influx_client.query(query)
        
        equipamentos = {}
        # rs.items() retorna ((nome_serie, tags), gerador_pontos)
        for (name, tags), points in rs.items():
            equipment_code = tags.get('equipment')
            if not equipment_code: continue
            
            # Pega o último ponto
            for point in points:
                equipamentos[equipment_code] = {
                    'medicoes': {
                        'estado_maquina': int(point.get('estado_maquina', 0) or 0),
                        'velocidade_atual': float(point.get('velocidade_atual', 0) or 0),
                        'ordem_producao': point.get('ordem_producao', 'N/A'),
                        'sku_codigo': point.get('sku_codigo', 'N/A'),
                        'descricao': point.get('descricao', 'N/A'),
                        'cuc': point.get('cuc', 'N/A'),
                        'oee': float(point.get('oee', 0) or 0),
                        'formato_gramas': float(point.get('formato_gramas', 0) or 0),
                        'contagem_saida': float(point.get('contagem_saida', 0) or 0),
                        'descarte': float(point.get('descarte', 0) or 0),
                        'temperatura': float(point.get('temperatura', 0) or 0),
                        'pressao': float(point.get('pressao', 0) or 0)
                    },
                    'timestamp': point.get('time')
                }
                break 

        return jsonify(equipamentos)

    except Exception as e:
        logger.error(f"Error getting all realtime: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api/linha/<linha_nome>/status', methods=['GET'])
def get_linha_status(linha_nome):
    """
    Retorna o status atual de todos os equipamentos da linha.
    """
    try:
        influx_client = current_app.extensions.get('influx_client')
        if not influx_client:
            return jsonify({'error': 'DB not initialized'}), 500

        query = f"SELECT last(estado_maquina) as estado_maquina, last(ordem_producao) as ordem_producao, last(sku_codigo) as sku_codigo, last(descricao) as descricao, last(cuc) as cuc FROM production WHERE \"line\" = '{normalize_line_name(linha_nome)}' GROUP BY \"equipment\""
        rs = influx_client.query(query)
        
        equipamentos = []
        # rs.items() retorna ((nome_serie, tags), gerador_pontos)
        for (name, tags), points in rs.items():
            equipment_name = tags.get('equipment', 'Unknown') if tags else 'Unknown'
            # Pega o último ponto (deve haver apenas um por causa do last())
            for point in points:
                # Parse timestamp and check freshness
                last_time_str = point.get('time')
                is_stale = False
                if last_time_str:
                    try:
                        # InfluxDB time is typically ISO8601 UTC
                        # Ex: 2023-10-27T10:00:00Z
                        from dateutil import parser
                        last_dt = parser.parse(last_time_str)
                        # Check age (Timezone aware)
                        now_utc = datetime.now(last_dt.tzinfo) 
                        age = (now_utc - last_dt).total_seconds()
                        
                        if age > 45: # Tolerancia de 45s (30s heartbeat + margem)
                            is_stale = True
                    except: pass

                state_val = int(point.get('estado_maquina', 0) or 0)
                if is_stale:
                    state_val = 0 # Force Offline

                equipamentos.append({
                    'nome': equipment_name,
                    'medicoes': {
                        'estado_maquina': state_val,
                        'ordem_producao': point.get('ordem_producao', 'N/A'),
                        'sku_codigo': point.get('sku_codigo', 'N/A'),
                        'descricao': point.get('descricao', 'N/A'),
                        'cuc': point.get('cuc', 'N/A')
                    }
                })
                break # Apenas o mais recente

        return jsonify({
            'equipamentos': equipamentos,
            'agregados': {
                'total_equipamentos': len(equipamentos)
            }
        })

    except Exception as e:
        logger.error(f"Error getting line status: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api/operacao/dados/<eq_code>', methods=['GET'])
def get_operacao(eq_code):
    try:
        # Tenta usar Master State (Memory)
        production_engine = current_app.extensions.get('production_engine')
        state = production_engine.get_state(eq_code) if production_engine else {}
        metrics = state.get('latest_metrics', {})
        d_influx = state.get('last_payload', {}) 

        prod_op = float(metrics.get('producao_op', 0))
        refugo_op = float(metrics.get('refugo_op_acumulado', 0))
        
        # Lógica Defensiva: Se Refugo > Produção, assume que o contador de saída é LÍQUIDO (Boas)
        # e não BRUTO (Total). Isso evita "0 Peças Boas" e OEE 0%.
        if refugo_op > prod_op:
            pecas_boas = prod_op
            # Ajusta o total produzido para ser a soma (Boas + Ruins)
            # Nota: Isso afeta apenas a visualização deste endpoint, não o banco de dados
            prod_op_total_real = prod_op + refugo_op
        else:
            pecas_boas = max(0, prod_op - refugo_op)
            prod_op_total_real = prod_op

        # Tags de contexto
        op = str(state.get('last_op_atual', 'N/A'))
        sku = str(d_influx.get('sku_codigo', 'N/A'))
        if op == 'N/A': op = str(d_influx.get('ordem_producao', 'N/A'))
        
        return jsonify({
            "equipamento": eq_code,
            "cuc": str(d_influx.get('cuc', 'N/A')),
            "ordem_producao": op,
            "sku": sku,
            "descricao": str(d_influx.get('descricao', 'Produto não identificado')),
            "formato_gramas": float(d_influx.get('formato_gramas') or d_influx.get('formato') or 0),
            "planejado_op": int(d_influx.get('planejado_op', 0) or 0),
            "produzido_op": prod_op,
            "diferenca_op": metrics.get('diferenca_op', 0),
            "toneladas_op": metrics.get('toneladas_op', 0),
            "produzido_turno": metrics.get('producao_turno', 0),
            "toneladas_turno": metrics.get('toneladas_turno', 0),
            "turno_atual": metrics.get('turno_atual_nome', 'N/A'),
            "oee": metrics.get('oee_realtime', 0),
            "pecas_boas": pecas_boas, 
            "pecas_ruins": refugo_op,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Erro Operacao {eq_code}: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api/equipamento/dados/<eq_code>', methods=['GET'])
def get_equipamento(eq_code):
    try:
        influx_client = current_app.extensions.get('influx_client')
        if not influx_client:
            return jsonify({'error': 'InfluxDB not initialized'}), 500

        # 1. Query Production Data (Last Sensor Values)
        rs = influx_client.query(f"SELECT last(*) FROM production WHERE \"equipment\" = '{eq_code}'")
        pts = list(rs.get_points())
        if not pts: return jsonify({'status': 'Sem dados'}), 200
        d = pts[0]

        # --- STALE DATA CHECK ---
        is_stale = False
        last_time_str = d.get('time')
        if last_time_str:
            try:
                from dateutil import parser
                last_dt = parser.parse(last_time_str)
                now_utc = datetime.now(last_dt.tzinfo) 
                age = (now_utc - last_dt).total_seconds()
                if age > 45: is_stale = True
            except: pass
        # ------------------------
        
        # 2. Query Machine Status (Last Event) - Source of Truth for State
        # machine_status uses tags for state, so SELECT * returns multiple series. 
        # We need the one with the latest timestamp.
        rs_status = influx_client.query(f"SELECT * FROM machine_status WHERE \"equipment\" = '{eq_code}' ORDER BY time DESC LIMIT 1")
        items = list(rs_status.items())
        
        real_state = None
        real_state_ts = None
        
        # Find the latest event across all series
        for (name, tags), points in items:
            state_val = tags.get('estado_maquina') if tags else None
            if state_val and points:
                ts = points[0]['time'] # ISO String
                if not real_state_ts or ts > real_state_ts:
                    real_state_ts = ts
                    real_state = int(state_val)

        # 3. Determine Final State
        prod_state = int(d.get('last_estado_maquina', 0) or 0)
        
        # If we have a valid event from machine_status, use it.
        # Fallback to production state if machine_status is empty
        final_state = real_state if real_state is not None else prod_state

        # REMOVED: Stale data check was incorrectly forcing state to Offline
        # Equipment state should reflect actual condition, not data freshness
        # if is_stale:
        #     final_state = 0 # Force Offline
        #     d['last_velocidade_atual'] = 0
        #     d['last_oee_realtime'] = 0

        ignore = ['time', 'last_producao_op_acumulada', 'last_producao_turno_acumulada', 
                  'last_toneladas_op', 'last_toneladas_turno', 'last_diferenca_op',
                  'last_contagem_saida', 'last_contagem_entrada', 'last_velocidade_atual', 
                  'last_estado_maquina', 'last_ordem_producao_field', 'last_sku_codigo_field', 
                  'last_descricao', 'last_planejado_op', 'last_formato_gramas', 'last_formato', 
                  'last_cuc', 'last_shift', 'last_oee_realtime', 'last_performance_realtime',
                  'last_quality_realtime', 'last_availability_realtime', 'last_refugo_op_acumulado',
                  'last_tempo_parado_turno', 'last_tempo_planejado_turno', 'last_timestamp_medicao']

        sensores = []
        for k, v in d.items():
            if k not in ignore and v is not None:
                name = k.replace('last_', '').replace('_', ' ').capitalize()
                if name.lower() not in ['estado', 'cuc', 'formato', 'ordem producao field']:
                    sensores.append({"nome": name, "valor": round(v, 2) if isinstance(v, float) else v, "unidade": ""})

        return jsonify({
            "equipamento": eq_code,
            "velocidade_atual": int(d.get('last_velocidade_atual', 0) or 0),
            "pecas_produzidas": int(d.get('last_producao_op_acumulada', 0) or 0),
            "refugos": int(d.get('last_descarte', 0) or 0),
            "estado_atual": ESTADOS_MAQUINA.get(final_state, str(final_state)),
            "oee_atual": float(d.get('last_oee_realtime', 0) or 0),
            "sensores": sensores,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Erro Equipamento {eq_code}: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api/dados/inserir', methods=['POST'])
def inserir_dados():
    try:
        data = request.json
        
        production_engine = current_app.extensions.get('production_engine')
        influx_client = current_app.extensions.get('influx_client')
        
        if not influx_client or not production_engine:
            return jsonify({'error': 'Engine/DB not initialized'}), 500

        d = request.json
        
        # Handle both single object and list of objects
        if isinstance(d, list):
            # Process each equipment in the list
            for item in d:
                try:
                    # Extract data from item
                    eq = item.get('equipamento_codigo') or item.get('equipamento')
                    line = normalize_line_name(item.get('linha_codigo', ''))
                    ts = item.get('timestamp')
                    m = item.get('medicoes', {})
                    
                    if not eq or not m:
                        logger.warning(f"Dados incompletos para equipamento: {eq}")
                        continue
                    
                    # Process this equipment (same logic as single object below)
                    is_offline = m.get('plc_offline', False) or m.get('connection_status') == 'OFFLINE'
                    if is_offline:
                        m['estado_maquina'] = 0
                        m['velocidade_atual'] = 0
                        m['oee'] = 0
                    
                    est = int(m.get('estado_maquina', 0) or 0)
                    cont = int(float(m.get('contagem_saida', 0)))
                    desc = int(float(m.get('descarte', 0)))
                    op = str(m.get('ordem_producao', 'N/A'))
                    sku = str(m.get('sku_codigo', 'N/A'))
                    plan = int(float(m.get('planejado_op', 0)))
                    fmt = float(m.get('formato_gramas') or m.get('formato') or 0)
                    cont_in = int(float(m.get('contagem_entrada', 0))) # New Input Counter
                    
                    vel_real = m.get('velocidade_atual') or m.get('velocidade_real')
                    if vel_real is not None:
                        vel_calc = int(float(vel_real))
                    else:
                        vel_calc = calc_speed_rpm(eq, cont)
                    
                    res = production_engine.processar_dados(
                        equipamento=eq,
                        op_atual=op,
                        contagem_bruta=cont,
                        descarte=desc,
                        formato_gramas=fmt,
                        planejado=plan,
                        velocidade_atual=vel_calc,
                        estado_maquina=est,
                        contagem_entrada=cont_in, # Pass Input Counter
                         extra_context={
                            'sku_codigo': sku,
                            'descricao': str(m.get('descricao', 'N/A')),
                            'cuc': str(m.get('cuc', 'N/A')),
                            'ordem_producao': op,
                            'formato_gramas': fmt
                        }
                    )
                    
                    fields = {
                        "velocidade_atual": vel_calc,
                        "estado_maquina": est,
                        "ordem_producao": op,
                        "sku_codigo": sku,
                        "contagem_saida": cont,
                        "contagem_entrada": cont_in, # Persist Input
                        "descarte": desc,
                        "planejado_op": plan,
                        "oee_realtime": res['oee_realtime'],
                        "timestamp_medicao": time.time(),
                        # Campos que faltavam (agora consistentes com o bloco Single):
                        "refugo_op_acumulado": res.get('refugo_op_acumulado', 0),
                        "producao_op_acumulada": res.get('producao_op', 0),
                        "toneladas_op": res.get('toneladas_op', 0),
                        "producao_turno_acumulada": res.get('producao_turno', 0),
                        "toneladas_turno": res.get('toneladas_turno', 0),
                        "diferenca_op": res.get('diferenca_op', 0),
                        "performance_realtime": res.get('performance_realtime', 0),
                        "quality_realtime": res.get('quality_realtime', 0),
                        "availability_realtime": res.get('availability_realtime', 0),
                        "tempo_parado_turno": res.get('tempo_parado_segundos', 0),
                        "tempo_planejado_turno": res.get('tempo_planejado_segundos', 0),
                    }
                    
                    for k, v in m.items():
                        if k not in fields:
                            if k == 'cuc': fields[k] = str(v)
                            elif k in ['formato', 'formato_gramas']: fields[k] = float(v)
                            else: fields[k] = v
                    
                    points = [{
                        "measurement": "production",
                        "tags": {
                            "line": line,
                            "equipment": eq,
                            "shift": res.get('turno_atual_nome', 'N/A'),
                            "order_id": op,
                            "sku": sku
                        },
                        "time": ts if ts else None,
                        "fields": fields
                    }]
                    
                    influx_client.write_points(points)
                    
                except Exception as e:
                    logger.error(f"Erro processando equipamento {item.get('equipamento_codigo', 'unknown')}: {e}")
            
            return jsonify({'status': 'success', 'processed': len(d)}), 200
        
        # Single object (legacy support)
        eq = d.get('equipamento_codigo') or d.get('equipamento')
        line = normalize_line_name(d.get('linha_codigo', ''))
        ts = d.get('timestamp')
        m = d.get('medicoes', {})

        if not eq or not m: return jsonify({'error': 'Dados incompletos'}), 400

        # --- OFFLINE/ERROR HANDLING ---
        # Checks if Coletor flagged this packet as Offline or PLC Error
        is_offline = m.get('plc_offline', False) or m.get('connection_status') == 'OFFLINE'
        
        if is_offline:
            # Force OFFLINE state to prevent "Ghost Production"
            m['estado_maquina'] = 0 # 0 = Offline/Outro
            m['velocidade_atual'] = 0
            m['oee'] = 0
            # Zero out calculated metrics? 
            # Production Engine usually calculates from counters. 
            # If counters are stale (same value), production is 0.
            # But speed needs explicit zeroing.
        # ------------------------------

        est = int(m.get('estado_maquina', 0) or 0)
        cont = int(float(m.get('contagem_saida', 0)))
        desc = int(float(m.get('descarte', 0)))
        op = str(m.get('ordem_producao', 'N/A'))
        sku = str(m.get('sku_codigo', 'N/A'))
        plan = int(float(m.get('planejado_op', 0)))
        fmt = float(m.get('formato_gramas') or m.get('formato') or 0)
        cont_in = int(float(m.get('contagem_entrada', 0))) # New Input Counter

        # Debug incoming keys
        # logger.info(f"Ingestion {eq}: {list(m.keys())}")

        # Prioridade: Velocidade Real > Calculada
        vel_real = m.get('velocidade_atual') or m.get('velocidade_real')
        if vel_real is not None:
            vel_calc = int(float(vel_real))
        else:
            vel_calc = calc_speed_rpm(eq, cont)

        res = production_engine.processar_dados(
            equipamento=eq,
            op_atual=op,
            contagem_bruta=cont,
            descarte=desc,
            formato_gramas=fmt,
            planejado=plan,
            velocidade_atual=vel_calc,
            estado_maquina=est,
            contagem_entrada=cont_in, # Pass Input Counter
            extra_context={
                'sku_codigo': sku,
                'descricao': str(m.get('descricao', 'N/A')),
                'cuc': str(m.get('cuc', 'N/A')),
                'ordem_producao': op,
                'formato_gramas': fmt
            }
        )

        fields = {
            "velocidade_atual": vel_calc,
            "estado_maquina": est,
            "ordem_producao_field": op,
            "sku_codigo_field": sku,
            "producao_op_acumulada": res['producao_op'],
            "contagem_entrada": cont_in, # Persist Input
            "toneladas_op": res['toneladas_op'],
            "diferenca_op": res['diferenca_op'],
            "producao_turno_acumulada": res['producao_turno'],
            "toneladas_turno": res['toneladas_turno'],
            "oee_realtime": res['oee_realtime'],
            "performance_realtime": res['performance_realtime'],
            "quality_realtime": res['quality_realtime'],
            "availability_realtime": res['availability_realtime'],
            "refugo_op_acumulado": res['refugo_op_acumulado'],
            "tempo_parado_turno": res['tempo_parado_segundos'],
            "tempo_planejado_turno": res['tempo_planejado_segundos'],
            "timestamp_medicao": time.time()
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
                "shift": res['turno_atual_nome'],
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

@api_bp.route('/api/linha/<linha_nome>/ole-realtime', methods=['GET'])
def get_ole_realtime(linha_nome):
    """
    Retorna OLE (OMAC/ISA) e dados de progresso do turno.
    OLE = ProducaoReal / ProducaoEsperadaAteAgora * 100
    """
    try:
        influx_client = current_app.extensions.get('influx_client')
        production_engine = current_app.extensions.get('production_engine')
        
        if not influx_client or not production_engine:
            return jsonify({'error': 'Engine/DB not initialized'}), 500

        # 1. Busca Produção Real (Toneladas) USANDO O ÚLTIMO EQUIPAMENTO DA LINHA
        # Busca config da linha para saber ordem
        producao_real_ton = 0.0
        taxa_instantanea = 0.0 # Ton/h
        
        try:
             # Busca ID da Linha primeiro para pegar equipamentos ordenados
            import requests
            from decouple import config
            DJANGO_API_URL = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')
            
            resp_linha = requests.get(f"{DJANGO_API_URL}/linhas/?codigo={linha_nome}", timeout=2)
            l_id = None
            if resp_linha.ok:
                data_linha = resp_linha.json()
                res_l = data_linha.get('results', data_linha)
                if res_l:
                    l_id = res_l[0]['id']
                else:
                    # Fallback: match por nome normalizado
                    resp_all = requests.get(f"{DJANGO_API_URL}/linhas/", timeout=2)
                    if resp_all.ok:
                        all_lines = resp_all.json().get('results', [])
                        target_norm = normalize_line_name(linha_nome)
                        for lx in all_lines:
                            if normalize_line_name(lx.get('codigo', '')) == target_norm or normalize_line_name(lx.get('nome', '')) == target_norm:
                                l_id = lx['id']
                                break
            
            if l_id:
                    # Busca equipamentos ordenados
                    resp_eq = requests.get(f"{DJANGO_API_URL}/equipamentos/?linha={l_id}", timeout=2)
                    if resp_eq.ok:
                        data_eq = resp_eq.json()
                        eqs = data_eq.get('results', data_eq)
                        
                        if eqs:
                            # Ordena para identificar primeiro e último
                            eqs.sort(key=lambda x: x.get('ordem_na_linha', 0))
                            primeiro_eq = eqs[0]['codigo']   # Primeiro (velocidade)
                            ultimo_eq = eqs[-1]['codigo']     # Último (produção)
                            
                            # Tenta pegar PRODUÇÃO do ÚLTIMO equipamento (produto final)
                            if production_engine:
                                st_ultimo = production_engine.get_state(ultimo_eq)
                                met_ultimo = st_ultimo.get('latest_metrics', {})
                                producao_real_ton = met_ultimo.get('toneladas_turno', 0.0)
                                
                                logger.info(f"DEBUG PRODUCAO: ultimo_eq={ultimo_eq}, producao={producao_real_ton}t")
                            
                            # Tenta pegar VELOCIDADE do PRIMEIRO equipamento (dita ritmo)
                            if production_engine:
                                st_primeiro = production_engine.get_state(primeiro_eq)
                                met_primeiro = st_primeiro.get('latest_metrics', {})
                                vel = met_primeiro.get('velocidade_atual', 0)
                                fmt = met_primeiro.get('formato_gramas', 0)
                                if fmt == 0: fmt = st_primeiro.get('last_payload', {}).get('formato_gramas', 0)
                                
                                logger.info(f"DEBUG VAZAO: primeiro_eq={primeiro_eq}, vel={vel}, fmt={fmt}")
                                
                                # Ton/h = (PPM * 60 * Gramas) / 1M
                                if fmt > 0 and vel > 0:
                                    taxa_instantanea = (vel * 60 * fmt) / 1_000_000.0
                                    logger.info(f"DEBUG VAZAO CALC: ({vel} * 60 * {fmt}) / 1M = {taxa_instantanea} t/h")
                            
                            # Fallback Influx se Engine zerado (e Influx tiver histórico)
                            # NOVO: Tenta penúltimo equipamento antes de usar MAX de todos
                            if producao_real_ton == 0:
                                logger.warning(f"⚠️ Último equipamento ({ultimo_eq}) sem dados, tentando penúltimo...")
                                
                                # Tenta penúltimo equipamento
                                if len(eqs) > 1:
                                    penultimo_eq = eqs[-2]['codigo']
                                    st_penultimo = production_engine.get_state(penultimo_eq)
                                    met_penultimo = st_penultimo.get('latest_metrics', {})
                                    producao_real_ton = met_penultimo.get('toneladas_turno', 0.0)
                                    
                                    if producao_real_ton > 0:
                                        logger.info(f"✓ Usando penúltimo equipamento ({penultimo_eq}): {producao_real_ton}t")
                                
                                # Se ainda zerado, busca no InfluxDB
                                if producao_real_ton == 0:
                                    q_last = f"SELECT last(toneladas_turno), last(velocidade_atual), last(formato_gramas) FROM production WHERE \"equipment\" = '{ultimo_eq}'"
                                    rs_last = influx_client.query(q_last)
                                    pts_last = list(rs_last.get_points())
                                    if pts_last:
                                        producao_real_ton = float(pts_last[0].get('last', 0) or 0)
                                        vel_i = float(pts_last[0].get('last_1', 0) or 0)
                                        fmt_i = float(pts_last[0].get('last_2', 0) or 0)
                                        if taxa_instantanea == 0 and fmt_i > 0:
                                             taxa_instantanea = (vel_i * 60 * fmt_i) / 1_000_000.0
                                        
                                        if producao_real_ton > 0:
                                            logger.info(f"✓ Recuperado do InfluxDB ({ultimo_eq}): {producao_real_ton}t")

        except Exception as e:
            logger.error(f"Erro buscando ultimo eq: {e}")

        # Fallback se falhar (mantem logica antiga de MAX)
        if producao_real_ton == 0:
            query = f"SELECT last(toneladas_turno) FROM production WHERE \"line\" = '{normalize_line_name(linha_nome)}' GROUP BY \"equipment\""
            logger.info(f"DEBUG OLE: Fallback Query: {query}")
            rs = influx_client.query(query)
            points = list(rs.get_points())
            if points:
                producao_real_ton = max([float(p['last']) for p in points if p['last'] is not None], default=0.0)

        logger.info(f"DEBUG OLE: Real={producao_real_ton}")

        # 2. Busca Meta do Turno (Django) e Calcula Tempo
        meta_toneladas = 0.0
        tempo_decorrido = 0
        tempo_total_turno = 0
        
        # Dados do Turno Atual
        turno_info = production_engine.shift_manager.get_turno_info()
        
        # Busca ID da Linha (Redundante mas mantendo estrutura para pegar calendario)
        # Otimizacao: se ja pegamos l_id acima, reutilizar. Mas o scopo do try acima é local.
        # Repetindo logica de meta com robustez
        try:
              resp_linha = requests.get(f"{DJANGO_API_URL}/linhas/?codigo={linha_nome}", timeout=2)
              linha_id = None  # Inicializa
              if resp_linha.status_code == 200:
                data_linha = resp_linha.json()
                results_linha = data_linha.get('results', data_linha)
                if results_linha:
                    linha_id = results_linha[0]['id']
                else:
                    # Fallback: Buscar todas linhas e fazer match normalizado
                    resp_all = requests.get(f"{DJANGO_API_URL}/linhas/", timeout=2)
                    if resp_all.ok:
                        all_lines = resp_all.json().get('results', [])
                        target_norm = normalize_line_name(linha_nome)
                        for lx in all_lines:
                            if normalize_line_name(lx.get('codigo', '')) == target_norm or normalize_line_name(lx.get('nome', '')) == target_norm:
                                linha_id = lx['id']
                                break
              
              # Busca Calendário (somente se linha_id foi obtido)
              if linha_id:
                    if turno_info and 'inicio_timestamp' in turno_info:
                         dt_inicio = datetime.fromtimestamp(turno_info['inicio_timestamp'])
                         query_date = dt_inicio.strftime('%Y-%m-%d')
                    else:
                         query_date = datetime.now().strftime('%Y-%m-%d')
                         
                    resp_cal = requests.get(f"{DJANGO_API_URL}/calendario/?linha_id={linha_id}&data={query_date}", timeout=2)
                    
                    if resp_cal.status_code == 200:
                        data_cal = resp_cal.json()
                        results_cal = data_cal.get('results', data_cal)
                        if results_cal:
                            for entry in results_cal:
                                if entry.get('programado') and entry.get('meta_producao_turno'):
                                    val = float(entry.get('meta_producao_turno'))
                                    if val > 1000: val /= 1000.0
                                    
                                    # DEBUG SHIFT MATCHING
                                    f_shift = turno_info.get('nome') if turno_info else 'None'
                                    d_shift = entry.get('turno_nome')
                                    debug_shift_info = f"Flask: '{f_shift}' vs Django: '{d_shift}' | Date: {query_date}"
                                    logger.info(f"DEBUG CALENDAR: {debug_shift_info}")
                                    
                                    if turno_info and entry.get('turno_nome') == turno_info.get('nome'):
                                        meta_toneladas = val
                                        break
                                    if meta_toneladas == 0:
                                        meta_toneladas = val
        except: pass

        # 3. Calcula Tempo Decorrido e Total
        if turno_info:
            now = datetime.now()
            inicio = datetime.combine(now.date(), turno_info['inicio'])
            fim = datetime.combine(now.date(), turno_info['fim'])
            
            # Ajuste para virada de dia
            if turno_info['inicio'] > turno_info['fim']:
                if now.time() < turno_info['inicio']:
                    inicio -= timedelta(days=1)
                else:
                    fim += timedelta(days=1)
            
            tempo_total_turno = (fim - inicio).total_seconds()
            tempo_decorrido = (now - inicio).total_seconds()
            
            # Cap no tempo decorrido
            if tempo_decorrido > tempo_total_turno:
                tempo_decorrido = tempo_total_turno
        
        # 3.5 Calcula Equipamentos Online
        equipamentos_online = 0
        equipamentos_total = 0
        
        # Tentativa 1: Production Engine (Memória - Sincronizado com Header)
        engine_counted = False
        try:
             # Precisamos da lista de equipamentos. Tenta reutilizar ou busca.
             if 'eqs' not in locals() or not eqs:
                  # Busca rápida
                  if 'l_id' in locals():
                       resp_eq_chk = requests.get(f"{DJANGO_API_URL}/equipamentos/?linha={l_id}", timeout=2)
                       if resp_eq_chk.ok:
                            d_eq = resp_eq_chk.json()
                            eqs = d_eq.get('results', d_eq)
                  else:
                       # Busca ID
                       r_l = requests.get(f"{DJANGO_API_URL}/linhas/?codigo={linha_nome}", timeout=1)
                       if r_l.ok:
                           dl = r_l.json()
                           res = dl.get('results', dl)
                           if res:
                               lid = res[0]['id']
                               req = requests.get(f"{DJANGO_API_URL}/equipamentos/?linha={lid}", timeout=1)
                               if req.ok:
                                   de = req.json()
                                   eqs = de.get('results', de)
             
             if 'eqs' in locals() and eqs and production_engine:
                 equipamentos_total = len(eqs)
                 for eq_item in eqs:
                     cod = eq_item['codigo']
                     st = production_engine.get_state(cod)
                     # Heartbeat recente (2 min) define ONLINE, independente do estado
                     ts = st.get('last_timestamp', 0)
                     if (time.time() - ts < 120):
                         equipamentos_online += 1
                 engine_counted = True        
        except Exception as e:
             logger.error(f"Erro contagem engine: {e}")

        # Tentativa 2: Influx (Fallback)
        if not engine_counted:
            try:
                 # Query otimizada: Apenas Heartbeat check (tem dados recentes?)
                 q_online = f"SELECT count(estado_maquina) AS heartbeat FROM production WHERE \"line\" = '{normalize_line_name(linha_nome)}' AND time > now() - 2m GROUP BY \"equipment\""
                 rs_online = influx_client.query(q_online)
                 count_total = 0
                 count_on = 0
                 for (k, tags), pts in rs_online.items():
                     count_total += 1
                     # Se retornou ponto, está online
                     if pts: count_on += 1
                 
                 equipamentos_total = count_total
                 equipamentos_online = count_on
            except Exception as e:
                 logger.error(f"Erro contagem online Influx: {e}")

        # 4. Cálculo OLE (OMAC) e DYNAMIC METRICS
        producao_esperada = 0.0
        ole = 0.0
        projecao = 0.0
        ritmo_necessario = 0.0

        if meta_toneladas > 0 and tempo_total_turno > 0:
            logger.info(f"DEBUG ESPERADO: Meta={meta_toneladas}, Decorrido={tempo_decorrido}, Total={tempo_total_turno}")
            producao_esperada = meta_toneladas * (tempo_decorrido / tempo_total_turno)
            
            if producao_esperada > 0:
                ole = (producao_real_ton / producao_esperada) * 100.0
            
            # --- NOVAS FÓRMULAS DINÂMICAS ---
            tempo_restante_horas = (tempo_total_turno - tempo_decorrido) / 3600.0
            
            logger.info(f"DEBUG PROJECAO: Real={producao_real_ton}, Taxa={taxa_instantanea}, Restante={tempo_restante_horas}, TotalTurno={tempo_total_turno}, Decorrido={tempo_decorrido}")

            # Projeção Dinâmica: Real + (Rate * Remaining)
            if tempo_restante_horas > 0:
                projecao = producao_real_ton + (taxa_instantanea * tempo_restante_horas)
                logger.info(f"DEBUG PROJECAO CALC: {producao_real_ton} + ({taxa_instantanea} * {tempo_restante_horas}) = {projecao}")
            else:
                projecao = producao_real_ton # Turno acabou
                logger.info(f"DEBUG PROJECAO END: {projecao}")

            # GARANTIA: Projeção nunca pode ser menor que Real
            if projecao < producao_real_ton:
                logger.warning(f"CORRECAO PROJECAO: {projecao} < {producao_real_ton}. Ajustando para Real.")
                projecao = producao_real_ton
                
            # Ritmo Necessário Dinâmico: (Meta - Real) / Remaining
            saldo_necessario = meta_toneladas - producao_real_ton
            if tempo_restante_horas > 0:
                ritmo_necessario = max(0, saldo_necessario / tempo_restante_horas)
            else:
                ritmo_necessario = 0 # Turno acabou (ou impossível)

        # 5. Busca Contexto (SKU, OP, Descrição) - Pega o mais recente da linha
        line_context = {
            'sku_codigo': 'N/A',
            'ordem_producao': 'N/A',
            'descricao': 'N/A',
            'cuc': 'N/A',
            'formato_gramas': 0
        }
        try:
             # Prioridade: Engine (via primeiro_eq que tem os dados de contexto)
             if 'primeiro_eq' in locals() and primeiro_eq and production_engine:
                 st = production_engine.get_state(primeiro_eq)
                 meta = st.get('latest_metrics', {})
                 ctx = st.get('last_payload', {})
                 
                 if ctx:
                     line_context['sku_codigo'] = str(ctx.get('sku', ctx.get('sku_codigo', line_context['sku_codigo'])))
                     line_context['ordem_producao'] = str(ctx.get('ordem_producao', line_context['ordem_producao']))
                     line_context['descricao'] = str(ctx.get('descricao', line_context['descricao']))
                     line_context['cuc'] = str(ctx.get('cuc', line_context['cuc']))
                     line_context['formato_gramas'] = float(ctx.get('formato_gramas', 0) or meta.get('formato_gramas', 0) or 0)
                     
                     logger.info(f"DEBUG CONTEXT: primeiro_eq={primeiro_eq}, OP={line_context['ordem_producao']}, SKU={line_context['sku_codigo']}, CUC={line_context['cuc']}, Desc={line_context['descricao']}")
                 else:
                     logger.warning(f"DEBUG CONTEXT: primeiro_eq={primeiro_eq} last_payload vazio")
             
             # Fallback Influx se dados estiverem faltando ("N/A")
             if line_context['sku_codigo'] == 'N/A':
                 # FIX: Tenta pegar contexto do PRIMEIRO equipamento (Lider) especificamente
                 # Se buscar pela linha inteira ("line"='...'), pode pegar o ultimo ponto de um equipamento final (ex: Encaixotadora)
                 # que ainda nao recebeu o SKU e está N/A.
                 target_clause = f"\"line\" = '{normalize_line_name(linha_nome)}'"
                 if 'primeiro_eq' in locals() and primeiro_eq:
                      target_clause = f"\"equipment\" = '{primeiro_eq}'"
                 
                 q_ctx = f"SELECT last(sku_codigo_field) as sku_1, last(sku) as sku_2, last(ordem_producao_field) as op_1, last(order_id) as op_2, last(descricao) as descricao_val, last(produto) as prod, last(cuc) as cuc_val, last(formato_gramas) as fmt FROM production WHERE {target_clause}"
                 
                 rs_ctx = influx_client.query(q_ctx)
                 
                 pts = list(rs_ctx.get_points())
                 if pts:
                     best_point = pts[0]
                     
                     line_context['sku_codigo'] = best_point.get('sku_1') or best_point.get('sku_2') or 'N/A'
                     line_context['ordem_producao'] = best_point.get('op_1') or best_point.get('op_2') or 'N/A'
                     line_context['descricao'] = best_point.get('descricao_val') or best_point.get('prod') or 'N/A'
                     line_context['cuc'] = best_point.get('cuc') or 'N/A'
                     line_context['formato_gramas'] = float(best_point.get('fmt') or 0)

        except Exception as e:
             logger.error(f"Erro context line: {e}")

        # Fallback Final: Planner (Django) - Se ainda N/A
        if line_context['sku_codigo'] in ['N/A', None] or line_context['sku_codigo'] == 'None':
             try:
                 # Precisamos do ID da linha
                 l_id_target = locals().get('l_id') or locals().get('lid')
                 if not l_id_target:
                      # 1. Busca Direta
                       r_l = requests.get(f"{DJANGO_API_URL}/linhas/?codigo={linha_nome}", timeout=1)
                       if r_l.ok:
                           dl = r_l.json()
                           res = dl.get('results', dl)
                           if res: 
                                l_id_target = res[0]['id']
                           else:
                                # 2. Busca Todos (Fallback de Nome)
                                r_all = requests.get(f"{DJANGO_API_URL}/linhas/", timeout=1)
                                if r_all.ok:
                                     d_all = r_all.json()
                                     all_lines = d_all.get('results', d_all)
                                     target_norm = normalize_line_name(linha_nome) # L01
                                     for lx in all_lines:
                                          if normalize_line_name(lx['codigo']) == target_norm or normalize_line_name(lx['nome']) == target_norm:
                                               l_id_target = lx['id']
                                               break

                 if l_id_target:
                      r_plan = requests.get(f"{DJANGO_API_URL}/linhas/{l_id_target}/active_op/", timeout=2)
                      if r_plan.ok:
                          d_plan = r_plan.json()
                          line_context['sku_codigo'] = str(d_plan.get('sku_codigo', 'N/A'))
                          line_context['ordem_producao'] = str(d_plan.get('ordem_producao', 'N/A'))
                          line_context['descricao'] = str(d_plan.get('descricao', 'N/A'))
             except Exception as e:
                 logger.error(f"Erro fallback planner: {e}")

        return jsonify({
            'ole': round(ole, 1),
            'producao_real': round(producao_real_ton, 3),
            'producao_esperada': round(producao_esperada, 3),
            'projecao': round(projecao, 3),
            'ritmo_necessario': round(ritmo_necessario, 1),
            'taxa_instantanea': round(taxa_instantanea, 1),
            'meta_turno': round(meta_toneladas, 1),
            'tempo_decorrido_perc': round((tempo_decorrido / tempo_total_turno * 100) if tempo_total_turno > 0 else 0, 1),
            'equipamentos_online': equipamentos_online,
            'equipamentos_total': equipamentos_total,
            # Context Data
            'sku': line_context['sku_codigo'],
            'op': line_context['ordem_producao'],
            'descricao': line_context['descricao'],
            'cuc': line_context['cuc'],
            'formato': line_context['formato_gramas'],
            'debug_meta': str(debug_shift_info) if 'debug_shift_info' in locals() else 'No Info'
        })

    except Exception as e:
        logger.error(f"Erro OLE Realtime: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api/linha/<linha_nome>/overview-status', methods=['GET'])
def get_linha_overview_status(linha_nome):
    """
    Retorna o status consolidado da linha para o Header.
    Prioridade: Produzindo > Falha > Setup/Manutenção > Parada > Offline
    Lógica Híbrida: Eventos (Machine Status) > Sensores (Production)
    """
    try:
        influx_client = current_app.extensions.get('influx_client')
        if not influx_client: 
            return jsonify({'status': 'Offline', 'reason': 'DB Error'}), 500

        # Busca ultimo evento de status de cada serie (estado)
        # machine_status usa tags, então buscamos tudo e filtramos em memória pelo timestamp mais recente
        query = f"SELECT * FROM machine_status WHERE \"line\" = '{normalize_line_name(linha_nome)}' ORDER BY time DESC LIMIT 1"
        rs = influx_client.query(query)
        items = list(rs.items())
        
        last_states = {}
        
        for (name, tags), points in items:
            if not tags: continue
            eq = tags.get('equipment')
            state_val = tags.get('estado_maquina')
            if not eq or not state_val: continue
            
            for p in points:
                ts = p['time']
                if eq not in last_states:
                    last_states[eq] = {'time': ts, 'state': int(state_val)}
                else:
                    if ts > last_states[eq]['time']:
                        last_states[eq] = {'time': ts, 'state': int(state_val)}
        
        # Fallback: Se machine_status vazio (ex: sistema novo), tenta production
        if not last_states:
             query_prod = f"SELECT last(estado_maquina) as estado FROM production WHERE \"line\" = '{normalize_line_name(linha_nome)}' GROUP BY \"equipment\""
             rs_prod = influx_client.query(query_prod)
             for (name, tags), points in rs_prod.items():
                 for p in points:
                     last_states[tags['equipment']] = {'state': int(p.get('estado', 0) or 0)}
                     
        if not last_states:
             return jsonify({'status': 'Offline', 'reason': 'No Data'}), 200

        estados = [d['state'] for d in last_states.values()]
        
        final_status = 'Parada'
        
        # Prioridade de Status Global
        if any(e == 4 for e in estados):
            final_status = 'Falha/Quebra'
        elif any(e in [1, 11] for e in estados):
            final_status = 'Produzindo'
        elif any(e in [5, 6, 8] for e in estados):
            final_status = 'Manutenção/Setup'
        elif any(e == 2 for e in estados):
            final_status = 'Aguardando'
        elif any(e == 0 for e in estados):
            final_status = 'Parada'
        
        return jsonify({'status': final_status})

    except Exception as e:
        logger.error(f"Erro Overview Status: {e}")
        return jsonify({'status': 'Offline', 'error': str(e)}), 500

@api_bp.route('/api/linha/<linha_nome>/kpis', methods=['GET'])
def get_linha_kpis(linha_nome):
    """
    Retorna KPIs agregados da linha e gargalo.
    REFACTORED: Usa production_engine para consistência com Home Page.
    """
    try:
        production_engine = current_app.extensions.get('production_engine')
        
        linha_norm = normalize_line_name(linha_nome)
        
        # 1. Busca Equipamentos da Linha (Django)
        try:
            url = f"{DJANGO_API_URL}/equipamentos/?linha__codigo={linha_norm}"
            resp = requests.get(url, timeout=2)
            if resp.ok:
                data = resp.json()
                equipamentos = data.get('results', data)
            else:
                equipamentos = []
        except:
            equipamentos = []

        total_avail = 0.0
        total_perf = 0.0
        total_qual = 0.0
        count = 0
        
        gargalo_nome = 'N/A'
        gargalo_oee = 100.0

        for eq in equipamentos:
            eq_code = eq.get('codigo')
            # Busca estado do Engine (Mesma fonte da Home)
            state = production_engine.get_state(eq_code) if production_engine else {}
            metrics = state.get('latest_metrics', {})
            
            # OEE Components
            a = float(metrics.get('availability_realtime', 0))
            p = float(metrics.get('performance_realtime', 0))
            q = float(metrics.get('quality_realtime', 0))
            if q == 0 and metrics.get('producao_op', 0) > 0: q = 100.0
            
            oee = metrics.get('oee_realtime', 0)
            
            total_avail += a
            total_perf += p
            total_qual += q
            count += 1
            
            # Gargalo Logic: Menor OEE
            if count == 1 or oee < gargalo_oee:
                gargalo_oee = oee
                gargalo_nome = eq.get('nome', eq_code)

        if count > 0:
            avg_avail = total_avail / count
            avg_perf = total_perf / count
            avg_qual = total_qual / count
        else:
            avg_avail = 0.0
            avg_perf = 0.0
            avg_qual = 0.0

        # Tentar buscar metricas de descarte persistidas
        total_descarte_tons = 0.0
        perc_descarte = 0.0
        
        try:
            from influx_data_provider import get_client as get_influx_client
            client = current_app.extensions.get('influx_client')
            if client:
                # Query ultimo ponto da measurement line_metrics
                # Ajuste: busca por type='waste_agg'
                q_waste = "SELECT last(waste_tons), last(waste_percent) FROM line_metrics WHERE \"type\"='waste_agg'" 
                rs_waste = client.query(q_waste)
                pts_waste = list(rs_waste.get_points())
                if pts_waste:
                    total_descarte_tons = float(pts_waste[0].get('last', 0))
                    perc_descarte = float(pts_waste[0].get('last_1', 0))
        except Exception as e:
            logger.error(f"Erro fetch waste metrics: {e}")

        return jsonify({
            'kpis': {
                'disponibilidade': round(avg_avail, 1),
                'performance': round(avg_perf, 1),
                'qualidade': round(avg_qual, 1),
                'descarte_ton': round(total_descarte_tons, 3),     # Novo field
                'descarte_percent': round(perc_descarte, 2)        # Novo field
            },
            'gargalo': {
                'nome': gargalo_nome,
                'oee': round(gargalo_oee, 1)
            }
        })

    except Exception as e:
        logger.error(f"Erro KPIs: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api/linha/<linha_nome>/timeline', methods=['GET'])
def get_linha_timeline(linha_nome):
    """
    Retorna timeline agregada (mockada ou real).
    Por enquanto retorna estrutura vazia ou mockada para o frontend.
    """
    # TODO: Implementar busca real de machine_status
    return jsonify({
        'events': [] 
    })

@api_bp.route('/api/linha/<linha_nome>/upstream', methods=['GET'])
def get_linha_upstream(linha_nome):
    return jsonify([
        {'name': 'Silo 04', 'status': 'Normal', 'detail': 'Nível 78%'},
        {'name': 'Rosca 02', 'status': 'Warning', 'detail': 'Vibração Alta'},
        {'name': 'Misturador 01', 'status': 'Normal', 'detail': 'Disponível'}
    ])

@api_bp.route('/api/linha/<linha_nome>/downstream', methods=['GET'])
def get_linha_downstream(linha_nome):
    return jsonify([
        {'name': 'Armazém', 'percentage': 84},
        {'name': 'WIP', 'percentage': 12},
        {'name': 'Reprocesso', 'percentage': 4}
    ])

@api_bp.route('/api/system/refresh-shifts', methods=['POST'])
def refresh_shifts():
    production_engine = current_app.extensions.get('production_engine')
    if production_engine:
        if production_engine.recarregar_configuracoes():
            return jsonify({'status': 'ok'}), 200
    return jsonify({'error': 'fail'}), 500

@api_bp.route('/api/health', methods=['GET'])
def health(): return jsonify({'status': 'ok'})

@api_bp.route('/api/fabrica/mapa', methods=['GET'])
def get_factory_map_route():
    """
    Rota dedicada para o mapa do chão de fábrica.
    Retorna status (1o equipamento), OLE e layout.
    """
    try:
        from factory_kpis_engine import get_factory_map_data
        data = get_factory_map_data()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Erro na rota de mapa: {e}")
        return jsonify([]), 500
@api_bp.route('/api/equipamento/<codigo>/historico-detalhado', methods=['GET'])
def get_equipamento_historico_detalhado(codigo):
    """
    Retorna histórico detalhado e AGREGADO do equipamento para a aba Histórico.
    Suporta filtros por período: hora, turno, dia, semana.
    """
    try:
        influx_client = current_app.extensions.get('influx_client')
        if not influx_client:
            return jsonify({'error': 'DB not initialized'}), 500

        # Parâmetros avançados
        start_param = request.args.get('start') # ISO format
        end_param = request.args.get('end')     # ISO format
        interval_param = request.args.get('interval') # 1h, 8h, 1d, total

        # Parâmetros legados (mantidos para compatibilidade)
        periodo = request.args.get('period', 'hora') 
        data_ref = request.args.get('date')

        start_time = None
        # Lógica de Tempo: Prioriza start/end, fallback para period/date
        if start_param and end_param:
            try:
                # Tenta analisar ISO format (pode vir do JS como YYYY-MM-DDTHH:mm:ss.sssZ)
                start_time = datetime.fromisoformat(start_param.replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(end_param.replace('Z', '+00:00'))
            except ValueError:
                # Fallback simples se falhar parse
                start_time = datetime.now() - timedelta(hours=24)
                end_time = datetime.now()
        else:
            # Lógica Legada
            now = datetime.now()
            if data_ref:
                try:
                    dt_ref = datetime.strptime(data_ref, '%Y-%m-%d')
                    start_time = dt_ref.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_time = dt_ref.replace(hour=23, minute=59, second=59, microsecond=999999)
                except:
                    start_time = now - timedelta(hours=24)
                    end_time = now
            else:
                start_time = now - timedelta(hours=24)
                end_time = now
                
                # Ajustes específicos do modo legado
                if periodo == 'dia':
                    start_time = now - timedelta(days=7)
                elif periodo == 'semana':
                    start_time = now - timedelta(weeks=4)
                elif periodo == 'mes':
                    start_time = now - timedelta(days=30)
                elif periodo == 'turno':
                    start_time = now - timedelta(hours=48)

        # Lógica de Agrupamento
        if interval_param:
            if interval_param == 'total' or interval_param == 'consolidado':
                group_by = None # Sem agrupamento por tempo (agregação total)
            else:
                group_by = interval_param
        else:
            # Fallback legado
            if periodo == 'dia' or periodo == 'mes':
                group_by = "1d"
            elif periodo == 'semana':
                group_by = "1w"
            elif periodo == 'turno':
                group_by = "8h"
            else:
                group_by = "1h"

        # Formata para Influx
        s_str = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
        e_str = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')

        # Query Agregada
        # Usa spread() para contadores (max - min) e mean() para gauges
        query = f"""
            SELECT 
                spread(contagem_saida) as producao, 
                spread(contagem_entrada) as entrada,
                spread(descarte) as descarte,
                mean(velocidade_atual) as velocidade_media,
                mean(oee_realtime) as oee_medio,
                mean(disponibilidade) as disp_media,
                mean(performance) as perf_media,
                mean(qualidade) as qual_media,
                last(*)
            FROM production 
            WHERE "equipment" = '{codigo}' 
            AND time >= '{s_str}' AND time <= '{e_str}' 
            GROUP BY time({group_by}) fill(0)
        """
        
        rs = influx_client.query(query)
        points = list(rs.get_points())
        
        historico = []
        for p in points:
            # Ignora pontos zerados se desejar, ou mantém para mostrar buracos
            # Se producao e OEE forem 0, provavelmente estava parado ou sem dados
            if p['producao'] == 0 and p['oee_medio'] == 0:
                continue

            item = {
                'data_hora': p['time'],
                'producao': int(p['producao']),
                'entrada': int(p['entrada']),
                'descarte': int(p['descarte']),
                'velocidade_media': float(p['velocidade_media']),
                'oee': float(p['oee_medio']),
                'disponibilidade': float(p['disp_media']),
                'performance': float(p['perf_media']),
                'qualidade': float(p['qual_media'])
            }
            
            # Add dynamic fields (last_*)
            for k, v in p.items():
                if k.startswith('last_'):
                    # Clean key name
                    clean_key = k.replace('last_', '')
                    # Skip fields we already handled explicitly
                    if clean_key in ['velocidade_atual', 'oee_realtime', 'disponibilidade', 'performance', 'qualidade', 'contagem_saida', 'contagem_entrada', 'descarte']:
                        continue
                    item[clean_key] = v
            
            historico.append(item)

        # Ordena decrescente (mais recente primeiro) - REMOVIDO para corrigir gráfico
        # historico.reverse()

        return jsonify({
            'equipamento': codigo,
            'periodo': periodo,
            'historico': historico
        })

    except Exception as e:
        logger.error(f"Error getting equipment history: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api/diagnostics/capture/<equipamento_codigo>', methods=['POST'])
def capture_golden_state_endpoint(equipamento_codigo):
    """
    Captura o estado atual como Golden State.
    """
    try:
        profile = capture_golden_state(equipamento_codigo, capture_type='MANUAL')
        if profile:
            return jsonify({
                'status': 'success',
                'message': 'Golden State captured successfully',
                'profile': profile
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to capture Golden State (no data?)'
            }), 400
    except Exception as e:
        logger.error(f"Error capturing Golden State: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api_bp.route('/api/diagnostics/alerts/<equipamento_codigo>', methods=['GET'])
def get_diagnostics_alerts(equipamento_codigo):
    """
    Retorna alertas de diagnóstico para o equipamento.
    """
    try:
        realtime_data = get_equipamento_realtime(equipamento_codigo)
        alerts = run_diagnostics(equipamento_codigo, realtime_data)
        golden_state = get_latest_golden_state(equipamento_codigo)
        
        # Check for SKU filter
        sku_filter = request.args.get('sku')
        
        # Smart Filter: Use current running SKU if requested
        if request.args.get('current_sku_only') == 'true':
            # realtime_data is { 'medicoes': { ... }, 'timestamp': ... }
            med = realtime_data.get('medicoes', {})
            # Keys in medicoes have 'last_' stripped by realtime_store.py logic
            # So 'last_sku_codigo_field' becomes 'sku_codigo_field'
            sku_filter = med.get('sku_codigo_field') or med.get('sku_codigo') or med.get('sku')
        
        history = get_golden_state_history(equipamento_codigo, sku=sku_filter)
        
        return jsonify({
            'status': 'success',
            'alerts': alerts,
            'golden_state': golden_state,
            'golden_state_history': history
        })
    except Exception as e:
        logger.error(f"Error getting diagnostics: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500



@api_bp.route('/api/linha/<linha_nome>/historico', methods=['GET'])
def get_linha_historico(linha_nome):
    """
    Retorna histórico agregado da linha (Produção Total, OEE Médio, etc.)
    respeitando filtros de data.
    """
    try:
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        interval = request.args.get('interval', '1h')
        influx_client = current_app.extensions.get('influx_client')

        if not start_str or not end_str:
            # Default last 24h
            end_dt = datetime.utcnow()
            start_dt = end_dt - timedelta(hours=24)
            s_str = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            e_str = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            # Validate format
            try:
                # Se vier com timezone Z
                if start_str.endswith('Z'):
                    s_dt = datetime.strptime(start_str, '%Y-%m-%dT%H:%M:%S.%fZ')
                else:
                    s_dt = datetime.fromisoformat(start_str)
                
                if end_str.endswith('Z'):
                    e_dt = datetime.strptime(end_str, '%Y-%m-%dT%H:%M:%S.%fZ')
                else:
                    e_dt = datetime.fromisoformat(end_str)
                    
                s_str = s_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                e_str = e_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            except:
                # Fallback simple
                s_str = start_str
                e_str = end_str

        # Adjust interval for Influx
        group_by = interval
        if interval == 'total':
            group_by = '1000d' # Hack to group all

        # Query: Sum of production across all equipment, Mean of OEE across all equipment
        # InfluxQL subquery
        query = f"""
            SELECT 
                sum(producao) as producao_total,
                mean(oee) as oee_medio
            FROM (
                SELECT 
                    spread(contagem_saida) as producao,
                    mean(oee_realtime) as oee
                FROM production 
                WHERE "line" = '{normalize_line_name(linha_nome)}' 
                AND time >= '{s_str}' AND time <= '{e_str}' 
                GROUP BY time({group_by}), "equipment"
            ) 
            GROUP BY time({group_by}) fill(0)
        """
        
        rs = influx_client.query(query)
        points = list(rs.get_points())
        
        historico = []
        for p in points:
            historico.append({
                'data_hora': p['time'],
                'producao_total': int(p['producao_total'] or 0),
                'oee_medio': float(p['oee_medio'] or 0)
            })

        return jsonify({
            'linha': linha_nome,
            'historico': historico
        })

    except Exception as e:
        logger.error(f"Erro ao buscar histórico da linha: {e}")
        return jsonify({'error': str(e)}), 500


# ==========================================================================================
# RESTORED MISSING REALTIME ENDPOINTS (CRITICAL FOR UI)
# ==========================================================================================

@api_bp.route('/api/equipamento/dados/<codigo>', methods=['GET'])
def get_equipamento_dados(codigo):
    """
    Retorna os dados em tempo real de um equipamento específico.
    Usado pelo Home.tsx e LineDeepView.tsx
    """
    try:
        # Tenta obter do cache/store primeiro
        rt = get_equipamento_realtime(codigo)
        if rt:
            return jsonify({
                "velocidade_atual": rt.get('velocidade_atual', 0),
                "estado_atual": ESTADOS_MAQUINA.get(int(rt.get('estado_maquina', 0) or 0), 'Desconhecido'),
                "pecas_produzidas": rt.get('contagem_saida', 0),
                "timestamp": rt.get('timestamp')
            })

        # Fallback InfluxDB
        influx_client = current_app.extensions.get('influx_client')
        if not influx_client: return jsonify({'error': 'DB Error'}), 500

        query = f"SELECT last(estado_maquina), last(velocidade_atual), last(contagem_saida) FROM production WHERE \"equipment\" = '{codigo}'"
        rs = influx_client.query(query)
        points = list(rs.get_points())
        
        if points:
            p = points[0]
            return jsonify({
                "velocidade_atual": float(p.get('last_velocidade_atual') or 0),
                "estado_atual": ESTADOS_MAQUINA.get(int(p.get('last_estado_maquina') or 0), 'Desconhecido'),
                "pecas_produzidas": float(p.get('last_contagem_saida') or 0),
                "timestamp": p.get('time')
            })
            
        return jsonify({
            "velocidade_atual": 0,
            "estado_atual": "Offline",
            "pecas_produzidas": 0,
            "timestamp": None
        })

    except Exception as e:
        logger.error(f"Erro Realtime Equipamento {codigo}: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/operacao/dados/<codigo>', methods=['GET'])
def get_operacao_dados(codigo):
    """
    Retorna dados operacionais (SKU, OP, CUC) de um equipamento.
    """
    try:
        influx_client = current_app.extensions.get('influx_client')
        production_engine = current_app.extensions.get('production_engine')
        
        if not influx_client:
            return jsonify({'error': 'DB not initialized'}), 500
        
        # Query InfluxDB directly for fresh data
        query = f"SELECT last(*) FROM production WHERE \"equipment\" = '{codigo}'"
        rs = influx_client.query(query)
        points = list(rs.get_points())
        
        if not points:
            return jsonify({'error': 'No data'}), 404
        
        d = points[0]
        
        # Get production engine state for calculated metrics
        state = production_engine.get_state(codigo) if production_engine else {}
        
        # Debug: Log values from InfluxDB vs production_engine
        influx_sku = str(d.get('last_sku_codigo', 'N/A'))
        influx_op = str(d.get('last_ordem_producao', 'N/A'))
        logger.info(f"DEBUG {codigo}: InfluxDB SKU={influx_sku}, OP={influx_op}")
        logger.info(f"DEBUG {codigo}: State keys={list(state.keys()) if state else 'None'}")
        
        return jsonify({
            "equipamento": codigo,
            "cuc": str(d.get('last_cuc', 'N/A')),
            "sku": influx_sku,  # Use InfluxDB value directly
            "descricao": str(d.get('last_descricao', 'N/A')),
            "ordem_producao": influx_op,  # Use InfluxDB value directly
            "formato_gramas": float(d.get('last_formato') or d.get('last_formato_gramas') or 0),
            "planejado_op": int(d.get('last_planejado_op', 0) or 0),
            "produzido_op": state.get('producao_op', 0),
            "diferenca_op": state.get('diferenca_op', 0),
            "toneladas_op": state.get('toneladas_op', 0),
            "oee": state.get('oee_realtime', 0),
            "pecas_boas": state.get('producao_op', 0),
            "pecas_ruins": state.get('refugo_op_acumulado', 0),
            "produzido_turno": state.get('producao_turno', 0),
            "toneladas_turno": state.get('toneladas_turno', 0),
            "turno_atual": state.get('turno_atual_nome', 'N/A'),
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Erro Operacao Equipamento {codigo}: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/linha/<linha>/realtime', methods=['GET'])
def get_linha_realtime_ole(linha):
    """
    Retorna OLE e Métricas de Uma Linha para LineOverview
    """
    try:
        linha_norm = normalize_line_name(linha)
        
        influx_client = current_app.extensions.get('influx_client')
        production_engine = current_app.extensions.get('production_engine')
        
        if not influx_client: return jsonify({'error': 'DB Error'}), 500
        
        try:
            response = requests.get(f"{DJANGO_API_URL}/equipamentos/?linha__codigo={linha_norm}", timeout=5)
            if response.ok:
                data = response.json()
                equipamentos = data.get('results', data) if isinstance(data, dict) else data
            else:
                equipamentos = []
        except Exception as e:
            logger.error(f"Erro fetching equipments: {e}")
            equipamentos = []
        
        # Aggregate production from production_engine states
        producao_real_total = 0
        ole_values = []
        meta_total = 0
        
        for eq in equipamentos:
            eq_code = eq.get('codigo')
            if not eq_code:
                continue
            
            state = production_engine.get_state(eq_code) if production_engine else {}
            
            # Sum production from current shift
            prod_turno = state.get('acc_shift', 0)
            producao_real_total += prod_turno
            
            # Collect OLE values for averaging
            metrics = state.get('latest_metrics', {})
            oee = metrics.get('oee_realtime', 0)
            
            # Collect OLE values for averaging
            metrics = state.get('latest_metrics', {})
            oee = metrics.get('oee_realtime', 0)
            
            # Collect OLE values for averaging
            metrics = state.get('latest_metrics', {})
            oee = metrics.get('oee_realtime', 0)
            
            if oee > 0:
                ole_values.append(oee)
            
            # Sum planned production
        # 2. Busca Meta do Turno e Calcula Metricas Temporais
        producao_planejada_ate_agora = 0.0
        producao_planejada_total = float(meta_total) # Default to sum(planejado_op)
        tempo_decorrido = 0
        tempo_total_turno = 28800 # 8h default
        projecao = 0.0
        
        try:
            # Recupera Line ID dos equipamentos para buscar calendario
            linha_id = None
            if equipamentos:
                linha_id = equipamentos[0].get('linha')
            
            # Recupera Info do Turno do Engine
            turno_info = production_engine.shift_manager.get_turno_info()
            
            if turno_info:
                now = datetime.now()
                start_ts = turno_info.get('inicio_timestamp')
                if start_ts:
                    inicio = datetime.fromtimestamp(start_ts)
                    # Recalcula fim baseado no inicio (simples) ou usa lógica mais complexa se disponivel
                    # Assumindo turno de 8h se fim não explícito, mas shift_manager tem inicio/fim
                    # shift_manager retorna 'fim' como time object.
                    
                    # Vamos confiar no timestamp de inicio e calcular decorrido
                    tempo_decorrido = (now - inicio).total_seconds()
                    
                    # Para total, precisamos da diferenca. ShiftManager retorna struct com inicio/fim time.
                    # Vamos simplificar: usar tempo_decorrido e meta para projecao lineal simples
                    # Mas precisamos do tempo total.
                    # Recalculando tempo total baseado no turno_info original
                    # Precisamos saber se cruza dia.
                    
                    # Re-implementacao simplificada de calculo de tempo total:
                    dt_inicio = datetime.combine(now.date(), turno_info['inicio'])
                    dt_fim = datetime.combine(now.date(), turno_info['fim'])
                    if dt_fim <= dt_inicio: dt_fim += timedelta(days=1)
                    # Ajuste para data correta do inicio (pode ser ontem)
                    if abs((inicio - dt_inicio).total_seconds()) > 40000:
                         dt_inicio = inicio
                         dt_fim = datetime.combine(inicio.date(), turno_info['fim'])
                         if dt_fim <= dt_inicio: dt_fim += timedelta(days=1)

                    tempo_total_turno = (dt_fim - dt_inicio).total_seconds()
                    tempo_decorrido = max(0, min(tempo_total_turno, (now - dt_inicio).total_seconds()))

            # Busca Meta no Calendario (Django) se tivermos Linha ID
            if linha_id:
                query_date = datetime.now().strftime('%Y-%m-%d')
                if turno_info:
                   # Se turno comecou ontem, a meta pode estar no calendario de ontem?
                   # Geralmente calendario é pela data de INICIO do turno.
                   if 'inicio_timestamp' in turno_info:
                       query_date = datetime.fromtimestamp(turno_info['inicio_timestamp']).strftime('%Y-%m-%d')

                try:
                    resp_cal = requests.get(f"{DJANGO_API_URL}/calendario/?linha={linha_id}&data={query_date}", timeout=2)
                    if resp_cal.ok:
                        cal_data = resp_cal.json()
                        results_cal = cal_data.get('results', cal_data)
                        if results_cal:
                            for entry in results_cal:
                                # Filtra pelo turno atual se disponivel
                                if turno_info and entry.get('turno_nome') != turno_info.get('nome'):
                                    continue
                                
                                val = float(entry.get('meta_producao_turno') or 0)
                                if val > 0:
                                    producao_planejada_total = val
                                    break
                except Exception as e:
                    logger.error(f"Erro buscando calendario: {e}")

        except Exception as e:
            logger.error(f"Erro calculo temporal/meta: {e}")

        # 3. Calcula Esperado e Projeção
        if tempo_total_turno > 0:
            proporcao = tempo_decorrido / tempo_total_turno
            producao_planejada_ate_agora = producao_planejada_total * proporcao
            
            # Projeção baseada no ritmo atual
            if tempo_decorrido > 300: # 5 min warmup
                 ritmo = producao_real_total / tempo_decorrido # ton/seg
                 projecao = producao_real_total + (ritmo * (tempo_total_turno - tempo_decorrido))
            else:
                 projecao = producao_planejada_total # Inicio do turno

        # Calculate average OLE
        ole_medio = sum(ole_values) / len(ole_values) if ole_values else 0
        
        # Convert production from pieces to tons (using last known format)
        # OBS: producao_real_total ja esta em pecas ou ton? 
        # R: routes.py soma producao_turno do engine, que é PECAS.
        # Precisamos converter para TONELADAS.
        
        # O código original (linha 1613+) fazia conversão.
        # production_engine.processar_dados retorna 'toneladas_turno' também!
        # Podemos usar 'toneladas_turno' do engine se disponivel, ou converter aqui.
        # O engine tem acesso ao formato. Seria melhor usar toneladas do engine.
        
        # Ajuste: Vamos somar toneladas do engine se disponivel
        
        # ... (Mantendo conversão original por segurança, mas engine seria melhor) ...
        # Vamos manter a conversão original abaixo para evitar mexer em muita coisa agora.
        
        # Query InfluxDB for formato to convert
        try:
            query = f"SELECT last(formato) FROM production WHERE \"line\" = '{linha_norm}'"
            rs = influx_client.query(query)
            points = list(rs.get_points())
            formato = float(points[0].get('last') or 0) if points else 0
        except:
            formato = 0
        
        # Convert to tons
        producao_real_tons = (producao_real_total * formato) / 1000000 if formato > 0 else 0
        
        return jsonify({
            "linha": linha_norm,
            "ole": float(ole_medio),
            "producao_real": float(producao_real_tons),
            "producao_planejada_ate_agora": float(producao_planejada_ate_agora),
            "producao_planejada_total": float(producao_planejada_total),
            "tempo_decorrido": int(tempo_decorrido),
            "tempo_total_turno": int(tempo_total_turno),
            "projecao": float(projecao),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Erro Linha Realtime {linha}: {e}")
        # Retorna estrutura vazia para não quebrar UI
        return jsonify({})
