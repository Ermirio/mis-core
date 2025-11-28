import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from influxdb import InfluxDBClient
from decouple import config
from datetime import datetime, timedelta
import requests
import time  # NOVO: Importar time no topo

app = Flask(__name__)

# ===== CONFIGURAÇÃO DE CORS =====
# Permite TODAS as origens em desenvolvimento
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "Accept", "Origin"],
        "supports_credentials": False
    }
})

# ===== CONFIGURAÇÃO DE LOGGING =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Iniciando Flask API...")

# ===== CONFIGURAÇÕES DA APLICAÇÃO =====
INFLUX_HOST = config('INFLUXDB_HOST', default='127.0.0.1')
INFLUX_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUX_DB = config('INFLUXDB_DATABASE', default='industrial_db')
INFLUX_USER = config('INFLUXDB_USER', default='admin')
INFLUX_PASS = config('INFLUXDB_USER_PASSWORD', default='ixvq10A@10')

DJANGO_API_URL = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')

# ===== CLIENTE INFLUXDB =====
logger.info(f"Tentando conectar ao InfluxDB: {INFLUX_HOST}:{INFLUX_PORT}/{INFLUX_DB}")
logger.info(f"Usuário: {INFLUX_USER}, Senha: {'*' * len(INFLUX_PASS) if INFLUX_PASS else 'None'}")

try:
    influx_client = InfluxDBClient(
        host=INFLUX_HOST, 
        port=INFLUX_PORT, 
        username=INFLUX_USER, 
        password=INFLUX_PASS, 
        database=INFLUX_DB
    )
    
    # Testa conexão
    influx_client.ping()
    logger.info(f"✓ Conectado ao InfluxDB em {INFLUX_HOST}:{INFLUX_PORT}, database '{INFLUX_DB}'")

except Exception as e:
    logger.error(f"✗ Erro ao conectar InfluxDB: {e}")
    influx_client = None

# ===== FUNÇÕES AUXILIARES PARA SCHEMA INFLUXDB =====

def detectar_turno():
    """
    Detecta o turno atual baseado no horário.
    A: 06:00-14:00, B: 14:00-22:00, C: 22:00-06:00
    """
    hora_atual = datetime.now().hour
    if 6 <= hora_atual < 14:
        return 'A'
    elif 14 <= hora_atual < 22:
        return 'B'
    else:
        return 'C'


def calcular_velocidade(contagem_atual, contagem_anterior, intervalo_segundos=5):
    """
    Calcula velocidade em peças/minuto.
    
    Args:
        contagem_atual: Contador atual
        contagem_anterior: Contador anterior
        intervalo_segundos: Intervalo entre leituras (padrão 5s)
    
    Returns:
        int: Velocidade em peças/minuto
    """
    if contagem_anterior is None or contagem_atual <= contagem_anterior:
        return 0
    
    delta = contagem_atual - contagem_anterior
    velocidade_por_segundo = delta / intervalo_segundos
    velocidade_por_minuto = int(velocidade_por_segundo * 60)
    
    return velocidade_por_minuto


# Cache global para detectar mudanças de estado
_estado_anterior = {}

def mudou_estado(equipamento_codigo, estado_atual):
    """
    Detecta se o estado da máquina mudou.
    
    Args:
        equipamento_codigo: Código do equipamento
        estado_atual: Estado atual da máquina
    
    Returns:
        bool: True se mudou, False caso contrário
    """
    global _estado_anterior
    
    estado_prev = _estado_anterior.get(equipamento_codigo)
    mudou = estado_prev != estado_atual
    
    if mudou:
        _estado_anterior[equipamento_codigo] = estado_atual
    
    return mudou


# Cache para cálculo de velocidade
_contador_anterior = {}

def get_contador_anterior(equipamento_codigo):
    """Retorna o contador anterior para cálculo de velocidade"""
    return _contador_anterior.get(equipamento_codigo)

def set_contador_anterior(equipamento_codigo, contador):
    """Armazena o contador atual para próxima iteração"""
    _contador_anterior[equipamento_codigo] = contador

