# Guia de Migração - Sistema MIS v2

## 📋 Visão Geral

Este guia detalha o processo de migração do sistema MIS básico para a versão 2 com cálculo real de OEE, eventos de estado e gestão de turnos.

## 🔄 Mudanças Principais

### 1. Models Django

#### Novos Models

- **`TurnoProducao`**: Gestão de turnos de trabalho
- **`CalendarioProducao`**: Programação de produção por linha/turno/data
- **`EstadoEquipamento`**: Enum com 10 estados industriais
- **`EventoEstadoEquipamento`**: Rastreamento de mudanças de estado

#### Models Atualizados

- **`MetricaProducao`**: Novos campos para tempos detalhados
  - `tempo_programado` (novo)
  - `tempo_disponivel` (novo)
  - `tempo_nao_programado` (novo)
  - Cálculo automático de OEE no `save()`

### 2. API Django

#### Novos Endpoints

```
GET  /api/turnos/                  - Lista turnos
GET  /api/calendario/              - Lista calendário de produção
GET  /api/eventos-estado/          - Lista eventos de estado
POST /api/eventos_estado/          - Registra mudança de estado (usado pelo Coletor)
```

#### Endpoints Atualizados

```
POST /api/metricas_consolidadas/   - Agora aceita campos adicionais de tempo
```

### 3. Flask

#### Mudanças no Endpoint de Inserção

```python
# ANTES
{
  "equipamento": "Enchedora 01",
  "medicoes": {...}
}

# DEPOIS
{
  "equipamento_codigo": "L01_ENCH_01",  # Código do equipamento
  "linha_codigo": "L01",                 # Código da linha
  "medicoes": {...}
}
```

#### Nova Função de Agregação

- Consulta eventos de estado no Django
- Calcula tempos por categoria (produção, parada, setup, não programado)
- Calcula KPIs reais baseados em tempos reais

### 4. Coletor

#### Detecção de Estados

- Monitora tag `estado` (valor inteiro 0-9)
- Mapeia para enum de estados
- Detecta mudanças automaticamente
- Envia eventos para Django

#### Mapeamento de Estados

```python
MAPEAMENTO_ESTADOS = {
    1: 'RUN',           # Produzindo
    2: 'WAIT_PREV',     # Aguardando equipamento anterior
    3: 'BLOCK_NEXT',    # Equipamento seguinte bloqueado
    4: 'FAULT',         # Falha
    5: 'SETUP',         # Setup / Troca SKU
    6: 'TESTE_PROJ',    # Teste de Projeto
    7: 'AGUARD_MNT',    # Aguardando Manutenção
    8: 'MANUTENCAO',    # Em Manutenção
    9: 'FALTA_MAT',     # Falta de Material
    0: 'OUTRO',         # Outro
}
```

### 5. React

#### Novos Componentes

- **`LinhaDetalhes.tsx`**: Visão detalhada da linha
- **`EquipamentoDetalhes.tsx`**: Visão detalhada do equipamento

#### Componentes Atualizados

- **`Home.tsx`**: Navegação para LinhaDetalhes
- **`EquipamentoCard.tsx`**: Navegação para EquipamentoDetalhes

## 🚀 Processo de Migração

### Passo 1: Backup

```bash
# Backup do banco MySQL
mysqldump -u root -p mis_db > backup_mis_db_$(date +%Y%m%d).sql

# Backup do InfluxDB
influxd backup -portable /path/to/backup

# Backup dos arquivos
tar -czf backup_mis_$(date +%Y%m%d).tar.gz \
  django_app/ flask_app/ coletor/ react_app/
```

### Passo 2: Parar Serviços

```bash
# Parar Coletor
pkill -f coletor.py

# Parar Flask
pkill -f "flask.*app.py"

# Parar Django
pkill -f "manage.py runserver"

# Parar React (desenvolvimento)
pkill -f "vite"
```

### Passo 3: Atualizar Django

```bash
cd django_app

# Ativar ambiente virtual
source venv/bin/activate

# Substituir arquivos
cp /path/to/new/models.py .
cp /path/to/new/serializers.py .
cp /path/to/new/views.py .
cp /path/to/new/urls.py .
cp /path/to/new/admin.py .

# Criar migrações
python manage.py makemigrations

# Revisar migrações
python manage.py sqlmigrate app_name 0001

# Aplicar migrações
python manage.py migrate

# Verificar
python manage.py check
```

