"""
Migration: cria tabela NodeRedUser para gerenciar usuários do editor
Node-RED a partir do admin Django, eliminando a necessidade de editar
settings.js + node-red-admin hash-pw a cada novo usuário.

Ver: equipamentos.models.NodeRedUser e node-red/settings.js (adminAuth).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('equipamentos', '0041_slug_uuid_equipamento'),
    ]

    operations = [
        migrations.CreateModel(
            name='NodeRedUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(
                    help_text='Login que o operador digita na tela do Node-RED.',
                    max_length=150, unique=True, verbose_name='Usuário')),
                ('password_hash', models.CharField(
                    help_text='Hash gerado automaticamente quando você grava uma nova senha.',
                    max_length=256, verbose_name='Senha (hash)')),
                ('nivel', models.CharField(
                    choices=[
                        ('*', 'Administrador (total)'),
                        ('read', 'Somente leitura'),
                        ('custom', 'Customizado (use o campo permissoes)'),
                    ],
                    default='read', max_length=10, verbose_name='Nível de acesso')),
                ('permissoes', models.CharField(
                    blank=True, default='',
                    help_text=(
                        'Apenas usado quando `nivel = Customizado`. Lista separada por '
                        'vírgula. Ex.: "flows.read,flows.write,nodes.read,settings.read". '
                        'Se vazio com nivel != Customizado, o nível define tudo.'
                    ),
                    max_length=255, verbose_name='Permissões granulares')),
                ('ativo', models.BooleanField(
                    default=True,
                    help_text='Desmarque para bloquear o login sem perder o usuário.',
                    verbose_name='Ativo')),
                ('observacoes', models.CharField(
                    blank=True, default='',
                    help_text='Quem é, qual fábrica/linha responde, contato — livre.',
                    max_length=255, verbose_name='Observações')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('ultimo_login_em', models.DateTimeField(
                    blank=True, null=True,
                    verbose_name='Último login bem-sucedido')),
            ],
            options={
                'verbose_name': 'Usuário Node-RED',
                'verbose_name_plural': 'Usuários Node-RED',
                'ordering': ['username'],
            },
        ),
    ]
