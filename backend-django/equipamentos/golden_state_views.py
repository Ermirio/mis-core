"""
Golden State — "Receita de Ouro" da linha.

Conceito
--------
Para um SKU específico rodando na linha, encontrar AUTOMATICAMENTE as
melhores corridas históricas (janelas de ouro) e expor a "receita" que
fez aquele desempenho — combinação de valores das variáveis marcadas
como `golden_state=True` nos modelos Sensor/TagColeta.

A janela de ouro é catalogada como `GoldenStateRun`:
  - AUTO: signal pós-fechamento de turno detectou score alto e gravou.
  - MANUAL: coordenador clicou "Capturar momento" e definiu a janela.

Score combinado:
  - TPH alto (50%)
  - Refugo baixo (30%)
  - Estabilidade (20%) - proxy: performance consistente.

Comparando o estado ATUAL contra a receita derivada dos runs, expõe:
  - Score de aderência (0-100)
  - Quais variáveis estão dentro/fora da faixa de ouro
  - Quanto tempo fora
  - Calendário de 30 dias de aderência por dia.
"""
from __future__ import annotations

import logging
import math
import statistics
from datetime import datetime, timedelta
from typing import Any

import pytz
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import (
    LinhaProducao, Equipamento, Sensor, TagColeta, MetricaProducao,
    GoldenStateRun, GoldenStateVarSnapshot,
)
from .influx_helpers import get_influx_client

logger = logging.getLogger(__name__)
TZ = pytz.timezone('America/Sao_Paulo')


def _golden_variables(linha: LinhaProducao) -> list[dict]:
    """Lista variáveis golden da linha (sensores + tags)."""
    from django.db.models import Q
    out = []
    sensores = Sensor.objects.filter(
        golden_state=True, ativo=True
    ).filter(
        Q(linha=linha) | Q(equipamento__linha=linha)
    ).select_related('equipamento')
    for s in sensores:
        out.append({
            'origem': 'sensor',
            'id': s.id,
            'sensor_id': s.id,
            'tag_id': None,
            'codigo': s.codigo,
            'nome': s.nome,
            'tag_influx': s.tag_influxdb,
            'unidade': s.unidade or '',
            'lsl': s.lsl,
            'usl': s.usl,
            'nominal': s.nominal,
            'equipamento_codigo': s.equipamento.codigo if s.equipamento else None,
            'equipamento_nome': s.equipamento.nome if s.equipamento else linha.nome,
        })
    tags = TagColeta.objects.filter(
        golden_state=True, ativa=True,
        equipamento__linha=linha,
    ).select_related('equipamento')
    for t in tags:
        out.append({
            'origem': 'tag',
            'id': t.id,
            'sensor_id': None,
            'tag_id': t.id,
            'codigo': t.nome_metrica,
            'nome': t.nome_metrica,
            'tag_influx': t.nome_metrica,
            'unidade': t.unidade or '',
            'lsl': None,
            'usl': None,
            'nominal': None,
            'equipamento_codigo': t.equipamento.codigo,
            'equipamento_nome': t.equipamento.nome,
        })
    return out


def _influx_percentis(tag_influx: str, equipamento_codigo: str | None,
                      inicio: datetime, fim: datetime) -> dict:
    """Calcula p10/p50/p90 de uma variável em uma janela."""
    client = get_influx_client()
    where_eq = f"\"equipment\" = '{equipamento_codigo}'" if equipamento_codigo else ''
    start = inicio.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
    end = fim.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
    q = (
        f"SELECT mean({tag_influx}) as v FROM production "
        f"WHERE {where_eq} AND time >= '{start}' AND time <= '{end}' "
        f"GROUP BY time(5m) fill(none)"
    )
    valores: list[float] = []
    try:
        pts = list(client.query(q).get_points())
        for p in pts:
            v = p.get('v')
            if v is None:
                continue
            try:
                fv = float(v)
                if math.isnan(fv):
                    continue
                valores.append(fv)
            except (TypeError, ValueError):
                continue
    except Exception as e:
        logger.warning("Influx percentis falhou para %s: %s", tag_influx, e)

    if not valores:
        return {'p10': None, 'p50': None, 'p90': None, 'n': 0}
    valores.sort()
    n = len(valores)

    def pct(p):
        k = max(0, min(n - 1, int(round((p / 100.0) * (n - 1)))))
        return valores[k]

    return {
        'p10': round(pct(10), 3),
        'p50': round(pct(50), 3),
        'p90': round(pct(90), 3),
        'n': n,
    }


