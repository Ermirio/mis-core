import logging
from typing import Optional, Dict, List
from datetime import datetime
import requests

logger = logging.getLogger(__name__)

# Tentar usar cliente v2, se não funcionar usa requests diretamente
try:
    from influxdb_client import InfluxDBClient, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS
    HAS_INFLUX_CLIENT = True
except ImportError:
    HAS_INFLUX_CLIENT = False

class InfluxDBService:
    """Serviço para comunicação com InfluxDB 1.8"""
    
    def __init__(self):
        self.client = None
        self.write_api = None
        self.query_api = None
        self.config = None
    
    def initialize_client(self, config: Dict = None) -> bool:
        """Inicializa cliente InfluxDB com configuração"""
        try:
            if config is None:
                # Carregar config padrão
                from src.config import Config as DatabaseConfig
                conf_obj = DatabaseConfig.influxdb_config
                if conf_obj:
                    config = {
                        'host': conf_obj.host,
                        'port': conf_obj.port,
                        'database': conf_obj.database,
                        'username': getattr(conf_obj, 'username', ''),
                        'password': getattr(conf_obj, 'password', '')
                    }
            
            if not config:
                # Valores padrão para InfluxDB 1.8
                config = {
                    'host': 'mis-core-influxdb',
                    'port': 8086,
                    'database': 'db_energy',
                    'username': '',
                    'password': ''
                }
            
            self.config = config
            
            # Criar database se não existir
            self._create_database_if_not_exists()
            
            if HAS_INFLUX_CLIENT:
                # Adaptação para InfluxDB 1.8 usando client v2
                url = f"http://{config.get('host', 'localhost')}:{config.get('port', 8086)}"
                token = f"{config.get('username', '')}:{config.get('password', '')}"
                
                self.client = InfluxDBClient(
                    url=url,
                    token=token,
                    org='-'  # InfluxDB 1.8 compatibility
                )
                
                self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
                self.query_api = self.client.query_api()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao inicializar cliente InfluxDB: {e}")
            return False
    
    def _create_database_if_not_exists(self):
        """Cria database db_energy se não existir (InfluxDB 1.8)"""
        try:
            host = self.config.get('host', 'mis-core-influxdb')
            port = self.config.get('port', 8086)
            database = self.config.get('database', 'db_energy')
            
            url = f"http://{host}:{port}/query"
            
            # Criar database
            response = requests.post(url, params={
                'q': f'CREATE DATABASE IF NOT EXISTS "{database}"'
            }, timeout=5)
            
            if response.status_code == 200:
                logger.info(f"Database '{database}' verificado/criado com sucesso")
                return True
            else:
                logger.warning(f"Resposta ao criar database: {response.text}")
                return False
                
        except Exception as e:
            logger.warning(f"Não foi possível verificar/criar database: {e}")
            return False
    
    def test_connection(self, config: Dict = None) -> Dict:
        """Testa conexão com InfluxDB 1.8"""
        try:
            if config is None:
                config = self.config or {
                    'host': 'mis-core-influxdb',
                    'port': 8086,
                    'database': 'db_energy'
                }
            
            host = config.get('host', 'mis-core-influxdb')
            port = config.get('port', 8086)
            database = config.get('database', config.get('bucket', 'db_energy'))
            
            url = f"http://{host}:{port}/ping"
            
            response = requests.get(url, timeout=5)
            
            if response.status_code == 204:
                # Verificar/criar database
                query_url = f"http://{host}:{port}/query"
                db_response = requests.get(query_url, params={
                    'q': 'SHOW DATABASES'
                }, timeout=5)
                
                return {
                    'connected': True,
                    'message': f'Conexão InfluxDB 1.8 bem-sucedida. Database: {database}',
                    'version': response.headers.get('X-Influxdb-Version', '1.8')
                }
            else:
                return {
                    'connected': False,
                    'message': f'InfluxDB retornou status {response.status_code}'
                }
                
        except requests.exceptions.ConnectionError as e:
            return {
                'connected': False,
                'message': f'Não foi possível conectar ao InfluxDB: {str(e)}'
            }
        except Exception as e:
            return {
                'connected': False,
                'message': f'Erro ao testar conexão: {str(e)}'
            }
    
    def write_measurement(self, equipment_id: int, equipment_name: str, 
                         value: float, unit: str, location: str = None, 
                         area: str = None, hierarchy_path: str = None,
                         equipment_type: str = None, timestamp: datetime = None) -> bool:
        """Escreve medição no InfluxDB"""
        try:
            if not self.config:
                if not self.initialize_client():
                    return False
            
            if timestamp is None:
                timestamp = datetime.now()
            
            host = self.config.get('host', 'mis-core-influxdb')
            port = self.config.get('port', 8086)
            database = self.config.get('database', 'db_energy')
            
            # Line Protocol para InfluxDB 1.8
            tags = f'equipment_id={equipment_id},equipment_name={equipment_name.replace(" ", "_")},unit={unit}'
            if location:
                tags += f',location={location.replace(" ", "_")}'
            if area:
                tags += f',area={area.replace(" ", "_")}'
            if equipment_type:
                tags += f',equipment_type={equipment_type}'
            
            line = f'energy_consumption,{tags} value={float(value)} {int(timestamp.timestamp() * 1e9)}'
            
            url = f"http://{host}:{port}/write"
            response = requests.post(url, params={
                'db': database
            }, data=line, timeout=5)
            
            return response.status_code == 204
            
        except Exception as e:
            logger.error(f"Erro ao escrever medição no InfluxDB: {e}")
            return False
    
    def close(self):
        """Fecha conexão com InfluxDB"""
        if self.client:
            self.client.close()
            self.client = None
            self.write_api = None
            self.query_api = None

# Instância global do serviço
influxdb_service = InfluxDBService()


