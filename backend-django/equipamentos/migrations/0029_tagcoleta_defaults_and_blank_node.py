from django.db import migrations, models


DEFAULT_TAGS_COLETA = [
    {'nome': 'contagem_entrada', 'tipo_dado': 'INT', 'unidade': 'un', 'fator_conversao': 1.0},
    {'nome': 'contagem_saida', 'tipo_dado': 'INT', 'unidade': 'un', 'fator_conversao': 1.0},
    {'nome': 'estado', 'tipo_dado': 'INT', 'unidade': 'estado', 'fator_conversao': 1.0},
    {'nome': 'velocidade_atual', 'tipo_dado': 'FLOAT', 'unidade': 'un/min', 'fator_conversao': 1.0},
    {'nome': 'ordem_producao', 'tipo_dado': 'STRING', 'unidade': '', 'fator_conversao': 1.0},
    {'nome': 'sku_codigo', 'tipo_dado': 'STRING', 'unidade': '', 'fator_conversao': 1.0},
    {'nome': 'descricao', 'tipo_dado': 'STRING', 'unidade': '', 'fator_conversao': 1.0},
    {'nome': 'formato', 'tipo_dado': 'FLOAT', 'unidade': 'g', 'fator_conversao': 1.0},
    {'nome': 'planejado_op', 'tipo_dado': 'INT', 'unidade': 'un', 'fator_conversao': 1.0},
    {'nome': 'cuc', 'tipo_dado': 'FLOAT', 'unidade': '', 'fator_conversao': 1.0},
    {'nome': 'descarte', 'tipo_dado': 'INT', 'unidade': 'un', 'fator_conversao': 1.0},
]


def criar_tags_padrao(apps, schema_editor):
    Equipamento = apps.get_model('equipamentos', 'Equipamento')
    TagColeta = apps.get_model('equipamentos', 'TagColeta')

    for equipamento in Equipamento.objects.all():
        for defaults in DEFAULT_TAGS_COLETA:
            TagColeta.objects.get_or_create(
                equipamento=equipamento,
                nome_metrica=defaults['nome'],
                defaults={
                    'node_id': '',
                    'tipo_dado': defaults['tipo_dado'],
                    'unidade': defaults['unidade'],
                    'fator_conversao': defaults['fator_conversao'],
                    'ativa': False,
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ('equipamentos', '0028_alter_linhaproducao_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tagcoleta',
            name='nome_metrica',
            field=models.CharField(
                help_text='Variavel OPC. As variaveis padrao ja sao criadas automaticamente para preencher apenas o Node ID.',
                max_length=100,
                verbose_name='Nome da Métrica',
            ),
        ),
        migrations.AlterField(
            model_name='tagcoleta',
            name='node_id',
            field=models.CharField(
                blank=True,
                help_text='Informe apenas o Node ID OPC. Ex: ns=2;s=Linha1.Enchedora.Velocidade',
                max_length=255,
                verbose_name='Node ID',
            ),
        ),
        migrations.RunPython(criar_tags_padrao, migrations.RunPython.noop),
    ]
