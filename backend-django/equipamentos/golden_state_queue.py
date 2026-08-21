"""
Fila in-memory de comandos Golden State (substitui
backend-flask/services/command_queue.py durante a Onda 5 do Flask-out).

Coletor faz POST de comandos via /api/golden-state/apply → entra na fila.
Coletor então polleia /api/golden-state/pending e marca como aplicado via
/api/golden-state/callback. Frontend pollea /api/golden-state/status/<id>
para acompanhar.

Limitação: dict in-memory por processo. Sobrevive ao container (não ao
restart). Para persistência forte futuramente, migrar para tabela
Postgres com pgnotify.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any

# {scope: [batch, ...]} onde scope normalmente é 'GLOBAL'
_pending: dict[str, list[dict[str, Any]]] = defaultdict(list)

# {batch_id: {status, message, progress, updated_at}}
_status: dict[str, dict[str, Any]] = {}

_lock = threading.Lock()


def add_command(scope: str, batch: dict[str, Any]) -> None:
    with _lock:
        _pending[scope].append(batch)
        _status[batch['id']] = {
            'status': 'pending',
            'message': '',
            'progress': 0,
            'updated_at': time.time(),
        }


def get_pending_commands(scope: str) -> list[dict[str, Any]]:
    """Retorna e LIMPA os comandos pendentes do escopo (entregues 1 vez)."""
    with _lock:
        cmds = list(_pending[scope])
        _pending[scope].clear()
        for batch in cmds:
            bid = batch.get('id')
            if bid in _status:
                _status[bid]['status'] = 'delivered'
                _status[bid]['updated_at'] = time.time()
        return cmds


def peek_queue(scope: str) -> list[dict[str, Any]]:
    """Inspeciona sem consumir."""
    with _lock:
        return list(_pending[scope])


def update_command_status(
    batch_id: str, status: str, message: str = '', progress: int = 0
) -> None:
    with _lock:
        _status[batch_id] = {
            'status': status,
            'message': message,
            'progress': progress,
            'updated_at': time.time(),
        }


def get_command_status(batch_id: str) -> dict[str, Any]:
    with _lock:
        return _status.get(batch_id, {
            'status': 'unknown',
            'message': 'Batch ID not found',
            'progress': 0,
        })
