from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('equipamentos', '0046_remove_externaltools_access_portainer'),
    ]

    operations = [
        migrations.AlterField(
            model_name='produto',
            name='peso_unitario',
            field=models.DecimalField(
                decimal_places=3,
                help_text='Peso do produto em gramas',
                max_digits=10,
                validators=[MinValueValidator(0)],
                verbose_name='Peso Unitário (g)',
            ),
        ),
    ]
