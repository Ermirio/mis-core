# Chat IA (LLM) — Configuração e Integração de Dados

Documento de referência para os itens 4 e 5: como configurar o endpoint do
modelo LLM e o que o serviço precisa fornecer para o modelo consultar dados
da linha.

---

## Item 4 — Como configurar o endpoint do modelo LLM

### Onde fica a configuração

A tela do **Chat IA** (`/machine-chat`) tem um botão de engrenagem (⚙️) que abre
o modal "Configurações do Chat IA". **A partir do v10.6, esse botão e o modal
só aparecem para superusuário.** Operadores não veem nem a engrenagem.

Os campos do modal:

| Campo | O que é |
|---|---|
| **Endpoint do LLM** | URL do servidor do modelo (ex.: LM Studio, Ollama, vLLM) |
| **Endpoint da API de Dados** | URL do serviço que fornece dados das linhas (Flask, porta 5002) |

### As fontes de configuração (ordem de precedência)

O valor efetivo vem de variáveis de ambiente do build do React, com fallback:

```
REACT_APP_LLAMA_ENDPOINT       → endpoint do LLM        (default: "/")
REACT_APP_LLAMA_TIMEOUT        → timeout LLM em ms       (default: 540000 = 9 min)
REACT_APP_DATA_API_ENDPOINT    → endpoint da API dados   (default: "/data-api")
REACT_APP_DATA_API_TIMEOUT     → timeout dados em ms     (default: 20000 = 20 s)
REACT_APP_AI_NAME              → nome do assistente       (default: "LIIA")
```

### Como configurar em produção (build do frontend)

No `Dockerfile` do frontend (`mis-change-over/Frontend/dockerfile`), as
`REACT_APP_*` são fixadas no momento do `npm run build`. Para apontar o LLM:

```dockerfile
# Exemplo: LM Studio rodando na máquina OT 192.168.70.160 porta 1234
ENV REACT_APP_LLAMA_ENDPOINT=http://192.168.70.160:1234/v1/chat/completions
ENV REACT_APP_DATA_API_ENDPOINT=/mis-change-over-data-api
```

> **Atenção:** como o CRA fixa `REACT_APP_*` no build, mudar o endpoint exige
> rebuild da imagem do frontend. Para mudança sem rebuild, use o modal (que
> guarda em estado/localStorage) — porém isso é por-navegador e só superuser.

### Onde o LLM normalmente roda na fábrica

| Servidor LLM | URL típica | Formato de API |
|---|---|---|
| **LM Studio** | `http://host:1234/v1/chat/completions` | OpenAI-compatible |
| **Ollama** | `http://host:11434/api/chat` | Ollama nativo |
| **vLLM** | `http://host:8000/v1/chat/completions` | OpenAI-compatible |

O `LM_STUDIO_URL` também é passado ao backend Django no compose (variável de
ambiente `LM_STUDIO_URL`) — usado por recursos server-side do chat, se houver.

### Roteamento via proxy central

Se o LLM e a API de dados ficam atrás do proxy central, configure as
`location` no `proxy-reverse/nginx.conf` (igual fizemos para o Recipe Monitor).
Hoje já existe:

```
/mis-change-over-data-api/   → API de dados (Flask :5002)
```

Para o LLM, se quiser expô-lo via proxy (em vez de IP:porta direto):

```nginx
location /mis-change-over-llm/ {
    proxy_pass http://192.168.70.160:1234/;
    proxy_read_timeout 600s;   # respostas de LLM são lentas
    proxy_set_header Host $host;
}
```

E no build do frontend: `REACT_APP_LLAMA_ENDPOINT=/mis-change-over-llm/v1/chat/completions`.

---

## Item 5 — O que o serviço deve fornecer para o modelo consultar dados da linha

O Chat IA não dá ao LLM acesso direto ao banco/CLP. Ele faz **RAG simples**:
busca dados na **API de dados** (Flask), monta um contexto textual e envia ao
LLM junto com a pergunta do operador. Logo, o serviço de dados precisa expor
endpoints REST que devolvam JSON consumível.

### Endpoints que o Chat IA já consome (observados no MachineChat.js)

O frontend monta as URLs a partir de `DATA_API_ENDPOINT`. Os padrões usados:

