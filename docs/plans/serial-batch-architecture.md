# Plano Futuro: Linhas Seriadas, Batch/Batelada e Migração Sem Flask

## Contexto

O MIS Core está bem posicionado para gestão de linhas seriadas: equipamentos em sequência, `ordem_na_linha`, contadores de entrada/saída, velocidade nominal, OEE, gargalo, timeline e produção por turno.

Para processos batch/batelada, a lógica operacional muda. Em vez de fluxo contínuo e contador por minuto, a gestão passa a depender de batelada, receita, fase, ciclo, carga, descarga, rendimento, hold, reprocesso e parâmetros por etapa.

## Direção Arquitetural

1. FastAPI deve ser a nova camada de regras operacionais.
2. Flask deve ser eliminado gradualmente.
3. Django deve ficar como cadastro/admin, autenticação e dados mestres.
4. O coletor continua lendo OPC, mas deve postar para uma API estável que não dependa do Flask no longo prazo.
5. Frontend deve adaptar a experiência pelo modo de produção da linha/equipamento.

## Classificação Proposta

Adicionar em `LinhaProducao` e, se necessário, em `Equipamento`:

- `modo_producao`: `SERIAL`, `BATCH`, `MIXED`, `UTILITY`
- `tipo_processo`: envase, mistura, cozimento, reator, tanque, processo, utilidade etc.
- `unidade_base`: `un`, `kg`, `L`, `ton`
- `usa_contador_continuo`
- `usa_eventos_fase`
- `capacidade_nominal`
- `tempo_ciclo_padrao_min`

## Entidades Batch Propostas

- `Receita`
- `ReceitaFase`
- `Batelada`
- `EventoFaseBatelada`
- `ParametroProcessoBatelada`
- `MaterialConsumido`
- `ResultadoBatelada`

## Tags Padrão Para Batch

- `batch_id`
- `recipe_id`
- `fase_atual`
- `estado_batch`
- `quantidade_carregada`
- `quantidade_produzida`
- `quantidade_aprovada`
- `quantidade_rejeitada`
- `temperatura`
- `pressao`
- `setpoint_temperatura`
- `agitacao_rpm`
- `tempo_fase`

## KPIs Seriados

- Produção por turno
- Descarte por turno
- Velocidade real vs nominal
- OEE
- Gargalo
- Timeline de estados
- Projeção de produção

## KPIs Batch

- Tempo de ciclo real vs padrão
- Tempo por fase
- Rendimento da batelada
- Quantidade carregada vs aprovada
- Perdas/reprocesso por fase
- Aderência a setpoint por fase
- Bateladas concluídas por turno
- Bateladas em hold
- Consumo real vs receita

## Frontend

Linha `SERIAL`:

- Manter cards atuais de equipamento.
- Manter timeline por equipamento.
- Manter produção, descarte, OEE, gargalo e analytics temporal.

Linha `BATCH`:

- Criar visão de batelada atual.
- Exibir receita, fase atual e progresso do ciclo.
- Mostrar timeline de fases.
- Mostrar parâmetros críticos por fase.
- Mostrar rendimento e perdas.
- Comparar bateladas por receita.

Linha `MIXED`:

- Permitir seções seriadas e batch na mesma tela.
- Exemplo: preparo batch alimentando envase seriado.

## Eliminação Gradual do Flask

Fase 1:

- Manter Flask apenas para ingestão legada.
- Criar endpoints FastAPI equivalentes para leitura operacional.
- Frontend sempre tenta FastAPI primeiro.

Fase 2:

- Migrar ingestão do coletor para FastAPI.
- FastAPI grava no Influx/Timeseries.
- Flask deixa de receber novos dados.

Fase 3:

- Migrar analytics e diagnósticos restantes.
- Remover fallback de frontend para Flask.
- Remover rotas Flask do compose.

Fase 4:

- Remover serviço Flask.
- Atualizar documentação operacional e scripts offline.

## Plano Recomendado

1. Criar `modo_producao` em linha/equipamento.
2. Expor o campo no admin, serializers e frontend.
3. Ajustar sidebar para sinalizar linhas `SERIAL`, `BATCH`, `MIXED`.
4. Criar contrato mínimo de tags batch.
5. Criar endpoints FastAPI `/api/v2/batch/*`.
6. Criar tela batch MVP.
7. Migrar ingestão do coletor para FastAPI.
8. Retirar dependências de Flask uma rota por vez.

## Decisão Técnica

Não adaptar batelada em cima do cálculo seriado. Batch deve ter domínio próprio, com entidades e métricas específicas. A camada comum deve ser apenas infraestrutura: cadastro, tags, coleta, armazenamento, estados, autenticação e navegação.
