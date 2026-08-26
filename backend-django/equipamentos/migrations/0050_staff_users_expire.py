from datetime import timedelta

from django.conf import settings
from django.db import migrations
from django.utils import timezone


def expire_staff_non_superusers(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    Policy = apps.get_model('equipamentos', 'UserAccessPolicy')
    expiry = timezone.now() + timedelta(days=120)
    staff_ids = User.objects.filter(is_staff=True, is_superuser=False).values_list('pk', flat=True)
    Policy.objects.filter(user_id__in=staff_ids, expires_at__isnull=True).update(expires_at=expiry)


class Migration(migrations.Migration):
    dependencies = [('equipamentos', '0049_user_access_policy')]

    operations = [migrations.RunPython(expire_staff_non_superusers, migrations.RunPython.noop)]
