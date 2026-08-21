"""
InfluxDB Helpers
================
Funções reutilizáveis para consultas ao InfluxDB
"""

from influxdb import InfluxDBClient
from decouple import config
from typing import Optional, Dict, Any
from datetime import datetime


def _escape_tag(value: str) -> str:
    return str(value).replace('\\', '\\\\').replace("'", "\\'")


def _identity_filter(equipamento_codigo: str, linha_codigo: str | None = None) -> str:
    where = f'"equipment" = \'{_escape_tag(equipamento_codigo)}\''
    if linha_codigo:
        where += f' AND "line" = \'{_escape_tag(linha_codigo)}\''
    return where


def equipment_where_clause(equipamento) -> str:
    """Retorna o filtro hierárquico canônico para call-sites legados.

    Mantém GiveAway e demais views antigas compatíveis, sem voltar ao filtro
    ambíguo que considerava apenas o código curto do equipamento.
    """
    from .influx_repository import EquipamentoInflux

    return EquipamentoInflux(equipamento).where()


def get_influx_client() -> InfluxDBClient:
    """
    Retorna cliente InfluxDB configurado
    """
    return InfluxDBClient(
        host=config('INFLUXDB_HOST', default='127.0.0.1'),
        port=config('INFLUXDB_PORT', default=8086, cast=int),
        username=config('INFLUXDB_USER', default=''),
        password=config('INFLUXDB_PASSWORD', default=''),
        database=config('INFLUXDB_DATABASE', default='mis_core_db')
    )


def get_current_count(
    equipamento_codigo: str,
    client: Optional[InfluxDBClient] = None,
    linha_codigo: str | None = None,
) -> float:
    """
    Busca contagem atual de um equipamento (último valor registrado)

    Args:
        equipamento_codigo: Código do equipamento
        client: Cliente InfluxDB (opcional)

    Returns:
        Contagem atual ou 0.0 se não encontrado
    """
    if client is None:
        client = get_influx_client()

    # Busca o ÚLTIMO valor registrado (sem restrição de tempo para garantir que pegue o último)
    query = f"""
        SELECT last("contagem_saida")
        FROM "production"
        WHERE {_identity_filter(equipamento_codigo, linha_codigo)}
    """

    result = client.query(query)
    points = list(result.get_points())

    if points:
        return float(points[0].get('last', 0))
    return 0.0


def get_count_at_time(
    equipamento_codigo: str,
    target_time: datetime,
    client: Optional[InfluxDBClient] = None,
    linha_codigo: str | None = None,
) -> float:
    """
    Busca contagem em um momento específico (primeiro valor após o timestamp)

    Args:
        equipamento_codigo: Código do equipamento
        target_time: Timestamp alvo
        client: Cliente InfluxDB (opcional)

    Returns:
        Contagem no momento ou 0.0
    """
    if client is None:
        client = get_influx_client()

    query = f"""
        SELECT first("contagem_saida")
        FROM "production"
        WHERE {_identity_filter(equipamento_codigo, linha_codigo)}
        AND time >= '{target_time.isoformat()}'
    """

    result = client.query(query)
    points = list(result.get_points())

    if points:
        return float(points[0].get('first', 0))
    return 0.0


def get_count_1min_ago(
    equipamento_codigo: str,
    client: Optional[InfluxDBClient] = None,
    linha_codigo: str | None = None,
) -> float:
    """
    Busca contagem de 1 minuto atrás

    Args:
        equipamento_codigo: Código do equipamento
        client: Cliente InfluxDB (opcional)

    Returns:
        Contagem de 1 minuto atrás ou contagem atual se não encontrado
    """
    if client is None:
        client = get_influx_client()

    query = f"""
        SELECT first("contagem_saida")
        FROM "production"
        WHERE {_identity_filter(equipamento_codigo, linha_codigo)}
        AND time >= now() - 1m
    """

    result = client.query(query)
    points = list(result.get_points())

    if points:
        return float(points[0].get('first', 0))

    # Fallback: retorna contagem atual
    return get_current_count(equipamento_codigo, client, linha_codigo)


