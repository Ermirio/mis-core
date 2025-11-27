import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from influxdb import InfluxDBClient
from decouple import config
from datetime import datetime, timedelta
import requests

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
INFLUX_USER = config('INFLUXDB_USER', default=None)
INFLUX_PASS = config('INFLUXDB_USER_PASSWORD', default=None)

DJANGO_API_URL = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')

# ===== CLIENTE INFLUXDB =====
try:
    influx_client = InfluxDBClient(
        host=INFLUX_HOST, 
        port=INFLUX_PORT, 
        username=INFLUX_USER, 
        password=INFLUX_PASS, 
        database=INFLUX_DB
    )
    
    # Tenta criar o DB (só por garantia)
    influx_client.create_database(INFLUX_DB)
    
    logger.info(f"✓ Conectado ao InfluxDB em {INFLUX_HOST}:{INFLUX_PORT}, database '{INFLUX_DB}'")

except Exception as e:
    logger.error(f"✗ Erro ao conectar InfluxDB: {e}")
    influx_client = None

# ===== ACUMULADORES DE PRODUÇÃO =====
# Dicionários para rastrear produção acumulada por OP e SKU
# Formato: {equipamento_codigo_ordem_producao: {contagem_inicial, producao_acumulada}}
acumuladores_op = {}
acumuladores_sku = {}
logger.info("Acumuladores de produção inicializados")


# ===== CLASSE DE CONTROLE DE PRODUÇÃO =====
class ProductionCounter:
    def __init__(self):
        # Estado: { 'equipamento': { 'op': '...', 'sku': '...', 'last_count': 0, 'acc_op': 0.0, 'acc_sku': 0.0 } }
        self.states = {}

    def get_last_accumulated(self, client, eq_code, tag_key, tag_value, field_key):
        """Busca o último valor acumulado no InfluxDB para uma OP ou SKU específico"""
        try:
            if not client: return 0.0
            # Query otimizada: busca apenas o último valor do campo específico filtrado pela tag
            query = f"""
                SELECT last("{field_key}") 
                FROM "producao" 
                WHERE "equipamento_codigo" = '{eq_code}' 
                AND "{tag_key}" = '{tag_value}'
            """
            result = client.query(query)
            points = list(result.get_points())
            if points:
                return float(points[0].get('last', 0.0))
            return 0.0
        except Exception as e:
            logger.error(f"Erro ao buscar histórico de produção: {e}")
            return 0.0

    def process(self, eq_code, op, sku, counter, format_g, client):
        state = self.states.get(eq_code)
        
        # Inicializa estado se não existir (primeira execução ou restart)
        if not state:
            state = {
                'op': None,
                'sku': None,
                'last_count': counter, # Assume contador atual como base inicial
                'acc_op': 0.0,
                'acc_sku': 0.0
            }
            # Tenta recuperar estado anterior se for a mesma OP (caso de restart do Flask)
            if op:
                last_op_val = self.get_last_accumulated(client, eq_code, 'ordem_producao', op, 'producao_acumulada_op')
                if last_op_val > 0:
                    state['op'] = op
                    state['acc_op'] = last_op_val
                    logger.info(f"[RESUME] Retomando OP {op} com {last_op_val} ton")
            
            if sku:
                last_sku_val = self.get_last_accumulated(client, eq_code, 'sku_codigo', sku, 'producao_acumulada_sku')
                if last_sku_val > 0:
                    state['sku'] = sku
                    state['acc_sku'] = last_sku_val

            self.states[eq_code] = state

        # Detecta Mudança de OP
        if state['op'] != op:
            logger.info(f"[OP CHANGE] {state['op']} -> {op}")
            # Busca valor acumulado da NOVA OP (Resume Logic)
            prev_acc = 0.0
            if op:
                prev_acc = self.get_last_accumulated(client, eq_code, 'ordem_producao', op, 'producao_acumulada_op')
            
            state['op'] = op
            state['acc_op'] = prev_acc
            state['last_count'] = counter # Reseta referência do delta para o momento da troca
            logger.info(f"[OP START] Iniciando OP {op} com {prev_acc} ton")

        # Detecta Mudança de SKU
        if state['sku'] != sku:
            logger.info(f"[SKU CHANGE] {state['sku']} -> {sku}")
            prev_acc = 0.0
            if sku:
                prev_acc = self.get_last_accumulated(client, eq_code, 'sku_codigo', sku, 'producao_acumulada_sku')
            
            state['sku'] = sku
            state['acc_sku'] = prev_acc
            state['last_count'] = counter

        # Calcula Delta
        delta = counter - state['last_count']
        
        # Tratamento de Reset do PLC ou Rollover
        if delta < 0:
            logger.warning(f"[COUNTER RESET] Contador reiniciou: {state['last_count']} -> {counter}")
            delta = counter # Assume que resetou e produziu 'counter' peças
        
        # Calcula Produção em Toneladas
        prod_ton = (delta * format_g) / 1000000.0
        
        # Atualiza Acumuladores
        state['acc_op'] += prod_ton
        state['acc_sku'] += prod_ton
        state['last_count'] = counter
        
        return state['acc_op'], state['acc_sku']

