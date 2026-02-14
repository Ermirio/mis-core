"""
Script de Teste - Aplipack Mock API
Testa se a API mock está funcionando corretamente

Uso:
    python test_mock_api.py
"""

import requests
import json
import xml.etree.ElementTree as ET

# ==================== CONFIGURAÇÃO ====================

API_URL = "http://localhost:5003"
HEALTH_URL = f"{API_URL}/health"
SOAP_URL = f"{API_URL}/GetListaOP"

# ==================== FUNÇÕES DE TESTE ====================

def test_health_check():
    """Testa o endpoint de health check"""
    print("=" * 60)
    print("TESTE 1: Health Check")
    print("=" * 60)
    
    try:
        response = requests.get(HEALTH_URL, timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ Health check passou!")
            return True
        else:
            print("❌ Health check falhou!")
            return False
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return False

def test_soap_request(linha="L01"):
    """Testa requisição SOAP para uma linha específica"""
    print("\n" + "=" * 60)
    print(f"TESTE 2: Requisição SOAP - Linha {linha}")
    print("=" * 60)
    
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
    
    try:
        response = requests.post(SOAP_URL, data=envelope, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        print(f"Response Size: {len(response.text)} bytes")
        
        # Parse XML
        root = ET.fromstring(response.text)
        
        # Extrair xStatus
        status_elem = root.find('.//{http://www.aplipack.com.br/}xStatus')
        status = status_elem.text if status_elem is not None else None
        print(f"xStatus: {status}")
        
        # Extrair xListaJSON
        json_elem = root.find('.//{http://www.aplipack.com.br/}xListaJSON')
        if json_elem is not None and json_elem.text:
            lista_json = json_elem.text
            print(f"xListaJSON Size: {len(lista_json)} bytes")
            
            # Parse JSON
            data = json.loads(lista_json)
            ordens = data.get("OrdensProducao", [])
            print(f"Total de Ordens: {len(ordens)}")
            
            if ordens:
                print("\nPrimeira Ordem:")
                print(json.dumps(ordens[0], indent=2, ensure_ascii=False))
                
                print("\nÚltima Ordem:")
                print(json.dumps(ordens[-1], indent=2, ensure_ascii=False))
        
        if response.status_code == 200 and status == "0":
            print(f"✅ Requisição SOAP para linha {linha} passou!")
            return True
        else:
            print(f"❌ Requisição SOAP para linha {linha} falhou!")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_linha_invalida():
    """Testa requisição com linha inválida (deve retornar erro)"""
    print("\n" + "=" * 60)
    print("TESTE 3: Linha Inválida (deve retornar erro)")
    print("=" * 60)
    
    linha_producao = "L99IP"  # Linha que não existe
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
        response = requests.post(SOAP_URL, data=envelope, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        # Parse XML
        root = ET.fromstring(response.text)
        
        # Extrair xStatus
        status_elem = root.find('.//{http://www.aplipack.com.br/}xStatus')
        status = status_elem.text if status_elem is not None else None
        print(f"xStatus: {status}")
        
        # Extrair xErro
        erro_elem = root.find('.//{http://www.aplipack.com.br/}xErro')
        erro = erro_elem.text if erro_elem is not None else None
        print(f"xErro: {erro}")
        
        if status == "-1" and erro:
            print("✅ Erro tratado corretamente!")
            return True
        else:
            print("❌ Erro não foi tratado corretamente!")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_comparacao_linhas():
    """Testa se linhas diferentes retornam dados diferentes"""
    print("\n" + "=" * 60)
    print("TESTE 4: Comparação entre Linhas (L01 vs L02)")
    print("=" * 60)
    
    def get_skus_linha(linha):
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
        
        response = requests.post(SOAP_URL, data=envelope, headers=headers, timeout=10)
        root = ET.fromstring(response.text)
        json_elem = root.find('.//{http://www.aplipack.com.br/}xListaJSON')
        
        if json_elem is not None and json_elem.text:
            data = json.loads(json_elem.text)
            ordens = data.get("OrdensProducao", [])
            return [ordem.get("CodigoSKU") for ordem in ordens]
        return []
    
    try:
        skus_l01 = get_skus_linha("L01")
        skus_l02 = get_skus_linha("L02")
        
        print(f"SKUs L01 (primeiros 5): {skus_l01[:5]}")
        print(f"SKUs L02 (primeiros 5): {skus_l02[:5]}")
        
        # Verificar se são diferentes
        if skus_l01 != skus_l02:
            print("✅ Linhas retornam dados diferentes!")
            return True
        else:
            print("❌ Linhas retornam os mesmos dados!")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

# ==================== EXECUTAR TESTES ====================

def run_all_tests():
    """Executa todos os testes"""
    print("\n")
    print("🧪 INICIANDO TESTES DA APLIPACK MOCK API")
    print("=" * 60)
    
    resultados = []
    
    # Teste 1: Health Check
    resultados.append(("Health Check", test_health_check()))
    
    # Teste 2: SOAP L01
    resultados.append(("SOAP L01", test_soap_request("L01")))
    
    # Teste 3: SOAP L02
    resultados.append(("SOAP L02", test_soap_request("L02")))
    
    # Teste 4: Linha Inválida
    resultados.append(("Linha Inválida", test_linha_invalida()))
    
    # Teste 5: Comparação
    resultados.append(("Comparação Linhas", test_comparacao_linhas()))
    
    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO DOS TESTES")
    print("=" * 60)
    
    total = len(resultados)
    passou = sum(1 for _, result in resultados if result)
    falhou = total - passou
    
    for nome, result in resultados:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{nome}: {status}")
    
    print("=" * 60)
    print(f"Total: {total} | Passou: {passou} | Falhou: {falhou}")
    print("=" * 60)
    
    if falhou == 0:
        print("🎉 TODOS OS TESTES PASSARAM!")
    else:
        print(f"⚠️  {falhou} TESTE(S) FALHARAM!")
    
    return falhou == 0

if __name__ == '__main__':
    import sys
    
    print("Certifique-se de que a API mock está rodando em http://localhost:5003")
    print("Para iniciar a API: python aplipack_mock_api.py")
    print()
    
    input("Pressione Enter para iniciar os testes...")
    
    sucesso = run_all_tests()
    sys.exit(0 if sucesso else 1)

