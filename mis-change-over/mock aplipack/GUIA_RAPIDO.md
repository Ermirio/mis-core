# Guia Rápido - Aplipack Mock API

## 🚀 Instalação em 3 Passos

### Passo 1: Extrair Arquivos
```bash
# Extrair o ZIP
unzip aplipack_mock_api_completo.zip -d aplipack-mock

# Entrar na pasta
cd aplipack-mock
```

### Passo 2: Instalar e Rodar
```bash
# Instalar dependências
pip install -r requirements_mock_api.txt

# Rodar API
python aplipack_mock_api.py
```

### Passo 3: Testar
```bash
# Em outro terminal
curl http://localhost:5003/health
```

**Pronto! A API está rodando em http://localhost:5003** ✅

---

## 🔧 Configurar no Django

### Opção A: Configuração Automática (Recomendado)

1. **Copiar arquivo de configuração:**
   ```bash
   cp aplipack_config.py /caminho/para/seu/app/django/
   ```

2. **Editar aplipack_config.py:**
   ```python
   USE_MOCK = True  # Ativar modo mock
   ```

3. **Aplicar patch no views.py:**
   - Abra `views_patch_aplipack_config.py`
   - Copie a função `get_lista_op` corrigida
   - Substitua no seu `views.py`

4. **Reiniciar Django:**
   ```bash
   docker restart mis_backend_container
   ```

### Opção B: Configuração Manual (Rápida)

1. **Editar views.py:**
   
   Localize a linha (~862):
   ```python
   url = "http://192.168.30.42:82/WsOffLineCom.asmx?op=GetListaOP"
   ```
   
   Altere para:
   ```python
   url = "http://localhost:5003/GetListaOP"
   ```
   
   **OU** (se Django estiver em Docker):
   ```python
   url = "http://host.docker.internal:5003/GetListaOP"
   ```

2. **Reiniciar Django:**
   ```bash
   docker restart mis_backend_container
   ```

---

## ✅ Validar Funcionamento

### 1. Testar API Mock
```bash
python test_mock_api.py
```

### 2. Testar no Django
```bash
# Acessar a aplicação
http://192.168.15.13:3000/

# Clicar em "Sincronizar SKUs"
# Deve carregar 30 SKUs da linha selecionada
```

### 3. Ver Logs
```bash
# Logs da API Mock
# (no terminal onde rodou python aplipack_mock_api.py)

# Logs do Django
docker logs mis_backend_container
```

---

## 🔄 Alternar entre Mock e Produção

### Método 1: Usando aplipack_config.py

```python
# Editar aplipack_config.py

# Para MOCK (desenvolvimento)
USE_MOCK = True

# Para PRODUÇÃO
USE_MOCK = False
```

### Método 2: Variável de Ambiente

```bash
# Linux/Mac
export APLIPACK_USE_MOCK=true   # Mock
export APLIPACK_USE_MOCK=false  # Produção

# Windows CMD
set APLIPACK_USE_MOCK=true

# Windows PowerShell
$env:APLIPACK_USE_MOCK='true'
```

### Método 3: Manual no views.py

```python
# MOCK
url = "http://localhost:5003/GetListaOP"

# PRODUÇÃO
url = "http://192.168.30.42:82/WsOffLineCom.asmx?op=GetListaOP"
```

---

## 📊 Dados Disponíveis

- **Linhas:** L01 e L02
- **SKUs por linha:** 30
- **Formato:** SOAP XML (idêntico à Aplipack)

### Exemplo de SKU Retornado:

```json
{
  "CodigoSKU": "FLX0001",
  "DescricaoSKU": "Produto Flexível L01 - Item 1",
  "DataOP": "/Date(1729872000000)/",
  "IdOrdemProd": "10100",
  "NumeroOP": "OP-L01-0001",
  "DUN14": "12345678000001",
  "Validade": "06/2026",
  "QuantidadePorPallet": "100",
  "StatusOP": "Ativo"
}
```

---

## 🐛 Problemas Comuns

### "Connection refused"
```bash
# Verificar se API está rodando
curl http://localhost:5003/health

# Se não estiver, iniciar
python aplipack_mock_api.py
```

### Django não conecta (Docker)
```python
# Usar URL correta para Docker
url = "http://host.docker.internal:5003/GetListaOP"
```

### Dados não aparecem
```bash
# Ver logs do Django
docker logs mis_backend_container

# Ver logs da API
# (no terminal da API)
```

---

## 📞 Comandos Úteis

```bash
# Iniciar API
python aplipack_mock_api.py

# Testar API
curl http://localhost:5003/health
python test_mock_api.py

# Ver exemplos
python exemplo_uso_api.py

# Reiniciar Django
docker restart mis_backend_container

# Ver logs Django
docker logs -f mis_backend_container
```

---

## 📚 Documentação Completa

Para mais detalhes, consulte:
- **README_MOCK_API.md** - Documentação completa
- **views_patch_aplipack_config.py** - Instruções de integração
- **exemplo_uso_api.py** - Exemplos de código

---

## 🎯 Checklist de Instalação

- [ ] Extrair arquivos do ZIP
- [ ] Instalar dependências: `pip install -r requirements_mock_api.txt`
- [ ] Iniciar API: `python aplipack_mock_api.py`
- [ ] Testar API: `curl http://localhost:5003/health`
- [ ] Copiar `aplipack_config.py` para o Django
- [ ] Editar `USE_MOCK = True` no `aplipack_config.py`
- [ ] Aplicar patch no `views.py`
- [ ] Reiniciar Django: `docker restart mis_backend_container`
- [ ] Testar sincronização na aplicação web
- [ ] Verificar se 30 SKUs foram carregados

---

**Pronto para usar! 🎉**

Se tiver dúvidas, consulte o README_MOCK_API.md ou execute os testes.

