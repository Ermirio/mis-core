"""
Testes unitários para o ProductionService.
"""
from django.test import TestCase
from equipamentos.services.production_service import ProductionService


class ProductionServiceTest(TestCase):
    """Testes para cálculos de produção"""
    
    def test_calculate_oee_perfect(self):
        """Testa cálculo de OEE com valores perfeitos"""
        oee = ProductionService.calculate_oee(100, 100, 100)
        self.assertEqual(oee, 100.0)
    
    def test_calculate_oee_typical(self):
        """Testa cálculo de OEE com valores típicos"""
        oee = ProductionService.calculate_oee(90, 95, 98)
        self.assertAlmostEqual(oee, 83.79, places=2)
    
    def test_calculate_oee_zero(self):
        """Testa cálculo de OEE com valores zerados"""
        oee = ProductionService.calculate_oee(0, 100, 100)
        self.assertEqual(oee, 0.0)
    
    def test_calculate_disponibilidade_full(self):
        """Testa disponibilidade com tempo total de produção"""
        disp = ProductionService.calculate_disponibilidade(480, 480)
        self.assertEqual(disp, 100.0)
    
    def test_calculate_disponibilidade_partial(self):
        """Testa disponibilidade com produção parcial"""
        disp = ProductionService.calculate_disponibilidade(400, 480)
        self.assertAlmostEqual(disp, 83.33, places=2)
    
    def test_calculate_disponibilidade_zero_time(self):
        """Testa disponibilidade com tempo disponível zero"""
        disp = ProductionService.calculate_disponibilidade(100, 0)
        self.assertEqual(disp, 0.0)
    
    def test_calculate_performance_perfect(self):
        """Testa performance perfeita"""
        perf = ProductionService.calculate_performance(1000, 1000)
        self.assertEqual(perf, 100.0)
    
    def test_calculate_performance_below_ideal(self):
        """Testa performance abaixo do ideal"""
        perf = ProductionService.calculate_performance(850, 1000)
        self.assertEqual(perf, 85.0)
    
    def test_calculate_performance_above_ideal(self):
        """Testa performance acima do ideal (limitado a 100%)"""
        perf = ProductionService.calculate_performance(1100, 1000)
        self.assertEqual(perf, 100.0)
    
    def test_calculate_qualidade_perfect(self):
        """Testa qualidade perfeita"""
        qual = ProductionService.calculate_qualidade(1000, 1000)
        self.assertEqual(qual, 100.0)
    
    def test_calculate_qualidade_with_defects(self):
        """Testa qualidade com defeitos"""
        qual = ProductionService.calculate_qualidade(950, 1000)
        self.assertEqual(qual, 95.0)
    
    def test_calculate_qualidade_no_production(self):
        """Testa qualidade sem produção"""
        qual = ProductionService.calculate_qualidade(0, 0)
        self.assertEqual(qual, 100.0)
    
    def test_calculate_descarte_no_waste(self):
        """Testa descarte sem perdas"""
        descarte = ProductionService.calculate_descarte(1000, 1000)
        self.assertEqual(descarte['total'], 0)
        self.assertEqual(descarte['percentual'], 0.0)
    
    def test_calculate_descarte_with_waste(self):
        """Testa descarte com perdas"""
        descarte = ProductionService.calculate_descarte(1000, 950)
        self.assertEqual(descarte['total'], 50)
        self.assertEqual(descarte['percentual'], 5.0)
    
    def test_calculate_descarte_negative_protection(self):
        """Testa proteção contra descarte negativo"""
        descarte = ProductionService.calculate_descarte(950, 1000)
        self.assertEqual(descarte['total'], 0)
    
    def test_calculate_projection_half_time(self):
        """Testa projeção na metade do tempo"""
        result = ProductionService.calculate_projection(500, 240, 480)
        self.assertEqual(result['projecao'], 1000.0)
        self.assertEqual(result['taxa_horaria'], 125.0)
    
    def test_calculate_projection_zero_time(self):
        """Testa projeção com tempo zero"""
        result = ProductionService.calculate_projection(500, 0, 480)
        self.assertEqual(result['projecao'], 0.0)
        self.assertEqual(result['taxa_horaria'], 0.0)
    
    def test_calculate_ritmo_necessario_normal(self):
        """Testa ritmo necessário em situação normal"""
        ritmo = ProductionService.calculate_ritmo_necessario(1000, 600, 240)
        self.assertEqual(ritmo, 100.0)  # 400 unidades em 4 horas = 100/hora
    
    def test_calculate_ritmo_necessario_meta_atingida(self):
        """Testa ritmo quando meta já foi atingida"""
        ritmo = ProductionService.calculate_ritmo_necessario(1000, 1000, 240)
        self.assertIsNone(ritmo)
    
    def test_calculate_ritmo_necessario_tempo_esgotado(self):
        """Testa ritmo quando tempo esgotou"""
        ritmo = ProductionService.calculate_ritmo_necessario(1000, 600, 0)
        self.assertIsNone(ritmo)
    
    def test_get_status_flag_superado(self):
        """Testa status quando meta foi superada"""
        status = ProductionService.get_status_flag(1100, 1000, 120)
        self.assertEqual(status, 'SUPERADO')
    
    def test_get_status_flag_atrasado(self):
        """Testa status quando tempo esgotou"""
        status = ProductionService.get_status_flag(800, 1000, 0)
        self.assertEqual(status, 'ATRASADO')
    
    def test_get_status_flag_normal(self):
        """Testa status normal"""
        status = ProductionService.get_status_flag(500, 1000, 240)
        self.assertEqual(status, 'NORMAL')
    
    def test_get_status_flag_atencao(self):
        """Testa status de atenção"""
        status = ProductionService.get_status_flag(300, 1000, 240)
        self.assertEqual(status, 'ATENCAO')
