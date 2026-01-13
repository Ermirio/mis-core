# Especificação de Lógica PLC para Integração com MIS-Core

## 1. Visão Geral

Este documento define a lógica que deve ser implementada no CLP (Controlador Lógico Programável) para integração com a plataforma MIS-Core. O objetivo é padronizar:

- **Estados de equipamento** (para cálculo de OEE)
- **Contagem de produção** (unidades produzidas)
- **Detecção automática de motivo de parada**

---

## 2. Estados de Equipamento (Machine States)

O MIS-Core utiliza 12 estados industriais que devem ser gerados pelo PLC:

| Código | Estado | Descrição | Impacto OEE |
|--------|--------|-----------|-------------|
| `RUN` | Produzindo | Máquina em operação normal | ✅ Tempo Produtivo |
| `PARTINDO` | Partindo | Máquina iniciando ciclo | ⚠️ Perda Planejada |
| `PARANDO` | Parando | Máquina encerrando ciclo | ⚠️ Perda Planejada |
| `WAIT_PREV` | Aguardando Anterior | Sem peça na entrada (gargalo a montante) | ❌ Perda por Espera |
| `BLOCK_NEXT` | Bloqueado Posterior | Saída cheia (gargalo a jusante) | ❌ Perda por Bloqueio |
| `FAULT` | Falha | Equipamento em falha/alarme | ❌ Perda por Falha |
| `SETUP` | Setup/Troca SKU | Troca de produto ou ajuste | ⚠️ Perda Planejada |
| `TESTE_PROJ` | Teste de Projeto | Teste de engenharia | ⚠️ Excluído do OEE |
| `AGUARD_MNT` | Aguardando Manutenção | Aguardando técnico | ❌ Perda por Manutenção |
| `MANUTENCAO` | Em Manutenção | Manutenção em execução | ⚠️ Parada Planejada |
| `FALTA_MAT` | Falta de Material | Sem insumo/embalagem | ❌ Perda por Material |
| `OUTRO` | Outro | Parada não classificada | ❌ Perda Diversa |

---

## 3. Lógica de Determinação de Estado

### 3.1 Diagrama de Decisão

```
                    ┌─────────────────────────────┐
                    │   MÁQUINA EM AUTOMÁTICO?    │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │              NÃO            │
                    │         → MANUTENCAO        │
                    └─────────────────────────────┘
                                   │
                                  SIM
                                   ▼
                    ┌─────────────────────────────┐
                    │     EXISTE ALARME ATIVO?    │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │              SIM            │
                    │           → FAULT           │
                    └─────────────────────────────┘
                                   │
                                  NÃO
                                   ▼
                    ┌─────────────────────────────┐
                    │    MOTOR PRINCIPAL LIGADO?  │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │              SIM            │
                    │           → RUN             │
                    │   (ou verificar sub-estados)│
                    └─────────────────────────────┘
                                   │
                                  NÃO
                                   ▼
            ┌───────────────────────────────────────────┐
            │         QUAL O MOTIVO DA PARADA?          │
            └─────────────────────┬─────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────┐
        │                         │                     │
        ▼                         ▼                     ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│ Sensor entrada│       │ Sensor saída  │       │ Comando troca │
│ sem peça há   │       │ cheio há      │       │ de SKU ativo? │
│ X segundos?   │       │ X segundos?   │       │               │
└───────┬───────┘       └───────┬───────┘       └───────┬───────┘
        │                       │                       │
       SIM                     SIM                     SIM
        │                       │                       │
        ▼                       ▼                       ▼
   WAIT_PREV               BLOCK_NEXT                SETUP
```

### 3.2 Pseudo-código Ladder/ST

