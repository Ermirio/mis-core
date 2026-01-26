from equipamentos.influx_helpers import get_influx_client
import time

def debug_write_test():
    client = get_influx_client()
    print("Tentando escrever ponto de teste...")
    
    # Tentativa 1: Escrever refugo_op_acumulado como INT
    data = [{
        "measurement": "production",
        "tags": {"equipment": "TEST_E001"},
        "fields": {
            "refugo_op_acumulado": 51,
            "descarte": 1,
            "teste_write": 1
        }
    }]
    
    try:
        client.write_points(data)
        print("Write processado (sem exceção).")
    except Exception as e:
        print(f"Erro no Write INT: {e}")
        
    time.sleep(1)
    
    # Verificar se gravou
    rs = client.query("SELECT * FROM production WHERE \"equipment\" = 'TEST_E001'")
    print("Resultado Read:", list(rs.get_points()))

debug_write_test()
