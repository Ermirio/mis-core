"""
API Flask Mock - Simulação da API Aplipack
Retorna dados SOAP XML idênticos ao web service real da Aplipack

Porta: 5003
Endpoint: /GetListaOP (POST)
Formato: SOAP 1.2 XML

Autor: Sistema MIS
Data: 2025-10-25
"""

from flask import Flask, request, Response
from datetime import datetime, timedelta
import random

app = Flask(__name__)

# ==================== DADOS MOCKADOS ====================

def gerar_timestamp_unix(dias_atras=0):
    """Gera timestamp Unix no formato /Date(milliseconds)/"""
    data = datetime.now() - timedelta(days=dias_atras)
    timestamp_ms = int(data.timestamp() * 1000)
    return f"/Date({timestamp_ms})/"

def gerar_skus_linha(linha, quantidade=30):
    """Gera SKUs mockados para uma linha específica"""
    skus = []
    
    # Prefixos e categorias por linha
    if linha == "L01IP":
        prefixos = ["FLX", "STD", "PRO"]
        categorias = ["Flexível", "Standard", "Premium"]
    elif linha == "L02IP":
        prefixos = ["CTR", "ECO", "MAX"]
        categorias = ["Cartucho", "Econômico", "Máximo"]
    else:
        prefixos = ["GEN", "COM", "ESP"]
        categorias = ["Genérico", "Comum", "Especial"]
    
    for i in range(1, quantidade + 1):
        prefixo = random.choice(prefixos)
        categoria = random.choice(categorias)
        
        # Gerar dados variados
        codigo_sku = f"{prefixo}{i:04d}"
        descricao = f"Produto {categoria} {linha.replace('IP', '')} - Item {i}"
        
        # Variar datas (últimos 30 dias)
        dias_atras = random.randint(0, 30)
        dataop = gerar_timestamp_unix(dias_atras)
        
        # Gerar IDs únicos
        id_ordem = 10000 + (i * 100) + random.randint(1, 99)
        numero_op = f"OP-{linha.replace('IP', '')}-{i:04d}"
        
        # Gerar DUN14 (14 dígitos)
        dun14 = f"{random.randint(10000000, 99999999)}{i:06d}"
        
        # Validade (meses futuros)
        mes_validade = random.randint(1, 12)
        ano_validade = random.randint(2025, 2027)
        validade = f"{mes_validade:02d}/{ano_validade}"
        
        # Quantidade por pallet (varia entre 50 e 200)
        qtd_pallet = random.choice([50, 75, 100, 120, 150, 200])
        
        # Status (maioria ativo, alguns em produção)
        status = random.choice(["Ativo", "Ativo", "Ativo", "Em Produção", "Ativo"])
        
        sku = {
            "CodigoSKU": codigo_sku,
            "DescricaoSKU": descricao,
            "DataOP": dataop,
            "IdOrdemProd": str(id_ordem),
            "NumeroOP": numero_op,
            "DUN14": dun14,
            "Validade": validade,
            "QuantidadePorPallet": str(qtd_pallet),
            "StatusOP": status
        }
        
        skus.append(sku)
    
    return skus

def gerar_json_ordens(linha):
    """Gera JSON com ordens de produção para uma linha"""
    skus = gerar_skus_linha(linha, quantidade=30)
    
    # Montar JSON no formato esperado
    ordens_json = '{"OrdensProducao":['
    
    for i, sku in enumerate(skus):
        if i > 0:
            ordens_json += ','
        
        ordens_json += '{'
        ordens_json += f'"CodigoSKU":"{sku["CodigoSKU"]}",'
        ordens_json += f'"DescricaoSKU":"{sku["DescricaoSKU"]}",'
        ordens_json += f'"DataOP":"{sku["DataOP"]}",'
        ordens_json += f'"IdOrdemProd":"{sku["IdOrdemProd"]}",'
        ordens_json += f'"NumeroOP":"{sku["NumeroOP"]}",'
        ordens_json += f'"DUN14":"{sku["DUN14"]}",'
        ordens_json += f'"Validade":"{sku["Validade"]}",'
        ordens_json += f'"QuantidadePorPallet":"{sku["QuantidadePorPallet"]}",'
        ordens_json += f'"StatusOP":"{sku["StatusOP"]}"'
        ordens_json += '}'
    
    ordens_json += ']}'
    
    return ordens_json

