import requests
from influxdb import InfluxDBClient
from decouple import config

DJANGO_API_URL = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')
INFLUXDB_HOST = config('INFLUXDB_HOST', default='localhost')
INFLUXDB_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUXDB_USER = config('INFLUXDB_USER', default='admin')
INFLUXDB_USER_PASSWORD = config('INFLUXDB_USER_PASSWORD', default='')
INFLUXDB_DATABASE = config('INFLUXDB_DATABASE', default='industrial_db')

ESTADOS_MAQUINA = {
    0: "Desconhecido",
    1: "Produzindo",
    2: "Aguardando",
    3: "Bloqueado",
    4: "Parado",
    5: "Setup",
    6: "Teste",
    7: "Manutenção",
    8: "Falha",
    9: "Outro"
}

def get_primeiro_equipamento_por_linha():
    mapping = {}
    try:
        resp = requests.get(f"{DJANGO_API_URL}/linhas/", timeout=3)
        if not resp.ok:
            print(f"Erro ao buscar linhas: {resp.status_code}")
            return mapping
        data = resp.json()
        linhas = data.get('results', data) if isinstance(data, dict) else data

        for linha in linhas:
            line_code = linha.get('codigo')
            line_id = linha.get('id')
            if not line_code or not line_id:
                continue

            r_eq = requests.get(
                f"{DJANGO_API_URL}/equipamentos/",
                params={"linha": line_id},
                timeout=3
            )
            if not r_eq.ok:
                print(f"Erro ao buscar equipamentos para linha {line_id}: {r_eq.status_code}")
                continue

            eqs_data = r_eq.json()
            eqs_list = eqs_data.get('results', eqs_data) if isinstance(eqs_data, dict) else eqs_data

            eqs_ordenados = sorted(
                eqs_list,
                key=lambda e: e.get('ordem_na_linha') or 999
            )

            if eqs_ordenados:
                first_eq = eqs_ordenados[0]
                print(f"Linha {line_code}: 1º Equipamento = {first_eq.get('codigo')} (Ordem: {first_eq.get('ordem_na_linha')})")
                mapping[line_code] = first_eq.get('codigo')
            else:
                print(f"Linha {line_code}: Sem equipamentos")
                
    except Exception as e:
        print(f"Erro geral: {e}")
    return mapping

def check_influx_status(line_code, first_eq_code):
    client = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT, username=INFLUXDB_USER, password=INFLUXDB_USER_PASSWORD, database=INFLUXDB_DATABASE)
    
    print(f"\nVerificando InfluxDB para {first_eq_code}...")
    q_state = f"SELECT last(estado_maquina) as state FROM production WHERE \"equipment\" = '{first_eq_code}'"
    rs_state = client.query(q_state)
    pts_state = list(rs_state.get_points())
    
    if pts_state:
        state = int(pts_state[0].get('state', 0) or 0)
        print(f"Estado encontrado: {state} -> {ESTADOS_MAQUINA.get(state, 'Unknown')}")
    else:
        print("Nenhum dado de estado encontrado no InfluxDB.")

if __name__ == "__main__":
    print("--- Debugging Line Status ---")
    mapping = get_primeiro_equipamento_por_linha()
    
    target_line = 'L01'
    if target_line in mapping:
        check_influx_status(target_line, mapping[target_line])
    else:
        print(f"Linha {target_line} não encontrada no mapeamento.")
