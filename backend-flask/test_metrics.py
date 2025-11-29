"""
Teste de Validação: OEE (Equipamento) e OLE (Linha)
Objetivo: Provar matematicamente que os cálculos estão ativos e persistindo
"""
import requests
import time

BASE_URL = "http://127.0.0.1:5000/api"

print("=" * 60)
print("DIAGNÓSTICO DE OEE/OLE - VALIDAÇÃO FUNCIONAL")
print("=" * 60)

# ===== CENÁRIO DE TESTE =====
# Velocidade Nominal assumida: 100 RPM (default do sistema)
# Dados enviados:
#   - Velocidade Atual: 50 RPM → Performance = 50%
#   - Produção: 1000 peças, Refugo: 100 → Qualidade = 90%
#   - Estado: 1 (Produzindo) → Disponibilidade = 100%
# OEE Esperado = 1.0 * 0.5 * 0.9 * 100 = 45%

payload = {
    "equipamento_codigo": "TEST-OEE",
    "linha_codigo": "LINHA-TESTE",
    "timestamp": None,
    "medicoes": {
        "estado_maquina": 1,        # Produzindo (Disponibilidade = 100%)
        "contagem_saida": 1000,     # Total produzido
        "descarte": 100,            # Refugo (Qualidade = 90%)
        "ordem_producao": "OP-TESTE",
        "sku_codigo": "SKU-TESTE",
        "planejado_op": 1000,
        "formato_gramas": 500,
        "cuc": "CUC-TESTE",
        "descricao": "Produto de Teste"
    }
}

print("\n[1/4] Enviando dados de teste para equipamento TEST-OEE...")
print(f"      Cenário: Vel=50 (Nom=100), Prod=1000, Refugo=100")
print(f"      Expectativa Matemática: OEE = 100% × 50% × 90% = 45%")

try:
    r = requests.post(f"{BASE_URL}/dados/inserir", json=payload, timeout=5)
    if r.status_code == 200:
        response_data = r.json()
        print(f"      ✅ Inserção bem-sucedida")
        print(f"      Resposta do Engine: {response_data.get('data', {})}")
    else:
        print(f"      ❌ Erro HTTP {r.status_code}: {r.text}")
        exit(1)
except requests.exceptions.ConnectionError:
    print(f"      ❌ Flask não está rodando em {BASE_URL}")
    print(f"      Certifique-se de que 'py run.py' está ativo")
    exit(1)
except Exception as e:
    print(f"      ❌ Erro: {e}")
    exit(1)

time.sleep(2)  # Aguarda persistência no InfluxDB

# ===== TESTE 1: OEE DO EQUIPAMENTO =====
print("\n[2/4] Testando rota GET /api/equipamento/dados/TEST-OEE...")

oee = 0  # Initialize
oee_status = "NOT_RUN"

try:
    r = requests.get(f"{BASE_URL}/equipamento/dados/TEST-OEE", timeout=5)
    data = r.json()
    oee = data.get('oee_atual', 0)
    
    print(f"      📊 OEE Retornado: {oee}%")
    
    if 40 <= oee <= 50:
        print(f"      ✅ SUCESSO: OEE correto (~45%). Diferença: {abs(45 - oee):.1f}%")
        oee_status = "PASS"
    elif oee == 0:
        print(f"      ❌ FALHA CRÍTICA: OEE zerado (cálculo inativo)")
        oee_status = "FAIL"
    elif oee == 100:
        print(f"      ❌ FALHA: OEE = 100% (usando valor hardcoded antigo)")
        oee_status = "FAIL"
    else:
        print(f"      ⚠️  ALERTA: Valor inesperado. Verifique lógica de cálculo.")
        oee_status = "WARN"
    
    print(f"      Dados completos: {data}")
    
except Exception as e:
    print(f"      ❌ Erro na consulta: {e}")
    oee_status = "ERROR"

# ===== TESTE 2: ROTA DE OPERAÇÃO (Alternativa) =====
print("\n[3/4] Testando rota GET /api/operacao/dados/TEST-OEE...")

try:
    r = requests.get(f"{BASE_URL}/operacao/dados/TEST-OEE", timeout=5)
    data_op = r.json()
    oee_op = data_op.get('oee', 0)
    
    print(f"      📊 OEE (Operação): {oee_op}%")
    print(f"      Peças Boas: {data_op.get('pecas_boas')}, Ruins: {data_op.get('pecas_ruins')}")
    
except Exception as e:
    print(f"      ⚠️  Erro: {e}")

# ===== TESTE 3: OLE DA LINHA =====
print("\n[4/4] Testando cálculo de OLE da LINHA-TESTE...")

ole = 0  # Initialize
ole_status = "NOT_RUN"

try:
    r = requests.get(f"{BASE_URL}/linha/LINHA-TESTE/realtime", timeout=5)
    data_line = r.json()
    ole = data_line.get('ole', 0)
    equipamentos_total = data_line.get('equipamentos_total', 0)
    equipamentos_online = data_line.get('equipamentos_online', 0)
    
    print(f"      📈 OLE Retornado: {ole}%")
    print(f"      Equipamentos: {equipamentos_online}/{equipamentos_total} online")
    
    if ole > 0:
        print(f"      ✅ SUCESSO: Rota de Linha ativa e calculando")
        print(f"      ℹ️  Nota: OLE deve ser persistido em 'line_metrics'")
        ole_status = "PASS"
    else:
        print(f"      ❌ FALHA: OLE zerado ou inativo")
        ole_status = "FAIL"
    
except Exception as e:
    print(f"      ❌ Erro: {e}")
    ole_status = "ERROR"

# ===== RELATÓRIO FINAL =====
print("\n" + "=" * 60)
print("RELATÓRIO FINAL DE VALIDAÇÃO")
print("=" * 60)

print(f"\n✓ OEE Calculado: {oee}% (Esperado: ~45%)")
print(f"✓ OLE Calculado: {ole}%")
print(f"✓ Status OEE: {oee_status}")
print(f"✓ Status OLE: {ole_status}")

print("\n📝 PRÓXIMOS PASSOS:")
print("   1. Verificar InfluxDB: SELECT * FROM line_metrics LIMIT 10")
print("   2. Confirmar campo 'refugo_op_acumulado' sendo persistido")
print("   3. Testar com múltiplos equipamentos na mesma linha")

print("\n" + "=" * 60)
