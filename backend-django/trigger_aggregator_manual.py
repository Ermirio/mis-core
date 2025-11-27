import os
import sys
import django
from django.utils import timezone
from datetime import timedelta

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from equipamentos.models import Equipamento, TagColeta, MetricaProducao
from equipamentos.agregador import AgregadorDados

def run_manual_aggregation():
    # Redirect stdout to file
    with open('debug_tonnage.txt', 'w', encoding='utf-8') as f:
        sys.stdout = f
        
        print("--- MANUAL AGGREGATION TRIGGER ---")
        
        # 1. Check Tags
        print("\n1. CHECKING TAGS CONFIGURATION")
        tags_with_format = TagColeta.objects.filter(formato__gt=0).count()
        print(f"Tags with format > 0: {tags_with_format}")
        
        if tags_with_format == 0:
            print("WARNING: No tags have format configured. Setting a default format for testing.")
            # Set default format for ONE tag per active equipment
            equips = Equipamento.objects.filter(status='ATIVO')
            for eq in equips:
                tag = eq.tags_coleta.filter(ativa=True).first()
                if tag:
                    tag.formato = 500  # 500 grams
                    tag.save()
                    print(f"Updated tag {tag.id} ({tag.nome_metrica}) for equipment {eq.nome} with format 500g")
                else:
                    print(f"Warning: Equipment {eq.nome} has no active tags.")
        
        # 2. Run Aggregation with Mock Data
        print("\n2. RUNNING AGGREGATION WITH MOCK DATA")
        
        # Monkeypatch buscar_dados_influx to return fake data
        original_buscar = AgregadorDados.buscar_dados_influx
        
        def mock_buscar_dados_influx(self, equipamento_codigo, inicio, fim):
            print(f"  [MOCK] Returning fake data for {equipamento_codigo}")
            return [
                {'time': inicio, 'contagem_entrada': 1000, 'contagem_saida': 5000},
                {'time': fim, 'contagem_entrada': 1200, 'contagem_saida': 5500} # Produced 500 units
            ]
        
        AgregadorDados.buscar_dados_influx = mock_buscar_dados_influx
        
        agregador = AgregadorDados()
        agora = timezone.now()
        
        equips = Equipamento.objects.filter(status='ATIVO')
        print(f"Processing {equips.count()} active equipment...")
        
        for eq in equips:
            print(f"Aggregating for {eq.nome}...")
            try:
                agregador.calcular_metricas_hora(eq, agora)
                print(f"  -> Done.")
            except Exception as e:
                print(f"  -> Error: {e}")
                import traceback
                traceback.print_exc(file=f)

        # Restore original method
        AgregadorDados.buscar_dados_influx = original_buscar

        # 3. Verify Results
        print("\n3. VERIFYING RESULTS")
        # Widen window because metric is saved with start of hour timestamp
        uma_hora_atras = agora - timedelta(hours=2)
        metricas = MetricaProducao.objects.filter(
            periodo='HORA',
            data_hora__gte=uma_hora_atras
        ).order_by('-data_hora')
        
        print(f"Metrics created in last 2 hours: {metricas.count()}")
        for m in metricas:
            try:
                if m.equipamento:
                    print(f"  - {m.equipamento.nome}: {m.toneladas_produzidas} ton, {m.vazao_real_ton_hora} ton/h (Format: {m.formato_gramas}g)")
                else:
                    print(f"  - Metric {m.id} has no equipment!")
            except Exception as e:
                print(f"  - Error displaying metric {m.id}: {e}")
            # Expected: 500 units * 500g = 250,000g = 0.25 tons

if __name__ == "__main__":
    run_manual_aggregation()
