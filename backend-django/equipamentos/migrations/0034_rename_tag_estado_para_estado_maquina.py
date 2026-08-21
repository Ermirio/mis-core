from django.db import migrations


def rename_estado_para_estado_maquina(apps, schema_editor):
    """
    Renomeia TagColeta.nome_metrica de 'estado' para 'estado_maquina'.

    Motivo: o coletor OPC, o diagnostics engine (Flask) e as views de
    descartes/realtime esperam o campo 'estado_maquina' no InfluxDB.
    O cadastro no Django registrava a tag padrao como 'estado', criando
    descompasso: diagnosticos reportava "Campo faltando: estado_maquina".
    Agora o nome usado no cadastro e o mesmo persistido pelo coletor.
    """
    TagColeta = apps.get_model('equipamentos', 'TagColeta')

    # Para cada equipamento, se existir tag 'estado' e nao existir
    # 'estado_maquina', renomeia. Caso ambas existam, mantem a antiga
    # como inativa e marca a nova como referencia.
    for tag in TagColeta.objects.filter(nome_metrica='estado'):
        ja_existe = TagColeta.objects.filter(
            equipamento=tag.equipamento, nome_metrica='estado_maquina'
        ).exclude(pk=tag.pk).exists()
        if ja_existe:
            tag.ativa = False
            tag.save(update_fields=['ativa'])
        else:
            tag.nome_metrica = 'estado_maquina'
            tag.save(update_fields=['nome_metrica'])


def reverse_estado_maquina_para_estado(apps, schema_editor):
    """Reverso: volta o nome para 'estado'."""
    TagColeta = apps.get_model('equipamentos', 'TagColeta')
    for tag in TagColeta.objects.filter(nome_metrica='estado_maquina'):
        ja_existe = TagColeta.objects.filter(
            equipamento=tag.equipamento, nome_metrica='estado'
        ).exclude(pk=tag.pk).exists()
        if not ja_existe:
            tag.nome_metrica = 'estado'
            tag.save(update_fields=['nome_metrica'])


class Migration(migrations.Migration):

    dependencies = [
        ('equipamentos', '0033_desativa_tag_descarte_padrao'),
    ]

    operations = [
        migrations.RunPython(
            rename_estado_para_estado_maquina,
            reverse_estado_maquina_para_estado,
        ),
    ]
