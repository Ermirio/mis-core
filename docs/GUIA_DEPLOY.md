# Guia de Deploy - MIS-Core Melhorias

## 📦 Commit Realizado

**Branch:** `mis-hub`  
**Commit Hash:** `e4d8ce50`  
**Data:** 2026-01-24

---

## 🚀 Próximos Passos para Deploy

### 1. Na Máquina de Desenvolvimento

```bash
# 1. Fazer pull das mudanças
cd /path/to/mis-core
git checkout mis-hub
git pull origin mis-hub

# 2. Verificar as mudanças
git log --oneline -1
git show e4d8ce50 --stat
```

### 2. Gerar Novas Imagens Docker

```bash
# Backend Flask
cd mis-core/backend-flask
docker build -t mis-core-flask:v1.2 .

# Frontend React
cd ../frontend-react
docker build -t mis-core-frontend:v1.1 .
```

**Nota:** As imagens Django e outros serviços não foram modificadas, não precisam rebuild.

### 3. Atualizar docker-compose.yml (Opcional)

Se quiser usar versionamento de imagens:

```yaml
services:
  flask:
    image: mis-core-flask:v1.2  # Atualizado
    # ... resto da config

  frontend:
    image: mis-core-frontend:v1.1  # Atualizado
    # ... resto da config
```

### 4. Deploy no Servidor OT Offline

#### Opção A: Transferir Imagens Docker

```bash
# Na máquina de desenvolvimento
docker save mis-core-flask:v1.2 | gzip > mis-core-flask-v1.2.tar.gz
docker save mis-core-frontend:v1.1 | gzip > mis-core-frontend-v1.1.tar.gz

# Transferir para servidor OT (USB, rede interna, etc.)
# No servidor OT
docker load < mis-core-flask-v1.2.tar.gz
docker load < mis-core-frontend-v1.1.tar.gz
```

#### Opção B: Git Clone + Build no Servidor

```bash
# No servidor OT
cd /path/to/mis-core
git pull origin mis-hub

# Rebuild apenas os serviços modificados
docker-compose build flask frontend
```

### 5. Reiniciar Serviços

```bash
# Parar serviços
docker-compose down

# Subir novamente
docker-compose up -d

# Verificar logs
docker-compose logs -f flask
docker-compose logs -f frontend
```

### 6. Validação Pós-Deploy

#### 6.1. Verificar Scheduler

```bash
# Verificar logs do Flask
docker-compose logs flask | grep "shift_end_check"

# Deve aparecer:
# ⏰ Verificando fim de turnos...
```

#### 6.2. Testar Endpoint de Reset

```bash
# Teste manual
curl -X POST http://localhost:5000/api/shift/reset \
  -H "Content-Type: application/json" \
  -d '{}'

# Resposta esperada:
# {"success": true, "message": "Reset de turno executado para todos equipamentos", "count": X}
```

#### 6.3. Verificar UI de Descarte

1. Acessar: `http://localhost:3000/linha/L01` (ou outra linha)
2. Verificar cards de equipamentos
3. Confirmar que aparece:
   - Linha "Descarte" com unidades
   - Badge colorido com percentual
   - Cores: Verde (< 2%), Amarelo (2-5%), Vermelho (> 5%)

#### 6.4. Verificar Logs de Detecção Inteligente

```bash
# Monitorar logs do Flask
docker-compose logs -f flask | grep -E "(Reset físico|Delta suspeito|Primeira medição)"

# Exemplos esperados:
# ✓ Reset físico detectado (contador diminuiu: 1000 -> 50)
# ⚠️ Delta suspeito após mudança de turno (1500), ignorando
# ⚠️ Primeira medição com valor alto (800), considerando como 0
```

---

## 🔍 Troubleshooting

### Problema: Scheduler não está executando

**Sintoma:** Não aparecem logs de "⏰ Verificando fim de turnos..."

**Solução:**
```bash
# Verificar se scheduler iniciou
docker-compose logs flask | grep "Scheduler Started"

# Deve aparecer:
# 🚀 Scheduler Started (Golden State Optimization: 5 min)

# Se não aparecer, reiniciar Flask
docker-compose restart flask
```

### Problema: Reset não está funcionando

**Sintoma:** Contadores não zeram no fim do turno

**Diagnóstico:**
```bash
# 1. Verificar se turnos estão cadastrados no Django
curl http://localhost:8000/api/turnos/?ativo=true

# 2. Verificar logs do scheduler
docker-compose logs flask | grep "Turno.*terminando"

# 3. Testar endpoint manualmente
curl -X POST http://localhost:5000/api/shift/reset -H "Content-Type: application/json" -d '{}'
```

**Possíveis Causas:**
- Turnos não cadastrados no Django
- Horário do servidor incorreto
- Scheduler não iniciou

### Problema: Descarte não aparece na UI

**Sintoma:** Cards de equipamento não mostram linha de descarte

**Solução:**
```bash
# 1. Verificar se frontend foi atualizado
docker-compose logs frontend | grep "build"

# 2. Limpar cache do navegador (Ctrl+Shift+R)

# 3. Verificar se dados estão chegando
curl http://localhost:5000/api/equipamento/dados/E01 | jq '.pecas_boas, .pecas_ruins'
```