# ===== DETECTOR DE MUDANÇA DE TURNO =====
class ShiftDetector:
    """Detecta mudanças de turno e dispara consolidação automática"""
    
    def __init__(self):
        # Estado: { 'linha_codigo': { 'turno_atual': 'A', 'ultimo_check': timestamp } }
        self.shift_states = {}
        self.consolidation_in_progress = set()  # Evita consolidações duplicadas

    
    def detect_and_consolidate(self, linha_codigo, turno_atual):
        """
        Detecta mudança de turno e dispara consolidação do turno anterior
        
        Args:
            linha_codigo: Código da linha
            turno_atual: Turno atual detectado nos dados
        
        Returns:
            bool: True se houve mudança de turno
        """
        if not turno_atual or not linha_codigo:
            return False
        
        # Buscar estado anterior
        state = self.shift_states.get(linha_codigo, {})
        turno_anterior = state.get('turno_atual')
        
        # Primeira vez vendo esta linha - só registra
        if not turno_anterior:
            self.shift_states[linha_codigo] = {
                'turno_atual': turno_atual,
                'ultimo_check': datetime.now()
            }
            return False
        
        # Mudança de turno detectada!
        if turno_anterior != turno_atual:
            logger.info(f"[SHIFT CHANGE] Linha {linha_codigo}: {turno_anterior} → {turno_atual}")
            
            # Atualiza estado
            self.shift_states[linha_codigo] = {
                'turno_atual': turno_atual,
                'ultimo_check': datetime.now()
            }
            
            # Dispara consolidação do turno anterior (async, não bloqueia coleta)
            consolidation_key = f"{linha_codigo}_{turno_anterior}_{datetime.now().date()}"
            
            if consolidation_key not in self.consolidation_in_progress:
                self.consolidation_in_progress.add(consolidation_key)
                
                try:
                    # Chamar endpoint Django para consolidar turno anterior
                    response = requests.post(
                        f"{DJANGO_API_URL}/bi/consolidar-turno/",
                        json={
                            'linha_codigo': linha_codigo,
                            'turno_codigo': turno_anterior,
                            'data': datetime.now().date().isoformat()
                        },
                        timeout=2
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"[CONSOLIDAÇÃO] ✓ Turno {turno_anterior} consolidado")
                    else:
                        logger.warning(f"[CONSOLIDAÇÃO] ⚠ Erro {response.status_code}")
                        
                except Exception as e:
                    logger.warning(f"[CONSOLIDAÇÃO] ⚠ Erro ao consolidar: {e}")
                finally:
                    # Remove do lock após 60s (evita acúmulo infinito)
                    from threading import Timer
                    Timer(60, lambda: self.consolidation_in_progress.discard(consolidation_key)).start()
                
            return True
        
        return False

# Instância global
shift_detector = ShiftDetector()


# ===== ROTAS DE API =====


