from influxdb import InfluxDBClient
from decouple import config

client = InfluxDBClient(host='influxdb', port=8086, username='admin', password='admin123', database='industrial_db')

def check_current():
    print("--- STATUS ATUAL DOS EQUIPAMENTOS ---")
    try:
        # Get all equipments
        rs = client.query("SHOW TAG VALUES FROM production WITH KEY = \"equipment\"")
        equipments = [p['value'] for p in rs.get_points()]
        
        for eq in equipments:
            # Get latest entry
            q = f"SELECT last(sku_codigo_field), last(velocidade_atual), last(estado_maquina) FROM production WHERE equipment = '{eq}'"
            rs = client.query(q)
            points = list(rs.get_points())
            
            if points:
                p = points[0]
                sku = p.get('last')
                vel = p.get('last_1')
                state = p.get('last_2')
                print(f"Equipamento: {eq} | SKU: {sku} | Velocidade: {vel} | Estado: {state}")
            else:
                print(f"Equipamento: {eq} | Sem dados recentes.")
                
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    check_current()
