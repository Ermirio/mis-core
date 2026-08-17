"""
app/core/metrics_catalog.py
===========================

Catálogo de métricas e estados — FONTE ÚNICA DE VERDADE sobre tipos de dados.

Por que isto existe (problema resolvido):
    No backend-flask legado, cada métrica tinha um tratamento ad-hoc espalhado
    em if/else dentro de `query_influx_to_df`. Faltava o conceito de "kind" —
    e esse é o pulo do gato que diferencia um analytics que mente (soma
    contadores cumulativos) de um que fala a verdade.

Terminologia (ISO 22400-2 + PI System / OSIsoft):
    GAUGE   — variável contínua instantânea. Ex.: temperatura, pressão,
              velocidade_atual, peso_medio. Agregação padrão = MEAN.
    COUNTER — contador monotônico (pode resetar). Ex.: contagem_saida,
              refugo_op_acumulado. Agregação padrão = DELTA (diff().clip(0).sum()).
    STATE   — variável categórica discreta. Ex.: estado_maquina. Agregação
              padrão = LAST ou tempo-em-estado (mode vs proportion).

Analogia (processo industrial):
    Imagine um totalizador de massa (COUNTER) e um medidor de temperatura
    (GAUGE). Tirar a média do totalizador é sem sentido — você quer saber
    quanto foi produzido NO PERÍODO. Já tirar o delta da temperatura também
    é sem sentido — você quer o valor médio/atual. "Kind" codifica isso
    no tipo da métrica, evitando o erro em todos os call sites.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ==============================================================================
# 1) KINDS — tipos de métrica que dirigem a agregação
# ==============================================================================
class MetricKind(str, Enum):
    GAUGE = "GAUGE"        # contínuo, agrega com mean/min/max/p95
    COUNTER = "COUNTER"    # cumulativo (reset-tolerante), agrega com delta
    STATE = "STATE"        # categórico, agrega com last/mode/duration
    EVENT = "EVENT"        # timestamped discreto (falha, alarme) — count/rate


class AggregationKind(str, Enum):
    MEAN = "mean"
    SUM = "sum"
    LAST = "last"
    DELTA = "delta"         # para COUNTER (reset-tolerante)
    P50 = "p50"
    P90 = "p90"
    P99 = "p99"
    COUNT = "count"
    NON_NULL_COUNT = "non_null_count"


# ==============================================================================
# 2) ESTADOS DE EQUIPAMENTO (compatível com o coletor OPC legado)
# ==============================================================================
class EquipState(str, Enum):
    """
    Semânticos — ordenados pelo impacto em OEE (ISO 22400-2):
        RUNNING / STARTING / STOPPING → operação
        IDLE → ligado mas sem produzir (estado=0 no schema legado)
        WAITING_UPSTREAM / BLOCKED_DOWNSTREAM → parada por causa externa
        SETUP → parada planejada (Availability)
        FAULT / MAINTENANCE / WAITING_MAINTENANCE → parada não planejada
        TEST, OFFLINE → excluídos de EDA por default
    """

    RUNNING = "RUNNING"
    STARTING = "STARTING"
    STOPPING = "STOPPING"
    IDLE = "IDLE"                        # [BUG-4] estado=0: máquina ligada, sem produzir
    WAITING_UPSTREAM = "WAITING_UPSTREAM"
    BLOCKED_DOWNSTREAM = "BLOCKED_DOWNSTREAM"
    SETUP = "SETUP"
    FAULT = "FAULT"
    MAINTENANCE = "MAINTENANCE"
    WAITING_MAINTENANCE = "WAITING_MAINTENANCE"
    LACK_OF_MATERIAL = "LACK_OF_MATERIAL"
    WAITING_CONDITIONS = "WAITING_CONDITIONS"
    TEST = "TEST"
    OFFLINE = "OFFLINE"                  # [BUG-4] estado=999: PLC sem comunicação
    OTHER = "OTHER"


# Mapping legado (código numérico gravado no InfluxDB) -> EquipState
# Mantido sincronizado com backend-flask/constants.py::ESTADOS_MAQUINA
LEGACY_CODE_TO_STATE: dict[int, EquipState] = {
    0: EquipState.IDLE,                  # [BUG-4] antes era OTHER (genérico) — agora explícito
    1: EquipState.RUNNING,
    2: EquipState.WAITING_UPSTREAM,
    3: EquipState.BLOCKED_DOWNSTREAM,
    4: EquipState.FAULT,
    5: EquipState.SETUP,
    6: EquipState.TEST,
    7: EquipState.WAITING_MAINTENANCE,
    8: EquipState.MAINTENANCE,
    9: EquipState.LACK_OF_MATERIAL,
    10: EquipState.OTHER,
    11: EquipState.STARTING,
    12: EquipState.WAITING_CONDITIONS,
    13: EquipState.STOPPING,
    999: EquipState.OFFLINE,             # [BUG-4] forçado pelo coletor / Flask quando PLC offline
}

# Default para OFF-mask em analytics — alinhado com Flask blueprints/analytics.py.
# [BUG-4] inclui IDLE e OFFLINE explicitamente. Sem eles, períodos com PLC
# desconectado ou máquina em standby contaminam EDA com zeros.
DEFAULT_EXCLUDE_STATES: list[EquipState] = [
    EquipState.IDLE,
    EquipState.FAULT,
    EquipState.TEST,
    EquipState.WAITING_MAINTENANCE,
    EquipState.MAINTENANCE,
    EquipState.OFFLINE,
    EquipState.OTHER,
]


# Helpers
def legacy_code_to_state(code: int | None) -> EquipState:
    """Mapeia código numérico legado para EquipState. None => OTHER."""
    if code is None:
        return EquipState.OTHER
    return LEGACY_CODE_TO_STATE.get(int(code), EquipState.OTHER)


# ==============================================================================
# 3) DEFINIÇÃO DE MÉTRICA
# ==============================================================================
@dataclass(frozen=True)
class MetricDef:
    """
    Metadados de uma métrica. Determina:
      - como agregar (kind + default_agg)
      - unidade de display
      - se é derivada de outras métricas (ex.: giveaway = f(peso, target))
    """

    name: str                          # chave canônica (snake_case)
    influx_field: str                  # coluna no InfluxDB
    kind: MetricKind
    default_agg: AggregationKind
    unit: str = ""
    description: str = ""
    derived: bool = False
    aliases: tuple[str, ...] = ()      # nomes alternativos aceitos do frontend


# ==============================================================================
# 4) CATÁLOGO — adicione novas métricas SOMENTE aqui
# ==============================================================================
METRICS: dict[str, MetricDef] = {
    # --- Contadores (COUNTER → DELTA) ---
    "contagem_saida": MetricDef(
        name="contagem_saida",
        influx_field="contagem_saida",
        kind=MetricKind.COUNTER,
        default_agg=AggregationKind.DELTA,
        unit="un",
        description="Contagem acumulada de unidades produzidas (reset no turno)",
    ),
    "refugo_op_acumulado": MetricDef(
        name="refugo_op_acumulado",
        influx_field="refugo_op_acumulado",
        kind=MetricKind.COUNTER,
        default_agg=AggregationKind.DELTA,
        unit="un",
        description="Refugo acumulado por ordem de produção",
    ),

    # --- Gauges (GAUGE → MEAN) ---
    "velocidade_atual": MetricDef(
        name="velocidade_atual",
        influx_field="velocidade_atual",
        kind=MetricKind.GAUGE,
        default_agg=AggregationKind.MEAN,
        unit="upm",
        description="Velocidade instantânea (unidades por minuto)",
    ),
    "ultimo_peso": MetricDef(
        name="ultimo_peso",
        influx_field="ultimo_peso",
        kind=MetricKind.GAUGE,
        default_agg=AggregationKind.MEAN,
        unit="g",
        description="Último peso medido (para give-away)",
    ),
    "formato_gramas": MetricDef(
        name="formato_gramas",
        influx_field="formato_gramas",
        kind=MetricKind.GAUGE,
        default_agg=AggregationKind.LAST,
        unit="g",
        description="Peso-alvo (target) do formato da OP",
    ),
    "oee_realtime": MetricDef(
        name="oee_realtime",
        influx_field="oee_realtime",
        kind=MetricKind.GAUGE,
        default_agg=AggregationKind.MEAN,
        unit="%",
        description="OEE calculado em tempo real (A × P × Q)",
    ),
    "availability_realtime": MetricDef(
        name="availability_realtime",
        influx_field="availability_realtime",
        kind=MetricKind.GAUGE,
        default_agg=AggregationKind.MEAN,
        unit="%",
    ),
    "performance_realtime": MetricDef(
        name="performance_realtime",
        influx_field="performance_realtime",
        kind=MetricKind.GAUGE,
        default_agg=AggregationKind.MEAN,
        unit="%",
    ),
    "quality_realtime": MetricDef(
        name="quality_realtime",
        influx_field="quality_realtime",
        kind=MetricKind.GAUGE,
        default_agg=AggregationKind.MEAN,
        unit="%",
    ),

    # --- States ---
    "estado_maquina": MetricDef(
        name="estado_maquina",
        influx_field="estado_maquina",
        kind=MetricKind.STATE,
        default_agg=AggregationKind.LAST,
        unit="",
        description="Código numérico de estado (ver LEGACY_CODE_TO_STATE)",
    ),
}


def get_metric(name: str) -> MetricDef | None:
    """Busca por nome canônico ou por alias."""
    m = METRICS.get(name)
    if m:
        return m
    for md in METRICS.values():
        if name in md.aliases:
            return md
    return None


__all__ = [
    "MetricKind",
    "AggregationKind",
    "EquipState",
    "LEGACY_CODE_TO_STATE",
    "DEFAULT_EXCLUDE_STATES",
    "MetricDef",
    "METRICS",
    "get_metric",
    "legacy_code_to_state",
]
