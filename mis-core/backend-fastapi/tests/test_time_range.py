"""
Testes do TimeRange Grafana-style.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.time_range import TimeRange


def test_last_24h_expande_para_start_end():
    tr = TimeRange(last="24h")
    assert tr.start is not None and tr.end is not None
    assert abs((tr.end - tr.start).total_seconds() - 86400) < 2


def test_start_end_explicitos():
    s = datetime(2026, 4, 1, tzinfo=timezone.utc)
    e = datetime(2026, 4, 2, tzinfo=timezone.utc)
    tr = TimeRange(start=s, end=e)
    assert tr.duration_s == 86400


def test_rejeita_start_apos_end():
    with pytest.raises(ValidationError):
        TimeRange(
            start=datetime(2026, 4, 2, tzinfo=timezone.utc),
            end=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )


def test_granularidade_auto_se_adapta():
    # 1 hora -> deve caber bem em 5s..10s
    tr = TimeRange(last="1h")
    assert tr.effective_granularity() in {"5s", "10s"}

    # 30 dias -> precisa granularidade mais larga
    tr = TimeRange(last="30d")
    assert tr.effective_granularity() in {"30m", "1h", "1d"}


def test_now_como_string_aceito():
    # aceita "now" (frontend legacy compat)
    tr = TimeRange(start="2026-04-20T00:00:00+00:00", end="now")
    assert tr.end is not None
