# backend/tests/test_models.py
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.main_backend import app, db
from src.models.hierarchy_model import Hierarchy
from src.models.equipment import Equipment
from src.models.gateway import Gateway

def test_hierarchy_creation():
    # Configurar para usar SQLite em memória para testes
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TESTING'] = True
    
    with app.app_context():
        # Limpar banco
        db.drop_all()
        db.create_all()
        
        print("Testing Hierarchy Creation...")
        
        # Criar Fábrica
        factory = Hierarchy(name="Factory A", type="factory", description="Main Factory")
        db.session.add(factory)
        db.session.commit()
        
        # Criar Área
        area = Hierarchy(name="Production", type="area", parent_id=factory.id)
        db.session.add(area)
        db.session.commit()
        
        # Criar Linha
        line = Hierarchy(name="Line 1", type="line", parent_id=area.id)
        db.session.add(line)
        db.session.commit()
        
        # Verificar
        assert Hierarchy.query.count() == 3
        assert line.parent.name == "Production"
        assert line.parent.parent.name == "Factory A"
        print("Hierarchy Creation: OK")
        
        return line.id

def test_equipment_creation(hierarchy_id):
    with app.app_context():
        print("\nTesting Equipment Creation...")
        
        # Criar Gateway (necessário para Modbus)
        gateway = Gateway(name="Gateway 1", ip_address="192.168.1.10")
        db.session.add(gateway)
        db.session.commit()
        
        # 1. Equipamento Modbus
        motor = Equipment(
            name="Conveyor Motor",
            hierarchy_id=hierarchy_id,
            equipment_type="motor",
            parameters={"rpm": 1750, "power_cv": 10},
            address_type="modbus",
            gateway_id=gateway.id,
            modbus_address=1,
            opc_register=40001
        )
        db.session.add(motor)
        
        # 2. Equipamento OPC
        sensor = Equipment(
            name="Temp Sensor",
            hierarchy_id=hierarchy_id,
            equipment_type="generic",
            address_type="opc",
            opc_node_id="ns=2;s=Temp1"
        )
        db.session.add(sensor)
        
        db.session.commit()
        
        # Verificar
        saved_motor = Equipment.query.filter_by(name="Conveyor Motor").first()
        assert saved_motor.parameters['rpm'] == 1750
        assert saved_motor.hierarchy.name == "Line 1"
        assert saved_motor.address_type == "modbus"
        
        saved_sensor = Equipment.query.filter_by(name="Temp Sensor").first()
        assert saved_sensor.address_type == "opc"
        assert saved_sensor.opc_node_id == "ns=2;s=Temp1"
        assert saved_sensor.gateway_id is None
        
        print("Equipment Creation: OK")

if __name__ == "__main__":
    try:
        line_id = test_hierarchy_creation()
        test_equipment_creation(line_id)
        print("\nALL TESTS PASSED")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
