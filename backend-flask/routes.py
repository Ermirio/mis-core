import logging
import time
import requests
from decouple import config
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, current_app

DJANGO_API_URL = config('DJANGO_API_URL', default='http://localhost:8000/api')

api_bp = Blueprint('api', __name__)

logger = logging.getLogger(__name__)

from constants import ESTADOS_MAQUINA

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

@api_bp.route('/api/linha/<linha_nome>/status', methods=['GET'])
def get_linha_status(linha_nome):
    """
    Retorna o status atual de todos os equipamentos da linha.
    """
    try:
        influx_client = current_app.extensions.get('influx_client')
        if not influx_client:
            return jsonify({'error': 'DB not initialized'}), 500

        query = f"SELECT last(estado_maquina) as estado_maquina, last(ordem_producao) as ordem_producao, last(sku_codigo) as sku_codigo, last(descricao) as descricao, last(cuc) as cuc FROM production WHERE \"line\" = '{linha_nome}' GROUP BY \"equipment\""
        rs = influx_client.query(query)
        
        equipamentos = []
        # rs.items() retorna ((nome_serie, tags), gerador_pontos)
        for (name, tags), points in rs.items():
            equipment_name = tags.get('equipment', 'Unknown')
            # Pega o último ponto (deve haver apenas um por causa do last())
            for point in points:
                equipamentos.append({
                    'nome': equipment_name,
                    'medicoes': {
                        'estado_maquina': int(point.get('estado_maquina', 0) or 0),
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

@api_bp.route('/api/linha/<linha_nome>/realtime', methods=['GET'])
def get_linha_realtime(linha_nome):
    """
    Calcula o OLE (Overall Line Effectiveness) em tempo real.
    """
    try:
        influx_client = current_app.extensions.get('influx_client')
        production_engine = current_app.extensions.get('production_engine')
        
        if not influx_client or not production_engine:
            return jsonify({'error': 'Engine/DB not initialized'}), 500

        # 1. Busca Produção Real (Toneladas) - Máximo entre os equipamentos (Gargalo/Final)
        query = f"SELECT last(toneladas_turno), last(formato_gramas), last(estado_maquina) FROM production WHERE \"line\" = '{linha_nome}' GROUP BY \"equipment\""
        rs = influx_client.query(query)
        points = list(rs.get_points())
        
        producao_real_ton = 0.0
        formato_gramas = 0.0
        equipamentos_online = 0
        equipamentos_total = len(points)
        
        for p in points:
            ton = float(p.get('last', 0) or 0)
            if ton > producao_real_ton:
                producao_real_ton = ton
                formato_gramas = float(p.get('last_1', 0) or 0)
            
            estado = int(p.get('last_2', 0) or 0)
            if estado in [1, 2, 3]: 
                equipamentos_online += 1

        # 2. Busca Meta do Turno (Django) e Calcula Tempo
        producao_planejada_total = 0.0
        producao_planejada_ate_agora = 0.0
        tempo_decorrido = 0
        tempo_total_turno = 28800 # Default 8h
        
        try:
            # Dados do Turno Atual via ShiftManager
            turno_info = production_engine.shift_manager.get_turno_info()
            if turno_info:
                agora = datetime.now()
                
                # Converte inicio/fim para datetime
                if 'inicio_timestamp' in turno_info:
                    inicio = datetime.fromtimestamp(turno_info['inicio_timestamp'])
                else:
                    # Fallback se não tiver timestamp
                    inicio = datetime.combine(agora.date(), turno_info['inicio'])
                
                fim = datetime.combine(inicio.date(), turno_info['fim'])
                
                # Ajusta fim se for no dia seguinte (turno noturno)
                if fim <= inicio:
                    fim += timedelta(days=1)
                
                if agora > fim: agora = fim # Clamp se estiver olhando histórico ou fim de turno
                
                delta_total = (fim - inicio).total_seconds()
                delta_decorrido = (agora - inicio).total_seconds()
                
                if delta_total > 0:
                    tempo_total_turno = delta_total
                    tempo_decorrido = max(0, delta_decorrido)

            # Busca Meta no Django
            import requests
            from decouple import config
            DJANGO_API_URL = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')
            
            # Busca ID da Linha
            resp_linha = requests.get(f"{DJANGO_API_URL}/linhas/?codigo={linha_nome}", timeout=2)
            if resp_linha.status_code == 200:
                data_linha = resp_linha.json()
                results_linha = data_linha.get('results', data_linha)
                if results_linha:
                    linha_id = results_linha[0]['id']
                    
                    # Busca Calendário
                    # Se tiver info do turno, usa a data de INÍCIO do turno (para lidar com virada de dia)
                    if turno_info and 'inicio_timestamp' in turno_info:
                         dt_inicio = datetime.fromtimestamp(turno_info['inicio_timestamp'])
                         query_date = dt_inicio.strftime('%Y-%m-%d')
                    else:
                         query_date = datetime.now().strftime('%Y-%m-%d')
                         
                    resp_cal = requests.get(f"{DJANGO_API_URL}/calendario/?linha_id={linha_id}&data={query_date}", timeout=2)
                    
                    meta_toneladas = 0.0
                    if resp_cal.status_code == 200:
                        data_cal = resp_cal.json()
                        results_cal = data_cal.get('results', data_cal)
                        if results_cal:
                            for entry in results_cal:
                                if entry.get('programado') and entry.get('meta_producao_turno'):
                                    # USER FIX: Valor já está em Toneladas (ou Kg se > 1000)
                                    val = float(entry.get('meta_producao_turno'))
                                    if val > 1000: val /= 1000.0
                                    
                                    # Tenta casar com o turno atual
                                    if turno_info and entry.get('turno_nome') == turno_info.get('nome'):
                                        meta_toneladas = val
                                        break
                                    
                                    # Se não casar, guarda o primeiro como fallback
                                    if meta_toneladas == 0:
                                        meta_toneladas = val
                    
                    # Fallback: Meta da Linha
                    if meta_toneladas == 0:
                        val = float(results_linha[0].get('meta_toneladas_turno') or 0)
                        if val > 1000: val /= 1000.0
                        meta_toneladas = val

                    producao_planejada_total = meta_toneladas

        except Exception as e:
            logger.error(f"Erro Meta/Turno: {e}")
            error_msg = str(e)

        # 3. Calcula Esperado até Agora
        proporcao = 0.0
        if tempo_total_turno > 0:
            proporcao = tempo_decorrido / tempo_total_turno
            proporcao = min(1.0, max(0.0, proporcao))
            
        producao_planejada_ate_agora = producao_planejada_total * proporcao

        # 4. Calcula OLE (OMAC/ISA)
        ole = 0.0
        if producao_planejada_ate_agora > 0.001: # Evita div por zero
            ole = (producao_real_ton / producao_planejada_ate_agora) * 100
            ole = min(ole, 120.0)
        
        ole = round(ole, 1)

        # 5. Persistência
        try:
            point_ole = {
                "measurement": "line_metrics",
                "tags": { "line": linha_nome },
                "fields": { 
                    "ole": float(ole),
                    "producao_real": float(producao_real_ton),
                    "producao_planejada_ate_agora": float(producao_planejada_ate_agora),
                    "producao_planejada_total": float(producao_planejada_total),
                    "equipamentos_online": int(equipamentos_online),
                    "equipamentos_total": int(equipamentos_total)
                },
                "time": datetime.now().isoformat()
            }
            influx_client.write_points([point_ole])
        except: pass

        return jsonify({
            "linha": linha_nome,
            "ole": ole,
            "producao_real": round(producao_real_ton, 3),
            "producao_planejada_ate_agora": round(producao_planejada_ate_agora, 3),
            "producao_planejada_total": round(producao_planejada_total, 3),
            "tempo_decorrido": int(tempo_decorrido),
            "tempo_total_turno": int(tempo_total_turno),
            "equipamentos_total": equipamentos_total,
            "equipamentos_online": equipamentos_online,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Erro OLE Linha: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api/operacao/dados/<eq_code>', methods=['GET'])
def get_operacao(eq_code):
    try:
        influx_client = current_app.extensions.get('influx_client')
        if not influx_client:
            return jsonify({'error': 'InfluxDB not initialized'}), 500

        rs = influx_client.query(f"SELECT last(*) FROM production WHERE \"equipment\" = '{eq_code}'")
        pts = list(rs.get_points())
        if not pts: return jsonify({'status': 'Aguardando...'}), 200
        d = pts[0]

        prod_op = int(d.get('last_producao_op_acumulada', 0) or 0)
        plan = int(d.get('last_planejado_op', 0) or 0)

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
            "oee": float(d.get('last_oee_realtime', 0) or 0),
            "pecas_boas": prod_op, 
            "pecas_ruins": int(d.get('last_descarte', 0) or 0),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api/equipamento/dados/<eq_code>', methods=['GET'])
def get_equipamento(eq_code):
    try:
        influx_client = current_app.extensions.get('influx_client')
        if not influx_client:
            return jsonify({'error': 'InfluxDB not initialized'}), 500

        rs = influx_client.query(f"SELECT last(*) FROM production WHERE \"equipment\" = '{eq_code}'")
        pts = list(rs.get_points())
        if not pts: return jsonify({'status': 'Sem dados'}), 200
        d = pts[0]
        
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

        est = int(d.get('last_estado_maquina', 0) or 0)
        return jsonify({
            "equipamento": eq_code,
            "velocidade_atual": int(d.get('last_velocidade_atual', 0) or 0),
            "pecas_produzidas": int(d.get('last_producao_op_acumulada', 0) or 0),
            "refugos": int(d.get('last_descarte', 0) or 0),
            "estado_atual": ESTADOS_MAQUINA.get(est, str(est)),
            "oee_atual": float(d.get('last_oee_realtime', 0) or 0),
            "sensores": sensores,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api/dados/inserir', methods=['POST'])
def inserir():
    try:
        influx_client = current_app.extensions.get('influx_client')
        production_engine = current_app.extensions.get('production_engine')
        
        if not influx_client or not production_engine:
            return jsonify({'error': 'Engine/DB not initialized'}), 500

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

        # Prioridade: Velocidade Real > Calculada
        vel_real = m.get('velocidade_atual')
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
            estado_maquina=est
        )

        fields = {
            "velocidade_atual": vel_calc,
            "estado_maquina": est,
            "ordem_producao_field": op,
            "sku_codigo_field": sku,
            "producao_op_acumulada": res['producao_op'],
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

        # 1. Busca Produção Real (Toneladas) - Máximo entre os equipamentos
        query = f"SELECT last(toneladas_turno) FROM production WHERE \"line\" = '{linha_nome}' GROUP BY \"equipment\""
        rs = influx_client.query(query)
        points = list(rs.get_points())
        toneladas_real = 0.0
        if points:
            toneladas_real = max([float(p['last']) for p in points if p['last'] is not None], default=0.0)

        # 2. Busca Meta do Turno (Django) e Calcula Tempo
        meta_toneladas = 0.0
        tempo_decorrido = 0
        tempo_total_turno = 0
        
        # Dados do Turno Atual
        turno_info = production_engine.shift_manager.get_turno_info()
        
        # Busca ID da Linha
        resp_linha = requests.get(f"{DJANGO_API_URL}/linhas/?codigo={linha_nome}", timeout=2)
        if resp_linha.status_code == 200:
            data_linha = resp_linha.json()
            results_linha = data_linha.get('results', data_linha)
            if results_linha:
                linha_id = results_linha[0]['id']
                
                # Busca Calendário (com correção de data do turno)
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
                                
                                # Tenta casar com o turno atual
                                if turno_info and entry.get('turno_nome') == turno_info.get('nome'):
                                    meta_toneladas = val
                                    break
                                
                                # Fallback
                                if meta_toneladas == 0:
                                    meta_toneladas = val

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
            
            # Cap no tempo decorrido (não pode ser maior que o total se o turno acabou)
            if tempo_decorrido > tempo_total_turno:
                tempo_decorrido = tempo_total_turno
        
        # 4. Cálculo OLE (OMAC)
        producao_esperada = 0.0
        ole = 0.0
        projecao = 0.0
        
        if meta_toneladas > 0 and tempo_total_turno > 0:
            producao_esperada = meta_toneladas * (tempo_decorrido / tempo_total_turno)
            
            if producao_esperada > 0:
                ole = (toneladas_real / producao_esperada) * 100.0
            
            # Projeção Linear
            if tempo_decorrido > 0:
                taxa_atual = toneladas_real / tempo_decorrido
                projecao = taxa_atual * tempo_total_turno

        return jsonify({
            'ole': round(ole, 1),
            'producao_real': round(toneladas_real, 3),
            'producao_esperada': round(producao_esperada, 3),
            'projecao': round(projecao, 1),
            'meta_turno': round(meta_toneladas, 1),
            'tempo_decorrido_perc': round((tempo_decorrido / tempo_total_turno * 100) if tempo_total_turno > 0 else 0, 1)
        })

    except Exception as e:
        logger.error(f"Erro OLE Realtime: {e}")
        return jsonify({'error': str(e)}), 500

# @api_bp.route('/api/linha/<linha_nome>/kpis', methods=['GET'])
# def get_linha_kpis(linha_nome):
#     """
#     Retorna KPIs agregados da linha e gargalo.
#     """
#     try:
#         influx_client = current_app.extensions.get('influx_client')
#         if not influx_client: return jsonify({'error': 'No DB'}), 500
#
#         # Busca últimos dados de todos os equipamentos da linha
#         query = f"SELECT last(availability_realtime), last(performance_realtime), last(quality_realtime), last(estado_maquina) FROM production WHERE \"line\" = '{linha_nome}' GROUP BY \"equipment\""
#         rs = influx_client.query(query)
#         points = list(rs.get_points())
#         
#         if not points:
#             return jsonify({
#                 'availability': 0, 'performance': 0, 'quality': 0,
#                 'bottleneck': {'name': 'N/A', 'oee': 0}
#             })
#
#         # Calcula Médias
#         avg_avail = sum([p['last'] for p in points if p['last'] is not None]) / len(points)
#         avg_perf = sum([p['last_1'] for p in points if p['last_1'] is not None]) / len(points)
#         avg_qual = sum([p['last_2'] for p in points if p['last_2'] is not None]) / len(points)
#
#         # Identifica Gargalo (Menor OEE = Avail * Perf * Qual)
#         bottleneck = None
#         min_oee = 101.0
#         
#         for p in points:
#             # Recalcula OEE localmente pois não buscamos o campo OEE direto (opcional)
#             a = p['last'] or 0
#             pe = p['last_1'] or 0
#             q = p['last_2'] or 0
#             oee = (a * pe * q) / 10000.0 # Se estiverem em 0-100
#             
#             # Influx retorna tags como chaves no get_points se group by
#             # Mas aqui points é lista de dicts com valores. O nome do equipamento está nas tags do resultset original
#             # Ajuste: get_points() retorna generator, list() flattens it but loses tags if not careful.
#             # Melhor iterar sobre rs.items()
#             pass
#
#         # Re-iterando corretamente para pegar nomes
#         items = list(rs.items())
#         equip_stats = []
#         
#         for (tags, generator) in items:
#             for p in generator:
#                 eq_name = tags['equipment']
#                 a = p['last'] or 0
#                 pe = p['last_1'] or 0
#                 q = p['last_2'] or 0
#                 oee = (a/100) * (pe/100) * (q/100) * 100
#                 equip_stats.append({'name': eq_name, 'oee': oee})
#
#         if equip_stats:
#             bottleneck = min(equip_stats, key=lambda x: x['oee'])
#         else:
#             bottleneck = {'name': 'N/A', 'oee': 0}
#
#         return jsonify({
#             'availability': round(avg_avail, 1),
#             'performance': round(avg_perf, 1),
#             'quality': round(avg_qual, 1),
#             'bottleneck': {
#                 'name': bottleneck['name'],
#                 'oee': round(bottleneck['oee'], 1)
#             }
#         })
#
#     except Exception as e:
#         logger.error(f"Erro KPIs: {e}")
#         return jsonify({'error': str(e)}), 500

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
