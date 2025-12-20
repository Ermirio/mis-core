import requests
from datetime import datetime, timedelta

def check_shifts():
    url = "http://127.0.0.1:8000/api/turnos/?ativo=true"
    try:
        resp = requests.get(url)
        data = resp.json()
        results = data.get('results', data)
        
        print(f"Found {len(results)} active shifts:")
        turnos = []
        for t in results:
            print(f"- {t['nome']}: {t['hora_inicio']} - {t['hora_fim']}")
            turnos.append({
                'nome': t['nome'],
                'inicio': datetime.strptime(t['hora_inicio'], '%H:%M:%S').time(),
                'fim': datetime.strptime(t['hora_fim'], '%H:%M:%S').time()
            })
            
        now = datetime.now()
        now_time = now.time()
        print(f"\nCurrent Time: {now_time}")
        
        detected = None
        for t in turnos:
            if t['inicio'] > t['fim']: # Night shift crossing midnight
                if now_time >= t['inicio'] or now_time < t['fim']:
                    detected = t['nome']
                    break
            else:
                if t['inicio'] <= now_time < t['fim']:
                    detected = t['nome']
                    break
                    
        print(f"Detected Shift: {detected}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_shifts()
