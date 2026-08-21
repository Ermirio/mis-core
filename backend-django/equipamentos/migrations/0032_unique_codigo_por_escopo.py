from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("equipamentos", "0031_equipamento_localizacao_opcional"),
    ]

    operations = [
        # Equipamento: remove unique global de codigo/nome
        migrations.AlterField(
            model_name="equipamento",
            name="codigo",
            field=models.CharField(blank=True, max_length=50, verbose_name="Código"),
        ),
        migrations.AlterField(
            model_name="equipamento",
            name="nome",
            field=models.CharField(max_length=100, verbose_name="Nome do Equipamento"),
        ),
        # Sensor: codigo passa a permitir blank e remove unique global
        migrations.AlterField(
            model_name="sensor",
            name="codigo",
            field=models.CharField(blank=True, max_length=50, verbose_name="Código do Sensor"),
        ),
        # Constraints escopadas
        migrations.AddConstraint(
            model_name="equipamento",
            constraint=models.UniqueConstraint(
                fields=("linha", "codigo"),
                name="uniq_equipamento_linha_codigo",
            ),
        ),
        migrations.AddConstraint(
            model_name="equipamento",
            constraint=models.UniqueConstraint(
                fields=("linha", "nome"),
                name="uniq_equipamento_linha_nome",
            ),
        ),
        migrations.AddConstraint(
            model_name="sensor",
            constraint=models.UniqueConstraint(
                fields=("equipamento", "codigo"),
                condition=models.Q(equipamento__isnull=False),
                name="uniq_sensor_equipamento_codigo",
            ),
        ),
        migrations.AddConstraint(
            model_name="sensor",
            constraint=models.UniqueConstraint(
                fields=("linha", "codigo"),
                condition=models.Q(equipamento__isnull=True, linha__isnull=False),
                name="uniq_sensor_linha_codigo",
            ),
        ),
    ]
