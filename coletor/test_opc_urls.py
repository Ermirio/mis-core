import unittest

from opc_urls import normalize_opc_tcp_url


class NormalizeOpcTcpUrlTest(unittest.TestCase):
    def test_preserves_valid_url(self):
        self.assertEqual(
            normalize_opc_tcp_url('opc.tcp://192.168.70.156:49320'),
            'opc.tcp://192.168.70.156:49320',
        )

    def test_repairs_missing_colon(self):
        self.assertEqual(
            normalize_opc_tcp_url('opc.tcp//192.168.70.156:49320'),
            'opc.tcp://192.168.70.156:49320',
        )

    def test_strips_outer_whitespace(self):
        self.assertEqual(
            normalize_opc_tcp_url('  opc.tcp://opc-server:4840  '),
            'opc.tcp://opc-server:4840',
        )

    def test_rejects_missing_port(self):
        with self.assertRaisesRegex(ValueError, 'porta ausente'):
            normalize_opc_tcp_url('opc.tcp://192.168.70.156')

    def test_rejects_non_opc_scheme(self):
        with self.assertRaisesRegex(ValueError, 'opc.tcp'):
            normalize_opc_tcp_url('http://192.168.70.156:49320')


if __name__ == '__main__':
    unittest.main()
