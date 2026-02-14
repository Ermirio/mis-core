# Aplipack Mock API

API Flask que simula o web service SOAP da Aplipack para testes offline e desenvolvimento.

## 📋 Características

- ✅ Retorna resposta SOAP XML idêntica à API real da Aplipack
- ✅ Gera 30 SKUs diferentes por linha (L01 e L02)
- ✅ Dados realistas e variados (datas, códigos, descrições)
- ✅ Suporta múltiplas linhas de produção
- ✅ Fácil integração com o Django existente
- ✅ Pode rodar localmente ou em Docker

## 🚀 Início Rápido

### Opção 1: Rodar Localmente

```bash
# 1. Instalar dependências
pip install -r requirements_mock_api.txt

# 2. Iniciar a API
python aplipack_mock_api.py

# 3. Testar
curl http://localhost:5003/health
```

### Opção 2: Rodar com Docker

```bash
# 1. Build da imagem
docker build -f Dockerfile.mock -t aplipack-mock:latest .

# 2. Rodar container
docker run -d -p 5003:5003 --name aplipack-mock aplipack-mock:latest

# 3. Ver logs
docker logs -f aplipack-mock

# 4. Parar container
docker stop aplipack-mock
docker rm aplipack-mock
```

### Opção 3: Rodar com Docker Compose

```bash
# 1. Build e iniciar
docker-compose -f docker-compose-mock.yml up -d

# 2. Ver logs
docker-compose -f docker-compose-mock.yml logs -f aplipack-mock

# 3. Parar
docker-compose -f docker-compose-mock.yml down
```

## 🔧 Configuração no Django

### Método 1: Usar arquivo de configuração (Recomendado)

1. **Copie o arquivo de configuração:**
   ```bash
   cp aplipack_config.py /caminho/para/seu/app/django/
   ```

2. **Aplique o patch no views.py:**
   - Abra o arquivo `views_patch_aplipack_config.py`
   - Siga as instruções para modificar o `views.py`

3. **Alternar entre mock e produção:**
   ```python
   # No arquivo aplipack_config.py
   USE_MOCK = True   # Para usar mock
   USE_MOCK = False  # Para usar produção
   ```

### Método 2: Alterar diretamente no views.py

Localize a função `get_lista_op` (linha ~862) e altere a URL:

```python
# ANTES (Produção)
url = "http://192.168.30.42:82/WsOffLineCom.asmx?op=GetListaOP"

# DEPOIS (Mock - Local)
url = "http://localhost:5003/GetListaOP"

# OU (Mock - Docker)
url = "http://host.docker.internal:5003/GetListaOP"
```

## 📡 Endpoints

### GET /
Página inicial com documentação da API

**Exemplo:**
```bash
curl http://localhost:5003/
```

### GET /health
Health check da API (retorna JSON)

**Exemplo:**
```bash
curl http://localhost:5003/health
```

**Resposta:**
```json
{
  "status": "ok",
  "service": "Aplipack Mock API",
  "version": "1.0.0",
  "timestamp": "2025-10-25T14:30:00",
  "linhas_disponiveis": ["L01IP", "L02IP"],
  "skus_por_linha": 30
}
```

### POST /GetListaOP
Endpoint principal SOAP (retorna XML)

**Exemplo:**
```bash
curl -X POST http://localhost:5003/GetListaOP \
  -H "Content-Type: text/xml" \
  -d '<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <GetListaOP xmlns="http://www.aplipack.com.br/">
      <UserSoftware>test</UserSoftware>
      <PasswordSoftware>1234</PasswordSoftware>
      <LinhaProducao>L01IP</LinhaProducao>
    </GetListaOP>
  </soap12:Body>
</soap12:Envelope>'
```

**Resposta:**
```xml
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <GetListaOPResponse xmlns="http://www.aplipack.com.br/">
      <GetListaOPResult>
        <xStatus>0</xStatus>
        <xErro></xErro>
        <xListaJSON>{"OrdensProducao":[...]}</xListaJSON>
      </GetListaOPResult>
    </GetListaOPResponse>
  </soap:Body>
</soap:Envelope>
```

## 🧪 Testes

Execute o script de testes para validar a API:

```bash
python test_mock_api.py
```

