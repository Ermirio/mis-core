# Coletor OPC UA - Serviço Standalone
# ====================================
# Autor: Sistema MIS
# Data: 2024
# Versão: 1.3 (Com Diagnóstico de CUC e Ingestão Dinâmica)

import asyncio
import json
import logging
import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
import requests
from asyncua import Client, ua
from asyncua.ua.uaerrors import BadNodeIdUnknown
from decouple import config
from opc_urls import normalize_opc_tcp_url

# [P0.4+P0.5+P0.6] Building blocks de resiliência.
# Se o módulo ainda não estiver disponível em ambiente legado, o import falha
# silenciosamente e o coletor segue no comportamento anterior (fail-safe).
try:
    from resilience import (
        retry_async,
        CircuitBreaker,
        CircuitOpenError,
        ConnectionWatchdog,
        OfflineBuffer,
        AsyncHttpClient,
    )
    RESILIENCE_AVAILABLE = True
except Exception as _e:  # pragma: no cover
    RESILIENCE_AVAILABLE = False
    logging.getLogger('Coletor').warning(
        f"⚠️ Módulo resilience indisponível ({_e}). Coletor rodará em modo legado."
    )

# ===== CONFIGURAÇÃO DE LOGGING =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('coletor.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logger = logging.getLogger('Coletor')

# ===== CONFIGURAÇÕES =====
DJANGO_API_URL = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')
# Endpoint de ingestao e comandos do coletor. O nome explicito evita manter
# o antigo acoplamento semantico ao backend Flask.
INGEST_API_URL = config('INGEST_API_URL', default=DJANGO_API_URL)
INTERVALO_COLETA = config('INTERVALO_COLETA', default=2, cast=int)
TIMEOUT_REQUEST = config('TIMEOUT_REQUEST', default=10, cast=int)
TAG_READ_TIMEOUT = config(
    'TAG_READ_TIMEOUT',
    default=min(float(TIMEOUT_REQUEST), 2.0),
    cast=float,
)
TAG_ERROR_LOG_INTERVAL = config('TAG_ERROR_LOG_INTERVAL', default=300.0, cast=float)

# ===== MODO DE OPERAÇÃO =====
# MIS_MODE=demo        → simulador interno, NÃO conecta em OPC real
# MIS_MODE=production  → comportamento padrão (OPC UA real)
MIS_MODE = config('MIS_MODE', default='production').strip().lower()
DEMO_BACKFILL_DIAS = config('DEMO_BACKFILL_DIAS', default=7, cast=int)
DEMO_BACKFILL_STEP_S = config('DEMO_BACKFILL_STEP_S', default=60, cast=int)
INFLUXDB_HOST = config('INFLUXDB_HOST', default='influxdb')
INFLUXDB_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUXDB_DATABASE = config('INFLUXDB_DATABASE', default='industrial_db')
INFLUXDB_USER = config('INFLUXDB_USER', default='admin')
INFLUXDB_PASSWORD = config('INFLUXDB_PASSWORD', default='admin123')

# Silencia logs verbosos do asyncua (evita tracebacks em timeouts esperados)
logging.getLogger("asyncua").setLevel(logging.ERROR)
logging.getLogger("asyncua.client.client").setLevel(logging.ERROR)
logging.getLogger("asyncua.client.ua_client.UaClient").setLevel(logging.ERROR)

# ===== MAPEAMENTO DE ESTADOS =====
# Mapeamento dos códigos numéricos do PLC para o vocabulário do MIS.
# CORREÇÃO: índices 12 e 13 estavam errados antes.
#   Antes: 12 → 'PARANDO' (errado), 13 ausente.
#   Agora: 12 → 'AGUARD_COND' (Aguardando condições), 13 → 'PARANDO'.
# Alinha com EstadoEquipamento no Django (equipamentos/models.py).
MAPEAMENTO_ESTADOS = {
    0: 'OUTRO',
    1: 'RUN',
    2: 'WAIT_PREV',
    3: 'BLOCK_NEXT',
    4: 'FAULT',
    5: 'SETUP',
    6: 'TESTE_PROJ',
    7: 'AGUARD_MNT',
    8: 'MANUTENCAO',
    9: 'FALTA_MAT',
    10: 'OUTRO',          # Reservado
    11: 'PARTINDO',
    12: 'AGUARD_COND',    # Aguardando condições (corrigido — era 'PARANDO' errado)
    13: 'PARANDO',        # Parando (adicionado — faltava)
    999: 'OFFLINE',       # Forçado pelo coletor quando PLC perde comunicação
}

CANONICAL_TAG_TYPES = {
    'contagem_entrada': 'INT',
    'contagem_saida': 'INT',
    'estado': 'INT',
    'estado_maquina': 'INT',
    'velocidade': 'FLOAT',
    'velocidade_real': 'FLOAT',
    'velocidade_atual': 'FLOAT',
    'ordem_producao': 'STRING',
    'sku_codigo': 'STRING',
    'descricao': 'STRING',
    'formato': 'FLOAT',
    'formato_gramas': 'FLOAT',
    'planejado_op': 'INT',
    'cuc': 'FLOAT',
    'descarte': 'INT',
}


def canonical_tag_type(nome: str, tipo_configurado: str = None) -> str:
    return CANONICAL_TAG_TYPES.get(str(nome or '').strip(), str(tipo_configurado or 'STRING').upper())


@dataclass(frozen=True)
class TagReadResult:
    status: str
    value: Any = None
    observed_type: str = 'UNKNOWN'
    data_type: str = 'UNKNOWN'
    value_rank: Optional[int] = None
    status_code: str = 'UNKNOWN'
    error: Optional[str] = None


def _type_name(value: Any) -> str:
    return type(value).__name__.upper() if value is not None else 'NULL'


def _convert_opc_value(value: Any, expected_type: str, factor: float = 1.0) -> Any:
    """Converte somente quando a operação é explícita e sem perda semântica."""
    expected = str(expected_type or '').strip().upper()
    if value is None:
        raise ValueError('valor Null')
    if isinstance(value, (list, tuple, dict, set)):
        raise ValueError('array/estrutura não suportado para tag escalar')

    try:
        scale = float(factor if factor is not None else 1.0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'escala inválida: {factor!r}') from exc
    if not math.isfinite(scale):
        raise ValueError(f'escala não finita: {factor!r}')

    if expected == 'FLOAT':
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f'{_type_name(value)} não é numérico')
        converted = float(value)
        if isinstance(value, int) and int(converted) != value:
            raise ValueError('inteiro não pode ser representado como float sem perda')
        converted *= scale
        if not math.isfinite(converted):
            raise ValueError('resultado numérico não finito')
        return converted

    if expected == 'INT':
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f'{_type_name(value)} não é inteiro')
        converted = float(value) * scale
        if not math.isfinite(converted) or not converted.is_integer():
            raise ValueError(f'{value!r} com escala {scale!r} perderia casas decimais')
        return int(converted)

    if expected == 'BOOL':
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        if isinstance(value, str) and value.strip().lower() in {
            '0', '1', 'false', 'true', 'não', 'nao', 'sim', 'no', 'yes', 'off', 'on'
        }:
            return value.strip().lower() in {'1', 'true', 'sim', 'yes', 'on'}
        raise ValueError(f'{value!r} não é booleano inequívoco')

    if expected == 'STRING':
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        raise ValueError(f'{_type_name(value)} não é escalar textual')

    raise ValueError(f'tipo configurado não suportado: {expected or "VAZIO"}')


