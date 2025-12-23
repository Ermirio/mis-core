"""
Configuração de fixtures para testes do Flask.
"""
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_influx_client():
    """Mock para InfluxDB client"""
    mock = MagicMock()
    mock.query.return_value.raw = {'series': []}
    mock.write_points.return_value = True
    return mock


@pytest.fixture
def sample_equipment_data():
    """Dados de exemplo para equipamento"""
    return {
        'id': 1,
        'nome': 'Enchedora 01',
        'codigo': 'ENC-01',
        'tipo': 'ENCHEDORA',
        'linha': 1,
        'linha_nome': 'Linha 01',
        'velocidade_nominal': 100.0,
        'velocidade_maxima': 120.0
    }


@pytest.fixture
def sample_production_data():
    """Dados de exemplo de produção"""
    return {
        'equipamento': 'ENC-01',
        'medicoes': {
            'temperatura': 75.5,
            'pressao': 100.2,
            'velocidade_atual': 98.5,
            'contagem_entrada': 1000,
            'contagem_saida': 950,
            'estado': 'Produzindo'
        }
    }
