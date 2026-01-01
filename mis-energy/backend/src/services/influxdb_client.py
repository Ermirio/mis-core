import logging
from typing import Optional, Dict, List
from datetime import datetime
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from src.config import Config as DatabaseConfig

logger = logging.getLogger(__name__)

class InfluxDBService:
    """Serviço para comunicação com InfluxDB 2.0"""
    
    def __init__(self):
        self.client = None
        self.write_api = None
        self.query_api = None
        self.config = None
    
    def initialize_client(self, config: Dict = None) -> bool:
        """Inicializa cliente InfluxDB com configuração"""
        try:
            if config is None:
                # Converter objeto config para dict se necessário
                conf_obj = DatabaseConfig.influxdb_config
                if conf_obj:
                    config = {
                        'host': conf_obj.host,
                        'port': conf_obj.port,
                        'database': conf_obj.database,
                        'username': conf_obj.username,
                        'password': conf_obj.password
                    }
            
            if not config:
                logger.warning("Configuração InfluxDB não encontrada")
                return False
            
            self.config = config
            
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
            
    def write_measurement(self, equipment_id: int, equipment_name: str, 
                         value: float, unit: str, location: str = None, 
                         area: str = None, hierarchy_path: str = None,
                         equipment_type: str = None, timestamp: datetime = None) -> bool:
        """Escreve medição no InfluxDB"""
        try:
            if not self.client or not self.write_api:
                if not self.initialize_client():
                    return False
            
            if timestamp is None:
                timestamp = datetime.now()
            
            # Criar ponto de dados
            point = Point("energy_consumption") \
                .tag("equipment_id", str(equipment_id)) \
                .tag("equipment_name", equipment_name) \
                .tag("unit", unit)
            
            if location:
                point = point.tag("location", location)
            if area:
                point = point.tag("area", area)
            if hierarchy_path:
                point = point.tag("hierarchy_path", hierarchy_path)
            if equipment_type:
                point = point.tag("equipment_type", equipment_type)
            
            point = point.field("value", float(value)) \
                .time(timestamp, WritePrecision.S)
            
            # Escrever no bucket (database/retention_policy)
            bucket = self.config.get('database', 'industrial_db')
            
            self.write_api.write(
                bucket=bucket,
                org='-',
                record=point
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao escrever medição no InfluxDB: {e}")
            return False
    
    def get_latest_measurements(self, equipment_id: int = None, 
                              limit: int = 100) -> List[Dict]:
        """Obtém últimas medições do InfluxDB"""
        try:
            if not self.client or not self.query_api:
                if not self.initialize_client():
                    return []
            
            # Construir query
            query = f'''
                from(bucket: "{self.config['bucket']}")
                |> range(start: -24h)
                |> filter(fn: (r) => r._measurement == "energy_consumption")
            '''
            
            if equipment_id:
                query += f'|> filter(fn: (r) => r.equipment_id == "{equipment_id}")'
            
            query += f'''
                |> sort(columns: ["_time"], desc: true)
                |> limit(n: {limit})
            '''
            
            result = self.query_api.query(query)
            
            measurements = []
            for table in result:
                for record in table.records:
                    measurements.append({
                        'equipment_id': record.values.get('equipment_id'),
                        'equipment_name': record.values.get('equipment_name'),
                        'value': record.values.get('_value'),
                        'unit': record.values.get('unit'),
                        'location': record.values.get('location'),
                        'area': record.values.get('area'),
                        'timestamp': record.values.get('_time').isoformat()
                    })
            
            return measurements
            
        except Exception as e:
            logger.error(f"Erro ao consultar medições no InfluxDB: {e}")
            return []
    
    def get_equipment_statistics(self, equipment_id: int, 
                               hours: int = 24) -> Dict:
        """Obtém estatísticas de um equipamento"""
        try:
            if not self.client or not self.query_api:
                if not self.initialize_client():
                    return {}
            
            query = f'''
                from(bucket: "{self.config['bucket']}")
                |> range(start: -{hours}h)
                |> filter(fn: (r) => r._measurement == "energy_consumption")
                |> filter(fn: (r) => r.equipment_id == "{equipment_id}")
                |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
            '''
            
            result = self.query_api.query(query)
            
            values = []
            for table in result:
                for record in table.records:
                    values.append(record.values.get('_value', 0))
            
            if not values:
                return {}
            
            return {
                'count': len(values),
                'average': sum(values) / len(values),
                'minimum': min(values),
                'maximum': max(values),
                'total': sum(values)
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas do InfluxDB: {e}")
            return {}
    
    def close(self):
        """Fecha conexão com InfluxDB"""
        if self.client:
            self.client.close()
            self.client = None
            self.write_api = None
            self.query_api = None

# Instância global do serviço
influxdb_service = InfluxDBService()

