# 🧪 Guia Completo de Testes

Este guia detalha todos os procedimentos de teste do Sistema de Monitoramento Industrial.

## 📋 Checklist de Testes

### ✅ Fase 1: Infraestrutura

- [ ] Docker instalado e funcionando
- [ ] Docker Compose instalado
- [ ] Python 3.11+ instalado
- [ ] Node.js 18+ instalado
- [ ] pnpm instalado

### ✅ Fase 2: Containers Docker

```bash
# Iniciar containers
cd projeto-monitoramento-industrial-completo
docker compose up -d

# Verificar status
docker ps

# Deve mostrar:
# - influxdb-industrial (porta 8086)
# - postgres-industrial (porta 5432)
```

**Testes:**

```bash
# Testar InfluxDB
curl http://localhost:8086/ping
# Esperado: retorna vazio com status 204

# Testar PostgreSQL
docker exec postgres-industrial psql -U django_user -d django_industrial -c "SELECT 1;"
# Esperado: retorna "1"
```

### ✅ Fase 3: Backend Django

```bash
cd backend-django
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

**Testes:**

#### **3.1. Testar Servidor**

```bash
curl http://localhost:8000/admin/
# Esperado: HTML da página de login
```

#### **3.2. Testar Login Admin**

1. Acessar: http://localhost:8000/admin
2. Login: `admin` / `admin123`
3. Verificar se abre o painel admin

#### **3.3. Testar Modelos**

No Django Admin, verificar se existem:

- [ ] **Linhas de Produção** (1 linha: L01)
- [ ] **Equipamentos** (4 equipamentos)
- [ ] **Sensores** (pelo menos 2: entrada e saída)
- [ ] **Métricas de Produção** (tabela vazia inicialmente)

#### **3.4. Testar APIs REST**

```bash
# Listar linhas
curl http://localhost:8000/api/linhas/ | python -m json.tool

# Listar equipamentos
curl http://localhost:8000/api/equipamentos/ | python -m json.tool

# Listar sensores
curl http://localhost:8000/api/sensores/ | python -m json.tool
```

**Esperado:** JSON com dados cadastrados

### ✅ Fase 4: Backend Flask

```bash
cd backend-flask
source ../backend-django/venv/bin/activate
python app.py
```

**Testes:**

#### **4.1. Health Check**

```bash
curl http://localhost:5000/api/health
```

**Esperado:**
```json
{
  "status": "ok",
  "timestamp": "2025-11-15T12:00:00"
}
```

#### **4.2. Listar Equipamentos (Proxy Django)**

```bash
curl http://localhost:5000/api/equipamentos | python -m json.tool
```

**Esperado:** JSON com 4 equipamentos

#### **4.3. Status em Tempo Real (SEM dados ainda)**

```bash
curl http://localhost:5000/api/realtime/status/Enchedora_01 | python -m json.tool
```

**Esperado:** Erro ou dados vazios (normal, pois simulador ainda não rodou)

### ✅ Fase 5: Simulador

```bash
cd simulador
source ../backend-django/venv/bin/activate
python simulador_producao.py
```

**Testes:**

#### **5.1. Verificar Logs**

O terminal deve mostrar mensagens como:

```
✓ Dados enviados: Enchedora_01 - Produzindo - Contagem: 100
✓ Dados enviados: Balanca_01 - Produzindo - Contagem: 80
✓ Dados enviados: Encaixotadora_01 - Produzindo - Contagem: 60
✓ Dados enviados: Envolvedora_01 - Produzindo - Contagem: 50
```

#### **5.2. Verificar Dados no InfluxDB**

```bash
# Aguardar 10 segundos após iniciar o simulador
sleep 10

# Consultar dados
docker exec influxdb-industrial influx -database industrial_db -execute "SELECT * FROM producao LIMIT 5"
```

**Esperado:** Tabela com dados de produção

#### **5.3. Verificar Flask API (COM dados)**

```bash
# Aguardar 10 segundos após iniciar o simulador
sleep 10

curl http://localhost:5000/api/realtime/status/Enchedora_01 | python -m json.tool
```

**Esperado:**
```json
{
  "equipamento": "Enchedora_01",
  "tipo": "Enchedora",
  "linha": "L01",
  "estado": "Produzindo",
  "medicoes": {
    "temperatura": 75.5,
    "pressao": 100.2,
    "velocidade_atual": 98.5,
    "velocidade_padrao": 100.0,
    "contagem": 5890
  },
  "kpis": {
    "disponibilidade": 100.0,
    "performance": 98.5,
    "qualidade": 99.3,
    "oee": 97.8
  }
}
```

### ✅ Fase 6: Frontend React

```bash
cd frontend-react
pnpm install
pnpm dev
```

**Testes:**

#### **6.1. Acessar Dashboard**

1. Abrir navegador: http://localhost:3000
2. Verificar se carrega a página

#### **6.2. Verificar Cards de Equipamentos**

Deve mostrar **4 cards** com:

- [ ] Nome do equipamento (Enchedora_01, Balanca_01, etc.)
- [ ] Badge de estado (Verde = Produzindo)
- [ ] Velocidade atual
- [ ] Velocidade padrão
- [ ] Temperatura e pressão
- [ ] KPIs: Disponibilidade, Performance, OEE

#### **6.3. Testar Auto-Atualização**

1. Observar os valores nos cards
2. Aguardar 5 segundos
3. Verificar se os valores mudaram
4. Verificar "Última atualização" no header

#### **6.4. Testar Botão de Tema**

1. Clicar no ícone de sol/lua no header
2. Verificar se alterna entre tema dark e light

#### **6.5. Testar Botão de Atualização Manual**

1. Clicar no ícone de refresh no header
2. Verificar se os dados atualizam imediatamente

### ✅ Fase 7: Teste de Integração Completa

#### **7.1. Fluxo Completo de Dados**

1. **Simulador** envia dados a cada 5 segundos
2. **Flask** recebe e insere no **InfluxDB**
3. **React** consulta Flask a cada 5 segundos
4. **Dashboard** atualiza automaticamente

**Verificação:**

```bash
# Terminal 1: Ver logs do simulador
# Deve mostrar: ✓ Dados enviados...

