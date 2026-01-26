from equipamentos.models import Equipamento
from equipamentos.influx_helpers import get_influx_client
from django.utils import timezone
import datetime

def debug_balanco_massa():
    client = get_influx_client()
    eq = Equipamento.objects.filter(nome__icontains="ACMA").first()
    
    print(f"DEBUG: Verificando Balanço de Massa para {eq.nome} ({eq.codigo})")
    
    agora = timezone.now()
    inicio = agora - datetime.timedelta(hours=24)
    start_str = inicio.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    query = f"""
        SELECT "contagem_entrada", "contagem_saida", "estado_maquina" 
        FROM "production" 
        WHERE "equipment" = '{eq.codigo}' 
        AND time >= '{start_str}' 
        ORDER BY time DESC 
        LIMIT 20
    """
    
    rs = client.query(query)
    points = list(rs.get_points())
    
    for p in points:
        ent = p.get('contagem_entrada')
        sai = p.get('contagem_saida')
        diff = (ent - sai) if (ent is not None and sai is not None) else None
        print(f"Time: {p['time']} | Ent: {ent} | Sai: {sai} | Diff (Refugo?): {diff}")

debug_balanco_massa()
