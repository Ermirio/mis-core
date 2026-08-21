import requests
import json

BASE_URL = "http://localhost:3000/flask-api"

payloads = [
    {
        "equipamento_codigo": "E001",
        "linha_codigo": "L01",
        "medicoes": {
            "contagem_saida": 2036,
            "descarte": 5149,
            "formato_gramas": 3500,
            "velocidade_atual": 100,
            "estado_maquina": 1,
            "sku_codigo": "35555552",
            "descricao": "Prod Teste ACMA"
        }
    },
    {
        "equipamento_codigo": "E002",
        "linha_codigo": "L01",
        "medicoes": {
            "contagem_saida": 2300,
            "descarte": 5400,
            "formato_gramas": 3500,
            "velocidade_atual": 100,
            "estado_maquina": 1,
            "sku_codigo": "35555552",
             "descricao": "Prod Teste ZUC"
        }
    }
]

for p in payloads:
    code = p['equipamento_codigo']
    print(f"Injecting {code}...")
    try:
        r = requests.post(f"{BASE_URL}/dados/inserir", json=p, timeout=5)
        print(f"Status: {r.status_code}")
        print(f"Resp: {r.text}")
    except Exception as e:
        print(f"Error: {e}")