def calculate_tonnage(delta_pecas: float, formato_gramas: float) -> float:
    """
    Calcula tonelagem a partir de delta de peças e formato

    Args:
        delta_pecas: Diferença de contagem de peças
        formato_gramas: Peso de cada peça em gramas

    Returns:
        Toneladas produzidas
    """
    if formato_gramas <= 0:
        return 0.0

    return (delta_pecas * float(formato_gramas)) / 1_000_000.0


def calculate_throughput(delta_pecas_min: float, formato_gramas: float) -> float:
    """
    Calcula vazão (t/h) a partir de delta de peças por minuto

    Args:
        delta_pecas_min: Diferença de contagem no último minuto
        formato_gramas: Peso de cada peça em gramas

    Returns:
        Vazão em toneladas por hora
    """
    if formato_gramas <= 0:
        return 0.0

    # Converte peças/min para toneladas/hora
    peso_min_ton = (delta_pecas_min * formato_gramas) / 1_000_000.0
    return peso_min_ton * 60.0


def get_realtime_metrics(
    equipamento_codigo: str,
    formato_gramas: float,
    inicio_turno: datetime,
    linha_codigo: str | None = None,
) -> Dict[str, Any]:
    """
    Busca métricas em tempo real de um equipamento

    Args:
        equipamento_codigo: Código do equipamento
        formato_gramas: Peso de cada peça em gramas
        inicio_turno: Timestamp de início do turno

    Returns:
        Dict com métricas: {
            'contagem_atual': float,
            'contagem_inicio_turno': float,
            'contagem_1min_ago': float,
            'toneladas_turno': float,
            'vazao_ton_hora': float
        }
    """
    client = get_influx_client()

    # Query otimizada para buscar tudo de uma vez
    query = f"""
        SELECT last("contagem_saida") as contagem, last("toneladas_turno") as toneladas
        FROM "production"
        WHERE {_identity_filter(equipamento_codigo, linha_codigo)}
    """

    result = client.query(query)
    points = list(result.get_points())

    contagem_atual = 0.0
    toneladas = 0.0

    if points:
        contagem_atual = float(points[0].get('contagem') or 0.0)
        toneladas = float(points[0].get('toneladas') or 0.0)

    # Buscamos contagem de 1 min atrás para vazão (mantido calculado pois é taxa instantânea)
    contagem_1min = get_count_1min_ago(equipamento_codigo, client, linha_codigo)

    # Vazão usa delta de 1 minuto para calcular taxa atual
    delta_min = max(0, contagem_atual - contagem_1min)
    vazao = calculate_throughput(delta_min, formato_gramas)

    return {
        'contagem_atual': contagem_atual,
        'contagem_inicio_turno': 0, # Não mais necessário para toneladas
        'contagem_1min_ago': contagem_1min,
        'toneladas_turno': toneladas,
        'vazao_ton_hora': vazao
    }


def get_production_by_op(equipamento_codigo: str, ordem_producao: str,
                         formato_gramas: float,
                         client: Optional[InfluxDBClient] = None) -> Dict[str, Any]:
    """
    Busca produção acumulada para uma Ordem de Produção específica

    Args:
        equipamento_codigo: Código do equipamento
        ordem_producao: Número da OP
        formato_gramas: Peso de cada peça em gramas
        client: Cliente InfluxDB (opcional)

    Returns:
        Dict com métricas: {
            'toneladas_op': float,
            'contagem_op': float,
            'primeira_contagem': float,
            'ultima_contagem': float
        }
    """
    import logging

    if client is None:
        client = get_influx_client()

    # Query para pegar MIN e MAX da contagem para esta OP
    # IMPORTANTE: Usando min/max em vez de first/last para garantir compatibilidade
    query = f"""
        SELECT min("contagem_saida") as primeira, max("contagem_saida") as ultima
        FROM "production"
        WHERE "equipment" = '{equipamento_codigo}'
        AND "ordem_producao" = '{ordem_producao}'
    """

    logging.info(f"[INFLUX QUERY OP] Executando query: {query.strip()}")

    try:
        result = client.query(query)
        points = list(result.get_points())

        logging.info(f"[INFLUX QUERY OP] Resultado: {points}")

        if points and points[0].get('primeira') is not None and points[0].get('ultima') is not None:
            primeira_contagem = float(points[0].get('primeira'))
            ultima_contagem = float(points[0].get('ultima'))

            # Delta = última - primeira contagem
            delta_contagem = max(0, ultima_contagem - primeira_contagem)
            toneladas = calculate_tonnage(delta_contagem, formato_gramas)

            logging.info(f"[INFLUX QUERY OP] Primeira={primeira_contagem}, Última={ultima_contagem}, "
                        f"Delta={delta_contagem}, Toneladas={toneladas:.3f}")

            return {
                'toneladas_op': toneladas,
                'contagem_op': delta_contagem,
                'primeira_contagem': primeira_contagem,
                'ultima_contagem': ultima_contagem
            }
        else:
            logging.warning(f"[INFLUX QUERY OP] Query retornou vazio ou valores None: {points}")

    except Exception as e:
        logging.error(f"[INFLUX QUERY OP] Erro na query: {e}")

    # Se não encontrou dados, retorna zeros
    return {
        'toneladas_op': 0.0,
        'contagem_op': 0.0,
        'primeira_contagem': 0.0,
        'ultima_contagem': 0.0
    }


