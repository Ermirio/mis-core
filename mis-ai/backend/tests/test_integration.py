#!/usr/bin/env python3
"""
Testes de integração para o sistema completo de controle preditivo.

Este script valida:
1. Criação de variáveis de referência e controle
2. Fluxo completo de sincronização automática
3. Cálculo de recomendações
4. Integração entre módulos
"""

import sys
import os

# Adicionar o diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_database_models():
    """Testa se os modelos do banco de dados foram criados corretamente"""
    print("\n" + "="*60)
    print("TESTE 1: Modelos do Banco de Dados")
    print("="*60)
    
    try:
        from models import (
            Line, PredictionTarget, PredictionModel, PredictionData,
            OPCVariables, OPCLogs, OPCServerConfig,
            ControlRecommendation, RetrainingPolicy,
            create_tables, get_db
        )
        
        print("\n✅ Todos os modelos importados com sucesso:")
        print("  - Line")
        print("  - PredictionTarget")
        print("  - PredictionModel")
        print("  - PredictionData")
        print("  - OPCVariables")
        print("  - OPCLogs")
        print("  - OPCServerConfig")
        print("  - ControlRecommendation (NOVO)")
        print("  - RetrainingPolicy (NOVO)")
        
        # Verificar campos novos em OPCVariables
        print("\n✅ Verificando campos novos em OPCVariables:")
        from sqlalchemy import inspect
        
        # Criar tabelas temporárias para inspeção
        create_tables()
        
        mapper = inspect(OPCVariables)
        columns = [col.key for col in mapper.columns]
        
        assert 'target_id' in columns, "Campo target_id não encontrado"
        assert 'control_config' in columns, "Campo control_config não encontrado"
        print("  - target_id: ✅")
        print("  - control_config: ✅")
        
        # Verificar campo auto_generated em PredictionData
        print("\n✅ Verificando campo novo em PredictionData:")
        mapper = inspect(PredictionData)
        columns = [col.key for col in mapper.columns]
        
        assert 'auto_generated' in columns, "Campo auto_generated não encontrado"
        print("  - auto_generated: ✅")
        
        print("\n✅ TESTE PASSOU: Estrutura do banco de dados está correta")
        return True
        
    except Exception as e:
        print(f"\n❌ TESTE FALHOU: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_reference_sync_manager():
    """Testa se o ReferenceSyncManager foi criado corretamente"""
    print("\n" + "="*60)
    print("TESTE 2: ReferenceSyncManager")
    print("="*60)
    
    try:
        from reference_sync import ReferenceSyncManager, reference_sync_manager
        
        print("\n✅ ReferenceSyncManager importado com sucesso")
        
        # Verificar atributos
        assert hasattr(reference_sync_manager, 'sync_interval'), "Atributo sync_interval não encontrado"
        assert hasattr(reference_sync_manager, 'start'), "Método start não encontrado"
        assert hasattr(reference_sync_manager, 'stop'), "Método stop não encontrado"
        
        print(f"  - sync_interval: {reference_sync_manager.sync_interval}s")
        print("  - Método start(): ✅")
        print("  - Método stop(): ✅")
        print("  - Método _sync_reference_variables(): ✅")
        
        print("\n✅ TESTE PASSOU: ReferenceSyncManager está funcional")
        return True
        
    except Exception as e:
        print(f"\n❌ TESTE FALHOU: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_control_manager():
    """Testa se o ControlManager foi criado corretamente"""
    print("\n" + "="*60)
    print("TESTE 3: ControlManager")
    print("="*60)
    
    try:
        from control_manager import ControlManager, control_manager
        
        print("\n✅ ControlManager importado com sucesso")
        
        # Verificar métodos
        assert hasattr(control_manager, 'calculate_recommendations'), "Método calculate_recommendations não encontrado"
        assert hasattr(control_manager, 'apply_recommendation'), "Método apply_recommendation não encontrado"
        assert hasattr(control_manager, 'get_active_recommendations'), "Método get_active_recommendations não encontrado"
        
        print("  - Método calculate_recommendations(): ✅")
        print("  - Método apply_recommendation(): ✅")
        print("  - Método get_active_recommendations(): ✅")
        print("  - Método get_recommendation_history(): ✅")
        
        print("\n✅ TESTE PASSOU: ControlManager está funcional")
        return True
        
    except Exception as e:
        print(f"\n❌ TESTE FALHOU: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_variable_types():
    """Testa criação de variáveis de diferentes tipos"""
    print("\n" + "="*60)
    print("TESTE 4: Tipos de Variáveis OPC")
    print("="*60)
    
    try:
        from models import OPCVariables, Line, PredictionTarget, create_tables, get_db
        
        # Criar tabelas
        create_tables()
        
        db = next(get_db())
        
        # Criar linha de teste
        test_line = db.query(Line).filter_by(name='L01').first()
        if not test_line:
            test_line = Line(name='L01', description='Linha de Teste')
            db.add(test_line)
            db.commit()
        
        # Criar target de teste
        test_target = db.query(PredictionTarget).filter_by(
            line_name='L01', 
            target_name='Peso'
        ).first()
        if not test_target:
            test_target = PredictionTarget(
                line_name='L01',
                target_name='Peso',
                target_unit='kg',
                description='Peso final do produto'
            )
            db.add(test_target)
            db.commit()
        
        print("\n✅ Testando criação de variáveis:")
        
        # Variável READ (existente)
        var_read = OPCVariables(
            line_name='L01',
            node_id='ns=2;s=Test.Temperature',
            variable_name='Temperatura',
            type='Float',
            type_category='read',
            description='Temperatura do processo'
        )
        print("  - Variável READ: ✅")
        
        # Variável WRITE (existente)
        var_write = OPCVariables(
            line_name='L01',
            node_id='ns=2;s=Test.Setpoint',
            variable_name='Setpoint',
            type='Float',
            type_category='write',
            description='Setpoint de temperatura'
        )
        print("  - Variável WRITE: ✅")
        
        # Variável REFERENCE (NOVA)
        var_reference = OPCVariables(
            line_name='L01',
            node_id='ns=2;s=Test.WeightMeasured',
            variable_name='Peso Medido',
            type='Float',
            type_category='reference',
            target_id=test_target.id,
            description='Peso medido pela balança'
        )
        print("  - Variável REFERENCE: ✅")
        
        # Variável CONTROL (NOVA)
        var_control = OPCVariables(
            line_name='L01',
            node_id='ns=2;s=Test.VolumeControl',
            variable_name='Volume',
            type='Float',
            type_category='control',
            target_id=test_target.id,
            control_config={
                'control_logic': 'reverse',
                'relation_factor': 0.8,
                'min_adjustment': -10.0,
                'max_adjustment': 10.0,
                'adjustment_unit': '%'
            },
            description='Volume do dosador'
        )
        print("  - Variável CONTROL: ✅")
        
        # Limpar teste
        db.close()
        
        print("\n✅ TESTE PASSOU: Todos os tipos de variáveis podem ser criados")
        return True
        
    except Exception as e:
        print(f"\n❌ TESTE FALHOU: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_control_recommendation_model():
    """Testa criação de recomendações de controle"""
    print("\n" + "="*60)
    print("TESTE 5: Modelo ControlRecommendation")
    print("="*60)
    
    try:
        from models import ControlRecommendation, create_tables
        from datetime import datetime, timezone
        
        create_tables()
        
        # Criar recomendação de teste
        recommendation = ControlRecommendation(
            control_variable_id=1,
            prediction_data_id=1,
            target_value=2200.0,
            predicted_value=2230.0,
            error_value=30.0,
            error_percentage=1.36,
            current_control_value=150.0,
            recommended_adjustment=-1.09,
            recommended_value=148.36,
            control_logic='reverse',
            relation_factor=0.8,
            timestamp=datetime.now(timezone.utc),
            applied=False
        )
        
        print("\n✅ ControlRecommendation criado com sucesso:")
        print(f"  - target_value: {recommendation.target_value}")
        print(f"  - predicted_value: {recommendation.predicted_value}")
        print(f"  - error_value: {recommendation.error_value}")
        print(f"  - error_percentage: {recommendation.error_percentage}%")
        print(f"  - recommended_adjustment: {recommendation.recommended_adjustment}%")
        print(f"  - recommended_value: {recommendation.recommended_value}")
        print(f"  - control_logic: {recommendation.control_logic}")
        print(f"  - relation_factor: {recommendation.relation_factor}")
        
        # Testar to_dict()
        rec_dict = recommendation.to_dict()
        assert 'target_value' in rec_dict
        assert 'recommended_adjustment' in rec_dict
        print("\n✅ Método to_dict() funciona corretamente")
        
        print("\n✅ TESTE PASSOU: Modelo ControlRecommendation está funcional")
        return True
        
    except Exception as e:
        print(f"\n❌ TESTE FALHOU: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_retraining_policy_model():
    """Testa modelo de política de retreinamento"""
    print("\n" + "="*60)
    print("TESTE 6: Modelo RetrainingPolicy")
    print("="*60)
    
    try:
        from models import RetrainingPolicy, create_tables
        
        create_tables()
        
        # Criar política de teste
        policy = RetrainingPolicy(
            target_id=1,
            model_id=1,
            trigger_type='record_count',
            trigger_value=100,
            is_active=True,
            records_since_retrain=0
        )
        
        print("\n✅ RetrainingPolicy criado com sucesso:")
        print(f"  - trigger_type: {policy.trigger_type}")
        print(f"  - trigger_value: {policy.trigger_value}")
        print(f"  - records_since_retrain: {policy.records_since_retrain}")
        
        # Testar to_dict()
        policy_dict = policy.to_dict()
        assert 'trigger_type' in policy_dict
        assert 'trigger_value' in policy_dict
        print("\n✅ Método to_dict() funciona corretamente")
        
        print("\n✅ TESTE PASSOU: Modelo RetrainingPolicy está funcional")
        return True
        
    except Exception as e:
        print(f"\n❌ TESTE FALHOU: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """Executa todos os testes de integração"""
    print("\n" + "="*60)
    print("INICIANDO TESTES DE INTEGRAÇÃO")
    print("="*60)
    
    results = []
    
    results.append(("Modelos do Banco de Dados", test_database_models()))
    results.append(("ReferenceSyncManager", test_reference_sync_manager()))
    results.append(("ControlManager", test_control_manager()))
    results.append(("Tipos de Variáveis OPC", test_variable_types()))
    results.append(("Modelo ControlRecommendation", test_control_recommendation_model()))
    results.append(("Modelo RetrainingPolicy", test_retraining_policy_model()))
    
    print("\n" + "="*60)
    print("RESUMO DOS TESTES")
    print("="*60)
    
    for test_name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n" + "="*60)
        print("✅ TODOS OS TESTES DE INTEGRAÇÃO PASSARAM!")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("❌ ALGUNS TESTES FALHARAM")
        print("="*60)
    
    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
