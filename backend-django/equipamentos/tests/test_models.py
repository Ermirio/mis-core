"""
Testes unitários para os modelos do Django.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import time
from django.db.utils import IntegrityError
from equipamentos.models import (
    Fabrica, Area, Produto, LinhaProducao, Equipamento, Sensor, TagColeta,
    DEFAULT_TAGS_COLETA, DEFAULT_TAGS_BY_NAME,
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

    def test_area_auto_codigo_sequencial(self):
        """Sem código informado, deve gerar A001, A002, ..."""
        a1 = Area.objects.create(fabrica=self.fabrica, nome="Envase")
        a2 = Area.objects.create(fabrica=self.fabrica, nome="Empacotamento")
        self.assertEqual(a1.codigo, "A001")
        self.assertEqual(a2.codigo, "A002")

    def test_area_codigo_manual_preservado(self):
        """Código informado pelo usuário não é sobrescrito"""
        a = Area.objects.create(fabrica=self.fabrica, nome="Utilidades", codigo="UTL")
        self.assertEqual(a.codigo, "UTL")

    def test_area_auto_codigo_tolera_codigos_manuais(self):
        """Após código manual, sequência continua a partir do maior 'A###'"""
        Area.objects.create(fabrica=self.fabrica, nome="X", codigo="CUSTOM")
        Area.objects.create(fabrica=self.fabrica, nome="Y", codigo="A007")
        a = Area.objects.create(fabrica=self.fabrica, nome="Z")
        self.assertEqual(a.codigo, "A008")


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

    def _criar_linha(self, **overrides):
        defaults = dict(
            nome=overrides.pop("nome", "Linha auto"),
            area=self.area,
            localizacao="Galpão A",
            velocidade_planejada=100.0,
            meta_producao_hora=6000,
            meta_producao_turno=48000,
        )
        defaults.update(overrides)
        return LinhaProducao.objects.create(**defaults)

    def test_linha_auto_codigo_sequencial(self):
        """Sem código informado, deve gerar L01, L02, ..."""
        l1 = self._criar_linha(nome="Linha A")
        l2 = self._criar_linha(nome="Linha B")
        self.assertEqual(l1.codigo, "L01")
        self.assertEqual(l2.codigo, "L02")

    def test_linha_auto_codigo_escala_alem_de_99(self):
        """Após L99, próximo é L100 (max int, não lex)"""
        self._criar_linha(nome="Linha gigante", codigo="L99")
        nova = self._criar_linha(nome="Linha 100")
        self.assertEqual(nova.codigo, "L100")

    def test_linha_codigo_manual_preservado(self):
        """Código informado pelo usuário não é sobrescrito"""
        l = self._criar_linha(nome="Linha legacy", codigo="LEGADO")
        self.assertEqual(l.codigo, "LEGADO")


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

    def test_equipamento_herda_localizacao_da_linha(self):
        """Sem localização informada, herda da linha"""
        equipamento = Equipamento.objects.create(
            linha=self.linha,
            nome="Enchedora sem loc",
            tipo="ENCHEDORA",
            velocidade_nominal=100.0,
            velocidade_maxima=120.0,
        )
        self.assertEqual(equipamento.localizacao, self.linha.localizacao)

    def test_equipamento_localizacao_explicita_preservada(self):
        """Localização informada não é sobrescrita pela linha"""
        equipamento = Equipamento.objects.create(
            linha=self.linha,
            nome="Enchedora com loc",
            tipo="ENCHEDORA",
            localizacao="Sala isolada",
            velocidade_nominal=100.0,
            velocidade_maxima=120.0,
        )
        self.assertEqual(equipamento.localizacao, "Sala isolada")

    def _criar_equipamento(self, linha=None, **overrides):
        defaults = dict(
            linha=linha or self.linha,
            nome=overrides.pop("nome", "Eq auto"),
            tipo="ENCHEDORA",
            velocidade_nominal=100.0,
            velocidade_maxima=120.0,
        )
        defaults.update(overrides)
        return Equipamento.objects.create(**defaults)

    def test_equipamento_codigo_auto_por_linha(self):
        """Auto-geração de E### é independente por linha"""
        linha2 = LinhaProducao.objects.create(
            codigo="L02", nome="Linha 02", localizacao="Galpão B",
            velocidade_planejada=100.0, meta_producao_hora=6000, meta_producao_turno=48000,
        )
        e1_l1 = self._criar_equipamento(linha=self.linha, nome="A1")
        e2_l1 = self._criar_equipamento(linha=self.linha, nome="A2")
        e1_l2 = self._criar_equipamento(linha=linha2, nome="B1")
        self.assertEqual(e1_l1.codigo, "E001")
        self.assertEqual(e2_l1.codigo, "E002")
        # Linha 2 começa do zero
        self.assertEqual(e1_l2.codigo, "E001")

    def test_equipamento_mesmo_codigo_linhas_diferentes_permitido(self):
        """E001 pode existir em L01 e em L02 simultaneamente"""
        linha2 = LinhaProducao.objects.create(
            codigo="L02", nome="Linha 02", localizacao="Galpão B",
            velocidade_planejada=100.0, meta_producao_hora=6000, meta_producao_turno=48000,
        )
        self._criar_equipamento(linha=self.linha, nome="A", codigo="E001")
        self._criar_equipamento(linha=linha2, nome="B", codigo="E001")
        # Não deve levantar — só ler dos dois deve funcionar
        self.assertEqual(self.linha.equipamentos.count(), 1)
        self.assertEqual(linha2.equipamentos.count(), 1)

    def test_equipamento_mesmo_codigo_mesma_linha_proibido(self):
        """E001 não pode repetir dentro da mesma linha"""
        self._criar_equipamento(linha=self.linha, nome="A", codigo="E001")
        with self.assertRaises(IntegrityError):
            self._criar_equipamento(linha=self.linha, nome="B", codigo="E001")

    def test_equipamento_mesmo_nome_mesma_linha_proibido(self):
        """Nome duplicado é proibido dentro da mesma linha"""
        self._criar_equipamento(linha=self.linha, nome="Enchedora", codigo="X1")
        with self.assertRaises(IntegrityError):
            self._criar_equipamento(linha=self.linha, nome="Enchedora", codigo="X2")

    def test_default_tags_nao_inclui_descarte(self):
        """A tag 'descarte' nao deve mais estar nos defaults nem nas
        TagColeta criadas automaticamente para um novo equipamento."""
        nomes_default = {t['nome'] for t in DEFAULT_TAGS_COLETA}
        self.assertNotIn('descarte', nomes_default)
        equipamento = Equipamento.objects.create(
            linha=self.linha,
            nome="Enchedora sem descarte",
            codigo="ENC-02",
            tipo="ENCHEDORA",
            localizacao="X",
            velocidade_nominal=100.0,
            velocidade_maxima=120.0,
        )
        criadas = set(equipamento.tags_coleta.values_list('nome_metrica', flat=True))
        self.assertNotIn('descarte', criadas)
        # Algumas tags ainda existem (e.g. contagem_entrada/saida)
        self.assertIn('contagem_entrada', criadas)
        self.assertIn('contagem_saida', criadas)

    def test_tag_padrao_usa_estado_maquina(self):
        """A tag padrão de estado se chama 'estado_maquina' (não 'estado')."""
        self.assertIn('estado_maquina', DEFAULT_TAGS_BY_NAME)
        self.assertNotIn('estado', DEFAULT_TAGS_BY_NAME)
        equipamento = Equipamento.objects.create(
            linha=self.linha,
            nome="Eq estado",
            codigo="X-01",
            tipo="ENCHEDORA",
            localizacao="A",
            velocidade_nominal=100.0,
            velocidade_maxima=120.0,
        )
        nomes = set(equipamento.tags_coleta.values_list('nome_metrica', flat=True))
        self.assertIn('estado_maquina', nomes)
        self.assertNotIn('estado', nomes)

    def test_default_tags_inclui_peso_real(self):
        """A tag 'peso_real' deve estar nos defaults para Give Away."""
        self.assertIn('peso_real', DEFAULT_TAGS_BY_NAME)
        equipamento = Equipamento.objects.create(
            linha=self.linha,
            nome="Enchedora peso",
            codigo="PR-01",
            tipo="ENCHEDORA",
            velocidade_nominal=100.0,
            velocidade_maxima=120.0,
        )
        nomes = set(equipamento.tags_coleta.values_list('nome_metrica', flat=True))
        self.assertIn('peso_real', nomes)