def inferir_estado_status_booleanos(medicoes: Dict) -> Optional[tuple]:
    """Converte os quatro sinais ISA de estado em estado canônico do MIS.

    Só atua quando os quatro sinais estão presentes. A precedência evita que
    estados simultâneos ou transições rápidas escondam falha/bloqueio.
    Retorna (código PLC, estado MIS) ou None quando a fonte é insuficiente.
    """
    nomes = ('StatusRunning', 'StatusWaiting', 'StatusBlocked', 'StatusFault')
    if not all(nome in medicoes for nome in nomes):
        return None
    if bool(medicoes['StatusFault']):
        return 4, 'FAULT'
    if bool(medicoes['StatusBlocked']):
        return 3, 'BLOCK_NEXT'
    if bool(medicoes['StatusWaiting']):
        return 2, 'WAIT_PREV'
    if bool(medicoes['StatusRunning']):
        return 1, 'RUN'
    return 0, 'OUTRO'


class ColetorOPC:
    def __init__(self):
        self.configuracao = None
        self.clientes_opc = {} # URL -> Client
        self.conexoes_info = {} # URL -> { 'tag_monitoramento': ..., 'tipo_monitoramento': ..., 'status_ok': Bool }
        self.ultima_atualizacao_config = None
        self.estados_anteriores = {}
        self.metadata_anteriores = {}
        self.urls_invalidas_reportadas = set()
        self.urls_normalizadas_reportadas = set()
        self.urls_watchdog_registradas = set()
        self._heartbeat_client = None
        self.ultimas_leituras_validas = {}
        self.tag_metadata_cache = {}
        self.tag_error_log_state = {}

        # --- [P0.4+P0.5+P0.6] Componentes de resiliência ---
        if RESILIENCE_AVAILABLE:
            self.http = AsyncHttpClient(timeout=TIMEOUT_REQUEST)
            self.buffer = OfflineBuffer(
                db_path=config('COLETOR_BUFFER_DB', default='coletor_buffer.db'),
                max_attempts=20,
            )
            # Um circuit breaker por endpoint crítico — failure em um não afeta o outro
            self.cb_ingest = CircuitBreaker(name='ingest-api', fail_threshold=5, reset_timeout=30.0)
            self.cb_django = CircuitBreaker(name='django-api', fail_threshold=5, reset_timeout=30.0)
            self.watchdog = ConnectionWatchdog(
                health_check_fn=self.verificar_saude_conexao,
                reconnect_fn=self._reconectar_url,
                check_interval=config('WATCHDOG_INTERVAL', default=10.0, cast=float),
                unhealthy_streak_to_reconnect=2,
            )
        else:
            self.http = None
            self.buffer = None
            self.cb_ingest = None
            self.cb_django = None
            self.watchdog = None

    async def inicializar(self):
        logger.info("=" * 60)
        logger.info("COLETOR OPC UA - ARQUITETURA CENTRALIZADA (V2.0)")
        logger.info("=" * 60)
        
        if not await self.atualizar_configuracao():
            logger.error("❌ Falha crítica: Sem configuração do Django.")
            return False
        
        # Conexão Inicial
        await self.gerenciar_conexoes()
        return True

    async def atualizar_configuracao(self) -> bool:
        try:
            url = f"{DJANGO_API_URL}/configuracao_coletor/"
            response = requests.get(url, timeout=TIMEOUT_REQUEST)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') != 'success': return False

            # Normaliza antes de calcular o hash. Assim um Django legado que
            # ainda devolva "opc.tcp//..." nao provoca reload a cada ciclo.
            for eq in data.get('equipamentos', []):
                conn = eq.get('conexao_detalhes') or {}
                raw_url = conn.get('url')
                if not raw_url:
                    continue
                try:
                    normalized_url = normalize_opc_tcp_url(raw_url)
                except ValueError:
                    continue
                if normalized_url != str(raw_url).strip():
                    report_key = f'{raw_url!r}->{normalized_url!r}'
                    if report_key not in self.urls_normalizadas_reportadas:
                        logger.warning(
                            f"URL OPC normalizada: {raw_url!r} -> {normalized_url!r}"
                        )
                        self.urls_normalizadas_reportadas.add(report_key)
                    conn['url'] = normalized_url
            
            # Verifica hash
            # O timestamp muda em toda resposta, mas nao representa mudanca de
            # configuracao. Ignora-lo evita reload e logs a cada ciclo.
            dados_hash = {k: v for k, v in data.items() if k != 'timestamp'}
            config_hash = {
                k: v for k, v in (self.configuracao or {}).items()
                if k != 'timestamp'
            }
            novo_hash = json.dumps(dados_hash, sort_keys=True)
            atual_hash = json.dumps(config_hash, sort_keys=True) if self.configuracao else ""
            
            if novo_hash != atual_hash:
                self.configuracao = data
                self.tag_metadata_cache.clear()
                logger.info(f"✅ NOVA Configuração carregada. {len(data.get('equipamentos', []))} equipamentos.")
                await self.gerenciar_conexoes() # Reconecta se mudar config
                return True
            
            return True
        except Exception as e:
            logger.error(f"❌ Erro config Django: {e}")
            return False
    
    async def gerenciar_conexoes(self):
        """Gerencia conexões baseadas na configuração agrupada"""
        if not self.configuracao: return

        urls_ativas = set()
        equipamentos = self.configuracao.get('equipamentos', [])

        # 1. Identificar conexões únicas necessárias
        for eq in equipamentos:
            conn = eq.get('conexao_detalhes')
            if conn and conn.get('url'):
                raw_url = conn['url']
                try:
                    url = normalize_opc_tcp_url(raw_url)
                except ValueError as exc:
                    invalid_key = str(raw_url)
                    if invalid_key not in self.urls_invalidas_reportadas:
                        logger.error(
                            f"Conexao OPC invalida {raw_url!r}: {exc}. "
                            f"Corrija no admin para opc.tcp://HOST:PORTA."
                        )
                        self.urls_invalidas_reportadas.add(invalid_key)
                    continue

                if url != str(raw_url).strip():
                    logger.warning(f"URL OPC normalizada: {raw_url!r} -> {url!r}")
                # Mantem toda a execucao usando a mesma chave normalizada.
                conn['url'] = url
                urls_ativas.add(url)
                # Atualiza metadados da conexão (tag monitoramento)
                self.conexoes_info[url] = {
                    'tag_monitoramento': conn.get('tag_monitoramento'),
                    'tipo_monitoramento': conn.get('tipo_monitoramento', 'HEARTBEAT'),
                    'nome': conn.get('nome'),
                    'status_ok': False # Reset status
                }

        # 2. Remover conexões obsoletas
        for url in list(self.clientes_opc.keys()):
            if url not in urls_ativas:
                try: 
                    logger.info(f"⚠️ Desconectando servidor obsoleto: {url}")
                    await self.clientes_opc[url].disconnect()
                except: pass
                del self.clientes_opc[url]

        for url in list(self.conexoes_info.keys()):
            if url not in urls_ativas:
                self.conexoes_info.pop(url, None)

        if self.watchdog is not None:
            for url in self.urls_watchdog_registradas - urls_ativas:
                self.watchdog.unregister(url)
            self.urls_watchdog_registradas.intersection_update(urls_ativas)

        # 3. Criar novas conexões
        # [P0.4] Retry com backoff exponencial para não flodar o OPC server
        # se ele estiver inicializando ou em rede instável.
        for url in urls_ativas:
            if url not in self.clientes_opc:
                await self._conectar_url(url)

            # Registrar no watchdog para supervisão contínua
            if self.watchdog is not None:
                self.watchdog.register(url)
                self.urls_watchdog_registradas.add(url)

    async def _conectar_url(self, url: str) -> bool:
        """[P0.4] Conecta a um OPC UA com retry exponencial. Retorna True se sucesso."""
        try:
            url = normalize_opc_tcp_url(url)
        except ValueError as exc:
            logger.error(f"Conexao OPC invalida {url!r}: {exc}")
            return False

        async def _do_connect():
            c = Client(url=url, timeout=5)
            await c.connect()
            return c

        try:
            if RESILIENCE_AVAILABLE:
                c = await retry_async(
                    _do_connect,
                    retryable_exceptions=(OSError, ConnectionError, asyncio.TimeoutError, TimeoutError, Exception),
                    max_attempts=3,
                    base_delay=1.0,
                    max_delay=8.0,
                    operation_name=f'opc.connect[{url}]',
                )
            else:
                c = await _do_connect()
            self.clientes_opc[url] = c
            logger.info(f"✅ Conectado a {url}")
            return True
        except Exception as e:
            logger.error(f"❌ Falha ao conectar {url}: {e}", exc_info=True)
            return False

    async def _reconectar_url(self, url: str) -> bool:
        """[P0.5] Reconexão disparada pelo watchdog — desconecta antigo + conecta novo."""
        old = self.clientes_opc.get(url)
        if old:
            try:
                await asyncio.wait_for(old.disconnect(), timeout=3.0)
            except Exception as e:
                logger.debug(f"[reconnect] disconnect antigo falhou (OK): {e}")
            self.clientes_opc.pop(url, None)
        return await self._conectar_url(url)

    # NOTE: A definição real de `async def executar(...)` está mais abaixo neste
    # arquivo (v2 resiliente, versão com watchdog + buffer + circuit breaker).
    # Em Python, o último método definido na classe sobrescreve os anteriores,
    # então a duplicata antiga foi removida para evitar divergência/confusão.

    async def verificar_saude_conexao(self, url: str) -> bool:
        """Verifica se a conexão está saudável (Ping + Tag de Monitoramento)"""
        client = self.clientes_opc.get(url)
        info = self.conexoes_info.get(url) or {}

        if not client: return False

        try:
            # 1. Teste Básico de Conexão (Ler Root Folder ou ServerStatus)
            # O próprio client.get_node... já testa um pouco

            # 2. Tag de Monitoramento (Se configurada)
            tag_mon = None if info.get('_tag_mon_disabled') else info.get('tag_monitoramento')
            # IMPORTANTE: tag_monitoramento precisa ter formato OPC NodeId
            # (i=NN, ns=N;s=..., ns=N;i=NN, b=, g=). Se vier uma URL ou texto
            # solto (config errada no Django admin), o parser da asyncua quebra
            # com "not enough values to unpack" e a conexao fica eternamente
            # OFFLINE -> equipamentos travam em estado 999.
            # Solucao: validar formato; se invalido, ignorar e considerar OK.
            def _looks_like_nodeid(s: str) -> bool:
                s = str(s).strip()
                if not s:
                    return False
                return s.startswith(('i=', 'ns=', 's=', 'b=', 'g='))

            if tag_mon and not _looks_like_nodeid(tag_mon):
                if not info.get('_tag_mon_warned'):
                    logger.warning(
                        f"⚠️ tag_monitoramento invalida em {url}: {tag_mon!r}. "
                        f"Formato esperado: 'ns=N;s=Tag' ou 'i=84'. "
                        f"Ignorando health check de tag — usando apenas ping de conexao."
                    )
                    info['_tag_mon_warned'] = True
                tag_mon = None  # ignora e passa adiante

            if tag_mon:
                node = client.get_node(tag_mon)
                try:
                    val = await node.read_value()
                except BadNodeIdUnknown:
                    # A sessao OPC esta ativa; apenas o NodeId opcional de
                    # monitoramento nao existe. Nao derruba 126 equipamentos
                    # por um erro de cadastro que nao afeta as tags de coleta.
                    if not info.get('_tag_mon_missing_warned'):
                        logger.warning(
                            f"tag_monitoramento inexistente em {url}: {tag_mon!r} "
                            f"(BadNodeIdUnknown). Desabilitando somente este "
                            f"health check; corrija ou deixe o campo vazio no admin."
                        )
                        info['_tag_mon_missing_warned'] = True
                    info['_tag_mon_disabled'] = True
                    return True

                # Lógica de Erro
                tipo = info.get('tipo_monitoramento')
                if tipo == 'ERROR_BOOL':
                    # Se True = ERRO
                    if bool(val):
                        logger.warning(f"🚨 ERRO NA CONEXÃO {url} (Tag {tag_mon} = True)")
                        return False

                # Logica Heartbeat seria comparar timestamp, mas por simplicidade
                # assumimos que se LEU, está OK (o nível acima cuida de stale data)
            else:
                # Sem uma tag opcional de monitoramento, ainda precisamos fazer
                # I/O real. Apenas possuir um objeto ``Client`` não comprova que
                # o socket/sessão OPC continua ativo; ``get_node`` também é uma
                # operação local e não detecta cliente desconectado. Ler o estado
                # padrão do servidor permite que o watchdog reconheça a queda e
                # execute ``_reconectar_url`` automaticamente.
                await client.get_node('i=2259').read_value()

            return True
        except Exception as e:
            logger.warning(f"⚠️ Falha Saúde Conexão {url}: {e}")
            # Tentar reconectar?
            return False
    
    def mapear_estado_opc(self, valor_opc: int) -> str:
        return MAPEAMENTO_ESTADOS.get(valor_opc, 'OUTRO')
    
    async def enviar_evento_estado(
        self, equipamento_codigo: str, estado: str,
        equipamento_slug: Optional[str] = None,
        linha_codigo: Optional[str] = None,
    ) -> bool:
        """Envia evento de transição de estado. Usa http assíncrono se disponível.

        Identidade do equipamento (preferência decrescente):
          - equipamento_slug ("L01.E001") — preferido, exato e único globalmente.
          - equipamento_codigo + linha_codigo — desambigua sem slug.
          - equipamento_codigo sozinho — só funciona em base com códigos únicos
            globalmente; em qualquer instalação > 1 linha pode dar 409.
        """
        url = f"{DJANGO_API_URL}/eventos_estado/"
        payload: Dict[str, Any] = {
            'estado': estado,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'origem': 'OPC',
        }
        if equipamento_slug:
            payload['equipamento_slug'] = equipamento_slug
        if equipamento_codigo:
            payload['equipamento_codigo'] = equipamento_codigo
        if linha_codigo:
            payload['linha_codigo'] = linha_codigo
        ident_log = equipamento_slug or f"{linha_codigo}.{equipamento_codigo}" if linha_codigo else equipamento_codigo
        try:
            if self.http is not None:
                return await self.http.post_json(url, payload)
            # Fallback síncrono em thread — não bloqueia event loop
            def _do():
                try:
                    r = requests.post(url, json=payload, timeout=TIMEOUT_REQUEST)
                    return 200 <= r.status_code < 300
                except Exception:
                    return False
            return await asyncio.to_thread(_do)
        except Exception as e:
            logger.warning(f"⚠️ enviar_evento_estado({ident_log}): {e}", exc_info=True)
            return False

    async def enviar_metadata_django(self, dados: Dict) -> bool:
        """Sync de metadata (OP/SKU/formato) — só fala com o Django."""
        url = f"{DJANGO_API_URL}/equipamentos/sync_metadata/"
        try:
            if self.http is not None:
                return await self.http.post_json(url, dados)
            def _do():
                try:
                    r = requests.post(url, json=dados, timeout=TIMEOUT_REQUEST)
                    return 200 <= r.status_code < 300
                except Exception:
                    return False
            return await asyncio.to_thread(_do)
        except Exception as e:
            logger.warning(f"⚠️ enviar_metadata_django: {e}", exc_info=True)
            return False

    async def _metadata_tag(self, node, node_id: str) -> tuple[str, Optional[int]]:
        """Lê DataType/ValueRank em melhor esforço, apenas para diagnóstico."""
        cache_key = str(node_id)
        cached = self.tag_metadata_cache.get(cache_key)
        if cached is not None:
            return cached

        data_type = 'UNKNOWN'
        value_rank = None
        metadata_timeout = min(TAG_READ_TIMEOUT, 1.0)
        try:
            raw_type = await asyncio.wait_for(
                node.read_data_type(), timeout=metadata_timeout
            )
            data_type = str(raw_type)
        except Exception:
            pass
        try:
            value_rank = await asyncio.wait_for(
                node.read_value_rank(), timeout=metadata_timeout
            )
        except Exception:
            pass
        result = (data_type, value_rank)
        self.tag_metadata_cache[cache_key] = result
        return result

    async def ler_tag_opc(
        self,
        cliente: Client,
        node_id: str,
        tipo_dado: str,
        fator_conversao: float = 1.0,
    ) -> TagReadResult:
        try:
            if not node_id:
                return TagReadResult(status='CONFIG_ERROR', error='NodeId vazio')
            node = cliente.get_node(node_id)
            data_value = await asyncio.wait_for(
                node.read_data_value(), timeout=TAG_READ_TIMEOUT
            )
            variant = getattr(data_value, 'Value', None)
            valor = getattr(variant, 'Value', None)
            variant_type = getattr(variant, 'VariantType', None)
            observed_type = getattr(variant_type, 'name', str(variant_type or _type_name(valor)))
            status_obj = getattr(data_value, 'StatusCode', None)
            status_code = str(status_obj or 'UNKNOWN')
            is_good = getattr(status_obj, 'is_good', None)
            if callable(is_good) and not is_good():
                data_type, value_rank = await self._metadata_tag(node, node_id)
                return TagReadResult(
                    status='NO_READ', observed_type=observed_type,
                    data_type=data_type, value_rank=value_rank,
                    status_code=status_code, error='StatusCode OPC ruim',
                )

            try:
                convertido = _convert_opc_value(valor, tipo_dado, fator_conversao)
            except ValueError as exc:
                data_type, value_rank = await self._metadata_tag(node, node_id)
                if value_rank is None:
                    value_rank = 1 if isinstance(valor, (list, tuple)) else -1
                return TagReadResult(
                    status='CONFIG_ERROR', observed_type=observed_type,
                    data_type=data_type, value_rank=value_rank,
                    status_code=status_code, error=str(exc),
                )
            return TagReadResult(
                status='OK', value=convertido, observed_type=observed_type,
                data_type=observed_type,
                value_rank=1 if isinstance(valor, (list, tuple)) else -1,
                status_code=status_code,
            )
        except BadNodeIdUnknown as exc:
            return TagReadResult(
                status='CONFIG_ERROR', error=f'NodeId inexistente: {exc}'
            )
        except (OSError, ConnectionError, asyncio.TimeoutError, TimeoutError, AttributeError) as e:
            return TagReadResult(status='NO_READ', error=f'falha/timeout de leitura: {e}')
        except Exception as e:
            error_name = type(e).__name__
            status = 'CONFIG_ERROR' if ('NodeId' in error_name or 'TypeMismatch' in error_name) else 'NO_READ'
            return TagReadResult(status=status, error=f'{error_name}: {e}')

    def _should_log_tag_issue(self, tag_key: str, leitura: TagReadResult) -> bool:
        signature = (
            leitura.status,
            leitura.observed_type,
            leitura.status_code,
            leitura.error,
        )
        now = time.monotonic()
        previous = self.tag_error_log_state.get(tag_key)
        if previous and previous["signature"] == signature:
            if now - previous["logged_at"] < TAG_ERROR_LOG_INTERVAL:
                return False
        self.tag_error_log_state[tag_key] = {
            "signature": signature,
            "logged_at": now,
        }
        return True

    async def coletar_dados_equipamento(self, equipamento: Dict, cliente_ativo: Client, conexao_ok: bool) -> Optional[Dict]:
        try:
            codigo = equipamento['codigo']
            # slug globalmente único (Solução 2 da identidade ISA-95). Quando o
            # Django expõe via /configuracao_coletor/, vem como "L01.E001".
            # Fallback construído da linha+codigo caso o servidor ainda não
            # tenha sido atualizado (retrocompat).
            slug = equipamento.get('slug')
            linha_codigo = equipamento.get('linha_codigo')  # Extract Line Code from config
            area_codigo = equipamento.get('area_codigo')
            fabrica_codigo = equipamento.get('fabrica_codigo')
            if not slug and linha_codigo and codigo:
                slug = f"{linha_codigo}.{codigo}"
            identity_key = slug or (f"{linha_codigo}.{codigo}" if linha_codigo else codigo)
            medicoes = {}

            # Se a conexão principal está ruim, força OFFLINE
            if not conexao_ok:
                medicoes['connection_status'] = 'OFFLINE'
                medicoes['estado_maquina'] = 999
                return {
                    "equipamento_codigo": codigo,
                    "equipamento_slug": slug,
                    "linha_codigo": linha_codigo,
                    "area_codigo": area_codigo,
                    "fabrica_codigo": fabrica_codigo,
                    "medicoes": medicoes,
                    "timestamp": datetime.utcnow().isoformat() + 'Z',
                    "_collector_stats": {
                        "valid": 0,
                        "rejected": 0,
                        "no_read": len(equipamento.get('tags_coleta', [])),
                    },
                }

            # --- Conexão OK, Ler Tags ---
            tags = equipamento.get('tags_coleta', [])
            
            # Metadata Init
            metadata = {
                'equipamento_codigo': codigo,
                'equipamento_slug': slug,
                'linha_codigo': linha_codigo,
                'op_codigo': None,
                'sku_codigo': None,
                'descricao': None,
                'formato': None,
                'meta_producao': None,
            }
            estado_txt, estado_num = None, None
            tag_stats = {"valid": 0, "rejected": 0, "no_read": 0}

            for tag in tags:
                nome = tag['nome_metrica']
                if not tag.get('node_id'):
                    tag_stats["rejected"] += 1
                    continue
                # Nota: A URL na tag (conexao_detalhes) pode ser ignorada ou validada,
                # assumimos que usamos o 'cliente_ativo' passado (da conexão do equip)
                
                tipo_tag = canonical_tag_type(nome, tag.get('tipo_dado'))
                leitura = await self.ler_tag_opc(
                    cliente_ativo,
                    tag['node_id'],
                    tipo_tag,
                    tag.get('fator_conversao', 1.0),
                )

                tag_key = f"{identity_key}|{nome}|{tag['node_id']}"
                if leitura.status == 'OK':
                    valor = leitura.value
                    tag_stats["valid"] += 1
                    self.ultimas_leituras_validas[tag_key] = {
                        "valor": valor,
                        "timestamp": datetime.utcnow().isoformat() + 'Z',
                    }
                    if self.tag_error_log_state.pop(tag_key, None) is not None:
                        logger.info(
                            "TAG_RECOVERED linha=%s equipamento=%s metrica=%s node_id=%s",
                            linha_codigo,
                            slug or codigo,
                            nome,
                            tag['node_id'],
                        )
                else:
                    counter = "rejected" if leitura.status == 'CONFIG_ERROR' else "no_read"
                    tag_stats[counter] += 1
                    last_valid = self.ultimas_leituras_validas.get(tag_key)
                    if self._should_log_tag_issue(tag_key, leitura):
                        logger.warning(
                            "TAG_%s linha=%s equipamento=%s metrica=%s node_id=%s "
                            "tipo_configurado=%s tipo_observado=%s data_type=%s "
                            "value_rank=%s status_code=%s ultima_leitura_valida=%s erro=%s",
                            leitura.status,
                            linha_codigo,
                            slug or codigo,
                            nome,
                            tag['node_id'],
                            tipo_tag,
                            leitura.observed_type,
                            leitura.data_type,
                            leitura.value_rank,
                            leitura.status_code,
                            last_valid,
                            leitura.error,
                        )
                    continue

                if valor is not None:
                    medicoes[nome] = valor
                    if nome in ('velocidade', 'velocidade_real'):
                        medicoes['velocidade_atual'] = valor
                    
                    # Preenchimento de Metadata e Estado (Lógica Padrão)
                    if nome == 'ordem_producao': metadata['op_codigo'] = str(valor)
                    elif nome == 'sku_codigo': metadata['sku_codigo'] = str(valor)
                    elif nome == 'descricao': metadata['descricao'] = str(valor)
                    elif nome == 'formato': 
                        try: 
                            val = float(valor)
                            metadata['formato'] = val
                            medicoes['formato_gramas'] = val
                        except: pass
                    elif nome == 'planejado_op':
                        try: metadata['meta_producao'] = int(float(valor))
                        except: pass
                    elif nome in ('estado', 'estado_maquina'):
                        try:
                            estado_num = int(valor)
                            medicoes['estado_maquina'] = estado_num
                            estado_txt = self.mapear_estado_opc(estado_num)
                        except:
                            medicoes['estado_maquina'] = 0
            
            # Equipamentos sem estado numérico dedicado podem expor os
            # quatro sinais booleanos ISA. Usa-os apenas quando o estado
            # dedicado não foi lido e quando todos os sinais estão presentes.
            if estado_num is None:
                estado_inferido = inferir_estado_status_booleanos(medicoes)
                if estado_inferido is not None:
                    estado_num, estado_txt = estado_inferido
                    medicoes['estado_maquina'] = estado_num

            # Enviar Metadata se mudou
            if metadata['op_codigo'] or metadata['sku_codigo']:
                 # Hash check simplificado
                 prev = self.metadata_anteriores.get(identity_key)
                 curr_hash = json.dumps(metadata, sort_keys=True)
                 if prev != curr_hash:
                     logger.info(f"📦 Metadata Update {identity_key}: {metadata}")
                     await self.enviar_metadata_django(metadata)
                     self.metadata_anteriores[identity_key] = curr_hash

            # Evento de Estado — propaga slug e linha para desambiguar no Django
            last_st = self.estados_anteriores.get(identity_key)
            current_st = medicoes.get('estado_maquina')
            if current_st is not None and current_st != last_st:
                logger.info(f"🔄 Estado {slug or codigo}: {last_st} -> {current_st}")
                msg_est = estado_txt if estado_txt else str(current_st)
                await self.enviar_evento_estado(
                    codigo, msg_est,
                    equipamento_slug=slug,
                    linha_codigo=linha_codigo,
                )
                self.estados_anteriores[identity_key] = current_st

            return {
                "equipamento_codigo": codigo,
                "equipamento_slug": slug,
                "linha_codigo": linha_codigo,
                "area_codigo": area_codigo,
                "fabrica_codigo": fabrica_codigo,
                "medicoes": medicoes,
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "_collector_stats": tag_stats,
            }

        except Exception as e:
            logger.error(f"Erro coleta {equipamento['codigo']}: {e}")
            return None

    async def enviar_para_ingestao(self, dados: Dict) -> bool:
        try:
            url = f"{INGEST_API_URL}/dados/inserir"
            requests.post(url, json=dados, timeout=TIMEOUT_REQUEST)
            return True
        except Exception as e:
            logger.error(f"Erro envio ingestao: {e}")
            return False
    
    async def ciclo_coleta(self):
        if not self.configuracao: return
        for eq in self.configuracao.get('equipamentos', []):
            dados = await self.coletar_dados_equipamento(eq)
            if dados: await self.enviar_para_ingestao(dados)
    
    async def escrever_tag_opc(self, cliente: Client, node_id: str, valor: any, tipo_dado: str) -> bool:
        """
        Escreve um valor no OPC UA com segurança de tipo e tratamento de erro.
        Usa write_attribute para evitar BadWriteNotSupported.
        """
        try:
            node = cliente.get_node(node_id)
            
            variant_val = None
            if tipo_dado == 'INT':
                variant_val = ua.Variant(int(valor), ua.VariantType.Int16) # Try Int16 first
            elif tipo_dado == 'FLOAT':
                variant_val = ua.Variant(float(valor), ua.VariantType.Float)
            elif tipo_dado == 'BOOL':
                variant_val = ua.Variant(bool(valor), ua.VariantType.Boolean)
            else:
                variant_val = ua.Variant(valor) # Auto-detect

            # Create DataValue explicitly to avoid compatibility issues
            # WARNING: Accessing ServerTimestamp property directly might fail on some bindings
            # Constructor defaults to None for timestamps, which is what we want.
            dv = ua.DataValue(variant_val)
            
            # Write Value Attribute directly
            await node.write_attribute(ua.AttributeIds.Value, dv)
            
            logger.info(f"✅ ESCRITA SUCESSO: {node_id} -> {valor} ({tipo_dado})")
            return True
        except Exception as e:
            logger.error(f"❌ FALHA ESCRITA OPC {node_id}: {e}")
            return False

    async def verificar_comandos(self):
        """Busca comandos pendentes no backend de ingestao e reporta resultado."""
        logger.info("🔍 DEBUG: verificar_comandos() INICIADO")
        try:
            url = f"{INGEST_API_URL}/golden-state/pending"
            logger.info(f"🔍 DEBUG: Buscando comandos em {url}")
            response = requests.get(url, timeout=TIMEOUT_REQUEST)
            if not response.ok: return
            
            batches = response.json()
            logger.info(f"🔍 DEBUG: Recebidos {len(batches)} batches do backend de ingestao")
            if not batches: return

            logger.info(f"📩 Recebidos {len(batches)} lotes de comando.")

            for batch in batches:
                batch_id = batch.get('id')
                eq_codigo = batch.get('equipamento_codigo')
                commands = batch.get('commands', [])
                
                success_count = 0
                error_count = 0
                
                # Encontrar configurações
                eq_config = next((e for e in self.configuracao.get('equipamentos', []) if e['codigo'] == eq_codigo), None)
                if not eq_config:
                    logger.warning(f"Equipamento {eq_codigo} não encontrado.")
                    # Report Failure
                    self.reportar_status_batch(batch_id, 'ERROR', "Equipamento não configurado no Coletor.")
                    continue
                
                # CORREÇÃO CRÍTICA: Buscar URL da conexão OPC do EQUIPAMENTO (não da tag)
                conn_details = eq_config.get('conexao_detalhes', {})
                url_server = conn_details.get('url')
                
                if not url_server:
                    error_msg = f"Equipamento {eq_codigo} não possui URL de conexão OPC configurada"
                    logger.error(f"❌ {error_msg}")
                    self.reportar_status_batch(batch_id, 'ERROR', error_msg)
                    continue
                
                logger.info(f"🔍 DEBUG: Equipamento {eq_codigo} → URL OPC: {url_server}")
                logger.info(f"🔍 DEBUG: Clientes OPC disponíveis: {list(self.clientes_opc.keys())}")
                
                # Verificar se cliente OPC está conectado ANTES do loop
                cliente = self.clientes_opc.get(url_server)
                if not cliente:
                    error_msg = f"Cliente OPC não conectado para URL '{url_server}' (Equipamento: {eq_codigo})"
                    logger.error(f"❌ {error_msg}")
                    logger.error(f"💡 DICA: Verifique se a conexão OPC está ativa")
                    self.reportar_status_batch(batch_id, 'ERROR', error_msg)
                    continue
                
                logger.info(f"✅ Cliente OPC encontrado para {eq_codigo}")
                
                # Report Started
                self.reportar_status_batch(batch_id, 'PENDING', "Iniciando escrita...", {'current': 0, 'total': len(commands)})
                
                success_count = 0
                error_count = 0
                
                for i, cmd in enumerate(commands):
                    tag_name = cmd.get('tag')
                    valor = cmd.get('value')
                    
                    # Report Progress
                    msg = f"Escrevendo {tag_name} ({i+1}/{len(commands)})..."
                    self.reportar_status_batch(batch_id, 'PENDING', msg, {'current': i, 'total': len(commands)})
                    
                    tag_config = next((t for t in eq_config.get('tags_coleta', []) if t['nome_metrica'] == tag_name), None)
                    if not tag_config:
                        error_msg = f"Tag '{tag_name}' não encontrada na configuração do equipamento {eq_codigo}"
                        logger.warning(f"❌ {error_msg}")
                        self.reportar_status_batch(batch_id, 'PENDING', error_msg, {'current': i, 'total': len(commands)})
                        error_count += 1
                        continue
                    
                    node_id = tag_config['node_id']
                    tipo = tag_config.get('tipo_dado', 'FLOAT')
                    
                    logger.info(f"🔍 DEBUG: Escrevendo '{tag_name}' → NodeID={node_id}, Tipo={tipo}, Valor={valor}")
                    
                    # Cliente já foi validado antes do loop
                    ok = await self.escrever_tag_opc(cliente, node_id, valor, tipo)
                    if ok: 
                        success_count += 1
                        logger.info(f"✅ ESCRITA SUCESSO: {tag_name} = {valor}")
                    else: 
                        error_count += 1
                        error_msg = f"Falha ao escrever {tag_name}: Erro na comunicação OPC UA"
                        logger.error(f"❌ {error_msg}")
                        self.reportar_status_batch(batch_id, 'PENDING', error_msg, {'current': i, 'total': len(commands)})

                # Report Final Status for Batch
                final_status = 'SUCCESS' if error_count == 0 else ('PARTIAL_SUCCESS' if success_count > 0 else 'ERROR')
                msg = f"Escrita concluída. Sucesso: {success_count}, Erros: {error_count}"
                self.reportar_status_batch(batch_id, final_status, msg, {'current': len(commands), 'total': len(commands)})

        except Exception as e:
            logger.error(f"Erro no loop de comandos: {e}")

    def reportar_status_batch(self, batch_id, status, message, progress=None):
        """Envia callback de status e progresso ao backend de ingestao."""
        try:
            url = f"{INGEST_API_URL}/golden-state/callback"
            payload = {'batch_id': batch_id, 'status': status, 'message': message}
            if progress: payload['progress'] = progress
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"Falha ao reportar status {batch_id}: {e}")

    # ---------------------------------------------------------------
    # [P0.6] Envio resiliente com circuit breaker + buffer offline
    # ---------------------------------------------------------------
    async def _send_ingest_raw(self, payload) -> bool:
        """Envio assincrono de leituras brutas. Retorna True/False."""
        if self.http is None:
            # Fallback legado: síncrono em thread para não bloquear event loop
            def _do():
                try:
                    r = requests.post(f"{INGEST_API_URL}/dados/inserir", json=payload, timeout=TIMEOUT_REQUEST)
                    return 200 <= r.status_code < 300
                except Exception:
                    return False
            return await asyncio.to_thread(_do)
        return await self.http.post_json(f"{INGEST_API_URL}/dados/inserir", payload)

    async def _send_django_raw(self, payload) -> bool:
        """
        Leituras brutas OPC vao APENAS para o backend de ingestao/InfluxDB.
        O Django recebe somente dados consolidados (via /api/metricas_consolidadas/).
        Endpoint /api/leituras/inserir/ nao existe — metodo mantido como no-op
        para nao quebrar o circuit breaker/buffer, mas nao envia nada.
        """
        return True

    def registrar_heartbeat(
        self,
        *,
        cycle_seconds: float,
        equipment_count: int,
        measurement_count: int,
        valid_tag_count: int = 0,
        rejected_tag_count: int = 0,
        no_read_tag_count: int = 0,
    ) -> bool:
        """Registra que um ciclo completo do coletor terminou.

        O health do sistema não deve inferir a vida do processo pela presença
        de ``estado_maquina``: uma linha sem tag configurada ou um intervalo
        sem mudança de estado não significa coletor parado. O heartbeat usa
        uma measurement própria e não contamina os dados industriais.
        """
        try:
            from influxdb import InfluxDBClient

            if self._heartbeat_client is None:
                self._heartbeat_client = InfluxDBClient(
                    host=INFLUXDB_HOST,
                    port=INFLUXDB_PORT,
                    username=INFLUXDB_USER,
                    password=INFLUXDB_PASSWORD,
                    database=INFLUXDB_DATABASE,
                    timeout=TIMEOUT_REQUEST,
                )

            payload = [{
                'measurement': 'collector_heartbeat',
                'tags': {'service': 'mis-core-coletor'},
                'time': datetime.utcnow().isoformat() + 'Z',
                'fields': {
                    'alive': 1,
                    'cycle_seconds': float(cycle_seconds),
                    'equipment_count': int(equipment_count),
                    'measurement_count': int(measurement_count),
                    'valid_tag_count': int(valid_tag_count),
                    'rejected_tag_count': int(rejected_tag_count),
                    'no_read_tag_count': int(no_read_tag_count),
                },
            }]
            written = bool(self._heartbeat_client.write_points(payload))
            if not written:
                logger.warning("Heartbeat do coletor não foi confirmado pelo InfluxDB.")
            return written
        except Exception as exc:
            # Descarta a conexão para que o próximo ciclo faça uma reconexão
            # limpa depois de uma indisponibilidade temporária do InfluxDB.
            self._heartbeat_client = None
            logger.warning(f"Falha ao registrar heartbeat do coletor: {exc}")
            return False

    async def _send_via_cb(self, breaker, sender, payload, endpoint: str) -> bool:
        """
        Envia via circuit breaker; em caso de circuito aberto OU falha real,
        enfileira no buffer offline para replay futuro.
        """
        if breaker is None or self.buffer is None:
            # Modo legado: só tenta enviar direto, sem buffer.
            return await sender(payload)

        try:
            ok = await breaker.call(sender, payload)
            if not ok:
                await self.buffer.enqueue(endpoint, payload)
            return ok
        except CircuitOpenError:
            logger.warning(f"🚧 [{endpoint}] circuito aberto — enfileirando payload.")
            await self.buffer.enqueue(endpoint, payload)
            return False
        except Exception as e:
            logger.error(f"❌ [{endpoint}] envio falhou: {e}", exc_info=True)
            await self.buffer.enqueue(endpoint, payload)
            return False

    async def executar(self):
        """Loop principal do Coletor Centralizado — versão resiliente (P0.4/5/6)."""
        await self.inicializar()

        # [P0.5] Watchdog em task paralela — reconexão automática ANTES do
        # próximo ciclo falhar.
        if self.watchdog is not None:
            asyncio.create_task(self.watchdog.run(), name='opc-watchdog')
            logger.info("🛡️ Watchdog OPC ativado.")

        while True:
            try:
                loop_start = time.time()

                # 1. Atualizar Config e Conexões
                await self.atualizar_configuracao()

                # [GUARD] Se configuracao ainda None (Django indisponível ou retornou erro),
                # pula o ciclo de coleta sem crashar. O log já foi feito em atualizar_configuracao().
                if self.configuracao is None:
                    logger.warning("⚠️ Configuração indisponível — aguardando próximo ciclo.")
                    await asyncio.sleep(INTERVALO_COLETA)
                    continue

                # 1b. [P0.6] Replay de pacotes pendentes do buffer offline.
                # Executa ANTES da nova coleta — evita dados ficarem em ordem errada
                # no InfluxDB (que indexa por timestamp, mas o consumidor downstream
                # pode assumir FIFO de chegada).
                if self.buffer is not None:
                    try:
                        pending = await self.buffer.pending_count()
                        if pending > 0:
                            logger.info(f"🔁 Drenando buffer offline ({pending} pendentes)...")
                            await self.buffer.drain('ingest', self._send_ingest_raw, batch_size=30)
                            await self.buffer.drain('django', self._send_django_raw, batch_size=30)
                    except Exception as e:
                        logger.warning(f"⚠️ replay buffer falhou: {e}", exc_info=True)

                # 2. Agrupar Equipamentos por URL de Conexão
                equipamentos_por_url = {}
                todos_equipamentos = self.configuracao.get('equipamentos', [])

                for eq in todos_equipamentos:
                    conn = eq.get('conexao_detalhes') or {}
                    url = conn.get('url')
                    if url:
                        if url not in equipamentos_por_url: equipamentos_por_url[url] = []
                        equipamentos_por_url[url].append(eq)

                logger.debug(f"Agrupados {len(equipamentos_por_url)} URLs de conexão")

                tasks = []

                # 3. Iterar por Grupo de Conexão
                for url, equipments_list in equipamentos_por_url.items():
                    conexao_ok = await self.verificar_saude_conexao(url)
                    cliente = self.clientes_opc.get(url)

                    if not conexao_ok:
                        logger.warning(
                            f"⚠️ Grupo Conexão {url} OFFLINE/ERRO. "
                            f"Forçando {len(equipments_list)} equipamentos para estado 999."
                        )

                    for eq in equipments_list:
                        tasks.append(self.coletar_dados_equipamento(eq, cliente, conexao_ok))

                # 4. Executar coletas (Gather)
                if tasks:
                    resultados = await asyncio.gather(*tasks, return_exceptions=True)

                    pacote_envio = []
                    cycle_tag_stats = {"valid": 0, "rejected": 0, "no_read": 0}
                    for res in resultados:
                        if isinstance(res, dict):
                            result_stats = res.pop("_collector_stats", {})
                            for key in cycle_tag_stats:
                                cycle_tag_stats[key] += int(result_stats.get(key, 0))
                            pacote_envio.append(res)
                        elif isinstance(res, Exception):
                            logger.error(f"Erro em tarefa de coleta: {res}", exc_info=True)

                    # 5. Envio resiliente da ingestao + Django (paralelo, com buffer de fallback)
                    if pacote_envio:
                        await asyncio.gather(
                            self._send_via_cb(self.cb_django, self._send_django_raw, pacote_envio, 'django'),
                            self._send_via_cb(self.cb_ingest, self._send_ingest_raw, pacote_envio, 'ingest'),
                            return_exceptions=True,
                        )
                else:
                    pacote_envio = []
                    cycle_tag_stats = {"valid": 0, "rejected": 0, "no_read": 0}
                    logger.warning("⚠️ Nenhuma tarefa de coleta criada!")

                # 6. Verificar e Executar Comandos (Write-Back)
                await self.verificar_comandos()

                # 7. Heartbeat explícito somente depois de um ciclo completo.
                # Executa em thread para não bloquear o event loop durante I/O.
                elapsed = time.time() - loop_start
                await asyncio.to_thread(
                    self.registrar_heartbeat,
                    cycle_seconds=elapsed,
                    equipment_count=len(todos_equipamentos),
                    measurement_count=len(pacote_envio),
                    valid_tag_count=cycle_tag_stats["valid"],
                    rejected_tag_count=cycle_tag_stats["rejected"],
                    no_read_tag_count=cycle_tag_stats["no_read"],
                )

                # Sleep inteligente
                elapsed = time.time() - loop_start
                sleep_time = max(0.1, INTERVALO_COLETA - elapsed)
                await asyncio.sleep(sleep_time)

            except Exception as e:
                # [P0.6] Log COM traceback completo — sem isso, em produção a gente
                # só vê "Erro fatal no loop: 'NoneType'" e perde 2 horas descobrindo
                # qual linha explodiu.
                logger.error(f"💥 Erro fatal no loop: {e}", exc_info=True)
                await asyncio.sleep(5)