```pascal
// ============================================================
// BLOCO FB_ESTADO_EQUIPAMENTO
// ============================================================

// Entradas
VAR_INPUT
    bAutoMode       : BOOL;     // Máquina em modo automático
    bMotorRunning   : BOOL;     // Motor principal ligado
    bAlarmActive    : BOOL;     // Qualquer alarme ativo
    bEntradaSensor  : BOOL;     // Sensor de presença na entrada
    bSaidaSensor    : BOOL;     // Sensor de presença na saída
    bSetupMode      : BOOL;     // Comando de troca de SKU
    bMaintRequest   : BOOL;     // Solicitação de manutenção
    tWaitTimeout    : TIME := T#5S;  // Tempo para detectar espera
END_VAR

// Saída
VAR_OUTPUT
    sEstado         : STRING;   // Estado atual ('RUN', 'FAULT', etc)
    nEstadoCodigo   : INT;      // Código numérico do estado
END_VAR

// Variáveis internas
VAR
    tonWaitPrev     : TON;      // Timer para WAIT_PREV
    tonBlockNext    : TON;      // Timer para BLOCK_NEXT
END_VAR

// ============================================================
// LÓGICA PRINCIPAL
// ============================================================

// 1. Verifica modo automático
IF NOT bAutoMode THEN
    sEstado := 'MANUTENCAO';
    nEstadoCodigo := 10;
    RETURN;
END_IF

// 2. Verifica alarmes
IF bAlarmActive THEN
    sEstado := 'FAULT';
    nEstadoCodigo := 6;
    RETURN;
END_IF

// 3. Verifica setup
IF bSetupMode THEN
    sEstado := 'SETUP';
    nEstadoCodigo := 7;
    RETURN;
END_IF

// 4. Verifica se está produzindo
IF bMotorRunning THEN
    sEstado := 'RUN';
    nEstadoCodigo := 1;
    RETURN;
END_IF

// 5. Motor parado - determinar motivo
// Timer para aguardando anterior (entrada vazia)
tonWaitPrev(IN := NOT bEntradaSensor, PT := tWaitTimeout);
IF tonWaitPrev.Q THEN
    sEstado := 'WAIT_PREV';
    nEstadoCodigo := 4;
    RETURN;
END_IF

// Timer para bloqueio posterior (saída cheia)
tonBlockNext(IN := bSaidaSensor, PT := tWaitTimeout);
IF tonBlockNext.Q THEN
    sEstado := 'BLOCK_NEXT';
    nEstadoCodigo := 5;
    RETURN;
END_IF

// Solicitação de manutenção
IF bMaintRequest THEN
    sEstado := 'AGUARD_MNT';
    nEstadoCodigo := 9;
    RETURN;
END_IF

// Estado não identificado
sEstado := 'OUTRO';
nEstadoCodigo := 12;
```

---

## 4. Contagem de Produção

### 4.1 Princípios

| Tipo | Descrição | Onde Contar |
|------|-----------|-------------|
| **Contador de Entrada** | Peças que ENTRAM no equipamento | Sensor de entrada (borda de subida) |
| **Contador de Saída** | Peças que SAEM do equipamento | Sensor de saída (borda de subida) |
| **Contador de Rejeitos** | Peças rejeitadas | Sensor de rejeito ou comando de descarte |

### 4.2 Lógica de Contagem

```pascal
// ============================================================
// BLOCO FB_CONTADOR_PRODUCAO
// ============================================================

VAR_INPUT
    bSensorEntrada   : BOOL;    // Sensor de entrada de peça
    bSensorSaida     : BOOL;    // Sensor de saída de peça
    bSensorRejeito   : BOOL;    // Sensor de rejeito
    bReset           : BOOL;    // Reset dos contadores
END_VAR

VAR_OUTPUT
    nContEntrada     : UDINT;   // Total de peças entrada
    nContSaida       : UDINT;   // Total de peças saída (produção boa)
    nContRejeito     : UDINT;   // Total de rejeitos
    nContCiclo       : UDINT;   // Ciclos da máquina
END_VAR

VAR
    rTrigEntrada     : R_TRIG;  // Borda de subida entrada
    rTrigSaida       : R_TRIG;  // Borda de subida saída
    rTrigRejeito     : R_TRIG;  // Borda de subida rejeito
END_VAR

// ============================================================
// LÓGICA
// ============================================================

// Reset
IF bReset THEN
    nContEntrada := 0;
    nContSaida := 0;
    nContRejeito := 0;
    nContCiclo := 0;
END_IF

// Contagem na borda de subida (transição 0→1)
rTrigEntrada(CLK := bSensorEntrada);
IF rTrigEntrada.Q THEN
    nContEntrada := nContEntrada + 1;
END_IF

rTrigSaida(CLK := bSensorSaida);
IF rTrigSaida.Q THEN
    nContSaida := nContSaida + 1;
    nContCiclo := nContCiclo + 1;  // Ciclo = produção
END_IF

rTrigRejeito(CLK := bSensorRejeito);
IF rTrigRejeito.Q THEN
    nContRejeito := nContRejeito + 1;
END_IF
```

### 4.3 Tipos de Contagem por Equipamento

| Equipamento | O que Contar | Sensor Típico |
|-------------|--------------|---------------|
| **Enchedora** | Garrafas cheias | Sensor após enchimento |
| **Paletizador** | Caixas empilhadas | Contagem no robô/garra |
| **Balança** | Peças pesadas (boas + rejeitos) | Pulso de fim de pesagem |
| **Encaixotadora** | Caixas fechadas | Sensor de saída |
| **Envolvedora** | Paletes envoltos | Fim de ciclo de envoltura |
| **Rotuladora** | Produtos rotulados | Sensor após aplicação |

---

## 5. Tags OPC UA para Comunicação

### 5.1 Estrutura de Tags

Convenção de nomenclatura: `LINHA.EQUIPAMENTO.VARIAVEL`

```
Exemplo: L10.ENCHEDORA_01.Estado
         L10.ENCHEDORA_01.ContadorSaida
         L10.ENCHEDORA_01.Velocidade
```

### 5.2 Tags Obrigatórias por Equipamento

