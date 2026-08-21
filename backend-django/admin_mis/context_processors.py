"""Context processors do admin_mis.

Por que existe:
    Os templates precisam saber a versão e o git hash do MIS para mostrar
    no rodapé/sidebar. Em vez de injetar via view, usamos um context
    processor para que TODA página do admin (e do app) tenha acesso.
"""

from __future__ import annotations

import os
from pathlib import Path

_VERSION_FILE = Path("/etc/mis-version")


def _read_stamp() -> dict[str, str]:
    out: dict[str, str] = {}
    if _VERSION_FILE.exists():
        try:
            for line in _VERSION_FILE.read_text().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip()
        except OSError:
            pass
    return out


def mis_version(request):
    stamp = _read_stamp()
    return {
        "MIS_VERSION": stamp.get("version") or os.getenv("MIS_VERSION", "0.0.0-dev"),
        "MIS_GIT_HASH": stamp.get("git") or os.getenv("MIS_GIT_HASH", "no-git"),
        "MIS_BUILD_TIME": stamp.get("build_time") or os.getenv("MIS_BUILD_TIME", "unknown"),
    }
