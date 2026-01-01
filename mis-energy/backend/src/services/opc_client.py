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

opc_client_service = OPCClientService()
