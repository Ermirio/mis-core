"""Endpoint de versão — fonte canônica do que está rodando no servidor.

Lê /etc/mis-version (gravado pelo Dockerfile) e retorna JSON. Se o arquivo
não existir (rodando em dev sem container), cai para variáveis de ambiente
e por fim para "unknown".

Por que existe:
    Quando o frontend está cacheado / sob proxy reverso, é difícil saber
    qual imagem está realmente atendendo. Esse endpoint contorna o cache
    do navegador (Cache-Control: no-store) e expõe a verdade: o que o
    container Django está vendo no momento.

Uso:
    GET /api/version/
    {"service": "mis-core-django", "version": "1.5.2", "git_hash": "ab12cd3",
     "build_time": "2026-04-28T14:08:12Z", "served_at": "..."}
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

VERSION_FILE = Path("/etc/mis-version")


def _read_stamp() -> dict[str, str]:
    """Lê /etc/mis-version no formato `key=value` por linha."""
    out: dict[str, str] = {}
    if VERSION_FILE.exists():
        try:
            for line in VERSION_FILE.read_text().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip()
        except OSError:
            pass
    return out


@never_cache
@require_GET
def version_view(request):
    stamp = _read_stamp()
    payload = {
        "service": "mis-core-django",
        "version": stamp.get("version") or os.getenv("MIS_VERSION", "0.0.0-runtime"),
        "git_hash": stamp.get("git") or os.getenv("MIS_GIT_HASH", "no-git"),
        "build_time": stamp.get("build_time") or os.getenv("MIS_BUILD_TIME", "unknown"),
        "served_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "debug": os.getenv("DJANGO_DEBUG", "False").lower() in ("1", "true", "yes"),
    }
    response = JsonResponse(payload)
    # Defesa explícita contra qualquer proxy reverso intermediário
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response
