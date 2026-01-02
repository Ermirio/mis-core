import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from src.models.user import db
from src.routes.user_routes import user_bp
from src.routes.gateway import gateway_bp
from src.routes.equipment import equipment_bp
from src.routes.config import config_bp
from src.routes.analytics import analytics_bp
from src.routes.simulation import simulation_bp
from src.routes.hierarchy_routes import hierarchy_bp
from src.routes.analytics_dashboard import analytics_dashboard_bp
from src.routes.metrics_routes import metrics_bp
from src.config import Config

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config.from_object(Config)

# Habilitar CORS para todas as rotas
CORS(app)

# Registrar blueprints
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(gateway_bp, url_prefix='/api')
app.register_blueprint(equipment_bp, url_prefix='/api')
app.register_blueprint(config_bp, url_prefix='/api')
app.register_blueprint(analytics_bp, url_prefix='/api')
app.register_blueprint(simulation_bp, url_prefix='/api')
app.register_blueprint(hierarchy_bp, url_prefix='/api')
app.register_blueprint(analytics_dashboard_bp, url_prefix='/api')
app.register_blueprint(metrics_bp, url_prefix='/api')
from src.routes.ingestion import ingestion_bp
app.register_blueprint(ingestion_bp, url_prefix='/api')

# Inicializar banco de dados
db.init_app(app)
with app.app_context():
    # Importar todos os modelos para garantir que as tabelas sejam criadas
    from src.models.gateway import Gateway
    from src.models.equipment import Equipment
    from src.models.hierarchy_model import Hierarchy
    from src.models.config_model import DatabaseConfig
    from src.models.metrics_config import MetricsConfig
    
    # Only create tables if not in testing mode (prevents import side-effects)
    if os.environ.get('FLASK_ENV') != 'testing':
        try:
            db.create_all()
        except Exception as e:
            print(f"Warning: Could not connect to database to create tables: {e}")

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404


import socket

def find_available_port(start_port, max_port=65535):
    """Encontra uma porta disponível a partir de start_port"""
    for port in range(start_port, max_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise IOError("Nenhuma porta disponível encontrada")

if __name__ == '__main__':
    # Usar porta fixa para garantir que o proxy do frontend funcione
    port = 5005
    print(f"Starting backend on port {port}...")
    print(app.url_map)
    app.run(host='127.0.0.1', port=port, debug=False)
