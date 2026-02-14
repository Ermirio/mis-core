"""
Exemplo de Uso - Aplipack Mock API
Demonstra como usar a API mock em diferentes cenários

Autor: Sistema MIS
Data: 2025-10-25
"""

import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime

# ==================== CONFIGURAÇÃO ====================

API_URL = "http://localhost:5003/GetListaOP"
# Se estiver em Docker: API_URL = "http://host.docker.internal:5003/GetListaOP"

# ==================== EXEMPLO 1: Requisição Básica ====================

def exemplo_basico():
    """Exemplo básico de requisição SOAP"""
    print("=" * 60)
    print("EXEMPLO 1: Requisição Básica")
    print("=" * 60)
    
    # Configurar requisição
    linha = "L01"
    linha_producao = linha + "IP"
    headers = {"Content-Type": "text/xml"}
    
    # Montar envelope SOAP
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
    
    # Fazer requisição
    response = requests.post(API_URL, data=envelope, headers=headers, timeout=10)
    
    print(f"Status: {response.status_code}")
    print(f"Resposta (primeiros 500 chars):\n{response.text[:500]}...")

# ==================== EXEMPLO 2: Parse da Resposta ====================

def exemplo_parse_resposta():
    """Exemplo de como fazer parse da resposta SOAP"""
    print("\n" + "=" * 60)
    print("EXEMPLO 2: Parse da Resposta")
    print("=" * 60)
    
    # Fazer requisição
    linha_producao = "L01IP"
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
    
    response = requests.post(API_URL, data=envelope, headers=headers, timeout=10)
    
    # Parse XML
    root = ET.fromstring(response.text)
    
    # Extrair xStatus
    status_elem = root.find('.//{http://www.aplipack.com.br/}xStatus')
    status = status_elem.text if status_elem is not None else None
    print(f"Status: {status}")
    
    # Extrair xListaJSON
    json_elem = root.find('.//{http://www.aplipack.com.br/}xListaJSON')
    
    if json_elem is not None and json_elem.text:
        # Parse JSON
        data = json.loads(json_elem.text)
        ordens = data.get("OrdensProducao", [])
        
        print(f"Total de Ordens: {len(ordens)}")
        
        # Mostrar primeira ordem
        if ordens:
            print("\nPrimeira Ordem:")
            print(json.dumps(ordens[0], indent=2, ensure_ascii=False))

# ==================== EXEMPLO 3: Processar Todas as Ordens ====================

def exemplo_processar_ordens():
    """Exemplo de como processar todas as ordens"""
    print("\n" + "=" * 60)
    print("EXEMPLO 3: Processar Todas as Ordens")
    print("=" * 60)
    
    def get_ordens(linha):
        """Função auxiliar para obter ordens"""
        linha_producao = linha + "IP"
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
        
        response = requests.post(API_URL, data=envelope, headers=headers, timeout=10)
        root = ET.fromstring(response.text)
        json_elem = root.find('.//{http://www.aplipack.com.br/}xListaJSON')
        
        if json_elem is not None and json_elem.text:
            data = json.loads(json_elem.text)
            return data.get("OrdensProducao", [])
        return []
    
    # Processar L01
    ordens_l01 = get_ordens("L01")
    print(f"L01: {len(ordens_l01)} ordens")
    
    # Estatísticas
    status_count = {}
    for ordem in ordens_l01:
        status = ordem.get("StatusOP", "Desconhecido")
        status_count[status] = status_count.get(status, 0) + 1
    
    print("\nDistribuição de Status (L01):")
    for status, count in status_count.items():
        print(f"  {status}: {count}")
    
    # Processar L02
    ordens_l02 = get_ordens("L02")
    print(f"\nL02: {len(ordens_l02)} ordens")

# ==================== EXEMPLO 4: Converter Timestamp Unix ====================

