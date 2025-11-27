#!/usr/bin/env python3
"""
Simulador de Produção Industrial
Simula dados de 4 equipamentos e envia para Flask API
"""

import requests
import time
import random
from datetime import datetime

# Configuração
FLASK_API_URL = "http://localhost:5000/api/dados/inserir"
INTERVALO_SEGUNDOS = 5  # Envia dados a cada 5 segundos

# Configuração dos equipamentos
EQUIPAMENTOS = {
    'Enchedora_01': {
        'velocidade_base': 100,
        'temp_min': 65, 'temp_max': 85,
        'pressao_min': 85, 'pressao_max': 115,
        'estados': ['Produzindo', 'Produzindo', 'Produzindo', 'Parada', 'Setup']
    },
    'Balanca_01': {
        'velocidade_base': 80,
        'temp_min': 18, 'temp_max': 28,
        'pressao_min': 55, 'pressao_max': 75,
        'estados': ['Produzindo', 'Produzindo', 'Produzindo', 'Parada']
    },
    'Encaixotadora_01': {
        'velocidade_base': 60,
        'temp_min': 18, 'temp_max': 32,
        'pressao_min': 65, 'pressao_max': 95,
        'estados': ['Produzindo', 'Produzindo', 'Parada', 'Setup']
    },
    'Envolvedora_01': {
        'velocidade_base': 50,
        'temp_min': 22, 'temp_max': 38,
        'pressao_min': 45, 'pressao_max': 65,
        'estados': ['Produzindo', 'Produzindo', 'Produzindo', 'Parada']
    }
}

# Contadores de produção
contadores = {nome: 0 for nome in EQUIPAMENTOS.keys()}

def gerar_medicoes(equipamento_nome, config):
    """Gera medições simuladas para um equipamento"""
    global contadores
    
    # Estado aleatório (mais chance de estar produzindo)
    estado = random.choice(config['estados'])
    
    # Velocidade (varia ±10% da base se produzindo, 0 se parado)
    if estado == 'Produzindo':
        velocidade = config['velocidade_base'] * random.uniform(0.9, 1.1)
        incremento = int(velocidade * INTERVALO_SEGUNDOS / 60)  # Conversão para unidades
        
        # Simula descarte (1% a 3% de chance de gerar descarte no ciclo)
        descarte_ciclo = 0
        if random.random() < 0.3: # 30% dos ciclos tem algum descarte
             descarte_ciclo = int(incremento * random.uniform(0.01, 0.05))
        
        contadores[equipamento_nome]['entrada'] += incremento
        contadores[equipamento_nome]['descarte'] += descarte_ciclo
        contadores[equipamento_nome]['saida'] = contadores[equipamento_nome]['entrada'] - contadores[equipamento_nome]['descarte']

    elif estado == 'Setup':
        velocidade = config['velocidade_base'] * random.uniform(0.3, 0.5)
        incremento = int(velocidade * INTERVALO_SEGUNDOS / 60 * 0.3)
        contadores[equipamento_nome]['entrada'] += incremento
        # Setup gera mais descarte
        descarte_ciclo = int(incremento * random.uniform(0.1, 0.2))
        contadores[equipamento_nome]['descarte'] += descarte_ciclo
        contadores[equipamento_nome]['saida'] = contadores[equipamento_nome]['entrada'] - contadores[equipamento_nome]['descarte']
    else:  # Parada
        velocidade = 0
    
    # Temperatura (varia dentro do range)
    temperatura = random.uniform(config['temp_min'], config['temp_max'])
    
    # Pressão (varia dentro do range)
    pressao = random.uniform(config['pressao_min'], config['pressao_max'])
    
    return {
        'temperatura': round(temperatura, 2),
        'pressao': round(pressao, 2),
        'velocidade_atual': round(velocidade, 2),
        'contagem_entrada': contadores[equipamento_nome],
        'contagem_saida': contadores[equipamento_nome],
        'estado': estado
    }

def enviar_dados(equipamento, medicoes):
    """Envia dados para a API Flask"""
    try:
        payload = {
            'equipamento': equipamento,
            'medicoes': medicoes
        }
        
        response = requests.post(FLASK_API_URL, json=payload, timeout=5)
        
        if response.status_code == 200:
            return True
        else:
            print(f"❌ Erro ao enviar dados de {equipamento}: {response.status_code}")
            return False
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro de conexão ao enviar dados de {equipamento}: {e}")
        return False

def main():
    """Loop principal do simulador"""
    print("=" * 70)
    print("🏭 SIMULADOR DE PRODUÇÃO INDUSTRIAL")
    print("=" * 70)
    print(f"\nEquipamentos configurados: {len(EQUIPAMENTOS)}")
    for nome in EQUIPAMENTOS.keys():
        print(f"  • {nome}")
    print(f"\nIntervalo de envio: {INTERVALO_SEGUNDOS} segundos")
    print(f"API Flask: {FLASK_API_URL}")
    print("\nIniciando simulação...\n")
    
    ciclo = 0
    
    try:
        while True:
            ciclo += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            print(f"[{timestamp}] Ciclo #{ciclo}")
            print("-" * 70)
            
            for equipamento_nome, config in EQUIPAMENTOS.items():
                # Gera medições
                medicoes = gerar_medicoes(equipamento_nome, config)
                
                # Envia para API
                sucesso = enviar_dados(equipamento_nome, medicoes)
                
                # Log
                status_icon = "✓" if sucesso else "✗"
                print(f"  {status_icon} {equipamento_nome:20} | "
                      f"Estado: {medicoes['estado']:12} | "
                      f"Vel: {medicoes['velocidade_atual']:6.2f} | "
                      f"Temp: {medicoes['temperatura']:5.2f}°C | "
                      f"Press: {medicoes['pressao']:6.2f} PSI | "
                      f"Total: {medicoes['contagem_saida']:6}")
            
            print()
            time.sleep(INTERVALO_SEGUNDOS)
    
    except KeyboardInterrupt:
        print("\n\n🛑 Simulação interrompida pelo usuário")
        print(f"\nTotal de ciclos executados: {ciclo}")
        print("\nContadores finais:")
        for equipamento, total in contadores.items():
            print(f"  • {equipamento}: {total} unidades")
    
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")

if __name__ == '__main__':
    main()