# Instância global
production_counter = ProductionCounter()


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
    global acumuladores_op, acumuladores_sku # Declare global to modify
    data = None
    try:
        data = request.json
        
        # Log do payload para debug
        # logger.info(f"Payload recebido: {json.dumps(data)}")
        
        equipamento_codigo = data.get('equipamento_codigo') or data.get('equipamento')
        linha_codigo = data.get('linha_codigo', '')
        
        # Normalização de código de linha (Fix temporário para compatibilidade)
        if linha_codigo == '1':
            linha_codigo = 'L01'
        elif linha_codigo == '2':
            linha_codigo = 'L02'
            
        medicoes = data.get('medicoes', {})

        timestamp = data.get('timestamp')
        
        # Garante tipos corretos
        if 'descarte' in medicoes:
            try:
                medicoes['descarte'] = int(float(medicoes['descarte']))
            except (ValueError, TypeError):
                pass

        
        if not equipamento_codigo or not medicoes:
            logger.warning(f"Payload inválido: {data}")
            return jsonify({'error': 'equipamento_codigo e medicoes são obrigatórios'}), 400
        
        # ===== ACUMULAÇÃO DE PRODUÇÃO POR OP E SKU (STATEFUL) =====
        ordem_producao = medicoes.get('ordem_producao', '')
        sku_codigo = medicoes.get('sku_codigo', '')
        contagem_saida = float(medicoes.get('contagem_saida', 0))
        formato_gramas = float(medicoes.get('formato_gramas', 0))
        
        # Processa acumulação usando a classe robusta
        acc_op, acc_sku = production_counter.process(
            equipamento_codigo, 
            ordem_producao, 
            sku_codigo, 
            contagem_saida, 
            formato_gramas, 
            influx_client
        )
        
        medicoes['producao_acumulada_op'] = acc_op
        medicoes['producao_acumulada_sku'] = acc_sku
        
        logger.info(f"[PROD] OP={ordem_producao}: {acc_op:.3f} ton | SKU={sku_codigo}: {acc_sku:.3f} ton")
        
        # ===== AUTO-CRIAÇÃO DE OP NO MYSQL (NOVO) =====
        if ordem_producao and ordem_producao != '':
            try:
                # Extrair dados adicionais se disponíveis
                descricao_op = medicoes.get('descricao', '') or medicoes.get('produto_descricao', '')
                meta_producao = medicoes.get('meta_producao') or medicoes.get('meta', 0)
                
                # Tentar criar OP no Django automaticamente
                response = requests.post(
                    f"{DJANGO_API_URL}/bi/ordens-producao/auto_create_or_get/",
                    json={
                        'codigo_op': ordem_producao,
                        'codigo_linha': linha_codigo,
                        'codigo_sku': sku_codigo,
                        'formato_gramas': formato_gramas,
                        'descricao': descricao_op,
                        'meta_producao': meta_producao
                    },
                    timeout=2  # Timeout curto para não atrasar coleta
                )
                
                if response.status_code in [200, 201]:
                    op_data = response.json()
                    if op_data.get('created'):
                        logger.info(f"[OP AUTO-CRIADA] OP {ordem_producao} criada no MySQL")
                    # Se já existia, não loga (evita spam)
            except Exception as e:
                # Não falha a coleta se auto-criação de OP falhar
                logger.warning(f"[OP AUTO] Erro ao auto-criar OP {ordem_producao}: {e}")
        
        # ===== DETECÇÃO REATIVA DE MUDANÇA DE TURNO =====
        # Detectar turno atual baseado no horário
        hora_atual = datetime.now().hour
        
        # Turnos padrão (ajuste conforme sua configuração)
        # A: 06:00-14:00, B: 14:00-22:00, C: 22:00-06:00
        if 6 <= hora_atual < 14:
            turno_atual = 'A'
        elif 14 <= hora_atual < 22:
            turno_atual = 'B'
        else:
            turno_atual = 'C'
        
        # Detectar mudança de turno e disparar consolidação
        if linha_codigo:
            shift_detector.detect_and_consolidate(linha_codigo, turno_atual)
        
        # ===== EXTRAI TAGS DO MEDICOES =====
        # CRÍTICO: Extrai DEPOIS de calcular producao_acumulada_op/sku
        # ordem_producao, sku_codigo e formato_gramas devem ser TAGS, não fields
        # Isso permite filtrar eficientemente por OP, SKU e formato nas queries
        ordem_producao_tag = str(medicoes.pop('ordem_producao', ''))
        sku_codigo_tag = str(medicoes.pop('sku_codigo', ''))
        formato_gramas_tag = str(medicoes.pop('formato_gramas', 0))
        descricao_tag = str(medicoes.pop('descricao', ''))
        
        # Prepara ponto de dados com tags separadas dos fields
        json_body = [{
            "measurement": "producao",
            "tags": {
                "equipamento_codigo": equipamento_codigo,
                "linha_codigo": linha_codigo,
                "ordem_producao": ordem_producao_tag,
                "sku_codigo": sku_codigo_tag,
                "formato_gramas": formato_gramas_tag,
                "descricao": descricao_tag
            },
            "time": timestamp if timestamp else datetime.utcnow().isoformat(),
            "fields": medicoes  # Agora inclui producao_acumulada_op e producao_acumulada_sku
        }]
        
        logger.info(f"[INFLUX] Tags: OP={ordem_producao_tag}, SKU={sku_codigo_tag}, Formato={formato_gramas_tag}")
        
        if not influx_client:
            logger.error("Cliente InfluxDB não disponível")
            return jsonify({'error': 'Banco de dados indisponível'}), 503
        
        # Insere no InfluxDB
        # Insere no InfluxDB
        influx_client.write_points(json_body)
        
        logger.info(f"✓ Dados inseridos: {equipamento_codigo}")

        # ===== LÓGICA DE PERDA ESTRATÉGICA (USER REQUEST) =====
        try:
            status_maquina = int(medicoes.get('estado', 1)) # 1=Run, 0=Stop (assumindo)
            # Se estado for diferente de 1 (RUN), considera parada
            # Ajuste conforme sua lógica de PLC (ex: 1=Run, 2=Stop, etc)
            is_stopped = (status_maquina == 0) 
            
            codigo_evento = medicoes.get('codigo_evento', 'OUTRO')
            velocidade_nominal = float(medicoes.get('velocidade_nominal', 0))
            
            # URL da API Django
            django_url = DJANGO_API_URL
            
            if is_stopped:
                # 1. InfluxDB: Ping de Perda (Sangramento)
                # Assume que este ping representa o intervalo desde a última coleta (ex: 1s)
                # Se o coletor manda a cada 1s, perda_segundos = 1
                perda_segundos = 1 
                perda_ton = (perda_segundos / 3600.0) * velocidade_nominal if velocidade_nominal else 0
                
                loss_point = [{
                    "measurement": "perda_tempo_real",
                    "tags": {
                        "equipamento_codigo": equipamento_codigo,
                        "linha_codigo": linha_codigo,
                        "evento_clp": codigo_evento,
                        "turno": medicoes.get('turno', 'A'), # Precisa vir do coletor ou calculado
                        "sku": sku_codigo_tag
                    },
                    "fields": {
                        "perda_ton": float(perda_ton),
                        "perda_segundos": int(perda_segundos)
                    }
                }]
                influx_client.write_points(loss_point)
                
                # 2. MySQL: Garante evento aberto
                # Verifica se já tem evento aberto para esta máquina via API
                # Otimização: Poderia cachear isso no Flask, mas vamos via API por segurança
                try:
                    resp = requests.get(f"{django_url}/eventos-parada/abertos/?maquina={equipamento_codigo}")
                    abertos = resp.json()
                    
                    if not abertos:
                        # Cria novo evento
                        requests.post(f"{django_url}/eventos-parada/", json={
                            "maquina": equipamento_codigo,
                            "op": ordem_producao_tag,
                            "turno": medicoes.get('turno', 'A'),
                            "sku": sku_codigo_tag,
                            "inicio": timestamp if timestamp else datetime.utcnow().isoformat(),
                            "categoria_clp": codigo_evento
                        })
                except Exception as e:
                    logger.error(f"Erro ao gerenciar evento MySQL (Open): {e}")
                    
            else:
                # Máquina Rodando: Fecha eventos abertos
                try:
                    resp = requests.get(f"{django_url}/eventos-parada/abertos/?maquina={equipamento_codigo}")
                    abertos = resp.json()
                    
                    for evento in abertos:
                        # Fecha evento
                        requests.patch(f"{django_url}/eventos-parada/{evento['id']}/", json={
                            "fim": timestamp if timestamp else datetime.utcnow().isoformat()
                        })
                except Exception as e:
                    logger.error(f"Erro ao gerenciar evento MySQL (Close): {e}")
                    
        except Exception as e:
            logger.error(f"Erro na lógica de perda estratégica: {e}")

        return jsonify({'status': 'success', 'message': 'Dados inseridos com sucesso'})
    
    except Exception as e:
        logger.error(f"✗ Erro ao inserir dados: {e}. Dados: {data}")
        return jsonify({'error': 'Falha ao salvar dados', 'details': str(e)}), 500


