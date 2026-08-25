from datetime import timedelta

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone
import equipamentos.models


def create_existing_policies(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Policy = apps.get_model('equipamentos', 'UserAccessPolicy')
    expiry = timezone.now() + timedelta(days=120)
    rows = []
    for user in User.objects.all().iterator():
        rows.append(Policy(user_id=user.pk, expires_at=None if (user.is_staff or user.is_superuser) else expiry))
    Policy.objects.bulk_create(rows, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('equipamentos', '0048_repair_legacy_equipment_slugs'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserAccessPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('expires_at', models.DateTimeField(blank=True, default=equipamentos.models.default_user_access_expiry, null=True, verbose_name='Acesso válido até')),
                ('revalidated_at', models.DateTimeField(blank=True, null=True, verbose_name='Revalidado em')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('revalidated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mis_access_revalidations', to=settings.AUTH_USER_MODEL, verbose_name='Revalidado por')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='mis_access_policy', to=settings.AUTH_USER_MODEL, verbose_name='Usuário')),
            ],
            options={
                'verbose_name': 'Validade de usuário',
                'verbose_name_plural': 'Validades de usuários',
                'ordering': ['expires_at', 'user__username'],
            },
        ),
        migrations.RunPython(create_existing_policies, migrations.RunPython.noop),
    ]