| Tag | Tipo | Descrição |
|-----|------|-----------|
| `Estado` | STRING ou INT | Estado atual do equipamento |
| `ContadorEntrada` | UDINT | Contador acumulado de entrada |
| `ContadorSaida` | UDINT | Contador acumulado de saída (produção) |
| `ContadorRejeito` | UDINT | Contador de rejeitos |
| `Velocidade` | REAL | Velocidade atual (unid/min) |
| `AlarmActive` | BOOL | Flag de alarme ativo |
| `AutoMode` | BOOL | Modo automático ativo |

### 5.3 Tags Opcionais (Recomendadas)

| Tag | Tipo | Descrição |
|-----|------|-----------|
| `VelocidadeSetpoint` | REAL | Velocidade programada |
| `TempoParada` | TIME | Tempo acumulado parado |
| `UltimoAlarme` | STRING | Descrição do último alarme |
| `Temperatura` | REAL | Temperatura (se aplicável) |
| `Pressao` | REAL | Pressão (se aplicável) |

---

## 6. Regras de Prioridade de Estados

Quando múltiplas condições ocorrem simultaneamente, usar esta ordem de prioridade:

1. **FAULT** (Alarme sempre tem prioridade máxima)
2. **MANUTENCAO** (Modo manual/manutenção)
3. **SETUP** (Troca de SKU em andamento)
4. **AGUARD_MNT** (Aguardando técnico)
5. **FALTA_MAT** (Sem material)
6. **WAIT_PREV** (Aguardando anterior)
7. **BLOCK_NEXT** (Bloqueado posterior)
8. **PARANDO** (Encerrando ciclo)
9. **PARTINDO** (Iniciando ciclo)
10. **RUN** (Produzindo)
11. **OUTRO** (Não classificado)

---

## 7. Temporização

### 7.1 Tempos Recomendados

| Parâmetro | Valor Sugerido | Descrição |
|-----------|----------------|-----------|
| Timeout WAIT_PREV | 5s | Tempo sem peça na entrada para considerar "aguardando" |
| Timeout BLOCK_NEXT | 5s | Tempo com saída cheia para considerar "bloqueado" |
| Debounce sensores | 50-100ms | Filtro de ruído em sensores |
| Ciclo de scan OPC | 1-2s | Frequência de envio para MIS-Core |

### 7.2 Evitar Oscilações

```pascal
// Usar histerese para evitar mudanças rápidas de estado
IF novoEstado <> estadoAnterior THEN
    tonHisterese(IN := TRUE, PT := T#2S);
    IF tonHisterese.Q THEN
        sEstadoFinal := novoEstado;
        estadoAnterior := novoEstado;
        tonHisterese(IN := FALSE);
    END_IF
END_IF
```

---

## 8. Exemplo Completo: Linha de Envase

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  DESPALETE- │───▶│  ENCHEDORA  │───▶│ ROTULADORA  │───▶│ ENCAIXOTA-  │
│   IZADOR    │    │             │    │             │    │   DORA      │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      │                  │                  │                  │
      ▼                  ▼                  ▼                  ▼
   Estado             Estado             Estado             Estado
   Contador           Contador           Contador           Contador
```

### Estados Típicos na Cadeia:

| Situação | Despaletizador | Enchedora | Rotuladora | Encaixotadora |
|----------|---------------|-----------|------------|---------------|
| Tudo OK | RUN | RUN | RUN | RUN |
| Enchedora em falha | BLOCK_NEXT | FAULT | WAIT_PREV | WAIT_PREV |
| Sem garrafas entrada | FAULT/FALTA_MAT | WAIT_PREV | WAIT_PREV | WAIT_PREV |
| Palete cheio no final | BLOCK_NEXT | BLOCK_NEXT | BLOCK_NEXT | BLOCK_NEXT |
| Troca de SKU | SETUP | SETUP | SETUP | SETUP |

---

## 9. Checklist de Implementação

### Para cada equipamento:

- [ ] Criar bloco FB_ESTADO com lógica de decisão
- [ ] Criar bloco FB_CONTADOR com contagem por borda
- [ ] Configurar tags OPC UA conforme padrão
- [ ] Testar transições de estado em campo
- [ ] Validar contagem com produção física
- [ ] Ajustar tempos de timeout conforme processo

### Validação:

- [ ] Estado RUN coincide com máquina rodando
- [ ] WAIT_PREV ativa quando entrada vazia por >5s
- [ ] BLOCK_NEXT ativa quando saída cheia por >5s
- [ ] FAULT ativa com qualquer alarme
- [ ] Contador incrementa 1 a cada peça (sem duplicação)
- [ ] Reset de contador funciona corretamente

---

## 10. Contato e Suporte

Para dúvidas sobre a integração:
- **Sistema**: MIS-Core
- **Versão**: v1.x
- **Documentação atualizada em**: Janeiro/2026

---

> **Nota**: Este documento deve ser adaptado conforme particularidades de cada equipamento e processo. Os tempos e lógicas apresentados são referências que podem necessitar ajustes em campo.
