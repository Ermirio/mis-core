from equipamentos.models import Equipamento
from equipamentos.influx_helpers import get_influx_client
from django.utils import timezone
import datetime

def debug_descarte_field():
    client = get_influx_client()
    eq = Equipamento.objects.filter(nome__icontains="ACMA").first()
    
    print(f"DEBUG: Verificando campo 'descarte' para {eq.nome} ({eq.codigo})")
    
    agora = timezone.now()
    inicio = agora - datetime.timedelta(hours=24)
    start_str = inicio.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Query campo 'descarte'
    query = f"""
        SELECT "descarte", "estado_maquina" 
        FROM "production" 
        WHERE "equipment" = '{eq.codigo}' 
        AND time >= '{start_str}' 
        ORDER BY time DESC 
        LIMIT 20
    """
    
    rs = client.query(query)
    points = list(rs.get_points())
    
    print(f"DEBUG: Encontrados {len(points)} pontos.")
    for p in points:
        print(f"Time: {p['time']} | Descarte: {p.get('descarte')} | Estado: {p.get('estado_maquina')}")

debug_descarte_field()
