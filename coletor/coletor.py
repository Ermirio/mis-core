# Coletor OPC UA - Serviço Standalone
# ====================================

# Este serviço é responsável por:
# 1. Buscar configuração da API Django
# 2. Conectar-se aos servidores OPC UA
# 3. Ler tags em tempo real
# 4. Enviar dados para a API Flask (InfluxDB)
# 5. Detectar mudanças de estado e enviar para Django

# Autor: Sistema MIS
# Data: 2024

import asyncio
import logging
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional
import requests
from asyncua import Client, ua
from decouple import config


# ===== CONFIGURAÇÃO DE LOGGING =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('coletor.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Configurar stdout para UTF-8 no Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logger = logging.getLogger('Coletor')


# ===== CONFIGURAÇÕES =====
DJANGO_API_URL = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')
FLASK_API_URL = config('FLASK_API_URL', default='http://127.0.0.1:5000/api')
INTERVALO_COLETA = config('INTERVALO_COLETA', default=2, cast=int)  # segundos
TIMEOUT_REQUEST = config('TIMEOUT_REQUEST', default=10, cast=int)


# ===== MAPEAMENTO DE ESTADOS OPC PARA ENUM =====
# Mapeia valores inteiros do OPC para estados do Django
MAPEAMENTO_ESTADOS = {
    1: 'RUN',           # Produzindo
    2: 'WAIT_PREV',     # Aguardando equipamento anterior
    3: 'BLOCK_NEXT',    # Equipamento seguinte bloqueado
    4: 'FAULT',         # Falha
    5: 'SETUP',         # Setup / Troca SKU
    6: 'TESTE_PROJ',    # Teste de Projeto
    7: 'AGUARD_MNT',    # Aguardando Manutenção
    8: 'MANUTENCAO',    # Em Manutenção
    9: 'FALTA_MAT',     # Falta de Material
    0: 'OUTRO',         # Outro
}