@app.route('/api/realtime/status/<equipamento_codigo>', methods=['GET'])
def get_realtime_status(equipamento_codigo):
    """
    Retorna status em tempo real de um equipamento
    """
    try:
        if not influx_client:
            logger.error("Cliente InfluxDB não disponível")
            return jsonify({'error': 'Banco de dados indisponível'}), 503
        
        # Busca dados mais recentes
        query = f"""
            SELECT * FROM producao
            WHERE equipamento_codigo = '{equipamento_codigo}'
            ORDER BY time DESC 
            LIMIT 1
        """
        
        result = influx_client.query(query)
        points = list(result.get_points())
        
        if not points:
            logger.info(f"Sem dados para {equipamento_codigo}")
            return jsonify({
                'equipamento': equipamento_codigo,
                'status': 'sem_dados',
                'message': 'Nenhum dado recente encontrado',
                'timestamp': datetime.now().isoformat()
            })
        
        # Formata resposta
        dados_tempo_real = points[0]
        dados_tempo_real.pop('time', None)
        
        response = {
            'equipamento': equipamento_codigo,
            'timestamp': datetime.now().isoformat(),
            'status': 'online',
            'medicoes': dados_tempo_real
        }
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"✗ Erro em /realtime/status/{equipamento_codigo}: {e}")
        return jsonify({'error': 'Erro ao buscar dados', 'details': str(e)}), 500


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
            FROM producao
            WHERE equipamento_codigo = '{equipamento_codigo}'
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
            FROM producao
            WHERE equipamento_codigo = '{equipamento_codigo}'
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
            FROM producao
            WHERE equipamento_codigo = '{equipamento_codigo}'
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