class SensorModelTest(TestCase):
    """Testes para o modelo Sensor"""

    def setUp(self):
        self.linha = LinhaProducao.objects.create(
            codigo="L01", nome="Linha 01", localizacao="Galpão A",
            velocidade_planejada=100.0, meta_producao_hora=6000, meta_producao_turno=48000,
        )
        self.eq1 = Equipamento.objects.create(
            linha=self.linha, nome="Enchedora", codigo="E001", tipo="ENCHEDORA",
            velocidade_nominal=100.0, velocidade_maxima=120.0,
        )
        self.eq2 = Equipamento.objects.create(
            linha=self.linha, nome="Paletizador", codigo="E002", tipo="PALETIZADOR",
            velocidade_nominal=100.0, velocidade_maxima=120.0,
        )

    def _criar_sensor(self, **kw):
        defaults = dict(
            nome="Sensor X",
            tipo="INPUT_FLOAT",
            tag_influxdb="x",
        )
        defaults.update(kw)
        return Sensor.objects.create(**defaults)

    def test_sensor_codigo_auto_por_equipamento(self):
        """Auto-gera S### independente por equipamento"""
        s1_a = self._criar_sensor(equipamento=self.eq1, nome="A")
        s2_a = self._criar_sensor(equipamento=self.eq1, nome="B")
        s1_b = self._criar_sensor(equipamento=self.eq2, nome="C")
        self.assertEqual(s1_a.codigo, "S001")
        self.assertEqual(s2_a.codigo, "S002")
        self.assertEqual(s1_b.codigo, "S001")

    def test_sensor_mesmo_codigo_equipamentos_diferentes_permitido(self):
        self._criar_sensor(equipamento=self.eq1, nome="A", codigo="S001")
        self._criar_sensor(equipamento=self.eq2, nome="B", codigo="S001")
        self.assertEqual(self.eq1.sensores.count(), 1)
        self.assertEqual(self.eq2.sensores.count(), 1)

    def test_sensor_mesmo_codigo_mesmo_equipamento_proibido(self):
        self._criar_sensor(equipamento=self.eq1, nome="A", codigo="S001")
        with self.assertRaises(IntegrityError):
            self._criar_sensor(equipamento=self.eq1, nome="B", codigo="S001")