### Problema: Valores impossíveis ainda aparecem

**Sintoma:** Produção começa com valores altos no início do turno

**Diagnóstico:**
```bash
# Verificar logs de detecção
docker-compose logs flask | grep "Delta suspeito\|Primeira medição"

# Se não aparecer, verificar se lógica está ativa
docker-compose exec flask python -c "from production_engine import ProductionEngine; print('OK')"
```

---

## 📊 Monitoramento Contínuo

### Logs Importantes

```bash
# Monitorar reset de turno
docker-compose logs -f flask | grep -E "(Reset de turno|shift_end_check)"

# Monitorar detecção de anomalias
docker-compose logs -f flask | grep -E "(Reset físico|Delta suspeito|valor alto)"

# Monitorar produção
docker-compose logs -f flask | grep "DEBUG PRODUCAO\|DEBUG VAZAO\|DEBUG PROJECAO"
```

### Métricas de Sucesso

**Após 1 semana de operação:**
- ✅ Nenhum caso de "vazamento" de dados entre turnos
- ✅ Logs de reset aparecem no horário correto
- ✅ Valores impossíveis são detectados e ignorados
- ✅ UI mostra descarte com percentual correto

---

## 🔧 Configurações Opcionais

### Ajustar Threshold de Detecção

Se os valores de threshold (500, 1000, 100) não forem adequados para sua operação:

**Arquivo:** `mis-core/backend-flask/production_engine.py`

```python
# Linha 320: Threshold de delta suspeito
elif shift_changed and delta > 1000:  # Ajustar este valor

# Linha 327: Threshold de primeira medição
if contagem_bruta > 500:  # Ajustar este valor

# Linha 346: Threshold de descarte
if descarte > 100:  # Ajustar este valor
```

### Ajustar Tempo de Antecedência do Reset

Se 60 segundos antes do fim do turno não for adequado:

**Arquivo:** `mis-core/backend-flask/scheduler.py`

```python
# Linha 59: Tempo de antecedência
if 0 < diff <= 60:  # Ajustar para 120 (2 min) ou outro valor
```

### Ajustar Cores do Badge de Descarte

**Arquivo:** `mis-core/frontend-react/client/src/components/LineDeepView/EquipmentCard.tsx`

```typescript
// Linha 34-38: Thresholds de cor
const getDescarteBadgeColor = (perc: number) => {
    if (perc < 2) return 'bg-green-100 text-green-700 border-green-300';  // Ajustar 2
    if (perc < 5) return 'bg-yellow-100 text-yellow-700 border-yellow-300';  // Ajustar 5
    return 'bg-red-100 text-red-700 border-red-300';
};
```

---

## 📝 Checklist de Deploy

- [ ] Pull do código atualizado
- [ ] Build das novas imagens Docker
- [ ] Transferência para servidor OT (se offline)
- [ ] Backup do banco de dados (precaução)
- [ ] Parar serviços antigos
- [ ] Subir novos serviços
- [ ] Verificar logs de inicialização
- [ ] Testar endpoint de reset
- [ ] Verificar UI de descarte
- [ ] Monitorar por 1 hora
- [ ] Validar no próximo fim de turno
- [ ] Documentar observações

---

## 🆘 Rollback (Se Necessário)

Se algo der errado:

```bash
# 1. Voltar para commit anterior
cd /path/to/mis-core
git checkout mis-hub
git reset --hard da633afd  # Commit anterior

# 2. Rebuild imagens
docker-compose build flask frontend

# 3. Reiniciar
docker-compose down
docker-compose up -d

# 4. Reportar problema
# Enviar logs para análise:
docker-compose logs flask > flask-error.log
docker-compose logs frontend > frontend-error.log
```

---

## 📞 Suporte

**Logs para enviar em caso de problemas:**
```bash
# Coletar todos logs relevantes
docker-compose logs flask > flask.log
docker-compose logs frontend > frontend.log
docker-compose logs django > django.log
docker-compose ps > containers-status.txt
```

**Informações úteis:**
- Commit hash: `e4d8ce50`
- Branch: `mis-hub`
- Data do deploy: _______
- Horário do primeiro fim de turno após deploy: _______
- Observações: _______

---

## ✅ Validação Final

Após 24 horas de operação, verificar:

1. **Reset de Turno:**
   - [ ] Contadores zeraram no horário correto
   - [ ] Logs de reset aparecem nos horários esperados
   - [ ] Nenhum vazamento de dados entre turnos

2. **Detecção Inteligente:**
   - [ ] Valores impossíveis foram detectados e ignorados
   - [ ] Resets físicos foram detectados corretamente
   - [ ] Logs de detecção aparecem quando necessário

3. **UI de Descarte:**
   - [ ] Percentual aparece corretamente
   - [ ] Cores do badge estão corretas
   - [ ] Valores batem com backend

4. **Persistência:**
   - [ ] Dados persistem após restart de container
   - [ ] Turno correto é mantido após reinicialização
   - [ ] Acumuladores corretos após perda de comunicação

---

**Deploy realizado por:** _______  
**Data:** _______  
**Validado por:** _______  
**Data da validação:** _______
