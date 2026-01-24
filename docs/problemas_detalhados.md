# Problemas Detalhados Identificados - MIS-Core

## 1. Reset de Contadores no Fim de Turno

### Análise do Código Atual

**Arquivo:** `backend-flask/production_engine.py` (linhas 236-251)

```python
# Mudança de turno: Zera acumuladores se o nome mudou OU se a data do início do turno mudou
shift_changed = False
current_shift_start = turno_info['inicio_timestamp'] if turno_info else None

if str(turno_atual).strip() != str(state['shift_code']).strip():
    shift_changed = True
elif current_shift_start and state['shift_start_time']:
    # Se o timestamp de início do turno mudou (ex: mesmo turno, outro dia)
    if abs(current_shift_start - state['shift_start_time']) > 60: # Margem de 1 min
        shift_changed = True

if shift_changed:
    state['acc_shift'] = 0
    state['acc_time_stop_shift'] = 0.0
    state['shift_code'] = turno_atual
    state['shift_start_time'] = current_shift_start
```

### Problemas Identificados

1. **Reset Reativo, Não Proativo**: O reset só acontece quando novos dados chegam no próximo turno
2. **Dependência de Dados**: Se a linha parar antes do fim do turno, contadores não são zerados
3. **Falta de Sincronização**: Não usa o horário de fim de turno cadastrado no Django
4. **Persistência Incompleta**: `shift_start_time` pode não estar sendo persistido corretamente no InfluxDB

### Impacto

- Dados de peças ruins/boas podem vazar entre turnos
- Relatórios de turno podem conter dados incorretos
- OEE calculado pode estar errado se incluir dados de múltiplos turnos

### Solução Proposta

1. Criar job agendado que verifica horários de fim de turno a cada minuto
2. Ao detectar fim de turno, forçar reset via API endpoint dedicado
3. Persistir timestamp de início de turno no InfluxDB
4. Adicionar flag `turno_resetado` para evitar resets duplicados

---

## 2. Informações de Descarte na LineDeepView

### Análise do Código Atual

**Arquivo:** `frontend-react/client/src/pages/LineDeepView.tsx` (linha 436)

```typescript
<EquipmentCard
    key={idx}
    nome={eq.nome}
    funcao={eq.tipo}
    estado={eq.medicoes?.estado ?? 'Desconhecido'}
    oee={safeNumber(eq.medicoes?.oee, 0)}
    velocidadeAtual={safeNumber(eq.medicoes?.velocidade_atual, 0)}
    velocidadeNominal={safeNumber(eq.velocidade_nominal, 100)}
    boas={safeNumber(eq.medicoes?.pecas_boas, 0)}
    ruins={safeNumber(eq.medicoes?.pecas_ruins, 0)}
    ultimaParada="N/A"
/>
```

**Arquivo:** `frontend-react/client/src/components/LineDeepView/EquipmentCard.tsx`

O componente recebe `boas` e `ruins`, mas não exibe:
- Percentual de descarte
- Indicador visual de alerta quando descarte é alto
- Total produzido (boas + ruins)

### Solução Proposta

Modificar `EquipmentCard.tsx` para adicionar:

```typescript
const totalProduzido = boas + ruins;
const percentualDescarte = totalProduzido > 0 ? (ruins / totalProduzido) * 100 : 0;

// Badge colorido:
// Verde: < 2%
// Amarelo: 2-5%
// Vermelho: > 5%
```

---

## 3. Lógica de Projeção e Esperado

### Análise do Código Atual

**Backend Flask:** `routes.py` (linhas 854-884)

```python
# ESPERADO (Correto ✓)
producao_esperada = meta_toneladas * (tempo_decorrido / tempo_total_turno)

# PROJEÇÃO (Correto ✓)
tempo_restante_horas = (tempo_total_turno - tempo_decorrido) / 3600.0
projecao = producao_real_ton + (taxa_instantanea * tempo_restante_horas)

# RITMO NECESSÁRIO (Correto ✓)
saldo_necessario = meta_toneladas - producao_real_ton
ritmo_necessario = max(0, saldo_necessario / tempo_restante_horas)
```