### Passo 4: Atualizar Flask

```bash
cd flask_app

# Ativar ambiente virtual
source venv/bin/activate

# Substituir arquivo
cp /path/to/new/app.py .

# Verificar sintaxe
python -m py_compile app.py

# Testar importação
python -c "from app import app; print('OK')"
```

### Passo 5: Atualizar Coletor

```bash
cd coletor

# Ativar ambiente virtual
source venv/bin/activate

# Substituir arquivo
cp /path/to/new/coletor.py .

# Verificar sintaxe
python -m py_compile coletor.py

# Testar importação
python -c "from coletor import ColetorOPC; print('OK')"
```

### Passo 6: Atualizar React

```bash
cd react_app

# Adicionar novos componentes
cp /path/to/new/LinhaDetalhes.tsx src/pages/
cp /path/to/new/EquipamentoDetalhes.tsx src/pages/

# Atualizar componentes existentes (se necessário)
cp /path/to/new/Home.tsx src/pages/
cp /path/to/new/EquipamentoCard.tsx src/components/

# Instalar dependências (se houver novas)
npm install

# Verificar erros de TypeScript
npm run type-check

# Build
npm run build
```

### Passo 7: Configurar Turnos e Calendário

```bash
# Acessar Django Admin
# http://localhost:8000/admin

# 1. Criar Turnos
Turnos de Produção → Adicionar

Turno A:
- Nome: Turno A
- Código: A
- Hora Início: 06:00
- Hora Fim: 14:00
- Duração: 8 horas

Turno B:
- Nome: Turno B
- Código: B
- Hora Início: 14:00
- Hora Fim: 22:00
- Duração: 8 horas

Turno C:
- Nome: Turno C
- Código: C
- Hora Início: 22:00
- Hora Fim: 06:00
- Duração: 8 horas

# 2. Programar Calendário (próximos 30 dias)
# Pode ser feito via script ou manualmente
```

### Passo 8: Adicionar Tag de Estado

```bash
# Para cada equipamento, adicionar tag de estado no Django Admin

Equipamentos → [Selecionar Equipamento] → Tags de Coleta → Adicionar

Tag Estado:
- Conexão: [Selecionar conexão OPC]
- Nome Métrica: estado
- Node ID: ns=2;s=Linha1.Enchedora.Estado
- Tipo: INT
- Ativa: ✓
```

### Passo 9: Reiniciar Serviços

```bash
# Django
cd django_app
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000 &

# Flask
cd flask_app
source venv/bin/activate
python app.py &

# Coletor
cd coletor
source venv/bin/activate
python coletor.py &

# React (produção)
cd react_app
npm run preview &

# Ou usar PM2 para gerenciamento de processos
pm2 start ecosystem.config.js
```

### Passo 10: Validação

```bash
# 1. Verificar Django
curl http://localhost:8000/api/linhas/
curl http://localhost:8000/api/turnos/
curl http://localhost:8000/api/eventos-estado/

# 2. Verificar Flask
curl http://localhost:5000/api/health

# 3. Verificar Coletor
tail -f coletor/coletor.log
# Deve mostrar: "Mudança de estado detectada"

# 4. Verificar React
# Abrir http://localhost:3000
# Navegar: Home → Linha → Equipamento
# Verificar se dados aparecem

# 5. Verificar eventos de estado
# Django Admin → Eventos de Estado
# Deve mostrar eventos sendo registrados

# 6. Aguardar 1 hora e verificar agregação
# Django Admin → Métricas de Produção
# Verificar se métricas horárias estão sendo criadas com KPIs calculados
```

## 🔍 Verificações Pós-Migração

### 1. Integridade dos Dados

```sql
-- Verificar se todos os equipamentos têm tags de estado
SELECT e.nome, COUNT(t.id) as num_tags_estado
FROM equipamento e
LEFT JOIN tagcoleta t ON t.equipamento_id = e.id AND t.nome_metrica = 'estado'
GROUP BY e.id
HAVING num_tags_estado = 0;

-- Verificar eventos de estado
SELECT COUNT(*) FROM eventoestadoequipamento;

-- Verificar métricas com novos campos
SELECT COUNT(*) FROM metricaproducao WHERE tempo_programado > 0;
```

### 2. Performance

