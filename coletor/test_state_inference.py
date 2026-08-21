import unittest

from coletor import inferir_estado_status_booleanos


class StateInferenceTests(unittest.TestCase):
    def test_requires_all_four_signals(self):
        self.assertIsNone(inferir_estado_status_booleanos({'StatusRunning': True}))

    def test_maps_mutually_exclusive_signals(self):
        base = {
            'StatusRunning': False,
            'StatusWaiting': False,
            'StatusBlocked': False,
            'StatusFault': False,
        }
        expected = {
            'StatusRunning': (1, 'RUN'),
            'StatusWaiting': (2, 'WAIT_PREV'),
            'StatusBlocked': (3, 'BLOCK_NEXT'),
            'StatusFault': (4, 'FAULT'),
        }
        for signal, state in expected.items():
            values = {**base, signal: True}
            with self.subTest(signal=signal):
                self.assertEqual(inferir_estado_status_booleanos(values), state)

    def test_fault_has_highest_precedence(self):
        self.assertEqual(
            inferir_estado_status_booleanos({
                'StatusRunning': True,
                'StatusWaiting': True,
                'StatusBlocked': True,
                'StatusFault': True,
            }),
            (4, 'FAULT'),
        )

    def test_all_false_is_other(self):
        self.assertEqual(
            inferir_estado_status_booleanos({
                'StatusRunning': False,
                'StatusWaiting': False,
                'StatusBlocked': False,
                'StatusFault': False,
            }),
            (0, 'OUTRO'),
        )


if __name__ == '__main__':
    unittest.main()
