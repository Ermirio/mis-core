from django.db import migrations


def desativa_tags_descarte(apps, schema_editor):
    """
    Marca como inativas as TagColeta com nome_metrica='descarte'.

    Motivacao: o descarte e calculado por delta entre contagem_entrada e
    contagem_saida (ver MetricaProducao.save()). Manter uma tag de descarte
    como padrao confundia o cadastro e nao agregava informacao - novos
    equipamentos passam a nao receber esta tag (ver DEFAULT_TAGS_COLETA).
    Tags existentes nao sao deletadas para preservar historico; quem ainda
    quiser ler o contador direto do CLP pode reativa-la manualmente.
    """
    TagColeta = apps.get_model('equipamentos', 'TagColeta')
    qs = TagColeta.objects.filter(nome_metrica='descarte', ativa=True)
    total = qs.count()
    if total:
        qs.update(ativa=False)
        print(f"  [0030] {total} tag(s) 'descarte' marcada(s) como inativa(s).")


def reativa_tags_descarte(apps, schema_editor):
    """Reverso: reativa as tags 'descarte' para o estado anterior."""
    TagColeta = apps.get_model('equipamentos', 'TagColeta')
    TagColeta.objects.filter(nome_metrica='descarte', ativa=False).update(ativa=True)


class Migration(migrations.Migration):

    dependencies = [
        ('equipamentos', '0032_unique_codigo_por_escopo'),
    ]

    operations = [
        migrations.RunPython(desativa_tags_descarte, reativa_tags_descarte),
    ]
