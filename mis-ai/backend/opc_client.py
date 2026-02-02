# opc_client.py
import asyncio
import logging
from typing import Any, Optional, Tuple, Dict, Callable
from asyncua import Client, ua 
from models import OPCLogs, OPCVariables, get_db
from datetime import datetime, timezone, timedelta
import os

logger = logging.getLogger(__name__)

class OPCClient:
    def __init__(self, url: str, timeout: int = 15):
        self.url = url
        self.timeout = timeout
        self._client: Optional[Client] = None
        self.connected = False
        self.last_error: Optional[str] = None
        self.logging_tasks: Dict[str, asyncio.Task] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        logger.info(f"OPCClient criado para URL: {url} (timeout: {self.timeout}s)")

    async def connect(self) -> bool:
        if self.connected: return True
        logger.info(f"INICIANDO TENTATIVA DE CONEXÃO com o servidor OPC UA: {self.url}")
        try:
            self._client = Client(url=self.url, timeout=self.timeout)
            await self._client.connect()
            self.connected = True
            logger.info(f"*** SUCESSO: OPCClient conectado ao OPC UA: {self.url} ***")
            return True
        except Exception as e:
            logger.critical(f"FALHA CRÍTICA DE CONEXÃO OPC: {e}", exc_info=True)
            self.connected = False
            return False

    def schedule_task_safely(self, coro):
        if not self.loop or not self.loop.is_running():
            raise RuntimeError("O loop de eventos do OPC Client não está rodando.")
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()

    async def _execute_with_retry(self, operation: Callable, *args, **kwargs):
        """Executa uma operação com retry automático"""
        try:
            return await operation(*args, **kwargs)
        except (OSError, ConnectionError, asyncio.TimeoutError) as e:
            logger.warning(f"⚠️ Erro de conexão OPC: {e}. Tentando reconectar...")
            try:
                await self.disconnect()
                await asyncio.sleep(1)
                await self.connect()
                return await operation(*args, **kwargs)
            except Exception as retry_err:
                logger.error(f"❌ Retry falhou: {retry_err}")
                raise retry_err
        except Exception as e:
            raise e

    async def _read_variable_value(self, node_path: str) -> Tuple[Any, str]:
        if not self.connected: return None, "OPC client is not connected."
        
        async def _do_read():
            node = self._client.get_node(node_path)
            data_value = await node.read_data_value()
            if data_value.StatusCode.is_good():
                return data_value.Value.Value, "good"
            return None, f"bad_quality_{data_value.StatusCode}"

        try:
            return await self._execute_with_retry(_do_read)
        except Exception as e:
            return None, "error_reading_node"

    async def _write_variable_value(self, node_path: str, value: Any, value_type: str = "Float") -> Tuple[bool, str]:
        if not self.connected: 
            return False, "OPC client is not connected."
        
        async def _do_write():
            node = self._client.get_node(node_path)
            
            try:
                if value_type == "Float":
                    value_to_write = float(value)
                elif value_type == "Integer":
                    value_to_write = int(value)
                elif value_type == "Boolean":
                    value_to_write = bool(value)
                else:
                    value_to_write = str(value)
            except (ValueError, TypeError) as e:
                logger.error(f"Erro ao converter valor {value} para o tipo {value_type}")
                return False, f"Type_conversion_error: {e}"
            
            variant_type_map = {
                "Float": ua.VariantType.Float,
                "Double": ua.VariantType.Double, # <--- ADICIONADO SUPORTE A DOUBLE (64-bit)
                "Integer": ua.VariantType.Int64, 
                "Boolean": ua.VariantType.Boolean,
                "String": ua.VariantType.String,
            }
            variant_type = variant_type_map.get(value_type, ua.VariantType.Float)
            
            data_value_to_write = ua.DataValue(ua.Variant(value_to_write, variant_type))
            status_code = await node.write_value(data_value_to_write)
            
            logger.info(f"Write Return Type: {type(status_code)} Val: {status_code}")

            is_good = False
            if hasattr(status_code, 'is_good'):
                is_good = status_code.is_good()
            elif hasattr(status_code, 'is_good_value'): 
                is_good = status_code.is_good_value()
            elif isinstance(status_code, (list, tuple)):
                is_good = any(s.is_good() for s in status_code if hasattr(s, 'is_good'))
            else:
                is_good = str(status_code) == "Good" or "Good" in str(status_code)

            if status_code is None: is_good = True

            if is_good:
                logger.info(f"Sucesso ao escrever valor {value_to_write} no nó {node_path}")
                return True, "good"
            else:
                logger.error(f"Falha ao escrever no nó {node_path}. StatusCode: {status_code}")
                return False, f"bad_quality_{status_code}"

        try:
            return await self._execute_with_retry(_do_write)
        except Exception as e:
            logger.error(f"Erro ao escrever variável {node_path}: {e}")
            return False, str(e)

    async def _get_opc_values(self, line):
        if not self.connected: return None, "OPC client is not connected."
        db = next(get_db())
        try:
            variables = db.query(OPCVariables).filter(
                OPCVariables.line_name == line,
                OPCVariables.is_active == True
            ).all()
            
            if not variables: return {}, None
            opc_values = {}
            for var in variables:
                value, quality = await self._read_variable_value(var.node_id)
                if quality == "good":
                    try: opc_values[var.node_id] = float(value)
                    except (ValueError, TypeError): pass
            return opc_values, None
        finally:
            db.close()
    
    async def _logging_worker(self, line: str, interval_seconds: int = 60):
        logger.info(f"Worker de logging INICIADO para linha {line}, intervalo de {interval_seconds} segundos.")
        while True:
            try:
                opc_values, error = await self._get_opc_values(line)
                if error:
                    logger.warning(f"WORKER LOG: Erro ao obter valores OPC para a linha {line}: {error}")
                elif opc_values:
                    db = next(get_db())
                    try:
                        timestamp_utc = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=-3)))
                        for node_id, value in opc_values.items():
                            log_entry = OPCLogs(
                                line_name=line,
                                node_id=node_id,
                                value=value,
                                timestamp=timestamp_utc
                            )
                            db.add(log_entry)
                        db.commit()
                        logger.info(f"WORKER LOG: Sucesso! {len(opc_values)} logs salvos no banco para a linha {line}.")
                    except Exception as db_error:
                         logger.error(f"WORKER LOG: FALHA ao salvar logs no banco para a linha {line}.", exc_info=True)
                    finally:
                        db.close()
                else:
                    logger.info(f"WORKER LOG: Nenhum valor OPC com boa qualidade para logar na linha {line} neste ciclo.")
                
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                logger.info(f"Worker de logging para a linha {line} está sendo encerrado.")
                break
            except Exception as e:
                logger.error(f"Erro inesperado no worker para a linha {line}: {e}", exc_info=True)
                await asyncio.sleep(interval_seconds)

    def get_opc_values(self, line):
        return self.schedule_task_safely(self._get_opc_values(line))
    
    async def read_variable(self, node_path: str) -> Optional[Any]:
        """Wrapper Público"""
        val, qual = await self._read_variable_value(node_path)
        if qual == "good": return val
        return None
        
    async def write_value(self, node_path: str, value: Any) -> bool:
        """Alias para _write_variable_value para compatibilidade com app.py"""
        success, _ = await self._write_variable_value(node_path, value)
        return success
        
    def write_variable_value(self, node_path, value, value_type="Float"):
        return self.schedule_task_safely(self._write_variable_value(node_path, value, value_type))

    def start_logging_for_line(self, line):
        async def _start():
            if line in self.logging_tasks and not self.logging_tasks[line].done():
                return False, "Logging já está ativo para esta linha."
            
            db = next(get_db())
            try:
                variables = db.query(OPCVariables).filter(OPCVariables.line_name == line).all()
                if not variables:
                    return False, "Nenhuma variável OPC cadastrada. Registre ao menos uma antes de iniciar o logging."
            finally:
                db.close()

            task = self.loop.create_task(self._logging_worker(line))
            self.logging_tasks[line] = task
            logger.info(f"Tarefa de logging agendada para a linha {line}.")
            return True, "Logging iniciado com sucesso."
        return self.schedule_task_safely(_start())

    def stop_logging_for_line(self, line):
        async def _stop():
            task = self.logging_tasks.get(line)
            if not task or task.done():
                return False, "Logging não estava ativo para esta linha."
            
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass 
            
            if line in self.logging_tasks:
                del self.logging_tasks[line]
            logger.info(f"Tarefa de logging para a linha {line} foi cancelada.")
            return True, "Logging parado com sucesso."
        return self.schedule_task_safely(_stop())

    async def disconnect(self):
        """Desconecta do servidor OPC"""
        if self._client and self.connected:
            try:
                await self._client.disconnect()
                self.connected = False
                logger.info("OPCClient desconectado com sucesso.")
            except Exception as e:
                logger.error(f"Erro ao desconectar OPCClient: {e}", exc_info=True)
                self.connected = False 

    async def configure(self, new_url: str):
        """Atualiza a URL de conexão e força reconexão"""
        logger.info(f"Reconfigurando OPCClient para nova URL: {new_url}")
        
        if self.connected:
            await self.disconnect()
            
        self.url = new_url
        logger.info("OPCClient reconfigurado. Chame .connect() para estabelecer conexão.")

    def get_logging_status_for_line(self, line):
        task = self.logging_tasks.get(line)
        return task is not None and not task.done()

opc_server_url = os.getenv('OPC_SERVER_URL')
opc_client = OPCClient(url=opc_server_url)