**Frontend React:** `productionCalculations.ts`

```typescript
// PROJEÇÃO (linha 74)
return data.producaoReal + (vazaoCalculada * horasRestantes);

// RITMO NECESSÁRIO (linha 108)
const deficit = data.metaTotal - data.producaoReal;
return safeDivide(deficit, horasRestantes, 0);
```

### Análise

✅ **A lógica matemática está CORRETA** tanto no backend quanto no frontend!

**Porém, há problemas de:**

1. **Fonte de Dados Inconsistente**: Frontend pode usar dados diferentes do backend
2. **Falta de Validação**: Não valida se `tempo_total_turno` vem do Django
3. **Produção Real Ambígua**: Pode estar usando equipamento errado

### Problemas Específicos

**Backend (routes.py linha 616-663):**
```python
# Tenta pegar PRODUÇÃO do ÚLTIMO equipamento (produto final)
st_ultimo = production_engine.get_state(ultimo_eq)
met_ultimo = st_ultimo.get('latest_metrics', {})
producao_real_ton = met_ultimo.get('toneladas_turno', 0.0)
```

**Problema:** Se o último equipamento não tiver dados, `producao_real_ton = 0`

**Fallback (linha 697-703):**
```python
if producao_real_ton == 0:
    query = f"SELECT last(toneladas_turno) FROM production WHERE \"line\" = '{normalize_line_name(linha_nome)}' GROUP BY \"equipment\""
    rs = influx_client.query(query)
    points = list(rs.get_points())
    if points:
        producao_real_ton = max([float(p['last']) for p in points if p['last'] is not None], default=0.0)
```

**Problema:** Usa `MAX()` de todos equipamentos, pode pegar valor errado se equipamentos intermediários tiverem contadores maiores

### Solução Proposta

1. **Priorizar Equipamento Líder**: Sempre usar equipamento configurado como "líder" no Django
2. **Validar Tempo de Turno**: Garantir que `tempo_total_turno` vem do cadastro de turno no Django
3. **Logging Detalhado**: Adicionar logs para rastrear qual equipamento está sendo usado
4. **Fallback Inteligente**: Se último equipamento não tiver dados, usar penúltimo, não MAX de todos

---

## 4. Persistência de Dados em Reinicializações

### Análise do Código Atual

**Arquivo:** `production_engine.py` (linhas 164-212)

```python
def _load_state_from_db(self, eq, current_op, current_shift):
    state = self._get_state(eq)
    if state['initialized']: return

    try:
        query = f"SELECT * FROM production WHERE \"equipment\" = '{eq}' ORDER BY time DESC LIMIT 1"
        rs = self.client.query(query)
        points = list(rs.get_points())
        
        if points:
            d = points[0]
            
            # Recupera acumuladores se o contexto for o mesmo
            if last_op == curr_op:
                state['acc_op'] = int(d.get('producao_op_acumulada', 0) or 0)
                state['acc_waste_op'] = int(d.get('refugo_op_acumulado', 0) or 0)
            
            if last_shift == curr_shift:
                state['acc_shift'] = int(d.get('producao_turno_acumulada', 0) or 0)
                state['acc_time_stop_shift'] = float(d.get('tempo_parado_turno', 0) or 0)
```

### Problemas Identificados

1. **Falta de Persistência de `shift_start_time`**: Não está sendo salvo no InfluxDB
2. **Comparação de String Frágil**: `last_shift == curr_shift` pode falhar com espaços/case
3. **Sem Validação de Data**: Não verifica se o turno recuperado é do mesmo dia
4. **Perda de Contexto**: Se container reiniciar no meio do turno, pode perder `shift_start_time`

### Solução Proposta

1. **Adicionar Campo no InfluxDB**: `turno_inicio_timestamp` em cada medição
2. **Validar Data do Turno**: Ao recuperar, verificar se `turno_inicio_timestamp` é do turno atual
3. **Persistência Periódica**: Salvar estado a cada 30s, não só ao processar dados
4. **Shutdown Graceful**: Adicionar handler para salvar estado antes de parar container

