# mis-recipe-intelligent · Recipe Monitor Service

Serviço FastAPI assíncrono que monitora variáveis OPC UA em tempo real e
expõe (REST + WebSocket) o estado atual para o frontend `ReceitaMonitorContent`.

**Importante:** este serviço roda como **processo separado** do Django
(`mis-change-over`). Compartilha apenas o repositório git — não importa
nenhum código Django, não toca em `manage.py`, não roda dentro do gunicorn.
Toda comunicação com o Django é via HTTP (rotas REST autenticadas com JWT).

## Por que separado?

O `mis-change-over` já tem workers OPC em threads daemon dentro do gunicorn
(`OPCIntertravamentoWorker`, `OPCValidacaoQualidadeWorker`). Esses workers
sofrem com o problema clássico de **N workers gunicorn × M threads OPC**
(ver o workaround em `ips/services.py:77-78` — janela de 10s para evitar
duplicatas). Esse padrão não escala para leitura contínua de receitas.

Aqui usamos `asyncua` (async) + subscriptions OPC UA persistentes em um
único processo. Sem GIL competindo com requests REST, sem N conexões
duplicadas, latência sub-segundo.

## Endpoints consumidos do Django

- `GET  /api/linhas-disponiveis/` — sidebar
- `GET  /api/formatos/`           — dropdown + receita (FormatoVariavel embutido)
- `GET  /api/opc-configs/`        — URLs OPC + tags por equipamento
- `PATCH /api/recipe-monitor/formato/<id>/sincronizar/` — escrita do sincronismo

## Endpoints expostos para o frontend

- `GET  /linhas/{nome}/snapshot`     — estado atual completo (REST)
- `WS   /ws/linhas/{nome}/stream`    — push de updates em tempo real
- `POST /linhas/{nome}/sincronizar`  — proxy autenticado para o Django
- `GET  /health`                     — liveness/readiness

## Variáveis de ambiente (ver `.env.example`)

| Variável | Default | Descrição |
|---|---|---|
| `DJANGO_BASE_URL` | `http://django:8000` | URL base do Django |
| `REDIS_URL` | `redis://redis:6379/0` | URL do Redis (cache + pub/sub) |
| `OPC_CONFIG_TTL_SECONDS` | `60` | TTL do cache de `/api/opc-configs/` |
| `OPC_SUBSCRIPTION_INTERVAL_MS` | `500` | Publishing interval das subscriptions |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |

## Como rodar local

```bash
cd mis-change-over/Backend/recipe_monitor_service
cp .env.example .env  # ajuste DJANGO_BASE_URL e REDIS_URL
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8100
```

## Como rodar em Docker

```bash
docker compose up recipe-monitor
```
(ver o `docker-compose.yml` do projeto raiz; este serviço pode ser
adicionado lá como mais um service junto do `django` e `redis`.)
