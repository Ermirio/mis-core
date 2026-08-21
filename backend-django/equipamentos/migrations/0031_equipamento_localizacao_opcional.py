from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("equipamentos", "0030_auto_codigos_area_linha"),
    ]

    operations = [
        migrations.AlterField(
            model_name="equipamento",
            name="localizacao",
            field=models.CharField(
                blank=True,
                help_text="Deixe em branco para herdar a localização da linha.",
                max_length=200,
                verbose_name="Localização",
            ),
        ),
    ]
