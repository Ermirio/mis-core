import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from equipamentos.serializers import EquipamentoColetorSerializer
from equipamentos.models import Equipamento, LinhaProducao, ConexaoOPC, Fabrica, Area

# Limpar dados de teste antigos
Equipamento.objects.filter(codigo="E_V2").delete()
LinhaProducao.objects.filter(codigo="L_V2").delete()
ConexaoOPC.objects.filter(nome="TEST_CONN_V2").delete()

print("Getting Conn...")
conexao, _ = ConexaoOPC.objects.get_or_create(
    nome="TEST_CONN_V2", 
    defaults={
        "url_servidor": "opc.tcp://test:4840", 
        "tag_monitoramento": "ns=2;s=Health",
        "tipo_monitoramento": "HEARTBEAT"
    }
)

print("Getting Fabrica...")
fabrica, _ = Fabrica.objects.get_or_create(nome="TEST_FACTORY", codigo="F_TEST")
print("Getting Area...")
area, _ = Area.objects.get_or_create(nome="TEST_AREA", codigo="A_TEST", fabrica=fabrica)

print("Getting Line...")
linha, _ = LinhaProducao.objects.get_or_create(
    codigo="L_V2",
    defaults={
        "nome": "TEST_LINE_V2",
        "conexao_padrao": conexao,
        "area": area
    }
)
print("Updating Line...")
linha.conexao_padrao = conexao
linha.area = area
linha.save()

print("Getting Equipment...")
eq, _ = Equipamento.objects.get_or_create(
    codigo="E_V2",
    defaults={
        "nome": "TEST_EQ_V2",
        "linha": linha,
        "tipo": "OU",
        "status": "ATIVO",
        "velocidade_nominal": 100,
        "velocidade_maxima": 200,
        "meta_oee": 85.0
    }
)

print("Serializing...")
serializer = EquipamentoColetorSerializer(eq)
data = serializer.data

print("CONEXAO_DETALHES:", json.dumps(data.get('conexao_detalhes'), indent=2))
