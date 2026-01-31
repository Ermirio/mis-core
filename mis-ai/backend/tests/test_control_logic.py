#!/usr/bin/env python3
"""
Testes para validar a lógica de controle preditivo.

Este script testa:
1. Cálculo de erro (absoluto e percentual)
2. Lógica direta vs reversa
3. Aplicação do fator de relação
4. Limites de ajuste (min/max)
5. Cálculo de novo valor sugerido
"""

import sys
import os

# Adicionar o diretório pai ao path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_error_calculation():
    """Testa cálculo de erro absoluto e percentual"""
    print("\n" + "="*60)
    print("TESTE 1: Cálculo de Erro")
    print("="*60)
    
    test_cases = [
        {"target": 2200, "predicted": 2230, "expected_error": 30, "expected_pct": 1.36},
        {"target": 100, "predicted": 95, "expected_error": -5, "expected_pct": -5.0},
        {"target": 50, "predicted": 50, "expected_error": 0, "expected_pct": 0.0},
        {"target": 1000, "predicted": 1100, "expected_error": 100, "expected_pct": 10.0},
    ]
    
    for i, case in enumerate(test_cases, 1):
        target = case["target"]
        predicted = case["predicted"]
        
        error_value = predicted - target
        error_percentage = (error_value / target) * 100.0 if target != 0 else 0.0
        
        print(f"\nCaso {i}:")
        print(f"  Target: {target}, Predito: {predicted}")
        print(f"  Erro Absoluto: {error_value:.2f} (esperado: {case['expected_error']:.2f})")
        print(f"  Erro Percentual: {error_percentage:.2f}% (esperado: {case['expected_pct']:.2f}%)")
        
        assert abs(error_value - case["expected_error"]) < 0.01, "Erro absoluto incorreto"
        assert abs(error_percentage - case["expected_pct"]) < 0.01, "Erro percentual incorreto"
        print("  ✅ PASSOU")

def test_direct_logic():
    """Testa lógica de controle direta"""
    print("\n" + "="*60)
    print("TESTE 2: Lógica Direta (aumentar controle aumenta target)")
    print("="*60)
    
    test_cases = [
        {
            "error_pct": 1.36,  # Target está baixo
            "relation_factor": 1.0,
            "expected_adjustment": 1.36,  # Aumentar controle
            "description": "Erro positivo → aumentar controle"
        },
        {
            "error_pct": -2.5,  # Target está alto
            "relation_factor": 1.0,
            "expected_adjustment": -2.5,  # Diminuir controle
            "description": "Erro negativo → diminuir controle"
        },
        {
            "error_pct": 5.0,
            "relation_factor": 0.5,
            "expected_adjustment": 2.5,  # 50% do erro
            "description": "Fator de relação 50%"
        },
    ]
    
    for i, case in enumerate(test_cases, 1):
        error_pct = case["error_pct"]
        relation_factor = case["relation_factor"]
        
        # Lógica direta: ajuste = erro * fator
        recommended_adjustment = error_pct * relation_factor
        
        print(f"\nCaso {i}: {case['description']}")
        print(f"  Erro: {error_pct:+.2f}%")
        print(f"  Fator de Relação: {relation_factor:.0%}")
        print(f"  Ajuste Recomendado: {recommended_adjustment:+.2f}%")
        print(f"  Esperado: {case['expected_adjustment']:+.2f}%")
        
        assert abs(recommended_adjustment - case["expected_adjustment"]) < 0.01
        print("  ✅ PASSOU")

def test_reverse_logic():
    """Testa lógica de controle reversa"""
    print("\n" + "="*60)
    print("TESTE 3: Lógica Reversa (aumentar controle diminui target)")
    print("="*60)
    
    test_cases = [
        {
            "error_pct": 1.36,  # Target está baixo (peso abaixo do esperado)
            "relation_factor": 0.8,
            "expected_adjustment": -1.09,  # Diminuir controle (ex: velocidade)
            "description": "Peso baixo → diminuir velocidade (80% do erro)"
        },
        {
            "error_pct": -3.0,  # Target está alto
            "relation_factor": 1.0,
            "expected_adjustment": 3.0,  # Aumentar controle
            "description": "Peso alto → aumentar velocidade"
        },
        {
            "error_pct": 10.0,
            "relation_factor": 0.3,
            "expected_adjustment": -3.0,  # 30% do erro, invertido
            "description": "Fator de relação conservador (30%)"
        },
    ]
    
    for i, case in enumerate(test_cases, 1):
        error_pct = case["error_pct"]
        relation_factor = case["relation_factor"]
        
        # Lógica reversa: ajuste = -erro * fator
        recommended_adjustment = -error_pct * relation_factor
        
        print(f"\nCaso {i}: {case['description']}")
        print(f"  Erro: {error_pct:+.2f}%")
        print(f"  Fator de Relação: {relation_factor:.0%}")
        print(f"  Ajuste Recomendado: {recommended_adjustment:+.2f}%")
        print(f"  Esperado: {case['expected_adjustment']:+.2f}%")
        
        assert abs(recommended_adjustment - case["expected_adjustment"]) < 0.01
        print("  ✅ PASSOU")

