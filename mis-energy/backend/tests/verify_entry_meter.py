import sys
import os
import json
from flask import Flask

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models.user import db
from src.models.equipment import Equipment
from src.models.hierarchy_model import Hierarchy
from src.models.gateway import Gateway
from src.routes.equipment import equipment_bp
from src.routes.hierarchy_routes import hierarchy_bp

def run_tests():
    print("Starting Entry Meter Logic Verification (Standalone App)...")
    
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TESTING'] = True
    
    db.init_app(app)
    app.register_blueprint(equipment_bp, url_prefix='/api')
    app.register_blueprint(hierarchy_bp, url_prefix='/api')
    
    with app.app_context():
        db.create_all()
        
        # Setup: Create test hierarchy

        # Create Factory
        factory = Hierarchy(name="TEST_HIER_FACTORY", type="factory")
        db.session.add(factory)
        db.session.commit()
        
        # Create Area
        area = Hierarchy(name="TEST_HIER_AREA", type="area", parent_id=factory.id)
        db.session.add(area)
        db.session.commit()
        
        print(f"Created Hierarchy: Factory ID {factory.id}, Area ID {area.id}")
        
        client = app.test_client()
        
        # Test 1: Create first entry meter (Should SUCCEED)
        print("\nTest 1: Create first entry meter in Area...")
        payload1 = {
            "name": "TEST_ENTRY_METER_1",
            "hierarchy_id": area.id,
            "is_entry_point": True,
            "meter_type": "energy",
            "gateway_id": None
        }
        res1 = client.post('/api/equipments', json=payload1)
        if res1.status_code == 201:
            print("✅ SUCCESS: First entry meter created.")
            eq1_id = res1.json['data']['id']
        else:
            print(f"❌ FAILED: {res1.json}")
            return

        # Test 2: Create second entry meter in SAME Area (Should FAIL)
        print("\nTest 2: Create second entry meter in SAME Area...")
        payload2 = {
            "name": "TEST_ENTRY_METER_DUP",
            "hierarchy_id": area.id,
            "is_entry_point": True,
            "meter_type": "energy",
            "gateway_id": None
        }
        res2 = client.post('/api/equipments', json=payload2)
        if res2.status_code == 400 and "Já existe um medidor de entrada" in res2.json.get('error', ''):
             print("✅ SUCCESS: Duplicate entry meter rejected with correct error.")
        else:
             print(f"❌ FAILED: Expected 400, got {res2.status_code}. Response: {res2.json}")

        # Test 3: Create normal meter in SAME Area (Should SUCCEED)
        print("\nTest 3: Create normal meter in SAME Area...")
        payload3 = {
            "name": "TEST_ENTRY_NORMAL",
            "hierarchy_id": area.id,
            "is_entry_point": False, 
            "meter_type": "energy",
            "gateway_id": None
        }
        res3 = client.post('/api/equipments', json=payload3)
        if res3.status_code == 201:
            print("✅ SUCCESS: Normal meter created.")
        else:
            print(f"❌ FAILED: {res3.json}")

        # Test 4: Delete the first entry meter (Should SUCCEED)
        print("\nTest 4: Delete the first entry meter...")
        res4 = client.delete(f'/api/equipments/{eq1_id}')
        if res4.status_code == 200:
             print("✅ SUCCESS: Entry meter deleted.")
        else:
             print(f"❌ FAILED: Delete failed. {res4.json}")
             
        # Test 5: Create entry meter AGAIN (Should SUCCEED now that previous is gone)
        print("\nTest 5: Create entry meter again...")
        res5 = client.post('/api/equipments', json=payload2) # Reusing payload2
        if res5.status_code == 201:
             print("✅ SUCCESS: Entry meter created after deletion of previous one.")
        else:
             print(f"❌ FAILED: {res5.json}")
             
        print("\nDone.")

if __name__ == "__main__":
    run_tests()
