"""
seed_demo_l01.py  — v9.1
Popula dados simulados para linha L01 com foco em Insights de Formatos:
  - 3 formatos (1kg, 5kg, 400-500g) com vazão realista
  - Histórico de TrocaSKU em blocos sequenciais de formato (sessões realistas)
  - Pipeline de Validações: SAP + Qualidade em vários estados
  - Usuários de teste com grupos corretos

Executar:
  sudo docker cp seed_demo_l01.py mis-changeover-backend:/tmp/seed.py
  sudo docker exec mis-changeover-backend python manage.py shell -c "exec(open('/tmp/seed.py').read())"
"""

import random
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User, Group

from ips.models import (
    Linha, Produto, AssociacaoProdutoLinha, Formato,
    TrocaSKU, LiberacaoSAP, ValidacaoQualidade,
)

random.seed(42)   # resultado reproduzível
now = timezone.now()

# ── Usuários ──────────────────────────────────────────────────────────────────

admin_user, _ = User.objects.get_or_create(
    username='admin',
    defaults={'is_superuser': True, 'is_staff': True, 'first_name': 'Admin'}
)

sap_group,  _ = Group.objects.get_or_create(name='SAP')
qual_group, _ = Group.objects.get_or_create(name='Qualidade')

sap_user, created = User.objects.get_or_create(
    username='ana.sap',
    defaults={'first_name': 'Ana', 'last_name': 'Pereira', 'email': 'ana@factory.local'}
)
if created:
    sap_user.set_password('demo1234')
    sap_user.save()
sap_user.groups.add(sap_group)

qual_user, created = User.objects.get_or_create(
    username='carlos.qualidade',
    defaults={'first_name': 'Carlos', 'last_name': 'Mendes', 'email': 'carlos@factory.local'}
)
if created:
    qual_user.set_password('demo1234')
    qual_user.save()
qual_user.groups.add(qual_group)

operador_user, created = User.objects.get_or_create(
    username='joao.operador',
    defaults={'first_name': 'João', 'last_name': 'Silva', 'email': 'joao@factory.local'}
)
if created:
    operador_user.set_password('demo1234')
    operador_user.save()

print("✓ Usuários criados/atualizados")

# ── Linha L01 ─────────────────────────────────────────────────────────────────

linha_l01, _ = Linha.objects.get_or_create(
    nome='L01',
    defaults={'descricao': 'Linha de Envase 01 — Embalagem Primária', 'ativa': True}
)
print(f"✓ Linha {linha_l01}")

# ── Formatos ──────────────────────────────────────────────────────────────────
# (nome, descricao, gramas, vazao_kg_hora)
FORMATOS_DEF = [
    ('1kg-L01',      'Embalagem 1 kg — L01',        1000, 2400.0),  # 2.4 ton/h
    ('5kg-L01',      'Embalagem 5 kg — L01',         5000, 4800.0),  # 4.8 ton/h
    ('400-500g-L01', 'Embalagem 400-500 g — L01',     500, 1200.0),  # 1.2 ton/h
]

formatos = {}
for fname, fdesc, fgramas, fvazao in FORMATOS_DEF:
    fmt, _ = Formato.objects.update_or_create(
        nome=fname,
        defaults={
            'descricao': fdesc,
            'gramas': fgramas,
            'vazao_kg_hora': fvazao,
            'criado_por': admin_user,
        }
    )
    formatos[fname] = fmt
    print(f"  ✓ Formato {fname} — {fvazao} kg/h")

print("✓ Formatos criados/atualizados")

# ── Produtos ──────────────────────────────────────────────────────────────────
# (sku, descricao, dun14, ean, validade, formato_nome)
SKUS_DEF = [
    ('SKU-1001', 'Farinha de Trigo 1kg Tipo 1',     'D14-1001', '8901234500010', '12 meses', '1kg-L01'),
    ('SKU-1003', 'Farinha Integral 1kg',             'D14-1003', '8901234500034', '10 meses', '1kg-L01'),
    ('SKU-1002', 'Farinha de Trigo 5kg Tipo 1',      'D14-1002', '8901234500027', '12 meses', '5kg-L01'),
    ('SKU-1004', 'Farinha de Milho 500g',            'D14-1004', '8901234500041',  '8 meses', '400-500g-L01'),
    ('SKU-1005', 'Mistura para Bolo 400g Chocolate', 'D14-1005', '8901234500058', '18 meses', '400-500g-L01'),
]

produtos_por_sku = {}
produtos_por_formato = {fname: [] for fname in formatos}

for sku, desc, dun, ean, validade, fmt_nome in SKUS_DEF:
    p, _ = Produto.objects.get_or_create(
        sku=sku,
        defaults={'descricao': desc, 'dun14': dun, 'ean': ean, 'validade': validade, 'criado_por': admin_user}
    )
    AssociacaoProdutoLinha.objects.update_or_create(
        produto=p, linha=linha_l01,
        defaults={'formato': formatos[fmt_nome]}
    )
    produtos_por_sku[sku] = p
    produtos_por_formato[fmt_nome].append(p)
    print(f"  ✓ Produto {sku} → {fmt_nome}")

