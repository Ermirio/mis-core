import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('equipamentos', '0044_externaltools_access_portainer'),
    ]

    operations = [
        migrations.AlterField(
            model_name='noderedsnapshot',
            name='parent',
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    'Cadeia linear por projeto: snapshot anterior do MESMO projeto.'
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='filhos',
                to='equipamentos.noderedsnapshot',
                verbose_name='Versão anterior',
            ),
        ),
        migrations.AlterField(
            model_name='nodereduser',
            name='id',
            field=models.BigAutoField(
                auto_created=True,
                primary_key=True,
                serialize=False,
                verbose_name='ID',
            ),
        ),
    ]
