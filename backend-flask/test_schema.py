"""
Script para testar e validar o novo schema InfluxDB.
Verifica se os dados estão sendo escritos corretamente nos measurements.
"""
from influxdb import InfluxDBClient
from datetime import datetime, timedelta

# Configuração
INFLUX_HOST = '127.0.0.1'
INFLUX_PORT = 8086
INFLUX_DB = 'industrial_db'
INFLUX_USER = 'admin'
INFLUX_PASS = 'ixvq10A@10'

def test_influx_schema():
    """Testa o novo schema InfluxDB"""
    
    print("=" * 60)
    print("TESTE DO NOVO SCHEMA INFLUXDB")
    print("=" * 60)
    
    try:
        # Conectar ao InfluxDB com autenticação
        print(f"Conectando ao InfluxDB: {INFLUX_HOST}:{INFLUX_PORT}/{INFLUX_DB}")
        print(f"Usuário: {INFLUX_USER}\n")
        
        client = InfluxDBClient(
            host=INFLUX_HOST, 
            port=INFLUX_PORT,
            username=INFLUX_USER,
            password=INFLUX_PASS,
            database=INFLUX_DB
        )
        
        # Testar conexão
        client.ping()
        print(f"✓ Conectado com sucesso!\n")
        
        # 1. Testar measurement 'production'
        print("1. Testando measurement 'production':")
        print("-" * 60)
        
        query = """
            SELECT * FROM production
            ORDER BY time DESC
            LIMIT 5
        """
        
        result = client.query(query)
        points = list(result.get_points())
        
        if points:
            print(f"✓ Encontrados {len(points)} registros recentes\n")
            
            # Mostrar primeiro registro
            first = points[0]
            print("Exemplo de registro:")
            print(f"  Time: {first.get('time')}")
            print(f"  Tags:")
            print(f"    - line: {first.get('line')}")
            print(f"    - equipment: {first.get('equipment')}")
            print(f"    - order_id: {first.get('order_id')}")
            print(f"    - sku: {first.get('sku')}")
            print(f"    - shift: {first.get('shift')}")
            print(f"  Fields:")
            print(f"    - contagem_saida: {first.get('contagem_saida')}")
            print(f"    - velocidade_atual: {first.get('velocidade_atual')}")
            print(f"    - descarte: {first.get('descarte')}")
            print(f"    - formato_gramas: {first.get('formato_gramas')}")
        else:
            print("✗ Nenhum registro encontrado em 'production'")
        
        print()
        
        # 2. Testar measurement 'machine_status'
        print("2. Testando measurement 'machine_status':")
        print("-" * 60)
        
        query = """
            SELECT * FROM machine_status
            ORDER BY time DESC
            LIMIT 5
        """
        
        result = client.query(query)
        points = list(result.get_points())
        
        if points:
            print(f"✓ Encontrados {len(points)} eventos de mudança de estado\n")
            
            # Mostrar eventos
            for i, point in enumerate(points, 1):
                print(f"Evento {i}:")
                print(f"  Time: {point.get('time')}")
                print(f"  Equipment: {point.get('equipment')}")
                print(f"  Estado: {point.get('estado_maquina')}")
                print(f"  Motivo: {point.get('motivo_parada')}")
                print()
        else:
            print("✗ Nenhum evento encontrado em 'machine_status'")
        
        print()
        
        # 3. Estatísticas por equipamento
        print("3. Estatísticas por equipamento (últimas 24h):")
        print("-" * 60)
        
        query = """
            SELECT 
                COUNT(contagem_saida) as registros,
                MEAN(velocidade_atual) as vel_media,
                MAX(contagem_saida) as max_saida
            FROM production
            WHERE time > now() - 24h
            GROUP BY equipment
        """
        
        result = client.query(query)
        
        for series in result:
            equip = series[0][1].get('equipment', 'N/A')
            data = list(series[1])
            if data:
                stats = data[0]
                print(f"Equipamento: {equip}")
                print(f"  Registros: {stats.get('registros', 0)}")
                print(f"  Velocidade média: {stats.get('vel_media', 0):.1f} pç/min")
                print(f"  Máx saída: {stats.get('max_saida', 0)}")
                print()
        
        print("=" * 60)
        print("TESTE CONCLUÍDO")
        print("=" * 60)
        
    except Exception as e:
        print(f"✗ Erro ao testar: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_influx_schema()