print("✓ Produtos associados à L01 com formatos")

# ── TrocaSKU — sessões realistas de formato ───────────────────────────────────
#
# Estratégia: simular o calendário de produção dos últimos 6 meses como
# blocos sequenciais. Cada bloco é uma "sessão de formato" com duração
# realista (2h a 16h), depois troca para outro formato.
# Dentro do bloco podem ocorrer micro-trocas entre SKUs do mesmo formato
# (ex: 1001 → 1003 → 1001) que NÃO mudam o formato — sessão continua.
#
# Layout de blocos (peso em produção):
#   1kg-L01      — formato mais rodado (~50% do tempo)
#   5kg-L01      — segundo mais rodado (~35%)
#   400-500g-L01 — menos rodado (~15%)

ValidacaoQualidade.objects.filter(linha=linha_l01).delete()
LiberacaoSAP.objects.filter(linha=linha_l01).delete()
TrocaSKU.objects.filter(linha='L01').delete()
print("✓ Dados anteriores de L01 removidos")

# Padrão de rotação de formatos ao longo do tempo
# Peso de escolha: 1kg=5, 5kg=3, 400-500g=2
FORMATO_SEQUENCIA = (
    ['1kg-L01'] * 5 + ['5kg-L01'] * 3 + ['400-500g-L01'] * 2
)

cursor = now - timedelta(days=180)   # 6 meses atrás
troca_records = []                   # (TrocaSKU, datetime)
trocas_primeira_rodada = {}          # sku → TrocaSKU (mais recente primeira_rodada)
skus_ja_rodados = set()              # para marcar primeira_rodada corretamente

bloco_idx = 0
while cursor < now - timedelta(hours=4):
    # Escolher próximo formato em sequência
    fmt_nome = FORMATO_SEQUENCIA[bloco_idx % len(FORMATO_SEQUENCIA)]
    bloco_idx += 1

    # Duração do bloco: formato 5kg dura mais (mais lento p/ trocar), 400g mais curto
    if fmt_nome == '5kg-L01':
        duracao_bloco_h = random.uniform(6, 18)
    elif fmt_nome == '1kg-L01':
        duracao_bloco_h = random.uniform(4, 14)
    else:
        duracao_bloco_h = random.uniform(1.5, 6)

    fim_bloco = cursor + timedelta(hours=duracao_bloco_h)
    if fim_bloco > now - timedelta(hours=4):
        fim_bloco = now - timedelta(hours=4)

    # Produtos disponíveis neste formato
    skus_do_formato = produtos_por_formato[fmt_nome]
    if not skus_do_formato:
        cursor = fim_bloco + timedelta(minutes=random.uniform(10, 40))
        continue

    # Gerar micro-trocas dentro do bloco (troca entre SKUs do mesmo formato)
    t_atual = cursor
    while t_atual < fim_bloco:
        produto = random.choice(skus_do_formato)
        sucesso = random.random() > 0.10   # 90% sucesso

        eq_total = random.randint(3, 6)
        eq_sucesso = eq_total if sucesso else random.randint(0, eq_total - 1)
        tempo_exec = round(random.uniform(8.0, 35.0), 2)

        eh_primeira = sucesso and (produto.sku not in skus_ja_rodados)
        if sucesso:
            skus_ja_rodados.add(produto.sku)

        t = TrocaSKU(
            linha='L01',
            sku_trocado=produto.sku,
            descricao=produto.descricao,
            sucesso=sucesso,
            equipamentos_processados=eq_total,
            equipamentos_sucesso=eq_sucesso,
            equipamentos_falha=eq_total - eq_sucesso,
            tempo_execucao=tempo_exec,
            usuario=operador_user,
            ip_origem='192.168.1.50',
            primeira_rodada=eh_primeira,
            numero_op=f'OP-{random.randint(10000, 99999)}',
        )
        troca_records.append((t, t_atual))

        if eh_primeira:
            trocas_primeira_rodada[produto.sku] = (t, t_atual)

        # Próxima micro-troca: entre 30min e 4h dentro do bloco
        t_atual += timedelta(minutes=random.uniform(30, 240))

    # Pausa entre blocos (setup/limpeza): 20min a 2h
    cursor = fim_bloco + timedelta(minutes=random.uniform(20, 120))

print(f"  Gerando {len(troca_records)} registros de TrocaSKU...")

for t, dt in troca_records:
    t.save()
    TrocaSKU.objects.filter(pk=t.pk).update(data_hora=dt)

print(f"✓ {len(troca_records)} TrocaSKU inseridas em sessões de formato")

# ── Trocas recentes (últimas horas) — para alimentar pipeline de validação ────