def _aplicar_tolerancia(receita: dict[str, dict], tolerancia: str) -> dict[str, dict]:
    """Ajusta a faixa de ouro segundo a tolerância escolhida pelo usuário.

       - 'estreita': faixa = metade da amplitude p10-p90 (~ p25-p75).
       - 'padrao':   faixa = p10..p90 (como salvo).
       - 'larga':    faixa = 1.5x amplitude (afrouxa).

    A `receita` é o dict {tag_influx: {p10, p50, p90, n, n_runs}}. Devolve
    novo dict com os mesmos campos, recalibrando p10 e p90 conforme a
    tolerância. p50 e n permanecem.
    """
    fator = {'estreita': 0.5, 'padrao': 1.0, 'larga': 1.5}.get(tolerancia, 1.0)
    if fator == 1.0:
        return receita
    out = {}
    for tag, r in receita.items():
        p10, p50, p90 = r.get('p10'), r.get('p50'), r.get('p90')
        if p10 is None or p50 is None or p90 is None:
            out[tag] = r
            continue
        baixo = p50 - (p50 - p10) * fator
        alto = p50 + (p90 - p50) * fator
        out[tag] = {**r, 'p10': round(baixo, 3), 'p90': round(alto, 3)}
    return out


def _metricas_janela(linha: LinhaProducao, inicio: datetime,
                     fim: datetime) -> dict:
    """Calcula TPH/refugo%/OEE médios na janela — combina Influx e MySQL."""
    client = get_influx_client()
    line_code = linha.codigo
    s = inicio.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
    e = fim.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
    out = {'tph_medio': None, 'refugo_pct': None, 'oee_medio': None}
    try:
        # TPH: max(toneladas_turno) / horas_janela (aproximação)
        q_tons = (
            f"SELECT max(toneladas_turno) as ton FROM production "
            f"WHERE \"line\" = '{line_code}' AND time >= '{s}' AND time <= '{e}'"
        )
        pts = list(client.query(q_tons).get_points())
        toneladas = float(pts[0]['ton'] or 0) if pts else 0
        horas = max(0.1, (fim - inicio).total_seconds() / 3600.0)
        if toneladas > 0:
            out['tph_medio'] = round(toneladas / horas, 2)

        q_oee = (
            f"SELECT mean(oee_realtime) as o FROM production "
            f"WHERE \"line\" = '{line_code}' AND time >= '{s}' AND time <= '{e}'"
        )
        pts2 = list(client.query(q_oee).get_points())
        if pts2 and pts2[0].get('o') is not None:
            o = float(pts2[0]['o'])
            if 0 < o <= 1.5:
                o *= 100
            out['oee_medio'] = round(o, 1)

        # Refugo: aproxima via descarte / produção
        q_desc = (
            f"SELECT max(descarte_turno_acumulado) as d, "
            f"max(producao_turno_acumulada) as p FROM production "
            f"WHERE \"line\" = '{line_code}' AND time >= '{s}' AND time <= '{e}'"
        )
        pts3 = list(client.query(q_desc).get_points())
        if pts3:
            d = float(pts3[0].get('d') or 0)
            p = float(pts3[0].get('p') or 0)
            if p > 0:
                out['refugo_pct'] = round((d / (p + d)) * 100, 2)
    except Exception as e_x:
        logger.warning("metricas_janela falhou: %s", e_x)
    return out


def _score_janela(tph: float | None, refugo_pct: float | None,
                  oee: float | None) -> float | None:
    """Score 0-100. 50% TPH (normalizado vs 20t/h ref), 30% qualidade,
    20% OEE. Sem dado → None."""
    if tph is None and refugo_pct is None and oee is None:
        return None
    n_tph = min(1.0, (tph or 0) / 20.0)
    n_qual = max(0.0, 1.0 - (refugo_pct or 0) / 10.0)
    n_oee = (oee or 0) / 100.0
    score = (0.5 * n_tph + 0.3 * n_qual + 0.2 * n_oee) * 100
    return round(max(0.0, min(100.0, score)), 1)


