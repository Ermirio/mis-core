import time
import json
import requests
import socket
import io
from smb.SMBConnection import SMBConnection
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Count, Avg
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import Group
from django.views.decorators.http import require_GET
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pycomm3 import SLCDriver
import traceback
from opcua import Client
from opcua import ua
from opcua.ua import UaError
from .models import Linha
from .serializers import LinhaOPCConfigSerializer
from .models import (
    Produto, Linha, Equipamento, Variavel, Formato, FormatoVariavel,
    ConfiguracaoEquipamentoVariavel, Impressora, InkjetPrinter,
    DiscrepanciaSKU, TrocaSKU, LogEquipamentoTroca, StatusLinha,
    ConexaoOPCUAServidor, AssociacaoProdutoLinha,
    LiberacaoSAP, ValidacaoQualidade,
    MensagemLinha, MencaoMensagem, UltimaVisualizacaoChat,
)
from .serializers import (
    ProdutoSerializer, ProdutoResumoSerializer, LinhaSerializer, LinhaStatusSerializer,
    EquipamentoSerializer, VariavelSerializer, FormatoSerializer, 
    FormatoVariavelSerializer, ConfiguracaoEquipamentoVariavelSerializer,
    DiscrepanciaSKUSerializer, TrocaSKUSerializer, TrocaSKURequestSerializer,
    TrocaSKUResponseSerializer, SincronizacaoSKUSerializer
)
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import logging
import re

# Configuração do logger para arquivos
class FileLogger:
    def __init__(self, log_file='app.log'):
        self._logger = logging.getLogger(f'FileLogger_{log_file}')
        if not self._logger.handlers:
            self._logger.setLevel(logging.INFO)
            handler = logging.FileHandler(log_file)
            formatter = logging.Formatter('[%(asctime)s] - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

    def log_request(self, method, url, headers, body):
        self._logger.info(f"Request - Method: {method}, URL: {url}, Headers: {headers}, Body: {body}")

    def log_response(self, status_code, response_body):
        self._logger.info(f"Response - Status: {status_code}, Body: {response_body}")

file_logger = FileLogger('requests.log')

# Classes para comunicação com impressora Inkjet
class SocketClient:
    def __init__(self, server_ip, server_port):
        self.server_ip = server_ip
        self.server_port = int(server_port)
        self.sock = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.server_ip, self.server_port))

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def send_command(self, command):
        if self.sock:
            self.sock.sendall(command.encode())

    def wait_for_response(self, timeout=10):
        if self.sock:
            try:
                self.sock.settimeout(timeout)
                response = self.sock.recv(1024).decode('ascii')
                return response
            except socket.timeout:
                return ""
        return ""

    def make_request(self, command):
        try:
            self.connect()
            self.send_command(command)
            response = self.wait_for_response()
            return response
        finally:
            self.disconnect()

class CommandHelper:
    @staticmethod
    def sla_command(job, line_number, description, sku, dun14):
        return f"SLA|{job}|DESCRICAO_SKU={description}|SKU={sku}|COD_BARRAS={dun14}|LINHA={line_number}|\r"

    @staticmethod
    def sla_validation(response, format_name):
    # A impressora pode enviar 'ACK\r\n' ou ' ACK '.
    # O .strip() remove espaços/quebras de linha.
    # O .upper() garante a comparação.
        return response.strip().upper() == "ACK"

# ==================== FUNÇÕES DE ESCRITA NOS CLPs ====================

# --- FUNÇÃO escrever_plc TOTALMENTE ATUALIZADA ---
def escrever_plc(equipamento, variaveis_dados):
    """
    Escreve variáveis no CLP via OPC UA com lógica de retentativa para TypeMismatch.
    """
    erros = []
    print(f"[{equipamento.nome}] Iniciando escrita via OPC UA...")

    if not equipamento.conexao_opcua:
        erros.append(f"[{equipamento.nome}] Nenhuma conexão OPC UA configurada.")
        return erros

    url = equipamento.conexao_opcua.url
    caminho_plc = equipamento.conexao_opcua.caminho_plc
    print(f"[{equipamento.nome}] Tentando conectar via OPC UA em {url}...")
    
    client = Client(url, timeout=10)
    
    try:
        client.connect()
        print(f"[{equipamento.nome}] Conectado via OPC UA.")
        
        for var_data in variaveis_dados:
            variavel_obj = var_data['variavel_obj']
            valor = var_data['valor']
            tag_plc = var_data['tag_plc_no_equipamento']
            
            if not tag_plc:
                erros.append(f"[{equipamento.nome}] Tag PLC não configurada para variável '{variavel_obj.nome}'.")
                continue
                
            node_path = f"ns=2;s={caminho_plc}{tag_plc}"
            
            try:
                node = client.get_node(node_path)
                
                # 1. Converte o valor baseado no tipo do *Banco de Dados*
                valor_convertido = convert_value(variavel_obj.tipo, valor)
                tipo_django = variavel_obj.tipo.upper()
                
                print(f"[{equipamento.nome}] Escrevendo tag '{node_path}' com valor '{valor_convertido}' (Tipo DB: {tipo_django})...")

                # 2. Mapeia o tipo do DB para o VariantType do OPC UA
                valor_escrita = None
                if tipo_django == "REAL":
                    valor_escrita = ua.DataValue(ua.Variant(float(valor_convertido), ua.VariantType.Float))
                elif tipo_django == "DINT":
                    valor_escrita = ua.DataValue(ua.Variant(int(valor_convertido), ua.VariantType.Int32))
                elif tipo_django == "UDINT":
                    valor_escrita = ua.DataValue(ua.Variant(int(valor_convertido), ua.VariantType.UInt32))
                elif tipo_django == "UINT":
                    valor_escrita = ua.DataValue(ua.Variant(int(valor_convertido), ua.VariantType.UInt32))
                elif tipo_django == "INT":
                    valor_escrita = ua.DataValue(ua.Variant(int(valor_convertido), ua.VariantType.Int16))
                elif tipo_django == "BOOL":
                    valor_escrita = ua.DataValue(ua.Variant(bool(valor_convertido), ua.VariantType.Boolean))
                else: # STRING
                    valor_escrita = ua.DataValue(ua.Variant(str(valor_convertido), ua.VariantType.String))
                    
                valor_escrita.ServerTimestamp = None
                valor_escrita.SourceTimestamp = None
                
                # 3. TENTATIVA 1: Escreve o valor
                node.set_value(valor_escrita)
                print(f"[{equipamento.nome}] Escrita (Tentativa 1) bem-sucedida em '{node_path}'.")

            except UaError as e:
                # 4. CAPTURA A FALHA: Verifica se é BadTypeMismatch
                if "BadTypeMismatch" in str(e):
                    print(f"[{equipamento.nome}] ⚠️ Mismatch em '{node_path}'. Tipo no DB: {tipo_django}. Tentando auto-correção...")
                    try:
                        # 5. RETENTATIVA: Pede o tipo correto ao servidor
                        expected_type = node.get_data_type_as_variant_type()
                        
                        # Cria um novo valor forçando o tipo esperado pelo servidor
                        valor_corrigido = ua.DataValue(ua.Variant(valor_convertido, expected_type))
                        valor_corrigido.ServerTimestamp = None
                        valor_corrigido.SourceTimestamp = None

                        print(f"[{equipamento.nome}]   ... Tipo esperado: {expected_type}. Tentando escrever novamente...")
                        
                        # Tenta escrever novamente
                        node.set_value(valor_corrigido)
                        print(f"[{equipamento.nome}] ✅ Escrita (Tentativa 2) bem-sucedida em '{node_path}'.")
                    
                    except Exception as e_retry:
                        # A retentativa falhou (ex: valor "ABC" não pode ser convertido para Int32)
                        erro_msg = f"[{equipamento.nome}] Erro na auto-correção em '{node_path}': {str(e_retry)} (DB: {tipo_django}, Esperado: {expected_type})"
                        print(f"[{equipamento.nome}] ❌ {erro_msg}")
                        erros.append(erro_msg)
                else:
                    # O erro não era TypeMismatch (ex: BadNodeIdUnknown, BadUserAccessDenied)
                    erro_msg = f"[{equipamento.nome}] Erro OPC UA em '{node_path}': {str(e)} (DB: {tipo_django})"
                    print(f"[{equipamento.nome}] ❌ {erro_msg}")
                    erros.append(erro_msg)
            
            except Exception as e_geral:
                # Outro erro (ex: falha no convert_value, get_node)
                erro_msg = f"[{equipamento.nome}] Erro geral em '{node_path}': {str(e_geral)} (DB: {tipo_django})"
                print(f"[{equipamento.nome}] ❌ {erro_msg}")
                erros.append(erro_msg)
            
            time.sleep(0.05) # Pequeno atraso entre as escritas
            
    except TimeoutError as e:
        erros.append(f"[{equipamento.nome}] Erro de timeout: Não foi possível conectar ao servidor em {url}.")
        print(f"[{equipamento.nome}] Erro de timeout: {str(e)}")
    except Exception as e:
        erros.append(f"[{equipamento.nome}] Erro na conexão ou escrita (OPC UA): {str(e)}")
        print(f"[{equipamento.nome}] Falha detalhada: {traceback.format_exc()}")
    finally:
        try:
            if client.uaclient._uasocket._socket: 
                client.disconnect()
                print(f"[{equipamento.nome}] Conexão OPC UA desconectada.")
        except AttributeError:
            print(f"[{equipamento.nome}] Nenhuma conexão ativa para desconectar.")
        except Exception as e:
            print(f"[{equipamento.nome}] Erro ao desconectar OPC UA: {str(e)}")

    return erros

# Em views.py
def convert_value(tipo, valor):
    """Converte valor para o tipo apropriado.

    Para tipos inteiros (DINT/UDINT/UINT/INT), aceita também strings em formato
    float como "32.0" — isso pode acontecer quando o Recipe Monitor gravou a
    receita após ler do CLP (Pydantic em versões antigas coercionava int → float).
    int("32.0") falha, mas int(float("32.0")) = 32 funciona.
    """
    try:
        if tipo == "REAL":
            return float(valor)
        elif tipo in ("DINT", "UDINT", "UINT", "INT"):
            # Aceita "32" e "32.0" — defensivo para receitas gravadas pelo
            # Recipe Monitor antes do fix de schemas.
            return int(float(valor))
        elif tipo == "BOOL":
            return str(valor).strip().lower() in ['true', '1', 'yes']
        elif tipo == "STRING":
            return str(valor)
        else:
            return valor
    except Exception:
        return valor

def escrever_impressora_3m(linha, codigo_sku, sku, descricao, dun14, validade, dia=None, hora=None):
    """Escreve dados nas impressoras 3M da linha"""
    erros = []
    impressoras = linha.impressoras_3m.all()
    print(f"Impressoras 3M disponíveis na linha {linha.nome}: {[impressora.nome for impressora in impressoras]}")

    if not impressoras.exists():
        erros.append(f"[{linha.nome}] Nenhuma impressora 3M associada à linha.")
        return erros

    import pytz
    tz_br = pytz.timezone('America/Sao_Paulo')
    agora = datetime.now(tz_br)
    dia_atual = agora.strftime("%d%m%Y")
    hora_atual = agora.strftime("%H%M%S")
    dia = dia or dia_atual
    hora = hora or hora_atual

    dados_impressora = f"{linha.nome} {codigo_sku} {sku} {dun14} {validade} {dia} {hora}"
    print(f"Dados para a impressora: {dados_impressora}")

    codigo_sku = codigo_sku or ""
    sku_param = sku or ""
    descricao_param = descricao or ""
    dun14_param = dun14 or ""
    validade_param = validade or ""
    dia_param = dia or ""
    hora_param = hora or ""

    conteudo = f";;{descricao_param};{sku_param};{dun14_param};{validade_param};{dia_atual};{hora_atual};;\r\n"
    conteudo02 = f";;;;;;;{dia_atual};{hora_atual};;\r\n"
    print(f"Conteúdo a ser escrito: {conteudo}")

    for impressora in impressoras:
        if not impressora.ip:
            erros.append(f"[{impressora.nome}] IP não configurado.")
            continue
        print(f"[{impressora.nome}] Conectando via SMB em {impressora.ip}")

        try:
            conn = SMBConnection('', '', 'mis-server', impressora.nome, use_ntlm_v2=True, is_direct_tcp=True)
            connected = conn.connect(impressora.ip, 445, timeout=10)
            if not connected:
                erros.append(f"[{impressora.nome}] Falha ao conectar via SMB em {impressora.ip}:445")
                continue

            conteudo_bytes = io.BytesIO(conteudo.encode('utf-8'))
            conn.storeFile('nandflash', '/AUTO/ARQ_auto.txt', conteudo_bytes)
            print(f"[{impressora.nome}] Arquivo escrito com sucesso via SMB: {conteudo}")

            time.sleep(5)

            conteudo02_bytes = io.BytesIO(conteudo02.encode('utf-8'))
            conn.storeFile('nandflash', '/AUTO/ARQ_auto.txt', conteudo02_bytes)
            print(f"[{impressora.nome}] SKU: {sku_param} definido como atual via SMB: {conteudo02}")

            conn.close()
        except Exception as e:
            erros.append(f"[{impressora.nome}] Erro ao escrever via SMB em {impressora.ip}: {str(e)}")
            print(f"[{impressora.nome}] Detalhes do erro: {traceback.format_exc()}")

    return erros

def escrever_impressora_inkjet(linha, sku, descricao, dun14):
    """Escreve dados nas impressoras Inkjet da linha"""
    erros = []
    impressoras_inkjet = linha.impressoras_inkjet.all()
    print(f"Impressoras Inkjet disponíveis na linha {linha.nome}: {[impressora.nome for impressora in impressoras_inkjet]}")

    if not impressoras_inkjet.exists():
        erros.append(f"[{linha.nome}] Nenhuma impressora Inkjet associada à linha.")
        return erros

    for printer in impressoras_inkjet:
        try:
            command = CommandHelper.sla_command(
                job=printer.format_name,
                line_number=linha.nome,
                description=descricao,
                sku=sku,
                dun14=dun14
            )
            
            sock_client = SocketClient(printer.ip_address, printer.port)
            sla_response = sock_client.make_request(command)
            
            if not CommandHelper.sla_validation(sla_response, printer.format_name):
                erros.append(f"[{printer.nome}] Falha na validação da resposta SLA. Resposta: {sla_response}")
            else:
                print(f"[{printer.nome}] Comando SLA enviado com sucesso.")
                
        except Exception as e:
            erros.append(f"[{printer.nome}] Erro na comunicação: {str(e)}")

    return erros

# ==================== VIEWS DE API ====================

