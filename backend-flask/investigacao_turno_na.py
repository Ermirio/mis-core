"""
INVESTIGAÇÃO COMPLETA - Por que API retorna N/A para turno
"""
from datetime import datetime
import requests
from influxdb import InfluxDBClient
import sys
sys.path.insert(0, '.')
from production_engine import get_engine

print("="*80)
print("INVESTIGAÇÃO COMPLETA - TURNO N/A")
print(f"Hora atual: {datetime.now()}")
print("="*80)

# 1. PRODUCTION ENGINE - O que detecta?
print("\n1. PRODUCTION ENGINE - Detecção de Turno:")
try:
    client = InfluxDBClient('localhost', 8086, 'admin', 'ixvq10A@10', 'industrial_db')
    engine = get_engine(client, 'http://localhost:8000/api')
    turno_detectado = engine.shift_manager.get_turno_atual()
    print(f"   Turno detectado pelo engine: '{turno_detectado}'")
except Exception as e:
    print(f"   ERRO: {e}")
    turno_detectado = None

# 2. INFLUXDB - O que está salvo?
print("\n2. INFLUXDB - Últimos 10 registros salvos:")
try:
    client = InfluxDBClient('localhost', 8086, 'admin', 'ixvq10A@10', 'industrial_db')
    query = """
        SELECT shift, producao_turno_acumulada, ordem_producao_field 
        FROM production 
        WHERE equipment='E001' 
        ORDER BY time DESC 
        LIMIT 10
    """
    result = client.query(query)
    points = list(result.get_points())
    
    if points:
        print(f"   Total de pontos retornados: {len(points)}")
        print(f"\n   Últimos registros:")
        for i, p in enumerate(points[:5], 1):
            shift = p.get('shift', '(vazio)')
            prod_turno = p.get('producao_turno_acumulada', 0)
            op = p.get('ordem_producao_field', '?')
            print(f"   [{i}] shift='{shift}' | prod_turno={prod_turno} | OP={op}")
    else:
        print("   NENHUM dado encontrado!")
        
except Exception as e:
    print(f"   ERRO: {e}")

# 3. QUERY EXATA DA API - O que a rota production.py faz?
print("\n3. QUERY EXATA QUE A API USA:")
try:
    client = InfluxDBClient('localhost', 8086, 'admin', 'ixvq10A@10', 'industrial_db')
    # Esta é a query EXATA que app/routes/production.py usa (linha 24-26)
    query_api = 'SELECT last(*) FROM production WHERE "equipment" = \'E001\''
    result = client.query(query_api)
    points = list(result.get_points())
    
    if points:
        data = points[0]
        last_shift = data.get('last_shift', 'NÃO ENCONTRADO')
        print(f"   Resultado da query 'SELECT last(*)': ")
        print(f"   last_shift = '{last_shift}'")
        print(f"   last_producao_turno_acumulada = {data.get('last_producao_turno_acumulada', 0)}")
        print(f"   last_ordem_producao_field = {data.get('last_ordem_producao_field', '?')}")
        
        # Verificar se shift existe como campo
        if 'last_shift' in data:
            print(f"\n   ✓ Campo 'last_shift' EXISTE no resultado")
            print(f"   Valor: '{last_shift}'")
            if last_shift in ['N/A', None, '']:
                print(f"   ⚠️  MAS o valor é '{last_shift}' (inválido!)")
        else:
            print(f"\n   ✗ Campo 'last_shift' NÃO EXISTE no resultado!")
            print(f"   Campos disponíveis: {list(data.keys())[:10]}...")
    else:
        print("   NENHUM resultado!")
except Exception as e:
    print(f"   ERRO: {e}")

# 4. API FLASK - O que retorna?
print("\n4. API FLASK - Resposta real:")
try:
    r = requests.get('http://localhost:5000/api/operacao/dados/E001', timeout=5)
    if r.status_code == 200:
        data = r.json()
        print(f"   Status: {r.status_code}")
        print(f"   turno_atual: '{data.get('turno_atual', 'campo não existe')}'")
        print(f"   produzido_turno: {data.get('produzido_turno', 0)}")
        print(f"   ordem_producao: {data.get('ordem_producao', '?')}")
    else:
        print(f"   ERRO Status: {r.status_code}")
except Exception as e:
    print(f"   ERRO: {e}")

# 5. COMPARAÇÃO E DIAGNÓSTICO
print("\n" + "="*80)
print("5. DIAGNÓSTICO:")
print("="*80)

if turno_detectado:
    print(f"✓ ProductionEngine detecta: '{turno_detectado}'")
else:
    print(f"✗ ProductionEngine FALHOU")

try:
    # Verificar se há dados recentes
    client = InfluxDBClient('localhost', 8086, 'admin', 'ixvq10A@10', 'industrial_db')
    result = client.query("SELECT last(shift) FROM production WHERE equipment='E001'")
    points = list(result.get_points())
    if points:
        ultimo_shift = points[0].get('last', 'vazio')
        print(f"✓ Último shift salvo no InfluxDB: '{ultimo_shift}'")
        
        if ultimo_shift == turno_detectado:
            print(f"✓ CONSISTENTE! InfluxDB == ProductionEngine")
        else:
            print(f"✗ INCONSISTENTE! InfluxDB ('{ultimo_shift}') != Engine ('{turno_detectado}')")
            print(f"\n⚠️  POSSÍVEL CAUSA:")
            print(f"   - Coletor não está enviando dados")
            print(f"   - Ou a rota /api/dados/inserir não está salvando o campo 'shift'")
except Exception as e:
    print(f"✗ Erro ao verificar: {e}")

print("\n" + "="*80)
print("FIM DA INVESTIGAÇÃO")
print("="*80)
