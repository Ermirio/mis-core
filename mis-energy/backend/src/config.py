# backend/src/config.py
import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

@dataclass
class DatabaseConfig:
    """Configuração para MySQL"""
    host: str = os.getenv('MYSQL_HOST', 'localhost')
    port: int = int(os.getenv('MYSQL_PORT', 3306))
    username: str = os.getenv('MYSQL_USER', 'root')
    password: str = os.getenv('MYSQL_PASSWORD', '')
    database: str = os.getenv('MYSQL_DB', 'energy_monitor')

@dataclass
class InfluxDBConfig:
    """Configuração para InfluxDB 1.8"""
# backend/src/config.py
import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

@dataclass
class DatabaseConfig:
    """Configuração para MySQL"""
    host: str = os.getenv('MYSQL_HOST', 'localhost')
    port: int = int(os.getenv('MYSQL_PORT', 3306))
    username: str = os.getenv('MYSQL_USER', 'root')
    password: str = os.getenv('MYSQL_PASSWORD', '')
    database: str = os.getenv('MYSQL_DB', 'energy_monitor')

@dataclass
class InfluxDBConfig:
    """Configuração para InfluxDB 1.8"""
    host: str = os.getenv('INFLUXDB_HOST', 'localhost')
    port: int = int(os.getenv('INFLUXDB_PORT', 8086))
    database: str = os.getenv('INFLUXDB_DATABASE', 'industrial_db')
    username: str = os.getenv('INFLUXDB_USER', 'admin')
    password: str = os.getenv('INFLUXDB_USER_PASSWORD', 'admin123')

from urllib.parse import quote_plus

class Config:
    """Configuração principal da aplicação"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'energy-monitor-secret-key-2024'

    # Configuração do MySQL via SQLAlchemy
    _user = os.getenv('MYSQL_USER', 'root')
    _pwd = quote_plus(os.getenv('MYSQL_PASSWORD', ''))
    _host = os.getenv('MYSQL_HOST', 'localhost')
    _port = os.getenv('MYSQL_PORT', 3306)
    _db = os.getenv('MYSQL_DB', 'energy_monitor')

    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{_user}:{_pwd}@{_host}:{_port}/{_db}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configurações de banco de dados (acessíveis via classe)
    mysql_config = DatabaseConfig()
    influxdb_config = InfluxDBConfig()