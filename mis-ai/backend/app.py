import asyncio
import logging
import os
import threading
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import func, exc

from ml_model import generic_predictor
from models import (Line, PredictionTarget, PredictionModel, PredictionData, 
                    OPCLogs, OPCVariables, OPCServerConfig, create_default_data, create_tables, get_db)
from opc_client import opc_client, OPCClient
from influx_client import influx_client

# ==================== CONFIGURAÇÕES INICIAIS ====================
load_dotenv()
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s",
    handlers=[logging.FileHandler("logs/app.log"), logging.StreamHandler()]
)

# ==================== CRIAÇÃO DO APP FLASK ====================
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ==================== INICIALIZAÇÃO DO BANCO DE DADOS ====================
try:
    os.makedirs("logs", exist_ok=True)
    create_tables()
    create_default_data()
    logging.info("✅ Banco de dados inicializado com sucesso.")
except Exception as e:
    logging.critical("❌ FALHA CRÍTICA ao inicializar o banco de dados.", exc_info=True)
    exit(1)

# ==================== INICIALIZAÇÃO INFLUXDB ====================
try:
    if influx_client.connect():
        influx_client.create_database()
        logging.info("✅ InfluxDB inicializado e banco 'mis-ai' verificado.")
    else:
        logging.warning("⚠️ Falha ao conectar ao InfluxDB na inicialização.")
except Exception as e:
    logging.error(f"❌ Erro ao inicializar InfluxDB: {e}", exc_info=True)

# ==================== INICIALIZAÇÃO DO OPC (PRODUÇÃO) ====================
# Esta seção roda automaticamente quando o módulo é importado pelo Gunicorn
# Garante que o OPC seja inicializado apenas uma vez, no worker master

_opc_initialized = False

def initialize_opc():
    """Inicializa o cliente OPC em uma thread separada"""
    global _opc_initialized
    
    if _opc_initialized:
        logging.info("⚠️  OPC já foi inicializado, pulando...")
        return
    
    _opc_initialized = True
    
    try:
        main_loop = asyncio.new_event_loop()
        opc_client.loop = main_loop
        
        # --- LÓGICA DE INICIALIZAÇÃO DINÂMICA ---
        db = next(get_db())
        try:
            config = db.query(OPCServerConfig).first()
            if config:
                logging.info(f"⚙️  Usando configuração OPC salva no banco: {config.opc_url}")
                opc_client.url = config.opc_url
            else:
                default_url = os.getenv('OPC_SERVER_URL', 'opc.tcp://host.docker.internal:4840')
                logging.info(f"⚙️  Nenhuma configuração salva. Usando padrão/env: {default_url}")
                
                # Salvar o padrão no banco para ser editável
                new_config = OPCServerConfig(opc_url=default_url, is_active=True)
                db.add(new_config)
                db.commit()
                opc_client.url = default_url
        except Exception as db_e:
            logging.error(f"⚠️ Erro ao carregar config do banco (pode ser a primeira execução): {db_e}")
            # Fallback para env var sem salvar no banco se der erro de DB
            opc_client.url = os.getenv('OPC_SERVER_URL', 'opc.tcp://host.docker.internal:4840')
        finally:
            db.close()
        # ----------------------------------------

        logging.info(f"🔌 Tentando conectar ao servidor OPC: {opc_client.url}")
        
        # Conectar ao OPC de forma assíncrona
        is_connected = main_loop.run_until_complete(opc_client.connect())
        
        if not is_connected:
            logging.warning("⚠️  Falha ao conectar ao servidor OPC. O sistema continuará tentando ou aguardará reconfiguração.")
        else:
            logging.info("✅ Conexão OPC estabelecida com sucesso.")
        
        # Função para rodar o loop em background
        def run_loop_in_thread(loop):
            asyncio.set_event_loop(loop)
            try:
                loop.run_forever()
            except Exception as e:
                logging.error(f"❌ Erro no loop OPC: {e}", exc_info=True)
        
        # Iniciar thread do OPC
        background_thread = threading.Thread(
            target=run_loop_in_thread, 
            args=(main_loop,), 
            daemon=True,
            name="OPC-Background-Thread"
        )
        background_thread.start()
        
        logging.info("🔌 Loop OPC iniciado com sucesso em thread separada.")
        
    except Exception as e:
        logging.error(f"❌ Erro ao inicializar OPC: {e}", exc_info=True)

