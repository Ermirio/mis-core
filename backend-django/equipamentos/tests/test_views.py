from django.test import TestCase
from django.utils import timezone
from datetime import datetime, timedelta, time
from rest_framework.test import APIClient
from rest_framework import status
from equipamentos.models import LinhaProducao, Equipamento, TagColeta, ConexaoOPC, Produto, OrdemProducao, CalendarioProducao, TurnoProducao, RegistroProducaoTurno
from unittest.mock import patch, MagicMock

class FactoryProductionViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # 1. Setup Shifts (Turnos)
        # T1: 06:00 - 14:00
        self.t1 = TurnoProducao.objects.create(nome="Turno 1", codigo="T1", hora_inicio=time(6,0), hora_fim=time(14,0), duracao_horas=8)
        # T2: 14:00 - 22:00
        self.t2 = TurnoProducao.objects.create(nome="Turno 2", codigo="T2", hora_inicio=time(14,0), hora_fim=time(22,0), duracao_horas=8)
        # T3: 22:00 - 06:00 (Crosses Midnight)
        self.t3 = TurnoProducao.objects.create(nome="Turno 3", codigo="T3", hora_inicio=time(22,0), hora_fim=time(6,0), duracao_horas=8)
        
        # 2. Setup Line & Equipment
        self.linha = LinhaProducao.objects.create(
            nome="Linha 1", codigo="L1", localizacao="Fabrica", 
            velocidade_planejada=100, meta_producao_hora=1000, meta_producao_turno=8000
        )
        self.conexao = ConexaoOPC.objects.create(nome="OPC Local", url_servidor="opc.tcp://localhost:4840")
        self.equipamento = Equipamento.objects.create(
            nome="Enchedora", codigo="ENCH1", linha=self.linha, tipo="ENCHEDORA",
            localizacao="Inicio", velocidade_nominal=100, velocidade_maxima=120
        )
        # Equipamento.save() cria as tags padrão. Configure a existente em vez
        # de violar a unicidade (equipamento, nome_metrica).
        self.tag_formato = self.equipamento.tags_coleta.get(nome_metrica="formato")
        self.tag_formato.node_id = "ns=2;s=Formato"
        self.tag_formato.formato = "1.0"
        self.tag_formato.ativa = True
        self.tag_formato.save()
        
        # 3. Setup Calendar (Targets in KG)
        # Scenario: T1=120t (120000kg), T2=78t (78000kg), T3=0
        today = timezone.localtime(timezone.now()).date()
        
        CalendarioProducao.objects.create(data=today, linha=self.linha, turno=self.t1, programado=True, meta_producao_turno=120000)
        CalendarioProducao.objects.create(data=today, linha=self.linha, turno=self.t2, programado=True, meta_producao_turno=78000)
        CalendarioProducao.objects.create(data=today, linha=self.linha, turno=self.t3, programado=False, meta_producao_turno=0)
        
        # 4. Setup Product & OP
        self.produto = Produto.objects.create(descricao="Prod 1", codigo="P1", peso_unitario=1.0)
        self.op = OrdemProducao.objects.create(
            codigo="OP1", linha=self.linha, produto=self.produto, 
            meta_total=1000, formato_gramas=1.0, 
            data_planejada_inicio=timezone.now()
        )

    @patch('equipamentos.influx_helpers.get_realtime_metrics')
    @patch('equipamentos.turno_helpers.obter_turno_atual')
    @patch('django.utils.timezone.now')
    def test_day_view_planned_tons(self, mock_now, mock_turno, mock_realtime):
        """
        Verify that Day View returns 198t (120 + 78 + 0)
        """
        # Set time to 19:08 (during T2)
        fixed_now = datetime.now().replace(hour=19, minute=8, second=0, microsecond=0)
        # Ensure TZ aware
        tz = timezone.get_current_timezone()
        fixed_now = fixed_now.replace(tzinfo=tz) if fixed_now.tzinfo is None else fixed_now
        
        mock_now.return_value = fixed_now
        mock_turno.return_value = self.t2
        mock_realtime.return_value = {'toneladas_turno': 10.0} # 10t produced in current shift
        
        # Create history for T1 (Closed) - 110t produced
        RegistroProducaoTurno.objects.create(
            ordem_producao=self.op, linha=self.linha, produto=self.produto,
            data=fixed_now.date(), turno=self.t1,
            producao_toneladas=110.0, producao_unidades=110000,
            tempo_programado_min=480, tempo_disponivel_min=480, tempo_producao_min=400,
            velocidade_planejada=100
        )
        
        response = self.client.get('/api/production/window/throughput/?granularity=day')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Planned: 120 + 78 + 0 = 198
        self.assertEqual(data['planned_tons'], 198.0)
        
        # Actual: 110 (History T1) + 10 (Realtime T2) = 120
        self.assertEqual(data['actual_tons'], 120.0)
        
        # Window
        self.assertEqual(data['window']['granularity'], 'day')

    @patch('equipamentos.influx_helpers.get_realtime_metrics')
    @patch('equipamentos.turno_helpers.obter_turno_atual')
    @patch('django.utils.timezone.now')
    def test_shift_view_planned_tons(self, mock_now, mock_turno, mock_realtime):
        """
        Verify that Shift View (T2) returns 78t
        """
        # Set time to 19:08 (during T2)
        fixed_now = datetime.now().replace(hour=19, minute=8, second=0, microsecond=0)
        tz = timezone.get_current_timezone()
        fixed_now = fixed_now.replace(tzinfo=tz) if fixed_now.tzinfo is None else fixed_now
        
        mock_now.return_value = fixed_now
        mock_turno.return_value = self.t2
        mock_realtime.return_value = {'toneladas_turno': 15.0}
        
        response = self.client.get('/api/production/window/throughput/?granularity=shift')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Planned: T2 only = 78t
        self.assertEqual(data['planned_tons'], 78.0)
        
        # Actual: Realtime only = 15t
        self.assertEqual(data['actual_tons'], 15.0)

    @patch('equipamentos.influx_helpers.get_realtime_metrics')
    @patch('equipamentos.turno_helpers.obter_turno_atual')
    @patch('django.utils.timezone.now')
    def test_tph_calculations(self, mock_now, mock_turno, mock_realtime):
        """
        Verify TPH calculations and edge cases
        """
        # Set time to start of T2 + 1 hour (15:00)
        fixed_now = datetime.now().replace(hour=15, minute=0, second=0, microsecond=0)
        tz = timezone.get_current_timezone()
        fixed_now = fixed_now.replace(tzinfo=tz) if fixed_now.tzinfo is None else fixed_now
        
        mock_now.return_value = fixed_now
        mock_turno.return_value = self.t2
        mock_realtime.return_value = {'toneladas_turno': 10.0}
        
        response = self.client.get('/api/production/window/throughput/?granularity=shift')
        data = response.json()
        
        # Elapsed: 1 hour. Actual TPH = 10 / 1 = 10
        self.assertEqual(data['actual_tph'], 10.0)
        
        # Remaining: 7 hours. Planned 78. Saldo = 68. Min Req = 68 / 7 = 9.71
        self.assertAlmostEqual(data['min_required_tph'], 9.71, places=2)
        self.assertEqual(data['status_flag'], 'NORMAL')
        
        # Scenario: Goal Exceeded
        mock_realtime.return_value = {'toneladas_turno': 80.0} # > 78
        response = self.client.get('/api/production/window/throughput/?granularity=shift')
        data = response.json()
        self.assertEqual(data['min_required_tph'], 0.0)
        self.assertEqual(data['status_flag'], 'SUPERADO')
        
        # Scenario: Deadline Passed (Time is 22:00)
        fixed_now = datetime.now().replace(hour=22, minute=0, second=0, microsecond=0)
        fixed_now = fixed_now.replace(tzinfo=tz) if fixed_now.tzinfo is None else fixed_now
        mock_now.return_value = fixed_now
        mock_realtime.return_value = {'toneladas_turno': 50.0} # < 78
        
        response = self.client.get('/api/production/window/throughput/?granularity=shift')
        data = response.json()
        self.assertIsNone(data['min_required_tph'])
        self.assertEqual(data['status_flag'], 'ATRASADO')
