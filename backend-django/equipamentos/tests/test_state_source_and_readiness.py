from unittest.mock import Mock, patch

from django.test import TestCase
from rest_framework.test import APIClient

from equipamentos.models import Equipamento, LinhaProducao, TagColeta


class EquipmentStateSourceTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.linha = LinhaProducao.objects.create(
            codigo='L01', nome='Linha 01', localizacao='A',
            velocidade_planejada=100.0,
            meta_producao_hora=6000,
            meta_producao_turno=48000,
        )
        self.equipamento = Equipamento.objects.create(
            linha=self.linha,
            nome='Enchedora',
            codigo='E001',
            tipo='ENCHEDORA',
            velocidade_nominal=100.0,
            velocidade_maxima=120.0,
        )

    def _payload(self):
        response = self.client.get(f'/api/equipamentos/{self.equipamento.id}/')
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_reports_missing_state_source(self):
        payload = self._payload()
        self.assertFalse(payload['estado_configurado'])
        self.assertEqual(payload['fonte_estado'], 'NAO_CONFIGURADA')
        self.assertEqual(payload['tags_estado'], [])

    def test_reports_dedicated_state_tag(self):
        TagColeta.objects.filter(
            equipamento=self.equipamento,
            nome_metrica='estado_maquina',
        ).update(ativa=True, node_id='ns=2;s=Line.State')
        payload = self._payload()
        self.assertTrue(payload['estado_configurado'])
        self.assertEqual(payload['fonte_estado'], 'TAG_DEDICADA')
        self.assertEqual(payload['tags_estado'], ['estado_maquina'])

    def test_requires_complete_boolean_state_set(self):
        names = ('StatusRunning', 'StatusWaiting', 'StatusBlocked', 'StatusFault')
        for name in names:
            TagColeta.objects.create(
                equipamento=self.equipamento,
                nome_metrica=name,
                node_id=f'ns=2;s=Line.{name}',
                tipo_dado='BOOL',
                ativa=True,
            )
        payload = self._payload()
        self.assertTrue(payload['estado_configurado'])
        self.assertEqual(payload['fonte_estado'], 'SINAIS_BOOLEANOS')
        self.assertEqual(payload['tags_estado'], list(names))


class SystemReadinessTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('equipamentos.flask_replacement_views._influx_client')
    def test_ready_returns_200_when_dependencies_are_healthy(self, influx_factory):
        client = Mock()
        client.ping.return_value = 'pong'
        client.query.return_value.get_points.return_value = iter([{
            'time': '2026-08-19T16:00:00Z',
            'alive': 1,
            'cycle_seconds': 166.2,
            'equipment_count': 126,
            'measurement_count': 31,
        }])
        influx_factory.return_value = client

        response = self.client.get('/api/health/ready')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ready'])
        self.assertEqual(
            response.json()['details']['coletor']['equipment_count'], 126
        )

    @patch('equipamentos.flask_replacement_views._influx_client')
    def test_ready_returns_503_when_collector_is_stale(self, influx_factory):
        client = Mock()
        client.ping.return_value = 'pong'
        client.query.return_value.get_points.return_value = iter([{'n': 0}])
        influx_factory.return_value = client

        response = self.client.get('/api/health/ready')
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()['ready'])
        self.assertIn('10 minutos', response.json()['details']['coletor_error'])