# =============================================================================
# MODO DEMO — Simulador (sem OPC UA real)
# =============================================================================
async def executar_simulacao():
    """
    Loop principal em MODO DEMO. NÃO conecta em nenhum OPC server.
    Gera dados sintéticos correlacionados (linha, estados, OEE, descarte)
    e envia para o backend de ingestao /dados/inserir + Django metadata sync.
    """
    from simulador import SimuladorEquipamentos

    logger.warning("=" * 70)
    logger.warning("⚠️  MODO SIMULAÇÃO ATIVO — NENHUMA CONEXÃO COM OPC REAL")
    logger.warning("⚠️  MIS_MODE=demo — dados gerados sinteticamente")
    logger.warning("=" * 70)

    sim = SimuladorEquipamentos()

    # ----- Backfill histórico (executado uma vez no startup) -----
    if DEMO_BACKFILL_DIAS > 0:
        try:
            from influxdb import InfluxDBClient
            logger.info(
                f"📜 Conectando InfluxDB {INFLUXDB_HOST}:{INFLUXDB_PORT} "
                f"para backfill de {DEMO_BACKFILL_DIAS} dias..."
            )
            # Espera InfluxDB ficar saudável
            for tentativa in range(30):
                try:
                    client = InfluxDBClient(
                        host=INFLUXDB_HOST, port=INFLUXDB_PORT,
                        username=INFLUXDB_USER, password=INFLUXDB_PASSWORD,
                        database=INFLUXDB_DATABASE, timeout=5,
                    )
                    client.ping()
                    break
                except Exception as e:
                    logger.info(f"  InfluxDB ainda não pronto ({e}), retry {tentativa+1}/30...")
                    await asyncio.sleep(2)
            else:
                logger.error("❌ InfluxDB indisponível após 60s — pulando backfill.")
                client = None

            if client is not None:
                # Idempotência: se já existe um marker, não duplica
                marker_q = "SELECT last(value) FROM demo_marker"
                try:
                    rs = client.query(marker_q)
                    pts = list(rs.get_points())
                except Exception:
                    pts = []
                if pts:
                    logger.info(f"📜 Backfill já feito anteriormente ({pts[0]}). Pulando.")
                else:
                    n = await asyncio.to_thread(
                        sim.backfill_influxdb, client,
                        DEMO_BACKFILL_DIAS, DEMO_BACKFILL_STEP_S,
                    )
                    client.write_points([{
                        "measurement": "demo_marker",
                        "fields": {"value": float(n)},
                    }])
                    logger.info(f"📜 Backfill registrado: {n} pontos.")
        except Exception as e:
            logger.error(f"❌ Falha no backfill (continuando com stream ao vivo): {e}", exc_info=True)

    # ----- Stream ao vivo -----
    estados_anteriores: Dict[str, int] = {}
    metadata_hash_anterior: Optional[str] = None

    while True:
        try:
            pacote = sim.passo(intervalo_s=INTERVALO_COLETA)

            # POST consolidado para a ingestao
            def _post_ingest():
                try:
                    r = requests.post(
                        f"{INGEST_API_URL}/dados/inserir",
                        json=pacote, timeout=TIMEOUT_REQUEST,
                    )
                    return 200 <= r.status_code < 300
                except Exception as e:
                    logger.warning(f"⚠️ Falha POST ingestao (simulacao): {e}")
                    return False

            ok = await asyncio.to_thread(_post_ingest)
            if not ok:
                logger.warning("⚠️ Ingestao offline - proximo ciclo tenta de novo.")

            # Eventos de transição de estado → Django
            # Mapeia codigo->slug pelo conjunto atual da simulação (1 fábrica
            # demo, sem duplicidade entre linhas). Em OT, slug vem do Django.
            sim_eq_index = {eq.get('codigo'): eq for eq in sim.metadata_atual() or []}
            transicoes = sim.transicoes_estado(estados_anteriores)
            for eq_cod, estado_txt in transicoes:
                eq_meta = sim_eq_index.get(eq_cod, {})
                linha_codigo = eq_meta.get('linha_codigo')
                slug = eq_meta.get('slug') or (
                    f"{linha_codigo}.{eq_cod}" if linha_codigo else None
                )
                payload = {
                    'equipamento_codigo': eq_cod,
                    'estado': estado_txt,
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'origem': 'SIMULADOR',
                }
                if slug:
                    payload['equipamento_slug'] = slug
                if linha_codigo:
                    payload['linha_codigo'] = linha_codigo
                def _send(p=payload):
                    try:
                        requests.post(f"{DJANGO_API_URL}/eventos_estado/", json=p, timeout=5)
                    except Exception:
                        pass
                await asyncio.to_thread(_send)

            # Metadata sync — só se mudou
            md = sim.metadata_atual()
            md_hash = json.dumps(md, sort_keys=True)
            if md_hash != metadata_hash_anterior:
                metadata_hash_anterior = md_hash
                for item in md:
                    def _send(p=item):
                        try:
                            requests.post(
                                f"{DJANGO_API_URL}/equipamentos/sync_metadata/",
                                json=p, timeout=5,
                            )
                        except Exception:
                            pass
                    await asyncio.to_thread(_send)

            await asyncio.sleep(INTERVALO_COLETA)

        except Exception as e:
            logger.error(f"💥 Erro no loop simulação: {e}", exc_info=True)
            await asyncio.sleep(5)


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    if MIS_MODE == 'demo':
        try:
            asyncio.run(executar_simulacao())
        except KeyboardInterrupt:
            logger.info("Simulador parado pelo usuário.")
    else:
        # IMPORTANTE: NÃO apagar dados do Influx automaticamente. Em produção,
        # se houver resquícios de demo, o operador limpa manualmente via:
        #   docker compose exec influxdb influx -username admin -password ... \
        #     -database industrial_db -execute 'DROP MEASUREMENT production'
        # Auto-limpeza no boot é destrutiva e quebra rollback.
        coletor = ColetorOPC()
        try:
            asyncio.run(coletor.executar())
        except KeyboardInterrupt:
            logger.info("Coletor parado pelo usuário.")