trocas_recentes = {}
for sku, produto in produtos_por_sku.items():
    t = TrocaSKU.objects.create(
        linha='L01',
        sku_trocado=produto.sku,
        descricao=produto.descricao,
        sucesso=True,
        equipamentos_processados=4,
        equipamentos_sucesso=4,
        equipamentos_falha=0,
        tempo_execucao=round(random.uniform(10.0, 30.0), 2),
        usuario=operador_user,
        ip_origem='192.168.1.50',
        primeira_rodada=True,
        numero_op=f'OP-{random.randint(10000, 99999)}',
    )
    dt_recente = now - timedelta(hours=random.uniform(0.5, 3.0))
    TrocaSKU.objects.filter(pk=t.pk).update(data_hora=dt_recente)
    trocas_recentes[sku] = t

print("✓ Trocas recentes (primeira_rodada=True) para pipeline")

# ── LiberacaoSAP ──────────────────────────────────────────────────────────────
# SKU-1001, SKU-1002, SKU-1003 → liberados
# SKU-1004, SKU-1005 → aguardando SAP

lista_skus = list(produtos_por_sku.keys())   # ordem: 1001, 1003, 1002, 1004, 1005
skus_com_sap = ['SKU-1001', 'SKU-1002', 'SKU-1003']
obs_sap = {
    'SKU-1001': 'Lista técnica conferida e aprovada conforme BOM v2.3.',
    'SKU-1002': 'Revisão de ingredientes OK — sem alteração de fornecedor.',
    'SKU-1003': 'Lista técnica validada. Atenção: novo rótulo a partir desta OP.',
}

for sku in skus_com_sap:
    produto = produtos_por_sku[sku]
    lib = LiberacaoSAP.objects.create(
        produto=produto,
        linha=linha_l01,
        liberado_por=sap_user,
        observacao=obs_sap[sku],
    )
    dt_lib = now - timedelta(hours=random.uniform(1.0, 5.0))
    LiberacaoSAP.objects.filter(pk=lib.pk).update(liberado_em=dt_lib)

print(f"✓ LiberacaoSAP: {skus_com_sap}")
print(f"  Aguardando SAP: SKU-1004, SKU-1005")

# ── ValidacaoQualidade ────────────────────────────────────────────────────────
# SKU-1001 → aprovada
# SKU-1002 → pendente 40% do prazo
# SKU-1003 → expirada (timer estourado)

VALIDACOES = [
    ('SKU-1001', 30, 'aprovado',  0.55, True),
    ('SKU-1002', 45, 'pendente',  0.40, False),
    ('SKU-1003', 30, 'expirado',  1.20, False),
]

for sku, prazo, st, pct, aprovada in VALIDACOES:
    produto = produtos_por_sku[sku]
    troca = trocas_recentes[sku]
    kwargs = dict(
        troca=troca,
        produto=produto,
        linha=linha_l01,
        status=st,
        prazo_minutos=prazo,
        tempo_producao_acumulado_s=prazo * 60 * pct,
        opc_sinal_enviado=(st == 'expirado'),
    )
    if aprovada:
        kwargs['aprovado_por'] = qual_user
        kwargs['aprovado_em'] = now - timedelta(hours=1)

    vq = ValidacaoQualidade.objects.create(**kwargs)
    dt_vq = now - timedelta(hours=2.5 if aprovada else (2.0 if st == 'expirado' else 1.5))
    ValidacaoQualidade.objects.filter(pk=vq.pk).update(criada_em=dt_vq)

print("✓ ValidacaoQualidade:")
print("  SKU-1001 → APROVADA")
print("  SKU-1002 → PENDENTE (40% do prazo)")
print("  SKU-1003 → EXPIRADA (sinal OPC enviado)")

# ── Resumo ────────────────────────────────────────────────────────────────────
n_trocas = TrocaSKU.objects.filter(linha='L01').count()
n_sap    = LiberacaoSAP.objects.filter(linha=linha_l01).count()
n_vq     = ValidacaoQualidade.objects.filter(linha=linha_l01).count()

print("")
print("=" * 60)
print("  SEED v9.1 CONCLUÍDO — Linha L01")
print("=" * 60)
print(f"  TrocaSKU total      : {n_trocas}")
print(f"  Produtos associados : {len(SKUS_DEF)}")
print(f"  Formatos criados    : {len(FORMATOS_DEF)}")
print(f"  LiberacaoSAP        : {n_sap}")
print(f"  ValidacaoQualidade  : {n_vq}")
print("")
print("  Formatos e vazões:")
for fname, _, fgramas, fvazao in FORMATOS_DEF:
    print(f"    {fname:<20} {fgramas}g   {fvazao:.0f} kg/h")
print("")
print("  Credenciais de teste:")
print("    ana.sap          / demo1234  (grupo SAP)")
print("    carlos.qualidade / demo1234  (grupo Qualidade)")
print("    joao.operador    / demo1234  (sem grupo especial)")
print("=" * 60)
