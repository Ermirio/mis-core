"""
Utilit\u00e1rios de C\u00e1lculo de Tonelagem
===================================
Fun\u00e7\u00f5es para calcular produ\u00e7\u00e3o em toneladas baseado no formato (peso) do produto.

F\u00f3rmulas:
- Toneladas = (Pe\u00e7as Boas \u00d7 Formato em gramas) / 1.000.000
- Vaz\u00e3o (ton/h) = (Toneladas / Tempo em minutos) \u00d7 60
"""

import logging

logger = logging.getLogger(__name__)


def calcular_toneladas(contagem_saida: int, formato_gramas: float) -> float:
    """
    Calcula toneladas produzidas a partir de pe\u00e7as boas e formato
    
    Args:
        contagem_saida: N\u00famero de pe\u00e7as boas produzidas
        formato_gramas: Peso unit\u00e1rio do produto em gramas
    
    Returns:
        Toneladas produzidas (3 casas decimais)
    
    Examples:
        >>> calcular_toneladas(5000, 2200)  # 5000 garrafas de 2200g
        11.0
        >>> calcular_toneladas(10000, 1600)  # 10000 garrafas de 1600g
        16.0
    """
    if not formato_gramas or formato_gramas <= 0:
        return 0.0
    
    if contagem_saida < 0:
        logger.warning(f"Contagem negativa recebida: {contagem_saida}")
        return 0.0
    
    toneladas = (contagem_saida * formato_gramas) / 1_000_000
    return round(toneladas, 3)


def calcular_vazao_ton_hora(toneladas: float, tempo_producao_min: float) -> float:
    """
    Calcula vaz\u00e3o em toneladas por hora
    
    Args:
        toneladas: Toneladas produzidas
        tempo_producao_min: Tempo de produ\u00e7\u00e3o em minutos
    
    Returns:
        Vaz\u00e3o em ton/h (3 casas decimais)
    
    Examples:
        >>> calcular_vazao_ton_hora(11.0, 60)  # 11 ton em 60 min
        11.0
        >>> calcular_vazao_ton_hora(5.5, 30)  # 5.5 ton em 30 min
        11.0
    """
    if tempo_producao_min <= 0:
        return 0.0
    
    if toneladas < 0:
        logger.warning(f"Toneladas negativas recebidas: {toneladas}")
        return 0.0
    
    vazao = (toneladas / tempo_producao_min) * 60
    return round(vazao, 3)


def obter_formato_equipamento(equipamento) -> float:
    """
    Busca o formato (peso em gramas) configurado para o equipamento
    
    Args:
        equipamento: Inst\u00e2ncia do modelo Equipamento
    
    Returns:
        Formato em gramas ou None se n\u00e3o configurado
    
    Note:
        Busca na primeira tag de coleta que tenha o campo 'formato' preenchido.
        Se m\u00faltiplas tags tiverem formato, usa a primeira encontrada.
    """
    try:
        # Buscar tag de coleta com formato configurado
        tag_formato = equipamento.tags_coleta.filter(
            formato__isnull=False
        ).first()
        
        if tag_formato and tag_formato.formato:
            formato = float(tag_formato.formato)
            if formato > 0:
                return formato
            else:
                logger.warning(
                    f"Formato inv\u00e1lido para {equipamento.nome}: {formato}g"
                )
                return None
        
        logger.debug(f"Nenhum formato configurado para {equipamento.nome}")
        return None
        
    except Exception as e:
        logger.error(
            f"Erro ao buscar formato para {equipamento.nome}: {e}"
        )
        return None


def calcular_toneladas_periodo(metricas_queryset) -> dict:
    """
    Calcula totais de tonelagem para um conjunto de m\u00e9tricas
    
    Args:
        metricas_queryset: QuerySet de MetricaProducao
    
    Returns:
        Dict com totais agregados:
        {
            'toneladas_total': float,
            'vazao_media': float,
            'tempo_total_min': float
        }
    
    Example:
        >>> metricas = MetricaProducao.objects.filter(periodo='HORA', ...)
        >>> totais = calcular_toneladas_periodo(metricas)
        >>> print(totais['toneladas_total'])
        45.823
    """
    from django.db.models import Sum, Avg
    
    agregados = metricas_queryset.aggregate(
        toneladas_total=Sum('toneladas_produzidas'),
        vazao_media=Avg('vazao_real_ton_hora'),
        tempo_total=Sum('tempo_producao')
    )
    
    return {
        'toneladas_total': round(agregados['toneladas_total'] or 0.0, 3),
        'vazao_media': round(agregados['vazao_media'] or 0.0, 3),
        'tempo_total_min': agregados['tempo_total'] or 0.0
    }