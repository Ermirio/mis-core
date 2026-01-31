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
            
            if not prediction_data or prediction_data.predicted_value is None:
                logging.warning(f"⚠️ Predição {prediction_data_id} não encontrada ou sem valor predito")
                return []
            
            predicted_value = prediction_data.predicted_value
            
            # Calcular erro
            error_value = predicted_value - target_value
            
            # Evitar divisão por zero
            if target_value == 0:
                error_percentage = 0.0
            else:
                error_percentage = (error_value / target_value) * 100.0
            
            logging.info(
                f"📊 Predição: {predicted_value:.2f}, "
                f"Alvo: {target_value:.2f}, "
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
            # Lógica direta: aumentar controle aumenta target
            # Se target está baixo (erro negativo), aumentar controle
            recommended_adjustment = error_percentage * relation_factor
        elif control_logic == 'reverse':
            # Lógica reversa: aumentar controle diminui target
            # Se target está alto (erro positivo), aumentar controle
            recommended_adjustment = -error_percentage * relation_factor
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
        
        try:
            if opc_client.connected:
                import asyncio
                future = asyncio.run_coroutine_threadsafe(
                    opc_client.read_variable(control_var.node_id),
                    opc_client.loop
                )
                current_control_value = future.result(timeout=5)
                
                if current_control_value is not None:
                    # Calcular novo valor sugerido
                    adjustment_factor = 1.0 + (recommended_adjustment / 100.0)
                    recommended_value = current_control_value * adjustment_factor
                    
        except Exception as e:
            logging.warning(f"⚠️ Não foi possível ler valor atual de {control_var.variable_name}: {e}")
        
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
        db.flush()  # Para obter o ID
        
        logging.info(
            f"✅ Recomendação calculada para {control_var.variable_name}: "
            f"Ajuste de {recommended_adjustment:+.2f}% "
            f"(lógica: {control_logic}, fator: {relation_factor:.0%})"
        )
        
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
                return False, "Cliente OPC não está conectado"
            
            try:
                success, message = opc_client.write_variable_value(
                    node_path=control_var.node_id,
                    value=recommendation.recommended_value,
                    value_type=control_var.type
                )
                
                if not success:
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
                logging.error(f"❌ Erro ao escrever no OPC: {e}", exc_info=True)
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