class ColetorOPC:
    """Classe principal do coletor OPC UA"""
    
    def __init__(self):
        self.configuracao = None
        self.clientes_opc = {}  # {url_servidor: Client}
        self.ultima_atualizacao_config = None
        self.contadores_anteriores = {}  # Para calcular descartes
        self.estados_anteriores = {}  # Para detectar mudanças de estado
        self.metadata_anteriores = {}  # Para detectar mudanças de OP/SKU/Formato
        
    async def inicializar(self):
        """Inicializa o coletor"""
        logger.info("=" * 60)
        logger.info("COLETOR OPC UA - INICIANDO (com detecção de estados)")
        logger.info("=" * 60)
        logger.info(f"Django API: {DJANGO_API_URL}")
        logger.info(f"Flask API: {FLASK_API_URL}")
        logger.info(f"Intervalo de coleta: {INTERVALO_COLETA}s")
        logger.info("=" * 60)
        
        # Busca configuração inicial
        if not await self.atualizar_configuracao():
            logger.error("FALHA CRÍTICA: Não foi possível obter configuração do Django")
            return False
        
        # Conecta aos servidores OPC
        if not await self.conectar_servidores_opc():
            logger.error("FALHA CRÍTICA: Não foi possível conectar aos servidores OPC")
            return False
        
        logger.info("[OK] Coletor inicializado com sucesso")
        return True
    
    async def atualizar_configuracao(self) -> bool:
        """Busca configuração da API Django"""
        try:
            logger.info("Buscando configuração do Django...")
            # Fixed indentation
            url = f"{DJANGO_API_URL}/configuracao_coletor/"
            
            response = requests.get(url, timeout=TIMEOUT_REQUEST)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') != 'success':
                logger.error(f"Resposta inválida do Django: {data}")
                return False
            
            self.configuracao = data
            self.ultima_atualizacao_config = datetime.now()
            
            total_equipamentos = data.get('total_equipamentos', 0)
            logger.info(f"[OK] Configuração obtida: {total_equipamentos} equipamentos")
            
            # Log detalhado dos equipamentos
            for eq in data.get('equipamentos', []):
                num_tags = len(eq.get('tags_coleta', []))
                tipo = eq.get('tipo', 'N/A')
                logger.info(f"  - {eq['nome']} ({tipo}): {num_tags} tags")
            
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao buscar configuração do Django: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao processar configuração: {e}", exc_info=True)
            return False
    
    async def conectar_servidores_opc(self) -> bool:
        """Conecta-se a todos os servidores OPC necessários"""
        try:
            if not self.configuracao:
                logger.error("Sem configuração disponível")
                return False
            
            # Identifica servidores únicos
            servidores = set()
            for eq in self.configuracao.get('equipamentos', []):
                for tag in eq.get('tags_coleta', []):
                    conexao = tag.get('conexao_detalhes')
                    if conexao and conexao.get('ativa'):
                        servidores.add(conexao['url_servidor'])
            
            if not servidores:
                logger.warning("Nenhum servidor OPC configurado")
                return True  # Não é erro crítico se não houver servidores
            
            logger.info(f"Conectando a {len(servidores)} servidor(es) OPC...")
            
            for url_servidor in servidores:
                try:
                    cliente = Client(url=url_servidor)
                    await cliente.connect()
                    
                    # Testa a conexão
                    await cliente.get_namespace_array()
                    
                    self.clientes_opc[url_servidor] = cliente
                    logger.info(f"[OK] Conectado a {url_servidor}")
                    
                except Exception as e:
                    logger.error(f"[ERRO] Falha ao conectar a {url_servidor}: {e}")
                    # Continua tentando outros servidores
            
            if not self.clientes_opc:
                logger.error("Nenhuma conexão OPC estabelecida")
                return False
            
            logger.info(f"[OK] {len(self.clientes_opc)} conexão(ões) OPC estabelecida(s)")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao conectar servidores OPC: {e}", exc_info=True)
            return False
    
    async def ler_tag_opc(self, cliente: Client, node_id: str, tipo_dado: str, fator_conversao: float = 1.0) -> Optional[any]:
        """Lê um tag OPC e retorna seu valor"""
        try:
            node = cliente.get_node(node_id)
            valor = await node.read_value()
            
            # Aplica fator de conversão para valores numéricos
            if tipo_dado in ['FLOAT', 'INT'] and valor is not None:
                valor = float(valor) * fator_conversao
                if tipo_dado == 'INT':
                    valor = int(valor)
            
            return valor
            
        except Exception as e:
            logger.warning(f"Erro ao ler tag {node_id}: {e}")
            return None
    
    def mapear_estado_opc(self, valor_opc: int) -> str:
        """Mapeia valor inteiro do OPC para enum de estado"""
        return MAPEAMENTO_ESTADOS.get(valor_opc, 'OUTRO')
    
    async def enviar_evento_estado(self, equipamento_codigo: str, estado: str) -> bool:
        """Envia evento de mudança de estado para Django"""
        try:
            url = f"{DJANGO_API_URL}/eventos_estado/"
            
            payload = {
                'equipamento_codigo': equipamento_codigo,
                'estado': estado,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'origem': 'OPC'
            }
            
            response = requests.post(
                url,
                json=payload,
                timeout=TIMEOUT_REQUEST
            )
            response.raise_for_status()
            
            logger.info(f"[OK] Evento de estado enviado: {equipamento_codigo} -> {estado}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao enviar evento de estado: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar evento de estado: {e}")
            return False
    
    async def enviar_metadata_django(self, dados: Dict) -> bool:
        """Envia metadados atualizados para o Django"""
        try:
            url = f"{DJANGO_API_URL}/equipamentos/sync_metadata/"
            
            response = requests.post(
                url,
                json=dados,
                timeout=TIMEOUT_REQUEST
            )
            response.raise_for_status()
            
            logger.info(f"[METADATA] Sincronizado com sucesso para {dados['equipamento_codigo']}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao sincronizar metadados: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao sincronizar metadados: {e}")
            return False

    async def coletar_dados_equipamento(self, equipamento: Dict) -> Optional[Dict]:
        """Coleta dados de um equipamento específico"""
        try:
            nome_equipamento = equipamento['nome']
            codigo_equipamento = equipamento['codigo']
            linha_codigo = equipamento['linha_codigo']
            tags_coleta = equipamento.get('tags_coleta', [])
            
            if not tags_coleta:
                logger.debug(f"Equipamento {nome_equipamento} sem tags configuradas")
                return None
            
            medicoes = {}
            estado_atual = None
            formato_gramas = 0  # Inicializa formato
            
            # Metadados atuais (lidos do PLC)
            metadata_atual = {
                'equipamento_codigo': codigo_equipamento,
                'op_codigo': None,
                'sku_codigo': None,
                'descricao': None,
                'formato': None,
                'meta_producao': None
            }
            
            for tag in tags_coleta:
                conexao = tag.get('conexao_detalhes')
                if not conexao:
                    continue
                
                url_servidor = conexao['url_servidor']
                cliente = self.clientes_opc.get(url_servidor)
                
                if not cliente:
                    logger.warning(f"Cliente OPC não disponível para {url_servidor}")
                    continue
                
                # Lê o valor da tag
                valor = await self.ler_tag_opc(
                    cliente=cliente,
                    node_id=tag['node_id'],
                    tipo_dado=tag['tipo_dado'],
                    fator_conversao=tag.get('fator_conversao', 1.0)
                )
                
                if valor is not None:
                    nome_metrica = tag['nome_metrica']
                    medicoes[nome_metrica] = valor
                    
                    # DEBUG: Log detalhado para tags SKU/OP/Descrição
                    if nome_metrica in ['sku_codigo', 'descricao', 'ordem_producao', 'planejado_op']:
                        logger.info(f"[DEBUG-TAG] {codigo_equipamento} - {nome_metrica}: '{valor}' (tipo: {type(valor).__name__})")
                        
                    # Preenche metadados atuais
                    if nome_metrica == 'ordem_producao':
                        metadata_atual['op_codigo'] = str(valor)
                    elif nome_metrica == 'sku_codigo':
                        metadata_atual['sku_codigo'] = str(valor)
                    elif nome_metrica == 'descricao':
                        metadata_atual['descricao'] = str(valor)
                    elif nome_metrica == 'formato':
                        try:
                            metadata_atual['formato'] = float(valor)
                        except:
                            pass
                    elif nome_metrica == 'planejado_op':
                        try:
                            metadata_atual['meta_producao'] = int(float(valor))
                        except:
                            pass
                    
                    # Detecta tag de estado
                    if nome_metrica == 'estado':
                        logger.info(f"[DEBUG-STATUS] {codigo_equipamento} - Valor bruto: {valor} (Tipo: {type(valor)})")
                        estado_atual = self.mapear_estado_opc(int(valor))
                        logger.info(f"[DEBUG-STATUS] {codigo_equipamento} - Mapeado para: {estado_atual}")
                        
                        # Adiciona estado_maquina às medições para ser enviado como tag/field
                        medicoes['estado_maquina'] = estado_atual
                
                # CRÍTICO: Extrai formato_gramas da configuração da tag
                # Isso é necessário para calcular produção por OP e SKU
                formato_tag = tag.get('formato')
                if formato_tag is not None:
                    try:
                        formato_float = float(formato_tag)
                        if formato_float > 0:
                            formato_gramas = formato_float
                    except (ValueError, TypeError):
                        pass
            
            if not medicoes:
                logger.debug(f"Nenhuma medição obtida para {nome_equipamento}")
                return None
            
            # ===== DETECÇÃO DE MUDANÇA DE METADADOS =====
            # Verifica se houve mudança em OP, SKU ou Formato
            metadata_anterior = self.metadata_anteriores.get(codigo_equipamento, {})
            
            mudou = False
            if metadata_atual['op_codigo'] and metadata_atual['op_codigo'] != metadata_anterior.get('op_codigo'):
                mudou = True
                logger.info(f"[CHANGE] OP mudou: {metadata_anterior.get('op_codigo')} -> {metadata_atual['op_codigo']}")
            
            if metadata_atual['sku_codigo'] and metadata_atual['sku_codigo'] != metadata_anterior.get('sku_codigo'):
                mudou = True
                logger.info(f"[CHANGE] SKU mudou: {metadata_anterior.get('sku_codigo')} -> {metadata_atual['sku_codigo']}")
                
            if metadata_atual['formato'] and metadata_atual['formato'] > 0:
                if float(metadata_atual['formato']) != float(metadata_anterior.get('formato') or 0):
                    mudou = True
                    logger.info(f"[CHANGE] Formato mudou: {metadata_anterior.get('formato')} -> {metadata_atual['formato']}")
            
            if metadata_atual['meta_producao'] and metadata_atual['meta_producao'] > 0:
                if metadata_atual['meta_producao'] != metadata_anterior.get('meta_producao'):
                    mudou = True
                    logger.info(f"[CHANGE] Meta OP mudou: {metadata_anterior.get('meta_producao')} -> {metadata_atual['meta_producao']}")
            
            if mudou:
                # Envia para Django
                await self.enviar_metadata_django(metadata_atual)
                # Atualiza cache anterior
                self.metadata_anteriores[codigo_equipamento] = metadata_atual.copy()
            
            # ADICIONA formato_gramas às medições se foi encontrado
            if formato_gramas > 0:
                medicoes['formato_gramas'] = formato_gramas
                logger.info(f"[FORMATO] {codigo_equipamento}: {formato_gramas}g")
            
            # Processa descartes (se houver contadores)
            if 'contagem_entrada' in medicoes and 'contagem_saida' in medicoes:
                contagem_entrada = medicoes['contagem_entrada']
                contagem_saida = medicoes['contagem_saida']
                
                # Calcula descarte
                descarte = int(contagem_entrada - contagem_saida)
                medicoes['descarte'] = max(0, descarte)
                
                # Calcula percentual de descarte
                if contagem_entrada > 0:
                    medicoes['percentual_descarte'] = (descarte / contagem_entrada) * 100
                else:
                    medicoes['percentual_descarte'] = 0.0
            
            # Detecta mudança de estado
            if estado_atual:
                estado_anterior = self.estados_anteriores.get(codigo_equipamento)
                
                if estado_anterior != estado_atual:
                    logger.info(f"Mudança de estado detectada: {codigo_equipamento} {estado_anterior} → {estado_atual}")
                    
                    # Envia evento para Django
                    await self.enviar_evento_estado(codigo_equipamento, estado_atual)
                    
                    # Atualiza estado anterior
                    self.estados_anteriores[codigo_equipamento] = estado_atual
            
            return {
                'equipamento_codigo': codigo_equipamento,
                'linha_codigo': linha_codigo,
                'medicoes': medicoes,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erro ao coletar dados de {equipamento.get('nome', 'UNKNOWN')}: {e}")
            return None
    
    async def enviar_para_flask(self, dados: Dict) -> bool:
        """Envia dados coletados para a API Flask"""
        try:
            url = f"{FLASK_API_URL}/dados/inserir"
            
            response = requests.post(
                url,
                json=dados,
                timeout=TIMEOUT_REQUEST
            )
            response.raise_for_status()
            
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao enviar dados para Flask: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar dados: {e}")
            return False
    
    async def ciclo_coleta(self):
        """Executa um ciclo completo de coleta"""
        try:
            if not self.configuracao:
                logger.warning("Sem configuração disponível, pulando ciclo")
                return
            
            equipamentos = self.configuracao.get('equipamentos', [])
            
            if not equipamentos:
                logger.warning("Nenhum equipamento configurado")
                return
            
            # Coleta dados de todos os equipamentos
            for equipamento in equipamentos:
                dados = await self.coletar_dados_equipamento(equipamento)
                
                if dados:
                    # Envia para Flask
                    sucesso = await self.enviar_para_flask(dados)
                    
                    if sucesso:
                        logger.info(f"[OK] {dados['equipamento_codigo']}: {len(dados['medicoes'])} medições enviadas")
                    else:
                        logger.warning(f"[FALHA] {dados['equipamento_codigo']}: Falha ao enviar dados")
            
        except Exception as e:
            logger.error(f"Erro no ciclo de coleta: {e}", exc_info=True)
    
    async def executar(self):
        """Loop principal do coletor"""
        logger.info("Iniciando loop de coleta...")
        
        ciclo = 0
        
        try:
            while True:
                ciclo += 1
                logger.info(f"--- Ciclo {ciclo} ---")
                
                # Executa coleta
                await self.ciclo_coleta()
                
                # Atualiza configuração a cada 60 ciclos (ou ~2 minutos)
                if ciclo % 60 == 0:
                    logger.info("Atualizando configuração...")
                    await self.atualizar_configuracao()
                    await self.conectar_servidores_opc()
                
                # Aguarda próximo ciclo
                await asyncio.sleep(INTERVALO_COLETA)
                
        except KeyboardInterrupt:
            logger.info("Interrupção recebida, encerrando...")
        except Exception as e:
            logger.error(f"Erro fatal no loop principal: {e}", exc_info=True)
        finally:
            await self.finalizar()
    
    async def finalizar(self):
        """Finaliza o coletor e fecha conexões"""
        logger.info("Finalizando coletor...")
        
        # Fecha conexões OPC
        for url, cliente in self.clientes_opc.items():
            try:
                await cliente.disconnect()
                logger.info(f"[OK] Desconectado de {url}")
            except Exception as e:
                logger.error(f"Erro ao desconectar de {url}: {e}")
        
        logger.info("Coletor finalizado")


async def main():
    """Função principal"""
    coletor = ColetorOPC()
    
    # Inicializa
    if not await coletor.inicializar():
        logger.error("Falha na inicialização, encerrando...")
        sys.exit(1)
    
    # Executa
    await coletor.executar()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Erro fatal: {e}", exc_info=True)