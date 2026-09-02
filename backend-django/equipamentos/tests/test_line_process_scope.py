from types import SimpleNamespace

from django.test import SimpleTestCase

from equipamentos.flask_replacement_views import (
    _select_line_process_stage,
    _select_line_product_context,
)
from equipamentos.production_plan_client import _format_grams_from_description


class LineProcessStageTests(SimpleTestCase):
    def test_serial_stages_are_not_double_counted(self):
        equipments = [
            SimpleNamespace(codigo='E001', ordem_na_linha=1),
            SimpleNamespace(codigo='E002', ordem_na_linha=2),
        ]
        snapshot = _select_line_process_stage(equipments, {
            'E001': {'ton': 12.0, 'vel': 100, 'fmt': 1000},
            'E002': {'ton': 11.5, 'vel': 95, 'fmt': 1000},
        })

        self.assertEqual(snapshot['production_tons'], 11.5)
        self.assertEqual(snapshot['production_stage'], 2)
        self.assertEqual(snapshot['production_equipments'], ['E002'])

    def test_parallel_equipments_in_same_stage_are_summed(self):
        equipments = [
            SimpleNamespace(codigo='E004', ordem_na_linha=2),
            SimpleNamespace(codigo='E005', ordem_na_linha=2),
            SimpleNamespace(codigo='E010', ordem_na_linha=4),
        ]
        snapshot = _select_line_process_stage(equipments, {
            'E004': {'ton': 4.25, 'vel': 70, 'fmt': 800},
            'E005': {'ton': 5.75, 'vel': 70, 'fmt': 800},
            'E010': {'ton': 0, 'vel': 0, 'fmt': 0},
        })

        self.assertEqual(snapshot['production_tons'], 10.0)
        self.assertEqual(snapshot['production_equipments'], ['E004', 'E005'])
        self.assertAlmostEqual(snapshot['rate_tons_hour'], 6.72)

    def test_missing_process_data_returns_zero_without_cross_line_fallback(self):
        equipments = [SimpleNamespace(codigo='E001', ordem_na_linha=1)]

        snapshot = _select_line_process_stage(equipments, {})

        self.assertEqual(snapshot['production_tons'], 0.0)
        self.assertIsNone(snapshot['production_stage'])
        self.assertEqual(snapshot['production_equipments'], [])

    def test_product_master_format_is_parsed_from_pack_description(self):
        self.assertEqual(
            _format_grams_from_description('BRILHANTE CT 9X2.2KG'),
            2200.0,
        )
        self.assertEqual(
            _format_grams_from_description('OMO CART 24X400G'),
            400.0,
        )

    def test_product_context_comes_from_one_equipment(self):
        equipments = [
            SimpleNamespace(codigo='E001', ordem_na_linha=1),
            SimpleNamespace(codigo='E002', ordem_na_linha=2),
        ]
        context = _select_line_product_context(equipments, {
            'E001': {
                'sku': 'SKU-1', 'descricao': 'Produto 2,2 kg',
                'formato': 2200, 'op': None, 'cuc': None,
            },
            'E002': {
                'sku': None, 'descricao': None,
                'formato': 400, 'op': None, 'cuc': None,
            },
        })

        self.assertEqual(context['sku'], 'SKU-1')
        self.assertEqual(context['formato'], 2200.0)
        self.assertEqual(context['equipment'], 'E001')

    def test_product_context_prefers_upstream_on_equal_quality(self):
        equipments = [
            SimpleNamespace(codigo='E001', ordem_na_linha=1),
            SimpleNamespace(codigo='E002', ordem_na_linha=2),
        ]
        context = _select_line_product_context(equipments, {
            'E001': {'sku': 'A', 'descricao': 'A', 'formato': 1600},
            'E002': {'sku': 'B', 'descricao': 'B', 'formato': 800},
        })

        self.assertEqual(context['sku'], 'A')
        self.assertEqual(context['equipment'], 'E001')
