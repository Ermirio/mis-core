---
trigger: always_on
---

Regras obrigatórias do Agente Antigravity (DoD – ponta a ponta)
1) Regra de rastreio de fluxo (sempre)

Antes de entregar qualquer tarefa, o agente DEVE mapear o caminho completo dos dados envolvidos:

Tags/OPC (origem)

Coletor OPC (ingestão / parsing / normalização)

Banco(s) (onde persiste: InfluxDB/MySQL etc.)

API (rotas, serializers, services, permissões)

Frontend (tela/endpoint consumido, renderização, estado)

Se o agente não conseguir listar esse caminho, ele NÃO pode considerar a tarefa concluída.

2) Regra de inspeção de rotas de API (sempre)

Para qualquer feature/bugfix que toque dados, o agente DEVE:

Identificar as rotas de API envolvidas (GET/POST/PUT/DELETE)

Conferir contrato: payload, query params, status codes, paginação, filtros

Verificar autenticação/permite (se existe)

Validar erros: 400/401/403/404/500 com mensagens coerentes

3) Regra de validação de bancos (sempre)

O agente DEVE:

Identificar quais tabelas/medidas/retentions são afetadas

Confirmar que o dado está chegando e está com timestamp/unidade corretos

Garantir integridade:

MySQL: chaves, constraints, migrations, índices se necessário

InfluxDB: measurement, tags vs fields, cardinalidade, retention policy

4) Regra do coletor OPC (quando houver OPC no fluxo)

Se houver OPC/PLC no fluxo, o agente DEVE:

Confirmar quais tags OPC são lidas e com que frequência

Validar transformação: tipo (bool/int/float/string), escala, unidade, arredondamento

Conferir comportamento em falha: reconexão, timeouts, fila/buffer, logs

Garantir que o coletor não derruba o sistema quando OPC fica indisponível

5) Regra de prova no Frontend (sempre)

O agente DEVE acessar o frontend e validar visualmente/funcionalmente:

Tela(s) carregam sem erro no console

O frontend chama a rota correta

O dado exibido corresponde ao que está no banco (amostra comparada)

Estados: loading, vazio (no data), erro, retry

Se não houver como acessar UI, o agente deve ao menos simular as chamadas do frontend (ex: curl/Postman) e provar resposta.

6) Regra de teste ponta-a-ponta (sempre)

Para declarar “feito”, o agente DEVE apresentar evidências de pelo menos 1 caso:

“Inseri/observei tag X no OPC → apareceu no banco → API retornou → UI exibiu”.

E deve registrar no resultado final:

Rotas testadas

Queries executadas no banco

Prints/trechos de logs relevantes (curtos)

O que foi verificado na UI

7) Regra de não quebrar (guardrails)

O agente NÃO pode:

Alterar nomes/paths de rotas existentes sem manter compatibilidade

Mudar schema/tipos de dados sem migration e fallback

Introduzir campos/tag no Influx que aumentem cardinalidade sem justificativa

Fazer “fix” no frontend mascarando erro de backend (ex: fallback silencioso)

8) Regra de “pronto de verdade”

Só está concluído quando:

Dados percorrem o fluxo completo

API responde conforme contrato

UI mostra o dado corretamente

Logs não mostram erros relevantes

Não há regressão nas rotas e telas relacionadas