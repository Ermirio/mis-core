"""
Patch para adicionar cálculo de OEE ao agregador
=================================================

Este script adiciona cálculo de OEE (Disponibilidade, Performance, Qualidade)
às métricas do agregador via monkey-patching, sem modificar o arquivo original.

Uso:
    python patch_oee_agregador.py
"""

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from equipamentos.agregador import AgregadorDados
from equipamentos.models import MetricaProducao
import logging

logger = logging.getLogger('PatchOEE')

# Salva métodos originais
_original_calcular_metricas_hora = AgregadorDados.calcular_metricas_hora
_original_calcular_metricas_turno = AgregadorDados.calcular_metricas_turno
_original_calcular_metricas_dia = AgregadorDados.calcular_metricas_dia


def calcular_oee_components(contagem_entrada, contagem_saida, tempo_producao, tempo_disponivel, velocidade_real, velocidade_planejada):
    """
    Calcula componentes do OEE
    
    Returns:
        dict com disponibilidade, performance, qualidade, oee, descarte
    """
    # 1. Disponibilidade = (Tempo Produção / Tempo Disponível) * 100
    disponibilidade = (tempo_producao / tempo_disponivel * 100) if tempo_disponivel > 0 else 0
    
    # 2. Performance = (Velocidade Real / Velocidade Planejada) * 100
    performance = (velocidade_real / velocidade_planejada * 100) if velocidade_planejada > 0 else 0
    
    # 3. Descarte e Qualidade
    descarte = max(0, contagem_entrada - contagem_saida)
    qualidade = ((contagem_saida - descarte) / contagem_saida * 100) if contagem_saida > 0 else 100
    
    # 4. OEE = (Disponibilidade * Performance * Qualidade) / 10000
    oee = (disponibilidade * performance * qualidade) / 10000
    
    return {
        'disponibilidade': disponibilidade,
        'performance': performance,
        'qualidade': qualidade,
        'oee': oee,
        'descarte': descarte,
        'percentual_descarte': (descarte / contagem_entrada * 100) if contagem_entrada > 0 else 0
    }


def patched_calcular_metricas_hora(self, equipamento, data_hora):
    """Versão patcheada que adiciona OEE"""
    from datetime import timedelta
    
    # Chama método original
    _original_calcular_metricas_hora(self, equipamento, data_hora)
    
    # Busca a métrica recém-criada
    hora_inicio = data_hora.replace(minute=0, second=0, microsecond=0)
    
    try:
        metrica = MetricaProducao.objects.get(
            linha=equipamento.linha,
            equipamento=equipamento,
            data_hora=hora_inicio,
            periodo='HORA'
        )
        
        # Calcula OEE
        oee_data = calcular_oee_components(
            contagem_entrada=metrica.contagem_entrada,
            contagem_saida=metrica.contagem_saida,
            tempo_producao=metrica.tempo_producao,
            tempo_disponivel=60.0,  # 1 hora em minutos
            velocidade_real=metrica.velocidade_real,
            velocidade_planejada=metrica.velocidade_planejada
        )
        
        # Atualiza métrica com OEE
        metrica.disponibilidade = oee_data['disponibilidade']
        metrica.performance = oee_data['performance']
        metrica.qualidade = oee_data['qualidade']
        metrica.oee = oee_data['oee']
        metrica.descarte = oee_data['descarte']
        metrica.percentual_descarte = oee_data['percentual_descarte']
        metrica.tempo_disponivel = 60.0
        metrica.save()
        
        logger.info(f"✓ OEE adicionado à métrica HORA: {equipamento.nome} - OEE={oee_data['oee']:.2f}%")
        
    except MetricaProducao.DoesNotExist:
        logger.warning(f"Métrica HORA não encontrada para {equipamento.nome}")


