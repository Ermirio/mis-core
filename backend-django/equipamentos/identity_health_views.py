"""
Healthcheck de identidade de equipamentos.

Endpoint que verifica a saúde do sistema de identidade global (Solução 2):
  - equipamentos sem slug (devem ser zero após migration 0041)
  - equipamentos sem uuid
  - códigos duplicados entre linhas (FAZ PARTE do design, mas listar para auditoria)
  - equipamentos sem coleta recente no Influx
  - pontos no Influx sem tag `equipment_slug` (dados pre-Onda 3)

Use no setup OT: roda 1x após import_images e antes do go-live.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from django.db.models import Count
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Equipamento
from .influx_helpers import get_influx_client

logger = logging.getLogger(__name__)


@api_view(['GET'])
@authentication_classes([])  # public health, sem auth
@permission_classes([AllowAny])
def identity_health(request):
    """GET /api/health/equipamentos/

    Retorna diagnóstico completo da identidade de equipamentos:

    ```json
    {
      "status": "ok"|"warn"|"error",
      "total_equipamentos": 20,
      "sem_slug": 0,                 // bloqueante
      "sem_uuid": 0,                 // bloqueante
      "codigos_duplicados": [],      // lista (linha, codigo) com >1 ocorrência
      "sem_coleta_recente": [...],   // sem pontos Influx nos últimos 5min
      "pontos_legacy_influx": 1234,  // pontos sem equipment_slug
      "recomendacoes": ["..."]
    }
    ```
    """
    out: dict[str, Any] = {
        'total_equipamentos': 0,
        'sem_slug': 0,
        'sem_slug_lista': [],
        'sem_uuid': 0,
        'codigos_duplicados': [],
        'sem_coleta_recente': [],
        'pontos_legacy_influx': 0,
        'recomendacoes': [],
    }
    issues_blocking = 0
    issues_warning = 0

    # 1. Equipamentos sem slug ou uuid (deveria ser ZERO)
    sem_slug = list(
        Equipamento.objects.filter(slug='').values('id', 'codigo', 'linha__codigo')
    )
    out['sem_slug'] = len(sem_slug)
    out['sem_slug_lista'] = sem_slug
    if sem_slug:
        issues_blocking += len(sem_slug)
        out['recomendacoes'].append(
            f'{len(sem_slug)} equipamento(s) sem slug. Rode: docker exec mis-core-django '
            f'python manage.py shell -c "from equipamentos.models import Equipamento; '
            f'[e.save() for e in Equipamento.objects.filter(slug=\\\"\\\")]"'
        )

    sem_uuid = Equipamento.objects.filter(uuid__isnull=True).count()
    out['sem_uuid'] = sem_uuid
    if sem_uuid:
        issues_blocking += sem_uuid
        out['recomendacoes'].append(
            f'{sem_uuid} equipamento(s) sem UUID — execute novamente a migration 0041.'
        )

    # 2. Códigos duplicados entre linhas (design legítimo, mas auditável)
    dups = (
        Equipamento.objects.values('codigo')
        .annotate(n=Count('id'))
        .filter(n__gt=1)
        .order_by('-n')
    )
    for d in dups:
        ocorrencias = list(
            Equipamento.objects.filter(codigo=d['codigo'])
            .values('id', 'slug', 'linha__codigo', 'linha__nome', 'nome')
        )
        out['codigos_duplicados'].append({
            'codigo': d['codigo'],
            'n_ocorrencias': d['n'],
            'equipamentos': ocorrencias,
        })

    # 3. Total geral
    out['total_equipamentos'] = Equipamento.objects.count()

    # 4. Coletas no Influx — quais equipamentos sumiram?
    try:
        client = get_influx_client()
        rs = client.query(
            'SELECT last(estado_maquina) FROM production '
            'WHERE time > now() - 5m GROUP BY "equipment_slug"'
        )
        slugs_ativos = set()
        for (_, tags), _pts in rs.items():
            if tags and tags.get('equipment_slug'):
                slugs_ativos.add(tags['equipment_slug'])

        sem_coleta = []
        for eq in Equipamento.objects.filter(status='ATIVO').select_related('linha'):
            if eq.slug and eq.slug not in slugs_ativos:
                sem_coleta.append({
                    'id': eq.id,
                    'slug': eq.slug,
                    'nome': eq.nome,
                    'linha': eq.linha.codigo if eq.linha else None,
                })
        out['sem_coleta_recente'] = sem_coleta
        if sem_coleta:
            issues_warning += len(sem_coleta)

        # 5. Pontos Influx ainda sem equipment_slug (legacy)
        try:
            rs2 = client.query(
                'SELECT COUNT(estado_maquina) FROM production '
                'WHERE time > now() - 1h '
                "AND equipment_slug = ''"
            )
            pts = list(rs2.get_points())
            if pts:
                out['pontos_legacy_influx'] = int(pts[0].get('count') or 0)
        except Exception:
            pass

    except Exception as e:
        logger.warning("identity_health: falha ao consultar Influx: %s", e)
        out['recomendacoes'].append(f'InfluxDB indisponível: {e}')
        issues_warning += 1

    # Status final
    if issues_blocking > 0:
        out['status'] = 'error'
    elif issues_warning > 0:
        out['status'] = 'warn'
    else:
        out['status'] = 'ok'
        out['recomendacoes'].append('Identidade global de equipamentos OK.')

    return Response(out)


# Mapeamento canônico dos estados que o sistema reconhece. Espelha
# `EstadoEquipamento` no models.py + códigos especiais (0, 999).
ESTADOS_CANONICOS = {
    0: 'Outro/Idle',
    1: 'Produzindo (RUN)',
    2: 'Aguardando equipamento anterior',
    3: 'Bloqueado próximo',
    4: 'Falha',
    5: 'Setup / Troca SKU',
    6: 'Teste de Projeto',
    7: 'Aguardando manutenção',
    8: 'Manutenção',
    9: 'Falta de material',
    10: 'Outro (reservado)',
    11: 'Partindo',
    12: 'Aguardando condições',
    13: 'Parando',
    999: 'Offline (PLC sem comunicação)',
}


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def estados_clp_health(request):
    """GET /api/health/estados-clp/?since=24h&linha=L01

    Confronta os estados que o CLP REALMENTE escreveu no Influx contra a
    lista canônica que o MIS reconhece. Ajuda a detectar:
      - PLC com classificação de estado incompleta (não envia "Partindo")
      - Mapeamento OPC errado (envia código fora do range conhecido)
      - Linha/equipamento sem nenhuma transição de estado em N horas

    Query params:
      since: janela (24h, 7d, 30d). Default: 24h.
      linha: opcional — filtrar por código de linha.

    Resposta:
      {
        "since": "24h",
        "linha": "L01" | "todas",
        "estados_canonicos": {0: "Outro/Idle", ...},
        "estados_recebidos": [
            {"codigo": 1, "label": "Produzindo (RUN)", "pontos": 138863},
            ...
        ],
        "estados_ausentes": [
            {"codigo": 5,  "label": "Setup / Troca SKU"},
            {"codigo": 11, "label": "Partindo"},
            ...
        ],
        "estados_desconhecidos": [
            {"codigo": 42, "pontos": 5}  // PLC enviou algo fora do canônico
        ],
        "status": "ok" | "warn",
        "recomendacoes": [...]
      }
    """
    since = request.query_params.get('since', '24h')
    linha = request.query_params.get('linha')

    where_extra = f"AND \"line\" = '{linha}' " if linha else ''
    sql = (
        f"SELECT \"estado_maquina\" FROM \"production\" "
        f"WHERE time > now() - {since} {where_extra}"
    )

    try:
        client = get_influx_client()
        rs = client.query(sql)
        contagem: dict[int, int] = {}
        for p in rs.get_points():
            v = p.get('estado_maquina')
            if v is None:
                continue
            try:
                k = int(float(v))
            except (TypeError, ValueError):
                continue
            contagem[k] = contagem.get(k, 0) + 1
    except Exception as e:
        return Response({
            'error': f'Falha ao consultar Influx: {e}',
        }, status=500)

    estados_recebidos = []
    estados_desconhecidos = []
    for codigo, n in sorted(contagem.items()):
        if codigo in ESTADOS_CANONICOS:
            estados_recebidos.append({
                'codigo': codigo,
                'label': ESTADOS_CANONICOS[codigo],
                'pontos': n,
            })
        else:
            estados_desconhecidos.append({'codigo': codigo, 'pontos': n})

    codigos_recebidos = set(contagem.keys())
    # Considera ausentes apenas os estados "produtivos" — 999 (Offline)
    # não é esperado em operação normal, e 10 é reservado.
    codigos_esperados = set(ESTADOS_CANONICOS.keys()) - {10, 999}
    codigos_ausentes = codigos_esperados - codigos_recebidos
    estados_ausentes = [
        {'codigo': c, 'label': ESTADOS_CANONICOS[c]}
        for c in sorted(codigos_ausentes)
    ]

    recs = []
    if estados_desconhecidos:
        recs.append(
            f'PLC enviando códigos fora do mapeamento: '
            f'{[e["codigo"] for e in estados_desconhecidos]}. '
            f'Verifique se a programação do PLC corresponde ao vocabulário do MIS '
            f'(equipamentos/models.py:EstadoEquipamento).'
        )
    if estados_ausentes:
        partindo = any(e['codigo'] == 11 for e in estados_ausentes)
        setup = any(e['codigo'] == 5 for e in estados_ausentes)
        if partindo or setup:
            recs.append(
                f'Estados críticos ausentes nos últimos {since}: '
                f'{[e["codigo"] for e in estados_ausentes]}. '
                f'Estados de TRANSIÇÃO (Partindo/Setup/Parando) são onde '
                f'mais costuma haver descarte — se o PLC não os reporta, '
                f'a análise de descarte fica enviesada.'
            )
        else:
            recs.append(
                f'Estados não observados (pode ser normal): '
                f'{[e["codigo"] for e in estados_ausentes]}.'
            )

    status_str = 'ok'
    if estados_desconhecidos:
        status_str = 'warn'
    if any(e['codigo'] in (11, 5, 13) for e in estados_ausentes):
        status_str = 'warn'

    return Response({
        'since': since,
        'linha': linha or 'todas',
        'estados_canonicos': ESTADOS_CANONICOS,
        'estados_recebidos': estados_recebidos,
        'estados_ausentes': estados_ausentes,
        'estados_desconhecidos': estados_desconhecidos,
        'total_pontos': sum(contagem.values()),
        'status': status_str,
        'recomendacoes': recs or ['Mapeamento PLC↔MIS OK.'],
    })


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def contadores_influx_health(request):
    """GET /api/health/contadores-influx/?linha=L10&since=24h&equipamento=E001

    Diagnóstico de glitches em contadores monotônicos do CLP.

    O CLP escreve `refugo_turno_acumulado` e `producao_turno_acumulada`
    como contadores que só sobem dentro do turno. Em condições reais,
    o coletor às vezes lê `0` entre leituras válidas (timeout OPC,
    falha transitória de comunicação), formando padrões como:

        ... 100 → 102 → 105 → 0 → 108 → 110 ...
                            (glitch)

    Sem proteção, um algoritmo ingênuo somaria `+108` na recuperação,
    inflando o total. Este endpoint conta os glitches por equipamento
    e estima o impacto, para validar se a queda no descarte calculado
    após o fix do high-watermark é consistente com o número de glitches
    observado.

    Query params:
      linha:        opcional — filtra por código de linha (ex: L10).
      equipamento:  opcional — código do equipamento (ex: E001).
      since:        janela de tempo (default: 24h).

    Resposta:
      {
        "linha": "L10" | "todas",
        "equipamento": "E001" | "todos",
        "since": "24h",
        "equipamentos": [
          {
            "slug": "L10.E001",
            "linha": "L10",
            "equipamento": "E001",
            "refugo_turno": {
              "pontos_total": 12453,
              "zero_glitches": 7,         // quedas a 0 sem reset legitimo
              "resets_legitimos": 3,      // viradas de turno
              "incrementos_fantasma_estimados": 854,
              "valor_atual": 242,
              "pico_observado": 1097
            },
            "producao_turno": { ... mesma estrutura ... }
          },
          ...
        ],
        "total_glitches": 14,
        "status": "ok" | "warn",
        "recomendacoes": [...]
      }
    """
    since = request.query_params.get('since', '24h')
    linha = request.query_params.get('linha')
    equipamento = request.query_params.get('equipamento')

    where_parts = [f"time > now() - {since}"]
    if linha:
        where_parts.append(f"\"line\" = '{linha}'")
    if equipamento:
        where_parts.append(f"\"equipment\" = '{equipamento}'")
    where_sql = ' AND '.join(where_parts)

    sql = (
        'SELECT "refugo_turno_acumulado", "producao_turno_acumulada", '
        '"equipment_slug", "equipment", "line" '
        'FROM "production" '
        f'WHERE {where_sql} '
        'ORDER BY time ASC'
    )

    try:
        client = get_influx_client()
        rs = client.query(sql)
        points = list(rs.get_points())
    except Exception as e:
        return Response({
            'error': f'Falha ao consultar Influx: {e}',
        }, status=500)

    # Agrupa por slug (com fallback para equipment+line)
    series: dict[str, list[dict]] = {}
    for p in points:
        slug = p.get('equipment_slug') or f"{p.get('line') or '?'}.{p.get('equipment') or '?'}"
        series.setdefault(slug, []).append(p)

    resultado = []
    total_glitches = 0
    total_fantasmas_refugo = 0
    total_fantasmas_prod = 0

    def analisar_contador(pts, field):
        """Conta glitches e estima incrementos fantasmas para um contador."""
        zero_glitches = 0
        resets_legitimos = 0
        fantasmas = 0
        pico = 0.0
        valor_atual = 0.0
        last = None
        for p in pts:
            v = p.get(field)
            if v is None:
                continue
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            valor_atual = v
            if v > pico:
                pico = v
            if last is not None:
                # Caracterização:
                # - v == 0 e last > 10  → glitch quase certo (zero transitório)
                # - v < last * 0.1     → queda drástica (reset ou glitch grave)
                # - v < last * 0.5     → queda parcial suspeita
                if v == 0 and last > 10:
                    zero_glitches += 1
                elif last > 0 and v < last * 0.1:
                    # Pode ser virada de turno legítima.
                    resets_legitimos += 1
                elif last > 0 and v < last:
                    # Queda moderada — provavelmente glitch que recupera.
                    # Algoritmo antigo (_counter_delta) somaria `v` no
                    # próximo ponto crescente, então conta como fantasma
                    # estimado.
                    fantasmas += int(last - v)
            last = v
        return {
            'pontos_total': len(pts),
            'zero_glitches': zero_glitches,
            'resets_legitimos': resets_legitimos,
            'incrementos_fantasma_estimados': fantasmas,
            'valor_atual': round(valor_atual, 2),
            'pico_observado': round(pico, 2),
        }

    for slug in sorted(series.keys()):
        pts = series[slug]
        sample = pts[0] if pts else {}
        refugo_stats = analisar_contador(pts, 'refugo_turno_acumulado')
        prod_stats = analisar_contador(pts, 'producao_turno_acumulada')
        total_glitches += refugo_stats['zero_glitches'] + prod_stats['zero_glitches']
        total_fantasmas_refugo += refugo_stats['incrementos_fantasma_estimados']
        total_fantasmas_prod += prod_stats['incrementos_fantasma_estimados']
        resultado.append({
            'slug': slug,
            'linha': sample.get('line'),
            'equipamento': sample.get('equipment'),
            'refugo_turno': refugo_stats,
            'producao_turno': prod_stats,
        })

    recs = []
    status_str = 'ok'
    if total_glitches > 0:
        status_str = 'warn'
        recs.append(
            f'Detectados {total_glitches} zero-glitches nos contadores. '
            f'O fix high-watermark (waste_dashboard_views._counter_increment_pk) '
            f'evita que esses glitches inflem os deltas. '
            f'Estimativa de inflação evitada: ~{total_fantasmas_refugo} unidades '
            f'de refugo, ~{total_fantasmas_prod} unidades de produção.'
        )
    if not resultado:
        recs.append('Nenhum ponto encontrado na janela. Verifique se o coletor está rodando.')

    return Response({
        'linha': linha or 'todas',
        'equipamento': equipamento or 'todos',
        'since': since,
        'equipamentos': resultado,
        'total_glitches': total_glitches,
        'total_fantasmas_estimados_refugo': total_fantasmas_refugo,
        'total_fantasmas_estimados_producao': total_fantasmas_prod,
        'status': status_str,
        'recomendacoes': recs or ['Sem glitches detectados — contadores limpos.'],
    })
