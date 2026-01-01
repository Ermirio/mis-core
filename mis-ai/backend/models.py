# models.py - Versão melhorada para suportar predições genéricas
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, ForeignKey, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()
Base = declarative_base()

class Line(Base):
    """Linhas de produção - agora com mais flexibilidade"""
    __tablename__ = 'lines'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relacionamentos
    prediction_targets = relationship('PredictionTarget', back_populates='line_obj')
    opc_variables = relationship('OPCVariables', back_populates='line_obj')
    opc_logs = relationship('OPCLogs', back_populates='line_obj')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active
        }

class PredictionTarget(Base):
    """Targets de predição - o que queremos predizer (densidade, temperatura, etc.)"""
    __tablename__ = 'prediction_targets'
    id = Column(Integer, primary_key=True)
    line_name = Column(String(50), ForeignKey('lines.name'), nullable=False)
    target_name = Column(String(100), nullable=False)  # Ex: "Densidade", "Temperatura", "Pressão"
    target_unit = Column(String(20), nullable=True)    # Ex: "g/cm³", "°C", "bar"
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relacionamentos
    line_obj = relationship('Line', back_populates='prediction_targets')
    prediction_data = relationship('PredictionData', back_populates='target_obj')
    prediction_models = relationship('PredictionModel', back_populates='target_obj')

    def to_dict(self):
        return {
            'id': self.id,
            'line_name': self.line_name,
            'target_name': self.target_name,
            'target_unit': self.target_unit,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active
        }

class PredictionModel(Base):
    """Modelos de predição com configurações específicas"""
    __tablename__ = 'prediction_models'
    id = Column(Integer, primary_key=True)
    target_id = Column(Integer, ForeignKey('prediction_targets.id'), nullable=False)
    model_name = Column(String(100), nullable=False)  # Ex: "RandomForest_v1", "XGBoost_optimized"
    model_type = Column(String(50), default='RandomForest')  # RandomForest, XGBoost, LinearRegression, etc.
    
    # Parâmetros do modelo (JSON flexível)
    model_parameters = Column(JSON, nullable=True)  # Ex: {"n_estimators": 100, "max_depth": 10}
    
    # Métricas de performance
    mse = Column(Float, nullable=True)
    r2_score = Column(Float, nullable=True)
    feature_importances = Column(JSON, nullable=True)
    
    # Metadados
    trained_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    model_file_path = Column(String(255), nullable=True)  # Caminho para o arquivo do modelo
    
    # Relacionamentos
    target_obj = relationship('PredictionTarget', back_populates='prediction_models')

    def to_dict(self):
        return {
            'id': self.id,
            'target_id': self.target_id,
            'model_name': self.model_name,
            'model_type': self.model_type,
            'model_parameters': self.model_parameters,
            'mse': self.mse,
            'r2_score': self.r2_score,
            'feature_importances': self.feature_importances,
            'trained_at': self.trained_at.isoformat() if self.trained_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active,
            'model_file_path': self.model_file_path
        }

class PredictionData(Base):
    """Dados de predição - valores medidos e preditos"""
    __tablename__ = 'prediction_data'
    id = Column(Integer, primary_key=True)
    target_id = Column(Integer, ForeignKey('prediction_targets.id'), nullable=False)
    model_id = Column(Integer, ForeignKey('prediction_models.id'), nullable=True)  # Modelo usado para predição
    
    measured_value = Column(Float, nullable=True)    # Valor medido (para treinamento)
    predicted_value = Column(Float, nullable=True)   # Valor predito
    confidence_std_dev = Column(Float, nullable=True) # Desvio padrão da predição
    
    timestamp = Column(DateTime, default=datetime.utcnow)
    opc_values = Column(JSON, nullable=True)  # Valores das variáveis OPC no momento
    data_source = Column(String(20), default='manual')  # 'manual' ou 'opc'
    
    # Relacionamentos
    target_obj = relationship('PredictionTarget', back_populates='prediction_data')

    def to_dict(self):
        return {
            'id': self.id,
            'target_id': self.target_id,
            'model_id': self.model_id,
            'measured_value': self.measured_value,
            'predicted_value': self.predicted_value,
            'confidence_std_dev': self.confidence_std_dev,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'opc_values': self.opc_values,
            'data_source': self.data_source
        }

class OPCVariables(Base):
    """Variáveis OPC - mantém compatibilidade com versão anterior"""
    __tablename__ = 'opc_variables'
    id = Column(Integer, primary_key=True)
    line_name = Column(String(50), ForeignKey('lines.name'), nullable=False)
    node_id = Column(String(100), nullable=False)
    variable_name = Column(String(50), nullable=False)
    type = Column(String(20), nullable=False)
    type_category = Column(String(10), default='read')  # 'read' ou 'write'
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    
    line_obj = relationship('Line', back_populates='opc_variables')

    def to_dict(self):
        return {
            'id': self.id,
            'line_name': self.line_name,
            'node_id': self.node_id,
            'variable_name': self.variable_name,
            'type': self.type,
            'type_category': self.type_category,
            'description': self.description,
            'is_active': self.is_active
        }

class OPCLogs(Base):
    """Logs OPC - mantém compatibilidade com versão anterior"""
    __tablename__ = 'opc_logs'
    id = Column(Integer, primary_key=True)
    line_name = Column(String(50), ForeignKey('lines.name'), nullable=False)
    node_id = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    line_obj = relationship('Line', back_populates='opc_logs')

    def to_dict(self):
        return {
            'id': self.id,
            'line_name': self.line_name,
            'node_id': self.node_id,
            'value': self.value,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

class OPCServerConfig(Base):
    """Configuração singleton do servidor OPC"""
    __tablename__ = 'opc_server_config'
    id = Column(Integer, primary_key=True)
    opc_url = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'opc_url': self.opc_url,
            'is_active': self.is_active,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# Configuração do banco de dados
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///prediction_app.db')

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Cria todas as tabelas no banco de dados"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Gerador de sessões do banco de dados"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Dados padrão para inicialização
DEFAULT_LINES = [
    {'name': 'L01', 'description': 'Linha de Produção 01'},
    {'name': 'L02', 'description': 'Linha de Produção 02'},
    {'name': 'L06', 'description': 'Linha de Produção 06'},
    {'name': 'L10', 'description': 'Linha de Produção 10'},
    {'name': 'L16', 'description': 'Linha de Produção 16'}
]

def create_default_data():
    """Cria dados padrão no banco de dados"""
    db = SessionLocal()
    try:
        # Criar linhas padrão
        for line_data in DEFAULT_LINES:
            if not db.query(Line).filter_by(name=line_data['name']).first():
                line = Line(name=line_data['name'], description=line_data['description'])
                db.add(line)
        
        # Criar target padrão de densidade para cada linha
        for line_data in DEFAULT_LINES:
            line_name = line_data['name']
            if not db.query(PredictionTarget).filter_by(line_name=line_name, target_name='Densidade').first():
                target = PredictionTarget(
                    line_name=line_name,
                    target_name='Densidade',
                    target_unit='g/cm³',
                    description='Densidade do material produzido'
                )
                db.add(target)
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

