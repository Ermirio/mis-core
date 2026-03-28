from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ips', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Controle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100)),
                ('area', models.CharField(choices=[('QUALIDADE', 'Qualidade'), ('MANUTENCAO', 'Manutenção'), ('PROCESSOS', 'Processos')], max_length=20)),
                ('descricao', models.TextField(blank=True)),
                ('critico', models.BooleanField(default=False)),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Controle',
                'verbose_name_plural': 'Controles',
                'ordering': ['area', 'nome'],
                'unique_together': {('nome', 'area')},
            },
        ),
        migrations.CreateModel(
            name='IntertravamentoLinha',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('node_id_tag', models.CharField(blank=True, help_text='Endereço OPC UA único da tag de intertravamento (Leitura/Escrita)', max_length=200)),
                ('estado_opc', models.BooleanField(default=True)),
                ('habilitado_software', models.BooleanField(default=True)),
                ('modificado_em', models.DateTimeField(auto_now=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('conexao_opcua', models.ForeignKey(blank=True, help_text='Conexão OPC do equipamento onde a tag é lida', null=True, on_delete=django.db.models.deletion.SET_NULL, to='ips.conexaoopcuaservidor')),
                ('controle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='instancias', to='ips.controle')),
                ('linha', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='intertravamentos', to='ips.linha')),
                ('modificado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Intertravamento de Linha',
                'verbose_name_plural': 'Intertravamentos de Linha',
                'ordering': ['linha', 'controle__area', 'controle__nome'],
            },
        ),
        migrations.CreateModel(
            name='HistoricoIntertravamento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('campo', models.CharField(max_length=20)),
                ('valor_anterior', models.BooleanField()),
                ('valor_novo', models.BooleanField()),
                ('origem', models.CharField(choices=[('OPC', 'Leitura OPC UA'), ('MANUAL', 'Alteração Manual'), ('SISTEMA', 'Sistema')], max_length=10)),
                ('observacao', models.TextField(blank=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('intertravamento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='historico', to='ips.intertravamentolinha')),
            ],
            options={
                'verbose_name': 'Histórico de Intertravamento',
                'verbose_name_plural': 'Histórico de Intertravamentos',
                'ordering': ['-timestamp'],
            },
        ),
    ]