class ProdutoList(APIView):
    """Lista e cria produtos"""
    def get(self, request):
        produtos = Produto.objects.all()
        serializer = ProdutoSerializer(produtos, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ProdutoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class FormatoList(APIView):
    """Lista e cria formatos"""
    def get(self, request):
        formatos = Formato.objects.all()
        serializer = FormatoSerializer(formatos, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = FormatoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class EquipamentoList(APIView):
    """Lista e cria equipamentos"""
    def get(self, request):
        equipamentos = Equipamento.objects.all()
        serializer = EquipamentoSerializer(equipamentos, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = EquipamentoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ==================== VIEWS DE INTERFACE ====================

def index(request):
    """Página inicial"""
    context = {'linhas': range(1, 22)}
    return render(request, 'index.html', context)

def linhas_disponiveis(request):
    """
    Retorna as linhas ativas e suas categorias, incluindo 'liquidos'.
    """
    linhas = sorted(Linha.objects.filter(ativa=True).values_list('nome', flat=True))
    
    # Listas de linhas por categoria. Adapte estas listas conforme as linhas da sua produção.
    flexiveis = ['L14', 'L15', 'L17', 'L18', 'L19', 'L20', 'L21']
    cartucho = ['L01', 'L02', 'L06', 'L09', 'L10', 'L16']
    liquidos = ['L30', 'L31', 'L32']

    data = {
        'linhas': linhas,
        'flexiveis': [f for f in flexiveis if f in linhas],
        'cartucho': [c for c in cartucho if c in linhas],
        'liquidos': [l for l in liquidos if l in linhas]
    }

    return JsonResponse(data)

# No seu arquivo views.py

# ... (outras importações e funções) ...

def linha_detalhes(request, linha_nome):
    """
    Retorna detalhes de uma linha específica, incluindo produtos e histórico de trocas paginado.
    <<< CORRIGIDO: A estrutura do JSON para 'logs_equipamentos' foi ajustada
    para corresponder ao que o frontend espera.
    """
    linha = get_object_or_404(Linha, nome=linha_nome)

    # Lógica de produtos...
    associacoes = AssociacaoProdutoLinha.objects.filter(linha=linha).select_related('produto', 'formato')
    produtos_list = [
        {
            'codigo_sku': assoc.produto.sku,
            'descricao_sku': assoc.produto.descricao,
            'dun14': assoc.produto.dun14,
            'validade': assoc.produto.validade,
            'numero_op': assoc.produto.numero_op,
            'dataop_str': assoc.produto.dataop_str,
            'status_op': assoc.produto.status_op,
            'formato_associado': assoc.formato.nome if assoc.formato else None
        } for assoc in associacoes
    ]

    # Paginação...
    page_number = request.GET.get('page', 1)
    per_page = request.GET.get('per_page', 10)

    try:
        page_number = int(page_number)
        per_page = int(per_page)
    except (ValueError, TypeError):
        page_number = 1
        per_page = 10

    sku_filter = request.GET.get('sku', '').strip()
    qs_trocas = TrocaSKU.objects.filter(linha=linha_nome)
    if sku_filter:
        qs_trocas = qs_trocas.filter(sku_trocado__icontains=sku_filter)
    all_trocas = qs_trocas.select_related('usuario').order_by('-data_hora')
    paginator = Paginator(all_trocas, per_page)

    try:
        trocas_paginadas = paginator.page(page_number)
    except PageNotAnInteger:
        trocas_paginadas = paginator.page(1)
    except EmptyPage:
        trocas_paginadas = paginator.page(paginator.num_pages)

    ultimas_trocas_list = []
    for troca in trocas_paginadas:
        equipamentos_logs_list = []
        for log in troca.logs_equipamentos.all():
            # <<< CORREÇÃO PRINCIPAL: As chaves do dicionário foram alteradas aqui
            equipamentos_logs_list.append({
                "nome": log.nome_equipamento,             # Era 'nome_equipamento'
                "tipo": log.tipo_equipamento,             # Era 'tipo_equipamento'
                "sucesso": log.status == 'sucesso',       # A chave agora é 'sucesso'
                "mensagem": log.mensagem,
                "variaveis_escritas": log.variaveis_escritas,
                "variaveis_total": log.variaveis_total,
                "tempo_execucao": log.tempo_execucao,
                "erros": [log.erro_detalhado] if log.erro_detalhado else []
            })
        
        resumo_execucao = troca.get_resumo_execucao()

        # Tenta pegar o nome completo, senão o username, senão 'N/A'
        usuario_nome = 'N/A'
        if troca.usuario:
            usuario_nome = troca.usuario.get_full_name() or troca.usuario.username
    
        ultimas_trocas_list.append({
            'id': troca.id,
            'sku_trocado': troca.sku_trocado,
            'descricao': troca.descricao,
            'data_hora': troca.data_hora.isoformat(),
            'status_visual': troca.get_status_visual(),
            'tem_erros': resumo_execucao['falhas'] > 0,
            'resumo_execucao': resumo_execucao,
            # A chave principal 'equipamentos_logs' já estava correta
            'equipamentos_logs': equipamentos_logs_list,
            'usuario_nome': usuario_nome
        })

    data = {
        'linha': {'nome': linha.nome, 'descricao': linha.descricao},
        'produtos': produtos_list,
        'ultimas_trocas': ultimas_trocas_list,
        'paginacao': {
            'page': trocas_paginadas.number,
            'per_page': per_page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'has_next': trocas_paginadas.has_next(),
            'has_previous': trocas_paginadas.has_previous(),
            'start_index': trocas_paginadas.start_index(),
            'end_index': trocas_paginadas.end_index(),
        }
    }

    return JsonResponse(data)


def analytics_trocas(request, linha_nome):
    """
    Retorna analytics agregados de trocas para uma linha.
    GET /api/analytics/trocas/<linha_nome>/
    """
    get_object_or_404(Linha, nome=linha_nome)

    agora = timezone.now()
    hoje_inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    semana_inicio = agora - timedelta(days=7)
    mes_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ano_inicio = agora.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    doze_meses_atras = agora - timedelta(days=365)

    qs_base = TrocaSKU.objects.filter(linha=linha_nome)

    def _resumo(qs):
        total = qs.count()
        sucessos = qs.filter(sucesso=True).count()
        taxa = round(sucessos / total * 100, 1) if total > 0 else 0
        return {"trocas": total, "taxa_sucesso": taxa}

    tempo_medio_resultado = (
        qs_base.filter(tempo_execucao__isnull=False)
        .aggregate(media=Avg('tempo_execucao'))
    )
    tempo_medio = round(tempo_medio_resultado['media'] or 0, 1)

    resumo = {
        "hoje": _resumo(qs_base.filter(data_hora__gte=hoje_inicio)),
        "semana": _resumo(qs_base.filter(data_hora__gte=semana_inicio)),
        "mes_atual": _resumo(qs_base.filter(data_hora__gte=mes_inicio)),
        "ano": _resumo(qs_base.filter(data_hora__gte=ano_inicio)),
        "total_geral": _resumo(qs_base),
        "tempo_medio_seg": tempo_medio,
    }

    # Tendência mensal — últimos 12 meses
    por_mes = (
        qs_base
        .filter(data_hora__gte=doze_meses_atras)
        .annotate(mes=TruncMonth('data_hora'))
        .values('mes')
        .annotate(
            trocas=Count('id'),
            sucessos=Count('id', filter=Q(sucesso=True)),
            tempo_medio=Avg('tempo_execucao'),
        )
        .order_by('mes')
    )

    tendencia_mensal = []
    for entry in por_mes:
        total = entry['trocas']
        taxa = round(entry['sucessos'] / total * 100, 1) if total > 0 else 0
        tendencia_mensal.append({
            "mes": entry['mes'].strftime('%b/%y'),
            "mes_iso": entry['mes'].strftime('%Y-%m'),
            "trocas": total,
            "taxa_sucesso": taxa,
            "tempo_medio": round(entry['tempo_medio'] or 0, 1),
        })

    # Top 10 SKUs mais trocados no último ano
    top_skus_qs = (
        qs_base
        .filter(data_hora__gte=doze_meses_atras)
        .values('sku_trocado', 'descricao')
        .annotate(
            trocas=Count('id'),
            sucessos=Count('id', filter=Q(sucesso=True)),
            tempo_medio=Avg('tempo_execucao'),
        )
        .order_by('-trocas')[:10]
    )

    top_skus = []
    for entry in top_skus_qs:
        total = entry['trocas']
        taxa = round(entry['sucessos'] / total * 100, 1) if total > 0 else 0
        top_skus.append({
            "sku": entry['sku_trocado'],
            "descricao": entry['descricao'],
            "trocas": total,
            "taxa_sucesso": taxa,
            "tempo_medio": round(entry['tempo_medio'] or 0, 1),
        })

    return JsonResponse({
        "linha": linha_nome,
        "resumo": resumo,
        "tendencia_mensal": tendencia_mensal,
        "top_skus": top_skus,
    })


def buscar_skus(request):
    """
    Busca SKUs com base em critérios de pesquisa.
    CORRIGIDO: Agora filtra produtos que têm associação com a linha especificada.
    """
    query = request.GET.get('q', '')
    linha_nome = request.GET.get('linha', '')
    
    if not query:
        return JsonResponse({'skus': []})
    
    # Base query
    produtos_query = Produto.objects.filter(
        Q(sku__icontains=query) | 
        Q(descricao__icontains=query) |
        Q(numero_op__icontains=query) |
        Q(dun14__icontains=query)
    )
    
    # NOVA LÓGICA: Se linha especificada, filtrar apenas produtos associados
    if linha_nome:
        try:
            linha = Linha.objects.get(nome=linha_nome)
            # Filtrar produtos que têm associação com esta linha
            produtos_com_associacao = AssociacaoProdutoLinha.objects.filter(
                linha=linha
            ).values_list('produto_id', flat=True)
            produtos_query = produtos_query.filter(id__in=produtos_com_associacao)
        except Linha.DoesNotExist:
            pass
    
    produtos = produtos_query[:20]  # Limitar resultados
    
    skus_list = []
    for produto in produtos:
        # Verificar se tem associação com a linha (se especificada)
        tem_associacao = True
        formato_associado = None
        if linha_nome:
            try:
                associacao = AssociacaoProdutoLinha.objects.get(
                    produto=produto, 
                    linha__nome=linha_nome
                )
                formato_associado = associacao.formato.nome if associacao.formato else None
            except AssociacaoProdutoLinha.DoesNotExist:
                tem_associacao = False
        
        skus_list.append({
            'codigo_sku': produto.sku,
            'descricao_sku': produto.descricao,
            'dun14': produto.dun14,
            'validade': produto.validade,
            'numero_op': produto.numero_op,
            'status_op': produto.status_op,
            'dataop': produto.dataop_str,
            'configurado_para_linha': tem_associacao,
            'formato_associado': formato_associado
        })
    
    return JsonResponse({'skus': skus_list})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trocar_sku(request):
    """
    Processa a troca de SKU para uma linha específica.
    CORRIGIDO: Agora usa o novo modelo AssociacaoProdutoLinha para validar e obter o formato.
    """
    start_total_time = time.time()
    
    try:
        # O request.data é usado com @api_view
        data = request.data
        
        # 1. VERIFICAÇÃO DE AUTORIZAÇÃO BASEADA EM GRUPO
        try:
            operadores_group = Group.objects.get(name='Operadores')
        except Group.DoesNotExist:
            return Response(
                {"mensagem": "Erro de configuração: O grupo 'Operadores' não foi encontrado no sistema."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
        if operadores_group not in request.user.groups.all():
            return Response(
                {"mensagem": "Acesso negado. Apenas usuários do grupo 'Operadores' podem realizar a troca de SKU."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 2. OBTENÇÃO DO USUÁRIO LOGADO
        usuario_logado = request.user
        
        file_logger.log_request("POST", "/trocar_sku/", request.headers, json.dumps(data))

        linha_val = data.get('linha')
        sku = data.get('sku')
        descricao = data.get('descricao', '')
        dun14 = data.get('dun14', '')
        validade = data.get('validade', '')
        codigo_sku = data.get('codigo_sku', sku)
        dia = data.get('dia', '')
        hora = data.get('hora', '')
        # usuario_id não é mais usado, o usuário é obtido do token
        # usuario_id = data.get('usuario_id', 1) 
        ip_origem = data.get('ip_origem', request.META.get('REMOTE_ADDR', ''))
        ip_origem = data.get('ip_origem', request.META.get('REMOTE_ADDR', ''))

        # Validações básicas
        if not linha_val or not sku:
            return JsonResponse({"mensagem": "Linha e SKU são obrigatórios"}, status=400)

        # Buscar ou criar linha de teste
        if linha_val == "Linha Teste":
            linha, created = Linha.objects.get_or_create(nome="Linha Teste")
            if created:
                print("Linha de teste criada automaticamente.")
        else:
            try:
                linha = Linha.objects.get(nome=linha_val)
            except Linha.DoesNotExist:
                return JsonResponse({"mensagem": f"Linha '{linha_val}' não encontrada."}, status=404)


            if not linha.ativa:
                # Retorna um erro 400 (Bad Request) informando que a linha está inativa
                # Use 'Response' do DRF, já que você está em uma @api_view
                return Response(
                    {"mensagem": f"Operação não permitida: A linha '{linha_val}' está marcada como INATIVA no sistema."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        # Buscar o produto pelo SKU
        try:
            produto = Produto.objects.get(sku=sku)
        except Produto.DoesNotExist:
            return JsonResponse({
                "mensagem": f"Produto com SKU {sku} não encontrado",
                "erros": [f"SKU {sku} não está cadastrado no sistema"]
            }, status=404)

        # 🔑 VALIDAÇÃO PRINCIPAL: Obter o formato associado ao produto e à linha específica
        try:
            associacao = AssociacaoProdutoLinha.objects.get(produto=produto, linha=linha)
            formato = associacao.formato
            
            if not formato:
                return JsonResponse({
                    "mensagem": f"Configuração incompleta: O produto SKU '{sku}' está associado à linha '{linha_val}', mas não possui formato configurado.",
                    "erros": [f"Por favor, configure um formato para este produto na linha '{linha_val}' na área de administração."]
                }, status=400)
            
            # Validação opcional do padrão de nomenclatura
            if not formato.nome.upper().endswith(f'-{linha.nome.upper()}'):
                print(f"AVISO: O formato '{formato.nome}' não corresponde ao padrão esperado para a linha '{linha.nome}'.")
                
        except AssociacaoProdutoLinha.DoesNotExist:
            return JsonResponse({
                "mensagem": f"Configuração inválida: O produto SKU '{sku}' não está configurado para rodar na linha '{linha_val}'.",
                "erros": [f"Por favor, associe um formato para este produto na linha '{linha_val}' na área de administração."]
            }, status=400)

        # ── Verificação de liberação SAP (bloqueante) ──────────────────────
        # Nenhum SKU pode ser trocado sem que um profissional do grupo SAP
        # tenha validado a lista técnica para este produto nesta linha.
        if not LiberacaoSAP.objects.filter(produto=produto, linha=linha).exists():
            return Response(
                {
                    "mensagem": (
                        f"SKU '{sku}' não possui liberação SAP para a linha '{linha_val}'. "
                        "Um profissional do grupo SAP deve validar a lista técnica antes da troca."
                    ),
                    "codigo": "sap_nao_liberado",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Verifica se este SKU já rodou com sucesso nesta linha antes desta troca
        ja_rodou_antes = TrocaSKU.objects.filter(
            linha=linha_val,
            sku_trocado=sku,
            sucesso=True
        ).exists()

        # Criar a instância de TrocaSKU
        troca = TrocaSKU(
            linha=linha_val,
            sku_trocado=sku,
            descricao=descricao,
            dun14=dun14,
            validade=validade,
            numero_op=data.get("numero_op", ""),
            usuario=usuario_logado, # Salva o objeto User
            # usuario_id=usuario_id, # Campo obsoleto, não mais usado
            ip_origem=ip_origem,
            primeira_rodada=not ja_rodou_antes,
        )
        troca.save()

        general_equipment_errors = []
        
        # ==================== PROCESSAR EQUIPAMENTOS PLC ====================
        equipamentos = linha.equipamentos.all()
        for equipamento in equipamentos:
            start_equip_time = time.time()
            
            # Obter configurações de variáveis para este equipamento
            configuracoes = ConfiguracaoEquipamentoVariavel.objects.filter(equipamento=equipamento)
            
            if not configuracoes.exists():
                erro_msg = f"[{equipamento.nome}] Nenhuma configuração de variável encontrada."
                general_equipment_errors.append(erro_msg)
                LogEquipamentoTroca.objects.create(
                    troca=troca,
                    tipo_equipamento='equipamento',
                    nome_equipamento=equipamento.nome,
                    status='nao_configurado',
                    mensagem="Nenhuma configuração de variável encontrada.",
                    erro_detalhado=erro_msg,
                    variaveis_escritas=0,
                    variaveis_total=0,
                    tempo_execucao=0,
                    ip_equipamento=None,
                    conexao_opcua=equipamento.conexao_opcua.url if equipamento.conexao_opcua else ''
                )
                continue

            valores_prioritarios = {
                # Mapeia o NOME DA VARIÁVEL MESTRA para o VALOR DO PRODUTO
                # (Adicione ou remova linhas aqui conforme sua necessidade)
                'SKU_Esperado': sku,
                "Descricao_Esperada": produto.descricao,
                'EAN_Esperado': produto.ean,     # Usa o campo 'ean' do modelo Produto
                'DUN14_Esperado': produto.dun14,  # Usa o campo 'dun14' do modelo Produto
                'Filme_Esperado': produto.filme,        # Lê o campo "Filme" do seu Produto
                'NumeroOP_Esperado': produto.numero_op  # Lê o campo "Numero op" do seu Produto
            }

            # Preparar dados das variáveis para escrita (linha 847)
            variaveis_dados = []
            variaveis_total = configuracoes.count()
            
            for config in configuracoes:
                variavel_mestra = config.variavel_mestra
                tag_plc = config.tag_plc
                valor = None

                # 2. LÓGICA DE ESCRITA LIMPA
                
                # Primeiro, tenta buscar no mapa prioritário (Produto/API)
                if variavel_mestra.nome in valores_prioritarios:
                    valor = valores_prioritarios[variavel_mestra.nome]
                    print(f"[{equipamento.nome}] INTERCEPTADO (Produto): Definindo '{variavel_mestra.nome}' para '{valor}'")
                
                # Se não, busca no mapa de Formato (lógica padrão)
                else:
                    try:
                        formato_variavel = FormatoVariavel.objects.get(
                            formato=formato,
                            variavel=variavel_mestra
                        )
                        valor = formato_variavel.valor
                    except FormatoVariavel.DoesNotExist:
                        # Pula apenas se a variável de FORMATO não for encontrada
                        print(f"[{equipamento.nome}] Variável de Formato {variavel_mestra.nome} não encontrada.")
                        continue 
                
                # 3. ADICIONA À LISTA
                if valor is not None:
                    variaveis_dados.append({
                        'variavel_obj': variavel_mestra,
                        'valor': valor,
                        'tag_plc_no_equipamento': tag_plc
                    })

            # Escrever no CLP
            plc_erros = escrever_plc(equipamento, variaveis_dados)
            tempo_execucao = time.time() - start_equip_time
            variaveis_escritas = len(variaveis_dados) - len(plc_erros)

            status_log = 'sucesso' if not plc_erros else 'falha'

            # Detalhes por variável para visualização na UI
            _erros_str = ' '.join(plc_erros)
            _variaveis_detalhes = [
                {
                    'nome': v['variavel_obj'].nome,
                    'tag_plc': v['tag_plc_no_equipamento'],
                    'valor': str(v['valor']),
                    'sucesso': v['tag_plc_no_equipamento'] not in _erros_str
                              and v['variavel_obj'].nome not in _erros_str,
                }
                for v in variaveis_dados
            ]

            LogEquipamentoTroca.objects.create(
                troca=troca,
                tipo_equipamento='equipamento',
                nome_equipamento=equipamento.nome,
                status=status_log,
                mensagem='Escrita realizada com sucesso.' if not plc_erros else 'Falha na escrita de algumas variáveis.',
                erro_detalhado='; '.join(plc_erros) if plc_erros else '',
                variaveis_escritas=variaveis_escritas,
                variaveis_total=len(variaveis_dados),
                variaveis_detalhes=_variaveis_detalhes,
                tempo_execucao=round(tempo_execucao, 2),
                ip_equipamento=None,
                conexao_opcua=equipamento.conexao_opcua.url if equipamento.conexao_opcua else ''
            )
            if plc_erros:
                general_equipment_errors.extend(plc_erros)

        # ==================== PROCESSAR IMPRESSORAS INKJET ====================
        impressoras_inkjet = linha.impressoras_inkjet.all()
        for printer in impressoras_inkjet:
            start_time = time.time()
            
            try:
                command = CommandHelper.sla_command(
                    job=printer.format_name,
                    line_number=linha_val,
                    description=descricao,
                    sku=sku,
                    dun14=dun14
                )
                
                sock_client = SocketClient(printer.ip_address, printer.port)
                sla_response = sock_client.make_request(command)
                
                if CommandHelper.sla_validation(sla_response, printer.format_name):
                    status_log = 'sucesso'
                    mensagem = 'Comando SLA enviado com sucesso.'
                    erro_detalhado = ''
                else:
                    status_log = 'falha'
                    mensagem = 'Falha na validação da resposta SLA.'
                    erro_detalhado = f'Resposta recebida: {sla_response}'
                    general_equipment_errors.append(f"[{printer.nome}] {mensagem}")
                
            except Exception as e:
                status_log = 'falha'
                mensagem = 'Erro na comunicação com a impressora Inkjet.'
                erro_detalhado = str(e)
                general_equipment_errors.append(f"[{printer.nome}] {mensagem}: {erro_detalhado}")
            
            tempo_execucao = time.time() - start_time

            LogEquipamentoTroca.objects.create(
                troca=troca,
                tipo_equipamento='impressora_inkjet',
                nome_equipamento=printer.nome,
                status=status_log,
                mensagem=mensagem,
                erro_detalhado=erro_detalhado,
                variaveis_escritas=1 if status_log == 'sucesso' else 0,
                variaveis_total=1,
                variaveis_detalhes=[{
                    'nome': 'Comando SLA',
                    'tag_plc': printer.format_name,
                    'valor': f'SKU={sku} | Desc={descricao} | DUN14={dun14}',
                    'sucesso': status_log == 'sucesso',
                }],
                tempo_execucao=round(tempo_execucao, 2),
                ip_equipamento=printer.ip_address,
                conexao_opcua=''
            )

        # ==================== PROCESSAR IMPRESSORAS 3M ====================
        impressoras_3m = linha.impressoras_3m.all()
        start_impressora_time = time.time()
        impressora_erros_list = escrever_impressora_3m(linha, codigo_sku, sku, descricao, dun14, validade, dia, hora)
        tempo_execucao_impressora = time.time() - start_impressora_time

        for impressora in impressoras_3m:
            current_impressora_errors = [e for e in impressora_erros_list if f"[{impressora.nome}]" in e]
            
            variaveis_total = 7
            variaveis_escritas = variaveis_total - len(current_impressora_errors)
            status_log_impressora = 'sucesso' if not current_impressora_errors else 'falha'
            
            _3m_detalhes = [
                {'nome': 'SKU',       'tag_plc': 'ARQ_auto.txt', 'valor': str(sku),       'sucesso': not current_impressora_errors},
                {'nome': 'Descrição', 'tag_plc': 'ARQ_auto.txt', 'valor': str(descricao),  'sucesso': not current_impressora_errors},
                {'nome': 'DUN14',     'tag_plc': 'ARQ_auto.txt', 'valor': str(dun14),      'sucesso': not current_impressora_errors},
                {'nome': 'Validade',  'tag_plc': 'ARQ_auto.txt', 'valor': str(validade),   'sucesso': not current_impressora_errors},
                {'nome': 'Dia',       'tag_plc': 'ARQ_auto.txt', 'valor': str(dia),        'sucesso': not current_impressora_errors},
                {'nome': 'Hora',      'tag_plc': 'ARQ_auto.txt', 'valor': str(hora),       'sucesso': not current_impressora_errors},
                {'nome': 'CódSKU',   'tag_plc': 'ARQ_auto.txt', 'valor': str(codigo_sku), 'sucesso': not current_impressora_errors},
            ]

            LogEquipamentoTroca.objects.create(
                troca=troca,
                tipo_equipamento='impressora_3m',
                nome_equipamento=impressora.nome,
                status=status_log_impressora,
                mensagem='Escrita realizada com sucesso.' if not current_impressora_errors else 'Falha na escrita no arquivo ARQ_auto.txt.',
                erro_detalhado='; '.join(current_impressora_errors) if current_impressora_errors else '',
                variaveis_escritas=variaveis_escritas,
                variaveis_total=variaveis_total,
                variaveis_detalhes=_3m_detalhes,
                tempo_execucao=round(tempo_execucao_impressora, 2),
                ip_equipamento=impressora.ip,
                conexao_opcua=''
            )
            if current_impressora_errors:
                general_equipment_errors.extend(current_impressora_errors)

        # Atualização final da TrocaSKU
        troca.tempo_execucao = round(time.time() - start_total_time, 2)
        troca.save()

        # Atualizar StatusLinha
        status_linha, created = StatusLinha.objects.get_or_create(linha=linha)
        status_linha.sku_atual = sku
        status_linha.descricao_sku_atual = descricao
        status_linha.data_ultima_troca = troca.data_hora
        status_linha.equipamentos_ativos = troca.equipamentos_sucesso
        status_linha.equipamentos_total = troca.equipamentos_processados
        status_linha.save()

        # ── Criar ValidacaoQualidade se for primeira rodada ────────────────
        # Isolado em try/except: falha aqui não deve reverter nem bloquear a troca.
        # O worker é quem conta as caixas e escreve no OPC ao atingir a meta.
        validacao_qualidade_iniciada = False
        if troca.primeira_rodada:
            try:
                from .models import CriterioValidacaoQualidade, HistoricoValidacaoQualidade
                # Meta de caixas do critério Formato×Linha (ou default global).
                meta_caixas = CriterioValidacaoQualidade.resolver_meta(formato, linha)

                # Cancelar validações pendentes anteriores do mesmo produto+linha
                # para garantir que só existe uma ativa por vez (o worker usará a mais recente).
                ValidacaoQualidade.objects.filter(
                    produto=produto,
                    linha=linha,
                    status=ValidacaoQualidade.StatusValidacao.PENDENTE,
                ).update(status=ValidacaoQualidade.StatusValidacao.CANCELADO)

                # meta 0 → recurso desativado p/ este Formato×Linha: não cria validação
                # (não para a linha). Registra intenção no log e segue.
                if meta_caixas and meta_caixas > 0:
                    vq_nova = ValidacaoQualidade.objects.create(
                        troca=troca,
                        produto=produto,
                        linha=linha,
                        quantidade_caixas_meta=meta_caixas,
                    )
                    HistoricoValidacaoQualidade.objects.create(
                        validacao=vq_nova,
                        evento=HistoricoValidacaoQualidade.Evento.CRIADA,
                        caixas_no_momento=0,
                        meta_caixas=meta_caixas,
                        usuario=usuario_logado,
                        observacao=f'Primeira rodada de {sku} na {linha_val}. Meta: {meta_caixas} caixas.',
                    )
                    validacao_qualidade_iniciada = True
                    print(f"[TROCAR_SKU] ValidacaoQualidade criada (meta {meta_caixas} caixas) "
                          f"para SKU '{sku}' na linha '{linha_val}'.")
                else:
                    print(f"[TROCAR_SKU] Validação por caixas desativada p/ {sku}/{linha_val} "
                          "(meta 0) — não criada.")
            except Exception as vq_err:
                # Falha silenciosa intencional: troca já foi executada.
                # Admin pode criar a validação manualmente se necessário.
                print(f"[TROCAR_SKU] AVISO: falha ao criar ValidacaoQualidade: {vq_err}")

        response_data = {
            "mensagem": "Troca realizada com sucesso!" if not general_equipment_errors else "Troca realizada com erros.",
            "sucesso": not bool(general_equipment_errors),
            "resumo_execucao": troca.get_resumo_execucao(),
            "erros": general_equipment_errors,
            "troca_id": troca.id,
            "primeira_rodada": troca.primeira_rodada,
            "validacao_qualidade_iniciada": validacao_qualidade_iniciada,
        }

        file_logger.log_response(status.HTTP_200_OK if not general_equipment_errors else status.HTTP_400_BAD_REQUEST, json.dumps(response_data))

        return Response(response_data, status=status.HTTP_200_OK if not general_equipment_errors else status.HTTP_400_BAD_REQUEST)

    except json.JSONDecodeError:
        return Response({"mensagem": "Erro ao decodificar JSON"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print("Erro geral:", traceback.format_exc())
        return Response({"mensagem": f"Erro ao processar a solicitação: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ==================== FUNÇÕES AUXILIARES ====================

def executar_funcao_django(request):
    """Função de teste"""
    try:
        linha = request.GET.get('linha', 'não especificada')
        resultado = f"Função executada com sucesso para a linha {linha}"
        print(resultado)
        return JsonResponse({'mensagem': resultado})
    except Exception as e:
        print(f"Erro ao executar a função: {e}")
        return JsonResponse({'mensagem': f"Erro ao executar a função: {e}"}, status=500)

def enviar_para_node_red(request):
    """Envia dados para Node-RED"""
    print("Iniciando envio para o Node-RED...")
    linha = request.GET.get('linha', None)
    if not linha:
        print("Linha não especificada.")
        return JsonResponse({'mensagem': 'Linha não especificada'}, status=400)
    node_red_url = "http://127.0.0.1:1880/execute"
    payload = {'message': 'Informação enviada pelo Django', 'linha': linha}
    try:
        print(f"Tentando conectar ao Node-RED na URL {node_red_url}")
        print(f"Payload enviado: {payload}")
        response = requests.post(node_red_url, json=payload, timeout=5)
        print(f"Resposta do Node-RED: {response.status_code} - {response.text}")
        if response.status_code == 200:
            print("Informação enviada para o Node-RED com sucesso!")
            return JsonResponse({'mensagem': 'Informação enviada para o Node-RED com sucesso!'})
        else:
            print(f"Erro ao enviar para o Node-RED: {response.text}")
            return JsonResponse({'mensagem': f'Erro ao enviar para o Node-RED: {response.text}'}, status=response.status_code)
    except requests.exceptions.RequestException as e:
        print(f"Erro na conexão com o Node-RED: {str(e)}")
        return JsonResponse({'mensagem': f'Erro na conexão com o Node-RED: {str(e)}'}, status=500)

@csrf_exempt
def registrar_discrepancia_sku(request):
    """Registra discrepâncias de SKU"""
    if request.method != "POST":
        return JsonResponse({'mensagem': 'Método não permitido'}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8'))
        linha = data.get('linha')
        sku_esperado = data.get('sku_esperado')
        sku_atual = data.get('sku_atual')
        if not all([linha, sku_esperado, sku_atual]):
            return JsonResponse({'mensagem': 'Dados incompletos: linha, sku_esperado e sku_atual são obrigatórios'}, status=400)
        discrepancia = DiscrepanciaSKU(linha=linha, sku_esperado=sku_esperado, sku_atual=sku_atual)
        discrepancia.save()
        return JsonResponse({'mensagem': 'Discrepância registrada com sucesso!'})
    except json.JSONDecodeError:
        return JsonResponse({'mensagem': 'Erro ao decodificar JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'mensagem': f'Erro ao processar a solicitação: {str(e)}'}, status=500)

# ==================== FUNÇÕES DE SINCRONIZAÇÃO ====================

def get_lista_op(linha=None):
    """Obtém lista de OPs do web service SOAP"""
    url = "http://192.168.30.42:82/WsOffLineCom.asmx?op=GetListaOP"
    
    #url =  "http://localhost:5003/GetListaOP"
   

    linha_producao = linha + "IP" if linha else ""
    headers = {"Content-Type": "text/xml"}
    envelope = f'''<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                             xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                             xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <GetListaOP xmlns="http://www.aplipack.com.br/">
      <UserSoftware>test</UserSoftware>
      <PasswordSoftware>1234</PasswordSoftware>
      <LinhaProducao>{linha_producao}</LinhaProducao>
    </GetListaOP>
  </soap12:Body>
</soap12:Envelope>'''
    try:
        response = requests.post(url, data=envelope, headers=headers, timeout=10)
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Erro ao conectar ao web service SOAP: {e}")
        return None

def parse_soap_response(xml_string):
    """Faz parse da resposta SOAP"""
    if not xml_string:
        return None, None
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError:
        return None, None
    status_elem = root.find('.//xStatus')
    json_elem = root.find('.//xListaJSON')
    if status_elem is None or json_elem is None:
        ns = {'apli': 'http://www.aplipack.com.br/'}
        status_elem = root.find('.//apli:xStatus', ns) if status_elem is None else status_elem
        json_elem = root.find('.//apli:xListaJSON', ns) if json_elem is None else json_elem
    status = status_elem.text if status_elem is not None else None
    json_data = json_elem.text if json_elem is not None else None
    return status, json_data

def convert_unix_timestamp(dataop_raw):
    """Converte timestamp Unix para datetime"""
    try:
        start = dataop_raw.find("(")
        end = dataop_raw.find(")")
        if start == -1 or end == -1:
            return None
        ts_str = dataop_raw[start+1:end]
        ts = int(ts_str)
        return datetime.utcfromtimestamp(ts / 1000)
    except (ValueError, TypeError):
        return None

def orders_view(request):
    """View para exibir ordens de produção"""
    soap_response = get_lista_op()
    if soap_response is None:
        return HttpResponse("Erro ao conectar com o web service SOAP.", status=500)
    status_val, lista_json = parse_soap_response(soap_response)
    if status_val is None:
        return HttpResponse("Erro: xStatus não encontrado na resposta SOAP.", status=500)
    if status_val == "-1":
        error_elem = ET.fromstring(soap_response).find('.//xErro')
        error_msg = error_elem.text if error_elem is not None else "Erro desconhecido"
        return HttpResponse(f"Erro: {error_msg}", status=500)
    if lista_json is None:
        return HttpResponse("Erro: xListaJSON não encontrado na resposta SOAP.", status=500)
    orders = []
    try:
        data = json.loads(lista_json)
        for ordem in data.get("OrdensProducao", []):
            codigo_sku = ordem.get("CodigoSKU")
            descricao_sku = ordem.get("DescricaoSKU")
            dataop_raw = ordem.get("DataOP")
            dataop_dt = convert_unix_timestamp(dataop_raw)
            dataop_str = dataop_dt.strftime("%d/%m/%Y %H:%M:%S") if dataop_dt else "Data inválida"
            orders.append({
                "codigo_sku": codigo_sku,
                "descricao_sku": descricao_sku,
                "dataop": dataop_str,
                "id_ordem_prod": ordem.get("IdOrdemProd"),
                "numero_op": ordem.get("NumeroOP"),
                "dun14": ordem.get("DUN14"),
                "validade": ordem.get("Validade"),
                "quantidade_por_pallet": ordem.get("QuantidadePorPallet"),
                "status_op": ordem.get("StatusOP")
            })
    except json.JSONDecodeError:
        return HttpResponse("Erro ao decodificar JSON da resposta SOAP.", status=500)
    context = {'orders': orders}
    return render(request, 'orders.html', context)

# 🔧 FUNÇÃO ORIGINAL DE SINCRONIZAÇÃO - COPIADA EXATAMENTE DO ARQUIVO FUNCIONAL
def get_skus_aplipack(request):
    """
    🔑 FUNÇÃO ORIGINAL QUE FUNCIONAVA - Copiada exatamente do arquivo funcional
    Obtém SKUs do sistema Aplipack via web service SOAP e salva no banco de dados
    """
    print(f"[GET_SKUS_APLIPACK] Iniciando função original...")
    print(f"[GET_SKUS_APLIPACK] Método: {request.method}")
    print(f"[GET_SKUS_APLIPACK] GET params: {dict(request.GET)}")
    
    linha_nome = request.GET.get('linha', '')
    if not linha_nome:
        print("[GET_SKUS_APLIPACK] ERRO: Parâmetro 'linha' não especificado")
        return JsonResponse({'mensagem': 'Parâmetro linha é obrigatório'}, status=400)
    
    print(f"[GET_SKUS_APLIPACK] Processando linha: {linha_nome}")
    
    try:
        linha = Linha.objects.get(nome=linha_nome)
        print(f"[GET_SKUS_APLIPACK] Linha encontrada: {linha}")
    except Linha.DoesNotExist:
        print(f"[GET_SKUS_APLIPACK] ERRO: Linha '{linha_nome}' não encontrada")
        return JsonResponse({'mensagem': f'Linha {linha_nome} não encontrada.'}, status=404)
    
    # Consultar web service SOAP
    print(f"[GET_SKUS_APLIPACK] Consultando web service SOAP...")
    soap_response = get_lista_op(linha=linha_nome)
    if soap_response is None:
        print("[GET_SKUS_APLIPACK] ERRO: Falha ao conectar com web service SOAP")
        return JsonResponse({'mensagem': 'Erro ao conectar com o web service SOAP.'}, status=500)

    status_val, lista_json = parse_soap_response(soap_response)
    if status_val is None:
        print("[GET_SKUS_APLIPACK] ERRO: xStatus não encontrado na resposta SOAP")
        return JsonResponse({'mensagem': 'Erro: xStatus não encontrado na resposta SOAP.'}, status=500)
    if status_val == "-1":
        error_elem = ET.fromstring(soap_response).find('.//xErro')
        error_msg = error_elem.text if error_elem is not None else "Erro desconhecido"
        print(f"[GET_SKUS_APLIPACK] ERRO SOAP: {error_msg}")
        return JsonResponse({'mensagem': f'Erro: {error_msg}'}, status=500)
    if lista_json is None:
        print("[GET_SKUS_APLIPACK] ERRO: xListaJSON não encontrado na resposta SOAP")
        return JsonResponse({'mensagem': 'Erro: xListaJSON não encontrado na resposta SOAP.'}, status=500)

    print(f"[GET_SKUS_APLIPACK] Status SOAP: {status_val}")
    print(f"[GET_SKUS_APLIPACK] JSON recebido (primeiros 200 chars): {lista_json[:200]}...")

    # Processar dados JSON
    skus_aplipack = []
    try:
        data = json.loads(lista_json)
        ordens_producao = data.get("OrdensProducao", [])
        print(f"[GET_SKUS_APLIPACK] Total de ordens encontradas: {len(ordens_producao)}")

        # Busca em uma única query todos os SKUs que já rodaram com sucesso nesta linha
        skus_que_ja_rodaram = set(
            TrocaSKU.objects.filter(linha=linha_nome, sucesso=True)
            .values_list('sku_trocado', flat=True)
            .distinct()
        )
        print(f"[GET_SKUS_APLIPACK] SKUs com histórico nesta linha: {len(skus_que_ja_rodaram)}")

        for i, ordem in enumerate(ordens_producao):
            codigo_sku = ordem.get("CodigoSKU")
            descricao_sku = ordem.get("DescricaoSKU")
            dataop_raw = ordem.get("DataOP", "")
            dt = convert_unix_timestamp(dataop_raw)
            dataop = dt.strftime("%d/%m/%Y %H:%M:%S") if dt else ""
            id_ordem_prod = ordem.get("IdOrdemProd")
            numero_op = ordem.get("NumeroOP")
            dun14 = ordem.get("DUN14")
            validade = ordem.get("Validade")
            quantidade_por_pallet = ordem.get("QuantidadePorPallet")
            status_op = ordem.get("StatusOP")

            print(f"[GET_SKUS_APLIPACK] Processando ordem {i+1}/{len(ordens_producao)}: {codigo_sku}")

            skus_aplipack.append({
                "codigo_sku": codigo_sku,
                "descricao_sku": descricao_sku,
                "dataop": dataop,
                "id_ordem_prod": id_ordem_prod,
                "numero_op": numero_op,
                "dun14": dun14,
                "validade": validade,
                "quantidade_por_pallet": quantidade_por_pallet,
                "status_op": status_op,
                "ja_rodou_nesta_linha": codigo_sku in skus_que_ja_rodaram,
            })
    except json.JSONDecodeError as e:
        print(f"[GET_SKUS_APLIPACK] ERRO JSON: {str(e)}")
        return JsonResponse({'mensagem': f'Erro ao processar os dados JSON: {str(e)}'}, status=500)

    # 🔑 SINCRONIZAR PRODUTOS (EXATAMENTE COMO NO ORIGINAL FUNCIONAL)
    produtos_criados = 0
    produtos_atualizados = 0
    associacoes_criadas = 0
    
    print(f"[GET_SKUS_APLIPACK] Iniciando sincronização de {len(skus_aplipack)} produtos...")
    
    for sku_data in skus_aplipack:
        codigo_sku = sku_data.get('codigo_sku')
        descricao_sku = sku_data.get('descricao_sku')
        dun14 = sku_data.get('dun14', '')
        validade = sku_data.get('validade', '')
        dataop = sku_data.get('dataop', '')
        id_ordem_prod = sku_data.get('id_ordem_prod', '')
        numero_op = sku_data.get('numero_op', '')
        quantidade_por_pallet = sku_data.get('quantidade_por_pallet', '')
        status_op = sku_data.get('status_op', '')

        if not codigo_sku or not descricao_sku:
            print(f"[GET_SKUS_APLIPACK] SKU ignorado devido a dados incompletos: {sku_data}")
            continue

        # 🔑 CRIAR/ATUALIZAR PRODUTO (EXATAMENTE COMO NO ORIGINAL FUNCIONAL)
        produto, created = Produto.objects.get_or_create(
            sku=codigo_sku,
            defaults={
                'descricao': descricao_sku,
                'dun14': dun14,
                'validade': validade,
                'dataop_str': dataop,
                'id_ordem_prod': id_ordem_prod,
                'numero_op': numero_op,
                'quantidade_por_pallet': quantidade_por_pallet,
                'status_op': status_op
            }
        )
        
        if created:
            produtos_criados += 1
            print(f"[GET_SKUS_APLIPACK] ✅ Produto CRIADO: {produto.sku} - {produto.descricao}")
        else:
            # Atualizar produto existente (EXATAMENTE COMO NO ORIGINAL FUNCIONAL)
            if (produto.descricao != descricao_sku or
                produto.dun14 != dun14 or
                produto.validade != validade or
                produto.dataop_str != dataop or
                produto.id_ordem_prod != id_ordem_prod or
                produto.numero_op != numero_op or
                produto.quantidade_por_pallet != quantidade_por_pallet or
                produto.status_op != status_op):
                
                produto.descricao = descricao_sku
                produto.dun14 = dun14
                produto.validade = validade
                produto.dataop_str = dataop
                produto.id_ordem_prod = id_ordem_prod
                produto.numero_op = numero_op
                produto.quantidade_por_pallet = quantidade_por_pallet
                produto.status_op = status_op
                produto.save()
                produtos_atualizados += 1
                print(f"[GET_SKUS_APLIPACK] ✅ Produto ATUALIZADO: {produto.sku} - {produto.descricao}")

        # 🔑 ASSOCIAR À LINHA (ADAPTADO PARA NOVO MODELO)
        # No original funcional era: produto.linhas.add(linha)
        # Agora usamos: AssociacaoProdutoLinha
        associacao, associacao_created = AssociacaoProdutoLinha.objects.get_or_create(
            produto=produto,
            linha=linha,
            defaults={
                'formato': None  # Será configurado manualmente no admin
            }
        )
        
        if associacao_created:
            associacoes_criadas += 1
            print(f"[GET_SKUS_APLIPACK] ✅ Associação CRIADA: {produto.sku} -> {linha.nome}")
        else:
            print(f"[GET_SKUS_APLIPACK] ℹ️ Associação já existe: {produto.sku} -> {linha.nome}")

    # Relatório final
    print(f"[GET_SKUS_APLIPACK] ✅ CONCLUÍDA!")
    print(f"[GET_SKUS_APLIPACK] - Produtos criados: {produtos_criados}")
    print(f"[GET_SKUS_APLIPACK] - Produtos atualizados: {produtos_atualizados}")
    print(f"[GET_SKUS_APLIPACK] - Associações criadas: {associacoes_criadas}")
    print(f"[GET_SKUS_APLIPACK] - Total de SKUs retornados: {len(skus_aplipack)}")

    # Retornar resposta (EXATAMENTE COMO NO ORIGINAL FUNCIONAL)
    return JsonResponse({'skus': skus_aplipack}, status=200)

# Função de sincronização que chama a original
def sincronizar_skus(request):
    """
    Função de sincronização que chama a função original get_skus_aplipack
    """
    print("[SINCRONIZAR_SKUS] Redirecionando para get_skus_aplipack...")
    return get_skus_aplipack(request)

# ==================== VIEWS DE TESTE ====================

def send_sku(request):
    """View de teste para envio de SKU"""
    return HttpResponse("Envio Executado", status=200)

def test_skus(request):
    """Retorna SKUs de teste"""
    skus_teste = [
        {
            "codigo_sku": "1111111111",
            "descricao_sku": "Produto Teste 1",
            "dataop": "01/01/2025 08:00:00",
            "id_ordem_prod": "123",
            "numero_op": "OP001",
            "dun14": "DUN001",
            "validade": "31/12/2025",
            "quantidade_por_pallet": "100",
            "status_op": "Ativa"
        },
        {
            "codigo_sku": "2222222222",
            "descricao_sku": "Produto Teste 2",
            "dataop": "02/01/2025 09:00:00",
            "id_ordem_prod": "124",
            "numero_op": "OP002",
            "dun14": "DUN002",
            "validade": "31/12/2025",
            "quantidade_por_pallet": "200",
            "status_op": "Inativa"
        }
    ]
    return JsonResponse({"skus": skus_teste})

def test_skus_page(request):
    """Página de teste para SKUs"""
    linha = {'nome': 'Linha Teste'}
    ultimas_trocas = []
    test_skus = [
        {
            "codigo_sku": "1111111111",
            "descricao_sku": "Produto Teste 1",
            "dataop": "01/01/2025 08:00:00",
            "id_ordem_prod": "123",
            "numero_op": "OP001",
            "dun14": "DUN001",
            "validade": "31/12/2025",
            "quantidade_por_pallet": "100",
            "status_op": "Ativa"
        },
        {
            "codigo_sku": "2222222222",
            "descricao_sku": "Produto Teste 2",
            "dataop": "02/01/2025 09:00:00",
            "id_ordem_prod": "124",
            "numero_op": "OP002",
            "dun14": "DUN002",
            "validade": "31/12/2025",
            "quantidade_por_pallet": "200",
            "status_op": "Inativa"
        }
    ]
    context = {
        'linha': linha,
        'ultimas_trocas': ultimas_trocas,
        'skus': test_skus,
    }
    return render(request, 'linha_detalhes_test.html', context)

def api_health(request):
    """Health check da API"""
    try:
        return JsonResponse({
            'status': 'healthy',
            'service': 'Django API',
            'timestamp': datetime.now().isoformat(),
            'message': 'Django está funcionando corretamente'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'service': 'Django API',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, status=500)

class OPCCoordinatorConfigView(APIView):
    # Endpoint service-to-service (consumido pelo mis-recipe-intelligent e pelo
    # Flask OPC Unified legado). NÃO usar autenticação JWT — esses serviços
    # não têm usuário humano. A configuração OPC é informação não-sensível.
    permission_classes = []  # service-to-service (recipe-monitor)
    """
    Endpoint para o serviço Flask OPC Unified.
    Retorna a configuração completa das linhas, equipamentos e variáveis OPC UA ativas.
    """
    def get(self, request, *args, **kwargs):
        # Filtra apenas as linhas ativas, se desejar
        linhas = Linha.objects.filter(ativa=True)
        # Prefetch_related para otimizar queries e evitar N+1 problems
        linhas = linhas.prefetch_related(
            'equipamentos__conexao_opcua', # Prefetch a conexão OPC de cada equipamento
            'equipamentos__configuracoes_variaveis__variavel_mestra' # Prefetch as variáveis mestras das configurações
        ).all()

        serializer = LinhaOPCConfigSerializer(linhas, many=True)
        
        response_data = {
            "linhas_configuracoes": serializer.data
        }
        return Response(response_data, status=status.HTTP_200_OK)

from rest_framework import viewsets
from .models import Controle, IntertravamentoLinha, HistoricoIntertravamento
from .serializers import (
    ControleSerializer, IntertravamentoLinhaSerializer,
    HistoricoIntertravamentoSerializer
)
from .permissions import PodeAlterarIntertravamento

# ==================== VIEWS PARA INTERTRAVAMENTOS ====================

class ControleViewSet(viewsets.ModelViewSet):
    queryset = Controle.objects.all()
    serializer_class = ControleSerializer
    permission_classes = [PodeAlterarIntertravamento]
    
    def get_queryset(self):
        qs = super().get_queryset()
        area = self.request.query_params.get('area')
        if area:
            qs = qs.filter(area=area)
        return qs

from rest_framework.decorators import action

class IntertravamentoLinhaViewSet(viewsets.ModelViewSet):
    queryset = IntertravamentoLinha.objects.select_related(
        'controle', 'linha', 'conexao_opcua', 'modificado_por'
    ).all()
    serializer_class = IntertravamentoLinhaSerializer
    permission_classes = [PodeAlterarIntertravamento]

    def get_queryset(self):
        qs = super().get_queryset()
        linha = self.request.query_params.get('linha')
        area  = self.request.query_params.get('area')
        if linha:
            qs = qs.filter(Q(linha__nome=linha))
        if area:
            qs = qs.filter(controle__area=area)
        return qs

    @action(detail=False, methods=['get'], url_path='por-linha/(?P<linha_nome>[^/.]+)')
    def por_linha(self, request, linha_nome=None):
        """
        Retorna intertravamentos de uma linha agrupados por área.
        """
        qs = self.get_queryset().filter(Q(linha__nome=linha_nome))
        
        resultado = {}
        from .models import Controle
        areas = [choice[0] for choice in Controle._meta.get_field('area').choices]
        for area in areas:
            itens = qs.filter(controle__area=area)
            resultado[area] = IntertravamentoLinhaSerializer(itens, many=True).data
        
        return Response(resultado)

    @action(detail=False, methods=['get'], url_path='status-summary')
    def status_summary(self, request):
        """
        Retorna contadores agregados para o badge.
        """
        linha = request.query_params.get('linha')
        qs = self.get_queryset()
        if linha:
            qs = qs.filter(Q(linha__nome=linha))
        
        total = qs.count()
        opc_offline = qs.filter(estado_opc=False).count()
        desabilitados = qs.filter(habilitado_software=False).count()
        
        # Bypass detectado (Software ON, PLC OFF)
        bypassed_offline = qs.filter(habilitado_software=True, estado_opc=False).count()
        
        criticos_offline = qs.filter(
            Q(estado_opc=False) | Q(habilitado_software=False),
            controle__critico=True
        ).count()
        
        return Response({
            'total': total,
            'habilitados': qs.filter(habilitado_software=True, estado_opc=True).count(),
            'desabilitados_manual': desabilitados,
            'opc_offline': opc_offline,
            'criticos_offline': criticos_offline,
            'bypassed_offline': bypassed_offline
        })

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """
        Liga/desliga o habilitado_software do intertravamento.
        """
        intertravamento = self.get_object()
        
        novo_estado = request.data.get('habilitado')
        observacao  = request.data.get('observacao', '').strip()
        
        if novo_estado is None:
            return Response({'detail': 'Campo "habilitado" obrigatório.'}, status=400)
        if not observacao:
            return Response({'detail': 'Campo "observacao" obrigatório para alterações manuais.'}, status=400)
        
        valor_anterior = intertravamento.habilitado_software
        novo_estado_bool = bool(novo_estado)
        
        if valor_anterior == novo_estado_bool:
            return Response({'detail': 'Estado já é o solicitado.'}, status=400)
        
        intertravamento.habilitado_software = novo_estado_bool
        intertravamento.modificado_por = request.user
        intertravamento.save(update_fields=['habilitado_software', 'modificado_por', 'modificado_em'])

        # ── Escrever no CLP via OPC UA ─────────────────────────────────────
        opc_obs = ''
        if intertravamento.conexao_opcua and intertravamento.node_id_tag:
            from .services import write_opc_node
            ok, err = write_opc_node(
                intertravamento.conexao_opcua.url,
                intertravamento.node_id_tag,
                novo_estado_bool
            )
            if ok:
                # Confirmar estado_opc com o valor escrito
                intertravamento.estado_opc = novo_estado_bool
                intertravamento.save(update_fields=['estado_opc'])
                opc_obs = ' | OPC: escrito com sucesso'
            else:
                opc_obs = f' | OPC: falha na escrita ({err})'
                import logging
                logging.getLogger(__name__).warning(
                    f"Falha ao escrever OPC {intertravamento.node_id_tag}: {err}"
                )

        HistoricoIntertravamento.objects.create(
            intertravamento=intertravamento,
            campo='habilitado_software',
            valor_anterior=valor_anterior,
            valor_novo=novo_estado_bool,
            origem='MANUAL',
            usuario=request.user,
            observacao=observacao + opc_obs
        )

        return Response(IntertravamentoLinhaSerializer(intertravamento).data)

    @action(detail=True, methods=['post'])
    def resync(self, request, pk=None):
        """
        Reenvia o valor atual de habilitado_software ao CLP via OPC UA.
        Usado para sincronizar quando o CLP foi alterado localmente (bypass).
        """
        intertravamento = self.get_object()

        if not intertravamento.conexao_opcua or not intertravamento.node_id_tag:
            return Response({'detail': 'Sem conexão OPC configurada para este intertravamento.'}, status=400)

        from .services import write_opc_node
        valor_atual = intertravamento.habilitado_software
        ok, err = write_opc_node(
            intertravamento.conexao_opcua.url,
            intertravamento.node_id_tag,
            valor_atual
        )

        if ok:
            intertravamento.estado_opc = valor_atual
            intertravamento.save(update_fields=['estado_opc'])
            HistoricoIntertravamento.objects.create(
                intertravamento=intertravamento,
                campo='estado_opc',
                valor_anterior=not valor_atual,
                valor_novo=valor_atual,
                origem='MANUAL',
                usuario=request.user,
                observacao='Sincronização forçada: reenvio do estado habilitado_software ao CLP.'
            )
            return Response(IntertravamentoLinhaSerializer(intertravamento).data)
        else:
            return Response({'detail': f'Falha ao escrever no CLP: {err}'}, status=502)

    @action(detail=True, methods=['get'])
    def historico(self, request, pk=None):
        intertravamento = self.get_object()
        qs = intertravamento.historico.order_by('-timestamp')
        per_page = min(int(request.query_params.get('per_page', 20)), 100)
        page     = max(int(request.query_params.get('page', 1)), 1)
        total    = qs.count()
        total_pages = max((total + per_page - 1) // per_page, 1)
        page    = min(page, total_pages)
        offset  = (page - 1) * per_page
        items   = qs[offset: offset + per_page]
        return Response({
            'results':     HistoricoIntertravamentoSerializer(items, many=True).data,
            'page':        page,
            'per_page':    per_page,
            'total_pages': total_pages,
            'total':       total,
        })


# ==================== VALIDAÇÕES v9.0 ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def validacoes_pipeline(request):
    """
    GET /api/validacoes/?linha=L09
    Retorna o pipeline SAP → Qualidade → Liberado para todos os SKUs
    associados à linha, ordenados por situação mais crítica primeiro.
    """
    linha_nome = request.query_params.get('linha')
    if not linha_nome:
        return Response({'detail': 'Parâmetro ?linha= obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        linha = Linha.objects.get(nome=linha_nome)
    except Linha.DoesNotExist:
        return Response({'detail': f"Linha '{linha_nome}' não encontrada."}, status=status.HTTP_404_NOT_FOUND)

    # Todos os produtos associados a esta linha
    associacoes = AssociacaoProdutoLinha.objects.filter(linha=linha).select_related('produto')

    # Liberações SAP desta linha
    sap_map = {
        lib.produto_id: lib
        for lib in LiberacaoSAP.objects.filter(linha=linha).select_related('liberado_por')
    }

    # ValidacaoQualidade ativas (pendente ou expirado) — ascending so newest overwrites in dict
    validacoes_ativas = {
        vq.produto_id: vq
        for vq in ValidacaoQualidade.objects.filter(
            linha=linha,
            status__in=[
                ValidacaoQualidade.StatusValidacao.PENDENTE,
                ValidacaoQualidade.StatusValidacao.EXPIRADO,
            ]
        ).select_related('aprovado_por').order_by('produto_id', 'criada_em')
    }
    # Aprovadas mais recentes — ascending so newest overwrites in dict
    validacoes_aprovadas = {
        vq.produto_id: vq
        for vq in ValidacaoQualidade.objects.filter(
            linha=linha,
            status=ValidacaoQualidade.StatusValidacao.APROVADO,
        ).select_related('aprovado_por').order_by('produto_id', 'aprovado_em')
    }

    resultado = []
    for assoc in associacoes:
        produto = assoc.produto
        sap_lib = sap_map.get(produto.id)
        vq_ativa = validacoes_ativas.get(produto.id)
        vq_aprovada = validacoes_aprovadas.get(produto.id)

        sap_info = None
        if sap_lib:
            sap_info = {
                'liberado_por': sap_lib.liberado_por.get_full_name() or sap_lib.liberado_por.username,
                'liberado_em': sap_lib.liberado_em.isoformat(),
                'observacao': sap_lib.observacao,
            }

        qualidade_info = None
        vq = vq_ativa or vq_aprovada
        if vq:
            qualidade_info = {
                'id': vq.id,
                'status': vq.status,
                'status_display': vq.get_status_display(),
                # Critério por CAIXAS (v11.0)
                'quantidade_caixas_meta': vq.quantidade_caixas_meta,
                'caixas_produzidas': vq.caixas_produzidas,
                'caixas_restantes': vq.caixas_restantes,
                'percentual_caixas': vq.percentual_caixas,
                'meta_atingida': vq.meta_atingida,
                'caixas_na_aprovacao': vq.caixas_na_aprovacao,
                'observacao_qualidade': vq.observacao_qualidade,
                # Legado (tempo) — mantido por compatibilidade
                'prazo_minutos': vq.prazo_minutos,
                'tempo_acumulado_s': vq.tempo_producao_acumulado_s,
                'tempo_restante_s': vq.tempo_restante_s,
                'percentual_consumido': vq.percentual_consumido,
                'aprovado_por': (
                    vq.aprovado_por.get_full_name() or vq.aprovado_por.username
                ) if vq.aprovado_por else None,
                'aprovado_em': vq.aprovado_em.isoformat() if vq.aprovado_em else None,
                'criada_em': vq.criada_em.isoformat(),
            }

        # Determinar etapa atual do pipeline
        if not sap_lib:
            etapa = 'aguarda_sap'
        elif vq_ativa:
            etapa = 'aguarda_qualidade'
        elif vq_aprovada:
            etapa = 'liberado'
        else:
            # SAP ok mas nunca precisou de qualidade (ou ainda não iniciou)
            etapa = 'sap_ok'

        resultado.append({
            'sku': produto.sku,
            'descricao': produto.descricao,
            'produto_id': produto.id,
            'etapa': etapa,
            'sap': sap_info,
            'qualidade': qualidade_info,
        })

    # Ordenar: aguarda_sap > aguarda_qualidade > sap_ok > liberado
    ordem = {'aguarda_sap': 0, 'aguarda_qualidade': 1, 'sap_ok': 2, 'liberado': 3}
    resultado.sort(key=lambda x: ordem.get(x['etapa'], 99))

    return Response({'linha': linha_nome, 'pipeline': resultado})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validacoes_sap_liberar(request):
    """
    POST /api/validacoes/sap/liberar/
    Body: { "sku": "...", "linha": "...", "observacao": "..." }
    Requer grupo SAP.
    Cria ou retorna existente LiberacaoSAP para produto+linha.
    """
    grupos_usuario = set(request.user.groups.values_list('name', flat=True))
    if not grupos_usuario & {'SAP', 'Engenheiro'}:
        return Response(
            {'detail': 'Acesso negado. Apenas SAP ou Engenheiro podem liberar.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    sku = request.data.get('sku', '').strip()
    linha_nome = request.data.get('linha', '').strip()
    observacao = request.data.get('observacao', '').strip()

    if not sku or not linha_nome:
        return Response({'detail': 'sku e linha são obrigatórios.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        produto = Produto.objects.get(sku=sku)
    except Produto.DoesNotExist:
        return Response({'detail': f"SKU '{sku}' não encontrado."}, status=status.HTTP_404_NOT_FOUND)

    try:
        linha = Linha.objects.get(nome=linha_nome)
    except Linha.DoesNotExist:
        return Response({'detail': f"Linha '{linha_nome}' não encontrada."}, status=status.HTTP_404_NOT_FOUND)

    lib, criada = LiberacaoSAP.objects.get_or_create(
        produto=produto,
        linha=linha,
        defaults={'liberado_por': request.user, 'observacao': observacao},
    )

    return Response({
        'criada': criada,
        'sku': produto.sku,
        'linha': linha.nome,
        'liberado_por': lib.liberado_por.get_full_name() or lib.liberado_por.username,
        'liberado_em': lib.liberado_em.isoformat(),
        'observacao': lib.observacao,
    }, status=status.HTTP_201_CREATED if criada else status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def status_produto(request, linha_nome):
    """
    GET /api/status-produto/<linha_nome>/
    Lê tags OPC da linha em tempo real e retorna KPIs ISA 101.
    Se o servidor OPC não estiver configurado ou inacessível, retorna nulls
    para os campos de OPC mas nunca retorna erro 5xx.
    """
    try:
        linha = Linha.objects.select_related(
            'conexao_opc_status'
        ).prefetch_related('equipamentos__conexao_opcua').get(nome=linha_nome)
    except Linha.DoesNotExist:
        return Response({'detail': f"Linha '{linha_nome}' não encontrada."}, status=status.HTTP_404_NOT_FOUND)

    agora = timezone.now()
    opc_configurado = bool(linha.conexao_opc_status and linha.tag_status_linha_opc)

    # Valores padrão (nulos)
    kpis = {
        'sku_atual': None,
        'status_codigo': None,
        'status_label': None,
        'velocidade': None,
        'giveaway': None,
        'descarte_turno': None,
        'peso_medio': None,
        'caixas_turno': None,
        'toneladas_turno': None,
    }

    if opc_configurado:
        from opcua import Client as OPCClient
        _TAG_MAP = {
            'status_codigo':    linha.tag_status_linha_opc,
            'sku_atual':        linha.tag_sku_atual_opc,
            'velocidade':       linha.tag_velocidade_opc,
            'giveaway':         linha.tag_giveaway_opc,
            'descarte_turno':   linha.tag_descarte_turno_opc,
            'peso_medio':       linha.tag_peso_medio_opc,
            'caixas_turno':     linha.tag_caixas_turno_opc,
        }
        client = OPCClient(linha.conexao_opc_status.url, timeout=3)
        try:
            client.connect()
            for campo, tag in _TAG_MAP.items():
                if not tag:
                    continue
                try:
                    val = client.get_node(tag).get_value()
                    kpis[campo] = val
                except Exception:
                    pass
        except Exception:
            opc_configurado = False  # servidor inacessível
        finally:
            try:
                client.disconnect()
            except Exception:
                pass

    # Normalizar status_codigo
    STATUS_LABELS = {10: 'Rodando', 20: 'Aguardando', 30: 'Bloqueado', 40: 'Falha'}
    if kpis['status_codigo'] is not None:
        try:
            kpis['status_codigo'] = int(kpis['status_codigo'])
            kpis['status_label'] = STATUS_LABELS.get(kpis['status_codigo'], str(kpis['status_codigo']))
        except (TypeError, ValueError):
            kpis['status_codigo'] = None

    # Normalizar strings
    if kpis['sku_atual'] is not None:
        kpis['sku_atual'] = str(kpis['sku_atual']).strip() or None

    # Calcular toneladas_turno = caixas × formato.gramas / 1_000_000
    if kpis['caixas_turno'] is not None and kpis['sku_atual']:
        try:
            assoc = AssociacaoProdutoLinha.objects.select_related('formato').get(
                produto__sku=kpis['sku_atual'], linha=linha
            )
            if assoc.formato and assoc.formato.gramas:
                kpis['toneladas_turno'] = round(
                    float(kpis['caixas_turno']) * assoc.formato.gramas / 1_000_000, 3
                )
        except AssociacaoProdutoLinha.DoesNotExist:
            pass
        except Exception:
            pass

    # Validação de qualidade ativa para esta linha
    validacao_info = None
    try:
        vq = (
            ValidacaoQualidade.objects
            .filter(
                linha=linha,
                status__in=[
                    ValidacaoQualidade.StatusValidacao.PENDENTE,
                    ValidacaoQualidade.StatusValidacao.EXPIRADO,
                ]
            )
            .select_related('produto')
            .order_by('-criada_em')
            .first()
        )
        if vq:
            validacao_info = {
                'id': vq.id,
                'sku': vq.produto.sku,
                'status': vq.status,
                'status_display': vq.get_status_display(),
                'prazo_minutos': vq.prazo_minutos,
                'tempo_acumulado_s': vq.tempo_producao_acumulado_s,
                'tempo_restante_s': vq.tempo_restante_s,
                'percentual_consumido': vq.percentual_consumido,
            }
    except Exception:
        pass

    # Floats: garantir serialização limpa
    for campo in ('giveaway', 'descarte_turno', 'peso_medio', 'caixas_turno', 'velocidade', 'toneladas_turno'):
        if kpis[campo] is not None:
            try:
                kpis[campo] = round(float(kpis[campo]), 2)
            except (TypeError, ValueError):
                kpis[campo] = None

    return Response({
        'linha': linha_nome,
        'opc_configurado': opc_configurado,
        'timestamp': agora.isoformat(),
        **kpis,
        'validacao_qualidade': validacao_info,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ultima_troca(request, linha_nome):
    """
    GET /api/ultima-troca/<linha>/
    Retorna a última TrocaSKU da linha com os logs de equipamentos e suas variáveis detalhadas.
    Usado pela tela de Status do Produto para exibir variáveis enviadas na última troca.
    """
    try:
        linha = Linha.objects.get(nome=linha_nome)
    except Linha.DoesNotExist:
        return Response({'detail': f"Linha '{linha_nome}' não encontrada."}, status=status.HTTP_404_NOT_FOUND)

    troca = (
        TrocaSKU.objects
        .filter(linha=linha_nome)
        .prefetch_related('logs_equipamentos')
        .order_by('-data_hora')
        .first()
    )

    if not troca:
        return Response({'troca': None})

    logs = []
    for log in troca.logs_equipamentos.all():
        logs.append({
            'tipo_equipamento': log.tipo_equipamento,
            'nome_equipamento': log.nome_equipamento,
            'status': log.status,
            'mensagem': log.mensagem,
            'variaveis_escritas': log.variaveis_escritas,
            'variaveis_total': log.variaveis_total,
            'variaveis_detalhes': log.variaveis_detalhes,
            'tempo_execucao': log.tempo_execucao,
            'ip_equipamento': log.ip_equipamento,
        })

    return Response({
        'troca': {
            'id': troca.id,
            'sku': troca.sku_trocado,
            'descricao': troca.descricao,
            'data_hora': troca.data_hora.isoformat(),
            'sucesso': troca.sucesso,
            'primeira_rodada': troca.primeira_rodada,
            'equipamentos_processados': troca.equipamentos_processados,
            'equipamentos_sucesso': troca.equipamentos_sucesso,
            'tempo_execucao': troca.tempo_execucao,
        },
        'logs': logs,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validacoes_qualidade_engenheiro_aprovar(request):
    """
    POST /api/validacoes/qualidade/engenheiro-aprovar/
    Body: { "sku": "...", "linha": "..." }
    Requer grupo Engenheiro. Cria ValidacaoQualidade se não existe e aprova imediatamente.
    """
    user_groups_eng = set(request.user.groups.values_list('name', flat=True))
    if 'Engenheiro' not in user_groups_eng:
        return Response({'detail': 'Acesso negado. Apenas Engenheiro pode usar este bypass.'}, status=status.HTTP_403_FORBIDDEN)

    sku = request.data.get('sku', '').strip()
    linha_nome = request.data.get('linha', '').strip()
    if not sku or not linha_nome:
        return Response({'detail': 'sku e linha são obrigatórios.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        produto = Produto.objects.get(sku=sku)
    except Produto.DoesNotExist:
        return Response({'detail': f"SKU '{sku}' não encontrado."}, status=status.HTTP_404_NOT_FOUND)

    try:
        linha = Linha.objects.get(nome=linha_nome)
    except Linha.DoesNotExist:
        return Response({'detail': f"Linha '{linha_nome}' não encontrada."}, status=status.HTTP_404_NOT_FOUND)

    # Cancela pendentes anteriores para garantir unicidade
    ValidacaoQualidade.objects.filter(
        produto=produto, linha=linha,
        status=ValidacaoQualidade.StatusValidacao.PENDENTE,
    ).update(status=ValidacaoQualidade.StatusValidacao.CANCELADO)

    # Reutiliza expirada se existir, senão cria nova
    vq = ValidacaoQualidade.objects.filter(
        produto=produto, linha=linha,
        status=ValidacaoQualidade.StatusValidacao.EXPIRADO,
    ).first() or ValidacaoQualidade(produto=produto, linha=linha)

    vq.status = ValidacaoQualidade.StatusValidacao.APROVADO
    vq.aprovado_por = request.user
    vq.aprovado_em = timezone.now()
    vq.save()

    return Response({'detail': f"Qualidade de '{sku}' aprovada via bypass de engenheiro."})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validacoes_qualidade_aprovar(request, validacao_id):
    """
    POST /api/validacoes/qualidade/<id>/aprovar/
    Requer grupo Qualidade.
    Marca ValidacaoQualidade como aprovado, registrando aprovado_por e aprovado_em.
    """
    user_groups = set(request.user.groups.values_list('name', flat=True))
    pode_aprovar = bool(user_groups & {'Qualidade', 'Engenheiro'})
    if not pode_aprovar:
        return Response(
            {'detail': 'Acesso negado. Apenas Qualidade ou Engenheiro podem aprovar.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        vq = ValidacaoQualidade.objects.select_related('produto', 'linha').get(pk=validacao_id)
    except ValidacaoQualidade.DoesNotExist:
        return Response({'detail': 'Validação não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if vq.status == ValidacaoQualidade.StatusValidacao.APROVADO:
        return Response({'detail': 'Validação já aprovada.'}, status=status.HTTP_400_BAD_REQUEST)

    if vq.status == ValidacaoQualidade.StatusValidacao.CANCELADO:
        return Response({'detail': 'Validação cancelada não pode ser aprovada.'}, status=status.HTTP_400_BAD_REQUEST)

    from .models import HistoricoValidacaoQualidade

    # Observação opcional da qualidade sobre a amostra avaliada
    observacao_qualidade = (request.data.get('observacao') or '').strip() if hasattr(request, 'data') else ''

    vq.status = ValidacaoQualidade.StatusValidacao.APROVADO
    vq.aprovado_por = request.user
    vq.aprovado_em = timezone.now()
    vq.caixas_na_aprovacao = vq.caixas_produzidas
    if observacao_qualidade:
        vq.observacao_qualidade = observacao_qualidade
    vq.save(update_fields=['status', 'aprovado_por', 'aprovado_em',
                           'caixas_na_aprovacao', 'observacao_qualidade', 'atualizada_em'])

    # Escrever False no tag OPC de "aguardando validação" para liberar a máquina
    opc_obs = ''
    opc_ok = None
    linha = vq.linha
    if (linha.conexao_opc_status and linha.tag_aguardando_validacao_opc):
        from .services import write_opc_node
        opc_ok, err = write_opc_node(
            linha.conexao_opc_status.url,
            linha.tag_aguardando_validacao_opc,
            False,
        )
        opc_obs = ' | OPC: liberado' if opc_ok else f' | OPC: falha ({err})'
        if not opc_ok:
            import logging
            logging.getLogger(__name__).warning(
                f"[QUALIDADE] Falha ao escrever False em {linha.tag_aguardando_validacao_opc}: {err}"
            )

    # ── Tracking: aprovação + liberação OPC ────────────────────────────
    try:
        HistoricoValidacaoQualidade.objects.create(
            validacao=vq,
            evento=HistoricoValidacaoQualidade.Evento.APROVADA,
            caixas_no_momento=vq.caixas_produzidas,
            meta_caixas=vq.quantidade_caixas_meta,
            usuario=request.user,
            observacao=(f'Aprovado com {vq.caixas_produzidas} caixas amostradas.'
                        + (f' Obs: {observacao_qualidade}' if observacao_qualidade else '')),
        )
        if opc_ok is not None:
            HistoricoValidacaoQualidade.objects.create(
                validacao=vq,
                evento=(HistoricoValidacaoQualidade.Evento.LIBERADA_OPC if opc_ok
                        else HistoricoValidacaoQualidade.Evento.FALHA_OPC),
                caixas_no_momento=vq.caixas_produzidas,
                meta_caixas=vq.quantidade_caixas_meta,
                usuario=request.user,
                observacao='Liberação enviada ao CLP (False).' if opc_ok else str(err),
            )
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning(f"[QUALIDADE] Erro ao gravar histórico VQ #{vq.id}: {_e}")

    return Response({
        'id': vq.id,
        'sku': vq.produto.sku,
        'linha': vq.linha.nome,
        'status': vq.status,
        'caixas_amostradas': vq.caixas_produzidas,
        'meta_caixas': vq.quantidade_caixas_meta,
        'aprovado_por': request.user.get_full_name() or request.user.username,
        'aprovado_em': vq.aprovado_em.isoformat(),
        'opc_obs': opc_obs.strip(' | '),
    })


# ==================== INSIGHTS DE FORMATOS v9.1 ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analytics_formatos(request, linha_nome):
    """
    GET /api/analytics/formatos/<linha>/
    Query params:
      periodo=30|90|180|365  (dias, default 90)

    Algoritmo O(n): única passagem ordenada pelas trocas.
    Detecta mudanças de formato e acumula tempo por sessão.
    """
    try:
        linha = Linha.objects.get(nome=linha_nome)
    except Linha.DoesNotExist:
        return Response({'detail': f"Linha '{linha_nome}' não encontrada."}, status=status.HTTP_404_NOT_FOUND)

    try:
        periodo_dias = int(request.query_params.get('periodo', 90))
    except ValueError:
        periodo_dias = 90
    periodo_dias = max(7, min(365, periodo_dias))

    agora = timezone.now()
    desde = agora - timedelta(days=periodo_dias)

    # Mapear SKU → (formato_nome, vazao_kg_hora) — única query
    sku_fmt = {}
    for assoc in AssociacaoProdutoLinha.objects.filter(linha=linha).select_related('produto', 'formato'):
        if assoc.formato:
            sku_fmt[assoc.produto.sku] = (
                assoc.formato.nome,
                assoc.formato.vazao_kg_hora or 0.0,
            )

    if not sku_fmt:
        return Response({
            'linha': linha_nome, 'periodo_dias': periodo_dias,
            'total_sessoes': 0, 'sessoes_por_formato': [],
            'tendencia_mensal': [], 'top_formatos': [],
            'ranking_curtos': [], 'formatos_unicos': [],
        })

    # Buscar trocas ordenadas — inclui janela extra para capturar
    # sessão iniciada antes do período solicitado.
    # Não filtra por sucesso pois para detectar sessões de formato importa
    # apenas a sequência de SKUs trocados, independente do resultado no CLP.
    trocas = list(
        TrocaSKU.objects
        .filter(linha=linha_nome, data_hora__gte=desde - timedelta(days=60))
        .order_by('data_hora')
        .values('sku_trocado', 'data_hora')
    )

    if not trocas:
        return Response({
            'linha': linha_nome, 'periodo_dias': periodo_dias,
            'total_sessoes': 0, 'sessoes_por_formato': [],
            'tendencia_mensal': [], 'top_formatos': [],
            'ranking_curtos': [], 'formatos_unicos': [],
        })

    # ── Passagem O(n): detectar sessões de formato ────────────────────────────
    # Uma sessão é um bloco contínuo de trocas com o mesmo formato.
    # Ela começa na primeira troca do formato e termina quando o formato muda.
    from collections import defaultdict

    sessoes = []           # lista de (fmt_nome, vazao, inicio, fim)
    sess_fmt   = None      # formato atual
    sess_vazao = 0.0
    sess_inicio = None

    for i, t in enumerate(trocas):
        fmt_info = sku_fmt.get(t['sku_trocado'])
        fmt_nome = fmt_info[0] if fmt_info else None
        vazao    = fmt_info[1] if fmt_info else 0.0

        if fmt_nome != sess_fmt:
            # Fechar sessão anterior
            if sess_fmt is not None:
                sessoes.append((sess_fmt, sess_vazao, sess_inicio, t['data_hora']))
            # Abrir nova sessão
            sess_fmt    = fmt_nome
            sess_vazao  = vazao
            sess_inicio = t['data_hora']

    # Fechar última sessão com agora
    if sess_fmt is not None:
        sessoes.append((sess_fmt, sess_vazao, sess_inicio, agora))

    # ── Agregar por formato filtrando pelo período ────────────────────────────
    agg = defaultdict(lambda: {
        'formato': '', 'vazao_kg_hora': 0.0,
        'tempo_total_h': 0.0, 'ton_total': 0.0,
        'n_sessoes': 0, 'duracao_media_h': 0.0,
        'sessao_mais_longa_h': 0.0, 'sessao_mais_curta_h': None,
    })

    # Também guardar sessões para tendência mensal
    sessoes_detalhe = []  # (fmt, vazao, inicio_efetivo, fim_efetivo, duracao_h, ton)

    for fmt_nome, vazao, inicio, fim in sessoes:
        if fmt_nome is None:
            continue
        # Ignorar sessão que terminou antes do período
        if fim < desde:
            continue
        ini_ef = max(inicio, desde)
        fim_ef = min(fim, agora)
        dur_h = max(0.0, (fim_ef - ini_ef).total_seconds() / 3600)
        ton   = round(vazao * dur_h / 1000, 3)

        r = agg[fmt_nome]
        r['formato']      = fmt_nome
        r['vazao_kg_hora'] = vazao
        r['tempo_total_h'] += dur_h
        r['ton_total']    += ton
        r['n_sessoes']    += 1
        if dur_h > r['sessao_mais_longa_h']:
            r['sessao_mais_longa_h'] = dur_h
        if r['sessao_mais_curta_h'] is None or dur_h < r['sessao_mais_curta_h']:
            r['sessao_mais_curta_h'] = dur_h

        sessoes_detalhe.append((fmt_nome, ini_ef, fim_ef, ton))

    for r in agg.values():
        if r['n_sessoes'] > 0:
            r['duracao_media_h'] = round(r['tempo_total_h'] / r['n_sessoes'], 2)
        r['tempo_total_h']       = round(r['tempo_total_h'], 2)
        r['ton_total']           = round(r['ton_total'], 3)
        r['sessao_mais_longa_h'] = round(r['sessao_mais_longa_h'], 2)
        r['sessao_mais_curta_h'] = round(r['sessao_mais_curta_h'] or 0.0, 2)

    sessoes_por_formato = sorted(agg.values(), key=lambda x: x['ton_total'], reverse=True)
    formatos_unicos = [r['formato'] for r in sessoes_por_formato]

    # ── Tendência mensal (últimos 6 meses) — O(meses × sessoes) ──────────────
    meses_range = []
    for m in range(5, -1, -1):
        ref = agora - timedelta(days=m * 30)
        label = ref.strftime('%b/%y')
        ini_m = (ref - timedelta(days=ref.day - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        fim_m = agora if m == 0 else (
            (agora - timedelta(days=(m - 1) * 30) - timedelta(days=(agora - timedelta(days=(m-1)*30)).day - 1))
            .replace(hour=0, minute=0, second=0, microsecond=0)
        )
        meses_range.append((label, ini_m, fim_m))

    tendencia = []
    for label, ini_m, fim_m in meses_range:
        ponto = {'mes': label}
        for fmt in formatos_unicos:
            ponto[fmt] = round(sum(
                ton for f, ini, fim, ton in sessoes_detalhe
                if f == fmt and ini < fim_m and fim > ini_m
            ), 2)
        tendencia.append(ponto)

    ranking_curtos = sorted(
        [r for r in sessoes_por_formato if r['n_sessoes'] >= 2],
        key=lambda x: x['duracao_media_h']
    )[:5]

    return Response({
        'linha': linha_nome,
        'periodo_dias': periodo_dias,
        'total_sessoes': len(sessoes_detalhe),
        'sessoes_por_formato': sessoes_por_formato,
        'tendencia_mensal': tendencia,
        'top_formatos': sessoes_por_formato[:8],
        'ranking_curtos': ranking_curtos,
        'formatos_unicos': formatos_unicos,
    })


# ==================== COMUNICAÇÃO POR LINHA — v9.2 ====================

import re as _re

def _extrair_mencoes(texto):
    """Extrai usernames mencionados com @ no texto."""
    return list(set(_re.findall(r'@(\w+)', texto)))

def _turno_label(turno):
    return {'A': 'Turno A (06–14h)', 'B': 'Turno B (14–22h)', 'C': 'Turno C (22–06h)'}.get(turno, turno)

def _msg_dict(msg, user_id):
    nome_completo = msg.autor.get_full_name() or msg.autor.username
    # Grupos do autor (usa cache prefetch se disponível, senão busca)
    try:
        grupos = [g.name for g in msg.autor.groups.all()]
    except Exception:
        grupos = []
    return {
        'id': msg.id,
        'autor_id': msg.autor_id,
        'autor': msg.autor.username,
        'autor_nome': nome_completo,
        'autor_iniciais': ''.join(p[0].upper() for p in nome_completo.split()[:2]),
        'autor_grupos': grupos,
        'texto': msg.texto,
        'tags': msg.tags if hasattr(msg, 'tags') else [],
        'turno': msg.turno,
        'turno_label': _turno_label(msg.turno),
        'criada_em': msg.criada_em.isoformat(),
        'editada': msg.editada,
        'e_minha': msg.autor_id == user_id,
        'mencoes': [{'username': m.mencionado.username} for m in msg.mencoes.all()] if hasattr(msg, '_prefetched_mencoes') else [],
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chat_mensagens(request, linha_nome):
    """
    GET /api/chat/<linha>/
    Query params:
      turno=A|B|C|todos  (default: turno atual)
      data=YYYY-MM-DD     (default: hoje)
      before_id=<id>      (paginação: msgs anteriores ao id)
      limit=50
    """
    try:
        linha = Linha.objects.get(nome=linha_nome)
    except Linha.DoesNotExist:
        return Response({'detail': f"Linha '{linha_nome}' não encontrada."}, status=status.HTTP_404_NOT_FOUND)

    from django.utils import timezone as tz
    from datetime import date as _date
    import datetime as _dt

    # Filtro de data
    data_str = request.query_params.get('data')
    if data_str:
        try:
            data_ref = _dt.date.fromisoformat(data_str)
        except ValueError:
            data_ref = tz.localtime(tz.now()).date()
    else:
        data_ref = tz.localtime(tz.now()).date()

    inicio_dia = tz.make_aware(_dt.datetime.combine(data_ref, _dt.time.min))
    fim_dia    = tz.make_aware(_dt.datetime.combine(data_ref, _dt.time.max))

    qs = (
        MensagemLinha.objects
        .filter(linha=linha, criada_em__gte=inicio_dia, criada_em__lte=fim_dia)
        .select_related('autor')
        .prefetch_related('mencoes__mencionado', 'autor__groups')
    )

    # Filtro turno
    turno_param = request.query_params.get('turno', '')
    if turno_param in ('A', 'B', 'C'):
        qs = qs.filter(turno=turno_param)

    # Paginação por cursor
    before_id = request.query_params.get('before_id')
    limit = min(int(request.query_params.get('limit', 50)), 100)

    if before_id:
        qs = qs.filter(id__lt=before_id)

    # Marcar prefetch flag
    msgs = list(qs.order_by('-criada_em')[:limit])
    for m in msgs:
        m._prefetched_mencoes = True

    msgs.reverse()  # cronológico

    # Marcar menções como lidas
    MencaoMensagem.objects.filter(
        mensagem__in=[m.id for m in msgs],
        mencionado=request.user,
        lida=False,
    ).update(lida=True, lida_em=tz.now())

    return Response({
        'linha': linha_nome,
        'data': data_ref.isoformat(),
        'turno_filtro': turno_param or 'todos',
        'mensagens': [_msg_dict(m, request.user.id) for m in msgs],
        'has_more': len(msgs) == limit,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_enviar(request, linha_nome):
    """
    POST /api/chat/<linha>/
    Body: { "texto": "...", "turno": "A" (opcional) }
    """
    try:
        linha = Linha.objects.get(nome=linha_nome)
    except Linha.DoesNotExist:
        return Response({'detail': f"Linha '{linha_nome}' não encontrada."}, status=status.HTTP_404_NOT_FOUND)

    texto = request.data.get('texto', '').strip()
    if not texto:
        return Response({'detail': 'Texto não pode ser vazio.'}, status=status.HTTP_400_BAD_REQUEST)
    if len(texto) > 1000:
        return Response({'detail': 'Mensagem muito longa (máx 1000 caracteres).'}, status=status.HTTP_400_BAD_REQUEST)

    from ips.models import _turno_atual
    turno = request.data.get('turno') or _turno_atual()
    if turno not in ('A', 'B', 'C'):
        turno = _turno_atual()

    # Extrair hashtags
    tags = list(set(_re.findall(r'#(\w+)', texto)))

    msg = MensagemLinha.objects.create(
        linha=linha,
        autor=request.user,
        texto=texto,
        turno=turno,
        tags=tags,
    )

    # Processar @menções
    usernames = _extrair_mencoes(texto)
    if usernames:
        from django.contrib.auth.models import User as _User
        users_mencionados = _User.objects.filter(username__in=usernames).exclude(id=request.user.id)
        for u in users_mencionados:
            MencaoMensagem.objects.create(mensagem=msg, mencionado=u)

    msg.refresh_from_db()
    msg._prefetched_mencoes = True
    # Prefetch grupos do autor para o dict
    request.user.groups.all()  # já no cache do request.user
    msg.autor = request.user
    return Response(_msg_dict(msg, request.user.id), status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chat_mencoes_nao_lidas(request):
    """
    GET /api/chat/mencoes/nao-lidas/
    Retorna contagem de menções não lidas do usuário logado (para badge no header).
    """
    count = MencaoMensagem.objects.filter(
        mencionado=request.user,
        lida=False,
    ).count()
    return Response({'nao_lidas': count})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chat_usuarios(request):
    """
    GET /api/chat/usuarios/
    Lista usuários ativos para autocomplete de @menção.
    """
    from django.contrib.auth.models import User as _User
    users = _User.objects.filter(is_active=True).prefetch_related('groups').order_by('first_name', 'username')
    return Response([{
        'id': u.id,
        'username': u.username,
        'nome': u.get_full_name() or u.username,
        'iniciais': ''.join(p[0].upper() for p in (u.get_full_name() or u.username).split()[:2]),
        'grupos': [g.name for g in u.groups.all()],
    } for u in users])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resumir_turno(request, linha_nome):
    """
    POST /api/chat/<linha>/resumir/
    Body: { "turno": "A|B|C", "data": "YYYY-MM-DD" }
    Formata as mensagens do turno e envia ao LM Studio para resumo.
    LM Studio deve estar rodando em LM_STUDIO_URL (default: http://host.docker.internal:1234).
    """
    import os
    import datetime as _dt
    from django.utils import timezone as tz
    from ips.models import _turno_atual as _turno_atual_fn

    try:
        linha = Linha.objects.get(nome=linha_nome)
    except Linha.DoesNotExist:
        return Response({'detail': f"Linha '{linha_nome}' não encontrada."}, status=status.HTTP_404_NOT_FOUND)

    data_str   = request.data.get('data')
    turno_req  = request.data.get('turno') or _turno_atual_fn()
    if turno_req not in ('A', 'B', 'C'):
        turno_req = _turno_atual_fn()

    if data_str:
        try:
            data_ref = _dt.date.fromisoformat(data_str)
        except ValueError:
            data_ref = tz.localtime(tz.now()).date()
    else:
        data_ref = tz.localtime(tz.now()).date()

    inicio_dia = tz.make_aware(_dt.datetime.combine(data_ref, _dt.time.min))
    fim_dia    = tz.make_aware(_dt.datetime.combine(data_ref, _dt.time.max))

    msgs = list(
        MensagemLinha.objects
        .filter(linha=linha, turno=turno_req, criada_em__gte=inicio_dia, criada_em__lte=fim_dia)
        .select_related('autor')
        .order_by('criada_em')
    )

    if not msgs:
        return Response({'detail': 'Sem mensagens para resumir neste turno.'}, status=status.HTTP_400_BAD_REQUEST)

    # Formatar conversa para o prompt
    linhas_texto = []
    for m in msgs:
        nome = m.autor.get_full_name() or m.autor.username
        hora = tz.localtime(m.criada_em).strftime('%H:%M')
        tags_str = f" [{', '.join('#' + t for t in m.tags)}]" if m.tags else ''
        linhas_texto.append(f"[{hora}] {nome}{tags_str}: {m.texto}")

    conversa = '\n'.join(linhas_texto)
    turno_label = _turno_label(turno_req)

    prompt = (
        f"Você é um assistente de manufatura industrial. "
        f"Abaixo estão as mensagens do {turno_label} da linha {linha_nome} "
        f"em {data_ref.strftime('%d/%m/%Y')}.\n\n"
        f"Gere um resumo objetivo em português com os seguintes tópicos:\n"
        f"• **Principais eventos** ocorridos no turno\n"
        f"• **Problemas e anomalias** (especialmente os marcados com #hashtags)\n"
        f"• **Ações tomadas** pela equipe\n"
        f"• **Pendências** para o próximo turno\n\n"
        f"Mensagens do turno:\n{conversa}\n\n"
        f"Resumo:"
    )

    lm_url = os.environ.get('LM_STUDIO_URL', 'http://host.docker.internal:1234')

    try:
        resp = requests.post(
            f"{lm_url}/v1/chat/completions",
            json={
                'model': 'local-model',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
                'max_tokens': 800,
            },
            timeout=90,
            headers={'Content-Type': 'application/json'},
        )
        resp.raise_for_status()
        resumo = resp.json()['choices'][0]['message']['content'].strip()
        return Response({
            'resumo': resumo,
            'turno': turno_req,
            'turno_label': turno_label,
            'data': data_ref.isoformat(),
            'n_mensagens': len(msgs),
        })
    except requests.exceptions.ConnectionError:
        return Response(
            {'detail': f'LM Studio não disponível em {lm_url}. Verifique se está rodando.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception as e:
        return Response({'detail': f'Erro ao chamar LM Studio: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chat_nao_lidas_por_linha(request):
    """
    GET /api/chat/nao-lidas-por-linha/
    Retorna contagem de mensagens não lidas por linha para o usuário autenticado.
    "Não lida" = mensagem de outro usuário posterior à última visualização.
    Resposta: { "L01": 3, "L02": 0, ... }
    """
    usuario = request.user
    linhas = Linha.objects.all()

    # Mapa de última visualização por linha para este usuário
    visualizacoes = {
        v.linha_id: v.visualizado_em
        for v in UltimaVisualizacaoChat.objects.filter(usuario=usuario)
    }

    resultado = {}
    for linha in linhas:
        ultima_viz = visualizacoes.get(linha.pk)
        qs = MensagemLinha.objects.filter(linha=linha).exclude(autor=usuario)
        if ultima_viz:
            qs = qs.filter(criada_em__gt=ultima_viz)
        else:
            # Nunca visitou — não bombarda com todas as mensagens históricas;
            # conta apenas das últimas 24 horas.
            qs = qs.filter(criada_em__gt=timezone.now() - timedelta(hours=24))
        resultado[linha.nome] = qs.count()

    return Response(resultado)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_marcar_visualizado(request, linha_nome):
    """
    POST /api/chat/<linha>/visualizar/
    Atualiza o timestamp de última visualização do usuário para esta linha.
    Chamado pelo frontend quando o usuário abre o chat de uma linha.
    """
    try:
        linha = Linha.objects.get(nome=linha_nome)
    except Linha.DoesNotExist:
        return Response({'detail': 'Linha não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    UltimaVisualizacaoChat.objects.update_or_create(
        usuario=request.user,
        linha=linha,
        defaults={},  # auto_now=True cuida do timestamp
    )
    return Response({'ok': True})


# ==================== RECIPE MONITOR — Sincronismo CLP → Receita ====================

import uuid as _uuid
from django.db import transaction
from .models import HistoricoSincronismoReceita
from .permissions import PodeSincronizarReceita


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, PodeSincronizarReceita])
def recipe_monitor_sincronizar(request, formato_id):
    """
    PATCH /api/recipe-monitor/formato/<formato_id>/sincronizar/

    Atualiza valores de FormatoVariavel a partir de leituras feitas no CLP
    pelo serviço externo `mis-recipe-intelligent`.

    Permissão: grupos TIM / Engenharia / Coordenação (ver PodeSincronizarReceita).

    Body esperado:
        {
            "linha_nome": "L21",                       # opcional, só p/ auditoria
            "observacao": "Pós-ajuste de pressão",     # opcional
            "variaveis": [
                {"variavel_id": 12, "valor": "1.004"},
                {"variavel_id": 18, "valor": "TRUE"},
                ...
            ]
        }

    Comportamento:
      - Apenas variáveis JÁ existentes em FormatoVariavel(formato=X) são
        atualizadas. IDs desconhecidos são reportados em `ignoradas` (não
        cria FormatoVariavel novo — isso é responsabilidade do admin).
      - Cada atualização cria um registro em HistoricoSincronismoReceita,
        agrupado pelo mesmo `lote_uuid`.
      - Tudo dentro de uma transação atômica. Falha → rollback total.

    Resposta (200):
        {
            "lote_uuid": "...",
            "formato_id": 1,
            "formato_nome": "PET 500ml — Água c/ Gás",
            "atualizadas": [{"variavel_id": 12, "nome": "...",
                             "valor_anterior": "1.000", "valor_novo": "1.004"}],
            "ignoradas":   [{"variavel_id": 999, "motivo": "..."}],
            "usuario": "joao.silva",
            "data_hora": "2026-05-29T13:42:11Z"
        }
    """
    # 1. Formato precisa existir
    try:
        formato = Formato.objects.get(pk=formato_id)
    except Formato.DoesNotExist:
        return Response(
            {'detail': f'Formato id={formato_id} não encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # 2. Validação do body
    data = request.data or {}
    variaveis_input = data.get('variaveis')
    if not isinstance(variaveis_input, list) or len(variaveis_input) == 0:
        return Response(
            {'detail': 'Campo "variaveis" é obrigatório e deve ser lista não vazia.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    linha_nome = (data.get('linha_nome') or '').strip()
    observacao = (data.get('observacao') or '').strip()
    ip_origem = request.META.get('REMOTE_ADDR') or None

    linha_obj = None
    if linha_nome:
        linha_obj = Linha.objects.filter(nome=linha_nome).first()

    # 2b. TRAVA DE SEGURANÇA: o formato a sincronizar DEVE ser o que está
    # rodando na linha agora (detectado via OPC / última troca). Isso impede
    # gravar valores do CLP na receita de um formato errado. Só valida quando
    # a linha foi informada e foi possível detectar o formato ativo.
    if linha_obj is not None:
        fa = _resolver_formato_ativo(linha_obj)
        if fa['detectado'] and fa['formato'].id != formato.id:
            return Response(
                {
                    'detail': (
                        f"Formato divergente: a linha '{linha_nome}' está rodando o SKU "
                        f"'{fa['sku']}' (formato '{fa['formato'].nome}'), mas o sincronismo "
                        f"foi solicitado para o formato '{formato.nome}'. Operação bloqueada "
                        "para não corromper a receita."
                    ),
                    'codigo': 'formato_divergente',
                    'formato_atual_id': fa['formato'].id,
                    'formato_atual_nome': fa['formato'].nome,
                    'sku_atual': fa['sku'],
                },
                status=status.HTTP_409_CONFLICT,
            )
        # fa['detectado']=False (OPC off + sem troca) → não bloqueia, mas o
        # frontend já não deixa sincronizar nesse caso.

    # 3. Pré-carrega os FormatoVariavel deste formato em um dict por variavel_id
    fvs_existentes = {
        fv.variavel_id: fv
        for fv in FormatoVariavel.objects.filter(formato=formato).select_related('variavel')
    }

    lote_uuid = _uuid.uuid4()
    atualizadas = []
    ignoradas = []

    # 4. Aplica em transação atômica
    try:
        with transaction.atomic():
            for item in variaveis_input:
                if not isinstance(item, dict):
                    ignoradas.append({
                        'variavel_id': None,
                        'motivo': 'Item inválido (esperado objeto com variavel_id e valor).',
                    })
                    continue

                variavel_id = item.get('variavel_id')
                valor_novo = item.get('valor')

                if variavel_id is None or valor_novo is None:
                    ignoradas.append({
                        'variavel_id': variavel_id,
                        'motivo': 'Faltando variavel_id ou valor.',
                    })
                    continue

                fv = fvs_existentes.get(variavel_id)
                if fv is None:
                    ignoradas.append({
                        'variavel_id': variavel_id,
                        'motivo': (
                            'Variável não está mapeada a este formato '
                            '(FormatoVariavel inexistente). Cadastre via admin antes.'
                        ),
                    })
                    continue

                valor_anterior = fv.valor
                valor_novo_str = str(valor_novo)

                # Evita updates no-op (mesmo valor → não polui histórico)
                if valor_anterior == valor_novo_str:
                    ignoradas.append({
                        'variavel_id': variavel_id,
                        'nome': fv.variavel.nome,
                        'motivo': 'Valor idêntico ao atual — nada a fazer.',
                    })
                    continue

                fv.valor = valor_novo_str
                fv.atualizado_por = request.user
                fv.save(update_fields=['valor', 'atualizado_por', 'atualizado_em'])

                HistoricoSincronismoReceita.objects.create(
                    lote_uuid=lote_uuid,
                    formato=formato,
                    variavel=fv.variavel,
                    linha=linha_obj,
                    valor_anterior=valor_anterior,
                    valor_novo=valor_novo_str,
                    usuario=request.user,
                    ip_origem=ip_origem,
                    origem_servico='recipe-monitor',
                    observacao=observacao,
                )

                atualizadas.append({
                    'variavel_id': variavel_id,
                    'nome': fv.variavel.nome,
                    'tipo': fv.variavel.tipo,
                    'valor_anterior': valor_anterior,
                    'valor_novo': valor_novo_str,
                })

    except Exception as e:
        return Response(
            {'detail': f'Erro ao gravar sincronismo: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {
            'lote_uuid': str(lote_uuid),
            'formato_id': formato.id,
            'formato_nome': formato.nome,
            'atualizadas': atualizadas,
            'ignoradas': ignoradas,
            'total_atualizadas': len(atualizadas),
            'total_ignoradas': len(ignoradas),
            'usuario': request.user.username,
            'data_hora': timezone.now().isoformat(),
        },
        status=status.HTTP_200_OK,
    )


# ==================== GESTÃO DE USUÁRIOS (item 3 — só superuser) ====================

from rest_framework.permissions import IsAdminUser


def _serializar_usuario_expiracao(user):
    """Monta o dict de status de expiração de um usuário para a tela de gestão."""
    from .models import ContaUsuarioExpiracao
    exp = getattr(user, 'expiracao', None)
    grupos = list(user.groups.values_list('name', flat=True))

    base = {
        'id': user.id,
        'username': user.username,
        'nome_completo': user.get_full_name() or user.username,
        'email': user.email,
        'is_active': user.is_active,
        'is_superuser': user.is_superuser,
        'is_staff': user.is_staff,
        'grupos': grupos,
        'ultimo_login': user.last_login.isoformat() if user.last_login else None,
    }

    if user.is_superuser:
        base.update({
            'tem_expiracao': False,
            'status': 'superuser',
            'validade_ate': None,
            'dias_ate_validade': None,
            'dias_inativo': None,
            'motivo_expiracao': None,
        })
        return base

    if exp is None:
        base.update({
            'tem_expiracao': False,
            'status': 'sem_controle',
            'validade_ate': None,
            'dias_ate_validade': None,
            'dias_inativo': None,
            'motivo_expiracao': None,
        })
        return base

    motivo = exp.motivo_expiracao()
    if not user.is_active:
        st = 'bloqueado'
    elif motivo:
        st = 'expirado'  # vencido mas worker ainda não desativou
    else:
        dias = exp.dias_ate_validade()
        st = 'a_vencer' if (dias is not None and dias <= 7) else 'ativo'

    base.update({
        'tem_expiracao': True,
        'status': st,
        'validade_ate': exp.validade_ate.isoformat(),
        'dias_ate_validade': exp.dias_ate_validade(),
        'dias_inativo': exp.dias_inativo(),
        'motivo_expiracao': motivo,
    })
    return base


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def gestao_usuarios_listar(request):
    """
    GET /api/gestao-usuarios/
    Lista usuários com status de expiração. APENAS superuser (IsAdminUser).

    IsAdminUser checa is_staff; reforçamos is_superuser abaixo para garantir
    que apenas superusers vejam a gestão (staff comum não basta).
    """
    if not request.user.is_superuser:
        return Response(
            {'detail': 'Apenas superusuários podem acessar a gestão de usuários.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    from django.contrib.auth.models import User
    usuarios = (
        User.objects.all()
        .select_related('expiracao')
        .prefetch_related('groups')
        .order_by('-is_active', 'username')
    )
    data = [_serializar_usuario_expiracao(u) for u in usuarios]

    # Resumo para os cards do topo da tela
    resumo = {
        'total': len(data),
        'ativos': sum(1 for d in data if d['is_active']),
        'bloqueados': sum(1 for d in data if d['status'] == 'bloqueado'),
        'a_vencer': sum(1 for d in data if d['status'] == 'a_vencer'),
        'expirados': sum(1 for d in data if d['status'] == 'expirado'),
    }
    return Response({'usuarios': data, 'resumo': resumo})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def gestao_usuarios_renovar(request, user_id):
    """
    POST /api/gestao-usuarios/<user_id>/renovar/
    Renova a validade da conta por +5 meses e reativa. APENAS superuser.
    """
    if not request.user.is_superuser:
        return Response(
            {'detail': 'Apenas superusuários podem renovar contas.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    from django.contrib.auth.models import User
    from .models import ContaUsuarioExpiracao
    from datetime import timedelta

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'detail': 'Usuário não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if user.is_superuser:
        return Response(
            {'detail': 'Superusuários não possuem validade para renovar.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    exp, _ = ContaUsuarioExpiracao.objects.get_or_create(
        user=user,
        defaults={'validade_ate': timezone.now() + timedelta(days=ContaUsuarioExpiracao.VALIDADE_DIAS)},
    )
    exp.renovar(por_usuario=request.user)

    return Response({
        'ok': True,
        'mensagem': f'Conta de {user.username} renovada por mais 5 meses.',
        'usuario': _serializar_usuario_expiracao(user),
    })


# ==================== RECIPE MONITOR — FORMATO ATIVO (anti-erro de seleção) ====================

def _resolver_formato_ativo(linha):
    """
    Resolve o formato que está REALMENTE rodando na linha agora, para o
    sincronismo de receita agir sobre ele (sem o usuário escolher e errar).

    Ordem de detecção:
      1. OPC — lê tag_sku_atual_opc no servidor conexao_opc_status (fonte real do CLP)
      2. Fallback — StatusLinha.sku_atual (último SKU registrado pelo MIS)
    Depois resolve: SKU → AssociacaoProdutoLinha(produto, linha) → formato.

    Retorna dict:
      {sku, fonte, formato, detectado, motivo}
      - detectado=True quando achou formato; False caso contrário (com motivo).
    """
    resultado = {'sku': None, 'fonte': None, 'formato': None,
                 'detectado': False, 'motivo': None}

    sku = None
    fonte = None

    # 1. OPC — SKU real na máquina
    if linha.conexao_opc_status and linha.tag_sku_atual_opc:
        try:
            from opcua import Client as OPCClient
            client = OPCClient(linha.conexao_opc_status.url, timeout=3)
            try:
                client.connect()
                val = client.get_node(linha.tag_sku_atual_opc).get_value()
                if val is not None:
                    s = str(val).strip()
                    if s:
                        sku, fonte = s, 'opc'
            finally:
                try:
                    client.disconnect()
                except Exception:
                    pass
        except Exception:
            pass  # OPC inacessível → cai no fallback

    # 2. Fallback — última troca registrada no MIS
    if not sku:
        try:
            status_linha = StatusLinha.objects.filter(linha=linha).first()
            if status_linha and status_linha.sku_atual:
                sku, fonte = status_linha.sku_atual.strip(), 'ultima_troca'
        except Exception:
            pass

    resultado['sku'] = sku
    resultado['fonte'] = fonte

    if not sku:
        resultado['motivo'] = 'nao_foi_possivel_ler_sku'
        return resultado

    # 3. Resolver SKU → formato (via associação produto-linha)
    try:
        assoc = (AssociacaoProdutoLinha.objects
                 .select_related('formato', 'produto')
                 .get(produto__sku=sku, linha=linha))
    except AssociacaoProdutoLinha.DoesNotExist:
        resultado['motivo'] = 'sku_sem_associacao_na_linha'
        return resultado

    if not assoc.formato:
        resultado['motivo'] = 'associacao_sem_formato'
        return resultado

    resultado['formato'] = assoc.formato
    resultado['detectado'] = True
    return resultado


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recipe_monitor_formato_ativo(request, linha_nome):
    """
    GET /api/recipe-monitor/linha/<linha_nome>/formato-ativo/

    Retorna o formato que está rodando na linha AGORA (detectado via OPC, com
    fallback para a última troca), com suas variáveis (receita) — para a tela
    de sincronismo agir sobre ele sem o usuário selecionar e correr o risco de
    errar o formato.
    """
    try:
        linha = Linha.objects.get(nome=linha_nome)
    except Linha.DoesNotExist:
        return Response({'detail': f"Linha '{linha_nome}' não encontrada."},
                        status=status.HTTP_404_NOT_FOUND)

    r = _resolver_formato_ativo(linha)

    if not r['detectado']:
        motivos = {
            'nao_foi_possivel_ler_sku': 'Não foi possível ler o SKU atual da linha (OPC indisponível e sem troca registrada).',
            'sku_sem_associacao_na_linha': f"O SKU '{r['sku']}' em operação não está associado a esta linha.",
            'associacao_sem_formato': f"O SKU '{r['sku']}' está associado à linha, mas sem formato configurado.",
        }
        return Response({
            'detectado': False,
            'sku': r['sku'],
            'fonte': r['fonte'],
            'motivo': r['motivo'],
            'mensagem': motivos.get(r['motivo'], 'Não foi possível detectar o formato ativo.'),
        }, status=status.HTTP_200_OK)

    formato = r['formato']
    # Reusa o serializer (get_variaveis já corrigido contra recursão)
    data = FormatoSerializer(formato).data
    return Response({
        'detectado': True,
        'sku': r['sku'],
        'fonte': r['fonte'],  # 'opc' ou 'ultima_troca'
        'formato': data,       # inclui id, nome, variaveis (receita)
    }, status=status.HTTP_200_OK)