def _capturar_run(linha: LinhaProducao, inicio: datetime, fim: datetime,
                  fonte: str = GoldenStateRun.Fonte.MANUAL,
                  nome: str = '', sku_codigo: str | None = None,
                  formato_gramas: float | None = None,
                  observacoes: str = '', criado_por: str = '') -> GoldenStateRun:
    """Calcula métricas e percentis da janela e persiste como GoldenStateRun.
    Idempotente para AUTO (constraint unique).
    """
    metricas = _metricas_janela(linha, inicio, fim)
    score = _score_janela(metricas['tph_medio'], metricas['refugo_pct'], metricas['oee_medio'])

    # Se o usuário não informou formato, tenta inferir do Influx na janela.
    if formato_gramas is None:
        try:
            client = get_influx_client()
            s = inicio.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
            e = fim.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
            q = (
                f"SELECT last(formato_gramas) as f FROM production "
                f"WHERE \"line\" = '{linha.codigo}' AND time >= '{s}' AND time <= '{e}'"
            )
            pts = list(client.query(q).get_points())
            if pts and pts[0].get('f') is not None:
                formato_gramas = float(pts[0]['f'])
        except Exception:
            pass

    with transaction.atomic():
        run = GoldenStateRun.objects.create(
            linha=linha,
            nome=nome or f"{inicio.astimezone(TZ).strftime('%d/%m %H:%M')}–{fim.astimezone(TZ).strftime('%H:%M')}",
            sku_codigo=sku_codigo,
            formato_gramas=formato_gramas,
            fonte=fonte,
            inicio=inicio,
            fim=fim,
            score=score,
            tph_medio=metricas['tph_medio'],
            refugo_pct=metricas['refugo_pct'],
            oee_medio=metricas['oee_medio'],
            observacoes=observacoes,
            criado_por=criado_por,
        )
        # Snapshots por variável golden
        for v in _golden_variables(linha):
            pct = _influx_percentis(v['tag_influx'], v['equipamento_codigo'], inicio, fim)
            if pct['n'] == 0:
                continue
            GoldenStateVarSnapshot.objects.create(
                run=run,
                sensor_id=v.get('sensor_id'),
                tag_id=v.get('tag_id'),
                nome_amigavel=v['nome'],
                tag_influx=v['tag_influx'],
                unidade=v['unidade'],
                equipamento_codigo=v['equipamento_codigo'] or '',
                p10=pct['p10'],
                p50=pct['p50'],
                p90=pct['p90'],
                n_amostras=pct['n'],
            )
    return run


def _agregar_receita_dos_runs(linha: LinhaProducao,
                              filtro: str,
                              sku: str | None,
                              formato: float | None,
                              dias: int) -> tuple[dict[str, dict], list[GoldenStateRun]]:
    """Pega os runs ATIVOS e agrega seus snapshots.

    O filtro define o escopo da agregação:
      - 'sku'     → só runs com mesmo sku_codigo
      - 'formato' → só runs com mesmo formato_gramas (±2g)
      - 'todos'   → qualquer run

    Quando o escopo escolhido não traz runs, faz fallback para 'todos' para
    não mostrar a tela vazia. Retorna também a lista de runs usados.
    """
    corte = timezone.now() - timedelta(days=dias)
    qs = GoldenStateRun.objects.filter(
        linha=linha, ativo=True, inicio__gte=corte,
    ).prefetch_related('variaveis').order_by('-score', '-criado_em')

    if filtro == 'sku' and sku:
        candidatos = list(qs.filter(sku_codigo=sku)[:5])
    elif filtro == 'formato' and formato is not None:
        candidatos = list(qs.filter(
            formato_gramas__gte=formato - 2,
            formato_gramas__lte=formato + 2,
        )[:5])
    else:
        candidatos = list(qs[:5])

    # Fallback: se o escopo solicitado veio vazio, tenta 'todos'.
    if not candidatos and filtro != 'todos':
        candidatos = list(qs[:5])

    if not candidatos:
        return {}, []

    # Agrega: mediana dos p10/p50/p90 por tag_influx.
    bag: dict[str, dict[str, list[float]]] = {}
    for run in candidatos:
        for snap in run.variaveis.all():
            d = bag.setdefault(snap.tag_influx, {'p10': [], 'p50': [], 'p90': [], 'n': []})
            d['p10'].append(snap.p10)
            d['p50'].append(snap.p50)
            d['p90'].append(snap.p90)
            d['n'].append(snap.n_amostras)

    agreg = {}
    for tag, vals in bag.items():
        agreg[tag] = {
            'p10': round(statistics.median(vals['p10']), 3),
            'p50': round(statistics.median(vals['p50']), 3),
            'p90': round(statistics.median(vals['p90']), 3),
            'n': sum(vals['n']),
            'n_runs': len(vals['p10']),
        }
    return agreg, candidatos


