"""
app/schemas/time_range.py
=========================

Contrato de filtro temporal estilo Grafana: par (start, end) + auto-resolução
da granularidade de agregação para evitar payloads de centenas de MB.

Substitui os filtros "Últimas 24h / 7d / 30d" fixos do Flask legado, que eram
uma das principais reclamações (projeto doc: "os filtros de tempos de
analytics precisam ser baseados em data hora e não somente tempos fixos").
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class TimeRange(BaseModel):
    """
    Janela temporal com resolução automática.

    Exemplos aceitos:
        {"start": "2026-04-20T00:00:00Z", "end": "2026-04-21T00:00:00Z"}
        {"start": "2026-04-23T08:00:00-03:00", "end": "now"}
        {"last": "24h"}   # shorthand compatível com frontend antigo
    """

    start: datetime | None = None
    end: datetime | None = None
    last: str | None = Field(
        default=None,
        description="Shorthand retrocompatível: '15m', '1h', '24h', '7d', '30d'",
    )
    granularity: Literal["auto", "5s", "10s", "30s", "1m", "5m", "10m", "30m", "1h", "1d"] = "auto"

    @field_validator("end", "start", mode="before")
    @classmethod
    def _parse_now(cls, v):
        if v == "now" or v == "NOW":
            return datetime.now(timezone.utc)
        return v

    @model_validator(mode="after")
    def _expand_last(self) -> "TimeRange":
        # Se o cliente passou `last`, expande para start/end.
        if self.last and not (self.start and self.end):
            delta = _parse_last(self.last)
            end = self.end or datetime.now(timezone.utc)
            start = end - delta
            object.__setattr__(self, "start", start)
            object.__setattr__(self, "end", end)
        if not self.start or not self.end:
            raise ValueError("TimeRange: informe 'start'+'end' ou 'last'.")
        if self.start >= self.end:
            raise ValueError("TimeRange.start deve ser < end")
        return self

    @property
    def duration_s(self) -> float:
        return (self.end - self.start).total_seconds()

    def effective_granularity(self, target_points: int = 2000, min_interval_s: int = 5) -> str:
        """
        Escolhe granularidade para caber em ~target_points pontos, respeitando
        resolução mínima. Mesma heurística do Flask legado (lógica consolidada).
        """
        if self.granularity != "auto":
            return self.granularity
        ideal = max(min_interval_s, int(self.duration_s / target_points))
        if ideal <= 5:
            return "5s"
        if ideal <= 10:
            return "10s"
        if ideal <= 30:
            return "30s"
        if ideal <= 60:
            return "1m"
        if ideal <= 300:
            return "5m"
        if ideal <= 1800:
            return "30m"
        if ideal <= 3600:
            return "1h"
        return "1d"


_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 86400 * 7}


def _parse_last(last: str) -> timedelta:
    """'15m' -> 900s, '24h' -> 86400s."""
    last = last.strip().lower()
    if not last:
        raise ValueError("'last' vazio")
    unit = last[-1]
    if unit not in _UNITS:
        raise ValueError(f"unidade inválida em 'last': {unit!r}")
    try:
        n = int(last[:-1])
    except ValueError as e:
        raise ValueError(f"quantidade inválida em 'last': {last!r}") from e
    if n <= 0:
        raise ValueError("'last' deve ser > 0")
    return timedelta(seconds=n * _UNITS[unit])


__all__ = ["TimeRange"]
