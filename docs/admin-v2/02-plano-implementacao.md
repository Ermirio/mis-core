# Plano de Implementação — Admin Backend MIS Core (v2)

> **Para:** Claude agent rodando dentro do VS Code (workspace `mis-core-stand-alone`).
> **De:** Análise feita no Cowork desktop.
> **Objetivo:** Reescrever o front-end do `/admin` do Django para que ele use a mesma identidade visual ISA-101 do `frontend-react`, mantendo um diferenciador sutil (faixa accent + wordmark "Backend") sem reescrever nenhuma `ModelAdmin`.
> **Princípio raiz:** **NÃO mexer em models nem em ModelAdmin.** Toda a customização vai por `templates/admin/*` + `static/admin/*`. Se uma feature pedir mais que isso, parar e perguntar.

---

## 1. Diagnóstico do estado atual

### 1.1 Frontend (referência visual)

A identidade está consolidada em `frontend-react/client/src/styles/isa101.css` e nos componentes `SidebarV2.css` / `MainLayout.css`. Tokens-chave:

| Token | Valor |
|---|---|
| `--isa-bg` | `#f4f5f7` |
| `--isa-bg-panel` | `#ffffff` |
| `--isa-border` | `#d7dbe0` |
| `--isa-text` | `#2c3138` |
| `--isa-text-muted` | `#657384` |
| `--isa-accent` | `#3f5b7c` (azul-acinzentado) |
| `--isa-accent-soft` | `#eaf0f7` |
| `--isa-ok` / `--isa-warn` / `--isa-bad` | `#2d8659` / `#c9932d` / `#b53a2b` |
| `--isa-radius` | `6px` |
| `--isa-fs-default` | `13px` |

Filosofia ISA 101.01: **cor saturada só em desvio**. Cinza domina, badges semânticas têm fundo claro.

### 1.2 Admin atual (Django default)

`backend-django/config/settings.py` — `INSTALLED_APPS` tem **apenas** `django.contrib.admin`. Nenhum tema (jazzmin, grappelli, unfold). Sem `templates/admin/` e sem `static/admin/`. A "tentativa de admin customizado" se resume a:

1. `admin.site.site_header / site_title / index_title` em `equipamentos/admin.py`.
2. Funções `*_badge` que retornam `format_html('<span style="color: green;">…')` com cores inline → desorganizado, não responde a tema.

### 1.3 Modelos registrados (escopo do redesign)

App `equipamentos`:

`Fabrica`, `Area`, `Produto`, `HistoricoSKU`, `LinhaProducao`, `ConexaoOPC`, `Equipamento` (com inlines `TagColeta` e `Sensor`), `TagColeta`, `Sensor`, `TurnoProducao`, `CalendarioProducao`, `EventoEstadoEquipamento`, `MetricaProducao`, `Defeito`, `OrdemProducao`, `RegistroProducaoTurno`, `EventoParada`, `StrategicInitiative`.

App `analytics`: `AnalyticsProfile`.

Vários usam `ImportExportModelAdmin` (`django-import-export`) — o template precisa preservar o botão **Import / Export**.

---

## 2. Estratégia: "skin" via override de templates + CSS

### 2.1 Por que não usar Jazzmin/Unfold

Considerei pacotes prontos. Descartei pelos seguintes motivos:

| Pacote | Veredito |
|---|---|
| Jazzmin | Bootstrap 4, AdminLTE — destoa do ISA-101 do frontend, traria componentes que não combinam. |
| Django Unfold | Tailwind embutido, mais moderno, mas força um design system próprio que não casa com o nosso. |
| Grappelli | Visual datado, não vale o trabalho de retirar depois. |

**Decisão:** sobrescrever **apenas o que precisa** no admin nativo. O Django admin já é funcional; o problema é só visual + UX. Isso mantém o código limpo, evita lock-in e aproveita 100% do que `ModelAdmin` já entrega.

### 2.2 Pirâmide de override