def _node_id_da_variavel(v: dict) -> str | None:
    """Resolve node_id OPC de uma variável golden (sensor ou tag).
    Sensor não tem node_id direto: usa a TagColeta correspondente
    (mesmo equipamento, mesma tag_influxdb).
    """
    if v.get('origem') == 'tag':
        try:
            t = TagColeta.objects.get(pk=v['id'])
            return t.node_id or None
        except TagColeta.DoesNotExist:
            return None
    if v.get('origem') == 'sensor':
        try:
            s = Sensor.objects.get(pk=v['id'])
            if not s.equipamento_id:
                return None
            tag = TagColeta.objects.filter(
                equipamento_id=s.equipamento_id,
                nome_metrica=s.tag_influxdb,
            ).first()
            return tag.node_id if tag and tag.node_id else None
        except Sensor.DoesNotExist:
            return None
    return None


def _valor_atual_e_drift(variaveis: list[dict],
                          receita: dict[str, dict]) -> list[dict]:
    """Para cada variável golden lê último valor (1h) e calcula status vs
    faixa de ouro da receita agregada."""
    client = get_influx_client()
    out = []
    for v in variaveis:
        where_eq = f"\"equipment\" = '{v['equipamento_codigo']}'" if v['equipamento_codigo'] else ''
        q = (
            f"SELECT last({v['tag_influx']}) as v FROM production "
            f"WHERE {where_eq} AND time > now() - 1h"
        )
        atual = None
        try:
            pts = list(client.query(q).get_points())
            if pts and pts[0].get('v') is not None:
                atual = float(pts[0]['v'])
        except Exception:
            pass

        faixa = receita.get(v['tag_influx'], {})
        p10 = faixa.get('p10')
        p50 = faixa.get('p50')
        p90 = faixa.get('p90')

        # Tempo fora nas últimas 4h
        tempo_fora_min = None
        if p10 is not None and p90 is not None:
            try:
                q4 = (
                    f"SELECT mean({v['tag_influx']}) as v FROM production "
                    f"WHERE {where_eq} AND time > now() - 4h "
                    f"GROUP BY time(5m) fill(none)"
                )
                pts4 = list(client.query(q4).get_points())
                fora = sum(1 for p in pts4 if p.get('v') is not None
                           and (float(p['v']) < p10 or float(p['v']) > p90))
                tempo_fora_min = fora * 5
            except Exception:
                pass

        if atual is None or p10 is None or p90 is None:
            status = 'sem_dado'
            drift_pct = None
        elif p10 <= atual <= p90:
            status = 'ok'
            drift_pct = round(((atual - p50) / p50 * 100) if p50 else 0, 2)
        else:
            amp = max(1e-9, p90 - p10)
            dist = max(p10 - atual, atual - p90, 0)
            status = 'warn' if dist <= 0.05 * amp else 'bad'
            drift_pct = round(((atual - p50) / p50 * 100) if p50 else 0, 2)

        out.append({
            **v,
            'valor_atual': round(atual, 3) if atual is not None else None,
            'ouro_min': p10,
            'ouro_max': p90,
            'ouro_ideal': p50,
            'amostras_ouro': faixa.get('n', 0),
            'n_runs_referencia': faixa.get('n_runs', 0),
            'status': status,
            'drift_pct': drift_pct,
            'tempo_fora_min': tempo_fora_min,
            'tem_node_id': _node_id_da_variavel(v) is not None,
        })
    return out


