# Identidade global de Equipamentos — padrão ISA-95 / MES

> Este documento descreve a **arquitetura de identidade** dos equipamentos no
> MIS Core, implementada como Solução 2 após o problema "E001 em qual linha?"
> aparecer no deploy OT com 20+ linhas.

## Resumo executivo

Antes da Solução 2, um equipamento era identificado apenas pelo `codigo`
(ex.: `E001`), único **dentro da linha** mas não global. Em fábricas com
múltiplas linhas o mesmo `E001` existia em todas elas — coletor e endpoints
ficavam sem como desambiguar (HTTP 409 ou pior: ponto Influx escrito na
linha errada).

A Solução 2 adiciona **identidade tripla** a cada equipamento, padrão da
indústria MES (Wonderware/AVEVA, Ignition, FactoryTalk):

| Identificador | Tipo | Mutável? | Para quê? |
|---|---|---|---|
| `id` | int (PK) | — | Joins internos Django |
| `uuid` | UUIDv4 | Não | Integrações externas (ERP, MQTT, IIoT) — sobrevive a qualquer renomeação |
| `slug` | string `"L01.E001"` | Não (após primeiro save) | API, InfluxDB, logs, URLs profundas |
| `codigo` | string `"E001"` | Sim | UI compacta, único só por linha |

**O slug é congelado no primeiro save.** Renomear uma linha NÃO altera os
slugs dos equipamentos dela. Esse desacoplamento é o que permite que
integrações (Node-RED flows, Golden State snapshots, históricos Influx)
continuem funcionando depois de qualquer alteração de cadastro.

## Onde cada identificador aparece

```
                              ┌─────────────────────────────────────┐
                              │     Equipamento(id, uuid, slug,     │
                              │             codigo, linha, nome)    │
                              └──────────────┬──────────────────────┘
                                             │
        ┌──────────────────────┬─────────────┼──────────────┬────────────────┐
        ▼                      ▼             ▼              ▼                ▼
   InfluxDB tags         Coletor OPC      API REST        Admin           Frontend
   equipment_slug    equipamento_slug   resolver_de_     codigo + chip   slug em chip
   equipment (legacy)  (preferido)      payload(...)    "slug" colapsável  + URLs
   line               +linha_codigo
                      (fallback)
```

## Como o backend resolve um equipamento

Toda chamada que precisa identificar um equipamento usa o
`equipamentos.resolvers.resolver_equipamento(...)`. Ordem de precisão:

1. `equipamento_id` (PK) — exato, mais rápido
2. `equipamento_uuid` — exato, para integrações
3. `equipamento_slug` — exato, **preferido em todas as APIs novas**
4. `(equipamento_codigo, linha_codigo)` — desambiguação humana explícita
5. `equipamento_codigo` sozinho — só funciona em base **sem duplicação**

Se 5 retornar múltiplos candidatos, o resolver lança `EquipamentoAmbiguo`,
que o endpoint converte em HTTP 409 com a **lista de opções** no body —
o cliente sabe exatamente o que escolher.

### Exemplo de erro 409 estruturado

```json
{
  "status": "ambiguous",
  "codigo": "E001",
  "opcoes": [
    {"id": 1, "slug": "L01.E001", "codigo": "E001",
     "linha_codigo": "L01", "linha_nome": "Linha 01", "nome": "ACMA"},
    {"id": 4, "slug": "L02.E001", "codigo": "E001",
     "linha_codigo": "L02", "linha_nome": "Linha 02", "nome": "Tampadora"}
  ],
  "hint": "Inclua `equipamento_slug` (preferido), `linha_codigo` ou `equipamento_id` no payload para desambiguar."
}
```

## Tags no InfluxDB — dual-write

A partir da Onda 3 da Solução 2, **toda escrita** do coletor inclui as duas
tags em paralelo:

```python
tags = {
    'factory': 'F001',
    'area': 'A001',
    'line': 'L01',
    'equipment': 'E001',          # legacy — para retrocompatibilidade
    'equipment_slug': 'L01.E001', # canônica — para queries novas
    ...
}
```

Queries que querem ser à prova de ambiguidade usam o helper
`equipment_where_clause(equipamento)`:

```python
from .influx_helpers import equipment_where_clause

query = f"""
    SELECT last(velocidade_atual) FROM production
    WHERE {equipment_where_clause(eq)} AND time > now() - 5m
"""
# Expande para:
# WHERE ("equipment_slug" = 'L01.E001'
#        OR ("equipment" = 'E001' AND "line" = 'L01'))
```

