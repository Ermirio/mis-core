# backend/src/main.py
import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from src.models.user import db
from src.routes.user_routes import user_bp
from src.routes.gateway import gateway_bp
from src.routes.equipment import equipment_bp
from src.routes.config import config_bp
from src.routes.analytics import analytics_bp
from src.routes.simulation import simulation_bp
from src.routes.hierarchy_routes import hierarchy_bp
from src.config import Config

app = Flask(__name__)

# Configurações
app.config.from_object(Config)

# Habilitar CORS para todas as rotas
CORS(app, origins=['http://localhost:5173'])  # Permitir frontend React

# Registrar blueprints
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(gateway_bp, url_prefix='/api')
app.register_blueprint(equipment_bp, url_prefix='/api')
app.register_blueprint(config_bp, url_prefix='/api')
app.register_blueprint(analytics_bp, url_prefix='/api')
app.register_blueprint(simulation_bp, url_prefix='/api')
app.register_blueprint(hierarchy_bp, url_prefix='/api')

# Inicializar banco de dados
db.init_app(app)

from src.auth import jwt_required_cookie
from flask import request
@app.before_request
def check_jwt():
    if request.path.startswith('/api/health') or request.method == 'OPTIONS' or not request.path.startswith('/api/'):
        return None
        
    @jwt_required_cookie
    def validate():
        return None
        
    return validate()

# Criar tabelas (Mover para script de inicialização ou executar apenas se main)
# with app.app_context():
#     db.create_all()

# Rota para servir frontend (opcional - para produção)
@app.route('/')
def serve_frontend():
    try:
        return send_from_directory('../frontend/dist', 'index.html')
    except:
        return jsonify({
            'message': 'Energy Monitoring API',
            'version': '1.0.0',
            'status': 'running',
            'endpoints': {
                'simulation': '/api/simulation/status',
                'dashboard': '/api/analytics/dashboard',
                'gateways': '/api/gateways',
                'equipments': '/api/equipments'
            }
        })

@app.route('/<path:path>')
def serve_static(path):
    try:
        return send_from_directory('../frontend/dist', path)
    except:
        return jsonify({'error': 'File not found'}), 404

# Health check endpoint
@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'message': 'Energy Monitoring API is running'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

