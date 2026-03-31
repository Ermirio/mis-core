import time
import json
import requests
import socket
import io
from smb.SMBConnection import SMBConnection
import xml.etree.ElementTree as ET
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
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
    ConexaoOPCUAServidor, AssociacaoProdutoLinha  # Adicionado
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
    """Converte valor para o tipo apropriado"""
    try:
        if tipo == "REAL":
            return float(valor)
        # --- ALTERAÇÃO AQUI ---
        # Adiciona UINT e INT à lógica de conversão para inteiro
        elif tipo in ("DINT", "UDINT", "UINT", "INT"):
            print(f"Tipo {tipo}")
            return int(valor)
        # --- FIM DA ALTERAÇÃO ---
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

    dia_atual = datetime.now().strftime("%d%m%Y")
    hora_atual = datetime.now().strftime("%H%M%S")
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

    conteudo = f";;{codigo_sku};{descricao_param};{sku_param};{dun14_param};{validade_param};{dia_atual};{hora_atual};;\r\n"
    conteudo02 = f";;;;;;;{dia_atual};{hora_atual};;\r\n"
    print(f"Conteúdo a ser escrito: {conteudo}")

    for impressora in impressoras:
        if not impressora.ip:
            erros.append(f"[{impressora.nome}] IP não configurado.")
            continue
        print(f"[{impressora.nome}] Conectando via SMB em {impressora.ip}")

        try:
            conn = SMBConnection('', '', 'mis-server', impressora.nome, use_ntlm_v2=True, is_direct_tcp=False)
            connected = conn.connect(impressora.ip, 139, timeout=10)
            if not connected:
                erros.append(f"[{impressora.nome}] Falha ao conectar via SMB em {impressora.ip}:139")
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

    all_trocas = TrocaSKU.objects.filter(linha=linha_nome).select_related('usuario').order_by('-data_hora')
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

# ... (resto do seu arquivo views.py) ...
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
            ip_origem=ip_origem
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
            
            LogEquipamentoTroca.objects.create(
                troca=troca,
                tipo_equipamento='equipamento',
                nome_equipamento=equipamento.nome,
                status=status_log,
                mensagem='Escrita realizada com sucesso.' if not plc_erros else 'Falha na escrita de algumas variáveis.',
                erro_detalhado='; '.join(plc_erros) if plc_erros else '',
                variaveis_escritas=variaveis_escritas,
                variaveis_total=len(variaveis_dados),
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
            
            LogEquipamentoTroca.objects.create(
                troca=troca,
                tipo_equipamento='impressora_3m',
                nome_equipamento=impressora.nome,
                status=status_log_impressora,
                mensagem='Escrita realizada com sucesso.' if not current_impressora_errors else 'Falha na escrita no arquivo ARQ_auto.txt.',
                erro_detalhado='; '.join(current_impressora_errors) if current_impressora_errors else '',
                variaveis_escritas=variaveis_escritas,
                variaveis_total=variaveis_total,
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

        response_data = {
            "mensagem": "Troca realizada com sucesso!" if not general_equipment_errors else "Troca realizada com erros.",
            "sucesso": not bool(general_equipment_errors),
            "resumo_execucao": troca.get_resumo_execucao(),
            "erros": general_equipment_errors,
            "troca_id": troca.id
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
        historico = intertravamento.historico.all()[:50]
        return Response(HistoricoIntertravamentoSerializer(historico, many=True).data)

