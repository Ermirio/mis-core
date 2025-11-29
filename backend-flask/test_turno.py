"""
Script de diagnóstico para verificar detecção de turno
"""
from datetime import datetime
import requests

print("="*60)
print("DIAGNÓSTICO: Detecção de Turno")
print("="*60)

# 1. Hora atual
now = datetime.now().time()
print(f"\n1. HORA ATUAL: {now}")
print(f"   Formato HH:MM:SS: {now.hour:02d}:{now.minute:02d}:{now.second:02d}")

# 2. Buscar turnos do Django
print("\n2. BUSCANDO TURNOS DO DJANGO...")
try:
    r = requests.get('http://localhost:8000/api/turnos/?ativo=true', timeout=5)
    data = r.json()
    turnos = data.get('results', data) if isinstance(data, dict) else data
    print(f"   Status: {r.status_code}")
    print(f"   Turnos recebidos: {len(turnos)}")
except Exception as e:
    print(f"   ERRO: {e}")
    exit(1)

# 3. Processar turnos
print("\n3. PROCESSANDO TURNOS...")
turnos_processados = []
for t in turnos:
    try:
        inicio = datetime.strptime(t['hora_inicio'], '%H:%M:%S').time()
        fim = datetime.strptime(t['hora_fim'], '%H:%M:%S').time()
        turnos_processados.append({
            'id': t['id'],
            'nome': t['nome'],
            'inicio': inicio,
            'fim': fim
        })
        print(f"   ✓ {t['nome']}: {inicio} até {fim}")
    except Exception as e:
        print(f"   ✗ Erro processando {t.get('nome', 'Unknown')}: {e}")

# 4. Aplicar lógica de detecção
print("\n4. APLICANDO LÓGICA DE DETECÇÃO...")
print(f"   Testando cada turno contra hora atual ({now}):")
print()

turno_encontrado = None
for t in turnos_processados:
    cruza_meia_noite = t['inicio'] > t['fim']
    
    if cruza_meia_noite:
        # Lógica para turno que cruza meia-noite
        match = now >= t['inicio'] or now < t['fim']
        tipo = "CRUZA MEIA-NOITE"
        condicao = f"(now >= {t['inicio']} OR now < {t['fim']})"
    else:
        # Lógica normal
        match = t['inicio'] <= now < t['fim']
        tipo = "NORMAL"
        condicao = f"({t['inicio']} <= now < {t['fim']})"
    
    status = "✓ MATCH!" if match else "✗ Não match"
    print(f"   {t['nome']:12} | Tipo: {tipo:18} | {condicao:45} | {status}")
    
    if match and not turno_encontrado:
        turno_encontrado = t['nome']

# 5. Resultado final
print("\n" + "="*60)
print("RESULTADO FINAL:")
print("="*60)
if turno_encontrado:
    print(f"✓ TURNO DETECTADO: {turno_encontrado}")
else:
    print("✗ NENHUM TURNO DETECTADO - Retornando 'Fora de Turno'")
print("="*60)
