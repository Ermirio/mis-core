import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List

logger = logging.getLogger(__name__)

class SimulationService:
    """Serviço para gerar dados simulados para testes"""
    
    def __init__(self):
        self.simulation_mode = False
        self.simulated_gateways = []
        self.simulated_equipments = []
        self.last_generated = None
    
    def toggle_simulation_mode(self) -> bool:
        """Alterna o modo de simulação"""
        self.simulation_mode = not self.simulation_mode
        if self.simulation_mode:
            self.generate_sample_data()
        logger.info(f"Modo simulação {'ativado' if self.simulation_mode else 'desativado'}")
        return self.simulation_mode
    
    def set_simulation_mode(self, enabled: bool) -> bool:
        """Define o modo de simulação"""
        self.simulation_mode = enabled
        if self.simulation_mode:
            self.generate_sample_data()
        logger.info(f"Modo simulação {'ativado' if self.simulation_mode else 'desativado'}")
        return self.simulation_mode
    
    def is_simulation_active(self) -> bool:
        """Verifica se o modo simulação está ativo"""
        return self.simulation_mode
    
    def generate_sample_data(self):
        """Gera dados de exemplo para simulação"""
        # Gateways simulados
        self.simulated_gateways = [
            {
                'id': 1,
                'name': 'Gateway Principal',
                'description': 'Gateway principal da fábrica',
                'ip_address': '192.168.1.100',
                'port': 502,
                'timeout': 5,
                'is_active': True,
                'created_at': (datetime.now() - timedelta(days=30)).isoformat(),
                'updated_at': datetime.now().isoformat(),
                'equipment_count': 4
            },
            {
                'id': 2,
                'name': 'Gateway Setor 2',
                'description': 'Gateway do setor de produção 2',
                'ip_address': '192.168.1.101',
                'port': 502,
                'timeout': 5,
                'is_active': True,
                'created_at': (datetime.now() - timedelta(days=20)).isoformat(),
                'updated_at': datetime.now().isoformat(),
                'equipment_count': 3
            },
            {
                'id': 3,
                'name': 'Gateway Auxiliar',
                'description': 'Gateway para equipamentos auxiliares',
                'ip_address': '192.168.1.102',
                'port': 502,
                'timeout': 5,
                'is_active': False,
                'created_at': (datetime.now() - timedelta(days=10)).isoformat(),
                'updated_at': datetime.now().isoformat(),
                'equipment_count': 0
            }
        ]
        
        # Equipamentos simulados
        self.simulated_equipments = [
            {
                'id': 1,
                'name': 'Motor Principal A1',
                'description': 'Motor principal da linha de produção A',
                'location': 'Sala de Máquinas - Setor A',
                'area': 'Produção',
                'standard_consumption': 150.0,
                'gateway_id': 1,
                'gateway_name': 'Gateway Principal',
                'modbus_address': 1,
                'opc_register': 40001,
                'register_type': 'holding',
                'data_type': 'float32',
                'scale_factor': 1.0,
                'unit': 'kWh',
                'is_active': True,
                'polling_interval': 60,
                'created_at': (datetime.now() - timedelta(days=25)).isoformat(),
                'updated_at': datetime.now().isoformat(),
                'last_reading_at': (datetime.now() - timedelta(minutes=2)).isoformat(),
                'last_value': round(random.uniform(140, 160), 2)
            },
            {
                'id': 2,
                'name': 'Compressor B2',
                'description': 'Compressor de ar comprimido',
                'location': 'Sala de Compressores',
                'area': 'Utilidades',
                'standard_consumption': 85.0,
                'gateway_id': 1,
                'gateway_name': 'Gateway Principal',
                'modbus_address': 2,
                'opc_register': 40002,
                'register_type': 'holding',
                'data_type': 'float32',
                'scale_factor': 1.0,
                'unit': 'kWh',
                'is_active': True,
                'polling_interval': 60,
                'created_at': (datetime.now() - timedelta(days=20)).isoformat(),
                'updated_at': datetime.now().isoformat(),
                'last_reading_at': (datetime.now() - timedelta(minutes=1)).isoformat(),
                'last_value': round(random.uniform(80, 90), 2)
            },
            {
                'id': 3,
                'name': 'Bomba Hidráulica C3',
                'description': 'Bomba do sistema hidráulico',
                'location': 'Casa de Bombas',
                'area': 'Utilidades',
                'standard_consumption': 45.0,
                'gateway_id': 1,
                'gateway_name': 'Gateway Principal',
                'modbus_address': 3,
                'opc_register': 40003,
                'register_type': 'holding',
                'data_type': 'float32',
                'scale_factor': 1.0,
                'unit': 'kWh',
                'is_active': True,
                'polling_interval': 60,
                'created_at': (datetime.now() - timedelta(days=18)).isoformat(),
                'updated_at': datetime.now().isoformat(),
                'last_reading_at': (datetime.now() - timedelta(minutes=3)).isoformat(),
                'last_value': round(random.uniform(40, 50), 2)
            },
            {
                'id': 4,
                'name': 'Ventilador Industrial D4',
                'description': 'Sistema de ventilação industrial',
                'location': 'Área de Ventilação',
                'area': 'HVAC',
                'standard_consumption': 25.0,
                'gateway_id': 2,
                'gateway_name': 'Gateway Setor 2',
                'modbus_address': 1,
                'opc_register': 40001,
                'register_type': 'holding',
                'data_type': 'float32',
                'scale_factor': 1.0,
                'unit': 'kWh',
                'is_active': True,
                'polling_interval': 60,
                'created_at': (datetime.now() - timedelta(days=15)).isoformat(),
                'updated_at': datetime.now().isoformat(),
                'last_reading_at': (datetime.now() - timedelta(minutes=5)).isoformat(),
                'last_value': round(random.uniform(20, 30), 2)
            },
            {
                'id': 5,
                'name': 'Esteira Transportadora E5',
                'description': 'Esteira principal de transporte',
                'location': 'Linha de Produção B',
                'area': 'Produção',
                'standard_consumption': 35.0,
                'gateway_id': 2,
                'gateway_name': 'Gateway Setor 2',
                'modbus_address': 2,
                'opc_register': 40002,
                'register_type': 'holding',
                'data_type': 'float32',
                'scale_factor': 1.0,
                'unit': 'kWh',
                'is_active': True,
                'polling_interval': 60,
                'created_at': (datetime.now() - timedelta(days=12)).isoformat(),
                'updated_at': datetime.now().isoformat(),
                'last_reading_at': (datetime.now() - timedelta(hours=2)).isoformat(),
                'last_value': round(random.uniform(30, 40), 2)
            },
            {
                'id': 6,
                'name': 'Forno Industrial F6',
                'description': 'Forno para tratamento térmico',
                'location': 'Setor de Tratamento',
                'area': 'Produção',
                'standard_consumption': 200.0,
                'gateway_id': 2,
                'gateway_name': 'Gateway Setor 2',
                'modbus_address': 3,
                'opc_register': 40003,
                'register_type': 'holding',
                'data_type': 'float32',
                'scale_factor': 1.0,
                'unit': 'kWh',
                'is_active': False,
                'polling_interval': 60,
                'created_at': (datetime.now() - timedelta(days=8)).isoformat(),
                'updated_at': datetime.now().isoformat(),
                'last_reading_at': (datetime.now() - timedelta(hours=6)).isoformat(),
                'last_value': 0.0
            }
        ]
        
        self.last_generated = datetime.now()
    
    def get_dashboard_metrics(self) -> Dict:
        """Retorna métricas simuladas para o dashboard"""
        if not self.simulation_mode:
            return None
        
        active_equipments = len([eq for eq in self.simulated_equipments if eq['is_active']])
        total_equipments = len(self.simulated_equipments)
        active_gateways = len([gw for gw in self.simulated_gateways if gw['is_active']])
        total_gateways = len(self.simulated_gateways)
        
        # Calcular consumo total
        total_consumption = sum([eq['last_value'] for eq in self.simulated_equipments if eq['is_active']])
        
        # Equipamentos com alerta (sem leitura recente)
        alerts = len([eq for eq in self.simulated_equipments if eq['is_active'] and 
                     datetime.fromisoformat(eq['last_reading_at']) < datetime.now() - timedelta(hours=1)])
        
        return {
            'total_consumption': round(total_consumption, 2),
            'active_equipments': active_equipments,
            'total_equipments': total_equipments,
            'active_gateways': active_gateways,
            'total_gateways': total_gateways,
            'alerts': alerts,
            'consumption_trend': round(random.uniform(2.0, 8.0), 1),
            'efficiency': round(random.uniform(80.0, 95.0), 1)
        }
    
    def get_consumption_chart_data(self, hours: int = 24) -> List[Dict]:
        """Gera dados simulados para gráfico de consumo"""
        if not self.simulation_mode:
            return None
        
        chart_data = []
        now = datetime.now()
        
        for i in range(hours):
            time_point = now - timedelta(hours=hours-i-1)
            
            # Simular consumo baseado na hora do dia
            hour = time_point.hour
            if 6 <= hour <= 18:  # Horário comercial
                base_consumption = random.uniform(1000, 1400)
            elif 19 <= hour <= 22:  # Horário de pico
                base_consumption = random.uniform(1200, 1600)
            else:  # Madrugada
                base_consumption = random.uniform(600, 900)
            
            chart_data.append({
                'time': time_point.strftime('%H:%M'),
                'consumption': round(base_consumption),
                'timestamp': time_point.isoformat()
            })
        
        return chart_data
    
    def get_equipment_summary(self) -> List[Dict]:
        """Retorna resumo simulado dos equipamentos"""
        if not self.simulation_mode:
            return None
        
        equipment_data = []
        for equipment in self.simulated_equipments:
            if not equipment['is_active']:
                continue
            
            # Determinar status baseado na última leitura
            last_reading = datetime.fromisoformat(equipment['last_reading_at'])
            time_diff = datetime.now() - last_reading
            status = 'alert' if time_diff > timedelta(hours=1) else 'normal'
            
            # Atualizar valor com pequena variação
            base_value = equipment['standard_consumption']
            variation = random.uniform(0.8, 1.2)
            current_consumption = round(base_value * variation, 2)
            
            equipment_data.append({
                'id': equipment['id'],
                'name': equipment['name'],
                'location': equipment['location'],
                'area': equipment['area'],
                'consumption': current_consumption,
                'unit': equipment['unit'],
                'status': status,
                'last_reading': equipment['last_reading_at']
            })
        
        return equipment_data
    
    def simulate_modbus_read(self, equipment_id: int) -> Dict:
        """Simula leitura Modbus de um equipamento"""
        if not self.simulation_mode:
            return None
        
        equipment = next((eq for eq in self.simulated_equipments if eq['id'] == equipment_id), None)
        if not equipment:
            return {
                'success': False,
                'error': 'Equipamento não encontrado'
            }
        
        # Simular valor com variação
        base_value = equipment['standard_consumption']
        variation = random.uniform(0.7, 1.3)
        simulated_value = round(base_value * variation, 2)
        
        # Atualizar último valor
        equipment['last_value'] = simulated_value
        equipment['last_reading_at'] = datetime.now().isoformat()
        
        return {
            'success': True,
            'data': {
                'equipment_id': equipment_id,
                'value': simulated_value,
                'unit': equipment['unit'],
                'timestamp': datetime.now().isoformat(),
                'raw_value': [int(simulated_value * 100), 0],
                'converted_value': simulated_value,
                'scale_factor': equipment['scale_factor']
            }
        }
    
    def simulate_gateway_test(self, gateway_id: int) -> Dict:
        """Simula teste de conexão com gateway"""
        if not self.simulation_mode:
            return None
        
        gateway = next((gw for gw in self.simulated_gateways if gw['id'] == gateway_id), None)
        if not gateway:
            return {
                'success': False,
                'error': 'Gateway não encontrado'
            }
        
        # Simular resultado baseado no status do gateway
        if gateway['is_active']:
            response_time = round(random.uniform(0.02, 0.15), 3)
            return {
                'success': True,
                'data': {
                    'connected': True,
                    'response_time': response_time,
                    'message': f'Conexão estabelecida com sucesso em {response_time}s'
                }
            }
        else:
            return {
                'success': True,
                'data': {
                    'connected': False,
                    'response_time': None,
                    'message': 'Gateway inativo - simulação de falha de conexão'
                }
            }

# Instância global do serviço
simulation_service = SimulationService()