def test_adjustment_limits():
    """Testa aplicação de limites de ajuste"""
    print("\n" + "="*60)
    print("TESTE 4: Limites de Ajuste (min/max)")
    print("="*60)
    
    test_cases = [
        {
            "adjustment": 15.0,
            "min_limit": None,
            "max_limit": 10.0,
            "expected": 10.0,
            "description": "Ajuste acima do máximo"
        },
        {
            "adjustment": -8.0,
            "min_limit": -5.0,
            "max_limit": None,
            "expected": -5.0,
            "description": "Ajuste abaixo do mínimo"
        },
        {
            "adjustment": 3.0,
            "min_limit": -10.0,
            "max_limit": 10.0,
            "expected": 3.0,
            "description": "Ajuste dentro dos limites"
        },
    ]
    
    for i, case in enumerate(test_cases, 1):
        adjustment = case["adjustment"]
        min_limit = case["min_limit"]
        max_limit = case["max_limit"]
        
        # Aplicar limites
        if min_limit is not None and adjustment < min_limit:
            adjustment = min_limit
        if max_limit is not None and adjustment > max_limit:
            adjustment = max_limit
        
        print(f"\nCaso {i}: {case['description']}")
        print(f"  Ajuste Original: {case['adjustment']:+.2f}%")
        print(f"  Limites: [{min_limit}, {max_limit}]")
        print(f"  Ajuste Final: {adjustment:+.2f}%")
        print(f"  Esperado: {case['expected']:+.2f}%")
        
        assert abs(adjustment - case["expected"]) < 0.01
        print("  ✅ PASSOU")

def test_new_value_calculation():
    """Testa cálculo do novo valor sugerido"""
    print("\n" + "="*60)
    print("TESTE 5: Cálculo de Novo Valor Sugerido")
    print("="*60)
    
    test_cases = [
        {
            "current_value": 150.0,
            "adjustment_pct": -1.09,
            "expected_new_value": 148.365,
            "description": "Reduzir volume em 1.09%"
        },
        {
            "current_value": 2.5,
            "adjustment_pct": 5.0,
            "expected_new_value": 2.625,
            "description": "Aumentar velocidade em 5%"
        },
        {
            "current_value": 100.0,
            "adjustment_pct": 0.0,
            "expected_new_value": 100.0,
            "description": "Sem ajuste"
        },
    ]
    
    for i, case in enumerate(test_cases, 1):
        current_value = case["current_value"]
        adjustment_pct = case["adjustment_pct"]
        
        # Calcular novo valor
        adjustment_factor = 1.0 + (adjustment_pct / 100.0)
        new_value = current_value * adjustment_factor
        
        print(f"\nCaso {i}: {case['description']}")
        print(f"  Valor Atual: {current_value:.2f}")
        print(f"  Ajuste: {adjustment_pct:+.2f}%")
        print(f"  Novo Valor: {new_value:.3f}")
        print(f"  Esperado: {case['expected_new_value']:.3f}")
        
        assert abs(new_value - case["expected_new_value"]) < 0.01
        print("  ✅ PASSOU")

def test_real_world_scenario():
    """Testa cenário real completo: controle de peso por volume"""
    print("\n" + "="*60)
    print("TESTE 6: Cenário Real - Controle de Peso por Volume")
    print("="*60)
    
    print("\n📋 Contexto:")
    print("  - Target: Peso final de 2200 kg")
    print("  - Modelo prediz: 2230 kg (+30 kg)")
    print("  - Variável de controle: Volume do disco dosador")
    print("  - Lógica: Reversa (↑ volume → ↑ peso)")
    print("  - Fator de relação: 80% (ajuste conservador)")
    print("  - Valor atual do volume: 150.0 L")
    
    # Parâmetros
    target_value = 2200.0
    predicted_value = 2230.0
    current_volume = 150.0
    relation_factor = 0.80
    
    # Cálculos
    error_value = predicted_value - target_value
    error_percentage = (error_value / target_value) * 100.0
    
    # Lógica reversa: peso alto → diminuir volume
    recommended_adjustment = -error_percentage * relation_factor
    
    adjustment_factor = 1.0 + (recommended_adjustment / 100.0)
    recommended_volume = current_volume * adjustment_factor
    
    print("\n📊 Cálculos:")
    print(f"  Erro absoluto: {error_value:+.2f} kg")
    print(f"  Erro percentual: {error_percentage:+.2f}%")
    print(f"  Ajuste recomendado: {recommended_adjustment:+.2f}%")
    print(f"  Volume atual: {current_volume:.2f} L")
    print(f"  Volume sugerido: {recommended_volume:.2f} L")
    print(f"  Diferença: {recommended_volume - current_volume:+.2f} L")
    
    print("\n✅ Interpretação:")
    print(f"  O sistema recomenda REDUZIR o volume em {abs(recommended_adjustment):.2f}%")
    print(f"  (de {current_volume:.2f} L para {recommended_volume:.2f} L)")
    print(f"  Isso deve corrigir o excesso de {error_value:.0f} kg no peso final")
    
    # Validações
    assert error_value > 0, "Erro deve ser positivo (peso acima do alvo)"
    assert recommended_adjustment < 0, "Ajuste deve ser negativo (reduzir volume)"
    assert recommended_volume < current_volume, "Novo volume deve ser menor"
    
    print("\n  ✅ TODOS OS TESTES PASSARAM")

def run_all_tests():
    """Executa todos os testes"""
    print("\n" + "="*60)
    print("INICIANDO TESTES DE LÓGICA DE CONTROLE PREDITIVO")
    print("="*60)
    
    try:
        test_error_calculation()
        test_direct_logic()
        test_reverse_logic()
        test_adjustment_limits()
        test_new_value_calculation()
        test_real_world_scenario()
        
        print("\n" + "="*60)
        print("✅ TODOS OS TESTES PASSARAM COM SUCESSO!")
        print("="*60)
        return True
        
    except AssertionError as e:
        print(f"\n❌ TESTE FALHOU: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERRO INESPERADO: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
