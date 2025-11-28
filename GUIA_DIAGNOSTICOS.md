# Guia de Diagnósticos e Logs - MIS-Core

## 📍 Acessar a Tela de Diagnósticos

Abra seu navegador e acesse:
```
http://localhost:5173/diagnosticos
```

---

## 🔍 O que a Tela Mostra

### 1. **Status dos Equipamentos**

A tela mostra cada equipamento com seu status:

- **🟢 ONLINE** - Equipamento está enviando dados em tempo real
- **🟡 OFFLINE** - Equipamento está configurado mas não enviando dados
- **🔴 ERRO** - Equipamento não está respondendo

### 2. **Campos Presentes vs Campos Faltando**

Para cada equipamento, você verá:

**✅ Campos Presentes** - Dados que estão chegando corretamente do CLP
```
- contagem_entrada
- contagem_saida
- velocidade_atual
- estado_maquina
- temperatura
- pressao
```

**❌ Campos Faltando** - Dados que deveriam vir mas não estão chegando
```
- sku_codigo (SKU não está sendo coletado)
- descricao (Descrição do produto não está sendo coletada)
- oee (OEE não está sendo calculado)
- ordem_producao (Ordem de Produção não está sendo coletada)
```

### 3. **Erros Específicos**

A tela identifica automaticamente problemas como:

```
❌ Flask não está respondendo
   → Solução: Verifique se Flask está rodando em http://127.0.0.1:5000

❌ Django não está respondendo
   → Solução: Verifique se Django está rodando em http://127.0.0.1:8000

⚠️ SKU não está sendo coletado
   → Solução: Configure a tag de SKU no Django Admin

⚠️ OEE não está sendo calculado
   → Solução: Verifique se métricas estão sendo consolidadas no Django

⚠️ Ordem de Produção não está sendo coletada
   → Solução: Verifique o NodeID no OPC
```

---

## 🔧 Como Usar para Diagnosticar Problemas

### Problema: SKU não aparece na tela Home

**Passo 1:** Acesse http://localhost:5173/diagnosticos

**Passo 2:** Procure pelo equipamento na lista

**Passo 3:** Clique no equipamento para expandir

**Passo 4:** Procure por "sku_codigo" em "Campos Faltando"

**Passo 5:** Se estiver faltando:
- Verifique se a tag de SKU está configurada no Django Admin
- Verifique se o NodeID do OPC está correto
- Verifique se o coletor está rodando

---

## 📊 Entender o Fluxo de Dados

A tela mostra o fluxo esperado:

```
1. CLP → 2. OPC UA → 3. Coletor → 4. Flask → 5. InfluxDB → 6. Django → 7. React
```

Se um equipamento está "OFFLINE", o problema está em uma das etapas acima.

---

## 💡 Dicas

1. **Auto-refresh:** Marque a opção "Auto-atualizar a cada 10 segundos"
2. **Filtros:** Use os botões para ver apenas equipamentos "ONLINE" ou "ERRO"
3. **Expandir:** Clique em um equipamento para ver detalhes
4. **Exportar:** Exporte os logs para documentação

---

**Versão:** 1.0  
**Data:** 28 de Novembro de 2025
