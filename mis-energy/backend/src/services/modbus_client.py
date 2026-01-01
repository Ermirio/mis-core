import struct
import logging
from typing import Optional, Union, List
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from datetime import datetime

logger = logging.getLogger(__name__)

class ModbusClientService:
    """Serviço para comunicação Modbus TCP"""
    
    def __init__(self):
        self.clients = {}  # Cache de clientes por gateway
    
    def get_client(self, ip_address: str, port: int = 502, timeout: int = 5) -> ModbusTcpClient:
        """Obtém ou cria um cliente Modbus TCP"""
        client_key = f"{ip_address}:{port}"
        
        if client_key not in self.clients:
            self.clients[client_key] = ModbusTcpClient(
                host=ip_address,
                port=port,
                timeout=timeout
            )
        
        return self.clients[client_key]
    
    def test_connection(self, ip_address: str, port: int = 502, timeout: int = 5) -> dict:
        """Testa conexão com gateway Modbus TCP"""
        try:
            client = self.get_client(ip_address, port, timeout)
            
            start_time = datetime.now()
            connected = client.connect()
            end_time = datetime.now()
            
            if connected:
                client.close()
                response_time = (end_time - start_time).total_seconds()
                return {
                    'connected': True,
                    'response_time': round(response_time, 3),
                    'message': f'Conexão estabelecida com sucesso em {response_time:.3f}s'
                }
            else:
                return {
                    'connected': False,
                    'response_time': None,
                    'message': 'Falha ao conectar com o gateway'
                }
                
        except Exception as e:
            logger.error(f"Erro ao testar conexão Modbus: {e}")
            return {
                'connected': False,
                'response_time': None,
                'message': f'Erro de conexão: {str(e)}'
            }
    
    def read_register(self, ip_address: str, port: int, modbus_address: int, 
                     register: int, register_type: str = 'holding', 
                     data_type: str = 'float32', count: int = 2) -> dict:
        """Lê valor de um registro Modbus"""
        try:
            client = self.get_client(ip_address, port)
            
            if not client.connect():
                return {
                    'success': False,
                    'error': 'Falha ao conectar com o gateway'
                }
            
            try:
                # Ler registros baseado no tipo
                if register_type == 'holding':
                    result = client.read_holding_registers(register, count, modbus_address)
                elif register_type == 'input':
                    result = client.read_input_registers(register, count, modbus_address)
                elif register_type == 'coil':
                    result = client.read_coils(register, count, modbus_address)
                elif register_type == 'discrete':
                    result = client.read_discrete_inputs(register, count, modbus_address)
                else:
                    return {
                        'success': False,
                        'error': f'Tipo de registro não suportado: {register_type}'
                    }
                
                if result.isError():
                    return {
                        'success': False,
                        'error': f'Erro Modbus: {result}'
                    }
                
                # Converter dados baseado no tipo
                if register_type in ['coil', 'discrete']:
                    raw_value = result.bits[0] if result.bits else False
                    converted_value = float(raw_value)
                else:
                    raw_value = result.registers
                    converted_value = self.convert_registers_to_value(raw_value, data_type)
                
                return {
                    'success': True,
                    'raw_value': raw_value,
                    'converted_value': converted_value,
                    'timestamp': datetime.now().isoformat()
                }
                
            finally:
                client.close()
                
        except Exception as e:
            logger.error(f"Erro ao ler registro Modbus: {e}")
            return {
                'success': False,
                'error': f'Erro de leitura: {str(e)}'
            }
    
    def convert_registers_to_value(self, registers: List[int], data_type: str) -> float:
        """Converte registros Modbus para valor baseado no tipo de dados"""
        try:
            if data_type == 'float32':
                return self.ieee754_to_float(registers)
            elif data_type == 'int16':
                return float(registers[0] if registers else 0)
            elif data_type == 'int32':
                if len(registers) >= 2:
                    # Combinar dois registros de 16 bits em um int32
                    combined = (registers[0] << 16) | registers[1]
                    # Converter para signed int32
                    if combined >= 2**31:
                        combined -= 2**32
                    return float(combined)
                return 0.0
            elif data_type == 'uint16':
                return float(registers[0] if registers else 0)
            elif data_type == 'uint32':
                if len(registers) >= 2:
                    # Combinar dois registros de 16 bits em um uint32
                    combined = (registers[0] << 16) | registers[1]
                    return float(combined)
                return 0.0
            else:
                logger.warning(f"Tipo de dados não suportado: {data_type}")
                return float(registers[0] if registers else 0)
                
        except Exception as e:
            logger.error(f"Erro na conversão de dados: {e}")
            return 0.0
    
    def ieee754_to_float(self, registers: List[int]) -> float:
        """Converte registros Modbus para float IEEE 754"""
        try:
            if len(registers) < 2:
                return 0.0
            
            # Combinar dois registros de 16 bits em um valor de 32 bits
            # Ordem pode variar dependendo do dispositivo (big-endian vs little-endian)
            
            # Tentar big-endian primeiro (mais comum)
            combined_be = (registers[0] << 16) | registers[1]
            bytes_be = struct.pack('>I', combined_be)  # Big-endian unsigned int
            float_be = struct.unpack('>f', bytes_be)[0]  # Big-endian float
            
            # Verificar se o resultado é válido (não NaN ou infinito)
            if not (float_be != float_be or abs(float_be) == float('inf')):
                return float_be
            
            # Tentar little-endian se big-endian não funcionou
            combined_le = (registers[1] << 16) | registers[0]
            bytes_le = struct.pack('>I', combined_le)
            float_le = struct.unpack('>f', bytes_le)[0]
            
            return float_le if not (float_le != float_le or abs(float_le) == float('inf')) else 0.0
            
        except Exception as e:
            logger.error(f"Erro na conversão IEEE 754: {e}")
            return 0.0
    
    def close_all_connections(self):
        """Fecha todas as conexões ativas"""
        for client in self.clients.values():
            try:
                client.close()
            except:
                pass
        self.clients.clear()

# Instância global do serviço
modbus_service = ModbusClientService()

