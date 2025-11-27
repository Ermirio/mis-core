import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from influxdb import InfluxDBClient
from decouple import config
from datetime import datetime, timedelta
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

app = Flask(__name__)
CORS(app)

# --- Configuração de Logging ---
app.logger.setLevel(logging.INFO)
app.logger.info("Iniciando configuração do logger...")
# ------------------------------

# --- Configurações da Aplicação (lidas do .env) ---
INFLUX_HOST = config('INFLUXDB_HOST', default='127.0.0.1')
INFLUX_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUX_DB = config('INFLUXDB_DATABASE', default='industrial_db')
INFLUX_USER = config('INFLUXDB_USER', default=None)
INFLUX_PASS = config('INFLUXDB_USER_PASSWORD', default=None)

DJANGO_API_URL = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')
AGREGACAO_HABILITADA = config('AGREGACAO_HABILITADA', default=True, cast=bool)
# ----------------------------------------------------

# --- Cliente InfluxDB ---
try:
    influx_client = InfluxDBClient(
        host=INFLUX_HOST, 
        port=INFLUX_PORT, 
        username=INFLUX_USER, 
        password=INFLUX_PASS, 
        database=INFLUX_DB
    )
    
    # Tenta criar o DB (só por garantia, não faz mal se já existir)
    influx_client.create_database(INFLUX_DB)
    
    app.logger.info(f"✓ Conectado ao InfluxDB e database '{INFLUX_DB}' verificado.")

except Exception as e:
    app.logger.error(f"FATAL: Não foi possível conectar ou criar database no InfluxDB. Erro: {e}")
# ----------------------------------------------------


# ===== ROTAS DE API =====

