import time
import requests
import logging
from opcua import Client, ua
import os
from datetime import datetime
import sys

# Logging setup
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv('BACKEND_URL', 'http://mis-energy-backend:5005/api')
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', 10))

def get_config():
    try:
        url = f"{BACKEND_URL}/equipments/collector-config"
        logger.debug(f"Buscando configuração de: {url}")
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.json().get('data', [])
        logger.error(f"Erro config status: {res.status_code}")
    except Exception as e:
        logger.error(f"Erro buscando configuração: {e}")
    return []

def read_equipment(client, eq_config):
    nodes_map = eq_config.get('nodes', {})
    if not nodes_map:
        return None
    
    medicoes = {}
    for key, node_id in nodes_map.items():
        if not node_id: continue
        try:
            node = client.get_node(node_id)
            val = node.get_value()
            # Tentar converter para tipos simples
            if hasattr(val, 'item'): val = val.item()
            medicoes[key] = val
        except Exception as e:
            # Log apenas debug para não poluir se for erro comum de "nó não existe"
            logger.debug(f"Erro lendo nó {node_id} ({key}) para EQ {eq_config.get('tag')}: {e}")
    
    return medicoes

def send_data(payload):
    try:
        url = f"{BACKEND_URL}/dados/inserir"
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code in [200, 201, 204]:
            logger.info(f"Dados enviados com sucesso: {len(payload)} itens")
        else:
            logger.error(f"Falha envio dados ({res.status_code}): {res.text}")
    except Exception as e:
        logger.error(f"Erro enviando dados: {e}")

def process_cycle():
    config = get_config()
    if not config:
        logger.info("Nenhuma configuração encontrada (ou erro na API).")
        return

    payload_batch = []
    
    # Agrupar por Gateway para otimizar conexões
    gateways = {}
    for eq in config:
        gw_info = eq.get('gateway')
        if not gw_info or not gw_info.get('ip_address'):
            continue
            
        gw_key = f"{gw_info['ip_address']}:{gw_info['port']}"
        if gw_key not in gateways:
            gateways[gw_key] = []
        gateways[gw_key].append(eq)

    if not gateways:
        logger.info("Nenhum gateway configurado.")
        return

    for gw_key, equipments in gateways.items():
        gw_info = equipments[0].get('gateway', {})
        # Usar opc_url se disponível, senão construir a partir de ip:port
        opc_url = gw_info.get('opc_url') or f"opc.tcp://{gw_info.get('ip_address')}:{gw_info.get('port')}"
        
        client = None
        try:
            client = Client(opc_url)
            # Timeout curto para não travar o loop
            client.session_timeout = 5000 
            client.connect()
            logger.info(f"Conectado a {opc_url}")
            
            for eq in equipments:
                medicoes = read_equipment(client, eq)
                if medicoes:
                     # Add timestamp
                     payload_batch.append({
                         "equipamento_codigo": eq['tag'],
                         "medicoes": medicoes,
                         "timestamp": datetime.utcnow().isoformat() + "Z"
                     })
            
        except Exception as e:
            logger.error(f"Erro conexão Gateway {opc_url}: {e}")
        finally:
            if client:
                try: client.disconnect()
                except: pass
    
    if payload_batch:
        send_data(payload_batch)

if __name__ == "__main__":
    logger.info("Iniciando MIS-Energy Collector...")
    while True:
        try:
            process_cycle()
        except Exception as e:
            logger.error(f"Erro no ciclo principal: {e}")
        time.sleep(POLL_INTERVAL)
