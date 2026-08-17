#!/usr/bin/env python
"""
seed_ultima_troca.py
====================
Insere uma TrocaSKU simulada com logs detalhados de equipamentos
para visualizar o painel "Última Troca" na tela Status do Produto (v9.4).

Uso (dentro do container backend):
    python seed_ultima_troca.py [LINHA]

Exemplos:
    python seed_ultima_troca.py          # usa L01 (padrão)
    python seed_ultima_troca.py L02

Pré-requisito: a Linha deve existir no banco. Cria a TrocaSKU sem
precisar de Produto, Formato ou validação SAP (bypass direto no ORM).
"""
import os
import sys
import django

# ── bootstrap Django ────────────────────────────────────────────────────────
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digitalfactory.settings')
django.setup()

from django.utils import timezone
from ips.models import TrocaSKU, LogEquipamentoTroca, Linha

# ── parâmetros ──────────────────────────────────────────────────────────────
LINHA_NOME = sys.argv[1] if len(sys.argv) > 1 else 'L01'
SKU        = 'SKU-DEMO-001'
DESCRICAO  = 'Produto Demo 800g Caixa 6un'
DUN14      = '17894900112345'
VALIDADE   = '12'
NUMERO_OP  = 'OP-99999'

# ── verificar que a linha existe ────────────────────────────────────────────
try:
    linha_obj = Linha.objects.get(nome=LINHA_NOME)
    print(f"[OK] Linha '{LINHA_NOME}' encontrada.")
except Linha.DoesNotExist:
    linhas = list(Linha.objects.values_list('nome', flat=True))
    print(f"[ERRO] Linha '{LINHA_NOME}' não encontrada.")
    print(f"       Linhas disponíveis: {linhas or '(nenhuma cadastrada)'}")
    sys.exit(1)

# ── criar TrocaSKU ──────────────────────────────────────────────────────────
troca = TrocaSKU(
    linha=LINHA_NOME,
    sku_trocado=SKU,
    descricao=DESCRICAO,
    dun14=DUN14,
    validade=VALIDADE,
    numero_op=NUMERO_OP,
    ip_origem='127.0.0.1',
    primeira_rodada=True,
    tempo_execucao=4.87,
)
troca.save()
print(f"[OK] TrocaSKU criada — id={troca.id}")