1. **CSS:** um único `admin/css/admin-mis.css` com tokens ISA-101 e overrides direcionados (sidebar, lista, form, fieldsets).
2. **Templates parciais:** `base_site.html`, `base.html`, `index.html`, `app_index.html`, `change_list.html`, `change_form.html`, `login.html`. Apenas para reposicionar blocos e injetar wrappers.
3. **JS:** mínimo — atalho `/` para focar busca, navegação por teclado nas linhas, atalho `Ctrl+S` para Salvar.

Nenhum override de `templates/admin/<app>/*` por enquanto. A regra: se três telas pedem o mesmo ajuste, sobe pra base; se é exclusivo de um modelo, fica em `<app>/admin.py` via `Media`.

---

## 3. Estrutura de arquivos a criar

```
backend-django/
├── admin_mis/                        ← novo app só para o tema
│   ├── __init__.py
│   ├── apps.py                       ← AppConfig (label='admin_mis')
│   ├── templates/
│   │   └── admin/
│   │       ├── base.html             ← override do "shell"
│   │       ├── base_site.html        ← header + topbar + sidebar
│   │       ├── index.html            ← dashboard (apps + KPIs)
│   │       ├── app_index.html        ← visão por app
│   │       ├── change_list.html      ← lista
│   │       ├── change_form.html      ← formulário + inlines
│   │       ├── delete_confirmation.html
│   │       ├── login.html            ← tela de login
│   │       └── includes/
│   │           ├── sidebar.html      ← partial reutilizável
│   │           ├── topbar.html
│   │           └── breadcrumbs.html
│   └── static/
│       └── admin/
│           ├── css/
│           │   ├── admin-mis.css     ← TODOS os overrides (~700 linhas)
│           │   └── tokens.css        ← copiado do isa101.css com prefixo
│           ├── js/
│           │   └── admin-mis.js      ← atalhos e melhorias UX
│           └── img/
│               └── admin-logo.svg    ← marca "M Backend"
└── config/
    └── settings.py                   ← INSTALLED_APPS recebe 'admin_mis'
                                       ANTES de 'django.contrib.admin'
```

> **Regra crítica:** `admin_mis` deve aparecer **antes** de `django.contrib.admin` em `INSTALLED_APPS` para que o Django ache os templates customizados primeiro. O `whitenoise` já está no MIDDLEWARE — basta `collectstatic` em produção.

---

## 4. Roadmap em fases

### Fase 0 — Setup (estimativa: 30 min)

Tarefas:

1. Criar app `admin_mis` (`python manage.py startapp admin_mis`).
2. Atualizar `INSTALLED_APPS`:

   ```python
   INSTALLED_APPS = [
       'admin_mis',                # ← antes de django.contrib.admin
       'django.contrib.admin',
       ...
   ]
   ```

3. Criar diretórios `templates/admin/` e `static/admin/{css,js,img}/` dentro de `admin_mis/`.
4. Confirmar `APP_DIRS=True` em `TEMPLATES` (já está).
5. **Checkpoint:** rodar `python manage.py runserver` e abrir `/admin`. Tem que continuar funcionando exatamente como antes.

### Fase 1 — CSS base + login + topbar (1h30)

Arquivos a criar:

- `admin_mis/static/admin/css/tokens.css`
- `admin_mis/static/admin/css/admin-mis.css`
- `admin_mis/templates/admin/base.html`
- `admin_mis/templates/admin/base_site.html`
- `admin_mis/templates/admin/login.html`

`tokens.css` é cópia direta dos tokens do `isa101.css` do frontend, mantendo o prefixo `--isa-*`. **Nada de duplicar valores hex no admin-mis.css** — sempre `var(--isa-*)`.

`admin-mis.css` faz três coisas:

1. Reseta o stylesheet padrão do admin (`#header`, `#container`, `.module`, `.button`, `.object-tools`).
2. Re-pinta com tokens ISA.
3. Adiciona componentes novos (`.kpi`, `.app-card`, `.tag`).