def _calendario_aderencia(linha: LinhaProducao, variaveis: list[dict],
                          receita: dict[str, dict], dias: int = 30) -> list[dict]:
    if not variaveis or not receita:
        return []
    client = get_influx_client()
    fim = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    inicio = fim - timedelta(days=dias)
    out = []
    dia = inicio
    while dia <= fim:
        proxima = dia + timedelta(days=1)
        s = dia.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
        e = proxima.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
        scores_var = []
        for v in variaveis:
            faixa = receita.get(v['tag_influx'], {})
            p10, p90 = faixa.get('p10'), faixa.get('p90')
            if p10 is None or p90 is None:
                continue
            where_eq = f"\"equipment\" = '{v['equipamento_codigo']}'" if v['equipamento_codigo'] else ''
            q = (
                f"SELECT mean({v['tag_influx']}) as v FROM production "
                f"WHERE {where_eq} AND time >= '{s}' AND time < '{e}' "
                f"GROUP BY time(30m) fill(none)"
            )
            try:
                pts = list(client.query(q).get_points())
                vals = [p['v'] for p in pts if p.get('v') is not None]
                if not vals:
                    continue
                dentro = sum(1 for x in vals if p10 <= float(x) <= p90)
                scores_var.append((dentro / len(vals)) * 100)
            except Exception:
                continue
        if scores_var:
            out.append({
                'data': dia.date().isoformat(),
                'score': round(statistics.mean(scores_var), 1),
                'n_vars': len(scores_var),
            })
        else:
            out.append({'data': dia.date().isoformat(), 'score': None, 'n_vars': 0})
        dia = proxima
    return out


def _sku_atual(linha: LinhaProducao) -> str | None:
    try:
        client = get_influx_client()
        q = (
            "SELECT last(sku_codigo) as sku FROM production "
            f"WHERE \"line\" = '{linha.codigo}' AND time > now() - 1h"
        )
        pts = list(client.query(q).get_points())
        if pts and pts[0].get('sku'):
            return str(pts[0]['sku'])
    except Exception:
        pass
    return None


def _formato_atual(linha: LinhaProducao) -> float | None:
    try:
        client = get_influx_client()
        q = (
            "SELECT last(formato_gramas) as f FROM production "
            f"WHERE \"line\" = '{linha.codigo}' AND time > now() - 1h"
        )
        pts = list(client.query(q).get_points())
        if pts and pts[0].get('f') is not None:
            return float(pts[0]['f'])
    except Exception:
        pass
    return None


# Mapeamento de tolerância → par de percentis usado na faixa de ouro.
# "estreita" cobra o operador para ficar bem perto da mediana das corridas;
# "padrao" é o intervalo natural p10-p90 (90% das amostras das corridas
# de ouro caíam aqui); "larga" abre para min-max real.
_TOLERANCIA_PCT = {
    'estreita': (25, 75),
    'padrao': (10, 90),
    'larga': (0, 100),
}


# =========================================================================
# Endpoint principal: GET /api/linhas/<id>/golden-state/
# =========================================================================

