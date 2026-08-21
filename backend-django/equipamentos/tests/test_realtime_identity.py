from django.test import SimpleTestCase

from equipamentos.flask_replacement_views import _equipment_identity_where


class RealtimeIdentityWhereTests(SimpleTestCase):
    def test_realtime_uses_line_scoped_filter(self):
        where = _equipment_identity_where(
            "E001",
            slug="L02.E001",
            linha_codigo="L02",
        )

        self.assertEqual(where, '"equipment" = \'E001\' AND "line" = \'L02\'')
