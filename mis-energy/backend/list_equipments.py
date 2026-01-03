
import requests

BASE_URL = "http://localhost:5005/api" # Corrigido para 5005 conforme docker-compose

def list_equipments():
    try:
        url = f"{BASE_URL}/equipments"
        print(f"Listando equipamentos de: {url}")
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json().get('data', [])
            print(f"Total de equipamentos: {len(data)}")
            for eq in data:
                print(f"ID: {eq['id']} - Nome: {eq['name']}")
        else:
            print(f"Erro: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Erro de conexão: {e}")

if __name__ == "__main__":
    list_equipments()