def get_production_by_sku(equipamento_codigo: str, sku_codigo: str,
                          formato_gramas: float,
                          client: Optional[InfluxDBClient] = None) -> Dict[str, Any]:
    """
    Busca produção acumulada para um SKU específico

    Args:
        equipamento_codigo: Código do equipamento
        sku_codigo: Código do SKU
        formato_gramas: Peso de cada peça em gramas
        client: Cliente InfluxDB (opcional)

    Returns:
        Dict com métricas: {
            'toneladas_sku': float,
            'contagem_sku': float,
            'primeira_contagem': float,
            'ultima_contagem': float
        }
    """
    if client is None:
        client = get_influx_client()

    # Query para pegar MIN e MAX da contagem para este SKU
    # IMPORTANTE: Usando min/max em vez de first/last para garantir compatibilidade
    query = f"""
        SELECT min("contagem_saida") as primeira, max("contagem_saida") as ultima
        FROM "production"
        WHERE "equipment" = '{equipamento_codigo}'
        AND "sku_codigo" = '{sku_codigo}'
    """

    result = client.query(query)
    points = list(result.get_points())

    if points and points[0].get('primeira') is not None and points[0].get('ultima') is not None:
        primeira_contagem = float(points[0].get('primeira'))
        ultima_contagem = float(points[0].get('ultima'))

        # Delta = última - primeira contagem
        delta_contagem = max(0, ultima_contagem - primeira_contagem)
        toneladas = calculate_tonnage(delta_contagem, formato_gramas)

        return {
            'toneladas_sku': toneladas,
            'contagem_sku': delta_contagem,
            'primeira_contagem': primeira_contagem,
            'ultima_contagem': ultima_contagem
        }

    # Se não encontrou dados, retorna zeros
    return {
        'toneladas_sku': 0.0,
        'contagem_sku': 0.0,
        'primeira_contagem': 0.0,
        'ultima_contagem': 0.0
    }


def get_production_by_day(equipamento_codigo: str, day: str,
                          formato_gramas: float,
                          client: Optional[InfluxDBClient] = None) -> Dict[str, Any]:
    """
    Busca produção acumulada para um dia específico

    Args:
        equipamento_codigo: Código do equipamento
        day: Data no formato 'YYYY-MM-DD'
        formato_gramas: Peso de cada peça em gramas
        client: Cliente InfluxDB (opcional)

    Returns:
        Dict com métricas: {
            'toneladas_dia': float,
            'contagem_dia': float,
            'primeira_contagem': float,
            'ultima_contagem': float
        }
    """
    if client is None:
        client = get_influx_client()

    # Query para pegar MIN e MAX da contagem para este dia
    query = f"""
        SELECT min("contagem_saida") as primeira, max("contagem_saida") as ultima
        FROM "production"
        WHERE "equipment" = '{equipamento_codigo}'
        AND time >= '{day}T00:00:00Z' AND time < '{day}T23:59:59Z'
    """

    result = client.query(query)
    points = list(result.get_points())

    if points and points[0].get('primeira') is not None and points[0].get('ultima') is not None:
        primeira_contagem = float(points[0].get('primeira'))
        ultima_contagem = float(points[0].get('ultima'))

        delta_contagem = max(0, ultima_contagem - primeira_contagem)
        toneladas = calculate_tonnage(delta_contagem, formato_gramas)

        return {
            'toneladas_dia': toneladas,
            'contagem_dia': delta_contagem,
            'primeira_contagem': primeira_contagem,
            'ultima_contagem': ultima_contagem
        }

    return {
        'toneladas_dia': 0.0,
        'contagem_dia': 0.0,
        'primeira_contagem': 0.0,
        'ultima_contagem': 0.0
    }


