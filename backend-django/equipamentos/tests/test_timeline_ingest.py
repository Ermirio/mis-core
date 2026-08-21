from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from equipamentos.flask_replacement_views import _sync_estado_timeline
from equipamentos.models import (
    Area,
    Equipamento,
    EventoEstadoEquipamento,
    Fabrica,
    LinhaProducao,
)


class TimelineIngestTest(TestCase):
    def setUp(self):
        fabrica = Fabrica.objects.create(nome='Fabrica Teste', codigo='F001')
        area = Area.objects.create(nome='Area Teste', codigo='A001', fabrica=fabrica)
        self.linha = LinhaProducao.objects.create(
            codigo='L01',
            nome='Linha 01',
            area=area,
            localizacao='Teste',
            velocidade_planejada=100,
            meta_producao_hora=6000,
            meta_producao_turno=48000,
        )
        self.equipamento = Equipamento.objects.create(
            linha=self.linha,
            nome='Equipamento Timeline',
            codigo='E001',
            tipo='ENCHEDORA',
            localizacao='Teste',
            velocidade_nominal=100,
            velocidade_maxima=120,
        )

    def test_ingestao_cria_evento_aberto_sem_duplicar_estado_repetido(self):
        t0 = timezone.now()

        _sync_estado_timeline(self.equipamento, 1, t0.isoformat())
        _sync_estado_timeline(self.equipamento, 1, (t0 + timedelta(seconds=10)).isoformat())

        eventos = EventoEstadoEquipamento.objects.filter(equipamento=self.equipamento)
        self.assertEqual(eventos.count(), 1)
        self.assertEqual(eventos.first().estado, 'RUN')
        self.assertIsNone(eventos.first().fim)

    def test_ingestao_fecha_evento_anterior_quando_estado_muda(self):
        t0 = timezone.now()
        t1 = t0 + timedelta(minutes=5)

        _sync_estado_timeline(self.equipamento, 1, t0.isoformat())
        _sync_estado_timeline(self.equipamento, 4, t1.isoformat())

        eventos = list(
            EventoEstadoEquipamento.objects
            .filter(equipamento=self.equipamento)
            .order_by('inicio')
        )
        self.assertEqual(len(eventos), 2)
        self.assertEqual(eventos[0].estado, 'RUN')
        self.assertEqual(eventos[0].fim, t1)
        self.assertEqual(eventos[1].estado, 'FAULT')
        self.assertIsNone(eventos[1].fim)