`base.html` deve estender o de fato:

```django
{% extends "admin/base.html" %}
```
…e injetar a `<link rel="stylesheet" href="{% static 'admin/css/admin-mis.css' %}">` no bloco `extrastyle`. **Não** copiar o template todo — só estender e ampliar blocos.

**Diferenciador "Admin":**
- Faixa de 4px no topo: `linear-gradient(90deg, #2d4661, #3f5b7c, #eaf0f7)`.
- Pill `BACKEND` no topbar (font-weight 700, background `#2d4661`, color `#fff`).
- Sidebar mantém quase o mesmo visual do frontend para o usuário "se sentir em casa".

**Checkpoint:** abrir `/admin/login/` e ver a tela do POC. Logar. Conferir o topbar e o body sem erros de console.

### Fase 2 — Dashboard customizado (`index.html`) (1h)

Substituir o índice pré-formatado do Django por um layout em duas seções:

1. **KPI strip** (4 cards): linhas ativas, equipamentos em RUN, conexões OPC saudáveis, cadastros pendentes.
   - Por enquanto, valores **hardcoded** ou via `{% with %}` simples. **Não** consultar `MetricaProducao` aqui (custaria latência no admin/index, usar Flask em fase futura).
2. **Grid de "app cards"** equivalente ao `available_apps` do contexto do admin, mas reagrupado em 4 buckets fixos:
   - Hierarquia (Fabrica, Area, Produto, HistoricoSKU)
   - Equipamentos (LinhaProducao, Equipamento, TagColeta, Sensor, ConexaoOPC)
   - Operação (TurnoProducao, Calendario, EventoEstado, EventoParada, OrdemProducao, RegistroProducaoTurno)
   - Analytics (MetricaProducao, Defeito, StrategicInitiative, AnalyticsProfile)

A função de mapeamento pode ficar num `templatetag` simples em `admin_mis/templatetags/admin_mis.py`:

```python
APP_GROUPS = {
    'Hierarquia': ['fabrica', 'area', 'produto', 'historicosku'],
    'Equipamentos': ['linhaproducao', 'equipamento', 'tagcoleta', 'sensor', 'conexaoopc'],
    'Operação': ['turnoproducao', 'calendarioproducao', 'eventoestadoequipamento', 'eventoparada', 'ordemproducao', 'registroproducaoturno'],
    'Analytics': ['metricaproducao', 'defeito', 'strategicinitiative', 'analyticsprofile'],
}

@register.simple_tag(takes_context=True)
def grouped_apps(context):
    available = context['available_apps']
    # ...remapeia em buckets, fallback "Outros" para o que não bater.
```

**Checkpoint:** dashboard renderiza, contadores estão certos (`Model.objects.count()`), todos os models registrados aparecem em algum bucket.

### Fase 3 — Sidebar persistente (1h)

Hoje o admin do Django **não tem sidebar fixa**. Vamos adicionar via `base_site.html` reaproveitando o partial `includes/sidebar.html`. Estrutura:

```html
<aside class="sb">
  <div class="sb__header">…logo + wordmark BACKEND…</div>
  {% grouped_apps as buckets %}
  {% for group in buckets %}
    <nav class="sb__group">
      <p class="sb__section-title">{{ group.label }}</p>
      {% for model in group.models %}
        <a class="sb__link {% if request.path|startswith:model.admin_url %}is-active{% endif %}"
           href="{{ model.admin_url }}">
          <span class="ico">{{ model.icon }}</span>
          {{ model.name }}
          <span class="count">{{ model.count }}</span>
        </a>
      {% endfor %}
    </nav>
  {% endfor %}
  <div class="sb__footer">…user card…</div>
</aside>
```

Pontos de atenção:

- O Django já injeta `available_apps` em todas as views do admin (via `AdminSite.each_context`).
- O `count` deve ser **lazy / cached por request** — não chamar `Model.objects.count()` em loop sem cache. Usar um middleware ou um util com `cache.get_or_set('admin_counts', ..., timeout=60)`.
- Filtro `startswith` precisa ser custom (não vem por padrão). Criar em `admin_mis/templatetags/admin_mis.py`.

