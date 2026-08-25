from django.test import TestCase

from equipamentos.flask_replacement_views import _processar_item_ingestao
from equipamentos.models import Area, Equipamento, Fabrica, LinhaProducao
from equipamentos.resolvers import EquipamentoIdentityConflict, resolver_de_payload


class _FakeInflux:
    def __init__(self):
        self.points = []

    def write_points(self, points):
        self.points.extend(points)


class _FakeEngine:
    def __init__(self):
        self.calls = []

    def processar_dados(self, **kwargs):
        self.calls.append(kwargs)
        return {'turno_atual_nome': 'T1'}


class IngestIdentityTests(TestCase):
    def setUp(self):
        self.fabrica = Fabrica.objects.create(nome='Fabrica Base', codigo='F001')
        self.area = Area.objects.create(fabrica=self.fabrica, nome='Envase', codigo='A001')

    def _linha(self, codigo):
        return LinhaProducao.objects.create(
            area=self.area,
            codigo=codigo,
            nome=f'Linha {codigo}',
            localizacao='Galpao',
            velocidade_planejada=100,
            meta_producao_hora=6000,
            meta_producao_turno=48000,
        )

    def test_influx_point_carries_equipment_hierarchy(self):
        linha = self._linha('L02')
        equipamento = Equipamento.objects.create(
            linha=linha,
            nome='Enchedora',
            codigo='E001',
            tipo='ENCHEDORA',
            velocidade_nominal=100,
            velocidade_maxima=120,
        )
        influx = _FakeInflux()
        engine = _FakeEngine()

        ok = _processar_item_ingestao(
            {
                'equipamento_slug': equipamento.slug,
                'equipamento_codigo': equipamento.codigo,
                'linha_codigo': linha.codigo,
                'medicoes': {
                    'estado_maquina': 1,
                    'contagem_saida': 10,
                    'contagem_entrada': 10,
                    'velocidade_atual': 20,
                },
            },
            influx,
            engine,
        )

        self.assertTrue(ok)
        self.assertEqual(len(influx.points), 1)
        self.assertEqual(
            influx.points[0]['tags'],
            {
                'factory': 'F001',
                'area': 'A001',
                'line': 'L02',
                'equipment': 'E001',
                'shift': 'T1',
                'order_id': 'N/A',
                'sku': 'N/A',
            },
        )
        self.assertEqual(engine.calls[0]['equipamento_slug'], 'L02.E001')
        self.assertEqual(engine.calls[0]['linha_codigo'], 'L02')

    def test_zero_speed_is_preserved_instead_of_recalculated(self):
        linha = self._linha('L06')
        equipamento = Equipamento.objects.create(
            linha=linha,
            nome='Senzani',
            codigo='E001',
            tipo='ENCHEDORA',
            velocidade_nominal=300,
            velocidade_maxima=350,
        )
        influx = _FakeInflux()
        engine = _FakeEngine()

        ok = _processar_item_ingestao(
            {
                'equipamento_slug': equipamento.slug,
                'equipamento_codigo': equipamento.codigo,
                'linha_codigo': linha.codigo,
                'medicoes': {
                    'estado_maquina': 4,
                    'contagem_saida': 12345,
                    'velocidade_atual': 0.0,
                },
            },
            influx,
            engine,
        )

        self.assertTrue(ok)
        self.assertEqual(engine.calls[0]['velocidade_atual'], 0)
        self.assertEqual(influx.points[0]['fields']['velocidade_atual'], 0)

    def test_conflicting_slug_code_and_line_are_rejected(self):
        linha = self._linha('L10')
        e1 = Equipamento.objects.create(
            linha=linha, nome='ACMA', codigo='E001', tipo='ENCHEDORA',
            velocidade_nominal=100, velocidade_maxima=120,
        )
        e2 = Equipamento.objects.create(
            linha=linha, nome='Vincadora', codigo='E0025', tipo='OUTRO',
            velocidade_nominal=100, velocidade_maxima=120,
        )

        with self.assertRaises(EquipamentoIdentityConflict):
            resolver_de_payload({
                'equipamento_slug': e2.slug,
                'equipamento_codigo': e1.codigo,
                'linha_codigo': linha.codigo,
            })
