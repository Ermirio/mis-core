# reference_sync.py - Sincronização automática de variáveis de referência
import logging
import asyncio
from datetime import datetime, timezone
from models import OPCVariables, PredictionData, get_db
from opc_client import opc_client

class ReferenceSyncManager:
    """
    Gerencia a sincronização automática de variáveis de referência.
    
    Variáveis de referência são aquelas que capturam valores medidos automaticamente
    do OPC para alimentar o treinamento contínuo de modelos de predição.
    """
    
    def __init__(self):
        self.sync_interval = 5  # Intervalo de sincronização em segundos
        self.running = False
        self.sync_task = None
        logging.info("✅ ReferenceSyncManager inicializado")
    
    async def start(self):
        """Inicia o processo de sincronização automática"""
        if self.running:
            logging.warning("⚠️ ReferenceSyncManager já está rodando")
            return
        
        self.running = True
        self.sync_task = asyncio.create_task(self._sync_loop())
        logging.info("🔄 ReferenceSyncManager iniciado")
    
    async def stop(self):
        """Para o processo de sincronização automática"""
        if not self.running:
            return
        
        self.running = False
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
        logging.info("⏹️ ReferenceSyncManager parado")
    
    async def _sync_loop(self):
        """Loop principal de sincronização"""
        while self.running:
            try:
                await self._sync_reference_variables()
                await asyncio.sleep(self.sync_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"❌ Erro no loop de sincronização: {e}", exc_info=True)
                await asyncio.sleep(self.sync_interval)
    
    async def _sync_reference_variables(self):
        """
        Sincroniza todas as variáveis de referência ativas.
        
        Processo:
        1. Busca todas as variáveis com type_category='reference' e is_active=True
        2. Para cada variável:
           a) Lê o valor atual do OPC
           b) Busca todas as variáveis 'read' da mesma linha (features)
           c) Cria um registro em PredictionData com:
              - measured_value: valor da variável de referência
              - opc_values: JSON com todas as features
              - data_source: 'auto_reference'
              - auto_generated: True
        """
        if not opc_client.connected:
            return
        
        db = next(get_db())
        try:
            # Buscar variáveis de referência ativas
            reference_vars = db.query(OPCVariables).filter(
                OPCVariables.type_category == 'reference',
                OPCVariables.is_active == True,
                OPCVariables.target_id != None
            ).all()
            
            if not reference_vars:
                return
            
            for ref_var in reference_vars:
                try:
                    await self._sync_single_reference(db, ref_var)
                except Exception as e:
                    logging.error(f"❌ Erro ao sincronizar variável {ref_var.variable_name}: {e}")
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            logging.error(f"❌ Erro na sincronização de referências: {e}", exc_info=True)
        finally:
            db.close()
    
    async def _sync_single_reference(self, db, ref_var):
        """
        Sincroniza uma única variável de referência.
        
        Args:
            db: Sessão do banco de dados
            ref_var: Objeto OPCVariables com type_category='reference'
        """
        # 1. Ler valor da variável de referência
        ref_value = await opc_client.read_variable(ref_var.node_id)
        if ref_value is None:
            logging.warning(f"⚠️ Não foi possível ler variável de referência: {ref_var.variable_name}")
            return
        
        # 2. Buscar todas as variáveis 'read' da mesma linha (features)
        feature_vars = db.query(OPCVariables).filter(
            OPCVariables.line_name == ref_var.line_name,
            OPCVariables.type_category == 'read',
            OPCVariables.is_active == True
        ).all()
        
        if not feature_vars:
            logging.warning(f"⚠️ Nenhuma variável de entrada (read) encontrada para linha {ref_var.line_name}")
            return
        
        # 3. Ler valores de todas as features
        opc_values = {}
        for feature_var in feature_vars:
            try:
                value = await opc_client.read_variable(feature_var.node_id)
                if value is not None:
                    opc_values[feature_var.node_id] = value
            except Exception as e:
                logging.warning(f"⚠️ Erro ao ler feature {feature_var.variable_name}: {e}")
        
        if not opc_values:
            logging.warning(f"⚠️ Nenhuma feature válida lida para linha {ref_var.line_name}")
            return
        
        # 4. Criar registro em PredictionData
        new_data = PredictionData(
            target_id=ref_var.target_id,
            measured_value=float(ref_value),
            opc_values=opc_values,
            timestamp=datetime.now(timezone.utc),
            data_source='auto_reference',
            auto_generated=True
        )
        
        db.add(new_data)
        
        logging.info(
            f"✅ Sincronizado: {ref_var.variable_name} = {ref_value:.2f} "
            f"(target_id={ref_var.target_id}, features={len(opc_values)})"
        )
        
        # 5. Verificar se há política de retreinamento e atualizar contador
        from models import RetrainingPolicy
        policies = db.query(RetrainingPolicy).filter(
            RetrainingPolicy.target_id == ref_var.target_id,
            RetrainingPolicy.is_active == True,
            RetrainingPolicy.trigger_type == 'record_count'
        ).all()
        
        for policy in policies:
            policy.records_since_retrain += 1
            
            # Se atingiu o gatilho, agendar retreinamento
            if policy.records_since_retrain >= policy.trigger_value:
                logging.info(
                    f"🎯 Gatilho de retreinamento atingido para target_id={ref_var.target_id}, "
                    f"model_id={policy.model_id} ({policy.records_since_retrain} registros)"
                )
                # Aqui poderia disparar o retreinamento automaticamente
                # Por enquanto, apenas resetamos o contador e atualizamos timestamp
                policy.records_since_retrain = 0
                policy.last_retrain_at = datetime.now(timezone.utc)
                
                # TODO: Implementar chamada assíncrona para retreinamento
                # asyncio.create_task(self._trigger_retraining(policy.model_id))
    
    async def _trigger_retraining(self, model_id):
        """
        Dispara o retreinamento de um modelo (implementação futura).
        
        Args:
            model_id: ID do modelo a ser retreinado
        """
        # TODO: Implementar lógica de retreinamento assíncrono
        logging.info(f"🔄 Retreinamento do modelo {model_id} agendado (não implementado ainda)")
        pass

# Instância global do gerenciador
reference_sync_manager = ReferenceSyncManager()