`factory` e `area` preservam o agrupamento hierárquico para consultas
multiárea/multifábrica novas; `line`, `equipment` e `equipment_slug`
continuam sendo a identidade operacional da série. O fallback com `OR`
cobre **pontos históricos** escritos antes da migração — eles têm
`equipment` e `line` mas não `equipment_slug`.

## Healthcheck

Endpoint `GET /api/health/equipamentos/` retorna diagnóstico completo:

```json
{
  "status": "ok",
  "total_equipamentos": 20,
  "sem_slug": 0,
  "sem_uuid": 0,
  "codigos_duplicados": [
    {"codigo": "E001", "n_ocorrencias": 2, "equipamentos": [...]}
  ],
  "sem_coleta_recente": [],
  "pontos_legacy_influx": 1234,
  "recomendacoes": ["Identidade global de equipamentos OK."]
}
```

Use este endpoint:

- **Após o `import-images.sh`** no servidor OT, antes do go-live.
- **Em smoke tests** de release.
- **Em monitoramento** contínuo (Prometheus exporter via blackbox-style).

## Checklist de deploy OT

1. `bash mis-core-offline/import-images.sh` — carrega imagens.
2. `docker compose up -d` — sobe stack.
3. `docker exec mis-core-django python manage.py migrate` — aplica
   migrations (a `0041_slug_uuid_equipamento` popula slug+uuid).
4. `curl http://localhost:8080/api/health/equipamentos/` — deve retornar
   `status: ok`.
5. Após 5 min de coletor rodando, repete o health — `sem_coleta_recente`
   deve estar vazia, `pontos_legacy_influx` deve estar caindo.

## Migrar equipamento de linha (raro)

Se você **precisar** mover um equipamento físico de uma linha para outra:

```python
# Não faça apenas eq.linha = nova_linha; eq.save()
# Isso quebraria o slug (que ficaria L01.E001 num equipamento agora em L02).
# Faça via management command que registra o evento:

# TODO (backlog): equipamentos/management/commands/migrar_equipamento.py
# - cria registro de auditoria
# - atualiza Equipamento.linha
# - emite snapshot do estado anterior
# - mantém slug imutável (apontando para a linha histórica)
```

**Por enquanto, a recomendação é não fazer**. Crie um equipamento novo na
linha destino e arquive o antigo (status=INATIVO). A história fica
preservada e o novo equipamento ganha um slug novo.

## Como código consumidor deve identificar um equipamento

### ❌ Errado (legacy, suscetível a ambiguidade)

```python
eq = Equipamento.objects.filter(codigo='E001').first()
```

### ✅ Certo (slug, exato)

```python
eq = Equipamento.objects.get(slug='L01.E001')
```

### ✅ Certo (resolver, qualquer combo)

```python
from equipamentos.resolvers import resolver_de_payload, EquipamentoAmbiguo
try:
    eq = resolver_de_payload(request.data)
except EquipamentoAmbiguo as exc:
    return Response({'status': 'ambiguous', 'opcoes': exc.opcoes}, status=409)
```

## Mudanças por componente — referência

| Componente | Mudança | Arquivo |
|---|---|---|
| Model | +slug, +uuid, geração no save | `equipamentos/models.py` |
| Migration | 0041 popula slug/uuid existentes | `equipamentos/migrations/0041_slug_uuid_equipamento.py` |
| Resolver central | módulo novo | `equipamentos/resolvers.py` |
| Serializers | aceita slug/uuid/id/codigo+linha | `equipamentos/serializers.py` |
| Endpoint eventos_estado | usa resolver | `equipamentos/views.py` |
| Endpoint dados/inserir | usa resolver + dual-write Influx | `equipamentos/flask_replacement_views.py` |
| Coletor | propaga slug e linha_codigo | `coletor/coletor.py` |
| Queries Influx | `equipment_where_clause(eq)` | `equipamentos/influx_helpers.py` (helper) |
| Admin | mostra slug/uuid em fieldset Identidade | `equipamentos/admin.py` |
| Frontend | exibe slug em chip no card | `frontend-react/.../EquipamentoCard.tsx` |
| Healthcheck | `/api/health/equipamentos/` | `equipamentos/identity_health_views.py` |

---

**Pergunta frequente**: "por que slug e não UUID em tudo?"

Slug é **humano-amigável** (`L01.E001` aparece em log e o operador entende),
**estável** (não muda após o primeiro save) e **único globalmente** — atende
99% dos casos. UUID fica reservado para integrações onde renomeação de
equipamento DEVE ser tolerada (ex.: ERP que cadastra uma vez e nunca mais
quer mudar o ID). Para o dia a dia industrial, slug é melhor.