```bash
# Tempo de resposta da API Django
time curl http://localhost:8000/api/linhas/

# Tempo de resposta da API Flask
time curl http://localhost:5000/api/realtime/status/L01_ENCH_01

# Uso de memória
ps aux | grep -E "(python|node)" | awk '{print $6/1024 " MB\t" $11}'

# Uso de CPU
top -b -n 1 | grep -E "(python|node)"
```

### 3. Logs

```bash
# Verificar erros no Django
grep ERROR django_app/logs/django.log

# Verificar erros no Flask
grep ERROR flask_app/logs/flask.log

# Verificar erros no Coletor
grep ERROR coletor/coletor.log
```

## 🐛 Problemas Comuns

### Problema 1: Migrações Django Falham

**Sintoma**: Erro ao executar `python manage.py migrate`

**Solução**:
```bash
# Verificar estado das migrações
python manage.py showmigrations

# Fazer fake migration se necessário
python manage.py migrate --fake app_name 0001

# Ou reverter e reaplicar
python manage.py migrate app_name zero
python manage.py migrate app_name
```

### Problema 2: Coletor Não Detecta Estados

**Sintoma**: Nenhum evento de estado sendo criado

**Solução**:
```bash
# 1. Verificar se tag de estado existe
curl http://localhost:8000/api/configuracao_coletor/ | jq '.equipamentos[].tags_coleta[] | select(.nome_metrica=="estado")'

# 2. Verificar logs do Coletor
tail -f coletor/coletor.log | grep "estado"

# 3. Testar leitura da tag OPC manualmente
python -c "
from asyncua import Client
import asyncio

async def test():
    client = Client('opc.tcp://192.168.1.10:4840')
    await client.connect()
    node = client.get_node('ns=2;s=Linha1.Enchedora.Estado')
    value = await node.read_value()
    print(f'Valor: {value}')
    await client.disconnect()

asyncio.run(test())
"
```

### Problema 3: Flask Não Agrega Métricas

**Sintoma**: Métricas horárias não aparecem no Django

**Solução**:
```bash
# 1. Verificar se agregação está habilitada
grep AGREGACAO_HABILITADA flask_app/.env

# 2. Verificar logs do scheduler
tail -f flask_app/logs/flask.log | grep "agregação"

# 3. Executar agregação manualmente
python -c "
import sys
sys.path.insert(0, 'flask_app')
from app import agregar_metricas_hora
agregar_metricas_hora()
"

# 4. Verificar se há dados no InfluxDB
influx -execute "SELECT COUNT(*) FROM producao"
```

### Problema 4: React Não Exibe Novos Componentes

**Sintoma**: Erro 404 ao navegar para /linha/:id ou /equipamento/:id

**Solução**:
```bash
# 1. Verificar rotas no App.tsx
cat react_app/src/App.tsx | grep -A 5 "Route"

# 2. Adicionar rotas se necessário
# Editar App.tsx e adicionar:
<Route path="/linha/:linhaId" element={<LinhaDetalhes />} />
<Route path="/equipamento/:equipamentoId" element={<EquipamentoDetalhes />} />

# 3. Rebuild
cd react_app
npm run build
```

## 📊 Monitoramento Contínuo

### Dashboards Recomendados

1. **Grafana + InfluxDB**: Visualização de séries temporais
2. **Django Admin**: Gestão e visualização de eventos
3. **Logs Centralizados**: ELK Stack ou similar

### Alertas Recomendados

1. **Coletor offline**: > 5 minutos sem enviar dados
2. **OEE abaixo da meta**: < 70% por mais de 1 hora
3. **Equipamento em FAULT**: > 10 minutos
4. **Agregação falhou**: Sem métricas horárias por > 2 horas

## 🔐 Segurança

### Recomendações Pós-Migração

1. **Alterar senhas padrão** do Django Admin
2. **Habilitar HTTPS** em produção
3. **Configurar firewall** para limitar acesso às APIs
4. **Implementar autenticação** nas APIs (JWT)
5. **Revisar permissões** no Django Admin

## 📚 Documentação Adicional

- [README.md](README.md) - Documentação completa do sistema
- [CHANGELOG.md](CHANGELOG.md) - Histórico de mudanças
- [API_REFERENCE.md](API_REFERENCE.md) - Referência completa da API

## 🆘 Suporte

Em caso de problemas durante a migração:

1. Consultar logs detalhados
2. Verificar este guia de troubleshooting
3. Restaurar backup se necessário
4. Contatar equipe de suporte técnico

---

**Data de Criação**: 2024-01-15  
**Versão**: 2.0  
**Autor**: Equipe MIS