O script testa:
1. ✅ Health check
2. ✅ Requisição SOAP para L01
3. ✅ Requisição SOAP para L02
4. ✅ Tratamento de erro (linha inválida)
5. ✅ Diferença entre linhas

## 📊 Dados Gerados

### Estrutura dos SKUs

Cada linha gera 30 SKUs com:

- **CodigoSKU**: Código único (ex: FLX0001, CTR0015)
- **DescricaoSKU**: Descrição do produto
- **DataOP**: Data da ordem (timestamp Unix)
- **IdOrdemProd**: ID único da ordem
- **NumeroOP**: Número da OP (ex: OP-L01-0001)
- **DUN14**: Código de barras (14 dígitos)
- **Validade**: Data de validade (MM/YYYY)
- **QuantidadePorPallet**: Quantidade (50-200)
- **StatusOP**: Status (Ativo ou Em Produção)

### Diferenças entre Linhas

**L01IP (Linha Flexível):**
- Prefixos: FLX, STD, PRO
- Categorias: Flexível, Standard, Premium

**L02IP (Linha Cartucho):**
- Prefixos: CTR, ECO, MAX
- Categorias: Cartucho, Econômico, Máximo

## 🔄 Integração com Docker Compose Existente

Para integrar com seu Docker Compose principal, adicione ao `Docker-Compose.yaml`:

```yaml
services:
  # ... seus serviços existentes ...

  # API Mock da Aplipack
  aplipack-mock:
    build:
      context: .
      dockerfile: Dockerfile.mock
    image: aplipack-mock:latest
    container_name: aplipack_mock_container
    ports:
      - "5003:5003"
    networks:
      - app_network
      - shared-network
    restart: unless-stopped
```

E no Django, use:
```python
url = "http://aplipack-mock:5003/GetListaOP"
```

## 🐛 Troubleshooting

### Problema: Erro "Connection refused"

**Causa:** API não está rodando ou porta incorreta

**Solução:**
```bash
# Verificar se está rodando
curl http://localhost:5003/health

# Ver logs
docker logs aplipack-mock

# Reiniciar
docker restart aplipack-mock
```

### Problema: Django não consegue conectar (Docker)

**Causa:** URL incorreta para ambiente Docker

**Solução:**
```python
# Se Django estiver em container, use:
url = "http://host.docker.internal:5003/GetListaOP"

# Ou se ambos estiverem na mesma rede:
url = "http://aplipack-mock:5003/GetListaOP"
```

### Problema: Resposta vazia ou erro 500

**Causa:** Linha não especificada ou inválida

**Solução:**
- Certifique-se de enviar `LinhaProducao` no SOAP
- Use apenas linhas válidas: L01IP, L02IP

### Problema: Dados não aparecem no Django

**Causa:** Parse do XML/JSON pode estar falhando

**Solução:**
1. Verifique os logs do Django
2. Compare a resposta do mock com a real
3. Use o script de teste para validar

## 📝 Arquivos do Projeto

```
.
├── aplipack_mock_api.py           # API Flask principal
├── aplipack_config.py             # Configuração centralizada
├── views_patch_aplipack_config.py # Patch para views.py
├── requirements_mock_api.txt      # Dependências Python
├── Dockerfile.mock                # Dockerfile para a API
├── docker-compose-mock.yml        # Docker Compose
├── test_mock_api.py               # Script de testes
└── README_MOCK_API.md             # Este arquivo
```

## 🎯 Casos de Uso

### Desenvolvimento Offline
Trabalhe sem conexão com a API real da Aplipack

### Testes Automatizados
Use dados consistentes para testes

### Demonstrações
Mostre o sistema sem depender da API externa

### Debug
Controle os dados retornados para testar cenários específicos

## 🔐 Segurança

⚠️ **ATENÇÃO:** Esta API é apenas para desenvolvimento/testes!

- Não use em produção
- Não exponha publicamente
- Credenciais são mockadas (aceita qualquer valor)

## 📞 Suporte

Se tiver problemas:

1. Verifique os logs: `docker logs aplipack-mock`
2. Execute os testes: `python test_mock_api.py`
3. Verifique a configuração no Django
4. Compare com a API real da Aplipack

## 📄 Licença

Este é um projeto interno para desenvolvimento e testes.

---

**Criado para:** Sistema MIS - Troca Automática de SKU  
**Data:** 2025-10-25  
**Versão:** 1.0.0

