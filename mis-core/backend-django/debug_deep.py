from equipamentos.models import Equipamento
from equipamentos.influx_helpers import get_influx_client
from django.utils import timezone
import datetime

def debug_deep_scan():
    client = get_influx_client()
    eq = Equipamento.objects.filter(nome__icontains="ACMA").first()
    
    print(f"DEBUG DEEP SCAN: {eq.nome} ({eq.codigo})")
    
    # 30 dias
    query = f"""
        SELECT max("descarte") as max_d, sum("descarte") as sum_d
        FROM "production" 
        WHERE "equipment" = '{eq.codigo}' 
        AND time > now() - 30d
    """
    
    rs = client.query(query)
    points = list(rs.get_points())
    print("Resultado SCAN 30 DIAS:", points)
    
    # Verificação das Tags vs Fields
    # Às vezes o dado fica na tag por engano?
    print("\nChecando TAGS...")
    rs_tag = client.query(f"SHOW TAG VALUES FROM \"production\" WITH KEY = \"equipment\" WHERE \"equipment\" = '{eq.codigo}'")
    print(list(rs_tag.get_points()))

debug_deep_scan()
