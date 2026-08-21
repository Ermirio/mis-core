"""Template tags do admin_mis.

- grouped_apps: re-organiza ``available_apps`` em buckets fixos
  (Hierarquia, Equipamentos, Operação, Analytics).
- model_count: conta lazy de cada modelo (cache de 60s).
- path_starts_with: filtro para destacar link ativo da sidebar.
- icon_for: retorna emoji para um modelo.
"""

from __future__ import annotations

from django import template
from django.apps import apps
from django.core.cache import cache
from django.urls import NoReverseMatch, reverse

register = template.Library()


# ---------------------------------------------------------------------------
# Buckets — define em qual seção da sidebar cada model_name aparece.
# Os nomes (em minúsculas, sem app_label) são os object_name dos modelos.
# Modelos não listados caem em "Outros".
# ---------------------------------------------------------------------------
BUCKETS: list[tuple[str, str, list[str]]] = [
    ("Hierarquia", "🏭", [
        "fabrica", "area", "produto", "historicosku",
    ]),
    ("Equipamentos", "⚙", [
        "linhaproducao", "equipamento", "tagcoleta", "sensor", "conexaoopc",
    ]),
    ("Operação", "⌚", [
        "turnoproducao", "calendarioproducao", "eventoestadoequipamento",
        "eventoparada", "ordemproducao", "registroproducaoturno",
    ]),
    ("Analytics", "📊", [
        "metricaproducao", "defeito", "strategicinitiative", "analyticsprofile",
    ]),
]

# Ícones individuais (override por modelo, opcional)
MODEL_ICONS: dict[str, str] = {
    "fabrica": "🏭",
    "area": "▦",
    "produto": "📦",
    "historicosku": "↪",
    "linhaproducao": "━",
    "equipamento": "⚙",
    "tagcoleta": "⌗",
    "sensor": "⊙",
    "conexaoopc": "🔌",
    "turnoproducao": "⌚",
    "calendarioproducao": "📅",
    "eventoestadoequipamento": "▶",
    "eventoparada": "⏸",
    "ordemproducao": "📋",
    "registroproducaoturno": "📈",
    "metricaproducao": "📊",
    "defeito": "⚠",
    "strategicinitiative": "🎯",
    "analyticsprofile": "🧠",
    # Auth/users (sempre presentes)
    "user": "👤",
    "group": "👥",
}


def _bucket_for(model_name_lower: str) -> tuple[str, str]:
    for label, emoji, names in BUCKETS:
        if model_name_lower in names:
            return label, emoji
    return ("Outros", "📁")


@register.simple_tag(takes_context=True)
def grouped_apps(context):
    """Reorganiza context['available_apps'] em buckets do MIS.

    Retorna lista de dicts:
        [{label, emoji, models: [{name, object_name, admin_url, count, icon}, ...]}]
    """
    available = context.get("available_apps") or []
    groups: dict[str, dict] = {}

    for app in available:
        for model in app.get("models", []):
            obj_name = (model.get("object_name") or "").lower()
            label, emoji = _bucket_for(obj_name)

            if label not in groups:
                groups[label] = {"label": label, "emoji": emoji, "models": []}

            groups[label]["models"].append({
                "name": model.get("name"),
                "object_name": model.get("object_name"),
                "admin_url": model.get("admin_url"),
                "add_url": model.get("add_url"),
                "icon": MODEL_ICONS.get(obj_name, "•"),
                "count": _model_count(app["app_label"], obj_name),
            })

    # Ordena por ordem do BUCKETS, "Outros" sempre por último.
    order = [lbl for lbl, _, _ in BUCKETS] + ["Outros"]
    return [groups[lbl] for lbl in order if lbl in groups]


def _model_count(app_label: str, model_name_lower: str) -> str | int:
    """Conta lazy + cached por 60s. Falha silenciosa retorna '—'."""
    cache_key = f"admin_mis:count:{app_label}:{model_name_lower}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        Model = apps.get_model(app_label, model_name_lower)
        n = Model.objects.all().count()
    except Exception:
        n = "—"
    # Formata números grandes (12,4k)
    formatted: str | int
    if isinstance(n, int):
        if n >= 100_000:
            formatted = f"{n/1000:.0f}k"
        elif n >= 10_000:
            formatted = f"{n/1000:.1f}k"
        else:
            formatted = n
    else:
        formatted = n
    cache.set(cache_key, formatted, 60)
    return formatted


@register.filter
def path_starts_with(path: str, prefix: str) -> bool:
    """Retorna True se request.path começa com prefix. Usado pra is-active."""
    if not path or not prefix:
        return False
    return path.startswith(prefix)


@register.simple_tag
def admin_url(name: str, *args, **kwargs):
    try:
        return reverse(f"admin:{name}", args=args, kwargs=kwargs)
    except NoReverseMatch:
        return ""
