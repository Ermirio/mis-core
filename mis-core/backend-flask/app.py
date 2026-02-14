import logging
from flask import Flask
from flask_cors import CORS
from influxdb import InfluxDBClient
from decouple import config

from production_engine import get_engine
from routes import api_bp
from kpis_routes import kpis_bp
from blueprints.analytics import analytics_bp
from blueprints.golden_state import golden_state_bp

# ===== CONFIGS =====
INFLUX_HOST = config('INFLUXDB_HOST', default='127.0.0.1')
INFLUX_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUX_DB = config('INFLUXDB_DATABASE', default='mis_core_db')
INFLUX_USER = config('INFLUXDB_USER', default='admin')
INFLUX_PASS = config('INFLUXDB_PASSWORD', default='admin123')
DJANGO_API_URL = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')

# CORS Config
CORS_ALLOW_ALL = config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool)
CORS_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='').split(',')
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS if o.strip()]

if not CORS_ORIGINS and not CORS_ALLOW_ALL:
    CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"] # Default dev fallback

def create_app():
    """
    Application Factory for Flask.
    Initializes extensions and registers blueprints.
    """
    app = Flask(__name__)
    
    # Configure CORS
    if CORS_ALLOW_ALL:
        CORS(app, resources={r"/api/*": {"origins": "*"}})
    else:
        CORS(app, resources={r"/api/*": {"origins": CORS_ORIGINS}})

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    # Inicializa Engine e InfluxDB
    try:
        influx_client = InfluxDBClient(host=INFLUX_HOST, port=INFLUX_PORT, username=INFLUX_USER, password=INFLUX_PASS, database=INFLUX_DB)
        production_engine = get_engine(influx_client, DJANGO_API_URL)
        
        # Armazena nas extensões do app para acesso global (via current_app)
        app.extensions['influx_client'] = influx_client
        app.extensions['production_engine'] = production_engine
        
        app.extensions['production_engine'] = production_engine
        
        logger.info(f"[OK] Engine Iniciado (Conectado ao Django: {DJANGO_API_URL})")
        
        # Start Scheduler
        from scheduler import start_scheduler
        start_scheduler(app)
        
    except Exception as e:
        logger.error(f"[ERROR] Erro Crítico na Inicialização: {e}")
        app.extensions['influx_client'] = None
        app.extensions['production_engine'] = None

    # Registra Rotas
    app.register_blueprint(api_bp)
    app.register_blueprint(kpis_bp)
    app.register_blueprint(analytics_bp, url_prefix='/api')
    app.register_blueprint(golden_state_bp, url_prefix='/api/golden-state')
    
    # Diagnóstico de Rotas
    with app.app_context():
        print("\n--- ROTAS REGISTRADAS ---")
        for rule in app.url_map.iter_rules():
            print(f"✅ {rule} -> {rule.endpoint}")
        print("-------------------------\n")

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)