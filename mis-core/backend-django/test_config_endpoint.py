import os
import django
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from equipamentos.views import configuracao_coletor
from equipamentos.models import Equipamento, LinhaProducao, ConexaoOPC

# Garantir dados de teste
try:
    conexao = ConexaoOPC.objects.create(
        nome="TEST_CONN", 
        url_servidor="opc.tcp://test:4840", 
        tag_monitoramento="ns=2;s=Health",
        tipo_monitoramento="HEARTBEAT"
    )
except:
    conexao = ConexaoOPC.objects.get(nome="TEST_CONN")

try:
    linha = LinhaProducao.objects.create(nome="TEST_LINE", codigo="L_TEST", conexao_padrao=conexao)
except:
    linha = LinhaProducao.objects.get(codigo="L_TEST")
    linha.conexao_padrao = conexao
    linha.save()

try:
    eq = Equipamento.objects.create(nome="TEST_EQ", codigo="E_TEST", linha=linha, tipo="OU", status="ATIVO")
except:
    eq = Equipamento.objects.get(codigo="E_TEST")

factory = APIRequestFactory()
request = factory.get('/api/configuracao_coletor/')

response = configuracao_coletor(request)
print(response.data)
