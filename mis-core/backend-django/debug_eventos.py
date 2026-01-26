from equipamentos.models import EventoEstadoEquipamento, LinhaProducao
from django.db.models import Sum

def debug_eventos_perda():
    print("Consultando EventoEstadoEquipamento (SQL)...")
    
    # Busca eventos com perda > 0
    eventos = EventoEstadoEquipamento.objects.filter(
        toneladas_perdidas__gt=0
    ).order_by('-inicio')[:10]
    
    print(f"Total de eventos com perda > 0: {len(eventos)}")
    
    for e in eventos:
        print(f"Eq: {e.equipamento.nome} | Estado: {e.estado} | Perda: {e.toneladas_perdidas} t | Inicio: {e.inicio}")

    total = EventoEstadoEquipamento.objects.aggregate(Sum('toneladas_perdidas'))
    print(f"Total Geral de Perdas (t): {total}")

debug_eventos_perda()
