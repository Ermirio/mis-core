import os
import django
import logging
import sys
from datetime import datetime
from django.utils import timezone

# Configurar logging para stdout
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from equipamentos.agregador_service import agregar_metricas_turno
from equipamentos.models import MetricaProducao

def run_shift_aggregation():
    print("--- Rodando Agregação de Turno ---")
    
    # 1. Limpar métricas de turno de hoje para garantir regeneração
    hoje = timezone.now().date()
    deleted, _ = MetricaProducao.objects.filter(
        periodo='TURNO',
        data_hora__date=hoje
    ).delete()
    print(f"Métricas de turno deletadas: {deleted}")
    
    # 2. Rodar agregação
    total = agregar_metricas_turno()
    print(f"Total agregado: {total}")
    
    # 3. Verificar resultados
    metricas = MetricaProducao.objects.filter(
        periodo='TURNO',
        data_hora__date=hoje
    ).order_by('-data_hora')
    
    print(f"\nMétricas de Turno Geradas ({metricas.count()}):")
    for m in metricas:
        eq_nome = m.equipamento.nome if m.equipamento else "LINHA"
        print(f"  [{m.data_hora}] Eq: {eq_nome} | Turno: {m.turno} | OEE: {m.oee:.2f}% | Prod: {m.contagem_saida}")

if __name__ == '__main__':
    run_shift_aggregation()
