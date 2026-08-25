from django.db import migrations, transaction


# Correções estritamente limitadas aos slugs legados comprovadamente trocados
# no baseline da VM 160. O slug continua congelado para renomes legítimos.
SLUG_REPAIRS = (
    ('L01', 'E001', 'L01.E002', 'L01.E001'),
    ('L01', 'E0025', 'L01.E001', 'L01.E0025'),
    ('L01', 'E006', 'L02.E006', 'L01.E006'),
    ('L02', 'E001', 'L02.E002', 'L02.E001'),
    ('L02', 'E0025', 'L02.E001', 'L02.E0025'),
    ('L02', 'E006', 'L02.E006-2', 'L02.E006'),
    ('L06', 'E001', 'L06.E002', 'L06.E001'),
    ('L06', 'E0025', 'L06.E001', 'L06.E0025'),
    ('L09', 'E001', 'L09.E002', 'L09.E001'),
    ('L09', 'E0025', 'L09.E001', 'L09.E0025'),
    ('L10', 'E001', 'L10.E002', 'L10.E001'),
    ('L10', 'E0025', 'L10.E001', 'L10.E0025'),
    ('L16', 'E001', 'L16.E002', 'L16.E001'),
    ('L16', 'E0025', 'L16.E001', 'L16.E0025'),
)


def repair_legacy_slugs(apps, schema_editor):
    Equipamento = apps.get_model('equipamentos', 'Equipamento')
    rows = []
    for line_code, equipment_code, wrong_slug, expected_slug in SLUG_REPAIRS:
        row = Equipamento.objects.filter(
            linha__codigo=line_code,
            codigo=equipment_code,
            slug=wrong_slug,
        ).first()
        if row:
            rows.append((row, expected_slug))

    with transaction.atomic():
        # Libera primeiro todas as constraints únicas envolvidas nas trocas.
        for row, _ in rows:
            Equipamento.objects.filter(pk=row.pk).update(
                slug=f'repair-{row.pk}-{row.uuid.hex}'
            )
        for row, expected_slug in rows:
            Equipamento.objects.filter(pk=row.pk).update(slug=expected_slug)


class Migration(migrations.Migration):
    dependencies = [
        ('equipamentos', '0047_produto_peso_unitario_nonnegative'),
    ]

    operations = [
        migrations.RunPython(repair_legacy_slugs, migrations.RunPython.noop),
    ]