**Checkpoint:** sidebar aparece em todas as páginas do admin, link ativo destacado, contadores corretos, performance ok (DevTools → request `<200ms` na home).

### Fase 4 — Changelist (1h30)

Reescrever `change_list.html` mantendo **toda a funcionalidade** do default:
- caixinhas de seleção em massa
- ações (`<select>` com action_choices + Go)
- `list_filter` (sidebar de filtros à direita)
- paginação
- search box (`search_fields`)
- import/export (quando `ImportExportModelAdmin`)

A tabela ganha o estilo `.tbl` do POC. Ações de linha (`Editar`, `Excluir`) ficam num menu por linha (botão `⋮` que abre dropdown) — **não** acrescentar ações novas, só envolver as que o Django já gera.

`list_filter` vira sidebar à direita com chips, não dropdown. Cada chip é um link com `?campo=valor` exatamente como hoje.

**Checkpoint:** mesma URL produz a mesma listagem. Filtrar, buscar, paginar, executar ação em massa, exportar XLSX — tudo deve continuar funcionando.

### Fase 5 — Change form + inlines (1h30)

`change_form.html` é o mais delicado. Manter:

- `form.is_multipart` → `enctype` correto
- `formset.management_form` para cada inline
- `errors` por campo e formset
- Botão `Save / Save and continue / Save and add another`
- `History` link
- `Delete` na cara só se `has_delete_permission`

Layout em **duas colunas** (igual POC):
- Coluna principal: `fieldsets` na ordem definida pela `ModelAdmin`. Cada `fieldset` vira `<div class="fset">`.
- Coluna lateral (somente quando o modelo tem campos `readonly_fields` significativos): "Auditoria", "Estado", etc. Decidir por modelo via context flag.

Inlines:
- `TabularInline` → mesmo template do POC: `<table class="tbl">` dentro de `inline-tbl-wrap`. Cada `<tr>` recebe um `data-formset-row` com índice. Botão `+ Adicionar tag de coleta` chama o JS empty-form padrão do Django.
- `StackedInline` → mantém um `fset` por instância empilhada (deixar para fase futura se necessário).

**Atenção:** Django gera o HTML dos inlines via JS (`inlines.js`). **Não** sobrescrever esse JS. Apenas re-estilizar via CSS. Os `tbody.empty-form` precisam continuar com a classe `empty-form` para o JS achar.

**Checkpoint:** abrir `/admin/equipamentos/equipamento/<id>/change/`, editar todos os campos, adicionar/remover inline TagColeta, salvar, verificar que persistiu no banco. Testar com erro de validação (campo obrigatório vazio).

### Fase 6 — Polimentos (1h)

1. Botões de ação no topo direito do change form (`object-tools`) — re-estilizar para `.btn`.
2. Mensagens (`messages framework`) — toast no canto superior direito em vez de barra no topo.
3. Empty states — quando uma changelist está vazia, mostrar ilustração simples + CTA "Adicionar primeiro X".
4. Dark mode — **deferred**. Tokens já estão nomeados, mas não implementar agora; criar issue.
5. Acessibilidade básica: `aria-current="page"` no link ativo da sidebar, `aria-live="polite"` nos toasts, foco visível em todos os controles.

### Fase 7 — Validação (45 min)

Checklist obrigatório antes de considerar fechado:

- [ ] Login → dashboard sem erros JS no console.
- [ ] Cada bucket da sidebar abre a changelist correta.
- [ ] `equipamentos.Equipamento` change form salva com 3 inlines de `TagColeta` editados.
- [ ] Import/export XLSX em `Equipamento` continua funcionando.
- [ ] `?ativa__exact=1` aplicado pela URL filtra a lista (filtros por URL preservados).
- [ ] Botão "View site" leva ao frontend (`/`).
- [ ] Layout responsivo a 1280×720, 1440×900, 1920×1080 — sem scroll horizontal.
- [ ] Lighthouse: Performance > 85, Accessibility > 90 numa changelist de 50 linhas.
- [ ] `python manage.py collectstatic --noinput` funciona, e o admin servido por whitenoise renderiza igual.

