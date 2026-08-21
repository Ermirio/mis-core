"""
Repository pattern para acesso ao InfluxDB.

Arquitetura
-----------
Toda leitura ou escrita no InfluxDB de um equipamento, linha, área ou
fábrica passa POR AQUI. Não há mais filtros ad-hoc por string nas views.

A unicidade da consulta é GARANTIDA por construção:
  - cada Repository recebe um objeto Django (Equipamento, LinhaProducao,
    Area ou Fabrica) com identidade já resolvida pelo ORM;
  - o filtro Influx é montado a partir da hierarquia cadastrada
    (factory + area + line + equipment), exatamente o caminho que o
    usuário cadastrou no admin;
  - quem só tem uma string ("E001") precisa primeiro resolver para um
    objeto Django via `resolvers.resolver_equipamento(...)` — não há
    atalho direto de string para query.

Resultado: é IMPOSSÍVEL escrever query ambígua. Codigo duplicado entre
linhas continua válido (PR 3) mas as queries sempre desambiguam pela
hierarquia.

Tags canônicas no Influx (Onda final da identidade):
  factory   = código da fábrica   (F001)
  area      = código da área      (A001)
  line      = código da linha     (L01)   — único global
  equipment = código do equip.    (E001)  — único dentro da linha

As tags legadas `equipment_slug` e a tag `equipment` sem `line` deixam
de ser usadas como filtro de unicidade. Existem ainda durante o
backfill, mas o código novo não as consulta.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

from django.conf import settings
from influxdb import InfluxDBClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cliente Influx — singleton lazy
# ---------------------------------------------------------------------------

_client_cache: Optional[InfluxDBClient] = None


def get_client() -> InfluxDBClient:
    """Retorna um cliente Influx configurado pelas settings do Django.

    Reusa instância single para evitar reabrir socket a cada query.
    """
    global _client_cache
    if _client_cache is None:
        _client_cache = InfluxDBClient(
            host=getattr(settings, 'INFLUXDB_HOST', '127.0.0.1'),
            port=getattr(settings, 'INFLUXDB_PORT', 8086),
            username=getattr(settings, 'INFLUXDB_USER', ''),
            password=getattr(settings, 'INFLUXDB_PASSWORD', ''),
            database=getattr(settings, 'INFLUXDB_DATABASE', 'industrial_db'),
        )
    return _client_cache


def _escape_tag(value) -> str:
    """Escape um valor de tag antes de interpolar no InfluxQL."""
    return str(value or '').replace('\\', '\\\\').replace("'", "\\'")


# ===========================================================================
# Construção do filtro hierárquico
# ===========================================================================

class _HierarchicalFilter:
    """Encapsula a expressão WHERE de uma posição na hierarquia industrial.

    Cada Repository (Equipamento/Linha/Area/Fabrica) instancia este filter
    a partir do nível dele e os repositórios "mais específicos" herdam os
    níveis "menos específicos" automaticamente.
    """

    def __init__(
        self,
        *,
        factory: Optional[str] = None,
        area: Optional[str] = None,
        line: Optional[str] = None,
        equipment: Optional[str] = None,
    ):
        self.factory = factory or ''
        self.area = area or ''
        self.line = line or ''
        self.equipment = equipment or ''

    def where_clause(self) -> str:
        """Devolve o trecho WHERE construído a partir do nível disponível."""
        parts: list[str] = []
        if self.factory:
            parts.append(f"\"factory\" = '{_escape_tag(self.factory)}'")
        if self.area:
            parts.append(f"\"area\" = '{_escape_tag(self.area)}'")
        if self.line:
            parts.append(f"\"line\" = '{_escape_tag(self.line)}'")
        if self.equipment:
            parts.append(f"\"equipment\" = '{_escape_tag(self.equipment)}'")
        if not parts:
            raise ValueError(
                "Filtro hierárquico vazio: pelo menos UM nível deve ser informado."
            )
        return ' AND '.join(parts)

    def tags_dict(self) -> dict:
        """Devolve as tags que devem ser escritas no Influx (para writes)."""
        d: dict[str, str] = {}
        if self.factory: d['factory'] = self.factory
        if self.area: d['area'] = self.area
        if self.line: d['line'] = self.line
        if self.equipment: d['equipment'] = self.equipment
        return d

    def __repr__(self):
        return (
            f"<HierFilter factory={self.factory or '-'} "
            f"area={self.area or '-'} line={self.line or '-'} "
            f"equipment={self.equipment or '-'}>"
        )


# ===========================================================================
# Base — operações compartilhadas
# ===========================================================================

class _InfluxRepositoryBase:
    """Operações comuns: query construída a partir do filtro hierárquico."""

    _filter: _HierarchicalFilter
    measurement = 'production'

    @property
    def client(self) -> InfluxDBClient:
        return get_client()

    def where(self) -> str:
        return self._filter.where_clause()

    def query(self, sql_fragment: str):
        """Executa uma query Influx adicionando o WHERE hierárquico.

        Args:
            sql_fragment: trecho que vem DEPOIS do `WHERE` hierárquico.
                          Use `{m}` como placeholder para o measurement.
                          Use `AND ...` para adicionar filtros extras.

        Exemplo:
            >>> repo.query("AND time > now() - 5m GROUP BY time(1m)")
        """
        sql = (
            f"SELECT {self._select} FROM \"{self.measurement}\" "
            f"WHERE {self.where()} {sql_fragment}"
        )
        return self.client.query(sql)

    _select = '*'  # subclasses sobrescrevem se quiserem default


# ===========================================================================
# Repositórios por nível da hierarquia
# ===========================================================================

class FabricaInflux(_InfluxRepositoryBase):
    """Acesso Influx no escopo de uma Fábrica inteira."""

    def __init__(self, fabrica):
        if not fabrica or not getattr(fabrica, 'codigo', ''):
            raise ValueError("FabricaInflux exige uma Fabrica com codigo.")
        self.fabrica = fabrica
        self._filter = _HierarchicalFilter(factory=fabrica.codigo)


class AreaInflux(_InfluxRepositoryBase):
    """Acesso Influx no escopo de uma Área (toda a fábrica abaixo dela)."""

    def __init__(self, area):
        if not area or not getattr(area, 'codigo', ''):
            raise ValueError("AreaInflux exige uma Area com codigo.")
        self.area = area
        fabrica_codigo = area.fabrica.codigo if getattr(area, 'fabrica', None) else ''
        self._filter = _HierarchicalFilter(
            factory=fabrica_codigo,
            area=area.codigo,
        )


class LinhaInflux(_InfluxRepositoryBase):
    """Acesso Influx no escopo de UMA linha.

    Métodos especializados para o que a UI/relatórios da linha pedem.
    """

    def __init__(self, linha):
        if not linha or not getattr(linha, 'codigo', ''):
            raise ValueError("LinhaInflux exige uma LinhaProducao com codigo.")
        self.linha = linha
        area = getattr(linha, 'area', None)
        fabrica = area.fabrica if area else None
        self._filter = _HierarchicalFilter(
            factory=fabrica.codigo if fabrica else '',
            area=area.codigo if area else '',
            line=linha.codigo,
        )

    # ---- atalhos de uso frequente ----

    def equipments_realtime(self, since: str = '5m') -> list[dict]:
        """Retorna o último ponto de cada equipamento da linha
        (1 ponto por equipamento). Quem chama agrupa como quiser.
        """
        sql = (
            f"SELECT last(velocidade_atual) AS vel, "
            f"last(estado_maquina) AS estado, "
            f"last(oee_realtime) AS oee "
            f"FROM \"{self.measurement}\" "
            f"WHERE {self.where()} AND time > now() - {since} "
            f"GROUP BY \"equipment\""
        )
        rs = self.client.query(sql)
        out = []
        for (_, tags), points in rs.items():
            for p in points:
                out.append({
                    'equipment': (tags or {}).get('equipment'),
                    **{k: v for k, v in p.items() if k != 'time'},
                    'time': p.get('time'),
                })
                break
        return out


class EquipamentoInflux(_InfluxRepositoryBase):
    """Acesso Influx de UM equipamento. Único caminho legítimo para
    queries sobre dados de equipamento.

    Substitui as funções soltas em `influx_helpers.py`.
    """

    def __init__(self, equipamento):
        if not equipamento:
            raise ValueError("EquipamentoInflux exige um Equipamento.")
        if not getattr(equipamento, 'codigo', ''):
            raise ValueError(f"Equipamento {equipamento.pk} sem código.")
        self.eq = equipamento
        linha = getattr(equipamento, 'linha', None)
        area = getattr(linha, 'area', None) if linha else None
        fabrica = area.fabrica if area else None
        self._filter = _HierarchicalFilter(
            factory=fabrica.codigo if fabrica else '',
            area=area.codigo if area else '',
            line=linha.codigo if linha else '',
            equipment=equipamento.codigo,
        )

    # ---- métodos que substituem influx_helpers ----

    def last(self, field: str, since: Optional[str] = None) -> Optional[float]:
        """Último valor de um field. `since` opcional (ex.: '1h')."""
        extra = f"AND time > now() - {since}" if since else ""
        sql = (
            f"SELECT last(\"{field}\") AS v FROM \"{self.measurement}\" "
            f"WHERE {self.where()} {extra}"
        )
        pts = list(self.client.query(sql).get_points())
        if pts and pts[0].get('v') is not None:
            try:
                return float(pts[0]['v'])
            except (TypeError, ValueError):
                return None
        return None

    def first(self, field: str, since: Optional[str] = None) -> Optional[float]:
        """Primeiro valor de um field na janela."""
        extra = f"AND time > now() - {since}" if since else ""
        sql = (
            f"SELECT first(\"{field}\") AS v FROM \"{self.measurement}\" "
            f"WHERE {self.where()} {extra}"
        )
        pts = list(self.client.query(sql).get_points())
        if pts and pts[0].get('v') is not None:
            try:
                return float(pts[0]['v'])
            except (TypeError, ValueError):
                return None
        return None

    def points(
        self,
        fields: Iterable[str],
        start: str,
        end: Optional[str] = None,
        interval: Optional[str] = None,
    ) -> list[dict]:
        """Retorna pontos de múltiplos fields num intervalo.

        Args:
            fields: lista de fields ('velocidade_atual', 'oee_realtime', ...).
            start: timestamp ISO ou 'now() - 1h'.
            end:   timestamp ISO; default agora.
            interval: se fornecido (ex.: '1m'), faz GROUP BY time(interval).

        Returns:
            Lista de dicts com 'time' e os fields pedidos.
        """
        if not start.startswith('now('):
            start = f"'{start}'"
        end_clause = f" AND time <= '{end}'" if end else ''
        select = ', '.join(
            f"last(\"{f}\") AS \"{f}\"" if interval else f"\"{f}\""
            for f in fields
        )
        group_by = f" GROUP BY time({interval}) fill(none)" if interval else ''
        sql = (
            f"SELECT {select} FROM \"{self.measurement}\" "
            f"WHERE {self.where()} AND time >= {start}{end_clause}{group_by}"
        )
        return list(self.client.query(sql).get_points())

    def field_count(self, field: str, since: str = '5m') -> int:
        """Quantidade de pontos do field na janela."""
        sql = (
            f"SELECT count(\"{field}\") AS n FROM \"{self.measurement}\" "
            f"WHERE {self.where()} AND time > now() - {since}"
        )
        pts = list(self.client.query(sql).get_points())
        return int(pts[0].get('n', 0)) if pts else 0

    # ---- write — single source of truth ----

    def write_point(self, fields: dict, time_iso: Optional[str] = None) -> None:
        """Escreve um ponto com as tags hierárquicas obrigatórias.

        Tags são derivadas do equipamento (factory/area/line/equipment).
        Tudo passa por aqui — coletor e ingestão de dados também.
        """
        point = {
            'measurement': self.measurement,
            'tags': self._filter.tags_dict(),
            'fields': dict(fields),
        }
        if time_iso:
            point['time'] = time_iso
        self.client.write_points([point])

    @property
    def tags(self) -> dict:
        """Tags hierárquicas para serem mescladas em writes externos
        (ex.: production_engine que monta o point com shift/order_id)."""
        return self._filter.tags_dict()


# ===========================================================================
# Helpers de conveniência para casos onde só se tem o código
# ===========================================================================

def from_equipamento_code(codigo: str, linha_codigo: Optional[str] = None):
    """Resolve `Equipamento` por código (com linha opcional) e devolve
    `EquipamentoInflux`. Se o código for ambíguo e a linha não for
    informada, levanta `EquipamentoAmbiguo` (mesma exceção do resolver).

    Use APENAS em pontos legados onde só há string como input — para
    código novo, prefira passar o objeto Equipamento direto.
    """
    from .resolvers import resolver_equipamento  # import deferido (ciclo)
    eq = resolver_equipamento(codigo=codigo, linha_codigo=linha_codigo)
    return EquipamentoInflux(eq)


def from_equipamento_slug(slug: str):
    """Resolve por slug global (L01.E001) — caminho de migração legacy."""
    from .resolvers import resolver_equipamento
    eq = resolver_equipamento(slug=slug)
    return EquipamentoInflux(eq)


__all__ = [
    'get_client',
    'FabricaInflux',
    'AreaInflux',
    'LinhaInflux',
    'EquipamentoInflux',
    'from_equipamento_code',
    'from_equipamento_slug',
]
