# backend/src/routes/config.py

from flask import Blueprint, request, jsonify
from sqlalchemy import text
from src.models.user import db
from src.config import Config, DatabaseConfig as DbConf, InfluxDBConfig
from src.models.config_model import DatabaseConfig
from src.services.influxdb_client import influxdb_service

config_bp = Blueprint('config', __name__)

# --- Rotas MySQL ---

@config_bp.route('/config/mysql', methods=['GET'])
def get_mysql_config():
    """Retorna a configuração atual do MySQL"""
    config = DatabaseConfig.get_mysql_config()
    return jsonify({'success': True, 'data': config or {}})

@config_bp.route('/config/mysql', methods=['POST'])
def save_mysql_config():
    """Salva uma nova configuração do MySQL"""
    try:
        data = request.get_json()
        # Salva no banco de dados
        DatabaseConfig.set_mysql_config(data)
        # Atualiza a configuração em memória
        Config.update_mysql_config(DbConf(**data))
        return jsonify({'success': True, 'message': 'Configuração MySQL salva com sucesso.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@config_bp.route('/config/mysql/test', methods=['POST'])
def test_mysql_connection():
    """Testa a conexão com o MySQL usando as credenciais fornecidas"""
    try:
        data = request.get_json()
        uri = f"mysql+pymysql://{data['username']}:{data['password']}@{data['host']}:{data['port']}/{data['database']}"
        
        # Cria uma engine temporária para teste
        from sqlalchemy import create_engine
        engine = create_engine(uri, connect_args={'connect_timeout': 5})
        
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            
        return jsonify({'success': True, 'data': {'connected': True, 'message': 'Conexão MySQL bem-sucedida.'}})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Falha na conexão: {str(e)}'}), 500

# --- Rotas InfluxDB ---

@config_bp.route('/config/influxdb', methods=['GET'])
def get_influxdb_config():
    """Retorna a configuração atual do InfluxDB"""
    config = DatabaseConfig.get_influxdb_config()
    return jsonify({'success': True, 'data': config or {}})

@config_bp.route('/config/influxdb', methods=['POST'])
def save_influxdb_config():
    """Salva uma nova configuração do InfluxDB"""
    try:
        data = request.get_json()
        # Salva no banco de dados
        DatabaseConfig.set_influxdb_config(data)
        # Atualiza a configuração em memória
        Config.update_influxdb_config(InfluxDBConfig(**data))
        return jsonify({'success': True, 'message': 'Configuração InfluxDB salva com sucesso.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@config_bp.route('/config/influxdb/test', methods=['POST'])
def test_influxdb_connection():
    """Testa a conexão com o InfluxDB"""
    try:
        data = request.get_json()
        result = influxdb_service.test_connection(config=data)
        if result.get('connected'):
            return jsonify({'success': True, 'data': result})
        else:
            return jsonify({'success': False, 'error': result.get('message', 'Erro desconhecido')}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500