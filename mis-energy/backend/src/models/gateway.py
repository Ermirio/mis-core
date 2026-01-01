from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from src.models.user import db

class Gateway(db.Model):
    """Modelo para gateways de comunicação (Modbus TCP ou OPC UA)"""
    __tablename__ = 'gateways'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Tipo de protocolo: 'modbus' ou 'opc'
    protocol_type = db.Column(db.String(20), nullable=False, default='modbus')
    
    # Configurações Modbus TCP
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4 ou IPv6
    port = db.Column(db.Integer, nullable=True, default=502)  # Porta Modbus TCP padrão
    
    # Configurações OPC UA
    opc_url = db.Column(db.String(255), nullable=True)  # ex: opc.tcp://192.168.1.100:4840
    security_mode = db.Column(db.String(50), nullable=True, default='None')  # None, Sign, SignAndEncrypt
    
    # Configurações comuns
    timeout = db.Column(db.Integer, default=5)  # Timeout em segundos
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamento com equipamentos
    equipments = db.relationship('Equipment', backref='gateway', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        if self.protocol_type == 'opc':
            return f'<Gateway {self.name} (OPC: {self.opc_url})>'
        return f'<Gateway {self.name} (Modbus: {self.ip_address}:{self.port})>'
    
    def to_dict(self):
        """Converte o modelo para dicionário"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'protocol_type': self.protocol_type,
            'ip_address': self.ip_address,
            'port': self.port,
            'opc_url': self.opc_url,
            'security_mode': self.security_mode,
            'timeout': self.timeout,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'equipment_count': len(self.equipments) if self.equipments else 0
        }
    
    @classmethod
    def from_dict(cls, data):
        """Cria instância a partir de dicionário"""
        return cls(
            name=data.get('name'),
            description=data.get('description'),
            protocol_type=data.get('protocol_type', 'modbus'),
            ip_address=data.get('ip_address'),
            port=data.get('port', 502),
            opc_url=data.get('opc_url'),
            security_mode=data.get('security_mode', 'None'),
            timeout=data.get('timeout', 5),
            is_active=data.get('is_active', True)
        )
