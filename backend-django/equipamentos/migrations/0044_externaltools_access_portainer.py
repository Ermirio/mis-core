from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('equipamentos', '0043_nodered_snapshot_projeto'),
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
                    ('access_portainer', 'Pode acessar Portainer'),
                ],
                'verbose_name': 'Ferramenta externa (permissão)',
                'verbose_name_plural': 'Ferramentas externas (permissões)',
            },
        ),
    ]
