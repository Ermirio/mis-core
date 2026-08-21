import asyncio
import unittest
from unittest.mock import patch

from asyncua.ua.uaerrors import BadNodeIdUnknown

from coletor import ColetorOPC, TagReadResult, _convert_opc_value


class FakeStatus:
    def __init__(self, good=True, label='Good'):
        self.good = good
        self.label = label

    def is_good(self):
        return self.good

    def __str__(self):
        return self.label


class FakeVariantType:
    def __init__(self, name):
        self.name = name


class FakeVariant:
    def __init__(self, value, variant_type):
        self.Value = value
        self.VariantType = FakeVariantType(variant_type)


class FakeDataValue:
    def __init__(self, value, variant_type='Float', good=True):
        self.Value = FakeVariant(value, variant_type)
        self.StatusCode = FakeStatus(good, 'Good' if good else 'BadOutOfService')


class FakeNode:
    def __init__(self, value=None, variant_type='Float', good=True, error=None, delay=0):
        self.value = value
        self.variant_type = variant_type
        self.good = good
        self.error = error
        self.delay = delay

    async def read_data_value(self):
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return FakeDataValue(self.value, self.variant_type, self.good)

    async def read_data_type(self):
        return f"ns=0;i={self.variant_type}"

    async def read_value_rank(self):
        return 1 if isinstance(self.value, list) else -1


class FakeClient:
    def __init__(self, nodes):
        self.nodes = nodes

    def get_node(self, node_id):
        return self.nodes[node_id]


class TagIsolationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        with patch('coletor.RESILIENCE_AVAILABLE', False):
            self.collector = ColetorOPC()

    async def test_bad_node_does_not_cancel_other_tag(self):
        client = FakeClient({
            'bad': FakeNode(error=BadNodeIdUnknown()),
            'good': FakeNode(value=12.5, variant_type='Float'),
        })
        equipment = {
            'codigo': 'E001',
            'slug': 'L01.E001',
            'linha_codigo': 'L01',
            'tags_coleta': [
                {'nome_metrica': 'tag_ruim', 'node_id': 'bad', 'tipo_dado': 'FLOAT'},
                {'nome_metrica': 'tag_boa', 'node_id': 'good', 'tipo_dado': 'FLOAT'},
            ],
        }

        result = await self.collector.coletar_dados_equipamento(equipment, client, True)

        self.assertEqual(result['medicoes']['tag_boa'], 12.5)
        self.assertNotIn('tag_ruim', result['medicoes'])
        self.assertEqual(result['_collector_stats'], {'valid': 1, 'rejected': 1, 'no_read': 0})

    async def test_text_as_number_is_configuration_error(self):
        result = await self.collector.ler_tag_opc(
            FakeClient({'tag': FakeNode(value='12.5', variant_type='String')}),
            'tag', 'FLOAT', 1,
        )

        self.assertEqual(result.status, 'CONFIG_ERROR')
        self.assertEqual(result.observed_type, 'String')

    async def test_null_array_and_bad_status_are_isolated(self):
        cases = [
            (FakeNode(value=None, variant_type='Null'), 'CONFIG_ERROR'),
            (FakeNode(value=[1.0], variant_type='Float'), 'CONFIG_ERROR'),
            (FakeNode(value=1.0, variant_type='Float', good=False), 'NO_READ'),
        ]
        for node, expected in cases:
            with self.subTest(expected=expected, value=node.value):
                result = await self.collector.ler_tag_opc(
                    FakeClient({'tag': node}), 'tag', 'FLOAT', 1
                )
                self.assertEqual(result.status, expected)

    async def test_timeout_is_no_read(self):
        with patch('coletor.TAG_READ_TIMEOUT', 0.01):
            result = await self.collector.ler_tag_opc(
                FakeClient({'tag': FakeNode(value=1.0, delay=0.1)}),
                'tag', 'FLOAT', 1,
            )
        self.assertEqual(result.status, 'NO_READ')

    def test_repeated_issue_is_rate_limited_and_change_is_logged(self):
        issue = TagReadResult(status='NO_READ', error='offline')
        changed = TagReadResult(status='CONFIG_ERROR', error='tipo incorreto')

        self.assertTrue(self.collector._should_log_tag_issue('L01|tag', issue))
        self.assertFalse(self.collector._should_log_tag_issue('L01|tag', issue))
        self.assertTrue(self.collector._should_log_tag_issue('L01|tag', changed))


class SafeConversionTest(unittest.TestCase):
    def test_integer_conversion_rejects_fractional_loss(self):
        self.assertEqual(_convert_opc_value(2.0, 'INT'), 2)
        with self.assertRaises(ValueError):
            _convert_opc_value(2.5, 'INT')

    def test_float_rejects_text(self):
        with self.assertRaises(ValueError):
            _convert_opc_value('2.5', 'FLOAT')


if __name__ == '__main__':
    unittest.main()
