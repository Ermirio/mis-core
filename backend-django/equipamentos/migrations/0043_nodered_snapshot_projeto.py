"""
Adiciona o campo `projeto` a NodeRedSnapshot para acompanhar a feature
Projects do Node-RED. Snapshots existentes ficam com projeto='' (string
vazia = "global" / Projects desligado), o que preserva a timeline atual.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('equipamentos', '0042_nodered_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='noderedsnapshot',
            name='projeto',
            field=models.CharField(
                blank=True, db_index=True, default='', max_length=128,
                help_text=(
                    'Nome do projeto Node-RED (quando a feature Projects está '
                    'habilitada). Em branco = snapshot global / Projects desligado.'
                ),
                verbose_name='Projeto',
            ),
        ),
        migrations.AlterModelOptions(
            name='noderedsnapshot',
            options={
                'ordering': ['-criado_em'],
                'verbose_name': 'Snapshot Node-RED',
                'verbose_name_plural': 'Histórico Node-RED',
            },
        ),
        migrations.AddIndex(
            model_name='noderedsnapshot',
            index=models.Index(
                fields=['projeto', '-criado_em'],
                name='nrs_proj_ts_idx',
            ),
        ),
    ]