# ── logs simulados ──────────────────────────────────────────────────────────
logs = [
    # ── Enchedora (sucesso total) ───────────────────────────────────────────
    dict(
        tipo_equipamento='equipamento',
        nome_equipamento='Enchedora',
        status='sucesso',
        mensagem='Escrita realizada com sucesso.',
        erro_detalhado='',
        variaveis_escritas=6,
        variaveis_total=6,
        tempo_execucao=1.23,
        ip_equipamento=None,
        conexao_opcua='opc.tcp://192.168.1.10:4840',
        variaveis_detalhes=[
            {'nome': 'SKU_Esperado',      'tag_plc': 'L01.Enc.SKU_Esp',      'valor': SKU,       'sucesso': True},
            {'nome': 'Descricao_Esperada','tag_plc': 'L01.Enc.Desc_Esp',     'valor': DESCRICAO, 'sucesso': True},
            {'nome': 'EAN_Esperado',      'tag_plc': 'L01.Enc.EAN_Esp',      'valor': '7894900112345', 'sucesso': True},
            {'nome': 'DUN14_Esperado',    'tag_plc': 'L01.Enc.DUN14_Esp',    'valor': DUN14,     'sucesso': True},
            {'nome': 'Filme_Esperado',    'tag_plc': 'L01.Enc.Filme_Esp',    'valor': 'FILME-800G', 'sucesso': True},
            {'nome': 'NumeroOP_Esperado', 'tag_plc': 'L01.Enc.NumOP_Esp',    'valor': NUMERO_OP, 'sucesso': True},
        ],
    ),
    # ── Encaixotadora (1 falha) ─────────────────────────────────────────────
    dict(
        tipo_equipamento='equipamento',
        nome_equipamento='Encaixotadora',
        status='falha',
        mensagem='Falha na escrita de algumas variáveis.',
        erro_detalhado='[Encaixotadora] OPC: BadNodeIdUnknown para tag L01.Box.DUN14_Esp',
        variaveis_escritas=5,
        variaveis_total=6,
        tempo_execucao=2.11,
        ip_equipamento=None,
        conexao_opcua='opc.tcp://192.168.1.11:4840',
        variaveis_detalhes=[
            {'nome': 'SKU_Esperado',      'tag_plc': 'L01.Box.SKU_Esp',      'valor': SKU,       'sucesso': True},
            {'nome': 'Descricao_Esperada','tag_plc': 'L01.Box.Desc_Esp',     'valor': DESCRICAO, 'sucesso': True},
            {'nome': 'EAN_Esperado',      'tag_plc': 'L01.Box.EAN_Esp',      'valor': '7894900112345', 'sucesso': True},
            {'nome': 'DUN14_Esperado',    'tag_plc': 'L01.Box.DUN14_Esp',    'valor': DUN14,     'sucesso': False},
            {'nome': 'Filme_Esperado',    'tag_plc': 'L01.Box.Filme_Esp',    'valor': 'FILME-800G', 'sucesso': True},
            {'nome': 'NumeroOP_Esperado', 'tag_plc': 'L01.Box.NumOP_Esp',    'valor': NUMERO_OP, 'sucesso': True},
        ],
    ),
    # ── Paletizadora (nao_configurado) ──────────────────────────────────────
    dict(
        tipo_equipamento='equipamento',
        nome_equipamento='Paletizadora',
        status='nao_configurado',
        mensagem='Nenhuma configuração de variável encontrada.',
        erro_detalhado='[Paletizadora] Nenhuma configuração de variável encontrada.',
        variaveis_escritas=0,
        variaveis_total=0,
        tempo_execucao=0.0,
        ip_equipamento=None,
        conexao_opcua='',
        variaveis_detalhes=[],
    ),
    # ── Impressora 3M (sucesso) ─────────────────────────────────────────────
    dict(
        tipo_equipamento='impressora_3m',
        nome_equipamento='Impressora 3M L01',
        status='sucesso',
        mensagem='Escrita realizada com sucesso.',
        erro_detalhado='',
        variaveis_escritas=7,
        variaveis_total=7,
        tempo_execucao=0.98,
        ip_equipamento='192.168.1.50',
        conexao_opcua='',
        variaveis_detalhes=[
            {'nome': 'SKU',       'tag_plc': 'ARQ_auto.txt', 'valor': SKU,          'sucesso': True},
            {'nome': 'Descrição', 'tag_plc': 'ARQ_auto.txt', 'valor': DESCRICAO,    'sucesso': True},
            {'nome': 'DUN14',     'tag_plc': 'ARQ_auto.txt', 'valor': DUN14,        'sucesso': True},
            {'nome': 'Validade',  'tag_plc': 'ARQ_auto.txt', 'valor': VALIDADE,     'sucesso': True},
            {'nome': 'Dia',       'tag_plc': 'ARQ_auto.txt', 'valor': '11',         'sucesso': True},
            {'nome': 'Hora',      'tag_plc': 'ARQ_auto.txt', 'valor': '08:30',      'sucesso': True},
            {'nome': 'CódSKU',   'tag_plc': 'ARQ_auto.txt', 'valor': '001',        'sucesso': True},
        ],
    ),
    # ── Impressora Inkjet (sucesso) ─────────────────────────────────────────
    dict(
        tipo_equipamento='impressora_inkjet',
        nome_equipamento='Inkjet Linha 01',
        status='sucesso',
        mensagem='Comando SLA enviado com sucesso.',
        erro_detalhado='',
        variaveis_escritas=1,
        variaveis_total=1,
        tempo_execucao=0.55,
        ip_equipamento='192.168.1.60',
        conexao_opcua='',
        variaveis_detalhes=[
            {'nome': 'Comando SLA', 'tag_plc': 'FMT-800G-L01',
             'valor': f'SKU={SKU} | Desc={DESCRICAO} | DUN14={DUN14}', 'sucesso': True},
        ],
    ),
]

for log_data in logs:
    LogEquipamentoTroca.objects.create(troca=troca, **log_data)
    print(f"  [LOG] {log_data['tipo_equipamento']:15s} | {log_data['nome_equipamento']:22s} | {log_data['status']}")

# ── forçar recálculo do TrocaSKU ───────────────────────────────────────────
troca.save()

# ── resultado final ─────────────────────────────────────────────────────────
troca.refresh_from_db()
print()
print("=" * 55)
print(f"  TrocaSKU id={troca.id}  linha={troca.linha}")
print(f"  SKU        : {troca.sku_trocado}")
print(f"  Sucesso    : {troca.sucesso}")
print(f"  Equipamentos: {troca.equipamentos_sucesso}/{troca.equipamentos_processados}")
print("=" * 55)
print()
print(f"  Acesse: Status do Produto → Linha {LINHA_NOME}")
print(f"  O painel 'Última Troca' deve aparecer com {len(logs)} equipamentos.")
print()
