from django.test import SimpleTestCase

from equipamentos.analytics_views import _equipment_identity_where


class AnalyticsEquipmentIdentityTests(SimpleTestCase):
    def test_line_code_scopes_legacy_equipment_points(self):
        where_clause = _equipment_identity_where('E001', 'L02')

        self.assertEqual(
            where_clause,
            '"equipment" = \'E001\' AND "line" = \'L02\'',
        )

    def test_slug_does_not_replace_line_scope(self):
        where_clause = _equipment_identity_where('E001', 'L02', 'L02.E001')

        self.assertEqual(
            where_clause,
            '"equipment" = \'E001\' AND "line" = \'L02\'',
        )
