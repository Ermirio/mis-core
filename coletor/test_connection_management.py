import unittest
from copy import deepcopy
from unittest.mock import AsyncMock, patch

from asyncua.ua.uaerrors import BadNodeIdUnknown

from coletor import ColetorOPC


class DummyWatchdog:
    def __init__(self):
        self.registered = []
        self.unregistered = []

    def register(self, url):
        self.registered.append(url)

    def unregister(self, url):
        self.unregistered.append(url)


class MissingNode:
    async def read_value(self):
        raise BadNodeIdUnknown()


class ValueNode:
    def __init__(self, value=0):
        self.value = value

    async def read_value(self):
        return self.value


class DisconnectedNode:
    async def read_value(self):
        raise ConnectionError('client is disconnected')


class FakeClient:
    def get_node(self, _node_id):
        return MissingNode()


class ServerStateClient:
    def __init__(self, node):
        self.node = node
        self.requested_node_ids = []

    def get_node(self, node_id):
        self.requested_node_ids.append(node_id)
        return self.node


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        return None

    def json(self):
        return deepcopy(self.data)


class ConnectionManagementTest(unittest.IsolatedAsyncioTestCase):
    def new_collector(self):
        with patch('coletor.RESILIENCE_AVAILABLE', False):
            return ColetorOPC()

    async def test_normalizes_url_and_unregisters_stale_watchdog_key(self):
        collector = self.new_collector()
        old_url = 'opc.tcp//192.168.70.156:49320'
        new_url = 'opc.tcp://192.168.70.156:49320'
        connection = {
            'url': old_url,
            'tag_monitoramento': '',
            'tipo_monitoramento': 'HEARTBEAT',
            'nome': 'OPC linha',
        }
        collector.configuracao = {
            'equipamentos': [{'conexao_detalhes': connection}],
        }
        collector.watchdog = DummyWatchdog()
        collector.urls_watchdog_registradas = {old_url}
        collector.conexoes_info = {old_url: {}}
        collector._conectar_url = AsyncMock(return_value=True)

        await collector.gerenciar_conexoes()

        self.assertEqual(connection['url'], new_url)
        self.assertIn(old_url, collector.watchdog.unregistered)
        self.assertIn(new_url, collector.watchdog.registered)
        self.assertNotIn(old_url, collector.conexoes_info)

    async def test_missing_monitoring_node_does_not_mark_connection_offline(self):
        collector = self.new_collector()
        url = 'opc.tcp://192.168.70.156:49320'
        info = {
            'tag_monitoramento': 'ns=2;s=Health.Missing',
            'tipo_monitoramento': 'HEARTBEAT',
        }
        collector.clientes_opc[url] = FakeClient()
        collector.conexoes_info[url] = info

        healthy = await collector.verificar_saude_conexao(url)

        self.assertTrue(healthy)
        self.assertTrue(info['_tag_mon_disabled'])

    async def test_without_monitoring_tag_reads_server_state(self):
        collector = self.new_collector()
        url = 'opc.tcp://192.168.70.156:49320'
        client = ServerStateClient(ValueNode())
        collector.clientes_opc[url] = client
        collector.conexoes_info[url] = {'tag_monitoramento': None}

        healthy = await collector.verificar_saude_conexao(url)

        self.assertTrue(healthy)
        self.assertEqual(client.requested_node_ids, ['i=2259'])

    async def test_without_monitoring_tag_detects_disconnected_client(self):
        collector = self.new_collector()
        url = 'opc.tcp://192.168.70.156:49320'
        collector.clientes_opc[url] = ServerStateClient(DisconnectedNode())
        collector.conexoes_info[url] = {'tag_monitoramento': None}

        healthy = await collector.verificar_saude_conexao(url)

        self.assertFalse(healthy)

    async def test_timestamp_change_does_not_reload_configuration(self):
        collector = self.new_collector()
        collector.gerenciar_conexoes = AsyncMock()
        base = {
            'status': 'success',
            'timestamp': '2026-08-04T18:00:00Z',
            'equipamentos': [],
        }
        changed_timestamp = {**base, 'timestamp': '2026-08-04T18:00:02Z'}

        with patch(
            'coletor.requests.get',
            side_effect=[FakeResponse(base), FakeResponse(changed_timestamp)],
        ):
            self.assertTrue(await collector.atualizar_configuracao())
            self.assertTrue(await collector.atualizar_configuracao())

        collector.gerenciar_conexoes.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
