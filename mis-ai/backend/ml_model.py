# ml_model.py - Versão melhorada para suportar múltiplos modelos e targets
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import os
import logging
import threading
from datetime import datetime, timedelta, timezone
from models import PredictionData, PredictionTarget, PredictionModel, OPCVariables, get_db
from opc_client import opc_client
from influx_client import influx_client

class GenericPredictor:
    """Preditor genérico que suporta múltiplos targets e modelos"""
    
    def __init__(self):
        self.models = {}  # Cache de modelos carregados
        self.model_dir = 'models'
        os.makedirs(self.model_dir, exist_ok=True)
        # --- CORREÇÃO ---
        # Agora rastreamos workers por LINHA
        self.line_prediction_workers = {}  # {line_name: {'thread': thread, 'stop_event': event}}
        
        # Tipos de modelo disponíveis
        self.model_types = {
            'RandomForest': RandomForestRegressor,
            'LinearRegression': LinearRegression
        }
        
        # Parâmetros padrão para cada tipo de modelo
        self.default_parameters = {
            'RandomForest': {
                'n_estimators': 100,
                'max_depth': 10,
                'random_state': 42
            },
            'LinearRegression': {
                'fit_intercept': True
            }
        }
    
    def get_available_targets(self, line_name):
        """Retorna os targets disponíveis para uma linha"""
        db = next(get_db())
        try:
            targets = db.query(PredictionTarget).filter(
                PredictionTarget.line_name == line_name,
                PredictionTarget.is_active == True
            ).all()
            return [target.to_dict() for target in targets]
        finally:
            db.close()
    
    def get_available_models(self, target_id):
        """Retorna os modelos disponíveis para um target"""
        db = next(get_db())
        try:
            # CORREÇÃO: Retorna TODOS os modelos (ativos e inativos) para o frontend gerenciar
            models = db.query(PredictionModel).filter(
                PredictionModel.target_id == target_id
            ).order_by(PredictionModel.model_name).all()
            return [model.to_dict() for model in models]
        finally:
            db.close()
    
    def create_target(self, line_name, target_name, target_unit=None, description=None):
        """Cria um novo target de predição"""
        db = next(get_db())
        try:
            # Verificar se já existe
            existing = db.query(PredictionTarget).filter(
                PredictionTarget.line_name == line_name,
                PredictionTarget.target_name == target_name
            ).first()
            
            if existing:
                return False, "Target já existe para esta linha"
            
            new_target = PredictionTarget(
                line_name=line_name,
                target_name=target_name,
                target_unit=target_unit,
                description=description
            )
            db.add(new_target)
            db.commit()
            return True, f"Target '{target_name}' criado com sucesso"
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()
    
    def create_model(self, target_id, model_name, model_type='RandomForest', parameters=None):
        """Cria um novo modelo para um target"""
        db = next(get_db())
        try:
            if model_type not in self.model_types:
                return False, f"Tipo de modelo '{model_type}' não suportado"
            
            # Usar parâmetros padrão se não fornecidos
            if parameters is None:
                parameters = self.default_parameters.get(model_type, {})
            
            new_model = PredictionModel(
                target_id=target_id,
                model_name=model_name,
                model_type=model_type,
                model_parameters=parameters
            )
            db.add(new_model)
            db.commit()
            return True, f"Modelo '{model_name}' criado com sucesso"
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()
    
    def prepare_training_data(self, target_id, days_back=30):
        """Prepara dados para treinamento de um target específico"""
        db = next(get_db())
        try:
            # Buscar o target
            target = db.query(PredictionTarget).filter(PredictionTarget.id == target_id).first()
            if not target:
                return None, "Target não encontrado"
            
            # Buscar variáveis OPC ativas para a linha
            opc_vars = db.query(OPCVariables.node_id).filter(
                OPCVariables.line_name == target.line_name,
                OPCVariables.is_active == True,
                OPCVariables.type_category == 'read' # <-- CORREÇÃO: Ler APENAS inputs
            ).all()
            
            if not opc_vars:
                return None, "Nenhuma variável OPC ativa registrada para esta linha"
            
            valid_node_ids = {row[0] for row in opc_vars}
            
            # Buscar dados históricos
            start_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            prediction_data = db.query(PredictionData).filter(
                PredictionData.target_id == target_id,
                PredictionData.timestamp >= start_date,
                PredictionData.measured_value != None,
                PredictionData.opc_values != None
            ).all()
            
            if len(prediction_data) < 10:
                return None, "Dados insuficientes para treinamento (mínimo de 10 registros)"
            
            # Preparar dados de treinamento
            training_data = []
            for record in prediction_data:
                if isinstance(record.opc_values, dict) and record.opc_values:
                    filtered_opc_values = {
                        node_id: value for node_id, value in record.opc_values.items()
                        if node_id in valid_node_ids
                    }
                    
                    if filtered_opc_values:
                        training_data.append({
                            'target_value': record.measured_value,
                            **filtered_opc_values
                        })
            
            if not training_data:
                return None, "Nenhum dado válido encontrado após filtragem"
            
            training_df = pd.DataFrame(training_data).fillna(0)
            if len(training_df) < 5:
                return None, "Dados limpos insuficientes para treinamento"
            
            return training_df, "Dados preparados com sucesso"
        finally:
            db.close()
    
    def train_model(self, model_id):
        """Treina um modelo específico"""
        db = next(get_db())
        try:
            # Buscar o modelo
            model_record = db.query(PredictionModel).filter(PredictionModel.id == model_id).first()
            if not model_record:
                return False, "Modelo não encontrado"
            
            # Preparar dados de treinamento
            training_data, message = self.prepare_training_data(model_record.target_id)
            if training_data is None:
                return False, message
            
            # Separar features e target
            features = [col for col in training_data.columns if col != 'target_value']
            if not features:
                return False, "Nenhuma feature disponível para treinamento"
            
            X = training_data[features]
            y = training_data['target_value']
            
            # Dividir dados
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Criar e treinar modelo
            model_class = self.model_types[model_record.model_type]
            model_params = model_record.model_parameters or {}
            model = model_class(**model_params)
            model.fit(X_train, y_train)
            
            # Avaliar modelo
            y_pred = model.predict(X_test)
            mse = mean_squared_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            # Calcular importância das features (se disponível)
            feature_importances = None
            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
                feature_importance_map = sorted(zip(features, importances), key=lambda x: x[1], reverse=True)
                feature_importances = feature_importance_map
            
            # Salvar modelo
            model_filename = f'model_{model_id}_{model_record.model_type.lower()}.joblib'
            model_path = os.path.join(self.model_dir, model_filename)
            
            joblib.dump({
                'model': model,
                'features': features,
                'feature_importances': feature_importances,
                'mse': mse,
                'r2': r2,
                'trained_at': datetime.now(timezone.utc).isoformat()
            }, model_path)
            
            # Atualizar registro no banco
            model_record.mse = mse
            model_record.r2_score = r2
            model_record.feature_importances = feature_importances
            model_record.trained_at = datetime.now(timezone.utc)
            model_record.model_file_path = model_path
            db.commit()
            
            # Carregar modelo no cache
            self.models[model_id] = joblib.load(model_path)
            
            return True, f"Modelo treinado com sucesso - MSE: {mse:.4f}, R²: {r2:.4f}"
            
        except Exception as e:
            logging.error(f"Erro ao treinar modelo {model_id}: {e}", exc_info=True)
            db.rollback()
            return False, str(e)
        finally:
            db.close()
    
    def load_model(self, model_id):
        """Carrega um modelo do disco"""
        if model_id in self.models:
            return True, "Modelo já carregado"
        
        db = next(get_db())
        try:
            model_record = db.query(PredictionModel).filter(PredictionModel.id == model_id).first()
            if not model_record or not model_record.model_file_path:
                return False, "Modelo não encontrado ou não treinado"
            
            if not os.path.exists(model_record.model_file_path):
                return False, "Arquivo do modelo não encontrado"
            
            self.models[model_id] = joblib.load(model_record.model_file_path)
            return True, "Modelo carregado com sucesso"
        except Exception as e:
            logging.error(f"Erro ao carregar modelo {model_id}: {e}", exc_info=True)
            return False, str(e)
        finally:
            db.close()
    
    def predict(self, model_id, opc_values=None):
        """Faz predição usando um modelo específico e escreve o resultado de volta no OPC."""
        try:
            # Etapa 1: Carregar o modelo se não estiver em cache
            if model_id not in self.models:
                success, message = self.load_model(model_id)
                if not success:
                    return None, message
            
            model_data = self.models[model_id]
            model = model_data['model']
            required_features = model_data['features']
            
            # Etapa 2: Obter o nome da linha para as operações OPC
            db = next(get_db())
            try:
                model_record = db.query(PredictionModel).filter(PredictionModel.id == model_id).first()
                if not model_record: return None, "Registro do modelo não encontrado no DB."
                target = db.query(PredictionTarget).filter(PredictionTarget.id == model_record.target_id).first()
                if not target: return None, "Target associado ao modelo não encontrado no DB."
                line_name_for_opc = target.line_name
            finally:
                db.close()

            # Etapa 3: Obter valores OPC atuais (se não foram passados)
            if opc_values is None:
                opc_values, opc_error = opc_client.get_opc_values(line_name_for_opc)
                if opc_error or opc_values is None:
                    return None, f"Falha ao obter dados OPC para predição: {opc_error or 'Nenhum dado recebido'}"
            
            # Etapa 4: Preparar vetor de features e fazer a predição
            feature_vector = {feature: opc_values.get(feature, 0.0) for feature in required_features}
            X_pred = pd.DataFrame([feature_vector])[required_features]
            prediction = model.predict(X_pred)[0]
            
            # =============================================================================
            # INÍCIO DA NOVA LÓGICA DE ESCRITA NO OPC
            # =============================================================================
            db = next(get_db())
            try:
                # Encontra a variável OPC configurada como 'write' para a linha atual
                write_variable = db.query(OPCVariables).filter(
                    OPCVariables.line_name == line_name_for_opc,
                    OPCVariables.type_category == 'write',
                    OPCVariables.is_active == True
                ).first()

                if write_variable:
                    logging.info(f"Variável de escrita encontrada: {write_variable.node_id}. Tentando escrever o valor {prediction:.4f}.")
                    # Usa o novo método do cliente OPC para escrever o valor
                    success, msg = opc_client.write_variable_value(
                        node_path=write_variable.node_id,
                        value=prediction, # <--- CORREÇÃO (sem float())
                        value_type=write_variable.type
                    )
                    if not success:
                        logging.warning(f"Não foi possível escrever a predição no OPC para o nó {write_variable.node_id}: {msg}")
                else:
                    logging.info(f"Nenhuma variável OPC de 'escrita' ativa encontrada para a linha {line_name_for_opc}. A predição não será escrita no OPC.")
            
            except Exception as e:
                logging.error(f"Ocorreu um erro ao tentar escrever a predição no OPC: {e}", exc_info=True)
            finally:
                db.close()
            # =============================================================================
            # FIM DA NOVA LÓGICA DE ESCRITA NO OPC
            # =============================================================================
            
            # Etapa 5: Calcular confiança (lógica existente)
            confidence_std_dev = None
            if hasattr(model, 'estimators_'):
                tree_predictions = [tree.predict(X_pred)[0] for tree in model.estimators_]
                confidence_std_dev = np.std(tree_predictions)
            
            # Etapa 6: Salvar a predição no banco de dados (lógica existente)
            # ...
            # Etapa 6: Salvar a predição no banco de dados (lógica existente)
            db = next(get_db())
            try:
                # --- CORREÇÃO ---
                # Define o fuso GMT-3 (America/Sao_Paulo)
                local_timezone = timezone(timedelta(hours=-3))
                
                new_prediction = PredictionData(
                    target_id=model_record.target_id,
                    model_id=model_id,
                    predicted_value=prediction,
                    confidence_std_dev=confidence_std_dev,
                    timestamp=datetime.now(local_timezone), # <--- SALVA A HORA LOCAL
                    opc_values=opc_values,
                    data_source='opc'
                )
                db.add(new_prediction)
            # ...
                db.commit()
                db.refresh(new_prediction)
            except Exception as e:
                logging.error(f"Erro ao salvar predição no banco de dados: {e}", exc_info=True)
                db.rollback()
            finally:
                db.close()

            # =============================================================================
            # PERSISTÊNCIA NO INFLUXDB (NOVO)
            # =============================================================================
            try:
                if influx_client.connected:
                    influx_measurement = "predictions"
                    influx_tags = {
                        "line": line_name_for_opc,
                        "model_id": str(model_id),
                        "model_name": model_record.model_name
                    }
                    influx_fields = {
                        "value": float(prediction)
                    }
                    if confidence_std_dev is not None:
                        influx_fields["confidence"] = float(confidence_std_dev)
                    
                    # Escreve no Influx
                    influx_client.write_point(
                        measurement=influx_measurement,
                        tags=influx_tags,
                        fields=influx_fields,
                        time=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                    )
                    logging.info(f"✅ Predição gravada no InfluxDB: {prediction:.4f}")
            except Exception as e_influx:
                logging.error(f"❌ Erro ao gravar no InfluxDB: {e_influx}")
            # =============================================================================

            return new_prediction.to_dict(), "Predição realizada com sucesso"
            
        except Exception as e:
            logging.error(f"Erro GERAL no método de predição para modelo {model_id}: {e}", exc_info=True)
            return None, str(e)

    
    def save_manual_data(self, target_id, measured_value, opc_values=None, timestamp=None):
        """Salva dados manuais para treinamento"""
        db = next(get_db())
        try:
            if timestamp is None:
                timestamp = datetime.now(timezone.utc)
            
            new_data = PredictionData(
                target_id=target_id,
                measured_value=measured_value,
                timestamp=timestamp,
                opc_values=opc_values,
                data_source='manual'
            )
            db.add(new_data)
            db.commit()
            return True, "Dados salvos com sucesso"
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()
    
    def get_model_status(self, model_id):
        """Retorna status de um modelo"""
        db = next(get_db())
        try:
            model_record = db.query(PredictionModel).filter(PredictionModel.id == model_id).first()
            if not model_record:
                return None, "Modelo não encontrado"
            
            # Contar dados disponíveis para treinamento
            sample_count = db.query(PredictionData).filter(
                PredictionData.target_id == model_record.target_id,
                PredictionData.measured_value != None
            ).count()
            
            status_data = model_record.to_dict()
            status_data['sample_count'] = sample_count
            status_data['status'] = 'trained' if model_record.trained_at else 'not_trained'
            
            return status_data, "Status obtido com sucesso"
        finally:
            db.close()
    
    def _continuous_prediction_worker(self, line_name, stop_event, interval=5):
        """
        Esta é a nova thread de worker. UMA por LINHA.
        Ela lê o OPC uma vez e executa todos os modelos ativos para essa linha.
        """
        logging.info(f"✅ [WORKER-PRED] Iniciando worker de predição para a LINHA: {line_name}")
        
        while not stop_event.wait(interval):
            try:
                db = next(get_db())
                active_models = []
                try:
                    # 1. Buscar todos os modelos ATIVOS para esta linha
                    active_models = db.query(PredictionModel).join(PredictionTarget).filter(
                        PredictionTarget.line_name == line_name,
                        PredictionModel.is_active == True,
                        PredictionModel.trained_at != None # Só prediz com modelos treinados
                    ).all()
                finally:
                    db.close()

                # 2. Se não há modelos ativos, o worker pode parar
                if not active_models:
                    logging.info(f"⚠️  [WORKER-PRED] Nenhum modelo ativo encontrado para {line_name}. Encerrando worker.")
                    break # Encerra o loop while

                # 3. Ler dados do OPC (APENAS UMA VEZ)
                opc_values, opc_error = opc_client.get_opc_values(line_name)
                if opc_error:
                    logging.warning(f"⚠️  [WORKER-PRED] Falha ao ler dados OPC para {line_name}: {opc_error}")
                    continue # Pula esta iteração

                logging.info(f"✅ [WORKER-PRED] {line_name}: Dados OPC lidos. Executando predições para {len(active_models)} modelo(s)...")

                # 4. Loop (rápido, em memória) para executar cada predição
                for model in active_models:
                    try:
                        # Chamamos a função 'predict' interna, passando os dados OPC que já lemos
                        self.predict(model.id, opc_values=opc_values)
                    except Exception as e_pred:
                        logging.error(f"❌ [WORKER-PRED] Falha na predição do modelo {model.id}: {e_pred}")
                
            except Exception as e_loop:
                logging.error(f"❌ [WORKER-PRED] Erro crítico no loop para {line_name}: {e_loop}", exc_info=True)
        
        logging.info(f"🛑 [WORKER-PRED] Worker de predição para {line_name} foi encerrado.")
        # Limpa a si mesmo do dicionário de workers
        if line_name in self.line_prediction_workers:
            del self.line_prediction_workers[line_name]
            
            
    def start_continuous_predictions(self, model_id, interval=5):
        """Inicia predições contínuas para um modelo"""
        db = next(get_db())
        try:
            # 1. Encontrar o modelo e sua linha
            model = db.query(PredictionModel).filter(PredictionModel.id == model_id).first()
            if not model: return False, "Modelo não encontrado"
            if not model.trained_at: return False, "Modelo não está treinado"
            
            target = db.query(PredictionTarget).filter(PredictionTarget.id == model.target_id).first()
            if not target: return False, "Target não encontrado"
            line_name = target.line_name

            # 2. Marcar o modelo como ATIVO no banco
            model.is_active = True
            db.commit()

            # 3. Verificar se um worker para esta LINHA já existe
            if line_name in self.line_prediction_workers:
                logging.info(f"✅ [WORKER-PRED] Worker para {line_name} já está rodando. Modelo {model_id} adicionado ao loop.")
                return True, "Modelo ativado. Worker já estava em execução."

            # 4. Se não existe, criar um novo worker para a LINHA
            stop_event = threading.Event()
            thread = threading.Thread(
                target=self._continuous_prediction_worker, 
                args=(line_name, stop_event, interval), 
                daemon=True
            )
            thread.start()
            
            self.line_prediction_workers[line_name] = {
                'thread': thread,
                'stop_event': stop_event,
                'interval': interval
            }
            
            return True, f"Worker de predição para a linha {line_name} iniciado."
            
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()
            
            
            
    
    def stop_continuous_predictions(self, model_id):
        """Para predições contínuas para um modelo (apenas o desativa)"""
        db = next(get_db())
        try:
            # 1. Encontrar o modelo
            model = db.query(PredictionModel).filter(PredictionModel.id == model_id).first()
            if not model: return False, "Modelo não encontrado"

            # 2. Marcar o modelo como INATIVO
            # O worker da linha (se existir) vai parar sozinho na próxima iteração
            # se este for o último modelo ativo.
            model.is_active = False
            db.commit()
            
            logging.info(f"🛑 Modelo {model_id} desativado. O worker da linha irá parar se não houver mais modelos.")
            return True, f"Modelo {model_id} desativado com sucesso."
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()
    
    def is_continuous_predictions_active(self, model_id):
        """Verifica se um modelo está marcado como ATIVO no banco"""
        db = next(get_db())
        try:
            # A fonte da verdade agora é o banco de dados
            model = db.query(PredictionModel).filter(PredictionModel.id == model_id).first()
            if not model:
                return False
            return model.is_active
        finally:
            db.close()
# Instância global do preditor
generic_predictor = GenericPredictor()