@api_view(['GET'])
def golden_state_linha(request, linha_id: int):
    """Retorna receita de ouro + status atual + calendário.

    Query params:
      - filtro: 'sku' | 'formato' | 'todos' (default: 'sku')
      - sku, formato: filtros do escopo
      - tolerancia: 'estreita' | 'padrao' | 'larga' (default: 'padrao')
      - dias: janela de busca de runs (default: 30)
    """
    try:
        linha = LinhaProducao.objects.get(pk=linha_id)
    except LinhaProducao.DoesNotExist:
        return Response({'detail': 'Linha não encontrada'}, status=404)

    sku = request.query_params.get('sku') or _sku_atual(linha)
    try:
        formato_param = request.query_params.get('formato')
        formato = float(formato_param) if formato_param else _formato_atual(linha)
    except (TypeError, ValueError):
        formato = _formato_atual(linha)
    filtro = request.query_params.get('filtro', 'sku')
    if filtro not in ('sku', 'formato', 'todos'):
        filtro = 'sku'
    tolerancia = request.query_params.get('tolerancia', 'padrao')
    if tolerancia not in _TOLERANCIA_PCT:
        tolerancia = 'padrao'
    dias = int(request.query_params.get('dias') or 30)

    variaveis = _golden_variables(linha)
    if not variaveis:
        return Response({
            'linha': linha.codigo,
            'linha_nome': linha.nome,
            'sku_atual': sku,
            'dias_referencia': dias,
            'variaveis': [],
            'janelas_referencia': [],
            'calendario': [],
            'ouro_score_atual': None,
            'mensagem': (
                'Nenhuma variável marcada como Golden State nesta linha. '
                'Marque sensores ou tags no admin para começar.'
            ),
        })

    receita, runs = _agregar_receita_dos_runs(linha, filtro, sku, formato, dias)
    receita = _aplicar_tolerancia(receita, tolerancia)

    janelas_ref = [{
        'id': r.id,
        'nome': r.nome,
        'data': r.inicio.astimezone(TZ).date().isoformat(),
        'inicio': r.inicio.isoformat(),
        'fim': r.fim.isoformat(),
        'sku_codigo': r.sku_codigo,
        'formato_gramas': float(r.formato_gramas) if r.formato_gramas is not None else None,
        'fonte': r.fonte,
        'fonte_label': r.get_fonte_display(),
        'score': r.score,
        'tph': r.tph_medio,
        'refugo_pct': r.refugo_pct,
        'oee': r.oee_medio,
        'observacoes': r.observacoes,
    } for r in runs]

    variaveis_status = _valor_atual_e_drift(variaveis, receita)
    calendario = _calendario_aderencia(linha, variaveis, receita, dias=dias)

    com_dado = [v for v in variaveis_status if v['status'] != 'sem_dado']
    if com_dado:
        ok = sum(1 for v in com_dado if v['status'] == 'ok')
        warn = sum(1 for v in com_dado if v['status'] == 'warn')
        score = ((ok + 0.5 * warn) / len(com_dado)) * 100
        score = round(score, 1)
    else:
        score = None

    # Resumo da captura automática (para a UI explicar o que faz)
    from django.conf import settings as dj_settings
    from decouple import config
    score_auto_min = int(config('GOLDEN_AUTO_SCORE_MIN', default=80))
    ultima_auto = GoldenStateRun.objects.filter(
        linha=linha, fonte=GoldenStateRun.Fonte.AUTO, ativo=True,
    ).order_by('-criado_em').first()

    return Response({
        'linha': linha.codigo,
        'linha_nome': linha.nome,
        'sku_atual': sku,
        'formato_atual': formato,
        'dias_referencia': dias,
        'filtro_aplicado': filtro,
        'tolerancia_aplicada': tolerancia,
        'ouro_score_atual': score,
        'janelas_referencia': janelas_ref,
        'variaveis': variaveis_status,
        'calendario': calendario,
        'auto_capture': {
            'ativo': True,
            'criterio': f'turnos fechados com OEE ≥ {score_auto_min}%',
            'ultima_captura': ultima_auto.criado_em.isoformat() if ultima_auto else None,
            'ultima_captura_nome': ultima_auto.nome if ultima_auto else None,
        },
        'mensagem': None if runs else (
            'Nenhuma corrida de referência catalogada ainda. '
            'Clique em "Capturar momento" quando a linha estiver rodando bem, '
            f'ou aguarde a detecção automática (OEE ≥ {score_auto_min}% no fechamento do turno).'
        ),
    })


# =========================================================================
# Endpoint de captura manual
# =========================================================================

