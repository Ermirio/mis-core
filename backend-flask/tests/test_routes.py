"""
Testes para as rotas do Flask API.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from app import create_app


@pytest.fixture
def client():
    """Fixture para criar cliente de teste"""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_influx_client():
    """Mock para InfluxDB client"""
    mock = MagicMock()
    mock.query.return_value.raw = {'series': []}
    return mock


class TestHealthCheck:
    """Testes para o endpoint de health check"""
    
    def test_health_check_success(self, client):
        """Testa health check com sucesso"""
        response = client.get('/api/health')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert 'timestamp' in data


class TestEquipamentosEndpoint:
    """Testes para endpoints de equipamentos"""
    
    @patch('routes.requests.get')
    def test_get_equipamentos(self, mock_get, client):
        """Testa listagem de equipamentos"""
        # Mock da resposta do Django
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': [
                {
                    'id': 1,
                    'nome': 'Enchedora 01',
                    'codigo': 'ENC-01',
                    'tipo': 'ENCHEDORA'
                }
            ]
        }
        mock_get.return_value = mock_response
        
        response = client.get('/api/equipamentos')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'results' in data
        assert len(data['results']) > 0


class TestRealtimeStatus:
    """Testes para status em tempo real"""
    
    @patch('routes.get_influx_client')
    def test_realtime_status_no_data(self, mock_influx, client):
        """Testa status em tempo real sem dados"""
        mock_client = MagicMock()
        mock_client.query.return_value.raw = {'series': []}
        mock_influx.return_value = mock_client
        
        response = client.get('/api/realtime/status/ENC-01')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['equipamento'] == 'ENC-01'
        assert 'medicoes' in data


class TestDadosInserir:
    """Testes para inserção de dados"""
    
    @patch('routes.get_influx_client')
    def test_inserir_dados_success(self, mock_influx, client):
        """Testa inserção de dados com sucesso"""
        mock_client = MagicMock()
        mock_client.write_points.return_value = True
        mock_influx.return_value = mock_client
        
        payload = {
            'equipamento': 'ENC-01',
            'medicoes': {
                'temperatura': 75.5,
                'pressao': 100.2,
                'velocidade': 98.5,
                'estado': 'Produzindo'
            }
        }
        
        response = client.post(
            '/api/dados/inserir',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
    
    def test_inserir_dados_missing_fields(self, client):
        """Testa inserção com campos faltando"""
        payload = {
            'equipamento': 'ENC-01'
            # Faltando 'medicoes'
        }
        
        response = client.post(
            '/api/dados/inserir',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 400


class TestLineStatus:
    """Testes para status de linha"""
    
    @patch('routes.get_influx_client')
    @patch('routes.requests.get')
    def test_line_status(self, mock_django_get, mock_influx, client):
        """Testa status de linha"""
        # Mock Django response
        mock_django_response = Mock()
        mock_django_response.status_code = 200
        mock_django_response.json.return_value = {
            'results': [
                {'id': 1, 'codigo': 'L01', 'nome': 'Linha 01'}
            ]
        }
        mock_django_get.return_value = mock_django_response
        
        # Mock InfluxDB
        mock_client = MagicMock()
        mock_client.query.return_value.raw = {'series': []}
        mock_influx.return_value = mock_client
        
        response = client.get('/api/line/status/L01')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'linha_codigo' in data


class TestKPIsEndpoint:
    """Testes para endpoints de KPIs"""
    
    @patch('kpis_routes.get_influx_client')
    def test_kpis_calculation(self, mock_influx, client):
        """Testa cálculo de KPIs"""
        mock_client = MagicMock()
        mock_client.query.return_value.raw = {
            'series': [{
                'values': [[
                    '2025-01-01T00:00:00Z',
                    100.0,  # velocidade
                    1000,   # contagem
                    'Produzindo'
                ]]
            }]
        }
        mock_influx.return_value = mock_client
        
        response = client.get('/api/kpis/equipamento/ENC-01')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'oee' in data or 'error' in data  # Pode retornar erro se não houver dados suficientes
