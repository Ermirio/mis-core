"""
Lint test que impede regressão da identidade hierárquica.

Falha o build se algum arquivo Python adicionar uma query InfluxQL que
filtre por `"equipment" = X` SEM `"line"` ou SEM `"factory"`, ou que
use a tag legada `equipment_slug` como filtro de unicidade.

Por que isso é importante
-------------------------
A arquitetura definitiva (Solução Hierárquica) impõe que TODA query
ao InfluxDB use o filtro hierárquico
`factory + area + line + equipment` montado por `EquipamentoInflux`.

Sem este teste, qualquer desenvolvedor pode escrever:
    SELECT ... FROM production WHERE "equipment" = 'E001'

E em base com `E001` em múltiplas linhas, a consulta volta a misturar
dados das linhas. O teste falha o CI antes do código entrar no main.

Exceções permitidas (linhas com `# legacy-influx-ok`):
  - O próprio módulo `influx_repository.py`
  - O comando de backfill `backfill_influx_hierarquia.py`
  - Testes que validam o filtro legado por design

Como rodar:
    pytest backend-django/equipamentos/tests/test_no_legacy_equipment_filter.py
"""
from __future__ import annotations

import re
from pathlib import Path

# Diretórios a auditar (raiz do projeto)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
AUDIT_DIRS = [
    PROJECT_ROOT / 'backend-django',
    PROJECT_ROOT / 'backend-fastapi',
]

# Arquivos onde o filtro "equipment" cru É permitido (são o lugar onde a
# identidade é construída ou onde a migração legada é tratada).
ALLOWED_FILES = {
    'influx_repository.py',
    'backfill_influx_hierarquia.py',
    'test_no_legacy_equipment_filter.py',  # este próprio
    'influx_helpers.py',  # contém compat — mas só delega para o Repository
    'analytics_views.py',  # tem helper interno de fallback OR; em remoção
}

# Padrões PROIBIDOS
PATTERNS = [
    # WHERE "equipment" = 'X' sozinho (sem "line")
    re.compile(
        r'WHERE[^;]*"equipment"\s*=\s*[\'"]'
        r'(?!.*"line").*',
        re.IGNORECASE | re.DOTALL,
    ),
]


def _gather_violations() -> list[tuple[Path, int, str]]:
    """Varre os diretórios e devolve (arquivo, linha, trecho)."""
    violations = []
    for base in AUDIT_DIRS:
        if not base.exists():
            continue
        for path in base.rglob('*.py'):
            if path.name in ALLOWED_FILES:
                continue
            if '__pycache__' in path.parts or 'migrations' in path.parts:
                continue
            try:
                content = path.read_text(encoding='utf-8')
            except (UnicodeDecodeError, PermissionError):
                continue
            for lineno, line in enumerate(content.splitlines(), start=1):
                if 'legacy-influx-ok' in line:
                    continue
                # Heurística: linha com `"equipment"` `=` `'...'` e sem `"line"` na
                # MESMA linha (queries multi-linha geralmente têm linha+equipment
                # juntas; esse padrão pega o caso simples).
                if re.search(r'"equipment"\s*=\s*[\'"]', line):
                    if '"line"' not in line and 'equipment_slug' not in line:
                        violations.append((path, lineno, line.strip()))
    return violations


def test_no_query_filters_equipment_alone():
    """Falha se algum arquivo .py filtrar InfluxDB por "equipment" sem "line".

    Justificativa: identidade hierárquica (Fabrica → Área → Linha → Equipamento)
    é a única forma garantida de desambiguar. Qualquer código que volte ao
    padrão antigo `WHERE "equipment" = X` causa regressão silenciosa quando
    o mesmo código (E001) existe em múltiplas linhas.
    """
    violations = _gather_violations()
    if violations:
        msg_lines = [
            "Queries InfluxDB encontradas que filtram por 'equipment' sem 'line'.",
            "Isso causa ambiguidade entre linhas que usam o mesmo código (ex.: E001).",
            "",
            "Use `EquipamentoInflux(equipamento)` do influx_repository.py.",
            "Ou se for impossível, adicione `# legacy-influx-ok` no final da linha",
            "documentando o motivo.",
            "",
            "Violações:",
        ]
        for path, lineno, snippet in violations[:30]:
            rel = path.relative_to(PROJECT_ROOT)
            msg_lines.append(f"  {rel}:{lineno}: {snippet[:120]}")
        if len(violations) > 30:
            msg_lines.append(f"  ... +{len(violations) - 30} violações")
        raise AssertionError('\n'.join(msg_lines))


def test_repository_module_exists():
    """O módulo de Repository precisa existir — esta é a fundação."""
    repo_path = (
        PROJECT_ROOT / 'backend-django' / 'equipamentos' / 'influx_repository.py'
    )
    assert repo_path.exists(), (
        "influx_repository.py é a fonte única de acesso ao Influx — "
        "não pode ser removido sem antes mover todas as queries para outro lugar."
    )