# Terminal 2: Consultar Flask
watch -n 5 'curl -s http://localhost:5000/api/realtime/status/Enchedora_01 | python -m json.tool'

# Navegador: Ver dashboard atualizando
```

#### **7.2. Teste de Descarte**

1. Acessar Django Admin: http://localhost:8000/admin
2. Ir em "Sensores"
3. Verificar se existem sensores de entrada e saída
4. Consultar Flask API:

```bash
curl http://localhost:5000/api/realtime/status/Enchedora_01 | python -m json.tool | grep -A 3 "descarte"
```

**Esperado:**
```json
"descarte": {
  "total": 40,
  "percentual": 0.68
}
```

#### **7.3. Teste de Performance**

1. Verificar velocidade planejada no Django Admin
2. Verificar velocidade real no Dashboard React
3. Calcular performance manualmente: (Real / Planejada) × 100
4. Comparar com o valor mostrado no card

### ✅ Fase 8: Testes de Carga

#### **8.1. Múltiplos Equipamentos**

```bash
# Verificar se todos os 4 equipamentos aparecem no dashboard
# Verificar se todos atualizam simultaneamente
```

#### **8.2. Longa Duração**

```bash
# Deixar sistema rodando por 1 hora
# Verificar se:
# - Simulador continua enviando dados
# - Flask continua respondendo
# - React continua atualizando
# - Sem vazamento de memória
```

## 🐛 Resolução de Problemas

### **Problema: Django não inicia**

```bash
# Verificar se PostgreSQL está rodando
docker ps | grep postgres

# Verificar logs
docker logs postgres-industrial

# Recriar banco
docker compose down
docker compose up -d
cd backend-django
python manage.py migrate
```

### **Problema: Flask retorna erro 500**

```bash
# Verificar se InfluxDB está rodando
curl http://localhost:8086/ping

# Verificar se Django está rodando
curl http://localhost:8000/api/equipamentos/

# Ver logs do Flask
# (no terminal onde Flask está rodando)
```

### **Problema: React não mostra dados**

```bash
# Abrir console do navegador (F12)
# Verificar erros de CORS ou conexão

# Testar Flask manualmente
curl http://localhost:5000/api/realtime/status/Enchedora_01

# Verificar se simulador está rodando
# (ver logs do terminal)
```

### **Problema: Simulador não envia dados**

```bash
# Verificar se Flask está rodando
curl http://localhost:5000/api/health

# Verificar URL no código do simulador
# Deve ser: http://localhost:5000/api/dados/inserir

# Reiniciar simulador
# Ctrl+C e python simulador_producao.py
```

## 📊 Métricas de Sucesso

### **Sistema Funcionando 100%**

- [x] 2 containers Docker rodando
- [x] Django Admin acessível
- [x] Flask API respondendo
- [x] Simulador enviando dados
- [x] React Dashboard atualizando
- [x] 4 equipamentos visíveis
- [x] Dados atualizando a cada 5 segundos
- [x] KPIs calculados corretamente
- [x] Descarte calculado automaticamente

## 🎯 Casos de Teste Específicos

### **Teste 1: Adicionar Nova Linha**

1. Django Admin → Linhas de Produção → Adicionar
2. Preencher: L02, "Linha de Envase 02", velocidade 120
3. Salvar
4. Verificar se aparece na lista

### **Teste 2: Adicionar Novo Equipamento**

1. Django Admin → Equipamentos → Adicionar
2. Linha: L01
3. Nome: Rotuladora_01
4. Tipo: Enchedora (usar tipo existente)
5. Salvar
6. Verificar se aparece na lista

### **Teste 3: Configurar Sensores**

1. Django Admin → Sensores → Adicionar
2. Linha: L01
3. Tipo: Sensor de Entrada
4. Tag: contagem_entrada
5. Salvar
6. Repetir para Sensor de Saída

### **Teste 4: Inserir Dados Manualmente**

```bash
curl -X POST http://localhost:5000/api/dados/inserir \
  -H "Content-Type: application/json" \
  -d '{
    "equipamento": "Enchedora_01",
    "medicoes": {
      "temperatura": 75.5,
      "pressao": 100.2,
      "velocidade": 98.5,
      "contagem_entrada": 6000,
      "contagem_saida": 5920,
      "estado": "Produzindo"
    }
  }'
```

**Esperado:**
```json
{
  "status": "success",
  "message": "Dados inseridos com sucesso"
}
```

## ✅ Checklist Final

Antes de considerar o sistema pronto:

- [ ] Todos os containers Docker rodando
- [ ] Django Admin acessível e funcional
- [ ] Flask API respondendo corretamente
- [ ] Simulador enviando dados continuamente
- [ ] React Dashboard mostrando 4 equipamentos
- [ ] Auto-atualização funcionando (5 segundos)
- [ ] Tema dark/light alternando
- [ ] KPIs calculados corretamente
- [ ] Descarte calculado automaticamente
- [ ] Velocidade planejada vs real comparando
- [ ] Sem erros no console do navegador
- [ ] Sem erros nos logs dos serviços

---

**Tempo estimado de teste completo:** 30-45 minutos
