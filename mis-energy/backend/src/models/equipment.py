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
    
    # Tipo de Medidor: 'energy' (energia) ou 'production' (produção)
    meter_type = db.Column(db.String(20), default='energy', nullable=False)
    
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
    
    # Configurações OPC UA - Endereço legado (mantido para compatibilidade)
    opc_node_id = db.Column(db.String(200), nullable=True)  # NodeID do OPC UA (ex: ns=2;s=Machine1.Speed)
    
    # ===== MULTI-METRIC ADDRESSES (ISA 101/88) =====
    # Potência Ativa (kW) - Real-time power
    opc_node_power_kw = db.Column(db.String(200), nullable=True)
    modbus_register_power_kw = db.Column(db.Integer, nullable=True)
    
    # Energia Acumulada (kWh) - Totalizer
    opc_node_energy_kwh = db.Column(db.String(200), nullable=True)
    modbus_register_energy_kwh = db.Column(db.Integer, nullable=True)
    
    # Demanda Máxima (kW) - Peak demand
    opc_node_demand_kw = db.Column(db.String(200), nullable=True)
    modbus_register_demand_kw = db.Column(db.Integer, nullable=True)
    
    # Fator de Potência (0-1 ou 0-100)
    opc_node_power_factor = db.Column(db.String(200), nullable=True)
    modbus_register_power_factor = db.Column(db.Integer, nullable=True)
    
    # ===== POWER QUALITY (opcional) =====
    # Tensão por fase (V)
    opc_node_voltage_a = db.Column(db.String(200), nullable=True)
    opc_node_voltage_b = db.Column(db.String(200), nullable=True)
    opc_node_voltage_c = db.Column(db.String(200), nullable=True)
    
    # Corrente por fase (A)
    opc_node_current_a = db.Column(db.String(200), nullable=True)
    opc_node_current_b = db.Column(db.String(200), nullable=True)
    opc_node_current_c = db.Column(db.String(200), nullable=True)
    
    # ===== COST/TARIFF CONFIGURATION =====
    tariff_kwh = db.Column(db.Float, default=0.5)  # R$/kWh
    tariff_demand = db.Column(db.Float, nullable=True)  # R$/kW demanda
    shift_config = db.Column(db.JSON, default={})  # {start: '06:00', end: '18:00', name: 'Turno A'}
    
    # Configurações Modbus específicas (legado)
    modbus_register = db.Column(db.Integer, nullable=True)  # Endereço de memória Modbus (ex: 40001)
    data_type = db.Column(db.String(20), default='float32')
    scale_factor = db.Column(db.Float, default=1.0)
    unit = db.Column(db.String(10), default='kWh')
    
    # Configurações de monitoramento
    is_active = db.Column(db.Boolean, default=True)
    is_entry_point = db.Column(db.Boolean, default=False)  # Se é o medidor de entrada da hierarquia (totalizador)
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
            'hierarchy_level': self._get_hierarchy_level() if self.hierarchy_id else None,
            'meter_type': self.meter_type,
            'equipment_type': self.equipment_type,
            'parameters': self.parameters,
            'standard_consumption': self.standard_consumption,
            'address_type': self.address_type,
            'gateway_id': self.gateway_id,
            'gateway': {'id': self.gateway.id, 'name': self.gateway.name} if self.gateway else None,
            'gateway_name': self.gateway.name if self.gateway else None,
            'modbus_address': self.modbus_address,
            'opc_node_id': self.opc_node_id,
            # Multi-metric addresses
            'opc_node_power_kw': self.opc_node_power_kw,
            'opc_node_energy_kwh': self.opc_node_energy_kwh,
            'opc_node_demand_kw': self.opc_node_demand_kw,
            'opc_node_power_factor': self.opc_node_power_factor,
            'modbus_register_power_kw': self.modbus_register_power_kw,
            'modbus_register_energy_kwh': self.modbus_register_energy_kwh,
            'modbus_register_demand_kw': self.modbus_register_demand_kw,
            'modbus_register_power_factor': self.modbus_register_power_factor,
            # Power quality
            'opc_node_voltage_a': self.opc_node_voltage_a,
            'opc_node_voltage_b': self.opc_node_voltage_b,
            'opc_node_voltage_c': self.opc_node_voltage_c,
            'opc_node_current_a': self.opc_node_current_a,
            'opc_node_current_b': self.opc_node_current_b,
            'opc_node_current_c': self.opc_node_current_c,
            # Cost configuration
            'tariff_kwh': self.tariff_kwh,
            'tariff_demand': self.tariff_demand,
            'shift_config': self.shift_config,
            'modbus_register': self.modbus_register,
            'register_type': self.register_type,
            'data_type': self.data_type,
            'scale_factor': self.scale_factor,
            'unit': self.unit,
            'is_active': self.is_active,
            'is_entry_point': self.is_entry_point,
            'polling_interval': self.polling_interval,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_reading_at': self.last_reading_at.isoformat() if self.last_reading_at else None,
            'last_value': self.last_value
        }
    
    def _get_hierarchy_level(self):
        """Retorna o tipo de nível hierárquico (factory, area, line, machine_group)"""
        if not self.hierarchy:
            return None
        return self.hierarchy.type
    
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
            meter_type=data.get('meter_type', 'energy'),
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
            is_entry_point=data.get('is_entry_point', False),
            polling_interval=data.get('polling_interval', 60)
        )

