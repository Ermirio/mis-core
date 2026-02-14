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
from models import TrocaSKU
from django.views.decorators.csrf import csrf_exempt
from pylogix import PLC  # Importar a biblioteca pylogix

from models import Linha, ReceitaEnchedora, ReceitaEnchedoraItem, ReceitaEnfardadora, ReceitaEnfardadoraItem, TrocaSKU
# Adicione as importações necessárias no início do arquivo views.py (caso ainda não existam)
import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse

def send_sku(request):
    """
    View que processa o envio do SKU selecionado.
    Espera um POST com os dados da ordem.
    """
    if request.method == "POST":
        codigo = request.POST.get("codigo")
        sku = request.POST.get("sku")
        dun14 = request.POST.get("dun14")
        validade = request.POST.get("validade")
        id_ordem_prod = request.POST.get("id_ordem_prod")  # Se precisar usar no SOAP para alterar status, por exemplo
        
        # Data e hora atual
        now = datetime.now()
        dia = now.strftime("%d%m%Y")
        hora = now.strftime("%H%M%S")
        
        # Monta a linha no formato esperado:
        # ";;{codigo};;{sku};{dun14};{validade};{dia};{hora};;"
        file_content = f";;{codigo};;{sku};{dun14};{validade};{dia};{hora};;\n"
        
        # Caminho para o arquivo (verifique se o servidor Django tem acesso ao caminho de rede)
        file_path = r"\\192.168.50.25\nandflash\AUTO\ARQ_auto.txt"
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(file_content)
        except Exception as e:
            return HttpResponse(f"Erro ao escrever o arquivo: {str(e)}")
        
        # Opcional: Se desejar chamar outro web service (por exemplo, para alterar status da ordem) faça aqui
        
        return redirect("orders_view")
    else:
        return HttpResponse("Método não permitido", status=405)
