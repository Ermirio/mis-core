"""
0041_slug_uuid_equipamento.py

Solução 2 da identidade global de equipamento (padrão ISA-95 / MES):
adiciona `slug` (legível, estável) e `uuid` (imutável, máquina) ao
Equipamento, popula dados existentes e garante unicidade.

Ordem das operações (importante para bases com dados):
  1. Cria colunas como NULL/blank.
  2. RunPython preenche cada equipamento existente.
  3. Adiciona constraint UNIQUE.
"""
import uuid

from django.db import migrations, models


def populate_slug_e_uuid(apps, schema_editor):
    Equipamento = apps.get_model('equipamentos', 'Equipamento')
    for eq in Equipamento.objects.select_related('linha').iterator():
        changed = False
        if not eq.uuid:
            eq.uuid = uuid.uuid4()
            changed = True
        if not eq.slug:
            linha_code = eq.linha.codigo if eq.linha else 'SEMLINHA'
            base = f'{linha_code}.{eq.codigo}' if eq.codigo else f'{linha_code}.eq-{eq.pk}'
            candidate = base
            n = 2
            while Equipamento.objects.exclude(pk=eq.pk).filter(slug=candidate).exists():
                candidate = f'{base}-{n}'
                n += 1
            eq.slug = candidate
            changed = True
        if changed:
            eq.save(update_fields=['slug', 'uuid'])


def reverter_slug_e_uuid(apps, schema_editor):
    Equipamento = apps.get_model('equipamentos', 'Equipamento')
    Equipamento.objects.update(slug='', uuid=None)


class Migration(migrations.Migration):

    dependencies = [
        ('equipamentos', '0040_nodered_snapshot'),
    ]

    operations = [
        # ===== 1. Adiciona campos como nullable (sem unique ainda) =====
        migrations.AddField(
            model_name='equipamento',
            name='slug',
            field=models.SlugField(
                max_length=80,
                blank=True,
                default='',
                db_index=True,
                verbose_name='Slug global (L01.E001)',
                help_text=(
                    'Identificador legível e estável usado em APIs, InfluxDB, '
                    'logs e URLs profundas. Gerado automaticamente no primeiro '
                    'save a partir de {linha}.{codigo} e congelado depois.'
                ),
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='equipamento',
            name='uuid',
            field=models.UUIDField(
                null=True,
                blank=True,
                editable=False,
                db_index=True,
                verbose_name='UUID',
                help_text=(
                    'Identificador único imutável (UUIDv4) — para integrações '
                    'externas (ERP, IIoT, MQTT). Sobrevive a renomeações.'
                ),
            ),
        ),
        # ===== 2. Popula dados existentes =====
        migrations.RunPython(populate_slug_e_uuid, reverter_slug_e_uuid),
        # ===== 3. Aplica UNIQUE depois dos dados estarem preenchidos =====
        migrations.AlterField(
            model_name='equipamento',
            name='slug',
            field=models.SlugField(
                max_length=80,
                blank=True,
                unique=True,
                db_index=True,
                verbose_name='Slug global (L01.E001)',
                help_text=(
                    'Identificador legível e estável usado em APIs, InfluxDB, '
                    'logs e URLs profundas. Gerado automaticamente no primeiro '
                    'save a partir de {linha}.{codigo} e congelado depois.'
                ),
            ),
        ),
        migrations.AlterField(
            model_name='equipamento',
            name='uuid',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
                db_index=True,
                verbose_name='UUID',
                help_text=(
                    'Identificador único imutável (UUIDv4) — para integrações '
                    'externas (ERP, IIoT, MQTT). Sobrevive a renomeações.'
                ),
            ),
        ),
    ]
