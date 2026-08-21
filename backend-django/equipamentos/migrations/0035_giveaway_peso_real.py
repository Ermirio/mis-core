from django.db import migrations, models


def adiciona_tag_peso_real(apps, schema_editor):
    """Garante que cada equipamento existente tenha a tag padrao 'peso_real' inativa."""
    Equipamento = apps.get_model('equipamentos', 'Equipamento')
    TagColeta = apps.get_model('equipamentos', 'TagColeta')
    for eq in Equipamento.objects.all():
        TagColeta.objects.get_or_create(
            equipamento=eq,
            nome_metrica='peso_real',
            defaults={
                'node_id': '',
                'tipo_dado': 'FLOAT',
                'unidade': 'g',
                'fator_conversao': 1.0,
                'ativa': False,
            },
        )


def remove_tag_peso_real(apps, schema_editor):
    TagColeta = apps.get_model('equipamentos', 'TagColeta')
    TagColeta.objects.filter(nome_metrica='peso_real').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('equipamentos', '0034_rename_tag_estado_para_estado_maquina'),
    ]

    operations = [
        migrations.AddField(
            model_name='linhaproducao',
            name='formato_alvo_padrao',
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                help_text='Usado como referência de peso nominal quando ausente do Influx/SKU.',
                max_digits=10,
                null=True,
                verbose_name='Formato alvo padrão (g)',
            ),
        ),
        migrations.RunPython(adiciona_tag_peso_real, remove_tag_peso_real),
    ]