---

## 5. Riscos e como mitigar

| Risco | Mitigação |
|---|---|
| Override de template quebra paginação ou ações em massa | Sempre estender (`{% extends %}`) os defaults do Django, nunca copiar 100%. Quando precisar, copiar o original e marcar com comentário `<!-- @override-of: django/contrib/admin/templates/admin/change_list.html @ tag 5.0 -->`. |
| `{% load admin_list %}` exige nomes específicos no contexto | Não renomear nada do contexto, só envolver com classes CSS. |
| `import_export` injeta seu próprio botão | Re-estilizar via CSS, não tocar no template do `import_export`. Se a estilização não for suficiente, criar `admin/import_export/change_list_import_export.html` no app `admin_mis`. |
| Performance da sidebar com count em N modelos | Cache de 60s por usuário em `cache.get_or_set('admin_counts:{user_id}', ...)`. |
| Template tag `startswith` colide com algum lib | Nomear `path_starts_with` para evitar conflito. |
| User clica em "Voltar ao site" achando que vai logout | O botão linka pra `/`, não `/admin/logout/`. Logout fica no menu do user no canto inferior esquerdo. |

---

## 6. Como o agente do VSCode deve operar

### 6.1 Ordem fixa

Não pular fases. Cada fase é um commit. Mensagem padrão:
```
admin-v2(faseX): <ação curta>

Refs: docs/admin-v2/02-plano-implementacao.md §X
```

### 6.2 Antes de codar uma fase

1. Ler a seção correspondente neste documento.
2. Ler `docs/admin-v2/01-poc.html` na faixa visual da fase.
3. Confirmar se algum arquivo do passo já existe (não sobrescrever sem checar).
4. Criar/editar.
5. Rodar `python manage.py check` → sem erros.
6. Rodar o servidor e abrir o admin. Validar visualmente.
7. Commit.

### 6.3 Quando perguntar antes de fazer

- Mexer em qualquer arquivo fora de `admin_mis/`, `config/settings.py` (somente acrescentar app) e este `docs/admin-v2/`.
- Adicionar dependência nova ao `requirements.txt`.
- Mudar a estrutura de `INSTALLED_APPS` além do app novo.
- Tocar em `.agent/rules/*`.

### 6.4 Como pedir contexto adicional

Se uma classe `ModelAdmin` parecer mal estruturada para o template novo, **não** refatorar. Abrir issue / TODO e seguir. O escopo deste plano é só o front do admin.

---

## 7. Arquivos de referência

| Arquivo | Para quê |
|---|---|
| `docs/admin-v2/01-poc.html` | Aparência final esperada — abre direto no navegador. |
| `frontend-react/client/src/styles/isa101.css` | Fonte canônica dos tokens ISA-101. |
| `frontend-react/client/src/components/layout/SidebarV2.css` | Inspiração para o componente `.sb__*` do admin. |
| `backend-django/equipamentos/admin.py` | Lista oficial de `ModelAdmin` registrados. |
| `backend-django/analytics/admin.py` | Único `ModelAdmin` do app analytics. |

---

## 8. Critério de "feito"

A POC HTML representa o estado-alvo. O admin real está pronto quando, abrindo lado a lado o `01-poc.html` e `http://localhost:8000/admin/`, um observador casual confunde os dois — porém percebe pela faixa accent + pill `BACKEND` que está no admin, não no frontend operacional. Funcionalidade do Django admin: **100% preservada**.

---

**Tempo total estimado:** 7h–8h focadas. Pode ser dividido em duas sessões (Fases 0–3 = ~3h30, Fases 4–7 = ~4h).
