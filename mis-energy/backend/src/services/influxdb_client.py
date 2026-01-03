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
                    'username': 'admin',
                    'password': 'admin123'
                }
            
            print(f"[InfluxDB] Initializing client with config: {config}", flush=True)
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
                         equipment_type: str = None, timestamp: datetime = None,
                         tag_code: str = None, metric_name: str = 'power_kw') -> bool:
        """Escreve medição no InfluxDB (Alinhado com Coletor e Query History)"""
        try:
            if not self.config:
                if not self.initialize_client():
                    return False
            
            if timestamp is None:
                timestamp = datetime.now()
            
            host = self.config.get('host', 'mis-core-influxdb')
            port = self.config.get('port', 8086)
            database = self.config.get('database', 'db_energy')
            
            # Formatação de tags para Line Protocol
            # Query espera: tag={tag_code} e metric={metric_name}
            
            # Se tag_code não for fornecido, usa equipment_name como fallback
            target_tag = tag_code if tag_code else equipment_name
            
            # Base Tags necessárias para compatibilidade com Dashboard e Histórico
            influx_tags = [
                f'tag={target_tag}',
                f'metric={metric_name}',
                f'equipment_id={equipment_id}'
            ]
            
            # Tags extras para metadados
            if unit: influx_tags.append(f'unit={unit}')
            if equipment_type: influx_tags.append(f'equipment_type={equipment_type}')
            # opcional: location/area se necessário, mas mantenha curto para cardinalidade
            
            tags_str = ','.join(influx_tags)
            
            # Measurement name fixo para compatibilidade
            measurement = 'energy_consumption'
            
            # Line: energy_consumption,tag=X,metric=Y value=Z 123456789
            line = f'{measurement},{tags_str} value={float(value)} {int(timestamp.timestamp() * 1e9)}'
            
            url = f"http://{host}:{port}/write"
            
            # DEBUG LOGGING IMPERATIVO (PRINT)
            print(f"[InfluxDB] Writing to {url} (DB: {database})", flush=True)
            print(f"[InfluxDB] Payload: {line}", flush=True)
            
            # Recuperar credenciais da config
            username = self.config.get('username', 'admin')
            password = self.config.get('password', 'admin123')
            
            response = requests.post(url, params={
                'db': database,
                'u': username,
                'p': password
            }, data=line, timeout=5)
            
            print(f"[InfluxDB] Status: {response.status_code}", flush=True)
            if response.status_code != 204:
                print(f"[InfluxDB] Error Body: {response.text}", flush=True)
            
            return response.status_code == 204
            
        except Exception as e:
            logger.error(f"Erro ao escrever medição no InfluxDB: {e}")
            return False

    def write_batch_data(self, data: List[Dict]) -> bool:
        """Escreve lote de dados no InfluxDB (Compatível com Ingestão)"""
        try:
            if not self.config:
                if not self.initialize_client():
                    return False
            
            host = self.config.get('host', 'mis-core-influxdb')
            port = self.config.get('port', 8086)
            database = self.config.get('database', 'db_energy')
            
            lines = []
            for item in data:
                # { "equipamento_codigo": "...", "medicoes": {...}, "timestamp": "..." }
                eq_code = item.get('equipamento_codigo')
                if not eq_code: continue
                
                timestamp_str = item.get('timestamp') # ISO format expected
                if timestamp_str:
                    try:
                        ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        ts_nano = int(ts.timestamp() * 1e9)
                    except:
                        ts_nano = int(datetime.now().timestamp() * 1e9)
                else:
                    ts_nano = int(datetime.now().timestamp() * 1e9)
                
                measurements = item.get('medicoes', {})
                for metric, value in measurements.items():
                    if value is None: continue
                    # Line Protocol
                    # energy_consumption,tag=CODE field=value ts
                    line = f'energy_consumption,tag={eq_code},metric={metric} value={float(value)} {ts_nano}'
                    lines.append(line)
            
            if not lines:
                return True

            # Batch write (InfluxDB 1.8 API)
            url = f"http://{host}:{port}/write"
            body = '\n'.join(lines)
            
            params = {
                'db': database,
                'u': self.config.get('username', ''),
                'p': self.config.get('password', '')
            }
            
            response = requests.post(url, params=params, data=body, timeout=10)
            
            return response.status_code == 204
            
        except Exception as e:
            logger.error(f"Erro batch write: {e}")
            return False

    def execute_query(self, query: str, database: str = None) -> Optional[Dict]:
        """Executes a raw InfluxQL query against InfluxDB 1.8 with HTTP Basic Auth"""
        try:
            if not self.config:
                if not self.initialize_client():
                    return None
            
            host = self.config.get('host', 'mis-core-influxdb')
            port = self.config.get('port', 8086)
            db_name = database or self.config.get('database', 'db_energy')
            username = self.config.get('username', '')
            password = self.config.get('password', '')
            
            url = f"http://{host}:{port}/query"
            
            # Use HTTP Basic Auth for robustness
            response = requests.get(
                url, 
                params={'db': db_name, 'q': query},
                auth=(username, password),
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"InfluxDB Query Error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error executing InfluxDB query: {e}")
            return None

    def close(self):
        """Fecha conexão com InfluxDB"""
        if self.client:
            self.client.close()
            self.client = None
            self.write_api = None
            self.query_api = None

# Instância global do serviço
influxdb_service = InfluxDBService()


