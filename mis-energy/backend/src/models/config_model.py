# backend/src/models/config_model.py
from src.models.user import db
import json
from datetime import datetime

class DatabaseConfig(db.Model):
    """Modelo para armazenar configurações de banco de dados no DB"""
    __tablename__ = 'database_configs'

    id = db.Column(db.Integer, primary_key=True)
    config_type = db.Column(db.String(20), nullable=False)  # 'mysql' ou 'influxdb'
    config_data = db.Column(db.Text, nullable=False)  # JSON com as credenciais
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_config_dict(self):
        """Retorna a configuração como um dicionário Python."""
        try:
            return json.loads(self.config_data)
        except json.JSONDecodeError:
            return {}

    def set_config_dict(self, config_dict):
        """Define a configuração a partir de um dicionário Python."""
        self.config_data = json.dumps(config_dict)

    @classmethod
    def get_mysql_config(cls):
        """Retorna a configuração ativa do MySQL do banco de dados."""
        config = cls.query.filter_by(config_type='mysql', is_active=True).first()
        return config.get_config_dict() if config else None

    @classmethod
    def get_influxdb_config(cls):
        """Retorna a configuração ativa do InfluxDB do banco de dados."""
        config = cls.query.filter_by(config_type='influxdb', is_active=True).first()
        return config.get_config_dict() if config else None

    @classmethod
    def set_mysql_config(cls, config_dict):
        """Define ou atualiza a configuração do MySQL no banco de dados."""
        cls.query.filter_by(config_type='mysql').update({'is_active': False})
        config = cls(config_type='mysql')
        config.set_config_dict(config_dict)
        db.session.add(config)
        db.session.commit()
        return config

    @classmethod
    def set_influxdb_config(cls, config_dict):
        """Define ou atualiza a configuração do InfluxDB no banco de dados."""
        cls.query.filter_by(config_type='influxdb').update({'is_active': False})
        config = cls(config_type='influxdb')
        config.set_config_dict(config_dict)
        db.session.add(config)
        db.session.commit()
        return config