# Inicializar OPC automaticamente quando o módulo é carregado
# Isso acontece quando o Gunicorn importa o app
initialize_opc()

logging.info("✅ Backend iniciado e pronto para conexões via Gunicorn.")

# ==================== ROTAS DA API ====================

@app.route('/')
def home():
    return jsonify({'message': 'Generic Prediction App Backend is running!'})

@app.route('/api/health')
def health_check():
    db = next(get_db())
    try:
        from sqlalchemy import text
        db.execute(text('SELECT 1'))
        opc_status = 'connected' if opc_client.connected else 'disconnected'
        return jsonify({
            'status': 'healthy', 
            'database': 'connected', 
            'opc_client': opc_status
        })
    finally:
        db.close()

# --- ROTAS PARA LINHAS ---
@app.route('/api/lines', methods=['GET'])
def get_lines():
    db = next(get_db())
    try:
        lines = db.query(Line).order_by(Line.name).all()
        return jsonify([line.to_dict() for line in lines]), 200
    finally:
        db.close()

@app.route('/api/lines', methods=['POST'])
def create_line():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Nome da linha é obrigatório'}), 400
    
    db = next(get_db())
    try:
        existing = db.query(Line).filter(Line.name == data['name']).first()
        if existing:
            return jsonify({'error': 'Linha já existe'}), 400
        
        new_line = Line(name=data['name'], description=data.get('description', ''), is_active=True)
        db.add(new_line)
        db.commit()
        return jsonify({'message': 'Linha criada com sucesso', 'line': new_line.to_dict()}), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/lines/<int:line_id>', methods=['PUT'])
