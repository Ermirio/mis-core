from equipamentos.models import MetricaProducao, LinhaProducao
from django.db.models import Sum

def debug_sql_metrics():
    print("Consultando MetricaProducao (SQL)...")
    linha = LinhaProducao.objects.first()
    if not linha:
        print("Nenhuma linha encontrada.")
        return

    # Buscar métricas com descarte > 0 nos últimos 30 dias
    metricas = MetricaProducao.objects.filter(
        linha=linha,
        descarte__gt=0
    ).order_by('-data_hora')[:10]
    
    print(f"Total de registros com descarte > 0 encontrados: {len(metricas)}")
    
    for m in metricas:
        print(f"Data: {m.data_hora} | Periodo: {m.periodo} | Eq: {m.equipamento} | Descarte: {m.descarte} | Tons: {m.toneladas_produzidas}")

    # Soma total
    total = MetricaProducao.objects.filter(linha=linha).aggregate(Sum('descarte'))
    print(f"Soma total de descarte na tabela: {total}")

debug_sql_metrics()
