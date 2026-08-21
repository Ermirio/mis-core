"""
Service para lógica de negócios relacionada à produção.
Extrai a lógica complexa das views para facilitar testes e manutenção.
"""
from django.db.models import Sum, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ProductionService:
    """Serviço para cálculos e operações de produção"""
    
    @staticmethod
    def calculate_oee(disponibilidade: float, performance: float, qualidade: float) -> float:
        """
        Calcula o OEE (Overall Equipment Effectiveness).
        
        Args:
            disponibilidade: Percentual de disponibilidade (0-100)
            performance: Percentual de performance (0-100)
            qualidade: Percentual de qualidade (0-100)
            
        Returns:
            OEE calculado (0-100)
        """
        if not all([disponibilidade, performance, qualidade]):
            return 0.0
        
        return (disponibilidade * performance * qualidade) / 10000
    
    @staticmethod
    def calculate_disponibilidade(tempo_producao: float, tempo_disponivel: float) -> float:
        """
        Calcula a disponibilidade do equipamento.
        
        Args:
            tempo_producao: Tempo em que o equipamento produziu (minutos)
            tempo_disponivel: Tempo disponível para produção (minutos)
            
        Returns:
            Disponibilidade em percentual (0-100)
        """
        if tempo_disponivel <= 0:
            return 0.0
        
        return min((tempo_producao / tempo_disponivel) * 100, 100.0)
    
    @staticmethod
    def calculate_performance(producao_real: float, producao_ideal: float) -> float:
        """
        Calcula a performance do equipamento.
        
        Args:
            producao_real: Quantidade produzida
            producao_ideal: Quantidade ideal baseada na velocidade planejada
            
        Returns:
            Performance em percentual (0-100)
        """
        if producao_ideal <= 0:
            return 0.0
        
        return min((producao_real / producao_ideal) * 100, 100.0)
    
    @staticmethod
    def calculate_qualidade(pecas_boas: int, pecas_totais: int) -> float:
        """
        Calcula a qualidade da produção.
        
        Args:
            pecas_boas: Número de peças boas produzidas
            pecas_totais: Número total de peças produzidas
            
        Returns:
            Qualidade em percentual (0-100)
        """
        if pecas_totais <= 0:
            return 100.0  # Sem produção = sem defeitos
        
        return (pecas_boas / pecas_totais) * 100
    
    @staticmethod
    def calculate_descarte(entrada: int, saida: int) -> Dict[str, float]:
        """
        Calcula o descarte de produção.
        
        Args:
            entrada: Contagem de entrada
            saida: Contagem de saída
            
        Returns:
            Dict com 'total' e 'percentual' de descarte
        """
        descarte_total = max(entrada - saida, 0)
        descarte_percentual = (descarte_total / entrada * 100) if entrada > 0 else 0.0
        
        return {
            'total': descarte_total,
            'percentual': round(descarte_percentual, 2)
        }
    
    @staticmethod
    def calculate_projection(
        producao_atual: float,
        tempo_decorrido: float,
        tempo_total: float
    ) -> Dict[str, float]:
        """
        Calcula a projeção de produção para o final do período.
        
        Args:
            producao_atual: Produção acumulada até o momento
            tempo_decorrido: Tempo decorrido em minutos
            tempo_total: Tempo total do período em minutos
            
        Returns:
            Dict com 'projecao' e 'taxa_horaria'
        """
        if tempo_decorrido <= 0:
            return {'projecao': 0.0, 'taxa_horaria': 0.0}
        
        taxa_horaria = (producao_atual / tempo_decorrido) * 60  # Produção por hora
        projecao = (producao_atual / tempo_decorrido) * tempo_total
        
        return {
            'projecao': round(projecao, 2),
            'taxa_horaria': round(taxa_horaria, 2)
        }
    
    @staticmethod
    def calculate_ritmo_necessario(
        meta: float,
        producao_atual: float,
        tempo_restante: float
    ) -> Optional[float]:
        """
        Calcula o ritmo necessário para atingir a meta.
        
        Args:
            meta: Meta de produção
            producao_atual: Produção acumulada
            tempo_restante: Tempo restante em minutos
            
        Returns:
            Ritmo necessário em unidades/hora ou None se meta já atingida
        """
        if producao_atual >= meta:
            return None  # Meta já atingida
        
        if tempo_restante <= 0:
            return None  # Tempo esgotado
        
        falta_produzir = meta - producao_atual
        ritmo_necessario = (falta_produzir / tempo_restante) * 60  # Unidades por hora
        
        return round(ritmo_necessario, 2)
    
    @staticmethod
    def get_status_flag(
        producao_atual: float,
        meta: float,
        tempo_restante: float
    ) -> str:
        """
        Determina o status da produção.
        
        Args:
            producao_atual: Produção acumulada
            meta: Meta de produção
            tempo_restante: Tempo restante em minutos
            
        Returns:
            Status: 'SUPERADO', 'NORMAL', 'ATENCAO', 'ATRASADO'
        """
        if producao_atual >= meta:
            return 'SUPERADO'
        
        if tempo_restante <= 0:
            return 'ATRASADO'
        
        percentual_atingido = (producao_atual / meta) * 100 if meta > 0 else 0
        percentual_tempo = ((tempo_restante / 480) * 100) if tempo_restante > 0 else 0  # Assumindo turno de 8h
        
        # Se a produção está abaixo do esperado para o tempo decorrido
        if percentual_atingido < (100 - percentual_tempo):
            return 'ATENCAO'
        
        return 'NORMAL'
