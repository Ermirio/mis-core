"""
VERIFICAÇÃO COMPLETA DO SISTEMA DE DETECÇÃO DE TURNO
Data/Hora: 2025-11-28 23:02:58
"""
from datetime import datetime
import requests
import json

print("=" * 80)
print("VERIFICAÇÃO COMPLETA - SISTEMA DE DETECÇÃO DE TURNO")
print("=" * 80)

# =========================
# 1. HORA ATUAL DO SISTEMA
# =========================
now = datetime.now()
now_time = now.time()
print(f"\n{'='*80}")
print("1. HORA ATUAL DO SISTEMA")
print(f"{'='*80}")
print(f"   Data/Hora completa: {now}")
print(f"   Apenas hora: {now_time}")
print(f"   Formato HH:MM:SS: {now_time.hour:02d}:{now_time.minute:02d}:{now_time.second:02d}")

# =========================
# 2. TURNOS NO DJANGO
# =========================
print(f"\n{'='*80}")
print("2. TURNOS CADASTRADOS NO DJANGO")
print(f"{'='*80}")
try:
    r = requests.get('http://localhost:8000/api/turnos/?ativo=true', timeout=5)
    if r.status_code == 200:
        data = r.json()
        turnos_raw = data.get('results', data) if isinstance(data, dict) else data
        print(f"   ✓ Conexão bem-sucedida (Status: {r.status_code})")
        print(f"   ✓ Total de turnos ativos: {len(turnos_raw)}")
        print(f"\n   Detalhes dos turnos:")
        for i, t in enumerate(turnos_raw, 1):
            print(f"\n   [{i}] {t['nome']} (ID: {t['id']}, Código: {t['codigo']})")
            print(f"       Horário: {t['hora_inicio']} até {t['hora_fim']}")
            print(f"       Duração: {t['duracao_horas']}h")
            print(f"       Ativo: {'Sim' if t['ativo'] else 'Não'}")
    else:
        print(f"   ✗ Erro na conexão (Status: {r.status_code})")
        turnos_raw = []
except Exception as e:
    print(f"   ✗ ERRO: {e}")
    turnos_raw = []

# =========================
# 3. PROCESSAMENTO DOS TURNOS
# =========================
print(f"\n{'='*80}")
print("3. PROCESSAMENTO DOS TURNOS (Lógica do production_engine.py)")
print(f"{'='*80}")
turnos_processados = []
for t in turnos_raw:
    try:
        inicio = datetime.strptime(t['hora_inicio'], '%H:%M:%S').time()
        fim = datetime.strptime(t['hora_fim'], '%H:%M:%S').time()
        turnos_processados.append({
            'id': t['id'],
            'nome': t['nome'],
            'codigo': t['codigo'],
            'inicio': inicio,
            'fim': fim,
            'duracao': t['duracao_horas']
        })
        print(f"   ✓ {t['nome']:12} processado: {inicio} -> {fim}")
    except Exception as e:
        print(f"   ✗ Erro processando {t.get('nome', '?')}: {e}")

# =========================
# 4. APLICAÇÃO DA LÓGICA
# =========================
print(f"\n{'='*80}")
print("4. APLICAÇÃO DA LÓGICA DE DETECÇÃO")
print(f"{'='*80}")
print(f"   Hora atual para comparação: {now_time}")
print(f"\n   Testando cada turno:\n")

turno_detectado = None
for t in turnos_processados:
    inicio = t['inicio']
    fim = t['fim']
    
    # Verifica se cruza meia-noite
    cruza_meia_noite = inicio > fim
    
    if cruza_meia_noite:
        # Turno cruza meia-noite (ex: 22:00 -> 06:00)
        match = now_time >= inicio or now_time < fim
        tipo = "CRUZA MEIA-NOITE"
        explicacao = f"now({now_time}) >= inicio({inicio}) OU now < fim({fim})"
    else:
        # Turno normal (ex: 06:00 -> 14:00)
        match = inicio <= now_time < fim
        tipo = "NORMAL"
        explicacao = f"inicio({inicio}) <= now({now_time}) < fim({fim})"
    
    resultado = "✓✓ MATCH! ✓✓" if match else "✗ Não match"
    
    print(f"   {t['nome']:12} | Tipo: {tipo:18} | {resultado}")
    print(f"                  Início: {inicio} | Fim: {fim} | Cruza? {cruza_meia_noite}")
    print(f"                  Lógica: {explicacao}")
    print(f"                  Resultado: {match}")
    print()
    
    if match and not turno_detectado:
        turno_detectado = t['nome']

# =========================
# 5. RESULTADO DA LÓGICA
# =========================
print(f"{'='*80}")
print("5. RESULTADO DA LÓGICA DE DETECÇÃO")
print(f"{'='*80}")
if turno_detectado:
    print(f"   ✓✓✓ TURNO DETECTADO: {turno_detectado}")
else:
    print(f"   ✗✗✗ NENHUM TURNO DETECTADO")
    print(f"   Retorno: 'Fora de Turno'")

