from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("equipamentos", "0029_tagcoleta_defaults_and_blank_node"),
    ]

    operations = [
        migrations.AlterField(
            model_name="area",
            name="codigo",
            field=models.CharField(
                blank=True, max_length=20, unique=True, verbose_name="Código"
            ),
        ),
        migrations.AlterField(
            model_name="linhaproducao",
            name="codigo",
            field=models.CharField(
                blank=True, max_length=20, unique=True, verbose_name="Código da Linha"
            ),
        ),
    ]
