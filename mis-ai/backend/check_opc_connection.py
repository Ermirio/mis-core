# check_opc_connection.py
import asyncio
import os
from dotenv import load_dotenv
from asyncua import Client
import logging

# Configura um logging básico para vermos os detalhes
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    load_dotenv()
    url = os.getenv('OPC_SERVER_URL')

    if not url:
        logging.error("ERRO CRÍTICO: Variável OPC_SERVER_URL não está definida no seu arquivo .env")
        return

    logging.info(f"Iniciando teste de conexão com o servidor: {url}")
    logging.info("Timeout de conexão definido para 15 segundos.")
    
    client = Client(url=url, timeout=15)
    try:
        await client.connect()
        logging.info("**************************************")
        logging.info("*** CONEXÃO REALIZADA COM SUCESSO! ***")
        logging.info("**************************************")
        # Opcional: Ler um nó conhecido para confirmar a comunicação
        try:
            status_node = client.get_node("ns=0;i=2258") # Nó padrão do status do servidor
            server_status = await status_node.get_value()
            logging.info(f"Leitura do status do servidor bem-sucedida: {server_status}")
        except Exception as read_err:
            logging.warning(f"Conectado, mas falhou ao ler o nó de status: {read_err}")
        
        await client.disconnect()
        logging.info("Desconectado com sucesso.")

    except Exception as e:
        logging.error("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        logging.error("!!! FALHA NA TENTATIVA DE CONEXÃO !!!")
        logging.error(f"!!! Erro recebido: {e}")
        logging.error("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
        logging.info("--- AÇÕES SUGERIDAS ---")
        logging.info("1. [Firewall] Verifique o Firewall do Windows na MÁQUINA BACKEND. Ele pode estar bloqueando a conexão de SAÍDA para o processo 'python.exe'.")
        logging.info("2. [Firewall] Verifique o Firewall na MÁQUINA SERVIDOR OPC. Ele deve permitir conexões de ENTRADA do IP do seu backend na porta correta.")
        logging.info("3. [Rede] Se backend e servidor OPC estão em máquinas diferentes, confirme que há uma rota de rede entre elas.")


if __name__ == '__main__':
    # Garante que o script rode no Windows sem erros de loop de eventos
    # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()) # Descomente se tiver erros de loop no Windows
    asyncio.run(main())