@app.route('/api/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({'status': 'ok', 'service': 'Flask API'})


@app.route('/api/dados/inserir', methods=['POST'])
def inserir_dados():
    """
    Insere dados no InfluxDB
    Recebe dados do Coletor e salva rapidamente
    
    ATUALIZADO: Agora aceita equipamento_codigo e linha_codigo
    
    Payload esperado:
    {
        "equipamento_codigo": "L01_ENCH_01",
        "linha_codigo": "L01",
        "medicoes": {
            "contagem_entrada": 1000,
            "contagem_saida": 995,
            "velocidade_atual": 98.5,
            "estado": 1,
            "temperatura": 25.3,
            "pressao": 45.2
        },
        "timestamp": "2024-01-15T10:30:00Z"
    }
    """
    data = None
    try:
        data = request.json
        
        # Suporta tanto o formato antigo (equipamento) quanto o novo (equipamento_codigo)
        equipamento_codigo = data.get('equipamento_codigo') or data.get('equipamento')
        linha_codigo = data.get('linha_codigo', '')
        medicoes = data.get('medicoes', {})
        timestamp = data.get('timestamp')
        
        if not equipamento_codigo or not medicoes:
            app.logger.warning(f"Payload inválido recebido: {data}. 'equipamento_codigo' ou 'medicoes' ausente.")
            return jsonify({'error': 'equipamento_codigo e medicoes são obrigatórios'}), 400
        
        # Prepara ponto de dados para InfluxDB
        json_body = [{
            "measurement": "producao",
            "tags": {
                "equipamento_codigo": equipamento_codigo,
                "linha_codigo": linha_codigo
            },
            "time": timestamp if timestamp else datetime.utcnow().isoformat(),
            "fields": medicoes
        }]
        
        # Insere no InfluxDB
        influx_client.write_points(json_body)
        
        app.logger.info(f"Dados inseridos com sucesso para equipamento: {equipamento_codigo}")
        return jsonify({'status': 'success', 'message': 'Dados inseridos com sucesso'})
    
    except Exception as e:
        app.logger.error(f"Falha ao inserir dados no InfluxDB. Erro: {e}. Dados recebidos: {data}")
        return jsonify({'error': 'Falha ao salvar dados no banco', 'details': str(e)}), 500


@app.route('/api/realtime/status/<equipamento_codigo>', methods=['GET'])
def get_realtime_status(equipamento_codigo):
    """
    Retorna status em tempo real de um equipamento.
    
    ATUALIZADO: Busca por equipamento_codigo (tag) em vez de equipamento (field)
    """
    try:
        # Busca dados em tempo real do InfluxDB
        query = f"""
            SELECT * FROM producao
            WHERE equipamento_codigo = '{equipamento_codigo}'
            ORDER BY time DESC 
            LIMIT 1
        """
        
        try:
            result = influx_client.query(query)
            points = list(result.get_points())
        except Exception as e:
            app.logger.error(f"Falha ao consultar InfluxDB para {equipamento_codigo}. Query: {query}. Erro: {e}")
            return jsonify({'error': 'Falha ao buscar dados do banco (InfluxDB)', 'details': str(e)}), 500
        
        if not points:
            app.logger.info(f"Nenhum dado encontrado para {equipamento_codigo} no InfluxDB (último ponto).")
            return jsonify({
                'equipamento': equipamento_codigo,
                'status': 'sem_dados',
                'message': 'Nenhum dado recente encontrado',
                'timestamp': datetime.now().isoformat()
            })
        
        # points[0] contém o ponto de dado mais recente
        dados_tempo_real = points[0]
        dados_tempo_real.pop('time', None)
        
        # Retorna apenas os dados de tempo real
        response = {
            'equipamento': equipamento_codigo,
            'timestamp': datetime.now().isoformat(),
            'status': 'online',
            'medicoes': dados_tempo_real
        }
        
        return jsonify(response)
    
    except Exception as e:
        app.logger.error(f"Erro ao processar /realtime/status para {equipamento_codigo}. Erro: {e}", exc_info=True)
        return jsonify({'error': 'Erro interno no servidor', 'details': str(e)}), 500


@app.route('/api/realtime/variaveis/<equipamento_codigo>', methods=['GET'])
def get_process_variables(equipamento_codigo):
    """
    Retorna variáveis de processo em tempo real (últimos 2 minutos)
    """
    try:
        query = f"""
            SELECT *
            FROM producao
            WHERE equipamento_codigo = '{equipamento_codigo}'
            AND time > now() - 2m
            ORDER BY time DESC
            LIMIT 20
        """
        
        result = influx_client.query(query)
        points = list(result.get_points())
        
        if not points:
            app.logger.info(f"Nenhum dado (2m) encontrado para {equipamento_codigo} em /realtime/variaveis.")
            return jsonify({'error': 'Nenhum dado encontrado'}), 404
        
        points.reverse()
        
        return jsonify({
            'equipamento': equipamento_codigo,
            'timestamp': datetime.now().isoformat(),
            'dados': points
        })
    
    except Exception as e:
        app.logger.error(f"Falha ao consultar InfluxDB em /realtime/variaveis para {equipamento_codigo}. Erro: {e}")
        return jsonify({'error': 'Falha ao consultar banco de dados', 'details': str(e)}), 500


@app.route('/api/historico/<equipamento_codigo>', methods=['GET'])
def get_historico(equipamento_codigo):
    """
    Retorna histórico agregado por hora
    """
    try:
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
        app.logger.error(f"Falha ao consultar InfluxDB em /historico para {equipamento_codigo}. Erro: {e}")
        return jsonify({'error': 'Falha ao consultar banco de dados', 'details': str(e)}), 500


# ===== AGREGADOR DE DADOS COM CÁLCULO REAL DE OEE =====

def calcular_tempos_por_estado(equipamento_id, inicio, fim):
    """
    Consulta eventos de estado no Django e calcula tempos por categoria
    
    Retorna dict com:
    - tempo_producao (RUN)
    - tempo_parada (FAULT, FALTA_MAT, AGUARD_MNT, WAIT_PREV, BLOCK_NEXT)
    - tempo_setup (SETUP)
    - tempo_nao_programado (MANUTENCAO, TESTE_PROJ)
    """
    try:
        url = f'{DJANGO_API_URL}/eventos-estado/'
        params = {
            'equipamento_id': equipamento_id,
            'inicio': inicio.isoformat(),
            'fim': fim.isoformat()
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        eventos = response.json().get('results', [])
        
        tempos = {
            'tempo_producao': 0,
            'tempo_parada': 0,
            'tempo_setup': 0,
            'tempo_nao_programado': 0,
        }
        
        # Mapeamento de estados para categorias
        estados_producao = ['RUN']
        estados_parada = ['FAULT', 'FALTA_MAT', 'AGUARD_MNT', 'WAIT_PREV', 'BLOCK_NEXT']
        estados_setup = ['SETUP']
        estados_nao_programado = ['MANUTENCAO', 'TESTE_PROJ']
        
        for evento in eventos:
            duracao_segundos = evento.get('duracao_segundos', 0)
            if duracao_segundos <= 0:
                continue
            
            estado = evento.get('estado')
            duracao_minutos = duracao_segundos / 60.0
            
            if estado in estados_producao:
                tempos['tempo_producao'] += duracao_minutos
            elif estado in estados_parada:
                tempos['tempo_parada'] += duracao_minutos
            elif estado in estados_setup:
                tempos['tempo_setup'] += duracao_minutos
            elif estado in estados_nao_programado:
                tempos['tempo_nao_programado'] += duracao_minutos
        
        return tempos
        
    except Exception as e:
        app.logger.error(f"Erro ao buscar eventos de estado: {e}")
        # Retorna tempos zerados em caso de erro
        return {
            'tempo_producao': 0,
            'tempo_parada': 0,
            'tempo_setup': 0,
            'tempo_nao_programado': 0,
        }


def agregar_metricas_hora():
    """
    Tarefa agendada: Agrega métricas por hora e envia para o Django
    
    ATUALIZADO: Agora calcula OEE real baseado em eventos de estado
    
    Esta função:
    1. Consulta o InfluxDB para dados da última hora
    2. Consulta o Django para eventos de estado
    3. Calcula tempos por estado
    4. Calcula KPIs reais (Disponibilidade, Performance, Qualidade, OEE)
    5. Envia para o endpoint /api/metricas_consolidadas/ do Django
    """
    try:
        app.logger.info("=== Iniciando agregação horária com cálculo real de OEE ===")
        
        # Busca lista de equipamentos únicos no InfluxDB
        query = """
            SHOW TAG VALUES FROM producao WITH KEY = "equipamento_codigo"
        """
        
        result = influx_client.query(query)
        equipamentos_codigos = [item['value'] for item in result.get_points()]
        
        if not equipamentos_codigos:
            app.logger.warning("Nenhum equipamento encontrado no InfluxDB")
            return
        
        app.logger.info(f"Agregando dados de {len(equipamentos_codigos)} equipamento(s)")
        
        # Define intervalo da última hora
        fim = datetime.now().replace(minute=0, second=0, microsecond=0)
        inicio = fim - timedelta(hours=1)
        
        # Para cada equipamento, agrega dados da última hora
        for equipamento_codigo in equipamentos_codigos:
            try:
                # Query para agregar dados da última hora
                query = f"""
                    SELECT 
                        mean("velocidade_atual") as velocidade_media,
                        max("contagem_entrada") - min("contagem_entrada") as producao_entrada,
                        max("contagem_saida") - min("contagem_saida") as producao_saida,
                        count("velocidade_atual") as total_leituras
                    FROM producao
                    WHERE equipamento_codigo = '{equipamento_codigo}'
                    AND time >= '{inicio.isoformat()}Z'
                    AND time < '{fim.isoformat()}Z'
                """
                
                result = influx_client.query(query)
                points = list(result.get_points())
                
                if not points or not points[0].get('total_leituras'):
                    app.logger.info(f"Sem dados para agregar: {equipamento_codigo}")
                    continue
                
                dados = points[0]
                
                # Busca informações do equipamento no Django
                try:
                    django_url = f'{DJANGO_API_URL}/equipamentos/'
                    response = requests.get(django_url, timeout=10)
                    response.raise_for_status()
                    equipamentos_django = response.json().get('results', [])
                    
                    eq_info = next((eq for eq in equipamentos_django if eq['codigo'] == equipamento_codigo), None)
                    
                    if not eq_info:
                        app.logger.warning(f"Equipamento {equipamento_codigo} não encontrado no Django")
                        continue
                    
                except Exception as e:
                    app.logger.error(f"Erro ao buscar info do equipamento {equipamento_codigo}: {e}")
                    continue
                
                # Busca eventos de estado do Django
                tempos = calcular_tempos_por_estado(eq_info['id'], inicio, fim)
                
                # Extrai dados agregados
                contagem_entrada = int(dados.get('producao_entrada') or 0)
                contagem_saida = int(dados.get('producao_saida') or 0)
                velocidade_real = float(dados.get('velocidade_media') or 0)
                velocidade_planejada = float(eq_info.get('velocidade_nominal', 0))
                
                # Tempos (em minutos)
                tempo_programado = 60.0  # 1 hora
                tempo_producao = tempos['tempo_producao']
                tempo_parada = tempos['tempo_parada']
                tempo_setup = tempos['tempo_setup']
                tempo_nao_programado = tempos['tempo_nao_programado']
                tempo_disponivel = tempo_programado - tempo_nao_programado
                
                # Calcula KPIs REAIS
                # Disponibilidade (A) = tempo_producao / tempo_disponivel * 100
                if tempo_disponivel > 0:
                    disponibilidade = min(100, (tempo_producao / tempo_disponivel) * 100)
                else:
                    disponibilidade = 0.0
                
                # Performance (P) = producao_real / producao_teorica * 100
                if tempo_producao > 0 and velocidade_planejada > 0:
                    producao_teorica = velocidade_planejada * tempo_producao
                    if producao_teorica > 0:
                        performance = min(100, (contagem_saida / producao_teorica) * 100)
                    else:
                        performance = 0.0
                else:
                    performance = 0.0
                
                # Qualidade (Q) = producao_saida / producao_entrada * 100
                if contagem_entrada > 0:
                    qualidade = min(100, (contagem_saida / contagem_entrada) * 100)
                else:
                    qualidade = 0.0
                
                # OEE = (A * P * Q) / 10000
                oee = (disponibilidade * performance * qualidade) / 10000
                
                # Payload para enviar ao Django
                payload = {
                    'linha_id': eq_info['linha'],
                    'equipamento_id': eq_info['id'],
                    'data_hora': fim.isoformat(),
                    'periodo': 'HORA',
                    'contagem_entrada': contagem_entrada,
                    'contagem_saida': contagem_saida,
                    'velocidade_planejada': velocidade_planejada,
                    'velocidade_real': velocidade_real,
                    'tempo_programado': tempo_programado,
                    'tempo_disponivel': tempo_disponivel,
                    'tempo_producao': tempo_producao,
                    'tempo_parada': tempo_parada,
                    'tempo_setup': tempo_setup,
                    'tempo_nao_programado': tempo_nao_programado,
                    'disponibilidade': disponibilidade,
                    'performance': performance,
                    'qualidade': qualidade,
                    'oee': oee
                }
                
                # Envia para Django
                django_url = f'{DJANGO_API_URL}/metricas_consolidadas/'
                response = requests.post(django_url, json=payload, timeout=10)
                response.raise_for_status()
                
                app.logger.info(
                    f"✓ Métrica agregada enviada: {equipamento_codigo} - "
                    f"A={disponibilidade:.1f}% P={performance:.1f}% Q={qualidade:.1f}% OEE={oee:.1f}%"
                )
                
            except Exception as e:
                app.logger.error(f"Erro ao agregar dados de {equipamento_codigo}: {e}")
                continue
        
        app.logger.info("=== Agregação horária concluída ===")
        
    except Exception as e:
        app.logger.error(f"Erro na agregação horária: {e}", exc_info=True)


# ===== SCHEDULER =====

if AGREGACAO_HABILITADA:
    scheduler = BackgroundScheduler()
    
    # Agenda agregação a cada hora (no minuto 5)
    scheduler.add_job(
        func=agregar_metricas_hora,
        trigger=CronTrigger(minute=5),
        id='agregacao_horaria',
        name='Agregação de métricas por hora',
        replace_existing=True
    )
    
    scheduler.start()
    app.logger.info("✓ Scheduler de agregação iniciado (executa a cada hora com cálculo real de OEE)")
else:
    app.logger.info("Agregação desabilitada via configuração")


# ===== INICIALIZAÇÃO =====

if __name__ == '__main__':
    print("🚀 Flask API iniciando...")
    print(f" MODE: {'DEBUG' if app.debug else 'PRODUCTION'}")
    print(f"InfluxDB: {INFLUX_HOST}:{INFLUX_PORT}/{INFLUX_DB}")
    print(f"Django API: {DJANGO_API_URL}")
    print(f"Agregação: {'HABILITADA (com cálculo real de OEE)' if AGREGACAO_HABILITADA else 'DESABILITADA'}")
    app.run(host='0.0.0.0', port=5000, debug=True)
