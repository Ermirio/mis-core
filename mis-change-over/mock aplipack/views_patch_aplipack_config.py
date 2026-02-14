"""
PATCH para views.py - Integração com aplipack_config.py

Este arquivo mostra as alterações necessárias no views.py para usar
a configuração centralizada e alternar facilmente entre mock e produção.

INSTRUÇÕES:
1. Copie o arquivo aplipack_config.py para a pasta do app Django (mesma pasta do views.py)
2. Aplique as alterações abaixo no views.py

"""

# ==================== ALTERAÇÃO 1: IMPORTAR CONFIGURAÇÃO ====================
# Adicione esta linha no topo do views.py, junto com os outros imports

from .aplipack_config import APLIPACK_CONFIG, get_aplipack_url, get_aplipack_credentials, get_aplipack_timeout, is_mock_mode

# ==================== ALTERAÇÃO 2: MODIFICAR FUNÇÃO get_lista_op ====================
# ANTES (linha 862-886):

def get_lista_op_ANTES(linha=None):
    """Obtém lista de OPs do web service SOAP"""
    url = "http://192.168.30.42:82/WsOffLineCom.asmx?op=GetListaOP"  # ❌ URL hardcoded
   
    linha_producao = linha + "IP" if linha else ""
    headers = {"Content-Type": "text/xml"}
    envelope = f'''<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                             xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                             xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <GetListaOP xmlns="http://www.aplipack.com.br/">
      <UserSoftware>test</UserSoftware>
      <PasswordSoftware>1234</PasswordSoftware>
      <LinhaProducao>{linha_producao}</LinhaProducao>
    </GetListaOP>
  </soap12:Body>
</soap12:Envelope>'''
    try:
        response = requests.post(url, data=envelope, headers=headers, timeout=10)
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Erro ao conectar ao web service SOAP: {e}")
        return None


# DEPOIS (CORRIGIDO):

def get_lista_op(linha=None):
    """
    Obtém lista de OPs do web service SOAP
    Usa configuração centralizada (aplipack_config.py) para alternar entre mock e produção
    """
    # ✅ Usar configuração centralizada
    url = get_aplipack_url()
    credentials = get_aplipack_credentials()
    timeout = get_aplipack_timeout()
    
    # Log do modo atual (útil para debug)
    modo = "MOCK" if is_mock_mode() else "PRODUÇÃO"
    print(f"[GET_LISTA_OP] Modo: {modo}")
    print(f"[GET_LISTA_OP] URL: {url}")
   
    linha_producao = linha + "IP" if linha else ""
    headers = {"Content-Type": "text/xml"}
    
    # ✅ Usar credenciais da configuração
    envelope = f'''<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                             xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                             xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <GetListaOP xmlns="http://www.aplipack.com.br/">
      <UserSoftware>{credentials['user']}</UserSoftware>
      <PasswordSoftware>{credentials['password']}</PasswordSoftware>
      <LinhaProducao>{linha_producao}</LinhaProducao>
    </GetListaOP>
  </soap12:Body>
</soap12:Envelope>'''
    
    try:
        # ✅ Usar timeout da configuração
        print(f"[GET_LISTA_OP] Enviando requisição para linha: {linha_producao}")
        response = requests.post(url, data=envelope, headers=headers, timeout=timeout)
        print(f"[GET_LISTA_OP] Resposta recebida: Status {response.status_code}")
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"[GET_LISTA_OP] Erro ao conectar ao web service SOAP: {e}")
        return None


# ==================== ALTERAÇÃO 3: ADICIONAR LOG NO INÍCIO DO SERVIDOR ====================
# Adicione estas linhas no final do arquivo (ou no __init__.py do app)

# Imprimir configuração ao iniciar o servidor
if __name__ != '__main__':
    from .aplipack_config import print_config
    print_config()


# ==================== RESUMO DAS ALTERAÇÕES ====================
"""
RESUMO:
1. Importar: from .aplipack_config import ...
2. Substituir função get_lista_op() pela versão corrigida acima
3. (Opcional) Adicionar print_config() para ver configuração ao iniciar

COMO USAR:
- Para usar MOCK (desenvolvimento): 
  Edite aplipack_config.py e defina USE_MOCK = True
  
- Para usar PRODUÇÃO:
  Edite aplipack_config.py e defina USE_MOCK = False

- Ou use variável de ambiente:
  export APLIPACK_USE_MOCK=true   # Mock
  export APLIPACK_USE_MOCK=false  # Produção

VANTAGENS:
✅ Fácil alternar entre mock e produção
✅ Não precisa editar views.py toda vez
✅ Suporta variáveis de ambiente
✅ Detecta automaticamente se está em Docker
✅ Configuração centralizada
"""

