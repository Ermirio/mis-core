# control_manager.py - Gerenciamento de controle preditivo e recomendações de ajuste
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple
from models import (OPCVariables, ControlRecommendation, PredictionData, 
                    PredictionTarget, get_db)
from opc_client import opc_client

class ControlManager:
    """
    Gerencia o sistema de controle preditivo.
    
    Responsabilidades:
    - Calcular recomendações de ajuste baseadas em predições
    - Aplicar lógica direta/reversa
    - Aplicar fator de relação
    - Escrever valores no OPC (se configurado)
    - Manter histórico de recomendações
    """
    
    def __init__(self):
        logging.info("✅ ControlManager inicializado")
    
    def calculate_recommendations(
        self, 
        prediction_data_id: int, 
        target_value: float
    ) -> List[Dict]:
        """
        Calcula recomendações de ajuste para todas as variáveis de controle
        associadas ao target da predição.
        
        Args:
            prediction_data_id: ID do registro de predição
            target_value: Valor alvo desejado
            
        Returns:
            Lista de dicionários com recomendações calculadas
        """
        db = next(get_db())
        recommendations = []
        
        try:
            # Buscar dados da predição
            prediction_data = db.query(PredictionData).filter(
                PredictionData.id == prediction_data_id
            ).first()
            
            if not prediction_data:
                logging.warning(f"⚠️ Predição {prediction_data_id} não encontrada no banco.")
                return []
            
            if prediction_data.predicted_value is None:
                logging.warning(f"⚠️ Predição {prediction_data_id} encontrada mas sem valor predito (None).")
                return []
            
            logging.info(f"ℹ️ Predição {prediction_data_id} encontrada. Valor: {prediction_data.predicted_value}")
            
            predicted_value = prediction_data.predicted_value
            
            # LÓGICA DE TARGET DINÂMICO (NOVO)
            # Verifica se existe uma variável OPC do tipo 'target' para este PredictionTarget
            dynamic_target_var = db.query(OPCVariables).filter(
                OPCVariables.target_id == prediction_data.target_id,
                OPCVariables.type_category == 'target',
                OPCVariables.is_active == True
            ).first()

            if dynamic_target_var:
                try:
                    target_val_read = None
                    if opc_client.connected:
                        import asyncio
                        # Reutiliza o loop do cliente OPC se possível, ou usa threadsafe
                        future = asyncio.run_coroutine_threadsafe(
                            opc_client.read_variable(dynamic_target_var.node_id),
                            opc_client.loop
                        )
                        target_val_read = future.result(timeout=5)
                    
                    if target_val_read is not None and isinstance(target_val_read, (int, float)):
                        logging.info(f"🎯 Target Dinâmico Detectado! Usando valor lido do OPC: {target_val_read} (Variável: {dynamic_target_var.variable_name})")
                        target_value = float(target_val_read)
                    else:
                        logging.warning(f"⚠️ Falha ao ler Target Dinâmico ({dynamic_target_var.variable_name}). Usando valor padrão: {target_value}")
                except Exception as e:
                    logging.error(f"❌ Erro ao ler Target Dinâmico: {e}. Usando valor padrão: {target_value}")

            # Calcular erro (com o target_value possivelmente atualizado)
            error_value = predicted_value - target_value
            
            # Evitar divisão por zero
            if target_value == 0:
                error_percentage = 0.0
            else:
                error_percentage = (error_value / target_value) * 100.0
            
            logging.info(
                f"📊 Predição: {predicted_value:.2f}, "
                f"Alvo (Final): {target_value:.2f}, "
                f"Erro: {error_value:.2f} ({error_percentage:.2f}%)"
            )
            
            # Buscar variáveis de controle associadas ao target
            control_vars = db.query(OPCVariables).filter(
                OPCVariables.target_id == prediction_data.target_id,
                OPCVariables.type_category == 'control',
                OPCVariables.is_active == True
            ).all()
            
            if not control_vars:
                logging.info(f"ℹ️ Nenhuma variável de controle encontrada para target_id={prediction_data.target_id}")
                return []
            
            # Calcular recomendação para cada variável de controle
            for control_var in control_vars:
                try:
                    recommendation = self._calculate_single_recommendation(
                        db=db,
                        control_var=control_var,
                        prediction_data=prediction_data,
                        target_value=target_value,
                        predicted_value=predicted_value,
                        error_value=error_value,
                        error_percentage=error_percentage
                    )
                    
                    if recommendation:
                        recommendations.append(recommendation)
                        
                except Exception as e:
                    logging.error(
                        f"❌ Erro ao calcular recomendação para variável {control_var.variable_name}: {e}",
                        exc_info=True
                    )
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            logging.error(f"❌ Erro ao calcular recomendações: {e}", exc_info=True)
        finally:
            db.close()
        
        return recommendations
    
    def _calculate_single_recommendation(
        self,
        db,
        control_var: OPCVariables,
        prediction_data: PredictionData,
        target_value: float,
        predicted_value: float,
        error_value: float,
        error_percentage: float
    ) -> Optional[Dict]:
        """
        Calcula recomendação de ajuste para uma única variável de controle.
        
        Args:
            db: Sessão do banco de dados
            control_var: Variável de controle
            prediction_data: Dados da predição
            target_value: Valor alvo
            predicted_value: Valor predito
            error_value: Erro absoluto
            error_percentage: Erro percentual
            
        Returns:
            Dicionário com a recomendação ou None se houver erro
        """
        # Validar configuração de controle
        if not control_var.control_config:
            logging.warning(f"⚠️ Variável {control_var.variable_name} não possui control_config")
            return None
        
        config = control_var.control_config
        control_logic = config.get('control_logic', 'direct')
        relation_factor = config.get('relation_factor', 1.0)
        min_adjustment = config.get('min_adjustment')
        max_adjustment = config.get('max_adjustment')
        
        # Calcular ajuste baseado na lógica
        if control_logic == 'direct':
            # Lógica direta: aumentar controle aumenta target (Ex: Aquecedor)
            # Se target está baixo (Erro negativo: PV < SP => Precisa AUMENTAR controle)
            # Como error_percentage é negativo, usamos MENOS error_percentage para ter ajuste Positivo
            recommended_adjustment = -error_percentage * relation_factor
        elif control_logic == 'reverse':
            # Lógica reversa: aumentar controle diminui target (Ex: Refrigerador)
            # Se target está alto (Erro positivo: PV > SP => Precisa AUMENTAR controle)
            # error_percentage é positivo, usamos error_percentage direto?
            # Espere. Reverse: Increase Control -> Decrease PV.
            # Se PV > SP (Erro +), precisamos DIMINUIR PV -> AUMENTAR Controle.
            # Erro é +, queremos Ajuste +. Então sign é DIRETO?
            recommended_adjustment = error_percentage * relation_factor
        else:
            logging.error(f"❌ Lógica de controle inválida: {control_logic}")
            return None
        
        # Aplicar limites de ajuste
        if min_adjustment is not None and recommended_adjustment < min_adjustment:
            recommended_adjustment = min_adjustment
        if max_adjustment is not None and recommended_adjustment > max_adjustment:
            recommended_adjustment = max_adjustment
        
        # Ler valor atual da variável de controle (opcional)
        current_control_value = None
        recommended_value = None
        
        logging.info(f"📍 CHECKPOINT 1: Iniciando leitura atual para {control_var.variable_name}")
        try:
            if opc_client.connected:
                import asyncio
                # Verifica Loop
                if not opc_client.loop or not opc_client.loop.is_running():
                     logging.error("❌ LOOP OPC NÃO ESTÁ RODANDO! Leitura impossível.")
                else:
                    future = asyncio.run_coroutine_threadsafe(
                        opc_client.read_variable(control_var.node_id),
                        opc_client.loop
                    )
                    current_control_value = future.result(timeout=5)
                    logging.info(f"📍 CHECKPOINT 2: Leitura concluída. Valor: {current_control_value}")
                    
                    # --- SANITY CHECK: Reject garbage values from PLC ---
                    MAX_SANE_VALUE = 1e6  # Valor máximo "razoável" para uma variável de controle
                    if current_control_value is not None and abs(current_control_value) > MAX_SANE_VALUE:
                        logging.warning(f"⚠️ [SANITY] Valor lido do OPC ({current_control_value}) é absurdo. Usando target_value ({target_value}) como fallback.")
                        current_control_value = float(target_value) if target_value else 0.0
                
                if current_control_value is not None:

                    # Calcular novo valor sugerido
                    if current_control_value == 0 and recommended_adjustment > 0:
                        # Kickstart: Se atual é 0 e precisa aumentar, usa Target como referência inicial
                        recommended_value = float(target_value) if target_value else 1.0
                        logging.info(f"🚀 Kickstart: Controle estava 0, sugerindo {recommended_value} (Target)")
                    else:
                        adjustment_factor = 1.0 + (recommended_adjustment / 100.0)
                        recommended_value = current_control_value * adjustment_factor
                        
            else:
                 logging.warning("⚠️ OPC Client desconectado no Checkpoint 1")
                    
        except Exception as e:
            logging.warning(f"⚠️ Não foi possível ler valor atual de {control_var.variable_name}: {e}")
        
        # --- FAIL-SAFE: Clamp recommended_value to prevent writing garbage to PLC ---
        MAX_WRITE_VALUE = 10.0  # Valor máximo razoável para variável de controle (Lowered to 10)
        if recommended_value is not None and abs(recommended_value) > MAX_WRITE_VALUE:
            logging.error(f"🚫 [FAIL-SAFE] recommended_value ({recommended_value}) excede ±{MAX_WRITE_VALUE}. Rejeitando escrita. Usando target_value ({target_value}) como fallback.")
            recommended_value = float(target_value) if target_value else None


        
        logging.info("📍 CHECKPOINT 3: Criando registro")

        # Criar registro de recomendação
        recommendation_record = ControlRecommendation(
            control_variable_id=control_var.id,
            prediction_data_id=prediction_data.id,
            target_value=target_value,
            predicted_value=predicted_value,
            error_value=error_value,
            error_percentage=error_percentage,
            current_control_value=current_control_value,
            recommended_adjustment=recommended_adjustment,
            recommended_value=recommended_value,
            control_logic=control_logic,
            relation_factor=relation_factor,
            timestamp=datetime.now(timezone.utc),
            applied=False
        )
        
        db.add(recommendation_record)
        db.commit()  # <--- COMMIT IMPORTANTE: Para que apply_recommendation (nova sessão) veja o registro
        db.refresh(recommendation_record)
        
        # AUTO-APPLY (NOVO)
        logging.info(f"📍 CHECKPOINT 4: Verificando Auto-Apply. Config: {config.get('auto_apply')}")
        if config.get('auto_apply', False):
            # if True: # <--- REMOVIDO HACK
            logging.info(f"🤖 Auto-Apply ativado para {control_var.variable_name}. Aplicando...")
            success, msg = self.apply_recommendation(recommendation_record.id)
            if success:
                # Atualizar objeto local para retorno
                recommendation_record = db.query(ControlRecommendation).filter(
                    ControlRecommendation.id == recommendation_record.id
                ).first()
                # Atualizar valores locais
                current_control_value = recommendation_record.current_control_value # Pode ter mudado? Não.
                # Mas applied=True
        
        # Retornar dicionário com informações da recomendação
        return {
            'id': recommendation_record.id,
            'control_variable_id': control_var.id,
            'control_variable_name': control_var.variable_name,
            'control_variable_node_id': control_var.node_id,
            'target_value': target_value,
            'predicted_value': predicted_value,
            'error_value': error_value,
            'error_percentage': error_percentage,
            'current_control_value': current_control_value,
            'recommended_adjustment': recommended_adjustment,
            'recommended_value': recommended_value,
            'control_logic': control_logic,
            'relation_factor': relation_factor,
            'timestamp': recommendation_record.timestamp.isoformat(),
            'applied': False
        }
    
    def apply_recommendation(self, recommendation_id: int) -> Tuple[bool, str]:
        """
        Aplica uma recomendação de controle, escrevendo o valor no OPC.
        
        Args:
            recommendation_id: ID da recomendação a ser aplicada
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        db = next(get_db())
        
        try:
            # Buscar recomendação
            recommendation = db.query(ControlRecommendation).filter(
                ControlRecommendation.id == recommendation_id
            ).first()
            
            if not recommendation:
                return False, f"Recomendação {recommendation_id} não encontrada"
            
            if recommendation.applied:
                return False, "Recomendação já foi aplicada anteriormente"
            
            if recommendation.recommended_value is None:
                return False, "Recomendação não possui valor calculado"
            
            # Buscar variável de controle
            control_var = db.query(OPCVariables).filter(
                OPCVariables.id == recommendation.control_variable_id
            ).first()
            
            if not control_var:
                return False, "Variável de controle não encontrada"
            
            # Escrever valor no OPC
            if not opc_client.connected:
                logging.error(f"❌ [APPLY] Falha ao aplicar Recomendação {recommendation_id}: Cliente OPC desconectado.")
                return False, "Cliente OPC não está conectado"
            
            try:
                logging.info(f"📍 CHECKPOINT 5: Tentando escrever no OPC. Node: {control_var.node_id}, Valor: {recommendation.recommended_value}, Tipo: {control_var.type}")
                
                # Validação de sanidade
                if recommendation.recommended_value is None:
                     raise ValueError("Valor recomendado é None")

                success, message = opc_client.write_variable_value(
                    node_path=control_var.node_id,
                    value=recommendation.recommended_value,
                    value_type=control_var.type
                )
                
                logging.info(f"📍 CHECKPOINT 6: Retorno da escrita. Sucesso: {success}, Msg: {message}")
                
                if not success:
                    logging.error(f"❌ [APPLY] Falha na escrita OPC: {message}")
                    # HACK DE DEBUG: Salvar erro no campo control_logic para visualização no banco
                    try:
                        recommendation.control_logic = f"ERR: {message}"[:10] # Limite char
                        db.commit()
                    except: pass
                    
                    return False, f"Falha ao escrever no OPC: {message}"
                
                # Marcar recomendação como aplicada
                recommendation.applied = True
                recommendation.applied_at = datetime.now(timezone.utc)
                db.commit()
                
                logging.info(
                    f"✅ Recomendação {recommendation_id} aplicada com sucesso: "
                    f"{control_var.variable_name} = {recommendation.recommended_value:.2f}"
                )
                
                return True, f"Ajuste aplicado: {control_var.variable_name} = {recommendation.recommended_value:.2f}"
                
            except Exception as e:
                logging.error(f"❌ [APPLY] Exceção crítica ao escrever no OPC: {e}", exc_info=True)
                return False, f"Erro ao escrever no OPC: {str(e)}"
            
        except Exception as e:
            db.rollback()
            logging.error(f"❌ Erro ao aplicar recomendação: {e}", exc_info=True)
            return False, str(e)
        finally:
            db.close()
    
    def get_active_recommendations(self, target_id: Optional[int] = None, line_name: Optional[str] = None) -> List[Dict]:
        """
        Retorna recomendações ativas (não aplicadas) para um target ou linha.
        
        Args:
            target_id: ID do target (opcional)
            line_name: Nome da linha (opcional)
            
        Returns:
            Lista de recomendações ativas
        """
        db = next(get_db())
        
        try:
            query = db.query(ControlRecommendation).filter(
                ControlRecommendation.applied == False
            )
            
            if target_id:
                query = query.join(PredictionData).filter(
                    PredictionData.target_id == target_id
                )
            
            if line_name:
                query = query.join(
                    OPCVariables, 
                    ControlRecommendation.control_variable_id == OPCVariables.id
                ).filter(
                    OPCVariables.line_name == line_name
                )
            
            recommendations = query.order_by(
                ControlRecommendation.timestamp.desc()
            ).limit(50).all()
            
            result = []
            for rec in recommendations:
                control_var = db.query(OPCVariables).filter(
                    OPCVariables.id == rec.control_variable_id
                ).first()
                
                rec_dict = rec.to_dict()
                if control_var:
                    rec_dict['control_variable_name'] = control_var.variable_name
                    rec_dict['control_variable_node_id'] = control_var.node_id
                    rec_dict['line_name'] = control_var.line_name
                
                result.append(rec_dict)
            
            return result
            
        except Exception as e:
            logging.error(f"❌ Erro ao buscar recomendações ativas: {e}", exc_info=True)
            return []
        finally:
            db.close()
    
    def get_recommendation_history(
        self, 
        control_variable_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Retorna histórico de recomendações.
        
        Args:
            control_variable_id: ID da variável de controle (opcional)
            limit: Número máximo de registros
            
        Returns:
            Lista de recomendações históricas
        """
        db = next(get_db())
        
        try:
            query = db.query(ControlRecommendation)
            
            if control_variable_id:
                query = query.filter(
                    ControlRecommendation.control_variable_id == control_variable_id
                )
            
            recommendations = query.order_by(
                ControlRecommendation.timestamp.desc()
            ).limit(limit).all()
            
            return [rec.to_dict() for rec in recommendations]
            
        except Exception as e:
            logging.error(f"❌ Erro ao buscar histórico de recomendações: {e}", exc_info=True)
            return []
        finally:
            db.close()

# Instância global do gerenciador
control_manager = ControlManager()
