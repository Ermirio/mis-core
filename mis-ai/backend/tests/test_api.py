import pytest
import json
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import create_tables

@pytest.fixture
def client():
    app.config['TESTING'] = True
    create_tables()
    with app.test_client() as client:
        yield client

def test_health_check(client):
    """Test health check endpoint"""
    response = client.get('/api/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'status' in data

def test_save_density_data(client):
    """Test saving density data"""
    test_data = {
        'line': 'L01',
        'measured_density': 1.25
    }
    
    response = client.post('/api/density', 
                          data=json.dumps(test_data),
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'message' in data
    assert 'id' in data

def test_get_density_data(client):
    """Test retrieving density data"""
    # First save some data
    test_data = {
        'line': 'L01',
        'measured_density': 1.25
    }
    
    client.post('/api/density', 
                data=json.dumps(test_data),
                content_type='application/json')
    
    # Then retrieve it
    response = client.get('/api/density?line=L01')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)
    assert len(data) > 0

def test_register_opc_variable(client):
    """Test registering OPC variable"""
    test_data = {
        'line': 'L01',
        'node_id': 'ns=2;i=1001',
        'variable_name': 'Temperature',
        'type': 'Float'
    }
    
    response = client.post('/api/opc-variables',
                          data=json.dumps(test_data),
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'message' in data
    assert 'id' in data

def test_get_opc_variables(client):
    """Test retrieving OPC variables"""
    # First register a variable
    test_data = {
        'line': 'L01',
        'node_id': 'ns=2;i=1001',
        'variable_name': 'Temperature',
        'type': 'Float'
    }
    
    client.post('/api/opc-variables',
                data=json.dumps(test_data),
                content_type='application/json')
    
    # Then retrieve it
    response = client.get('/api/opc-variables?line=L01')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)
    assert len(data) > 0

if __name__ == '__main__':
    pytest.main([__file__])

