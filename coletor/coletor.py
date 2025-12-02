# Coletor OPC UA - Serviço Standalone
# ====================================
# Autor: Sistema MIS
# Data: 2024
# Versão: 1.3 (Com Diagnóstico de CUC e Ingestão Dinâmica)

import asyncio
import json
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

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logger = logging.getLogger('Coletor')

# ===== CONFIGURAÇÕES =====
DJANGO_API_URL = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')
FLASK_API_URL = config('FLASK_API_URL', default='http://127.0.0.1:5000/api')
INTERVALO_COLETA = config('INTERVALO_COLETA', default=2, cast=int)
TIMEOUT_REQUEST = config('TIMEOUT_REQUEST', default=10, cast=int)

# ===== MAPEAMENTO DE ESTADOS =====
MAPEAMENTO_ESTADOS = {
    1: 'RUN', 2: 'WAIT_PREV', 3: 'BLOCK_NEXT', 4: 'FAULT',
    5: 'SETUP', 6: 'TESTE_PROJ', 7: 'AGUARD_MNT', 8: 'MANUTENCAO',
    9: 'FALTA_MAT', 0: 'OUTRO',
}

class ColetorOPC:
    def __init__(self):
        self.configuracao = None
        self.clientes_opc = {} 
        self.ultima_atualizacao_config = None
        self.estados_anteriores = {} 
        self.metadata_anteriores = {}
        
    async def inicializar(self):
        logger.info("=" * 60)
        logger.info("COLETOR OPC UA - MODO DIAGNÓSTICO ATIVO")
        logger.info("=" * 60)
        
        if not await self.atualizar_configuracao():
            logger.error("❌ Falha crítica: Sem configuração do Django.")
            return False
        
        await self.conectar_servidores_opc()
        return True

    async def atualizar_configuracao(self) -> bool:
        try:
            # logger.info("🔄 Buscando configuração do Django...") # Silenciado para não poluir log
            url = f"{DJANGO_API_URL}/configuracao_coletor/"
            response = requests.get(url, timeout=TIMEOUT_REQUEST)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') != 'success':
                return False
            
            # Verifica se houve mudança na configuração
            novo_hash = json.dumps(data, sort_keys=True)
            atual_hash = json.dumps(self.configuracao, sort_keys=True) if self.configuracao else ""
            
            if novo_hash != atual_hash:
                self.configuracao = data
                equipamentos = data.get('equipamentos', [])
                logger.info(f"✅ NOVA Configuração detectada: {len(equipamentos)} equipamentos.")

                # --- DIAGNÓSTICO 1: O CUC VEIO DO DJANGO? ---
                for eq in equipamentos:
                    tags = [t['nome_metrica'] for t in eq.get('tags_coleta', [])]
                    # logger.info(f"[DIAGNOSTICO] Equipamento {eq['codigo']} tem as tags: {tags}")
                    if 'cuc' in tags:
                        pass # logger.info(f"[DIAGNOSTICO] ✅ Tag 'cuc' ENCONTRADA na configuração para {eq['codigo']}")
                    else:
                        logger.warning(f"[DIAGNOSTICO] ❌ Tag 'cuc' NÃO ESTÁ na configuração para {eq['codigo']}")
                # ----------------------------------------------
                return True # Mudou
            
            return True # Sucesso, mas sem mudanças
        except Exception as e:
            logger.error(f"❌ Erro config Django: {e}")
            return False
    
    async def conectar_servidores_opc(self) -> bool:
        try:
            if not self.configuracao: return False
            servidores = set()
            for eq in self.configuracao.get('equipamentos', []):
                for tag in eq.get('tags_coleta', []):
                    if tag.get('conexao_detalhes', {}).get('ativa'):
                        servidores.add(tag['conexao_detalhes']['url_servidor'])
            
            for url in servidores:
                if url not in self.clientes_opc:
                    try:
                        c = Client(url=url)
                        await c.connect()
                        self.clientes_opc[url] = c
                        logger.info(f"✅ Conectado a {url}")
                    except Exception as e:
                        logger.error(f"❌ Falha conexão {url}: {e}")
            return bool(self.clientes_opc)
        except Exception as e:
            logger.error(f"Erro conexão: {e}")
            return False
    
    async def ler_tag_opc(self, cliente: Client, node_id: str, tipo_dado: str, fator_conversao: float = 1.0) -> Optional[any]:
        try:
            node = cliente.get_node(node_id)
            valor = await node.read_value()
            
            if tipo_dado in ['FLOAT', 'INT'] and valor is not None:
                valor = float(valor) * fator_conversao
                if tipo_dado == 'INT': valor = int(valor)
            return valor
        except Exception as e:
            # logger.warning(f"Erro leitura tag {node_id}: {e}")
            return None
    
    def mapear_estado_opc(self, valor_opc: int) -> str:
        return MAPEAMENTO_ESTADOS.get(valor_opc, 'OUTRO')
    
    async def enviar_evento_estado(self, equipamento_codigo: str, estado: str) -> bool:
        try:
            url = f"{DJANGO_API_URL}/eventos_estado/"
            payload = {'equipamento_codigo': equipamento_codigo, 'estado': estado, 'timestamp': datetime.utcnow().isoformat() + 'Z', 'origem': 'OPC'}
            requests.post(url, json=payload, timeout=TIMEOUT_REQUEST)
            return True
        except: return False

    async def enviar_metadata_django(self, dados: Dict) -> bool:
        try:
            url = f"{DJANGO_API_URL}/equipamentos/sync_metadata/"
            requests.post(url, json=dados, timeout=TIMEOUT_REQUEST)
            return True
        except: return False

    async def coletar_dados_equipamento(self, equipamento: Dict) -> Optional[Dict]:
        try:
            codigo = equipamento['codigo']
            tags = equipamento.get('tags_coleta', [])
            medicoes = {}
            estado_txt, estado_num = None, None
            formato_gramas = 0
            
            metadata = {'equipamento_codigo': codigo, 'op_codigo': None, 'sku_codigo': None, 'descricao': None, 'formato': None, 'meta_producao': None}
            
            for tag in tags:
                nome = tag['nome_metrica']
                logger.info(f"Tag: {nome}")
                cliente = self.clientes_opc.get(tag.get('conexao_detalhes', {}).get('url_servidor'))
                if not cliente: continue
                
                valor = await self.ler_tag_opc(cliente, tag['node_id'], tag['tipo_dado'], tag.get('fator_conversao', 1.0))
                
                if valor is None and 'formato' in nome:
                    logger.warning(f"[DIAGNOSTICO] ❌ Falha ao ler FORMATO: {nome}")
                
                if valor is not None:
                    # nome = tag['nome_metrica']
                    medicoes[nome] = valor
                    
                    # --- DIAGNÓSTICO 2: O VALOR FOI LIDO? ---
                    if nome == 'cuc':
                        logger.info(f"[DIAGNOSTICO] 👁️ CUC LIDO do PLC: '{valor}' (Tipo: {type(valor)})")
                    if 'formato' in nome:
                        logger.info(f"[DIAGNOSTICO] 👁️ FORMATO LIDO do PLC: '{nome}' = '{valor}'")
                    # ----------------------------------------

                    # Preenchimento de Metadata e Estado (Lógica Padrão)
                    if nome == 'ordem_producao': metadata['op_codigo'] = str(valor)
                    elif nome == 'sku_codigo': metadata['sku_codigo'] = str(valor)
                    elif nome == 'descricao': metadata['descricao'] = str(valor)
                    elif nome == 'formato': 
                        try: 
                            val = float(valor)
                            metadata['formato'] = val
                            medicoes['formato_gramas'] = val
                            logger.info(f"[DIAGNOSTICO] Formato lido: {val}")
                        except: pass
                    elif nome == 'planejado_op':
                        try: metadata['meta_producao'] = int(float(valor))
                        except: pass
                    elif nome == 'estado':
                        try:
                            estado_num = int(valor)
                            medicoes['estado_maquina'] = estado_num
                            estado_txt = self.mapear_estado_opc(estado_num)
                        except:
                            medicoes['estado_maquina'] = 0

                if tag.get('formato'):
                    try: 
                        val = float(tag['formato'])
                        if val > 0: formato_gramas = val
                    except: pass
                
                # --- CAPTURA DE VELOCIDADE REAL ---
                nome_lower = nome.lower()
                if any(x in nome_lower for x in ['velocidade', 'vel', 'rpm', 'speed']):
                    try:
                        medicoes['velocidade_atual'] = float(valor)
                    except: pass
                # ----------------------------------
            
            if not medicoes: return None
            
            # Sincronização Metadata
            meta_ant = self.metadata_anteriores.get(codigo, {})
            if (metadata['op_codigo'] != meta_ant.get('op_codigo')) or (metadata['sku_codigo'] != meta_ant.get('sku_codigo')):
                await self.enviar_metadata_django(metadata)
                self.metadata_anteriores[codigo] = metadata.copy()
            
            if 'formato_gramas' not in medicoes and formato_gramas > 0:
                medicoes['formato_gramas'] = formato_gramas

            if 'contagem_entrada' in medicoes and 'contagem_saida' in medicoes:
                medicoes['descarte'] = max(0, int(medicoes['contagem_entrada'] - medicoes['contagem_saida']))
                if medicoes['contagem_entrada'] > 0:
                    medicoes['percentual_descarte'] = (medicoes['descarte'] / medicoes['contagem_entrada']) * 100

            if estado_txt:
                est_ant = self.estados_anteriores.get(codigo)
                if est_ant != estado_txt:
                    await self.enviar_evento_estado(codigo, estado_txt)
                    self.estados_anteriores[codigo] = estado_txt
            
            # --- DIAGNÓSTICO 3: O PACOTE CONTÉM CUC? ---
            if 'cuc' in medicoes:
                # logger.info(f"[DIAGNOSTICO] 📦 Pacote para Flask contém CUC: {medicoes['cuc']}")
                pass
            else:
                logger.warning(f"[DIAGNOSTICO] ⚠️ Pacote para Flask NÃO contém CUC! (Tags lidas: {list(medicoes.keys())})")
            # -------------------------------------------

            return {
                'equipamento_codigo': codigo,
                'linha_codigo': equipamento['linha_codigo'],
                'medicoes': medicoes,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Erro coleta: {e}")
            return None

    async def enviar_para_flask(self, dados: Dict) -> bool:
        try:
            url = f"{FLASK_API_URL}/dados/inserir"
            requests.post(url, json=dados, timeout=TIMEOUT_REQUEST)
            return True
        except Exception as e:
            logger.error(f"Erro envio Flask: {e}")
            return False
    
    async def ciclo_coleta(self):
        if not self.configuracao: return
        for eq in self.configuracao.get('equipamentos', []):
            dados = await self.coletar_dados_equipamento(eq)
            if dados: await self.enviar_para_flask(dados)
    
    async def executar(self):
        logger.info("🚀 Loop de coleta iniciado...")
        ciclo = 0
        try:
            while True:
                ciclo += 1
                await self.ciclo_coleta()
                if ciclo % 15 == 0: # A cada 30 segundos (15 * 2s)
                    await self.atualizar_configuracao()
                    await self.conectar_servidores_opc()
                await asyncio.sleep(INTERVALO_COLETA)
        except KeyboardInterrupt: pass
        finally:
            for c in self.clientes_opc.values():
                try: await c.disconnect()
                except: pass

async def main():
    coletor = ColetorOPC()
    if await coletor.inicializar():
        await coletor.executar()
    else:
        logger.error("❌ Falha na inicialização")

if __name__ == '__main__':
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt: pass