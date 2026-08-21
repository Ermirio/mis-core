from django.test import TestCase

from equipamentos.flask_replacement_views import _processar_item_ingestao
from equipamentos.models import Area, Equipamento, Fabrica, LinhaProducao


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
    def test_influx_point_carries_equipment_hierarchy(self):
        fabrica = Fabrica.objects.create(nome='Fabrica Teste', codigo='F001')
        area = Area.objects.create(fabrica=fabrica, nome='Envase', codigo='A001')
        linha = LinhaProducao.objects.create(
            area=area,
            codigo='L02',
            nome='Linha 02',
            localizacao='Galpao',
            velocidade_planejada=100,
            meta_producao_hora=6000,
            meta_producao_turno=48000,
        )
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
