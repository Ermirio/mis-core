import logging
import traceback
from opcua import Client, ua
from opcua.ua.uaerrors._base import UaError

logger = logging.getLogger(__name__)

class OPCClientService:
    def test_connection(self, opc_url, timeout=5):
        """
        Testa a conexão com um servidor OPC UA usando biblioteca síncrona.
        Retorna um dicionário com o resultado.
        """
        if not opc_url:
             return {
                'success': False,
                'error': 'URL OPC UA não fornecida.'
            }

        if not opc_url.startswith('opc.tcp://'):
             return {
                'success': False,
                'error': 'URL inválida. Deve começar com opc.tcp://'
            }

        client = None
        try:
            # Configura cliente síncrono com timeout
            client = Client(opc_url, timeout=timeout)
            
            logger.info(f"Tentando conectar OPC UA em {opc_url} com timeout {timeout}s")
            client.connect()
            
            # Tenta ler o nó raiz para garantir que a sessão está ativa
            root = client.get_root_node()
            # Apenas lê um atributo simples para confirmar
            root.get_node_class()
            
            logger.info("Conexão OPC bem sucedida")
            return {
                'success': True,
                'message': f'Conectado com sucesso ao servidor OPC UA: {opc_url}'
            }
        
        except UaError as e:
            # Erro específico do protocolo OPC UA
            error_msg = str(e) or repr(e) or e.__class__.__name__
            logger.error(f"Erro OPC UA: {error_msg}")
            return {
                'success': False,
                'error': f'Erro OPC UA: {error_msg}'
            }
        except TimeoutError as e:
            logger.error(f"Timeout ao conectar OPC: {e}")
            return {
                'success': False,
                'error': f'Timeout: Servidor não respondeu em {timeout} segundos.'
            }
        except ConnectionRefusedError as e:
            logger.error(f"Conexão recusada: {e}")
            return {
                'success': False,
                'error': 'Conexão recusada pelo servidor. Verifique IP/porta e firewall.'
            }
        except OSError as e:
            # Erros de rede (host unreachable, network down, etc)
            logger.error(f"Erro de rede: {e}")
            return {
                'success': False,
                'error': f'Erro de rede: {e}'
            }
        except Exception as e:
            # Captura genérica com máximo de detalhes
            error_msg = str(e)
            if not error_msg:
                error_msg = repr(e)
            if not error_msg:
                error_msg = e.__class__.__name__
            
            logger.error(f"Erro ao testar conexão OPC: {error_msg}")
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': f'Falha na conexão: {error_msg}'
            }
        finally:
            if client:
                try:
                    client.disconnect()
                except Exception as disc_err:
                    logger.warning(f"Erro ao desconectar: {disc_err}")

    def read_value(self, opc_url, node_id, timeout=5):
        """
        Lê o valor de um nó OPC UA específico.
        
        Args:
            opc_url: URL do servidor OPC UA (ex: opc.tcp://192.168.1.100:4840)
            node_id: Identificador do nó (ex: ns=2;s=Tag.Name ou ns=2;i=1234)
            timeout: Timeout em segundos
            
        Returns:
            dict com success, value, timestamp ou error
        """
        if not opc_url:
            return {
                'success': False,
                'error': 'URL OPC UA não fornecida.'
            }

        if not node_id:
            return {
                'success': False,
                'error': 'NodeID não fornecido.'
            }

        client = None
        try:
            from datetime import datetime
            
            client = Client(opc_url, timeout=timeout)
            logger.info(f"Conectando ao OPC {opc_url} para ler nó {node_id}")
            client.connect()
            
            # Obter o nó e ler seu valor
            node = client.get_node(node_id)
            value = node.get_value()
            
            logger.info(f"Leitura OPC bem sucedida: {node_id} = {value}")
            return {
                'success': True,
                'raw_value': value,
                'converted_value': float(value) if isinstance(value, (int, float)) else value,
                'timestamp': datetime.now().isoformat()
            }
            
        except UaError as e:
            error_msg = str(e) or repr(e) or e.__class__.__name__
            logger.error(f"Erro OPC UA ao ler {node_id}: {error_msg}")
            return {
                'success': False,
                'error': f'Erro OPC UA: {error_msg}'
            }
        except Exception as e:
            error_msg = str(e) or repr(e) or e.__class__.__name__
            logger.error(f"Erro ao ler valor OPC {node_id}: {error_msg}")
            return {
                'success': False,
                'error': f'Erro na leitura: {error_msg}'
            }
        finally:
            if client:
                try:
                    client.disconnect()
                except:
                    pass

opc_client_service = OPCClientService()