def gerar_soap_response(linha_producao):
    """Gera resposta SOAP XML idêntica à Aplipack"""
    
    # Validar linha
    if not linha_producao:
        return gerar_soap_erro("Linha de produção não especificada")
    
    # Linhas suportadas
    linhas_validas = ["L01IP", "L02IP"]
    
    if linha_producao not in linhas_validas:
        return gerar_soap_erro(f"Linha '{linha_producao}' não encontrada")
    
    # Gerar JSON com ordens
    lista_json = gerar_json_ordens(linha_producao)
    
    # Montar resposta SOAP
    soap_response = f'''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <soap:Body>
    <GetListaOPResponse xmlns="http://www.aplipack.com.br/">
      <GetListaOPResult>
        <xStatus>0</xStatus>
        <xErro></xErro>
        <xListaJSON>{lista_json}</xListaJSON>
      </GetListaOPResult>
    </GetListaOPResponse>
  </soap:Body>
</soap:Envelope>'''
    
    return soap_response

def gerar_soap_erro(mensagem_erro):
    """Gera resposta SOAP de erro"""
    soap_error = f'''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <soap:Body>
    <GetListaOPResponse xmlns="http://www.aplipack.com.br/">
      <GetListaOPResult>
        <xStatus>-1</xStatus>
        <xErro>{mensagem_erro}</xErro>
        <xListaJSON></xListaJSON>
      </GetListaOPResult>
    </GetListaOPResponse>
  </soap:Body>
</soap:Envelope>'''
    
    return soap_error

# ==================== ENDPOINTS ====================