def update_line(line_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados são obrigatórios'}), 400
    
    db = next(get_db())
    try:
        line = db.query(Line).filter(Line.id == line_id).first()
        if not line:
            return jsonify({'error': 'Linha não encontrada'}), 404
        
        if 'name' in data:
            existing = db.query(Line).filter(Line.name == data['name'], Line.id != line_id).first()
            if existing:
                return jsonify({'error': 'Nome da linha já existe'}), 400
            line.name = data['name']
        
        if 'description' in data:
            line.description = data['description']
        
        if 'is_active' in data:
            line.is_active = data['is_active']
        
        db.commit()
        return jsonify({'message': 'Linha atualizada com sucesso', 'line': line.to_dict()}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/lines/<int:line_id>', methods=['DELETE'])
def delete_line(line_id):
    db = next(get_db())
    try:
        line = db.query(Line).filter(Line.id == line_id).first()
        if not line:
            return jsonify({'error': 'Linha não encontrada'}), 404
        
        db.delete(line)
        db.commit()
        
        return jsonify({'message': 'Linha excluída permanentemente com sucesso'}), 200
    except exc.IntegrityError:
        db.rollback()
        return jsonify({'error': 'Não é possível excluir a linha pois ela possui dados associados (targets, etc.).'}), 409
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

# --- ROTAS PARA TARGETS ---
@app.route('/api/targets', methods=['GET'])
def get_targets():
    line_name = request.args.get('line')
    if not line_name:
        return jsonify({'error': 'Parâmetro line é obrigatório'}), 400
    
    db = next(get_db())
    try:
        targets = db.query(PredictionTarget).filter(PredictionTarget.line_name == line_name).order_by(PredictionTarget.target_name).all()
        return jsonify([target.to_dict() for target in targets]), 200
    finally:
        db.close()

@app.route('/api/targets', methods=['POST'])
def create_target():
    data = request.get_json()
    if not data or 'line_name' not in data or 'target_name' not in data:
        return jsonify({'error': 'Campos obrigatórios: line_name, target_name'}), 400
    
    success, message = generic_predictor.create_target(
        line_name=data['line_name'],
        target_name=data['target_name'],
        target_unit=data.get('target_unit', ''),
        description=data.get('description', '')
    )
    
    if success:
        return jsonify({'message': message}), 201
    else:
        return jsonify({'error': message}), 400

@app.route('/api/targets/<int:target_id>', methods=['PUT'])
def update_target(target_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados são obrigatórios'}), 400

    db = next(get_db())
    try:
        target = db.query(PredictionTarget).filter(PredictionTarget.id == target_id).first()
        if not target:
            return jsonify({'error': 'Target não encontrado'}), 404

        if 'target_name' in data: target.target_name = data['target_name']
        if 'target_unit' in data: target.target_unit = data['target_unit']
        if 'description' in data: target.description = data['description']
        if 'is_active' in data: target.is_active = data['is_active']
        
        db.commit()
        return jsonify({'message': 'Target atualizado com sucesso', 'target': target.to_dict()}), 200
    except Exception as e:
        db.rollback()
        logging.error("Erro ao atualizar target %s: %s", target_id, e)
        return jsonify({'error': 'Erro interno ao atualizar o target'}), 500
    finally:
        db.close()

@app.route('/api/targets/<int:target_id>', methods=['DELETE'])
def delete_target(target_id):
    db = next(get_db())
    try:
        target = db.query(PredictionTarget).filter(PredictionTarget.id == target_id).first()
        if not target:
            return jsonify({'error': 'Target não encontrado'}), 404
        
        db.delete(target)
        db.commit()
        return jsonify({'message': 'Target excluído permanentemente com sucesso'}), 200
    except exc.IntegrityError:
        db.rollback()
        return jsonify({'error': 'Não é possível excluir o target pois ele possui modelos ou dados associados.'}), 409
    except Exception as e:
        db.rollback()
        logging.error("Erro ao excluir target %s: %s", target_id, e)
        return jsonify({'error': 'Erro interno ao excluir o target'}), 500
    finally:
        db.close()

# --- ROTAS PARA MODELOS ---
@app.route('/api/models', methods=['GET'])
def get_models():
    target_id = request.args.get('target_id')
    if not target_id:
        return jsonify({'error': 'Parâmetro target_id é obrigatório'}), 400
    try:
        target_id = int(target_id)
        models = generic_predictor.get_available_models(target_id)
        return jsonify(models), 200
    except ValueError:
        return jsonify({'error': 'target_id deve ser um número'}), 400

@app.route('/api/models', methods=['POST'])
def create_model():
    data = request.get_json()
    required_fields = ['target_id', 'model_name']
    if not data or not all(field in data for field in required_fields):
        return jsonify({'error': 'Campos obrigatórios: target_id, model_name'}), 400
    success, message = generic_predictor.create_model(
        target_id=data['target_id'], 
        model_name=data['model_name'], 
        model_type=data.get('model_type', 'RandomForest'), 
        parameters=data.get('parameters')
    )
    if success: 
        return jsonify({'message': message}), 201
    else: 
        return jsonify({'error': message}), 400

@app.route('/api/models/<int:model_id>', methods=['PUT'])
def update_model(model_id):
    data = request.get_json()
    if not data: 
        return jsonify({'error': 'Dados são obrigatórios'}), 400
    db = next(get_db())
    try:
        model = db.query(PredictionModel).filter(PredictionModel.id == model_id).first()
        if not model: 
            return jsonify({'error': 'Modelo não encontrado'}), 404
        if 'model_name' in data: model.model_name = data['model_name']
        if 'model_type' in data: model.model_type = data['model_type']
        if 'parameters' in data: model.model_parameters = data['parameters']
        if 'is_active' in data: model.is_active = data['is_active']
        db.commit()
        return jsonify({'message': 'Modelo atualizado com sucesso', 'model': model.to_dict()}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/models/<int:model_id>', methods=['DELETE'])
def delete_model(model_id):
    db = next(get_db())
    try:
        model = db.query(PredictionModel).filter(PredictionModel.id == model_id).first()
        if not model: 
            return jsonify({'error': 'Modelo não encontrado'}), 404
        
        db.delete(model)
        db.commit()
        
        return jsonify({'message': 'Modelo excluído permanentemente com sucesso'}), 200
    except exc.IntegrityError:
        db.rollback()
        return jsonify({'error': 'Não é possível excluir o modelo pois ele possui dados associados.'}), 409
    except Exception as e:
        db.rollback()
        logging.error("Erro ao excluir modelo %s: %s", model_id, e)
        return jsonify({'error': 'Erro interno ao excluir o modelo'}), 500
    finally:
        db.close()

@app.route('/api/models/<int:model_id>/train', methods=['POST'])
def train_model(model_id):
    success, message = generic_predictor.train_model(model_id)
    if success:
        return jsonify({'message': message}), 200
    else:
        return jsonify({'error': message}), 500

@app.route('/api/models/<int:model_id>/status', methods=['GET'])
def get_model_status(model_id):
    """Retorna o status completo e métricas de um modelo"""
    try:
        # Chama a função de lógica de negócio do ml_model.py
        status_data, message = generic_predictor.get_model_status(model_id)
        
        if status_data:
            return jsonify(status_data), 200
        else:
            return jsonify({'error': message}), 404
            
    except Exception as e:
        logging.error(f"Erro ao obter status do modelo {model_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/models/<int:model_id>/predict', methods=['POST'])
def predict_with_model(model_id):
    # 'success' agora contém o objeto de dados, 'result' contém a mensagem
    success, result = generic_predictor.predict(model_id) 
    
    if success: # Se 'success' (os dados) não for None
        return jsonify(success), 200 # <-- CORREÇÃO: Retorna 'success' (os dados)
    else:
        return jsonify({'error': result}), 500
    
    
# ==========================================================
# NOVA ROTA (PARA O DASHBOARD)
# ==========================================================
@app.route('/api/models/<int:model_id>/last_prediction', methods=['GET'])
def get_last_prediction(model_id):
    """Retorna a última predição salva para um modelo"""
    db = next(get_db())
    try:
        last_pred = db.query(PredictionData).filter(
            PredictionData.model_id == model_id,
            PredictionData.predicted_value != None
        ).order_by(PredictionData.timestamp.desc()).first()
        
        if not last_pred:
            return jsonify({'error': 'Nenhuma predição encontrada'}), 404
            
        return jsonify(last_pred.to_dict()), 200
    except Exception as e:
        logging.error(f"Erro ao buscar última predição: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
# ==========================================================
# FIM DA NOVA ROTA
# ==========================================================




# --- ROTAS PARA PREDIÇÕES CONTÍNUAS ---
@app.route('/api/predictions/continuous/start', methods=['POST'])
def start_continuous_predictions():
    data = request.get_json()
    if not data or 'model_id' not in data:
        return jsonify({'error': 'model_id é obrigatório'}), 400
    
    model_id = data['model_id']
    interval = data.get('interval', 60)
    
    success, message = generic_predictor.start_continuous_predictions(model_id, interval)
    if success:
        return jsonify({'message': message}), 200
    else:
        return jsonify({'error': message}), 400

@app.route('/api/predictions/continuous/stop', methods=['POST'])
def stop_continuous_predictions():
    data = request.get_json()
    if not data or 'model_id' not in data:
        return jsonify({'error': 'model_id é obrigatório'}), 400
    
    success, message = generic_predictor.stop_continuous_predictions(data['model_id'])
    if success:
        return jsonify({'message': message}), 200
    else:
        return jsonify({'error': message}), 400

@app.route('/api/predictions/continuous/status', methods=['GET'])
def get_continuous_predictions_status():
    model_id = request.args.get('model_id')
    if not model_id:
        return jsonify({'error': 'model_id é obrigatório'}), 400
    
    try:
        model_id = int(model_id)
        is_running = generic_predictor.is_continuous_predictions_active(model_id)
        return jsonify({'is_running': is_running}), 200
    except ValueError:
        return jsonify({'error': 'model_id deve ser um número'}), 400

# --- ROTAS PARA DADOS ---
@app.route('/api/data', methods=['GET'])
def get_data():
    target_id = request.args.get('target_id')
    if not target_id:
        return jsonify({'error': 'target_id é obrigatório'}), 400
    
    try:
        target_id = int(target_id)
    except ValueError:
        return jsonify({'error': 'target_id deve ser um número'}), 400
    
    db = next(get_db())
    try:
        data = db.query(PredictionData).filter(
            PredictionData.target_id == target_id
        ).order_by(PredictionData.timestamp.desc()).limit(100).all()
        
        return jsonify([d.to_dict() for d in data]), 200
    finally:
        db.close()

@app.route('/api/data/manual', methods=['POST'])
def save_manual_data():
    data = request.get_json()
    if not data or 'target_id' not in data or 'measured_value' not in data:
        return jsonify({'error': 'Campos obrigatórios: target_id, measured_value'}), 400
    
    db = next(get_db())
    try:
        target = db.query(PredictionTarget).filter(PredictionTarget.id == data['target_id']).first()
        if not target:
            return jsonify({'error': 'Target não encontrado'}), 404
        
        opc_values_json = None
        data_timestamp = None
        
        # CASO 1: "Associar com OPC" (envia log_timestamp)
        if 'log_timestamp' in data:
            log_time_obj = date_parser.parse(data['log_timestamp'])
            data_timestamp = log_time_obj
            
            # Buscar TODOS os logs daquele exato timestamp para montar o JSON
            logs = db.query(OPCLogs).filter(
                OPCLogs.line_name == target.line_name,
                OPCLogs.timestamp == log_time_obj
            ).all()
            
            if not logs:
                return jsonify({'error': 'Logs OPC não encontrados para o timestamp selecionado'}), 404
                
            # Montar o JSON opc_values que o modelo de treino espera
            opc_values_json = {log.node_id: log.value for log in logs}

        # CASO 2: "Dados Manuais" (envia timestamp)
        elif 'timestamp' in data:
            data_timestamp = date_parser.parse(data['timestamp'])
            # opc_values_json continua None, o que é correto
        
        else:
            return jsonify({'error': 'Timestamp (timestamp ou log_timestamp) é obrigatório'}), 400

        # Salvar no banco
        new_data = PredictionData(
            target_id=data['target_id'],
            measured_value=data['measured_value'],
            timestamp=data_timestamp,
            opc_values=opc_values_json, # <--- Salva o JSON de features
            data_source='manual'
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)
        
        return jsonify({'message': 'Dado salvo com sucesso', 'data': new_data.to_dict()}), 201
    
    except Exception as e:
        db.rollback()
        logging.error(f"❌ Erro ao salvar dado manual: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

# ==================== ROTAS PARA OPC ====================

@app.route('/api/opc/status', methods=['GET'])
def get_opc_status():
    return jsonify({
        'connected': opc_client.connected,
        'server_url': os.getenv('OPC_SERVER_URL', 'Not configured')
    })

@app.route('/api/opc/connect', methods=['POST'])
def connect_opc():
    if opc_client.connected:
        return jsonify({'message': 'OPC já está conectado'}), 200
    
    success = asyncio.run_coroutine_threadsafe(opc_client.connect(), opc_client.loop).result()
    if success:
        return jsonify({'message': 'Conectado ao OPC com sucesso'}), 200
    else:
        return jsonify({'error': 'Falha ao conectar ao OPC'}), 500

@app.route('/api/opc/disconnect', methods=['POST'])
def disconnect_opc():
    if not opc_client.connected:
        return jsonify({'message': 'OPC já está desconectado'}), 200
    
    asyncio.run_coroutine_threadsafe(opc_client.disconnect(), opc_client.loop).result()
    return jsonify({'message': 'Desconectado do OPC com sucesso'}), 200

# --- ROTAS DE CONFIGURAÇÃO DE SERVIDOR OPC ---

@app.route('/api/opc/config', methods=['GET'])
def get_opc_config():
    """Retorna a configuração atual do servidor OPC"""
    db = next(get_db())
    try:
        config = db.query(OPCServerConfig).first()
        if not config:
            return jsonify({'opc_url': '', 'is_active': False}), 200
        return jsonify(config.to_dict()), 200
    finally:
        db.close()

@app.route('/api/opc/config', methods=['POST'])
def update_opc_config():
    """Atualiza a configuração do servidor OPC e reconecta"""
    data = request.get_json()
    if not data or 'opc_url' not in data:
        return jsonify({'error': 'Campo opc_url é obrigatório'}), 400

    db = next(get_db())
    try:
        config = db.query(OPCServerConfig).first()
        if not config:
            config = OPCServerConfig(opc_url=data['opc_url'], is_active=True)
            db.add(config)
        else:
            config.opc_url = data['opc_url']
            config.is_active = True # Reativar ao salvar
            
        db.commit()
        db.refresh(config)
        
        # --- APLICAR MUDANÇA (RECONECTAR) ---
        logging.info(f"🔄 Aplicando nova configuração OPC: {config.opc_url}")
        
        # Executa a reconfiguração no loop do OPC client
        # Isso vai desconectar o atual e atualizar a URL interna
        asyncio.run_coroutine_threadsafe(
            opc_client.configure(config.opc_url), 
            opc_client.loop
        ).result()
        
        # Tentar reconectar imediatamente
        success = asyncio.run_coroutine_threadsafe(
            opc_client.connect(), 
            opc_client.loop
        ).result()

        status_msg = "Conectado com sucesso" if success else "Configuração salva, mas falha na conexão imediata"
        return jsonify({
            'message': status_msg, 
            'config': config.to_dict(),
            'connected': success
        }), 200

    except Exception as e:
        db.rollback()
        logging.error(f"❌ Erro ao atualizar configuração OPC: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

# --- ROTAS CRUD PARA VARIÁVEIS OPC ---

@app.route('/api/opc/variables', methods=['GET'])
def get_opc_variables():
    """Lista todas as variáveis OPC de uma linha"""
    line_name = request.args.get('line')
    if not line_name:
        return jsonify({'error': 'Parâmetro line é obrigatório'}), 400
    
    db = next(get_db())
    try:
        variables = db.query(OPCVariables).filter_by(line_name=line_name).all()
        return jsonify([v.to_dict() for v in variables]), 200
    except Exception as e:
        logging.error(f"Erro ao listar variáveis OPC: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/opc/variables', methods=['POST'])
def create_opc_variable():
    """Cria uma nova variável OPC"""
    data = request.get_json()
    
    # Validações
    required_fields = ['line', 'node_id', 'variable_name', 'type', 'type_category']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Campo {field} é obrigatório'}), 400
    
    db = next(get_db())
    try:
        # Verificar se a linha existe
        line = db.query(Line).filter_by(name=data['line']).first()
        if not line:
            return jsonify({'error': f'Linha {data["line"]} não encontrada'}), 404
        
        # Verificar se já existe variável com mesmo node_id para essa linha
        existing = db.query(OPCVariables).filter_by(
            line_name=data['line'],
            node_id=data['node_id']
        ).first()
        if existing:
            return jsonify({'error': f'Variável com node_id {data["node_id"]} já existe para a linha {data["line"]}'}), 409
        
        # Criar nova variável
        new_variable = OPCVariables(
            line_name=data['line'],
            node_id=data['node_id'],
            variable_name=data['variable_name'],
            type=data['type'],
            type_category=data.get('type_category', 'read'),
            description=data.get('description', ''),
            is_active=True
        )
        
        db.add(new_variable)
        db.commit()
        db.refresh(new_variable)
        
        logging.info(f"✅ Variável OPC criada: {new_variable.variable_name} (ID: {new_variable.id})")
        return jsonify(new_variable.to_dict()), 201
        
    except Exception as e:
        db.rollback()
        logging.error(f"❌ Erro ao criar variável OPC: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/opc/variables/<int:variable_id>', methods=['PUT'])
def update_opc_variable(variable_id):
    """Atualiza uma variável OPC existente"""
    data = request.get_json()
    
    db = next(get_db())
    try:
        variable = db.query(OPCVariables).filter_by(id=variable_id).first()
        if not variable:
            return jsonify({'error': f'Variável OPC com ID {variable_id} não encontrada'}), 404
        
        # Atualizar campos permitidos
        if 'node_id' in data:
            variable.node_id = data['node_id']
        if 'variable_name' in data:
            variable.variable_name = data['variable_name']
        if 'type' in data:
            variable.type = data['type']
        if 'type_category' in data:
            variable.type_category = data['type_category']
        if 'description' in data:
            variable.description = data['description']
        if 'is_active' in data:
            variable.is_active = data['is_active']
        
        db.commit()
        db.refresh(variable)
        
        logging.info(f"✅ Variável OPC atualizada: {variable.variable_name} (ID: {variable_id})")
        return jsonify(variable.to_dict()), 200
        
    except Exception as e:
        db.rollback()
        logging.error(f"❌ Erro ao atualizar variável OPC: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/opc/variables/<int:variable_id>', methods=['DELETE'])
def delete_opc_variable(variable_id):
    """Deleta uma variável OPC"""
    db = next(get_db())
    try:
        variable = db.query(OPCVariables).filter_by(id=variable_id).first()
        if not variable:
            return jsonify({'error': f'Variável OPC com ID {variable_id} não encontrada'}), 404
        
        variable_name = variable.variable_name
        db.delete(variable)
        db.commit()
        
        logging.info(f"🗑️ Variável OPC deletada: {variable_name} (ID: {variable_id})")
        return jsonify({'message': f'Variável {variable_name} deletada com sucesso'}), 200
        
    except Exception as e:
        db.rollback()
        logging.error(f"❌ Erro ao deletar variável OPC: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

# --- ROTAS DE LOGGING OPC ---

@app.route('/api/opc/logging/status', methods=['GET'])
def get_opc_logging_status():
    """Retorna o status do logging OPC para uma linha"""
    line_name = request.args.get('line')
    if not line_name:
        return jsonify({'error': 'Parâmetro line é obrigatório'}), 400
    
    db = next(get_db())
    try:
        # --- CORREÇÃO ---
        # Perguntar ao client qual é o status REAL da task
        is_logging_active = opc_client.get_logging_status_for_line(line_name)
        
        # Manter a lógica de estatísticas (isso é útil)
        total_logs = db.query(OPCLogs).filter_by(line_name=line_name).count()
        last_log = db.query(OPCLogs).filter_by(line_name=line_name).order_by(OPCLogs.timestamp.desc()).first()
        last_log_time = last_log.timestamp.isoformat() if last_log else None
        
        return jsonify({
            'is_logging_active': is_logging_active,
            'total_logs': total_logs,
            'last_log_time': last_log_time,
            'opc_connected': opc_client.connected
        }), 200
        
    except Exception as e:
        logging.error(f"❌ Erro ao verificar status de logging: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/opc/logging/start', methods=['POST'])
def start_opc_logging():
    """Inicia o logging OPC para uma linha"""
    data = request.get_json()
    line_name = data.get('line')
    
    if not line_name:
        return jsonify({'error': 'Campo line é obrigatório'}), 400
    
    if not opc_client.connected:
        return jsonify({'error': 'Cliente OPC não está conectado'}), 503
    
    try:
        # --- CORREÇÃO ---
        # Chamar a função real do opc_client que inicia o worker
        success, message = opc_client.start_logging_for_line(line_name)
        # --- FIM DA CORREÇÃO ---
        
        if success:
            logging.info(f"✅ Logging OPC iniciado com sucesso para {line_name} pela API.")
            return jsonify({'message': message}), 200
        else:
            # A função start_logging_for_line já trata se "não há variáveis" ou "já está rodando"
            logging.warning(f"⚠️  Falha ao iniciar logging OPC para {line_name}: {message}")
            return jsonify({'error': message}), 400
            
    except Exception as e:
        logging.error(f"❌ Erro ao iniciar logging OPC: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/opc/logging/stop', methods=['POST'])
def stop_opc_logging():
    """Para o logging OPC para uma linha"""
    data = request.get_json()
    line_name = data.get('line')
    
    if not line_name:
        return jsonify({'error': 'Campo line é obrigatório'}), 400
    
    try:
        # --- CORREÇÃO ---
        # Chamar a função real do opc_client que para o worker
        success, message = opc_client.stop_logging_for_line(line_name)
        # --- FIM DA CORREÇÃO ---
        
        if success:
            logging.info(f"✅ Logging OPC parado com sucesso para {line_name} pela API.")
            return jsonify({'message': message}), 200
        else:
            logging.warning(f"⚠️  Falha ao parar logging OPC para {line_name}: {message}")
            return jsonify({'error': message}), 400
            
    except Exception as e:
        logging.error(f"❌ Erro ao parar logging OPC: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    
    
# ==========================================================
# NOVA ROTA (PARA O DASHBOARD DE ANÁLISE DETALHADA)
# ==========================================================
@app.route('/api/opc/history', methods=['GET'])
def get_opc_history():
    """
    Retorna o histórico de valores para uma lista de node_ids
    dentro de um intervalo de tempo.
    """
    line_name = request.args.get('line')
    start_time_str = request.args.get('start_time')
    end_time_str = request.args.get('end_time')
    node_ids_param = request.args.get('node_ids') # Lista separada por vírgulas
    
    if not line_name or not start_time_str or not end_time_str:
        return jsonify({'error': 'Parâmetros line, start_time e end_time são obrigatórios'}), 400
        
    try:
        start_time = date_parser.parse(start_time_str)
        end_time = date_parser.parse(end_time_str)
        
        # Se node_ids for fornecido, filtrar por eles
        node_ids = node_ids_param.split(',') if node_ids_param else None
        
        db = next(get_db())
        try:
            query = db.query(OPCLogs).filter(
                OPCLogs.line_name == line_name,
                OPCLogs.timestamp >= start_time,
                OPCLogs.timestamp <= end_time
            )
            
            if node_ids:
                query = query.filter(OPCLogs.node_id.in_(node_ids))
                
            logs = query.order_by(OPCLogs.timestamp.asc()).all()
            
            # Formatar para o frontend:
            # O Recharts prefere: [{ timestamp: '...', var1: val1, var2: val2 }, ...]
            # Mas como os timestamps podem não ser exatos entre variáveis, 
            # vamos agrupar por timestamp (com uma tolerância de segundos se necessário, 
            # mas aqui vamos assumir que o worker coleta tudo junto).
            
            # Agrupamento simples por timestamp exato
            data_map = {}
            
            for log in logs:
                ts_str = log.timestamp.isoformat()
                if ts_str not in data_map:
                    data_map[ts_str] = {'timestamp': ts_str}
                
                # Adiciona o valor da variável ao objeto desse timestamp
                # Usamos o node_id como chave
                data_map[ts_str][log.node_id] = log.value
                
            # Converter para lista ordenada
            result_data = sorted(data_map.values(), key=lambda x: x['timestamp'])
            
            return jsonify(result_data), 200
            
        except Exception as e:
            logging.error(f"❌ Erro ao buscar histórico OPC: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
        finally:
            db.close()
            
    except ValueError:
        return jsonify({'error': 'Formato de data inválido.'}), 400

@app.route('/api/opc/logs/by-date', methods=['GET'])
def get_opc_logs_by_date():
    """
    Retorna uma lista de timestamps únicos de logs OPC 
    para uma linha específica em uma data específica.
    """
    line_name = request.args.get('line')
    date_str = request.args.get('date')
    
    if not line_name:
        return jsonify({'error': 'Parâmetro line é obrigatório'}), 400
    if not date_str:
        return jsonify({'error': 'Parâmetro date é obrigatório'}), 400
    
    try:
        # Converter a string 'YYYY-MM-DD' para um objeto datetime
        start_of_day = date_parser.parse(date_str).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
        )
        end_of_day = start_of_day + timedelta(days=1)
        
        db = next(get_db())
        try:
            # Buscar timestamps ÚNICOS
            # A query usa distinct() para não repetir timestamps
            timestamps_query = db.query(OPCLogs.timestamp).filter(
                OPCLogs.line_name == line_name,
                OPCLogs.timestamp >= start_of_day,
                OPCLogs.timestamp < end_of_day
            ).distinct().order_by(OPCLogs.timestamp.desc())
            
            # O frontend espera uma lista de strings
            timestamps_list = [ts[0].isoformat() for ts in timestamps_query.all()]
            
            return jsonify(timestamps_list), 200
            
        except Exception as e:
            logging.error(f"❌ Erro ao buscar logs por data: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
        finally:
            db.close()
            
    except ValueError:
        return jsonify({'error': 'Formato de data inválido. Use YYYY-MM-DD.'}), 400
# ==========================================================
# FIM DA NOVA ROTA
# ==========================================================

# --- ROTAS DE LEITURA/ESCRITA OPC ---

@app.route('/api/opc/write', methods=['POST'])
def write_opc_variable():
    """Escreve um valor em uma variável OPC"""
    data = request.get_json()
    
    required_fields = ['node_id', 'value']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Campo {field} é obrigatório'}), 400
    
    if not opc_client.connected:
        return jsonify({'error': 'Cliente OPC não está conectado'}), 503
    
    try:
        node_id = data['node_id']
        value = data['value']
        
        # Escrever valor no OPC (assíncrono)
        future = asyncio.run_coroutine_threadsafe(
            opc_client.write_value(node_id, value),
            opc_client.loop
        )
        success = future.result(timeout=10)
        
        if success:
            logging.info(f"✅ Valor escrito no OPC: {node_id} = {value}")
            return jsonify({'message': f'Valor {value} escrito com sucesso em {node_id}'}), 200
        else:
            logging.error(f"❌ Falha ao escrever valor no OPC: {node_id}")
            return jsonify({'error': 'Falha ao escrever valor no OPC'}), 500
            
    except Exception as e:
        logging.error(f"❌ Erro ao escrever no OPC: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/opc/read', methods=['GET'])
def read_opc_variable():
    """Lê o valor atual de uma variável OPC"""
    node_id = request.args.get('node_id')
    
    if not node_id:
        return jsonify({'error': 'Parâmetro node_id é obrigatório'}), 400
    
    if not opc_client.connected:
        return jsonify({'error': 'Cliente OPC não está conectado'}), 503
    
    try:
        # Ler valor do OPC (assíncrono)
        future = asyncio.run_coroutine_threadsafe(
            opc_client.read_value(node_id),
            opc_client.loop
        )
        value = future.result(timeout=10)
        
        if value is not None:
            logging.info(f"✅ Valor lido do OPC: {node_id} = {value}")
            return jsonify({'node_id': node_id, 'value': value}), 200
        else:
            logging.error(f"❌ Falha ao ler valor do OPC: {node_id}")
            return jsonify({'error': 'Falha ao ler valor do OPC'}), 500
            
    except Exception as e:
        logging.error(f"❌ Erro ao ler do OPC: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# ==================== FIM DAS ROTAS ====================