@api_view(['POST'])
def golden_state_capturar(request, linha_id: int):
    """POST /api/linhas/<id>/golden-state/capturar/
    Body:
      {
        "nome": "Turno A 17/05",
        "inicio": "2026-05-17T14:00:00Z",  (opcional; default: agora-30min)
        "fim":    "2026-05-17T14:30:00Z",  (opcional; default: agora)
        "sku_codigo": "OMO 2400",          (opcional; default: SKU atual)
        "observacoes": "depois do ajuste"
      }
    """
    try:
        linha = LinhaProducao.objects.get(pk=linha_id)
    except LinhaProducao.DoesNotExist:
        return Response({'detail': 'Linha não encontrada'}, status=404)

    body = request.data or {}
    agora = timezone.now()
    try:
        fim = datetime.fromisoformat(body['fim'].replace('Z', '+00:00')) if body.get('fim') else agora
        inicio = (
            datetime.fromisoformat(body['inicio'].replace('Z', '+00:00'))
            if body.get('inicio') else (agora - timedelta(minutes=30))
        )
    except Exception:
        return Response({'detail': 'Datas inválidas (use ISO 8601)'}, status=400)

    if fim <= inicio:
        return Response({'detail': 'fim deve ser maior que inicio'}, status=400)
    if (fim - inicio) > timedelta(hours=12):
        return Response({'detail': 'Janela máxima: 12 horas'}, status=400)

    sku = body.get('sku_codigo') or _sku_atual(linha)
    nome = body.get('nome', '').strip()
    obs = body.get('observacoes', '').strip()
    try:
        formato = float(body['formato_gramas']) if body.get('formato_gramas') is not None else None
    except (TypeError, ValueError):
        formato = None

    if not _golden_variables(linha):
        return Response(
            {'detail': 'A linha não tem variáveis Golden State marcadas. '
                       'Marque ao menos uma no admin antes de capturar.'},
            status=400,
        )

    run = _capturar_run(
        linha, inicio, fim,
        fonte=GoldenStateRun.Fonte.MANUAL,
        nome=nome, sku_codigo=sku, formato_gramas=formato,
        observacoes=obs,
        criado_por=getattr(request.user, 'username', '') or '',
    )

    snaps = list(run.variaveis.all())
    return Response({
        'id': run.id,
        'nome': run.nome,
        'inicio': run.inicio.isoformat(),
        'fim': run.fim.isoformat(),
        'sku_codigo': run.sku_codigo,
        'formato_gramas': float(run.formato_gramas) if run.formato_gramas is not None else None,
        'fonte': run.fonte,
        'score': run.score,
        'tph_medio': run.tph_medio,
        'refugo_pct': run.refugo_pct,
        'oee_medio': run.oee_medio,
        'variaveis_capturadas': len(snaps),
        'mensagem': (
            f'Corrida capturada com {len(snaps)} variável(is). '
            'A receita já é considerada na aba.'
            if snaps else
            'Captura criada, mas nenhuma variável tinha amostras na janela. '
            'Verifique se o coletor estava rodando.'
        ),
    }, status=201)


# =========================================================================
# Endpoint para listar / desativar runs
# =========================================================================

@api_view(['GET', 'DELETE'])
def golden_state_runs(request, linha_id: int, run_id: int = None):
    """
    GET    /api/linhas/<id>/golden-state/runs/           → lista
    DELETE /api/linhas/<id>/golden-state/runs/<run_id>/  → desativa (soft delete)
    """
    try:
        linha = LinhaProducao.objects.get(pk=linha_id)
    except LinhaProducao.DoesNotExist:
        return Response({'detail': 'Linha não encontrada'}, status=404)

    if request.method == 'DELETE':
        if not run_id:
            return Response({'detail': 'run_id obrigatório'}, status=400)
        try:
            run = GoldenStateRun.objects.get(pk=run_id, linha=linha)
        except GoldenStateRun.DoesNotExist:
            return Response({'detail': 'Run não encontrado'}, status=404)
        run.ativo = False
        run.save(update_fields=['ativo'])
        return Response({'ok': True})

    runs = GoldenStateRun.objects.filter(linha=linha).order_by('-criado_em')[:50]
    out = []
    for r in runs:
        out.append({
            'id': r.id,
            'nome': r.nome,
            'data': r.inicio.astimezone(TZ).date().isoformat(),
            'inicio': r.inicio.isoformat(),
            'fim': r.fim.isoformat(),
            'sku_codigo': r.sku_codigo,
            'formato_gramas': float(r.formato_gramas) if r.formato_gramas is not None else None,
            'fonte': r.fonte,
            'fonte_label': r.get_fonte_display(),
            'score': r.score,
            'tph_medio': r.tph_medio,
            'refugo_pct': r.refugo_pct,
            'oee_medio': r.oee_medio,
            'observacoes': r.observacoes,
            'ativo': r.ativo,
            'criado_em': r.criado_em.isoformat(),
            'criado_por': r.criado_por,
            'n_variaveis': r.variaveis.count(),
        })
    return Response(out)


