"""Testes do filtro ativo=True/ativa=True nos ViewSets de Sensor e TagColeta."""
from django.test import TestCase
from rest_framework.test import APIClient
from equipamentos.models import LinhaProducao, Equipamento, Sensor, TagColeta


class SensorViewSetFiltroAtivoTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.linha = LinhaProducao.objects.create(
            codigo="L01", nome="L 01", localizacao="A",
            velocidade_planejada=100.0, meta_producao_hora=6000, meta_producao_turno=48000,
        )
        self.equipamento = Equipamento.objects.create(
            linha=self.linha, nome="Enchedora", codigo="E001", tipo="ENCHEDORA",
            localizacao="X", velocidade_nominal=100.0, velocidade_maxima=120.0,
        )
        self.s_ativo = Sensor.objects.create(
            equipamento=self.equipamento, codigo="S001", nome="Ativo",
            tipo="INPUT_FLOAT", tag_influxdb="ativo", ativo=True,
        )
        self.s_inativo = Sensor.objects.create(
            equipamento=self.equipamento, codigo="S002", nome="Inativo",
            tipo="INPUT_FLOAT", tag_influxdb="inativo", ativo=False,
        )

    def _nomes(self, response):
        data = response.json()
        results = data.get('results', data) if isinstance(data, dict) else data
        return {item['nome'] for item in results}

    def test_get_sensores_filtra_inativos_por_padrao(self):
        r = self.client.get(f"/api/sensores/?equipamento={self.equipamento.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._nomes(r), {"Ativo"})

    def test_get_sensores_inclui_inativos_quando_solicitado(self):
        r = self.client.get(
            f"/api/sensores/?equipamento={self.equipamento.id}&incluir_inativos=true"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._nomes(r), {"Ativo", "Inativo"})


class TagColetaViewSetFiltroAtivoTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.linha = LinhaProducao.objects.create(
            codigo="L01", nome="L 01", localizacao="A",
            velocidade_planejada=100.0, meta_producao_hora=6000, meta_producao_turno=48000,
        )
        self.equipamento = Equipamento.objects.create(
            linha=self.linha, nome="Enchedora", codigo="E001", tipo="ENCHEDORA",
            localizacao="X", velocidade_nominal=100.0, velocidade_maxima=120.0,
        )
        # ensure_default_tags_for_equipment cria as tags com ativa=False;
        # marca contagem_entrada como ativa para isolar.
        TagColeta.objects.filter(
            equipamento=self.equipamento, nome_metrica='contagem_entrada'
        ).update(ativa=True)

    def test_get_tags_filtra_inativas_por_padrao(self):
        r = self.client.get(f"/api/tags-coleta/?equipamento={self.equipamento.id}")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        results = data.get('results', data) if isinstance(data, dict) else data
        nomes = {item['nome_metrica'] for item in results}
        self.assertIn('contagem_entrada', nomes)
        # tags padrao restantes vem como ativa=False -> filtradas
        self.assertNotIn('contagem_saida', nomes)

    def test_incluir_inativos_traz_tudo(self):
        r = self.client.get(
            f"/api/tags-coleta/?equipamento={self.equipamento.id}&incluir_inativos=true"
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        results = data.get('results', data) if isinstance(data, dict) else data
        nomes = {item['nome_metrica'] for item in results}
        self.assertIn('contagem_entrada', nomes)
        self.assertIn('contagem_saida', nomes)
