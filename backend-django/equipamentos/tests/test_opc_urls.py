from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import TestCase

from equipamentos.models import ConexaoOPC
from equipamentos.serializers import EquipamentoColetorSerializer


class ConexaoOPCUrlTest(TestCase):
    def test_save_normalizes_missing_scheme_colon(self):
        conexao = ConexaoOPC.objects.create(
            nome='OPC linha 01',
            url_servidor='opc.tcp//192.168.70.156:49320',
        )

        self.assertEqual(
            conexao.url_servidor,
            'opc.tcp://192.168.70.156:49320',
        )

    def test_rejects_url_without_port(self):
        conexao = ConexaoOPC(
            nome='OPC sem porta',
            url_servidor='opc.tcp://192.168.70.156',
        )

        with self.assertRaises(ValidationError):
            conexao.full_clean()

    def test_rejects_non_opc_scheme(self):
        conexao = ConexaoOPC(
            nome='HTTP invalido',
            url_servidor='http://192.168.70.156:49320',
        )

        with self.assertRaises(ValidationError):
            conexao.full_clean()

    def test_collector_serializer_repairs_legacy_typo(self):
        conexao = SimpleNamespace(
            url_servidor='opc.tcp//192.168.70.156:49320',
            tag_monitoramento='',
            tipo_monitoramento='HEARTBEAT',
            nome='OPC legado',
        )
        equipamento = SimpleNamespace(
            linha=SimpleNamespace(conexao_padrao=conexao),
        )

        data = EquipamentoColetorSerializer().get_conexao_detalhes(equipamento)

        self.assertEqual(data['url'], 'opc.tcp://192.168.70.156:49320')