@app.route('/api/health', methods=['GET'])
def health():
    """Health check da API Flask"""
    return jsonify({
        'status': 'ok',
        'service': 'Flask API',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/dados/inserir', methods=['POST'])
def inserir_dados():
    """
    Recebe dados do coletor e insere no InfluxDB
    
    Payload esperado:
    {
        "equipamento_codigo": "001",
        "linha_codigo": "L01",
        "medicoes": {
            "contagem_entrada": 1000,
            "contagem_saida": 995,
            "velocidade_atual": 98.5,
            "estado": 1,
            "temperatura": 25.3,
            "pressao": 45.2,
            "ordem_producao": "OP-123",
            "sku_codigo": "SKU-ABC",
            "formato_gramas": 500
        },
        "timestamp": "2024-01-15T10:30:00Z"
    }
    """
    try:
        data = request.json
        logger.debug(f"Recebido payload de {data.get('equipamento_codigo')}")
        
        equipamento_codigo = data.get('equipamento_codigo') or data.get('equipamento')
        linha_codigo = data.get('linha_codigo', '')
        medicoes = data.get('medicoes', {})
        timestamp = data.get('timestamp')
        
        # Validação básica
        if not equipamento_codigo or not medicoes:
            logger.warning(f"Payload inválido: {data}")
            return jsonify({'error': 'equipamento_codigo e medicoes são obrigatórios'}), 400
        
        # ===== EXTRAIR DADOS DO PAYLOAD =====
        ordem_producao = medicoes.get('ordem_producao', '')
        sku_codigo = medicoes.get('sku_codigo', '')
        contagem_entrada = int(float(medicoes.get('contagem_entrada', 0)))
        contagem_saida = int(float(medicoes.get('contagem_saida', 0)))
        descarte = int(float(medicoes.get('descarte', 0)))
        formato_gramas = int(float(medicoes.get('formato_gramas', 0)))
        planejado_op = int(float(medicoes.get('planejado_op', 0)))
        descricao = medicoes.get('descricao', '')
        estado_maquina = medicoes.get('estado_maquina', 'UNKNOWN')
        motivo_parada = medicoes.get('motivo_parada', '')
        percentual_descarte = float(medicoes.get('percentual_descarte', 0))
        temperatura = float(medicoes.get('temperatura', 0))
        pressao = float(medicoes.get('pressao', 0))
        oee = float(medicoes.get('oee', 0))
        disponibilidade = float(medicoes.get('disponibilidade', 0))
        performance = float(medicoes.get('performance', 0))
        qualidade = float(medicoes.get('qualidade', 0))
        
        # ===== CALCULAR VALORES DERIVADOS =====
        turno = detectar_turno()
        contador_anterior = get_contador_anterior(equipamento_codigo)
        velocidade_atual = calcular_velocidade(contagem_saida, contador_anterior)
        set_contador_anterior(equipamento_codigo, contagem_saida)
        
        # ===== ESCREVER NO INFLUXDB =====
        points_to_write = []
        
        # 1. MEASUREMENT: production (sempre escreve)
        production_point = {
            "measurement": "production",
            "tags": {
                "line": linha_codigo,
                "equipment": equipamento_codigo,
                "order_id": ordem_producao,
                "sku": sku_codigo,
                "shift": turno,
                "estado_maquina": estado_maquina # Adiciona estado como tag
            },
            "fields": {
                "contagem_entrada": contagem_entrada,
                "contagem_saida": contagem_saida,
                "descarte": descarte,
                "percentual_descarte": percentual_descarte,
                "velocidade_atual": velocidade_atual,
                "formato_gramas": formato_gramas,
                "planejado_op": planejado_op,
                "descricao": descricao,
                "temperatura": temperatura,
                "pressao": pressao,
                "oee": oee,
                "disponibilidade": disponibilidade,
                "performance": performance,
                "qualidade": qualidade,
                "ordem_producao_field": ordem_producao if ordem_producao else "N/A",
                "sku_codigo_field": sku_codigo if sku_codigo else "N/A"
            }
        }
        
        if timestamp:
            production_point["time"] = timestamp
        
        # DEBUG: Log do ponto a ser escrito
        logger.info(f"[DEBUG-WRITE] Escrevendo ponto: {production_point}")
        
        points_to_write.append(production_point)
        logger.info(f"[PRODUCTION] {equipamento_codigo}: saída={contagem_saida}, vel={velocidade_atual} pç/min, estado={estado_maquina}")
        
        # 2. MEASUREMENT: machine_status (só escreve se mudou)
        if mudou_estado(equipamento_codigo, estado_maquina):
            status_point = {
                "measurement": "machine_status",
                "tags": {
                    "line": linha_codigo,
                    "equipment": equipamento_codigo,
                    "estado_maquina": estado_maquina,
                    "motivo_parada": motivo_parada if motivo_parada else "N/A",
                    "shift": turno
                },
                "fields": {
                    "value": 1
                }
            }
            
            if timestamp:
                status_point["time"] = timestamp
            
            points_to_write.append(status_point)
            logger.info(f"[STATUS CHANGE] {equipamento_codigo}: {estado_maquina}")
        
        # Escrever todos os pontos no InfluxDB
        if influx_client and points_to_write:
            try:
                influx_client.write_points(points_to_write)
                logger.debug(f"✓ {len(points_to_write)} pontos escritos no InfluxDB")
            except Exception as e:
                logger.error(f"✗ Erro ao escrever no InfluxDB: {e}")
                return jsonify({'error': 'Falha ao escrever no InfluxDB'}), 500
        
        return jsonify({'status': 'success', 'message': 'Dados inseridos com sucesso'})
    
    except Exception as e:
        import traceback
        error_msg = f"ERRO FATAL FLASK: {str(e)}\n{traceback.format_exc()}"
        logger.error(f"✗ Erro ao inserir dados: {e}")
        # Escreve em arquivo para debug persistente
        try:
            with open('flask_fatal_error.log', 'a') as f:
                f.write(f"\n[{datetime.now()}] {error_msg}\n")
        except:
            pass
        return jsonify({'error': 'Falha ao salvar dados', 'details': str(e)}), 500


@app.route('/api/realtime/status/<equipamento_codigo>', methods=['GET'])
def get_realtime_status(equipamento_codigo):
    """
    Retorna status em tempo real de um equipamento.
    Busca os últimos dados do measurement 'production'.
    """
    try:
        if not influx_client:
            logger.error("Cliente InfluxDB não disponível")
            return jsonify({'error': 'Banco de dados indisponível'}), 503
        
        # Query para buscar últimos dados do novo schema
        # Inclui TODOS os campos armazenados no InfluxDB
        query = f"""
            SELECT 
                last(contagem_saida) as contagem_saida,
                last(contagem_entrada) as contagem_entrada,
                last(velocidade_atual) as velocidade_atual,
                last(descarte) as descarte,
                last(percentual_descarte) as percentual_descarte,
                last(formato_gramas) as formato_gramas,
                last(planejado_op) as planejado_op,
                last(descricao) as descricao,
                last(temperatura) as temperatura,
                last(pressao) as pressao,
                last(oee) as oee,
                last(disponibilidade) as disponibilidade,
                last(performance) as performance,
                last(qualidade) as qualidade,
                last(ordem_producao_field) as ordem_producao,
                last(sku_codigo_field) as sku_codigo
            FROM production
            WHERE equipment = '{equipamento_codigo}'
            GROUP BY *
            ORDER BY time DESC
            LIMIT 1
        """
        
        result = influx_client.query(query)
        # get_points() com tags retorna um gerador de dicionários incluindo tags
        points = list(result.get_points())
        
        status_code = 'ONLINE' # Default
        
        if points:
            # Pega o estado do último ponto de produção
            status_code = points[0].get('estado_maquina', 'ONLINE')
        else:
            # Fallback para machine_status se não tiver produção recente
            query_status = f"""
                SELECT *
                FROM machine_status
                WHERE equipment = '{equipamento_codigo}'
                ORDER BY time DESC
                LIMIT 1
            """
            result_status = influx_client.query(query_status)
            points_status = list(result_status.get_points())
            if points_status:
                status_code = points_status[0].get('estado_maquina', 'ONLINE')
        
        if not points:
            logger.info(f"Sem dados para {equipamento_codigo}")
            return jsonify({
                'equipamento': equipamento_codigo,
                'status': 'OFFLINE',
                'message': 'Nenhum dado recente encontrado',
                'timestamp': datetime.now().isoformat()
            }), 200
        
        # Formata resposta
        data = points[0]
        
        # Verifica se tem dados válidos (pelo menos contagem_saida)
        if data.get('contagem_saida') is None:
             logger.info(f"Dados incompletos para {equipamento_codigo}")
             return jsonify({
                'equipamento': equipamento_codigo,
                'status': 'OFFLINE',
                'message': 'Dados incompletos',
                'timestamp': datetime.now().isoformat()
            }), 200

        response = {
            'equipamento': equipamento_codigo,
            'timestamp': datetime.now().isoformat(),
            'status': status_code,
            'medicoes': {
                'contagem_saida': int(data.get('contagem_saida') or 0),
                'contagem_entrada': int(data.get('contagem_entrada') or 0),
                'velocidade_atual': int(data.get('velocidade_atual') or 0),
                'descarte': int(data.get('descarte') or 0),
                'percentual_descarte': float(data.get('percentual_descarte') or 0),
                'formato_gramas': int(data.get('formato_gramas') or 0),
                'planejado_op': int(data.get('planejado_op') or 0),
                'descricao': data.get('descricao', ''),
                'temperatura': float(data.get('temperatura') or 0),
                'pressao': float(data.get('pressao') or 0),
                'oee': float(data.get('oee') or 0),
                'disponibilidade': float(data.get('disponibilidade') or 0),
                'performance': float(data.get('performance') or 0),
                'qualidade': float(data.get('qualidade') or 0),
                'ordem_producao': data.get('ordem_producao', ''),
                'sku_codigo': data.get('sku_codigo', ''),
                'estado': status_code
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"✗ Erro em /realtime/status/{equipamento_codigo}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/realtime/variaveis/<equipamento_codigo>', methods=['GET'])
def get_process_variables(equipamento_codigo):
    """
    Retorna variáveis de processo em tempo real (últimos 2 minutos)
    """
    try:
        if not influx_client:
            logger.error("Cliente InfluxDB não disponível")
            return jsonify({'error': 'Banco de dados indisponível'}), 503
        
        query = f"""
            SELECT *
            FROM production
            WHERE equipment = '{equipamento_codigo}'
            AND time > now() - 2m
            ORDER BY time ASC
            LIMIT 20
        """
        
        result = influx_client.query(query)
        points = list(result.get_points())
        
        if not points:
            logger.info(f"Sem dados (2m) para {equipamento_codigo}")
            return jsonify({'error': 'Nenhum dado encontrado'}), 404
        
        return jsonify({
            'equipamento': equipamento_codigo,
            'timestamp': datetime.now().isoformat(),
            'dados': points
        })
    
    except Exception as e:
        logger.error(f"✗ Erro em /realtime/variaveis/{equipamento_codigo}: {e}")
        return jsonify({'error': 'Erro ao buscar dados', 'details': str(e)}), 500


@app.route('/api/timeline/<equipamento_codigo>', methods=['GET'])
def get_timeline(equipamento_codigo):
    """
    Retorna dados granulares para timeline de velocidade e descarte
    Aceita parâmetros: start (ISO), end (ISO)
    """
    try:
        if not influx_client:
            logger.error("Cliente InfluxDB não disponível")
            return jsonify({'error': 'Banco de dados indisponível'}), 503
        
        start = request.args.get('start')
        end = request.args.get('end')
        
        if not start or not end:
            # Default: últimas 4 horas
            end = datetime.utcnow()
            start = end - timedelta(hours=4)
            start_str = start.isoformat() + 'Z'
            end_str = end.isoformat() + 'Z'
        else:
            start_str = start
            end_str = end

        # Query para velocidade e descarte (agrupado por minuto)
        query = f"""
            SELECT 
                mean("velocidade_atual") as velocidade,
                max("contagem_saida") - min("contagem_saida") as producao,
                max("descarte") - min("descarte") as descarte
            FROM production
            WHERE equipment = '{equipamento_codigo}'
            AND time >= '{start_str}' AND time <= '{end_str}'
            GROUP BY time(1m) fill(0)
        """
        
        result = influx_client.query(query)
        points = list(result.get_points())
        
        return jsonify({
            'equipamento': equipamento_codigo,
            'start': start_str,
            'end': end_str,
            'dados': points
        })
    
    except Exception as e:
        logger.error(f"✗ Erro em /timeline/{equipamento_codigo}: {e}")
        return jsonify({'error': 'Erro ao buscar timeline', 'details': str(e)}), 500


@app.route('/api/historico/<equipamento_codigo>', methods=['GET'])
def get_historico(equipamento_codigo):
    """
    Retorna histórico agregado por hora
    """
    try:
        if not influx_client:
            logger.error("Cliente InfluxDB não disponível")
            return jsonify({'error': 'Banco de dados indisponível'}), 503
        
        horas = request.args.get('horas', default=24, type=int)
        
        query = f"""
            SELECT mean("velocidade_atual") as velocidade_media,
                   mean("temperatura") as temperatura_media,
                   mean("pressao") as pressao_media,
                   max("contagem_saida") - min("contagem_saida") as producao_total
            FROM production
            WHERE equipment = '{equipamento_codigo}'
            AND time > now() - {horas}h
            GROUP BY time(1h)
        """
        
        result = influx_client.query(query)
        points = list(result.get_points())
        
        return jsonify({
            'equipamento': equipamento_codigo,
            'periodo': f'últimas {horas} horas',
            'dados': points
        })
    
    except Exception as e:
        logger.error(f"✗ Erro em /historico/{equipamento_codigo}: {e}")
        return jsonify({'error': 'Erro ao buscar histórico', 'details': str(e)}), 500


# ===== ERROS =====

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint não encontrado'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"✗ Erro interno: {error}")
    return jsonify({'error': 'Erro interno do servidor'}), 500


# ===== INICIALIZAÇÃO =====

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("Iniciando Flask API")
    logger.info(f"CORS habilitado para: 127.0.0.1:3000, 127.0.0.1:5173, 127.0.0.1:8000")
    logger.info(f"InfluxDB: {INFLUX_HOST}:{INFLUX_PORT}/{INFLUX_DB}")
    logger.info(f"Django API: {DJANGO_API_URL}")
    logger.info("=" * 60)
    
    app.run(host='127.0.0.1', port=5000, debug=False)