# =========================
# 6. TESTE DO PRODUCTION ENGINE REAL
# =========================
print(f"\n{'='*80}")
print("6. TESTE COM PRODUCTION ENGINE REAL (app.py)")
print(f"{'='*80}")
try:
    import sys
    sys.path.insert(0, 'c:/Users/ermir/Documents/GitHub/projeto-monitoramento-industrial-completo/backend-flask')
    from production_engine import get_engine
    from influxdb import InfluxDBClient
    
    client = InfluxDBClient('localhost', 8086, 'admin', 'ixvq10A@10', 'industrial_db')
    engine = get_engine(client, 'http://localhost:8000/api')
    
    turno_engine = engine.shift_manager.get_turno_atual()
    print(f"   ✓ ProductionEngine conectado")
    print(f"   Turno detectado pelo engine: '{turno_engine}'")
    
    if turno_engine == turno_detectado:
        print(f"   ✓✓ CONSISTENTE com lógica manual!")
    else:
        print(f"   ✗✗ INCONSISTENTE! Esperado: '{turno_detectado}', Recebido: '{turno_engine}'")
except Exception as e:
    print(f"   ✗ Erro ao testar ProductionEngine: {e}")

# =========================
# 7. TESTE DA API FLASK
# =========================
print(f"\n{'='*80}")
print("7. TESTE DAS APIs FLASK (Dados Reais)")
print(f"{'='*80}")

# 7.1 - API de Operação
try:
    r = requests.get('http://localhost:5000/api/operacao/dados/E001', timeout=5)
    if r.status_code == 200:
        data = r.json()
        print(f"   ✓ GET /api/operacao/dados/E001 (Status: {r.status_code})")
        print(f"     turno_atual: '{data.get('turno_atual', 'N/A')}'")
        print(f"     ordem_producao: {data.get('ordem_producao', 'N/A')}")
        print(f"     produzido_turno: {data.get('produzido_turno', 0)}")
    else:
        print(f"   ✗ Erro (Status: {r.status_code})")
except Exception as e:
    print(f"   ✗ Erro: {e}")

# 7.2 - API de Equipamento
try:
    r = requests.get('http://localhost:5000/api/equipamento/dados/E001', timeout=5)
    if r.status_code == 200:
        data = r.json()
        print(f"\n   ✓ GET /api/equipamento/dados/E001 (Status: {r.status_code})")
        print(f"     estado_atual: {data.get('estado_atual', 'N/A')}")
        print(f"     velocidade_atual: {data.get('velocidade_atual', 0)}")
    else:
        print(f"   ✗ Erro (Status: {r.status_code})")
except Exception as e:
    print(f"   ✗ Erro: {e}")

# =========================
# 8. ANÁLISE DE COBERTURA
# =========================
print(f"\n{'='*80}")
print("8. ANÁLISE DE COBERTURA DE TURNOS (24 HORAS)")
print(f"{'='*80}")

if turnos_processados:
    # Ordenar por hora de início
    turnos_ordenados = sorted(turnos_processados, key=lambda x: x['inicio'])
    
    print(f"\n   Turnos ordenados por horário de início:")
    for t in turnos_ordenados:
        cruza = " (CRUZA MEIA-NOITE)" if t['inicio'] > t['fim'] else ""
        print(f"     {t['nome']:12}: {t['inicio']} -> {t['fim']}{cruza}")
    
    print(f"\n   Verificando gaps/sobreposições:")
    
    # Verificar gaps
    for i in range(len(turnos_ordenados)):
        turno_atual = turnos_ordenados[i]
        proximo = turnos_ordenados[(i + 1) % len(turnos_ordenados)]
        
        if turno_atual['fim'] != proximo['inicio'] and not (turno_atual['inicio'] > turno_atual['fim']):
            if turno_atual['fim'] < proximo['inicio']:
                print(f"     ⚠️  GAP: {turno_atual['fim']} -> {proximo['inicio']} (sem cobertura)")
            elif turno_atual['fim'] > proximo['inicio']:
                print(f"     ⚠️  SOBREPOSIÇÃO: {turno_atual['nome']} e {proximo['nome']}")

# =========================
# 9. DIAGNÓSTICO FINAL
# =========================
print(f"\n{'='*80}")
print("9. DIAGNÓSTICO FINAL")
print(f"{'='*80}")

problemas = []

if not turnos_raw:
    problemas.append("CRÍTICO: Nenhum turno ativo cadastrado no Django")

if not turno_detectado:
    problemas.append(f"CRÍTICO: Horário atual ({now_time}) não está coberto por nenhum turno")

# Verificar se todos os turnos têm 8h ou somam 24h
if turnos_processados:
    total_horas = sum([t['duracao'] for t in turnos_processados])
    if abs(total_horas - 24.0) > 0.1:
        problemas.append(f"AVISO: Total de horas dos turnos ({total_horas}h) != 24h")

# Verificar conflitos de horário
for i, t1 in enumerate(turnos_processados):
    for t2 in turnos_processados[i+1:]:
        if t1['inicio'] == t2['inicio']:
            problemas.append(f"CRÍTICO: Turnos '{t1['nome']}' e '{t2['nome']}' têm mesmo horário de início")

if problemas:
    print(f"\n   ❌ PROBLEMAS IDENTIFICADOS:")
    for i, p in enumerate(problemas, 1):
        print(f"      [{i}] {p}")
else:
    print(f"\n   ✅ TUDO OK! Sistema funcionando corretamente.")

print(f"\n{'='*80}")
print("FIM DA VERIFICAÇÃO COMPLETA")
print(f"{'='*80}\n")
