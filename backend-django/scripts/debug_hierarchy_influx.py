import os
import sys
import django
from datetime import datetime, time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup Django with SQLite for Testing
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='debug-key',
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'equipamentos',
        ],
        TIME_ZONE='America/Sao_Paulo',
        USE_TZ=True,
    )

django.setup()

# Run Migrations for SQLite
from django.core.management import call_command
logger.info("Running migrations...")
call_command('migrate', verbosity=0)

# Force Localhost for InfluxDB
os.environ['INFLUXDB_HOST'] = 'localhost'

from equipamentos.models import Fabrica, Area, LinhaProducao, Equipamento, TurnoProducao
from equipamentos.agregador import AgregadorDados
from equipamentos.influx_helpers import get_influx_client



def setup_hierarchy():
    """Ensure hierarchy exists"""
    logger.info("Verifying hierarchy...")
    
    # Fabrica
    fabrica, created = Fabrica.objects.get_or_create(
        nome="Fábrica Principal",
        defaults={'codigo': 'F01'}
    )
    if created: logger.info(f"Created Fabrica: {fabrica}")
    else: logger.info(f"Found Fabrica: {fabrica}")
    
    # Area
    area, created = Area.objects.get_or_create(
        fabrica=fabrica,
        nome="Área de Envase",
        defaults={'codigo': 'A01'}
    )
    if created: logger.info(f"Created Area: {area}")
    else: logger.info(f"Found Area: {area}")
    
    # Update Lines to point to Area
    linhas = LinhaProducao.objects.all()
    for linha in linhas:
        if not linha.area:
            linha.area = area
            linha.save()
            logger.info(f"Updated Linha {linha} with Area {area}")
            
    # Create Shift (Covering whole day for simplicity)
    TurnoProducao.objects.get_or_create(
        codigo='T1',
        defaults={
            'nome': 'Turno 1',
            'hora_inicio': time(0, 0),
            'hora_fim': time(23, 59),
            'duracao_horas': 24,
            'ativo': True
        }
    )

    return fabrica, area

# Mocking InfluxDB
from unittest.mock import MagicMock, patch

def mock_query_side_effect(query):
    """Simulates InfluxDB query results"""
    query = query.strip()
    
    # Mock data for Equipment level (when aggregating for Line)
    if "FROM metricas_agregadas" in query and "nivel = 'equipamento'" in query:
        # Return 2 equipments for Line L01
        return MagicMock(get_points=lambda: [
            {
                'time': datetime.now().isoformat(),
                'codigo': 'EQ01',
                'toneladas': 10.0,
                'meta': 12.0,
                'oee': 85.0,
                'disponibilidade': 90.0,
                'performance': 95.0,
                'qualidade': 99.0,
                'producao': 1000,
                'velocidade_real': 100.0,
                'velocidade_nominal': 100.0
            },
            {
                'time': datetime.now().isoformat(),
                'codigo': 'EQ02',
                'toneladas': 20.0,
                'meta': 18.0,
                'oee': 80.0,
                'disponibilidade': 85.0,
                'performance': 90.0,
                'qualidade': 98.0,
                'producao': 2000,
                'velocidade_real': 200.0,
                'velocidade_nominal': 200.0
            }
        ])
    
    # Mock data for Line level (when aggregating for Area)
    if "FROM metricas_agregadas" in query and "nivel = 'linha'" in query:
        return MagicMock(get_points=lambda: [
            {
                'time': datetime.now().isoformat(),
                'codigo': 'L01',
                'toneladas': 30.0, # Sum of EQ01+EQ02
                'meta': 30.0,
                'oee': 81.66, # Weighted Avg
                'producao': 3000
            }
        ])

    # Mock data for Area level (when aggregating for Factory)
    if "FROM metricas_agregadas" in query and "nivel = 'area'" in query:
        return MagicMock(get_points=lambda: [
            {
                'time': datetime.now().isoformat(),
                'codigo': 'A01',
                'toneladas': 30.0,
                'meta': 30.0,
                'oee': 81.66,
                'producao': 3000
            }
        ])
        
    return MagicMock(get_points=lambda: [])

def debug_aggregation():
    fabrica, area = setup_hierarchy()
    
    # Create Line and Equipments in SQLite
    linha, _ = LinhaProducao.objects.get_or_create(
        codigo='L01', 
        defaults={
            'nome': 'Linha 01', 
            'area': area, 
            'velocidade_planejada': 1000,
            'meta_producao_hora': 1000,
            'meta_producao_turno': 8000,
            'localizacao': 'Galpão 1'
        }
    )
    
    Equipamento.objects.get_or_create(
        codigo='EQ01', 
        defaults={
            'nome': 'Equipamento 01', 
            'linha': linha, 
            'tipo': 'ENCHEDORA',
            'velocidade_nominal': 100,
            'velocidade_maxima': 120,
            'localizacao': 'Linha 1 - Início'
        }
    )
    
    Equipamento.objects.get_or_create(
        codigo='EQ02', 
        defaults={
            'nome': 'Equipamento 02', 
            'linha': linha, 
            'tipo': 'PALETIZADOR',
            'velocidade_nominal': 200,
            'velocidade_maxima': 220,
            'localizacao': 'Linha 1 - Fim'
        }
    )
    
    logger.info("Hierarchy setup complete.")
    
    # Patch the global 'influx_client' in agregador module
    with patch('equipamentos.agregador.influx_client') as mock_client:
        
        # Setup query mock
        mock_client.query.side_effect = mock_query_side_effect
        
        agregador = AgregadorDados()
        # Ensure the instance uses the mock (it should by default if patched before init)
        agregador.influx_client = mock_client
        logger.info("Running aggregation (Turno Atual)...")
        
        # We need to mock 'sincronizar_dados_producao' and 'calcular_metricas_equipamento' 
        # because they try to read raw production data from Influx which we haven't mocked fully.
        # We only want to test the HIERARCHICAL aggregation (Line->Area->Factory).
        # So we will skip the Equipment level calculation in this test by mocking it?
        # Or we can just let it fail/do nothing for equipment and focus on Line aggregation.
        # But 'agregar_turno_atual' calls everything.
        
        # Let's mock the methods inside AgregadorDados to skip base level calculation
        # and only run the hierarchical part?
        # No, 'agregar_turno_atual' calls them sequentially.
        
        # We will mock 'calcular_metricas_equipamento' to do nothing, 
        # assuming Equipment metrics are already in Influx (mocked by query).
        
        with patch.object(agregador, 'calcular_metricas_equipamento', return_value=None):
            with patch.object(agregador, 'sincronizar_dados_producao', return_value=None):
                agregador.agregar_turno_atual()
        
        logger.info("\n--- Verification of Writes ---")
        # Check what was written to InfluxDB
        calls = mock_client.write_points.call_args_list
        for call in calls:
            args, _ = call
            points = args[0]
            for p in points:
                logger.info(f"WRITE: Level={p['tags']['nivel']} | Code={p['tags']['codigo']} | Fields={p['fields']}")

if __name__ == "__main__":
    debug_aggregation()
