# backend/src/models/metrics_config.py
from src.models.user import db
from datetime import datetime

class MetricsConfig(db.Model):
    """Configurações globais de métricas do sistema"""
    __tablename__ = 'metrics_config'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Custo de energia
    kwh_cost_brl = db.Column(db.Float, default=0.85, nullable=False)  # R$/kWh
    
    # Taxas de câmbio
    usd_brl_rate = db.Column(db.Float, default=5.0, nullable=False)  # USD para BRL
    eur_brl_rate = db.Column(db.Float, default=5.5, nullable=False)  # EUR para BRL
    
    # Unidade de produção
    production_unit = db.Column(db.String(20), default='ton', nullable=False)  # ton, kg, pieces
    production_unit_label = db.Column(db.String(50), default='Toneladas', nullable=False)
    
    # Configuração de simulação
    simulation_enabled = db.Column(db.Boolean, default=True, nullable=False)
    
    # Metadados
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.String(100))
    
    def to_dict(self):
        return {
            'id': self.id,
            'kwh_cost_brl': self.kwh_cost_brl,
            'usd_brl_rate': self.usd_brl_rate,
            'eur_brl_rate': self.eur_brl_rate,
            'production_unit': self.production_unit,
            'production_unit_label': self.production_unit_label,
            'simulation_enabled': self.simulation_enabled,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'updated_by': self.updated_by,
            # Campos calculados
            'kwh_cost_usd': round(self.kwh_cost_brl / self.usd_brl_rate, 4) if self.usd_brl_rate else 0,
            'kwh_cost_eur': round(self.kwh_cost_brl / self.eur_brl_rate, 4) if self.eur_brl_rate else 0
        }
    
    @classmethod
    def get_instance(cls):
        """Retorna a única instância de configuração (singleton)"""
        config = cls.query.first()
        if not config:
            config = cls()
            db.session.add(config)
            db.session.commit()
        return config
