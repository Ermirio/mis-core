import requests
from datetime import datetime

def check_calendar():
    # Assuming Line 02 has ID 2 based on previous steps
    linha_id = 2
    date_str = datetime.now().strftime('%Y-%m-%d')
    url = f"http://127.0.0.1:8000/api/calendario/?linha_id={linha_id}&data={date_str}"
    
    print(f"Fetching calendar for Line ID {linha_id} on {date_str}...")
    try:
        resp = requests.get(url)
        data = resp.json()
        results = data.get('results', data)
        
        print(f"Found {len(results)} entries:")
        for entry in results:
            print(f"- Turno: {entry.get('turno_nome')} | Meta: {entry.get('meta_producao_turno')} | Programado: {entry.get('programado')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_calendar()