def exemplo_converter_timestamp():
    """Exemplo de como converter timestamp Unix"""
    print("\n" + "=" * 60)
    print("EXEMPLO 4: Converter Timestamp Unix")
    print("=" * 60)
    
    def convert_unix_timestamp(dataop_raw):
        """Converte timestamp Unix para datetime"""
        try:
            start = dataop_raw.find("(")
            end = dataop_raw.find(")")
            if start == -1 or end == -1:
                return None
            timestamp_ms = int(dataop_raw[start+1:end])
            timestamp_s = timestamp_ms / 1000
            return datetime.fromtimestamp(timestamp_s)
        except Exception:
            return None
    
    # Obter uma ordem
    linha_producao = "L01IP"
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
    
    response = requests.post(API_URL, data=envelope, headers=headers, timeout=10)
    root = ET.fromstring(response.text)
    json_elem = root.find('.//{http://www.aplipack.com.br/}xListaJSON')
    
    if json_elem is not None and json_elem.text:
        data = json.loads(json_elem.text)
        ordens = data.get("OrdensProducao", [])
        
        if ordens:
            ordem = ordens[0]
            dataop_raw = ordem.get("DataOP")
            
            print(f"Timestamp Raw: {dataop_raw}")
            
            dt = convert_unix_timestamp(dataop_raw)
            if dt:
                print(f"Data Convertida: {dt.strftime('%d/%m/%Y %H:%M:%S')}")

# ==================== EXEMPLO 5: Simular Sincronização Django ====================

def exemplo_sincronizacao_django():
    """Exemplo que simula o processo de sincronização do Django"""
    print("\n" + "=" * 60)
    print("EXEMPLO 5: Simular Sincronização Django")
    print("=" * 60)
    
    def convert_unix_timestamp(dataop_raw):
        """Converte timestamp Unix para datetime"""
        try:
            start = dataop_raw.find("(")
            end = dataop_raw.find(")")
            if start == -1 or end == -1:
                return None
            timestamp_ms = int(dataop_raw[start+1:end])
            timestamp_s = timestamp_ms / 1000
            return datetime.fromtimestamp(timestamp_s)
        except Exception:
            return None
    
    # Fazer requisição
    linha = "L01"
    linha_producao = linha + "IP"
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
    
    response = requests.post(API_URL, data=envelope, headers=headers, timeout=10)
    
    # Parse resposta
    root = ET.fromstring(response.text)
    status_elem = root.find('.//{http://www.aplipack.com.br/}xStatus')
    status = status_elem.text if status_elem is not None else None
    
    if status != "0":
        print("Erro na requisição!")
        return
    
    json_elem = root.find('.//{http://www.aplipack.com.br/}xListaJSON')
    
    if json_elem is None or not json_elem.text:
        print("JSON não encontrado!")
        return
    
    # Parse JSON
    data = json.loads(json_elem.text)
    ordens = data.get("OrdensProducao", [])
    
    print(f"Processando {len(ordens)} ordens...")
    
    # Processar cada ordem (simulando o que o Django faz)
    produtos_criados = 0
    
    for i, ordem in enumerate(ordens[:5], 1):  # Mostrar apenas 5 para exemplo
        codigo_sku = ordem.get("CodigoSKU")
        descricao_sku = ordem.get("DescricaoSKU")
        dataop_raw = ordem.get("DataOP", "")
        dt = convert_unix_timestamp(dataop_raw)
        dataop = dt.strftime("%d/%m/%Y %H:%M:%S") if dt else ""
        dun14 = ordem.get("DUN14")
        validade = ordem.get("Validade")
        
        print(f"\n[{i}] Processando SKU: {codigo_sku}")
        print(f"    Descrição: {descricao_sku}")
        print(f"    Data OP: {dataop}")
        print(f"    DUN14: {dun14}")
        print(f"    Validade: {validade}")
        
        # Aqui o Django criaria/atualizaria o produto no banco
        # produto, created = Produto.objects.get_or_create(...)
        produtos_criados += 1
    
    print(f"\n✅ {produtos_criados} produtos processados (exemplo)")
    print(f"Total disponível: {len(ordens)}")

# ==================== EXECUTAR EXEMPLOS ====================

if __name__ == '__main__':
    print("\n🔧 EXEMPLOS DE USO - APLIPACK MOCK API\n")
    
    try:
        exemplo_basico()
        exemplo_parse_resposta()
        exemplo_processar_ordens()
        exemplo_converter_timestamp()
        exemplo_sincronizacao_django()
        
        print("\n" + "=" * 60)
        print("✅ TODOS OS EXEMPLOS EXECUTADOS COM SUCESSO!")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERRO: Não foi possível conectar à API")
        print("Certifique-se de que a API está rodando:")
        print("  python aplipack_mock_api.py")
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

