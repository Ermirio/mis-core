"""
Arquivo de Configuração - Aplipack API
Facilita a troca entre ambiente de produção e mock (desenvolvimento)

Como usar:
1. Importe este arquivo no views.py:
   from .aplipack_config import APLIPACK_CONFIG

2. Use a URL configurada:
   url = APLIPACK_CONFIG['url']

3. Para alternar entre mock e produção:
   - Altere USE_MOCK = True (mock) ou False (produção)
   - Ou use variável de ambiente APLIPACK_USE_MOCK
"""

import os

# ==================== CONFIGURAÇÃO ====================

# Alternar entre mock e produção
# True = Usa API mock local (desenvolvimento/testes offline)
# False = Usa API real da Aplipack (produção)
USE_MOCK = os.getenv('APLIPACK_USE_MOCK', 'False').lower() == 'true'

# URLs das APIs
APLIPACK_URLS = {
    'production': 'http://192.168.30.42:82/WsOffLineCom.asmx?op=GetListaOP',
    'mock_local': 'http://localhost:5003/GetListaOP',
    'mock_docker': 'http://host.docker.internal:5003/GetListaOP',
}

# Credenciais (mock aceita qualquer valor)
APLIPACK_CREDENTIALS = {
    'production': {
        'user': 'test',
        'password': '1234'
    },
    'mock': {
        'user': 'test',
        'password': '1234'
    }
}

# Timeout para requisições (segundos)
APLIPACK_TIMEOUT = {
    'production': 10,
    'mock': 5
}

# ==================== DETECÇÃO AUTOMÁTICA DE AMBIENTE ====================

def detectar_ambiente():
    """
    Detecta automaticamente se está rodando em Docker ou local
    """
    # Verificar se está em container Docker
    if os.path.exists('/.dockerenv'):
        return 'docker'
    return 'local'

# ==================== CONFIGURAÇÃO FINAL ====================

AMBIENTE = detectar_ambiente()

if USE_MOCK:
    # Modo Mock (Desenvolvimento/Testes)
    if AMBIENTE == 'docker':
        URL_SELECIONADA = APLIPACK_URLS['mock_docker']
    else:
        URL_SELECIONADA = APLIPACK_URLS['mock_local']
    
    CREDENTIALS = APLIPACK_CREDENTIALS['mock']
    TIMEOUT = APLIPACK_TIMEOUT['mock']
    MODO = 'MOCK (Desenvolvimento)'
else:
    # Modo Produção
    URL_SELECIONADA = APLIPACK_URLS['production']
    CREDENTIALS = APLIPACK_CREDENTIALS['production']
    TIMEOUT = APLIPACK_TIMEOUT['production']
    MODO = 'PRODUÇÃO'

# Configuração final exportada
APLIPACK_CONFIG = {
    'url': URL_SELECIONADA,
    'user': CREDENTIALS['user'],
    'password': CREDENTIALS['password'],
    'timeout': TIMEOUT,
    'modo': MODO,
    'ambiente': AMBIENTE,
    'use_mock': USE_MOCK
}

# ==================== FUNÇÕES AUXILIARES ====================

def get_aplipack_url():
    """Retorna a URL configurada da Aplipack"""
    return APLIPACK_CONFIG['url']

def get_aplipack_credentials():
    """Retorna as credenciais configuradas"""
    return {
        'user': APLIPACK_CONFIG['user'],
        'password': APLIPACK_CONFIG['password']
    }

def get_aplipack_timeout():
    """Retorna o timeout configurado"""
    return APLIPACK_CONFIG['timeout']

def is_mock_mode():
    """Verifica se está em modo mock"""
    return APLIPACK_CONFIG['use_mock']

def print_config():
    """Imprime a configuração atual (útil para debug)"""
    print("=" * 60)
    print("CONFIGURAÇÃO APLIPACK API")
    print("=" * 60)
    print(f"Modo: {APLIPACK_CONFIG['modo']}")
    print(f"Ambiente: {APLIPACK_CONFIG['ambiente']}")
    print(f"URL: {APLIPACK_CONFIG['url']}")
    print(f"User: {APLIPACK_CONFIG['user']}")
    print(f"Password: {'*' * len(APLIPACK_CONFIG['password'])}")
    print(f"Timeout: {APLIPACK_CONFIG['timeout']}s")
    print(f"Use Mock: {APLIPACK_CONFIG['use_mock']}")
    print("=" * 60)

# ==================== EXECUÇÃO DIRETA ====================

if __name__ == '__main__':
    print_config()
    
    print("\nPara alternar entre mock e produção:")
    print("1. Edite USE_MOCK = True/False neste arquivo")
    print("2. Ou defina variável de ambiente: APLIPACK_USE_MOCK=true")
    print("\nExemplo:")
    print("  export APLIPACK_USE_MOCK=true  # Linux/Mac")
    print("  set APLIPACK_USE_MOCK=true     # Windows CMD")
    print("  $env:APLIPACK_USE_MOCK='true'  # Windows PowerShell")

