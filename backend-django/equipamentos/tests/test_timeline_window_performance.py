from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from equipamentos.models import (
    Area,
    Equipamento,
    EventoEstadoEquipamento,
    Fabrica,
    LinhaProducao,
)


class TimelineWindowPerformanceTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        fabrica = Fabrica.objects.create(nome='Fabrica Teste', codigo='F001')
        area = Area.objects.create(nome='Area Teste', codigo='A001', fabrica=fabrica)
        self.linha = LinhaProducao.objects.create(
            codigo='L20',
            nome='Linha 20',
            area=area,
            localizacao='Teste',
            velocidade_planejada=100,
            meta_producao_hora=6000,
            meta_producao_turno=48000,
        )
        self.outra_linha = LinhaProducao.objects.create(
            codigo='L21',
            nome='Linha 21',
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
        self.outro_equipamento = Equipamento.objects.create(
            linha=self.outra_linha,
            nome='Outro Equipamento',
            codigo='E001',
            tipo='ENCHEDORA',
            localizacao='Teste',
            velocidade_nominal=100,
            velocidade_maxima=120,
        )

    def test_compact_payload_does_not_expand_nested_configuration(self):
        linhas = self.client.get('/api/linhas/', {'compact': 1, 'codigo': 'L20'})
        self.assertEqual(linhas.status_code, 200)
        linha = linhas.json()['results'][0]
        self.assertEqual(linha['codigo'], 'L20')
        self.assertNotIn('equipamentos', linha)
        self.assertNotIn('sensores', linha)

        equipamentos = self.client.get(
            '/api/equipamentos/',
            {'compact': 1, 'linha': self.linha.id},
        )
        self.assertEqual(equipamentos.status_code, 200)
        equipamento = equipamentos.json()['results'][0]
        self.assertEqual(equipamento['codigo'], 'E001')
        self.assertNotIn('tags_coleta', equipamento)
        self.assertNotIn('sensores', equipamento)

    def test_timeline_returns_only_events_overlapping_selected_window(self):
        now = timezone.now()
        window_start = now - timedelta(hours=2)
        window_end = now - timedelta(hours=1)

        before = EventoEstadoEquipamento.objects.create(
            equipamento=self.equipamento,
            estado='RUN',
            inicio=window_start - timedelta(hours=2),
            fim=window_start - timedelta(minutes=1),
        )
        overlap = EventoEstadoEquipamento.objects.create(
            equipamento=self.equipamento,
            estado='WAIT',
            inicio=window_start - timedelta(minutes=10),
            fim=window_start + timedelta(minutes=10),
        )
        inside = EventoEstadoEquipamento.objects.create(
            equipamento=self.equipamento,
            estado='RUN',
            inicio=window_start + timedelta(minutes=20),
            fim=window_start + timedelta(minutes=40),
        )
        after = EventoEstadoEquipamento.objects.create(
            equipamento=self.equipamento,
            estado='FAULT',
            inicio=window_end + timedelta(minutes=1),
            fim=window_end + timedelta(minutes=10),
        )
        other_line = EventoEstadoEquipamento.objects.create(
            equipamento=self.outro_equipamento,
            estado='RUN',
            inicio=window_start + timedelta(minutes=5),
            fim=window_start + timedelta(minutes=15),
        )

        response = self.client.get('/api/eventos-estado/', {
            'linha_id': self.linha.id,
            'data_inicio': window_start.isoformat(),
            'data_fim': window_end.isoformat(),
            'page_size': 100,
        })
        self.assertEqual(response.status_code, 200)
        ids = {item['id'] for item in response.json()['results']}
        self.assertEqual(ids, {overlap.id, inside.id})
        self.assertNotIn(before.id, ids)
        self.assertNotIn(after.id, ids)
        self.assertNotIn(other_line.id, ids)

    def test_full_status_accepts_line_filter(self):
        response = self.client.get('/api/full_equipment_status/', {'linha_id': self.linha.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.json()], [self.equipamento.id])
