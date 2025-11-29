from datetime import datetime
import requests

print("="*60)
print("VERIFICACAO COMPLETA DO SISTEMA")
print("="*60)

now = datetime.now().time()
print(f"\n1. HORA ATUAL: {now.hour:02d}:{now.minute:02d}:{now.second:02d}")

# Buscar turnos
r = requests.get('http://localhost:8000/api/turnos/?ativo=true')
turnos = r.json()['results']

print(f"\n2. TURNOS CADASTRADOS ({len(turnos)} turnos):")
for t in turnos:
    print(f"   {t['nome']:12}: {t['hora_inicio']} -> {t['hora_fim']} ({t['duracao_horas']}h)")

# Testar lógica
print(f"\n3. TESTE DE DETECCAO:")
turno_match = None
for t in turnos:
    inicio = datetime.strptime(t['hora_inicio'], '%H:%M:%S').time()
    fim = datetime.strptime(t['hora_fim'], '%H:%M:%S').time()
    
    if inicio > fim:  # Cruza meia-noite
        match = now >= inicio or now < fim
    else:  # Normal
        match = inicio <= now < fim
    
    status = ">>> MATCH <<<" if match else "Nao match"
    print(f"   {t['nome']:12}: {status}")
    if match:
        turno_match = t['nome']

print(f"\n4. RESULTADO DA LOGICA:")
print(f"   Turno detectado: {turno_match if turno_match else 'Fora de Turno'}")

# Testar ProductionEngine
import sys
sys.path.insert(0, '.')
from production_engine import get_engine
from influxdb import InfluxDBClient

client = InfluxDBClient('localhost', 8086, 'admin', 'ixvq10A@10', 'industrial_db')
engine = get_engine(client, 'http://localhost:8000/api')
turno_engine = engine.shift_manager.get_turno_atual()

print(f"\n5. PRODUCTION ENGINE:")
print(f"   Turno detectado: {turno_engine}")

# Testar API Flask
r = requests.get('http://localhost:5000/api/operacao/dados/E001')
turno_api = r.json().get('turno_atual', 'N/A')

print(f"\n6. API FLASK (/api/operacao/dados/E001):")
print(f"   turno_atual: {turno_api}")
print(f"   produzido_turno: {r.json().get('produzido_turno', 0)}")

print(f"\n{'='*60}")
print("DIAGNOSTICO:")
print(f"{'='*60}")
if turno_match == turno_engine == turno_api:
    print("TUDO CONSISTENTE!")
else:
    print("INCONSISTENCIA DETECTADA:")
    print(f"  Logica: {turno_match}")
    print(f"  Engine: {turno_engine}")
    print(f"  API: {turno_api}")
print(f"{'='*60}\n")
