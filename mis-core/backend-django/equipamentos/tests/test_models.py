"""
Testes unitários para os modelos do Django.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import time
from equipamentos.models import (
    Fabrica, Area, Produto, LinhaProducao, Equipamento,
    TurnoProducao, OrdemProducao, CalendarioProducao
)


class FabricaModelTest(TestCase):
    """Testes para o modelo Fabrica"""
    
    def test_create_fabrica(self):
        """Testa criação de fábrica"""
        fabrica = Fabrica.objects.create(
            nome="Fábrica Teste",
            localizacao="São Paulo"
        )
        self.assertIsNotNone(fabrica.codigo)
        self.assertTrue(fabrica.codigo.startswith('F'))
        self.assertEqual(str(fabrica), f"{fabrica.nome} ({fabrica.codigo})")
    
    def test_fabrica_auto_codigo(self):
        """Testa geração automática de código"""
        f1 = Fabrica.objects.create(nome="Fábrica 1")
        f2 = Fabrica.objects.create(nome="Fábrica 2")
        
        self.assertNotEqual(f1.codigo, f2.codigo)
        self.assertTrue(f1.codigo < f2.codigo)


class AreaModelTest(TestCase):
    """Testes para o modelo Area"""
    
    def setUp(self):
        self.fabrica = Fabrica.objects.create(nome="Fábrica Teste")
    
    def test_create_area(self):
        """Testa criação de área"""
        area = Area.objects.create(
            fabrica=self.fabrica,
            nome="Envase",
            codigo="ENV-01"
        )
        self.assertEqual(area.fabrica, self.fabrica)
        self.assertIn(area, self.fabrica.areas.all())


class ProdutoModelTest(TestCase):
    """Testes para o modelo Produto"""
    
    def test_create_produto(self):
        """Testa criação de produto"""
        produto = Produto.objects.create(
            codigo="SKU-001",
            descricao="Produto Teste",
            peso_unitario=250.5
        )
        self.assertEqual(produto.codigo, "SKU-001")
        self.assertTrue(produto.ativo)
        self.assertEqual(str(produto), "SKU-001 - Produto Teste")
    
    def test_produto_peso_validation(self):
        """Testa validação de peso unitário"""
        produto = Produto(
            codigo="SKU-002",
            descricao="Produto Teste",
            peso_unitario=-10  # Peso negativo deve falhar
        )
        with self.assertRaises(ValidationError):
            produto.full_clean()


class LinhaProducaoModelTest(TestCase):
    """Testes para o modelo LinhaProducao"""
    
    def setUp(self):
        self.fabrica = Fabrica.objects.create(nome="Fábrica Teste")
        self.area = Area.objects.create(
            fabrica=self.fabrica,
            nome="Envase",
            codigo="ENV-01"
        )
    
    def test_create_linha(self):
        """Testa criação de linha de produção"""
        linha = LinhaProducao.objects.create(
            codigo="L01",
            nome="Linha 01",
            area=self.area,
            localizacao="Galpão A",
            velocidade_planejada=100.0,
            meta_producao_hora=6000,
            meta_producao_turno=48000,
            ativa=True
        )
        self.assertEqual(linha.codigo, "L01")
        self.assertTrue(linha.ativa)
        self.assertEqual(linha.site, self.fabrica)
        self.assertEqual(linha.tecnologia, self.area)
    
    def test_linha_velocidade_validation(self):
        """Testa validação de velocidade planejada"""
        linha = LinhaProducao(
            codigo="L02",
            nome="Linha 02",
            localizacao="Galpão B",
            velocidade_planejada=-10,  # Velocidade negativa
            meta_producao_hora=6000,
            meta_producao_turno=48000
        )
        with self.assertRaises(ValidationError):
            linha.full_clean()


class EquipamentoModelTest(TestCase):
    """Testes para o modelo Equipamento"""
    
    def setUp(self):
        self.linha = LinhaProducao.objects.create(
            codigo="L01",
            nome="Linha 01",
            localizacao="Galpão A",
            velocidade_planejada=100.0,
            meta_producao_hora=6000,
            meta_producao_turno=48000
        )
    
    def test_create_equipamento(self):
        """Testa criação de equipamento"""
        equipamento = Equipamento.objects.create(
            linha=self.linha,
            nome="Enchedora 01",
            codigo="ENC-01",
            tipo="ENCHEDORA",
            localizacao="Início da linha",
            velocidade_nominal=100.0,
            velocidade_maxima=120.0,
            ordem_na_linha=1
        )
        self.assertEqual(equipamento.linha, self.linha)
        self.assertEqual(equipamento.tipo, "ENCHEDORA")
        self.assertIn(equipamento, self.linha.equipamentos.all())


class TurnoProducaoModelTest(TestCase):
    """Testes para o modelo TurnoProducao"""
    
    def test_create_turno(self):
        """Testa criação de turno"""
        turno = TurnoProducao.objects.create(
            nome="Turno 1",
            codigo="T1",
            hora_inicio=time(6, 0),
            hora_fim=time(14, 0),
            duracao_horas=8
        )
        self.assertEqual(turno.codigo, "T1")
        self.assertEqual(turno.duracao_horas, 8)
    
    def test_turno_overnight(self):
        """Testa turno que cruza meia-noite"""
        turno = TurnoProducao.objects.create(
            nome="Turno 3",
            codigo="T3",
            hora_inicio=time(22, 0),
            hora_fim=time(6, 0),
            duracao_horas=8
        )
        self.assertTrue(turno.hora_inicio > turno.hora_fim)


class OrdemProducaoModelTest(TestCase):
    """Testes para o modelo OrdemProducao"""
    
    def setUp(self):
        self.linha = LinhaProducao.objects.create(
            codigo="L01",
            nome="Linha 01",
            localizacao="Galpão A",
            velocidade_planejada=100.0,
            meta_producao_hora=6000,
            meta_producao_turno=48000
        )
        self.produto = Produto.objects.create(
            codigo="SKU-001",
            descricao="Produto Teste",
            peso_unitario=250.0
        )
    
    def test_create_ordem_producao(self):
        """Testa criação de ordem de produção"""
        op = OrdemProducao.objects.create(
            codigo="OP-001",
            linha=self.linha,
            produto=self.produto,
            meta_total=10000,
            formato_gramas=250.0,
            data_planejada_inicio=timezone.now()
        )
        self.assertEqual(op.codigo, "OP-001")
        self.assertEqual(op.status, "PLANEJADA")
        self.assertEqual(op.producao_realizada, 0.0)
    
    def test_ordem_producao_status_choices(self):
        """Testa choices de status"""
        op = OrdemProducao.objects.create(
            codigo="OP-002",
            linha=self.linha,
            produto=self.produto,
            meta_total=10000,
            formato_gramas=250.0,
            data_planejada_inicio=timezone.now(),
            status="PRODUZINDO"
        )
        self.assertEqual(op.status, "PRODUZINDO")


class CalendarioProducaoModelTest(TestCase):
    """Testes para o modelo CalendarioProducao"""
    
    def setUp(self):
        self.linha = LinhaProducao.objects.create(
            codigo="L01",
            nome="Linha 01",
            localizacao="Galpão A",
            velocidade_planejada=100.0,
            meta_producao_hora=6000,
            meta_producao_turno=48000
        )
        self.turno = TurnoProducao.objects.create(
            nome="Turno 1",
            codigo="T1",
            hora_inicio=time(6, 0),
            hora_fim=time(14, 0),
            duracao_horas=8
        )
    
    def test_create_calendario(self):
        """Testa criação de calendário de produção"""
        hoje = timezone.now().date()
        calendario = CalendarioProducao.objects.create(
            data=hoje,
            linha=self.linha,
            turno=self.turno,
            programado=True,
            meta_producao_turno=48000
        )
        self.assertTrue(calendario.programado)
        self.assertEqual(calendario.meta_producao_turno, 48000)
    
    def test_calendario_unique_constraint(self):
        """Testa constraint de unicidade (data, linha, turno)"""
        hoje = timezone.now().date()
        CalendarioProducao.objects.create(
            data=hoje,
            linha=self.linha,
            turno=self.turno,
            programado=True,
            meta_producao_turno=48000
        )
        
        # Tentar criar duplicado deve falhar
        with self.assertRaises(Exception):
            CalendarioProducao.objects.create(
                data=hoje,
                linha=self.linha,
                turno=self.turno,
                programado=True,
                meta_producao_turno=50000
            )