def patched_calcular_metricas_turno(self, equipamento, turno, data):
    """Versão patcheada que adiciona OEE"""
    # Chama método original
    _original_calcular_metricas_turno(self, equipamento, turno, data)
    
    # Busca a métrica recém-criada
    turno_inicio, _ = self.obter_intervalo_turno(turno, data)
    
    try:
        metrica = MetricaProducao.objects.get(
            linha=equipamento.linha,
            equipamento=equipamento,
            data_hora=turno_inicio,
            periodo='TURNO',
            turno=turno.nome
        )
        
        # Calcula OEE
        tempo_disponivel = turno.duracao_horas * 60.0
        oee_data = calcular_oee_components(
            contagem_entrada=metrica.contagem_entrada,
            contagem_saida=metrica.contagem_saida,
            tempo_producao=metrica.tempo_producao,
            tempo_disponivel=tempo_disponivel,
            velocidade_real=metrica.velocidade_real,
            velocidade_planejada=metrica.velocidade_planejada
        )
        
        # Atualiza métrica com OEE
        metrica.disponibilidade = oee_data['disponibilidade']
        metrica.performance = oee_data['performance']
        metrica.qualidade = oee_data['qualidade']
        metrica.oee = oee_data['oee']
        metrica.descarte = oee_data['descarte']
        metrica.percentual_descarte = oee_data['percentual_descarte']
        metrica.tempo_disponivel = tempo_disponivel
        metrica.save()
        
        logger.info(f"✓ OEE adicionado à métrica TURNO: {equipamento.nome} - {turno.nome} - OEE={oee_data['oee']:.2f}%")
        
    except MetricaProducao.DoesNotExist:
        logger.warning(f"Métrica TURNO não encontrada para {equipamento.nome}")


def patched_calcular_metricas_dia(self, equipamento, data):
    """Versão patcheada que adiciona OEE"""
    from datetime import time
    from django.utils import timezone
    from datetime import datetime
    
    # Chama método original
    _original_calcular_metricas_dia(self, equipamento, data)
    
    # Busca a métrica recém-criada
    dia_inicio = timezone.make_aware(datetime.combine(data.date(), time.min))
    
    try:
        metrica = MetricaProducao.objects.get(
            linha=equipamento.linha,
            equipamento=equipamento,
            data_hora=dia_inicio,
            periodo='DIA'
        )
        
        # Calcula OEE
        tempo_disponivel = 24 * 60.0  # 24 horas em minutos
        oee_data = calcular_oee_components(
            contagem_entrada=metrica.contagem_entrada,
            contagem_saida=metrica.contagem_saida,
            tempo_producao=metrica.tempo_producao,
            tempo_disponivel=tempo_disponivel,
            velocidade_real=metrica.velocidade_real,
            velocidade_planejada=metrica.velocidade_planejada
        )
        
        # Atualiza métrica com OEE
        metrica.disponibilidade = oee_data['disponibilidade']
        metrica.performance = oee_data['performance']
        metrica.qualidade = oee_data['qualidade']
        metrica.oee = oee_data['oee']
        metrica.descarte = oee_data['descarte']
        metrica.percentual_descarte = oee_data['percentual_descarte']
        metrica.tempo_disponivel = tempo_disponivel
        metrica.save()
        
        logger.info(f"✓ OEE adicionado à métrica DIA: {equipamento.nome} - OEE={oee_data['oee']:.2f}%")
        
    except MetricaProducao.DoesNotExist:
        logger.warning(f"Métrica DIA não encontrada para {equipamento.nome}")


def aplicar_patch():
    """Aplica o patch ao AgregadorDados"""
    logger.info("=" * 60)
    logger.info("APLICANDO PATCH DE OEE AO AGREGADOR")
    logger.info("=" * 60)
    
    # Aplica monkey-patch
    AgregadorDados.calcular_metricas_hora = patched_calcular_metricas_hora
    AgregadorDados.calcular_metricas_turno = patched_calcular_metricas_turno
    AgregadorDados.calcular_metricas_dia = patched_calcular_metricas_dia
    
    logger.info("✓ Patch aplicado com sucesso!")
    logger.info("✓ Métodos patcheados:")
    logger.info("  - calcular_metricas_hora")
    logger.info("  - calcular_metricas_turno")
    logger.info("  - calcular_metricas_dia")
    logger.info("=" * 60)
    
    return AgregadorDados()


if __name__ == '__main__':
    # Aplica patch e executa agregador
    agregador = aplicar_patch()
    
    logger.info("Executando agregação com OEE...")
    
    try:
        agregador.agregar_ultima_hora()
        logger.info("✓ Agregação de HORA concluída com OEE")
    except Exception as e:
        logger.error(f"✗ Erro na agregação de HORA: {e}")
    
    try:
        agregador.agregar_ultimo_turno()
        logger.info("✓ Agregação de TURNO concluída com OEE")
    except Exception as e:
        logger.error(f"✗ Erro na agregação de TURNO: {e}")
    
    logger.info("=" * 60)
    logger.info("PATCH CONCLUÍDO")
    logger.info("=" * 60)
