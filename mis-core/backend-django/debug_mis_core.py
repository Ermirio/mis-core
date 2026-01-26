from equipamentos.influx_helpers import get_influx_client
from django.conf import settings

def debug_mis_core_db():
    print("DEBUG: Conectando com get_influx_client (deve usar mis_core_db agora)")
    client = get_influx_client()
    
    # Verificar qual database está selecionado
    # Infelizmente o client python não expõe facilmente, mas vamos confiar na config
    
    print("Measurements em mis_core_db:")
    try:
        rs = client.query("SHOW MEASUREMENTS")
        print(list(rs.get_points()))
        
        # Verificar dados de refugo
        print("\nVerificando production -> descarte (ULTIMAS 24H)...")
        # Usando equipamento E001 (ACMA)
        query = "SELECT count(descarte), sum(descarte), max(descarte) FROM production WHERE time > now() - 24h"
        rs = client.query(query)
        print("Agregados 24h:", list(rs.get_points()))

        query_raw = "SELECT descarte, estado_maquina FROM production WHERE descarte > 0 AND time > now() - 24h LIMIT 10"
        rs = client.query(query_raw)
        print("Pontos > 0:", list(rs.get_points()))
        
    except Exception as e:
        print(f"Erro: {e}")

debug_mis_core_db()