---

## 5. Perda de Comunicação e Heartbeat

### Análise do Código Atual

**Arquivo:** `production_engine.py` (linhas 259-264)

```python
# 4. Cálculo de Delta de Tempo
time_delta = 0.0
if state['last_timestamp'] is not None:
    time_delta = now_timestamp - state['last_timestamp']
    # Proteção: Ignora delta muito grande (servidor reiniciou)
    if time_delta > self.MAX_TIME_DELTA or time_delta < 0:
        logger.warning(f"{equipamento}: Delta tempo anormal ({time_delta:.1f}s), ignorando")
        time_delta = 0.0
```

**Constante:** `self.MAX_TIME_DELTA = 300` (5 minutos)

### Problemas Identificados

1. **Perda de Tempo Parado**: Se comunicação cair por > 5 min, tempo parado não é contabilizado
2. **Sem Alerta**: Não há notificação quando comunicação é perdida
3. **Recuperação Silenciosa**: Ao retomar, não há log do tempo perdido
4. **OEE Incorreto**: Disponibilidade pode estar errada se tempo parado não for contabilizado

### Solução Proposta

1. **Aumentar Timeout**: `MAX_TIME_DELTA = 600` (10 minutos)
2. **Registrar Perda de Comunicação**: Salvar evento no InfluxDB quando delta > 300s
3. **Alerta Visual**: Mostrar banner no frontend quando equipamento perde comunicação
4. **Recuperação Inteligente**: Ao retomar, estimar tempo parado baseado em último estado conhecido

---

## 6. Scheduler - Falta de Job de Reset de Turno

### Análise do Código Atual

**Arquivo:** `scheduler.py`

Jobs atuais:
- `job_continuous_optimization`: Golden State (5 min)
- `check_5min_triggers`: Performance (1 min)
- `check_30min_triggers`: Stability (30 min)
- `check_hourly_master`: Golden Master (1 hora)
- `check_waste_backoff`: Waste (1 min)

**Falta:** Job para verificar fim de turno e resetar contadores

### Solução Proposta

Adicionar novo job:

```python
def job_shift_end_check():
    """
    Verifica se algum turno está terminando e força reset de contadores
    """
    logger.info("⏰ Verificando fim de turnos...")
    
    try:
        # Busca turnos ativos do Django
        turnos = requests.get(f"{DJANGO_API_URL}/turnos/?ativo=true").json()
        
        now = datetime.now()
        for turno in turnos:
            hora_fim = datetime.strptime(turno['hora_fim'], '%H:%M:%S').time()
            
            # Verifica se está nos últimos 2 minutos do turno
            fim_dt = datetime.combine(now.date(), hora_fim)
            diff = (fim_dt - now).total_seconds()
            
            if 0 < diff <= 120:  # 2 minutos antes do fim
                logger.info(f"🔔 Turno {turno['nome']} terminando em {diff}s")
                # Força reset de todos equipamentos
                reset_shift_counters(turno['codigo'])
    
    except Exception as e:
        logger.error(f"Erro no job de fim de turno: {e}")

# Adicionar ao scheduler
scheduler.add_job(job_shift_end_check, 'interval', minutes=1, id='shift_end_check')
```

---

## Resumo de Prioridades

### 🔴 Crítico (Implementar Primeiro)

1. ✅ Reset de contadores no fim de turno (scheduler + endpoint)
2. ✅ Persistência de `shift_start_time` no InfluxDB
3. ✅ Validação de turno ao recuperar estado

### 🟡 Importante (Implementar em Seguida)

4. ✅ Adicionar descarte percentual na LineDeepView
5. ✅ Melhorar lógica de seleção de equipamento para produção real
6. ✅ Aumentar timeout de perda de comunicação

### 🟢 Melhorias (Implementar Depois)

7. Refatoração de código
8. Testes unitários
9. Documentação

---

## Próximos Passos

1. Implementar soluções críticas
2. Testar em ambiente local
3. Validar com dados reais
4. Fazer commit no GitHub
5. Documentar mudanças
