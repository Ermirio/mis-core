from equipamentos.models import Equipamento, LinhaProducao
from equipamentos.influx_helpers import get_influx_client
from django.utils import timezone
import datetime

def debug_waste():
    client = get_influx_client()
    # Buscar ACMA da Linha 01 (sabemos que teve descarte)
    eq = Equipamento.objects.filter(nome__icontains="ACMA").first()
    if not eq:
        print("Equipamento ACMA não encontrado.")
        return

    print(f"Verificando equipamento: {eq.nome} ({eq.codigo})")
    
    # Definir intervalo amplo (últimas 24h)
    agora = timezone.now()
    inicio = agora - datetime.timedelta(hours=24)
    
    start_str = inicio.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_str = agora.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    print(f"Intervalo: {start_str} a {end_str}")
    
    # 1. Query Bruta de Refugo
    query = f"""
        SELECT "refugo_op_acumulado", "estado_maquina" 
        FROM "production" 
        WHERE "equipment" = '{eq.codigo}' 
        AND time >= '{start_str}' AND time <= '{end_str}'
        ORDER BY time DESC
        LIMIT 20
    """
    
    print("\n--- Últimos 20 pontos brutos ---")
    rs = client.query(query)
    points = list(rs.get_points())
    
    if not points:
        print("Nenhum ponto encontrado no InfluxDB para este período.")
    else:
        for p in points:
            print(f"Time: {p['time']} | Refugo: {p.get('refugo_op_acumulado')} | Estado: {p.get('estado_maquina')}")

    # 2. Verificar se houve DELTA
    if len(points) > 1:
        first = points[-1].get('refugo_op_acumulado')
        last = points[0].get('refugo_op_acumulado')
        print(f"\nPrimeiro valor (janela): {first}")
        print(f"Último valor (janela): {last}")
        
        try:
            diff = float(last) - float(first)
            print(f"Diferença bruta: {diff}")
        except:
            print("Erro ao calcular diferença (valores nulos?)")

debug_waste()
