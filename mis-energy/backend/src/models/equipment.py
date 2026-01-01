# backend/src/models/equipment.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from src.models.user import db

class Equipment(db.Model):
    """Modelo para equipamentos de medição de energia"""
    __tablename__ = 'equipments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    tag = db.Column(db.String(50), unique=True, nullable=True) # Tag ISA (ex: FAC1-LIN2-MTR-001)
    description = db.Column(db.Text)
    location = db.Column(db.String(200))  # Localização física
    area = db.Column(db.String(100))  # Área/setor
    standard_consumption = db.Column(db.Float)  # Consumo padrão em kWh
    
    # Configurações Modbus
    hierarchy_id = db.Column(db.Integer, db.ForeignKey('hierarchies.id'), nullable=True)
    
    # Classificação do Equipamento
    equipment_type = db.Column(db.String(50), default='generic')  # motor, resistor, lighting, generic
    parameters = db.Column(db.JSON, default={})  # Parâmetros específicos (RPM, potência, etc)
    
    # Configurações de Endereçamento (Modbus ou OPC)
    address_type = db.Column(db.String(20), default='modbus')  # modbus, opc
    
    # Configurações Modbus (agora nullable pois pode ser OPC)
    gateway_id = db.Column(db.Integer, db.ForeignKey('gateways.id'), nullable=True)
    modbus_address = db.Column(db.Integer, nullable=True)
    register_type = db.Column(db.String(20), default='holding')
    
    # Configurações OPC UA
    opc_node_id = db.Column(db.String(200), nullable=True)  # NodeID do OPC UA (ex: ns=2;s=Machine1.Speed)
    
    # Configurações Modbus específicas
    modbus_register = db.Column(db.Integer, nullable=True)  # Endereço de memória Modbus (ex: 40001)
    data_type = db.Column(db.String(20), default='float32')
    scale_factor = db.Column(db.Float, default=1.0)
    unit = db.Column(db.String(10), default='kWh')
    
    # Configurações de monitoramento
    is_active = db.Column(db.Boolean, default=True)
    polling_interval = db.Column(db.Integer, default=60)
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_reading_at = db.Column(db.DateTime)
    last_value = db.Column(db.Float)
    
    def __repr__(self):
        return f'<Equipment {self.name} ({self.equipment_type})>'
    
    def to_dict(self):
        """Converte o modelo para dicionário"""
        return {
            'id': self.id,
            'name': self.name,
            'tag': self.tag,
            'description': self.description,
            'location': self.location, # Mantido para compatibilidade
            'area': self.area, # Mantido para compatibilidade
            'hierarchy_id': self.hierarchy_id,
            'hierarchy_path': self._get_hierarchy_path() if self.hierarchy_id else None,
            'equipment_type': self.equipment_type,
            'parameters': self.parameters,
            'standard_consumption': self.standard_consumption,
            'address_type': self.address_type,
            'gateway_id': self.gateway_id,
            'gateway_name': self.gateway.name if self.gateway else None,
            'modbus_address': self.modbus_address,
            'opc_node_id': self.opc_node_id,
            'modbus_register': self.modbus_register,
            'register_type': self.register_type,
            'data_type': self.data_type,
            'scale_factor': self.scale_factor,
            'unit': self.unit,
            'is_active': self.is_active,
            'polling_interval': self.polling_interval,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_reading_at': self.last_reading_at.isoformat() if self.last_reading_at else None,
            'last_value': self.last_value
        }
    
    def _get_hierarchy_path(self):
        """Retorna o caminho da hierarquia como string"""
        if not self.hierarchy:
            return None
        
        path = [self.hierarchy.name]
        current = self.hierarchy
        while current.parent:
            current = current.parent
            path.insert(0, current.name)
        return " > ".join(path)
    
    @classmethod
    def from_dict(cls, data):
        """Cria instância a partir de dicionário"""
        return cls(
            name=data.get('name'),
            tag=data.get('tag'),
            description=data.get('description'),
            location=data.get('location'),
            area=data.get('area'),
            hierarchy_id=data.get('hierarchy_id'),
            equipment_type=data.get('equipment_type', 'generic'),
            parameters=data.get('parameters', {}),
            standard_consumption=data.get('standard_consumption'),
            address_type=data.get('address_type', 'modbus'),
            gateway_id=data.get('gateway_id'),
            modbus_address=data.get('modbus_address'),
            opc_node_id=data.get('opc_node_id'),
            modbus_register=data.get('modbus_register'),
            register_type=data.get('register_type', 'holding'),
            data_type=data.get('data_type', 'float32'),
            scale_factor=data.get('scale_factor', 1.0),
            unit=data.get('unit', 'kWh'),
            is_active=data.get('is_active', True),
            polling_interval=data.get('polling_interval', 60)
        )