@app.route('/GetListaOP', methods=['POST'])
def get_lista_op():
    """
    Endpoint principal que simula o web service SOAP da Aplipack
    
    Recebe:
        - SOAP XML com UserSoftware, PasswordSoftware, LinhaProducao
    
    Retorna:
        - SOAP XML com lista de ordens de produção (JSON dentro do XML)
    """
    try:
        # Ler corpo da requisição
        soap_request = request.data.decode('utf-8')
        
        print(f"[MOCK API] Requisição recebida:")
        print(f"[MOCK API] Headers: {dict(request.headers)}")
        print(f"[MOCK API] Body (primeiros 500 chars): {soap_request[:500]}...")
        
        # Extrair linha de produção do SOAP
        linha_producao = ""
        if "<LinhaProducao>" in soap_request:
            start = soap_request.find("<LinhaProducao>") + len("<LinhaProducao>")
            end = soap_request.find("</LinhaProducao>")
            linha_producao = soap_request[start:end].strip()
        
        print(f"[MOCK API] Linha extraída: '{linha_producao}'")
        
        # Validar credenciais (mock - aceita qualquer coisa)
        user = ""
        password = ""
        if "<UserSoftware>" in soap_request:
            start = soap_request.find("<UserSoftware>") + len("<UserSoftware>")
            end = soap_request.find("</UserSoftware>")
            user = soap_request[start:end].strip()
        
        if "<PasswordSoftware>" in soap_request:
            start = soap_request.find("<PasswordSoftware>") + len("<PasswordSoftware>")
            end = soap_request.find("</PasswordSoftware>")
            password = soap_request[start:end].strip()
        
        print(f"[MOCK API] Credenciais: User='{user}', Password='{password}'")
        
        # Gerar resposta SOAP
        soap_response = gerar_soap_response(linha_producao)
        
        print(f"[MOCK API] Resposta gerada com sucesso para linha '{linha_producao}'")
        print(f"[MOCK API] Tamanho da resposta: {len(soap_response)} bytes")
        
        # Retornar resposta SOAP
        return Response(
            soap_response,
            mimetype='application/soap+xml; charset=utf-8',
            status=200
        )
        
    except Exception as e:
        print(f"[MOCK API] ERRO: {str(e)}")
        import traceback
        traceback.print_exc()
        
        soap_error = gerar_soap_erro(f"Erro interno do servidor: {str(e)}")
        return Response(
            soap_error,
            mimetype='application/soap+xml; charset=utf-8',
            status=500
        )

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de health check"""
    return {
        "status": "ok",
        "service": "Aplipack Mock API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "linhas_disponiveis": ["L01IP", "L02IP"],
        "skus_por_linha": 30
    }

@app.route('/', methods=['GET'])
def index():
    """Página inicial com informações da API"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Aplipack Mock API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; }
            .info { background: #f0f0f0; padding: 20px; border-radius: 5px; }
            .endpoint { background: #e8f4f8; padding: 15px; margin: 10px 0; border-left: 4px solid #0066cc; }
            code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <h1>🔧 Aplipack Mock API</h1>
        <div class="info">
            <p><strong>Status:</strong> ✅ Online</p>
            <p><strong>Porta:</strong> 5003</p>
            <p><strong>Versão:</strong> 1.0.0</p>
            <p><strong>Descrição:</strong> API mock que simula o web service SOAP da Aplipack</p>
        </div>
        
        <h2>Endpoints Disponíveis</h2>
        
        <div class="endpoint">
            <h3>POST /GetListaOP</h3>
            <p><strong>Descrição:</strong> Retorna lista de ordens de produção (SOAP XML)</p>
            <p><strong>Content-Type:</strong> text/xml</p>
            <p><strong>Linhas suportadas:</strong> L01IP, L02IP</p>
            <p><strong>SKUs por linha:</strong> 30</p>
        </div>
        
        <div class="endpoint">
            <h3>GET /health</h3>
            <p><strong>Descrição:</strong> Health check da API (JSON)</p>
        </div>
        
        <h2>Exemplo de Uso</h2>
        <pre><code>
# Python com requests
import requests

url = "http://localhost:5003/GetListaOP"
headers = {"Content-Type": "text/xml"}
envelope = '''<?xml version="1.0" encoding="utf-8"?>
&lt;soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope"&gt;
  &lt;soap12:Body&gt;
    &lt;GetListaOP xmlns="http://www.aplipack.com.br/"&gt;
      &lt;UserSoftware&gt;test&lt;/UserSoftware&gt;
      &lt;PasswordSoftware&gt;1234&lt;/PasswordSoftware&gt;
      &lt;LinhaProducao&gt;L01IP&lt;/LinhaProducao&gt;
    &lt;/GetListaOP&gt;
  &lt;/soap12:Body&gt;
&lt;/soap12:Envelope&gt;'''

response = requests.post(url, data=envelope, headers=headers)
print(response.text)
        </code></pre>
        
        <h2>Configuração no Django</h2>
        <p>Para usar esta API mock, altere a URL no arquivo <code>views.py</code>:</p>
        <pre><code>
# ANTES (Produção)
url = "http://192.168.30.42:82/WsOffLineCom.asmx?op=GetListaOP"

# DEPOIS (Mock - Desenvolvimento)
url = "http://localhost:5003/GetListaOP"
# ou (se Django estiver em Docker)
url = "http://host.docker.internal:5003/GetListaOP"
        </code></pre>
    </body>
    </html>
    """
    return html

# ==================== INICIALIZAÇÃO ====================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Iniciando Aplipack Mock API")
    print("=" * 60)
    print(f"Porta: 5003")
    print(f"Linhas disponíveis: L01IP, L02IP")
    print(f"SKUs por linha: 30")
    print(f"Formato: SOAP 1.2 XML")
    print("=" * 60)
    print(f"Acesse: http://localhost:5003")
    print(f"Health Check: http://localhost:5003/health")
    print(f"Endpoint SOAP: POST http://localhost:5003/GetListaOP")
    print("=" * 60)
    
    # Rodar servidor Flask
    app.run(
        host='0.0.0.0',  # Aceita conexões de qualquer IP
        port=5003,
        debug=True  # Modo debug para desenvolvimento
    )

