
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from models import (CadastroProdutoFlex, ReceitaEnfardadora, ReceitaEnchedora, Linha,DiscrepanciaSKU,
                     )
from serializers import (CadastroProdutoFlexSerializer, ReceitaEnfardadoraSerializer, ReceitaEnchedoraSerializer,
                          DiscrepanciaSKUSerializer,)
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse ,JsonResponse
import requests
import time
from django.db.models import Q

import json
from django.views.decorators.csrf import csrf_exempt  # Import necessário
from digitalfactory.ips.models import TrocaSKU
from django.views.decorators.csrf import csrf_exempt
from pylogix import PLC  # Importar a biblioteca pylogix

from digitalfactory.ips.models import Linha, ReceitaEnchedora, ReceitaEnchedoraItem, ReceitaEnfardadora, ReceitaEnfardadoraItem, TrocaSKU
# Adicione as importações necessárias no início do arquivo views.py (caso ainda não existam)
import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse

def get_lista_op():
    """
    Realiza a chamada SOAP para obter a lista de ordens de produção.
    """
    url = "http://192.168.30.42:82/WsOffLineCom.asmx?op=GetListaOP"
    headers = {"Content-Type": "text/xml"}
    envelope = '''<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                 xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <GetListaOP xmlns="http://www.aplipack.com.br/">
      <UserSoftware>test</UserSoftware>
      <PasswordSoftware>1234</PasswordSoftware>
      <LinhaProducao>L01IP</LinhaProducao>
    </GetListaOP>
  </soap12:Body>
</soap12:Envelope>'''
    response = requests.post(url, data=envelope, headers=headers)
    return response.text

def parse_soap_response(xml_string):
    """
    Faz o parse do XML da resposta SOAP para extrair xStatus e xListaJSON.
    """
    root = ET.fromstring(xml_string)
    status_elem = root.find('.//xStatus')
    json_elem = root.find('.//xListaJSON')
    status = status_elem.text if status_elem is not None else None
    json_data = json_elem.text if json_elem is not None else None
    return status, json_data

def convert_unix_timestamp(dataop_raw):
    """
    Converte uma string no formato /Date(1574431249000)/ para um objeto datetime.
    """
    try:
        ts_str = dataop_raw[dataop_raw.find("(")+1 : dataop_raw.find(")")]
        ts = int(ts_str)
        return datetime.utcfromtimestamp(ts)
    except Exception:
        return None

def orders_view(request):
    """
    View que obtém a lista de ordens de produção via SOAP, processa o JSON e renderiza um template.
    """
    soap_response = get_lista_op()
    status, lista_json = parse_soap_response(soap_response)
    
    if status == "-1":
        error_elem = ET.fromstring(soap_response).find('.//xErro')
        error_msg = error_elem.text if error_elem is not None else "Erro desconhecido"
        return HttpResponse(f"Erro: {error_msg}")

    orders = []
    try:
        data = json.loads(lista_json)
        for ordem in data.get("OrdensProducao", []):
            codigo_sku = ordem.get("CodigoSKU")
            descricao_sku = ordem.get("DescricaoSKU")
            dataop_raw = ordem.get("DataOP", "")
            dataop = convert_unix_timestamp(dataop_raw)
            id_ordem_prod = ordem.get("IdOrdemProd")
            numero_op = ordem.get("NumeroOP")
            dun14 = ordem.get("DUN14")
            validade = ordem.get("Validade")
            quantidade_por_pallet = ordem.get("QuantidadePorPallet")
            status_op = ordem.get("StatusOP")
            
            orders.append({
                "codigo_sku": codigo_sku,
                "descricao_sku": descricao_sku,
                "dataop": dataop.strftime("%d/%m/%Y %H:%M:%S") if dataop else "",
                "id_ordem_prod": id_ordem_prod,
                "numero_op": numero_op,
                "dun14": dun14,
                "validade": validade,
                "quantidade_por_pallet": quantidade_por_pallet,
                "status_op": status_op,
            })
    except Exception as e:
        return HttpResponse(f"Erro ao processar os dados: {str(e)}")
    
    # Renderize um template (ex.: orders_list.html) e passe a lista de ordens para o contexto
    return render(request, "orders_list.html", {"orders": orders})
