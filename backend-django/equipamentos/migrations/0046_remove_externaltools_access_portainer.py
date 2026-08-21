from django.db import migrations


def remove_stale_permission(apps, schema_editor):
    Permission = apps.get_model('auth', 'Permission')
    Permission.objects.filter(
        content_type__app_label='equipamentos',
        content_type__model='externaltools',
        codename='access_portainer',
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('equipamentos', '0045_alter_noderedsnapshot_parent_alter_nodereduser_id'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='externaltools',
            options={
                'default_permissions': (),
                'managed': False,
                'permissions': [
                    ('access_nodered', 'Pode acessar Node-RED'),
                    ('access_grafana', 'Pode acessar Grafana'),
                    ('access_chronograf', 'Pode acessar Chronograf'),
                    ('access_emqx', 'Pode acessar EMQX Dashboard'),
                ],
                'verbose_name': 'Ferramenta externa (permissão)',
                'verbose_name_plural': 'Ferramentas externas (permissões)',
            },
        ),
        migrations.RunPython(remove_stale_permission, migrations.RunPython.noop),
    ]
