"""
Flask Application Factory
Initializes Flask app, InfluxDB connection, and registers blueprints.
"""
import logging
from flask import Flask
from flask_cors import CORS
from influxdb import InfluxDBClient
from decouple import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(name)s] %(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('[FLASK:CORE]')

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Configuration
    app.config['INFLUX_HOST'] = config('INFLUXDB_HOST', default='127.0.0.1')
    app.config['INFLUX_PORT'] = config('INFLUXDB_PORT', default=8086, cast=int)
    app.config['INFLUX_DB'] = config('INFLUXDB_DATABASE', default='industrial_db')
    app.config['INFLUX_USER'] = config('INFLUXDB_USER', default='admin')
    app.config['INFLUX_PASS'] = config('INFLUXDB_USER_PASSWORD', default='ixvq10A@10')
    app.config['DJANGO_API_URL'] = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')
    
    # Initialize InfluxDB Client
    try:
        influx_client = InfluxDBClient(
            host=app.config['INFLUX_HOST'],
            port=app.config['INFLUX_PORT'],
            username=app.config['INFLUX_USER'],
            password=app.config['INFLUX_PASS'],
            database=app.config['INFLUX_DB']
        )
        # Test connection
        influx_client.ping()
        logger.info(f"✓ InfluxDB connected: {app.config['INFLUX_HOST']}:{app.config['INFLUX_PORT']}")
    except Exception as e:
        logger.error(f"✗ InfluxDB connection failed: {e}")
        influx_client = None
    
    # Store in app context
    app.influx_client = influx_client
    
    # Initialize Production Engine
    from app.services.production_engine import get_engine
    try:
        app.production_engine = get_engine(influx_client, app.config['DJANGO_API_URL'])
        logger.info(f"✓ Production Engine initialized (Django: {app.config['DJANGO_API_URL']})")
    except Exception as e:
        logger.error(f"✗ Production Engine initialization failed: {e}")
        app.production_engine = None
    
    # Register blueprints
    from app.routes import register_blueprints
    register_blueprints(app)
    
    logger.info("✓ Flask application initialized successfully")
    return app
