from opcua import Client
from opcua import ua

# Configuração do cliente OPC UA
url = "opc.tcp://1.0.0.158:49320"
client = Client(url)
client.set_timeout(10)  # Timeout de 10 segundos

try:
    # Conectar ao servidor
    print("Tentando conectar ao servidor OPC UA...")
    client.connect()
    print("Conectado ao servidor OPC UA")

    # Definir o nó (tag) para leitura e escrita
    tag = "ControlLogixT1.PLC Burner-SprayDryer.DI-6320-Density_Density BC-632"
    node = client.get_node(f"ns=2;s={tag}")

    # Ler o valor atual
    valor_lido = node.get_value()
    print(f"Valor lido de '{tag}': {valor_lido}")

    # Escrever um novo valor (exemplo: 450.0)
    novo_valor = 450.0
    valor_escrita = ua.DataValue(ua.Variant(novo_valor, ua.VariantType.Float))
    valor_escrita.ServerTimestamp = None
    valor_escrita.SourceTimestamp = None
    node.set_value(valor_escrita)
    print(f"Valor {novo_valor} escrito em '{tag}'")

except TimeoutError as e:
    print(f"Erro de timeout: Não foi possível conectar ao servidor em {url}. Verifique o endereço e a rede.")
except Exception as e:
    print(f"Erro inesperado: {e}")
finally:
    # Desconectar apenas se a conexão foi estabelecida
    try:
        if client.uaclient._uasocket._socket:  # Verifica se o socket existe
            client.disconnect()
            print("Desconectado do servidor")
    except AttributeError:
        print("Nenhuma conexão ativa para desconectar")