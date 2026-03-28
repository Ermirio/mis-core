import time
import threading
import logging
from opcua import Client, ua
from django.db import transaction

logger = logging.getLogger(__name__)


def write_opc_node(url, node_id, value, timeout=5):
    """
    Escreve um valor booleano em um nó OPC UA.
    Retorna (success: bool, error: str|None)
    """
    client = Client(url, timeout=timeout)
    try:
        client.connect()
        node = client.get_node(node_id)
        node.set_value(ua.DataValue(ua.Variant(bool(value), ua.VariantType.Boolean)))
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        try:
            client.disconnect()
        except Exception:
            pass

class OPCIntertravamentoWorker(threading.Thread):
    def __init__(self, interval=5):
        super().__init__()
        self.interval = interval
        self.daemon = True
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def connect_client(self, url):
        client = Client(url, timeout=5)
        client.connect()
        return client

    def run(self):
        logger.info("Iniciando serviço OPC Múltiplo para Intertravamentos...")
        # Import atrasado para garantir que os apps estejam carregados
        from .models import IntertravamentoLinha
        
        while not self._stop_event.is_set():
            try:
                # Agrupar intertravamentos por URL do servidor para minimizar conexões
                # Buscamos apenas linhas habilitadas do software
                intertravamentos = IntertravamentoLinha.objects.select_related('conexao_opcua').all()
                url_dict = {}
                for inter in intertravamentos:
                    if inter.conexao_opcua and inter.node_id_tag:
                        url = inter.conexao_opcua.url
                        if url not in url_dict:
                            url_dict[url] = []
                        url_dict[url].append(inter)

                for url, itens in url_dict.items():
                    client = None
                    try:
                        client = self.connect_client(url)
                        for item in itens:
                            try:
                                # node_id_tag já contém o endereço OPC completo
                                node = client.get_node(item.node_id_tag)
                                val = node.get_value()
                                val_bool = bool(val)
                                if item.estado_opc != val_bool:
                                    item.estado_opc = val_bool
                                    item.save(update_fields=['estado_opc'])
                            except Exception as e_node:
                                # Conseguiu conectar ao servidor mas falhou ao ler o nó específico
                                # → tag inexistente ou erro de leitura → marcar como offline (False)
                                logger.warning(f"Erro lendo nó {item.node_id_tag} em {url}: {e_node}")
                                if item.estado_opc is not False:
                                    item.estado_opc = False
                                    item.save(update_fields=['estado_opc'])

                    except Exception as e_conn:
                        # Servidor OPC inacessível → não alterar estado_opc (último valor conhecido)
                        logger.warning(f"Servidor OPC inacessível {url}: {e_conn}")
                    finally:
                        if client:
                            try:
                                client.disconnect()
                            except:
                                pass
                                
            except Exception as e:
                logger.error(f"Erro geral no loop de Intertravamentos: {e}")
            
            # Aguardar próximo tick
            self._stop_event.wait(self.interval)

def start_opc_service():
    worker = OPCIntertravamentoWorker(interval=4)
    worker.start()
    return worker
