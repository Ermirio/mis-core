import time
from influxdb import InfluxDBClient
import random
from datetime import datetime

# Configuração
host = 'localhost'
port = 8086
dbname = 'industrial_db'

client = InfluxDBClient(host, port, 'root', 'root', dbname)

# Dados atuais (baseados no que vimos)
op = '2222222'
sku = '444556856'
descricao = 'BRILHANTE LIMPEZA TOTAL'
equipamento = '003' # Zuchinni (Encaixotadora - Final da linha)
meta = 15.6 # Assumindo que a meta é 15.6 tons

# Contagem inicial
contagem = 1000

print(f"Simulando produção para OP {op} no equipamento {equipamento}...")

for i in range(10):
    contagem += random.randint(50, 100) # Incrementa contagem
    
    json_body = [
        {
            "measurement": "producao",
            "tags": {
                "equipamento_codigo": equipamento,
                "linha_codigo": "L01",
                "ordem_producao": op,
                "sku_codigo": sku
            },
            "time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            "fields": {
                "contagem_saida": int(contagem),
                "velocidade_atual": 50.0,
                "estado": "PRODUZINDO",
                "descricao": descricao,
                "planejado_op": float(meta)
            }
        }
    ]
    
    client.write_points(json_body)
    print(f"Escreveu ponto: Contagem={contagem}, Meta={meta}")
    time.sleep(2)

print("Simulação concluída.")