| Endpoint | Retorna | Quando é chamado |
|---|---|---|
| `GET /health` | status do serviço | checagem de conexão |
| `GET /routes` | rotas disponíveis | descoberta |
| `GET /analise/eficiencia` | KPIs de eficiência (todas linhas) | perguntas sobre eficiência |
| `GET /analise/qualidade` | KPIs de qualidade | perguntas sobre qualidade |
| `GET /todas_linhas/kpis` | KPIs consolidados | comparação entre linhas |
| `GET /todas_linhas/producao` | produção por linha | perguntas de produção |
| `GET /todas_linhas/variaveis` | variáveis de processo | perguntas técnicas |
| `GET /todas_linhas/qualidade` | qualidade por linha | comparativo |
| `GET /todas_linhas/contexto_completo` | tudo consolidado | análise geral / multi-tema |
| `GET /embalagem/<linha>/kpis` | KPIs de uma linha | pergunta sobre 1 linha |
| `GET /embalagem/<linha>/dados_qualidade` | qualidade da linha | idem |
| `GET /embalagem/<linha>/dados_producao` | produção da linha | idem |
| `GET /embalagem/<linha>/variaveis` | variáveis da linha | idem |
| `GET /embalagem/<linha>/contexto_completo` | contexto da linha | idem |

### Contrato mínimo de cada endpoint

Para o LLM "entender" os dados, cada endpoint deve devolver **JSON plano e
rotulado** (não códigos crus). Exemplo do que `/embalagem/L02/contexto_completo`
deveria retornar:

```json
{
  "linha": "L02",
  "timestamp": "2026-06-03T14:30:00-03:00",
  "sku_atual": "12345",
  "descricao_sku": "Produto X 800g",
  "status_linha": "produzindo",
  "kpis": {
    "oee": 78.5,
    "disponibilidade": 92.0,
    "performance": 88.0,
    "qualidade": 96.5,
    "unidade_oee": "%"
  },
  "producao": {
    "pecas_boas": 14230,
    "pecas_refugadas": 145,
    "velocidade_atual": 320,
    "velocidade_nominal": 350,
    "unidade_velocidade": "ppm"
  },
  "variaveis_processo": [
    { "nome": "Temperatura_Selagem", "valor": 185.4, "unidade": "°C", "status": "normal" },
    { "nome": "Pressao_Ar",          "valor": 5.8,   "unidade": "bar", "status": "atencao" }
  ],
  "alarmes_ativos": [
    { "codigo": "AL-102", "descricao": "Pressão de ar abaixo do setpoint", "desde": "14:12" }
  ]
}
```

### Princípios para os dados serem úteis ao LLM

1. **Rotular tudo em linguagem natural** — `"oee": 78.5` com `"unidade_oee": "%"`,
   não `"k1": 78.5`. O LLM lê os nomes dos campos.
2. **Incluir unidades** — sempre `valor` + `unidade`. Senão o modelo inventa.
3. **Incluir timestamp** — para o modelo saber se o dado é atual.
4. **Texto curto e plano** — evitar JSON aninhado profundo; o contexto enviado
   ao LLM tem limite de tokens.
5. **Status já classificado** — mandar `"status": "atencao"` pronto, não fazer
   o LLM calcular contra setpoint.
6. **Não mandar dados crus de CLP** — converter tag `DB10.DBW4` para
   `Temperatura_Selagem` antes de enviar.

### De onde esses dados podem vir

| Fonte | O que fornece | Como |
|---|---|---|
| **InfluxDB** (histórico) | KPIs, produção, séries temporais | Flask consulta InfluxDB |
| **Recipe Monitor** (`/recipe-monitor/linhas/<L>/snapshot`) | variáveis OPC em tempo real | Flask agrega ou frontend junta |
| **Django** (`/api/...`) | SKU atual, status da linha, formato | Flask consulta Django |

> O **Recipe Monitor já fornece** as variáveis de processo em tempo real
> (snapshot por linha). A API de dados do Chat IA pode reusar isso em vez de
> abrir nova conexão OPC — basta o Flask chamar
> `GET http://mis-recipe-monitor:8100/linhas/<linha>/snapshot`.

### Fluxo completo (RAG)

```
1. Operador pergunta: "Como está a eficiência da L02?"
2. MachineChat detecta o tema (eficiência) + linha (L02)
3. Chama GET {DATA_API}/embalagem/L02/contexto_completo
4. Recebe JSON com KPIs/produção/variáveis
5. Monta prompt: "Contexto: <json resumido>. Pergunta: <pergunta>"
6. Envia ao LLM (LLAMA_ENDPOINT)
7. Exibe a resposta em markdown
```

### O que falta implementar (se for evoluir o item 5)

Hoje os endpoints de dados são consumidos pelo frontend, mas a **API de dados
em si** (o Flask que serve `/embalagem/<linha>/contexto_completo` etc) é um
componente separado. Se esses endpoints ainda não existem ou estão incompletos,
o trabalho é: implementar no Flask cada rota da tabela acima, seguindo o
contrato JSON definido aqui, agregando InfluxDB + Recipe Monitor + Django.

Isso **não foi implementado** neste ciclo — esta seção é a especificação para
quando for priorizado.