# =========================================================================
# Endpoint de aplicação ao CLP
# =========================================================================

@api_view(['POST'])
def golden_state_aplicar(request, linha_id: int):
    """POST /api/linhas/<id>/golden-state/aplicar/

    Body opcional:
      { "filtro": "sku|formato|todos", "tolerancia": "estreita|padrao|larga",
        "variaveis_ids": [123, 456] }  // se ausente, aplica todas com node_id

    Pega a mediana (p50) de cada variável golden da receita atual,
    monta comandos e ENFILEIRA via golden_state_queue. Apenas variáveis com
    `node_id` OPC configurado entram (o coletor escreve no CLP).

    Resposta:
      {
        "status": "queued"|"skipped",
        "batch_id": "...",
        "comandos": [...],
        "ignorados": [...]   // por que cada uma foi pulada
      }
    """
    import uuid
    from . import golden_state_queue as gs_queue

    try:
        linha = LinhaProducao.objects.get(pk=linha_id)
    except LinhaProducao.DoesNotExist:
        return Response({'detail': 'Linha não encontrada'}, status=404)

    body = request.data or {}
    filtro = body.get('filtro', 'sku')
    if filtro not in ('sku', 'formato', 'todos'):
        filtro = 'sku'
    tolerancia = body.get('tolerancia', 'padrao')
    sku = body.get('sku') or _sku_atual(linha)
    try:
        formato = float(body['formato']) if body.get('formato') is not None else _formato_atual(linha)
    except (TypeError, ValueError):
        formato = _formato_atual(linha)

    receita, runs = _agregar_receita_dos_runs(linha, filtro, sku, formato, dias=30)
    if not receita:
        return Response(
            {'status': 'skipped', 'detail': 'Sem receita catalogada para aplicar.'},
            status=400,
        )

    # Lista variáveis golden da linha
    vars_golden = _golden_variables(linha)
    var_filter = set(body.get('variaveis_ids') or [])

    comandos_por_eq: dict[str, list[dict]] = {}
    ignorados = []

    # Para mapear node_id, precisamos consultar Sensor/TagColeta direto.
    for v in vars_golden:
        if var_filter and v['id'] not in var_filter:
            continue
        r = receita.get(v['tag_influx'])
        if not r or r.get('p50') is None:
            ignorados.append({'nome': v['nome'], 'motivo': 'sem amostras na receita'})
            continue

        node_id = _node_id_da_variavel(v)
        if not node_id:
            ignorados.append({
                'nome': v['nome'],
                'motivo': 'sem Node ID OPC mapeado (cadastre no admin para habilitar escrita)',
            })
            continue

        eq_code = v['equipamento_codigo']
        if not eq_code:
            ignorados.append({'nome': v['nome'], 'motivo': 'sem equipamento associado'})
            continue
        comandos_por_eq.setdefault(eq_code, []).append({
            'tag': v['tag_influx'],
            'node_id': node_id,
            'value': float(r['p50']),
            'unidade': v.get('unidade', ''),
            'nome': v['nome'],
        })

    if not comandos_por_eq:
        return Response({
            'status': 'skipped',
            'detail': 'Nenhuma variável golden tem Node ID OPC configurado.',
            'ignorados': ignorados,
        }, status=400)

    # Um batch por equipamento (a fila do coletor espera 1 equipamento por batch).
    batches = []
    for eq_code, cmds in comandos_por_eq.items():
        batch_id = str(uuid.uuid4())
        gs_queue.add_command('GLOBAL', {
            'id': batch_id,
            'equipamento_codigo': eq_code,
            'commands': [{'tag': c['tag'], 'node_id': c['node_id'], 'value': c['value']} for c in cmds],
            'origem': 'golden_state_recipe',
            'linha_codigo': linha.codigo,
        })
        batches.append({
            'batch_id': batch_id,
            'equipamento_codigo': eq_code,
            'comandos': cmds,
        })

    return Response({
        'status': 'queued',
        'batches': batches,
        'total_comandos': sum(len(b['comandos']) for b in batches),
        'ignorados': ignorados,
        'origem_receita': {
            'filtro': filtro,
            'tolerancia': tolerancia,
            'n_runs': len(runs),
        },
    }, status=202)