class LinhaProducaoFormatoAlvoTest(TestCase):
    def test_formato_alvo_padrao_e_opcional(self):
        linha = LinhaProducao.objects.create(
            codigo="LX", nome="LX", localizacao="A",
            velocidade_planejada=100.0, meta_producao_hora=6000, meta_producao_turno=48000,
        )
        # default null
        self.assertIsNone(linha.formato_alvo_padrao)
        # aceita valor
        linha.formato_alvo_padrao = 500.000
        linha.save()
        linha.refresh_from_db()
        self.assertEqual(float(linha.formato_alvo_padrao), 500.0)


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


class GetMetaTurnoTest(TestCase):
    """Testes do helper utils.get_meta_turno"""

    def setUp(self):
        self.linha = LinhaProducao.objects.create(
            codigo="L01", nome="Linha 01", localizacao="A",
            velocidade_planejada=100.0, meta_producao_hora=6000, meta_producao_turno=48000,
        )
        self.turno = TurnoProducao.objects.create(
            nome="Turno 1", codigo="T1",
            hora_inicio=time(6, 0), hora_fim=time(14, 0), duracao_horas=8,
        )

    def test_usa_meta_do_calendario_quando_existe(self):
        from equipamentos.utils import get_meta_turno
        hoje = timezone.now().date()
        CalendarioProducao.objects.create(
            data=hoje, linha=self.linha, turno=self.turno,
            programado=True, meta_producao_turno=20000,
        )
        self.assertEqual(get_meta_turno(self.linha, hoje, self.turno), 20000)

    def test_fallback_para_meta_padrao_da_linha(self):
        from equipamentos.utils import get_meta_turno
        # Sem calendário: deve usar meta_producao_turno da linha (48000)
        hoje = timezone.now().date()
        self.assertEqual(get_meta_turno(self.linha, hoje, self.turno), 48000)

    def test_fallback_quando_calendario_meta_zero(self):
        from equipamentos.utils import get_meta_turno
        hoje = timezone.now().date()
        CalendarioProducao.objects.create(
            data=hoje, linha=self.linha, turno=self.turno,
            programado=False, meta_producao_turno=0,
        )
        # Calendário existe mas meta=0 → usa fallback da linha
        self.assertEqual(get_meta_turno(self.linha, hoje, self.turno), 48000)