def get_production_by_hour(equipamento_codigo: str, start_time: datetime,
                           formato_gramas: float,
                           client: Optional[InfluxDBClient] = None) -> Dict[str, Any]:
    """
    Busca produção acumulada para uma hora específica

    Args:
        equipamento_codigo: Código do equipamento
        start_time: Timestamp de início da hora (datetime aware)
        formato_gramas: Peso de cada peça em gramas
        client: Cliente InfluxDB (opcional)

    Returns:
        Dict com métricas: {
            'toneladas_hora': float,
            'contagem_hora': float,
            'primeira_contagem': float,
            'ultima_contagem': float
        }
    """
    from datetime import timedelta

    if client is None:
        client = get_influx_client()

    end_time = start_time + timedelta(hours=1)

    # Query para pegar MIN e MAX da contagem para esta hora
    query = f"""
        SELECT min("contagem_saida") as primeira, max("contagem_saida") as ultima
        FROM "production"
        WHERE "equipment" = '{equipamento_codigo}'
        AND time >= '{start_time.isoformat()}' AND time < '{end_time.isoformat()}'
    """

    result = client.query(query)
    points = list(result.get_points())

    if points and points[0].get('primeira') is not None and points[0].get('ultima') is not None:
        primeira_contagem = float(points[0].get('primeira'))
        ultima_contagem = float(points[0].get('ultima'))

        delta_contagem = max(0, ultima_contagem - primeira_contagem)
        toneladas = calculate_tonnage(delta_contagem, formato_gramas)

        return {
            'toneladas_hora': toneladas,
            'contagem_hora': delta_contagem,
            'primeira_contagem': primeira_contagem,
            'ultima_contagem': ultima_contagem
        }

    return {
        'toneladas_hora': 0.0,
        'contagem_hora': 0.0,
        'primeira_contagem': 0.0,
        'ultima_contagem': 0.0
    }


def get_production_by_format(equipamento_codigo: str, formato_gramas: int,
                             client: Optional[InfluxDBClient] = None) -> Dict[str, Any]:
    """
    Busca produção acumulada para um formato específico (peso em gramas)

    Args:
        equipamento_codigo: Código do equipamento
        formato_gramas: Peso de cada peça em gramas (ex: 2200)
        client: Cliente InfluxDB (opcional)

    Returns:
        Dict com métricas: {
            'toneladas_formato': float,
            'contagem_formato': float,
            'primeira_contagem': float,
            'ultima_contagem': float
        }
    """
    if client is None:
        client = get_influx_client()

    # Query para pegar MIN e MAX da contagem para este formato
    # IMPORTANTE: formato_gramas agora é uma TAG
    query = f"""
        SELECT min("contagem_saida") as primeira, max("contagem_saida") as ultima
        FROM "production"
        WHERE "equipment" = '{equipamento_codigo}'
        AND "formato_gramas" = '{formato_gramas}'
    """

    result = client.query(query)
    points = list(result.get_points())

    if points and points[0].get('primeira') is not None and points[0].get('ultima') is not None:
        primeira_contagem = float(points[0].get('primeira'))
        ultima_contagem = float(points[0].get('ultima'))

        delta_contagem = max(0, ultima_contagem - primeira_contagem)
        toneladas = calculate_tonnage(delta_contagem, float(formato_gramas))

        return {
            'toneladas_formato': toneladas,
            'contagem_formato': delta_contagem,
            'primeira_contagem': primeira_contagem,
            'ultima_contagem': ultima_contagem
        }

    return {
        'toneladas_formato': 0.0,
        'contagem_formato': 0.0,
        'primeira_contagem': 0.0,
        'ultima_contagem': 0.0
    }
