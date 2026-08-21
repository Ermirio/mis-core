"""
Histórico/versionamento do Node-RED — estilo Git interno.

Fluxo:
  1. Usuário clica Deploy no editor Node-RED.
  2. nginx faz mirror do POST /flows para POST /api/nodered/snapshot/.
  3. Esta view cria um NodeRedSnapshot com hash, autor (X-MIS-User),
     diff vs último snapshot e parent referência.
  4. Admin Django mostra timeline e permite restauração.

Restore:
  - Usuário clica "Restaurar para esta versão" no admin.
  - POST /api/nodered/restore/<id>/ pega o flows_json arquivado e faz
    POST http://mis-core-nodered:1880/flows (admin API) para reescrever.
  - Cria novo snapshot tipo RESTORE marcando o evento na timeline.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import time
from typing import Any

import requests
from django.conf import settings as dj_settings
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import NodeRedSnapshot

logger = logging.getLogger(__name__)

# httpAdminRoot do Node-RED é "/nodered" — a admin API mora aí, não na raiz.
NODERED_INTERNAL_BASE = 'http://mis-core-nodered:1880'
NODERED_ADMIN_API = f'{NODERED_INTERNAL_BASE}/nodered'

# Service-user para o Django conseguir falar com a admin API agora que
# adminAuth está ativo. Provisionado on-demand (lazy) na 1ª chamada,
# senha vem de env (preferido) ou gerada e persistida em arquivo dentro
# do container.
NODERED_INTERNAL_USERNAME = os.getenv('NODERED_INTERNAL_USERNAME', '_mis_internal_')

# Token cache em ARQUIVO (não só em memória do processo). Sem isso, cada
# gunicorn worker — e cada restart do Django — faria um novo /auth/token,
# poluindo o audit log do Node-RED com dezenas de `auth.login` por hora.
_TOKEN_CACHE_FILE = '/tmp/.mis_nodered_token'
_TOKEN_CACHE_MEM: dict[str, Any] = {'token': None, 'expires_at': 0.0}

# Cache curto para o projeto ativo — evita uma GET /projects em CADA
# deploy ou listagem. O projeto muda raramente; 10s é suficiente.
_PROJETO_ATIVO_CACHE: dict[str, Any] = {'value': '', 'expires_at': 0.0}
_PROJETO_ATIVO_TTL_S = 10

# Quando a feature Projects está ligada no Node-RED, o endpoint
# /nodered/projects retorna {active: "nome", projects: [...]}. Quando está
# desligada (ou no Node-RED legado), responde 404. Tratamos as duas
# situações como cidadãs de primeira classe — sem projeto significa
# "snapshot global".
_PROJECTS_PROBE_TIMEOUT_S = 3


def _hash_flows(flows: Any) -> str:
    """SHA-256 do JSON canônico — usado para deduplicação."""
    canonical = json.dumps(flows, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _internal_password() -> str:
    """Retorna a senha do service-user. Origem (em ordem):
      1. env NODERED_INTERNAL_PASSWORD (deploy controla);
      2. arquivo persistido `/data/.mis_internal_pw` no container Django
         (gerado uma vez, sobrevive a restart);
      3. fallback baseado em SECRET_KEY (último recurso — sempre derivável,
         mas só usado se as duas opções acima falharem).
    """
    p = os.getenv('NODERED_INTERNAL_PASSWORD', '').strip()
    if p:
        return p
    cache_file = '/tmp/.mis_internal_pw'
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as fh:
                return fh.read().strip()
        except OSError:
            pass
    try:
        pw = secrets.token_urlsafe(32)
        with open(cache_file, 'w') as fh:
            fh.write(pw)
        os.chmod(cache_file, 0o600)
        return pw
    except OSError:
        # FS read-only — usa derivado da SECRET_KEY (estável entre restarts).
        return hashlib.sha256(
            f'nodered-internal::{dj_settings.SECRET_KEY}'.encode()
        ).hexdigest()[:48]


def _ensure_internal_user():
    """Garante que existe um NodeRedUser de serviço com permissões totais.

    Esse usuário existe SÓ para o Django poder chamar a admin API do
    Node-RED (capturar projeto ativo, restaurar snapshots etc.) agora
    que adminAuth está ligado. Não deve ser usado por humanos — fica
    com nome `_mis_internal_` e observação explícita.
    """
    from .models import NodeRedUser
    user, _ = NodeRedUser.objects.get_or_create(
        username=NODERED_INTERNAL_USERNAME,
        defaults={
            'nivel': NodeRedUser.NIVEL_ADMIN,
            'ativo': True,
            'observacoes': (
                'CONTA DE SERVIÇO — usada pelo Django para acessar a admin '
                'API do Node-RED (restore de snapshot, leitura de projeto '
                'ativo). NÃO USAR PARA LOGIN HUMANO. Senha vem da env '
                'NODERED_INTERNAL_PASSWORD ou é gerada no 1º uso.'
            ),
        }
    )
    pwd = _internal_password()
    if not user.check_password(pwd):
        user.set_password(pwd)
        user.save(update_fields=['password_hash', 'atualizado_em'])
    return user


def _load_token_from_disk() -> tuple[str | None, float]:
    """Lê o token cacheado em /tmp se ainda válido. Retorna (token, exp)."""
    try:
        with open(_TOKEN_CACHE_FILE, 'r') as fh:
            data = json.load(fh)
        return data.get('token'), float(data.get('expires_at') or 0)
    except (OSError, ValueError):
        return None, 0.0


def _save_token_to_disk(token: str, expires_at: float) -> None:
    try:
        with open(_TOKEN_CACHE_FILE, 'w') as fh:
            json.dump({'token': token, 'expires_at': expires_at}, fh)
        os.chmod(_TOKEN_CACHE_FILE, 0o600)
    except OSError as exc:
        logger.debug('Não consegui persistir token: %s', exc)


def _get_admin_token() -> str | None:
    """Token Bearer válido para a admin API do Node-RED.

    Três camadas de cache:
      1. memória (mais rápido, válido enquanto o processo viver);
      2. arquivo /tmp (sobrevive a restart do Django, compartilhado
         entre gunicorn workers — evita N auth.login simultâneos);
      3. autenticação real contra /auth/token (último recurso).

    Margem de 60s antes de expirar, ‑‑‑ auto-provisiona o service-user
    na primeira chamada.
    """
    now = time.time()

    # 1) memória
    if _TOKEN_CACHE_MEM['token'] and _TOKEN_CACHE_MEM['expires_at'] > now + 60:
        return _TOKEN_CACHE_MEM['token']

    # 2) disco
    disk_tok, disk_exp = _load_token_from_disk()
    if disk_tok and disk_exp > now + 60:
        _TOKEN_CACHE_MEM['token'] = disk_tok
        _TOKEN_CACHE_MEM['expires_at'] = disk_exp
        return disk_tok

    # 3) autentica de verdade
    try:
        _ensure_internal_user()
    except Exception:
        logger.exception('Falha ao garantir service-user do Node-RED')
        return None

    pwd = _internal_password()
    try:
        r = requests.post(
            f'{NODERED_ADMIN_API}/auth/token',
            data={
                'client_id': 'node-red-editor',
                'grant_type': 'password',
                'scope': '*',
                'username': NODERED_INTERNAL_USERNAME,
                'password': pwd,
            },
            timeout=5,
        )
        if not r.ok:
            logger.warning(
                'Token admin Node-RED: HTTP %s · %s',
                r.status_code, r.text[:200],
            )
            return None
        data = r.json()
        token = data.get('access_token')
        expires_in = int(data.get('expires_in') or 3600)
        if not token:
            return None
        exp = now + expires_in
        _TOKEN_CACHE_MEM['token'] = token
        _TOKEN_CACHE_MEM['expires_at'] = exp
        _save_token_to_disk(token, exp)
        return token
    except requests.RequestException as exc:
        logger.warning('Erro ao obter token admin Node-RED: %s', exc)
        return None


def _invalidate_token_cache() -> None:
    """Chamado quando recebemos 401 — força re-autenticação."""
    _TOKEN_CACHE_MEM['token'] = None
    _TOKEN_CACHE_MEM['expires_at'] = 0.0
    try:
        os.unlink(_TOKEN_CACHE_FILE)
    except OSError:
        pass


def _node_red_call(method: str, path: str, **kwargs) -> requests.Response | None:
    """Wrapper das chamadas à admin API com retry de 401.

    `path` é o sub-caminho a partir de `NODERED_ADMIN_API` (ex.: '/projects').
    Retorna o Response (mesmo se !ok) ou None se erro de rede.
    """
    url = f'{NODERED_ADMIN_API}{path}'
    headers = kwargs.pop('headers', None) or _admin_headers()
    try:
        resp = requests.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 401:
            _invalidate_token_cache()
            headers = _admin_headers()
            resp = requests.request(method, url, headers=headers, **kwargs)
        return resp
    except requests.RequestException as exc:
        logger.warning('Node-RED %s %s falhou: %s', method, path, exc)
        return None


def _listar_projetos() -> dict:
    """Lista os projetos conhecidos pelo Node-RED (live, não cacheado).

    Retorna `{'active': '<nome>', 'projetos': ['nome1', 'nome2', ...]}`
    ou `{'active': '', 'projetos': []}` quando Projects está desligado.
    """
    resp = _node_red_call('GET', '/projects', timeout=5)
    if not resp or not resp.ok:
        # 404 = Projects desativado; outros = erro
        if resp and resp.status_code != 404:
            logger.warning('listar_projetos: HTTP %s', resp.status_code)
        return {'active': '', 'projetos': []}
    try:
        data = resp.json() or {}
    except ValueError:
        return {'active': '', 'projetos': []}
    return {
        'active': str(data.get('active') or '').strip(),
        'projetos': sorted([str(p) for p in (data.get('projects') or [])]),
    }


def _obter_flow_do_projeto(nome: str, *, permitir_trocar: bool = False) -> list | None:
    """Lê o flow.json do projeto `nome`.

    Limitação importante do Node-RED: a admin API NÃO permite ler
    arquivos de um projeto INATIVO (retorna 400 "Cannot operate on
    inactive project"). Então a estratégia é:

      - Se `nome` é o projeto ATIVO → usa `GET /flows` (sempre disponível).
      - Se `nome` é INATIVO e `permitir_trocar=False` (default) → retorna
        None. O admin mostra "ainda não capturado" com um botão para
        trocar manualmente (`permitir_trocar=True`).
      - Se `nome` é INATIVO e `permitir_trocar=True` → faz `PUT /projects
        {active: nome}`, lê os flows, e RETORNA SEM voltar ao projeto
        anterior. O usuário fica trabalhando no novo projeto (intencional).

    Retorna a lista de nós (formato flows.json) ou None.
    """
    ativo = _projeto_ativo(use_cache=False)
    if not ativo:
        # Projects desligado — GET /flows ainda funciona (modo legacy)
        return _obter_flows_ativo_via_api()
    if nome == ativo:
        return _obter_flows_ativo_via_api()
    if not permitir_trocar:
        logger.info(
            'obter_flow(%r): projeto inativo, ativo=%r — chame com permitir_trocar=True',
            nome, ativo,
        )
        return None
    ok, msg = _set_projeto_ativo(nome)
    if not ok:
        logger.warning('obter_flow(%r): troca falhou: %s', nome, msg)
        return None
    return _obter_flows_ativo_via_api()


def _obter_flows_ativo_via_api() -> list | None:
    """GET /flows do projeto atualmente ativo. Retorna a lista ou None."""
    resp = _node_red_call('GET', '/flows', timeout=8)
    if not resp or not resp.ok:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    # Resposta v2: {flows:[...], rev:"..."}. v1: lista pura.
    if isinstance(data, dict) and isinstance(data.get('flows'), list):
        return data['flows']
    if isinstance(data, list):
        return data
    return None


def _capturar_snapshot_projeto(nome: str, usuario_nome: str = 'auto-sync',
                                acao: str | None = None,
                                permitir_trocar: bool = False) -> NodeRedSnapshot | None:
    """Captura o estado atual do projeto `nome` como um NodeRedSnapshot.

    Idempotente: se o flow atual tiver o mesmo hash do último snapshot
    desse projeto, retorna o existente sem criar duplicata.

    `permitir_trocar=True` autoriza trocar o projeto ativo do Node-RED
    para conseguir capturar — necessário para projetos inativos, mas
    interrompe os flows do projeto anterior. Use apenas em ação manual
    explícita do operador.

    Retorna o snapshot (novo ou existente) ou None se não foi possível
    obter os flows.
    """
    flows = _obter_flow_do_projeto(nome, permitir_trocar=permitir_trocar)
    if flows is None:
        logger.info('capturar_snapshot_projeto(%s): sem flow.json acessível', nome)
        return None

    sha = _hash_flows(flows)
    ultimo = (
        NodeRedSnapshot.objects
        .filter(projeto=nome)
        .order_by('-criado_em')
        .first()
    )
    if ultimo and ultimo.hash_sha == sha:
        return ultimo  # nada mudou — não duplica

    if acao is None:
        acao = (NodeRedSnapshot.Acao.INITIAL if not ultimo
                else NodeRedSnapshot.Acao.DEPLOY)
    diff = _resumo_diff(flows, ultimo.flows_json if ultimo else None)
    canonical = json.dumps(flows, separators=(',', ':')).encode('utf-8')
    snap = NodeRedSnapshot.objects.create(
        projeto=nome,
        usuario=None,
        usuario_nome=usuario_nome,
        acao=acao,
        descricao='Captura automática (descoberta de projeto)' if usuario_nome == 'auto-sync' else 'Captura manual',
        flows_json=flows,
        hash_sha=sha,
        num_nodes=len(flows),
        size_bytes=len(canonical),
        parent=ultimo,
        nodes_adicionados=diff['adicionados'],
        nodes_removidos=diff['removidos'],
        nodes_modificados=diff['modificados'],
    )
    logger.info(
        'Snapshot Node-RED #%s capturado (auto) para projeto %r (%s nós)',
        snap.id, nome, snap.num_nodes,
    )
    return snap


def sincronizar_projetos() -> dict:
    """Faz uma varredura nos projetos do Node-RED e garante que cada um
    tenha pelo menos 1 snapshot no Django.

    Chamado pelo scheduler a cada 5 min. Também acessível pelo botão
    "Sincronizar agora" no admin.

    Retorna stats: {'projetos_total', 'novos', 'sem_flow', 'ja_existiam'}.
    """
    info = _listar_projetos()
    projetos = info['projetos']
    stats = {
        'projetos_total': len(projetos),
        'novos': [],
        'sem_flow': [],
        'ja_existiam': [],
    }
    if not projetos:
        return stats

    # projetos que já têm snapshot no Django
    ja_com_snapshot = set(
        NodeRedSnapshot.objects
        .filter(projeto__in=projetos)
        .values_list('projeto', flat=True)
        .distinct()
    )
    for p in projetos:
        if p in ja_com_snapshot:
            stats['ja_existiam'].append(p)
            continue
        snap = _capturar_snapshot_projeto(p, usuario_nome='auto-sync')
        if snap is None:
            stats['sem_flow'].append(p)
        else:
            stats['novos'].append(p)
    return stats


def _admin_headers() -> dict:
    """Headers padrão para chamadas à admin API — inclui Bearer se houver."""
    h = {'Content-Type': 'application/json'}
    token = _get_admin_token()
    if token:
        h['Authorization'] = f'Bearer {token}'
    return h


def _projeto_ativo(*, use_cache: bool = True) -> str:
    """Consulta o Node-RED qual é o projeto ativo atualmente.

    Retorna a string vazia quando:
      - a feature Projects está desativada (settings.js);
      - o Node-RED está fora do ar / erro de rede;
      - a resposta não contém o campo `active` esperado.

    Quando ativo, retorna o nome do projeto. O nome é o identificador
    canônico (mesmo que aparece no menu do editor e no diretório
    `/data/projects/<nome>`).

    Cache curto (`_PROJETO_ATIVO_TTL_S`) para evitar uma GET /projects
    em cada deploy / listagem. `use_cache=False` força nova consulta.
    """
    now = time.time()
    if use_cache and _PROJETO_ATIVO_CACHE['expires_at'] > now:
        return _PROJETO_ATIVO_CACHE['value']

    def _do_get():
        return requests.get(
            f'{NODERED_ADMIN_API}/projects',
            headers=_admin_headers(),
            timeout=_PROJECTS_PROBE_TIMEOUT_S,
        )

    try:
        resp = _do_get()
        if resp.status_code == 401:
            # token expirado/inválido — invalida cache, tenta novamente
            _invalidate_token_cache()
            resp = _do_get()
    except requests.RequestException as exc:
        logger.debug('projeto_ativo: Node-RED inalcançável (%s)', exc)
        return ''

    if resp.status_code == 404:
        # Projects desativado — sinal explícito; cacheia também.
        _PROJETO_ATIVO_CACHE['value'] = ''
        _PROJETO_ATIVO_CACHE['expires_at'] = now + _PROJETO_ATIVO_TTL_S
        return ''
    if not resp.ok:
        logger.warning('projeto_ativo: HTTP %s do Node-RED', resp.status_code)
        return ''
    try:
        data = resp.json() or {}
    except ValueError:
        return ''
    nome = str(data.get('active') or '').strip()[:128]  # bate com max_length do model
    _PROJETO_ATIVO_CACHE['value'] = nome
    _PROJETO_ATIVO_CACHE['expires_at'] = now + _PROJETO_ATIVO_TTL_S
    return nome


def _set_projeto_ativo(nome: str) -> tuple[bool, str]:
    """Pede ao Node-RED para trocar o projeto ativo (PUT /projects).

    Necessário antes do restore quando o snapshot é de um projeto
    diferente do que está aberto no editor agora.
    Retorna (sucesso, mensagem).
    """
    if not nome:
        return False, 'Nome do projeto vazio.'

    def _do_put():
        return requests.put(
            f'{NODERED_ADMIN_API}/projects',
            json={'active': nome},
            headers=_admin_headers(),
            timeout=10,
        )

    try:
        resp = _do_put()
        if resp.status_code == 401:
            _invalidate_token_cache()
            resp = _do_put()
    except requests.RequestException as exc:
        return False, f'Falha de comunicação ao trocar projeto: {exc}'
    if resp.ok:
        # invalida cache para a próxima leitura refletir a troca imediatamente
        _PROJETO_ATIVO_CACHE['expires_at'] = 0.0
        return True, f'Projeto ativo trocado para "{nome}".'
    return False, f'Node-RED recusou troca de projeto (HTTP {resp.status_code}): {resp.text[:200]}'


def _resumo_diff(novo: list, antigo: list | None) -> dict:
    """Compara dois flows.json (lista de nós) e retorna contadores
    grosseiros: nós adicionados, removidos, modificados.

    O flows.json do Node-RED é uma lista de objects com 'id' único.
    """
    if not isinstance(novo, list):
        return {'adicionados': 0, 'removidos': 0, 'modificados': 0}
    if not antigo or not isinstance(antigo, list):
        return {'adicionados': len(novo), 'removidos': 0, 'modificados': 0}

    def by_id(lst):
        return {n.get('id'): n for n in lst if isinstance(n, dict) and n.get('id')}

    novo_map = by_id(novo)
    antigo_map = by_id(antigo)
    add = len(set(novo_map) - set(antigo_map))
    rem = len(set(antigo_map) - set(novo_map))
    mod = sum(
        1 for nid in (set(novo_map) & set(antigo_map))
        if novo_map[nid] != antigo_map[nid]
    )
    return {'adicionados': add, 'removidos': rem, 'modificados': mod}


def _resolver_usuario(request) -> tuple[User | None, str]:
    """Tenta achar o usuário responsável pela ação:
      1. Header X-MIS-User (injetado pelo gateway nginx).
      2. request.user se autenticado.
    Retorna (User|None, username_str).
    """
    username = request.META.get('HTTP_X_MIS_USER', '').strip()
    if username:
        try:
            return User.objects.get(username=username), username
        except User.DoesNotExist:
            return None, username
    if request.user.is_authenticated:
        return request.user, request.user.username
    return None, ''


# ---------------------------------------------------------------------------
# Endpoint chamado pelo mirror nginx
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([AllowAny])  # vem do nginx mirror, autorização já feita lá
def snapshot_create(request):
    """POST /api/nodered/snapshot/

    Chamado pelo mirror do nginx em TODA request a /nodered/. Filtramos
    aqui pelo path/método original: só processa POST /nodered/flows
    (o deploy real). GET de assets, polling de status, etc. retornam
    rápido 200 sem criar snapshot.
    """
    original_uri = request.META.get('HTTP_X_ORIGINAL_URI', '')
    original_method = request.META.get('HTTP_X_ORIGINAL_METHOD', '')

    # Filtra: só deploy do editor (POST /nodered/flows) vira snapshot.
    # O endpoint exato pode vir com query string (?...) ou variantes.
    is_deploy = (
        original_method == 'POST'
        and ('/flows' in original_uri and '/flows/' not in original_uri.rstrip('?'))
    )
    if not is_deploy:
        return Response({'skipped': True, 'uri': original_uri, 'method': original_method})

    try:
        flows = request.data
        if isinstance(flows, dict) and 'flows' in flows:
            flows = flows['flows']  # alguns deploys vêm encapsulados
    except Exception as e:
        logger.warning("snapshot_create: corpo inválido: %s", e)
        return Response({'detail': 'JSON inválido'}, status=400)

    if not isinstance(flows, list):
        return Response({'detail': 'flows.json deve ser uma lista de nós'}, status=400)

    sha = _hash_flows(flows)
    projeto = _projeto_ativo()  # '' quando Projects desligado

    # Dedup e parent são POR PROJETO. Sem isso, alternar entre projetos
    # criaria sempre "diferença total" e o parent ficaria errado.
    ultimo = (
        NodeRedSnapshot.objects
        .filter(projeto=projeto)
        .order_by('-criado_em')
        .first()
    )
    if ultimo and ultimo.hash_sha == sha:
        logger.debug(
            "Snapshot duplicado em projeto=%r (hash=%s) — ignorando",
            projeto, sha[:8],
        )
        return Response({
            'duplicado': True,
            'snapshot_id': ultimo.id,
            'projeto': projeto,
        })

    user, username = _resolver_usuario(request)
    descricao = request.META.get('HTTP_X_MIS_DESCRICAO', '').strip()[:200]

    diff = _resumo_diff(flows, ultimo.flows_json if ultimo else None)
    canonical_bytes = json.dumps(flows, separators=(',', ':')).encode('utf-8')

    snap = NodeRedSnapshot.objects.create(
        projeto=projeto,
        usuario=user,
        usuario_nome=username,
        acao=NodeRedSnapshot.Acao.INITIAL if not ultimo else NodeRedSnapshot.Acao.DEPLOY,
        descricao=descricao,
        flows_json=flows,
        hash_sha=sha,
        num_nodes=len(flows),
        size_bytes=len(canonical_bytes),
        parent=ultimo,
        nodes_adicionados=diff['adicionados'],
        nodes_removidos=diff['removidos'],
        nodes_modificados=diff['modificados'],
    )
    logger.info(
        "Snapshot Node-RED #%s salvo: projeto=%r %s (+%d/-%d/~%d) por %s",
        snap.id, projeto or '<global>', sha[:8],
        diff['adicionados'], diff['removidos'], diff['modificados'],
        username or 'anônimo',
    )
    return Response({
        'snapshot_id': snap.id, 'hash': sha,
        'projeto': projeto,
        'autor': username, 'diff': diff,
        'num_nodes': snap.num_nodes,
    }, status=201)


# ---------------------------------------------------------------------------
# Listagem e diff (consumidos pela UI / admin)
# ---------------------------------------------------------------------------

@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def history_list(request):
    """GET /api/nodered/history/?limit=50&offset=0&projeto=<nome>

    Lista compacta dos snapshots — sem o flows_json pesado.

    Filtros:
      - `projeto=<nome>` → só snapshots desse projeto.
      - `projeto=__none__` → snapshots sem projeto (global / legacy).
      - omitido → todos.

    Também retorna `projeto_ativo` (o que o Node-RED está editando agora)
    e `projetos_conhecidos` (todos os projetos com pelo menos 1 snapshot)
    para que a UI mostre um seletor.
    """
    limit = min(int(request.query_params.get('limit', 50)), 200)
    offset = int(request.query_params.get('offset', 0))
    projeto_filter = request.query_params.get('projeto')

    qs = NodeRedSnapshot.objects.select_related('usuario').order_by('-criado_em')
    if projeto_filter == '__none__':
        qs = qs.filter(projeto='')
    elif projeto_filter:
        qs = qs.filter(projeto=projeto_filter)

    total = qs.count()
    items = []
    for s in qs[offset:offset + limit]:
        items.append({
            'id': s.id,
            'criado_em': s.criado_em.isoformat(),
            'projeto': s.projeto,
            'usuario': s.usuario_nome or '—',
            'acao': s.acao,
            'acao_label': s.get_acao_display(),
            'descricao': s.descricao,
            'num_nodes': s.num_nodes,
            'size_bytes': s.size_bytes,
            'hash_short': s.hash_sha[:8],
            'parent_id': s.parent_id,
            'diff': {
                'adicionados': s.nodes_adicionados,
                'removidos': s.nodes_removidos,
                'modificados': s.nodes_modificados,
            },
        })

    # `.order_by('projeto')` derruba o ordering default por criado_em
    # — caso contrário o SELECT inclui criado_em e o DISTINCT vira no-op.
    projetos_conhecidos = sorted(
        NodeRedSnapshot.objects
        .order_by('projeto')
        .values_list('projeto', flat=True)
        .distinct()
    )

    return Response({
        'total': total,
        'items': items,
        'projeto_filtro': projeto_filter or '',
        'projeto_ativo': _projeto_ativo(),
        'projetos_conhecidos': projetos_conhecidos,
    })


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def diff_view(request, snap_id: int):
    """GET /api/nodered/diff/<id>/

    Diff detalhado entre o snapshot id e seu parent.
    Retorna nós adicionados, removidos e modificados com nome+tipo.
    """
    snap = get_object_or_404(NodeRedSnapshot, pk=snap_id)
    parent = snap.parent

    def por_id(lst):
        return {n.get('id'): n for n in (lst or []) if isinstance(n, dict) and n.get('id')}

    novos = por_id(snap.flows_json)
    antigos = por_id(parent.flows_json) if parent else {}

    def describe(n):
        return {
            'id': n.get('id'),
            'type': n.get('type', '?'),
            'name': n.get('name') or n.get('label') or '',
            'z': n.get('z'),  # tab/fluxo de origem
        }

    adicionados = [describe(novos[i]) for i in (set(novos) - set(antigos))]
    removidos = [describe(antigos[i]) for i in (set(antigos) - set(novos))]
    modificados = []
    for nid in (set(novos) & set(antigos)):
        if novos[nid] != antigos[nid]:
            antes = describe(antigos[nid])
            depois = describe(novos[nid])
            # campos que mudaram (chaves de top-level)
            campos = sorted(
                k for k in (set(novos[nid]) | set(antigos[nid]))
                if novos[nid].get(k) != antigos[nid].get(k)
            )
            modificados.append({**depois, 'campos_alterados': campos})

    return Response({
        'snapshot': {
            'id': snap.id, 'criado_em': snap.criado_em.isoformat(),
            'projeto': snap.projeto,
            'usuario': snap.usuario_nome, 'descricao': snap.descricao,
        },
        'parent_id': parent.id if parent else None,
        'adicionados': adicionados,
        'removidos': removidos,
        'modificados': modificados,
    })


# ---------------------------------------------------------------------------
# Restore — escreve uma versão antiga de volta no Node-RED
# ---------------------------------------------------------------------------

def _is_staff(u):
    return u.is_authenticated and (u.is_superuser or u.has_perm('equipamentos.access_nodered'))


def restore_snapshot_internal(snap_id: int, user, *, trocar_projeto: bool = True) -> dict:
    """Lógica pura (sem decorators DRF) para restaurar um snapshot.
    Pode ser chamada de uma view REST OU de uma view admin Django.

    Multi-projeto:
      - Se o snapshot tem `projeto != ''` e o Node-RED está em outro
        projeto, tenta trocar (PUT /projects). Se a troca falha (ou
        `trocar_projeto=False`), aborta SEM tocar nos flows, porque
        sobrescrever o projeto errado é destrutivo.
      - Se o snapshot é legacy (`projeto == ''`) e o Node-RED tem
        Projects ativo, aborta e pede para o usuário decidir.

    Retorna {ok, status_code, mensagem|detail, ...}.
    """
    if not _is_staff(user):
        return {'ok': False, 'status_code': 403,
                'detail': 'Sem permissão para restaurar — precisa de access_nodered.'}

    try:
        snap = NodeRedSnapshot.objects.get(pk=snap_id)
    except NodeRedSnapshot.DoesNotExist:
        return {'ok': False, 'status_code': 404, 'detail': 'Snapshot não encontrado.'}

    projeto_alvo = snap.projeto
    projeto_atual = _projeto_ativo()

    # Caso A: snapshot pertence a um projeto, mas Node-RED está em outro.
    if projeto_alvo and projeto_atual and projeto_atual != projeto_alvo:
        if not trocar_projeto:
            return {
                'ok': False, 'status_code': 409,
                'detail': (
                    f'Snapshot é do projeto "{projeto_alvo}" mas o Node-RED '
                    f'está editando "{projeto_atual}". Troque para o projeto '
                    f'correto no editor antes de restaurar.'
                ),
            }
        ok_switch, msg_switch = _set_projeto_ativo(projeto_alvo)
        if not ok_switch:
            return {'ok': False, 'status_code': 502, 'detail': msg_switch}
        projeto_atual = projeto_alvo

    # Caso B: snapshot legacy (sem projeto) mas Node-RED agora usa Projects.
    if not projeto_alvo and projeto_atual:
        return {
            'ok': False, 'status_code': 409,
            'detail': (
                f'Este snapshot é anterior à ativação da feature Projects no '
                f'Node-RED (sem projeto associado). O editor está em '
                f'"{projeto_atual}". Restaurar agora sobrescreveria esse '
                f'projeto com flows pré-Projects. Confirme manualmente — '
                f'use a API com `?forcar=1` se for intencional.'
            ),
        }

    # Caso C: snapshot tem projeto, Node-RED está sem Projects (ou inverso) —
    # raro, mas tratado: log e segue, porque o POST /flows opera no que
    # estiver ativo no momento.
    if projeto_alvo and not projeto_atual:
        logger.warning(
            "Restore: snapshot do projeto %r aplicado em Node-RED sem "
            "Projects ativo. Os flows vão direto em /data/flows.json.",
            projeto_alvo,
        )

    # Node-RED v3 admin API espera {flows: [...], rev?: "..."} no POST /flows.
    # Sem o envelope, ele dá 400 "Cannot read properties of undefined (forEach)".
    payload = {'flows': snap.flows_json}

    def _post(headers_):
        return requests.post(
            f'{NODERED_ADMIN_API}/flows',
            json=payload,
            headers=headers_,
            timeout=20,
        )

    headers = _admin_headers()
    headers['Node-RED-Deployment-Type'] = 'full'
    headers['Node-RED-API-Version'] = 'v2'
    try:
        resp = _post(headers)
        if resp.status_code == 401:
            _invalidate_token_cache()
            headers = _admin_headers()
            headers['Node-RED-Deployment-Type'] = 'full'
            headers['Node-RED-API-Version'] = 'v2'
            resp = _post(headers)
        if not resp.ok:
            logger.error("Restore falhou: HTTP %s · %s", resp.status_code, resp.text[:200])
            return {'ok': False, 'status_code': 502,
                    'detail': f'Node-RED retornou {resp.status_code}: {resp.text[:300]}'}
    except requests.RequestException as e:
        logger.exception("Restore: erro ao contatar Node-RED")
        return {'ok': False, 'status_code': 502,
                'detail': f'Falha de comunicação com Node-RED: {e}'}

    # parent encadeia POR PROJETO — não embaralha timelines.
    ultimo = (
        NodeRedSnapshot.objects
        .filter(projeto=projeto_alvo)
        .order_by('-criado_em')
        .first()
    )
    novo = NodeRedSnapshot.objects.create(
        projeto=projeto_alvo,
        usuario=user,
        usuario_nome=user.username,
        acao=NodeRedSnapshot.Acao.RESTORE,
        descricao=f'Restaurado a partir do snapshot #{snap.id}',
        flows_json=snap.flows_json,
        hash_sha=snap.hash_sha,
        num_nodes=snap.num_nodes,
        size_bytes=snap.size_bytes,
        parent=ultimo,
        nodes_adicionados=0, nodes_removidos=0, nodes_modificados=0,
    )
    proj_label = f'projeto "{projeto_alvo}"' if projeto_alvo else 'global'
    logger.info(
        "Restore Node-RED: snapshot #%s (%s) aplicado por %s (novo #%s)",
        snap.id, proj_label, user.username, novo.id,
    )
    return {
        'ok': True,
        'status_code': 200,
        'snapshot_origem': snap.id,
        'snapshot_evento': novo.id,
        'projeto': projeto_alvo,
        'mensagem': (
            f'Versão de {snap.criado_em:%d/%m %H:%M} ({proj_label}) restaurada '
            f'com sucesso. Recarregue o editor do Node-RED para ver as '
            f'alterações.'
        ),
    }


# ---------------------------------------------------------------------------
# Descoberta de projetos
# ---------------------------------------------------------------------------

@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def projects_overview(request):
    """GET /api/nodered/projects/

    Lista os projetos VIVOS no Node-RED (chama a admin API live, sem cache)
    e junta com as estatísticas do histórico Django:

    ```json
    {
      "active": "casa",
      "items": [
        {
          "nome": "casa",
          "ativo": true,
          "snapshots_total": 2,
          "ultimo_snapshot": {"id":7,"criado_em":"...","hash_short":"db64..."},
          "tem_snapshot_django": true
        },
        {
          "nome": "factory_north",
          "ativo": false,
          "snapshots_total": 0,
          "ultimo_snapshot": null,
          "tem_snapshot_django": false  // ainda não capturado
        }
      ]
    }
    ```
    """
    info = _listar_projetos()
    nomes = info['projetos']
    active = info['active']

    # Stats por projeto (uma query só)
    from django.db.models import Count, Max
    stats = {
        s['projeto']: s
        for s in NodeRedSnapshot.objects
        .filter(projeto__in=nomes)
        .values('projeto')
        .annotate(total=Count('id'), ultimo_id=Max('id'))
    }
    # Snapshot mais recente por projeto, para mostrar hash/timestamp
    ult_ids = [s['ultimo_id'] for s in stats.values() if s.get('ultimo_id')]
    ult_map = {
        s.projeto: s
        for s in NodeRedSnapshot.objects.filter(id__in=ult_ids)
    }

    items = []
    for nome in nomes:
        st = stats.get(nome, {'total': 0})
        ult = ult_map.get(nome)
        items.append({
            'nome': nome,
            'ativo': (nome == active),
            'snapshots_total': st.get('total', 0),
            'tem_snapshot_django': bool(st.get('total', 0)),
            'ultimo_snapshot': ({
                'id': ult.id,
                'criado_em': ult.criado_em.isoformat(),
                'hash_short': ult.hash_sha[:8],
                'num_nodes': ult.num_nodes,
                'acao': ult.acao,
            } if ult else None),
        })
    return Response({'active': active, 'items': items})


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def capture_project_snapshot(request, nome: str):
    """POST /api/nodered/projects/<nome>/capture/?trocar=1

    Força a captura do estado atual de um projeto como snapshot. Usado
    quando o operador acabou de criar um projeto e ainda não fez deploy
    nenhum — clica "Capturar agora" no admin e o estado inicial entra
    no histórico.

    `?trocar=1` autoriza trocar o projeto ativo do Node-RED se for
    necessário (projeto inativo). Sem isso, projeto inativo retorna 409.
    """
    if not _is_staff(request.user):
        return Response({'detail': 'Sem permissão.'}, status=403)
    permitir = request.query_params.get('trocar', '').lower() in ('1', 'true', 'yes')
    ativo = _projeto_ativo(use_cache=False)
    if nome != ativo and not permitir:
        return Response({
            'ok': False,
            'detail': (
                f'O projeto "{nome}" não está ativo (ativo atual: "{ativo}"). '
                f'Não posso ler seus flows sem trocá-lo. Use ?trocar=1 para '
                f'autorizar — isso interromperá os flows de "{ativo}".'
            ),
            'projeto_ativo': ativo,
        }, status=409)
    snap = _capturar_snapshot_projeto(
        nome,
        usuario_nome=request.user.username,
        acao=NodeRedSnapshot.Acao.INITIAL,
        permitir_trocar=permitir,
    )
    if snap is None:
        return Response({
            'ok': False,
            'detail': (
                f'Não foi possível ler o flow.json do projeto "{nome}". '
                f'Verifique se ele existe e tem conteúdo deployado.'
            ),
        }, status=404)
    return Response({
        'ok': True,
        'snapshot_id': snap.id,
        'hash_short': snap.hash_sha[:8],
        'num_nodes': snap.num_nodes,
        'mensagem': f'Snapshot #{snap.id} capturado para o projeto "{nome}".',
    })


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def sync_projects(request):
    """POST /api/nodered/projects/sync/

    Faz a varredura: para cada projeto do Node-RED sem snapshot no
    Django, captura um INITIAL automaticamente. Disparado também pelo
    scheduler periódico (a cada 5 min).
    """
    if not _is_staff(request.user):
        return Response({'detail': 'Sem permissão.'}, status=403)
    stats = sincronizar_projetos()
    return Response({'ok': True, **stats})


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def restore_snapshot(request, snap_id: int):
    """POST /api/nodered/restore/<id>/?forcar=1

    Wrapper REST para `restore_snapshot_internal`.

    `?forcar=1` autoriza o restore quando o snapshot é legacy (sem
    projeto) e o Node-RED está com Projects ativo — o "Caso B" do
    internal. Para os demais cenários, o internal já trata sozinho.
    """
    trocar = request.query_params.get('forcar', '').lower() in ('1', 'true', 'yes')
    result = restore_snapshot_internal(snap_id, request.user, trocar_projeto=True)
    if not result['ok'] and result.get('status_code') == 409 and trocar:
        # Operador autorizou explicitamente — força o POST /flows sem checagem.
        snap = NodeRedSnapshot.objects.filter(pk=snap_id).first()
        if snap:
            headers = _admin_headers()
            headers['Node-RED-Deployment-Type'] = 'full'
            headers['Node-RED-API-Version'] = 'v2'
            try:
                resp = requests.post(
                    f'{NODERED_ADMIN_API}/flows',
                    json={'flows': snap.flows_json},
                    headers=headers,
                    timeout=20,
                )
                if resp.ok:
                    novo = NodeRedSnapshot.objects.create(
                        projeto=_projeto_ativo(),
                        usuario=request.user,
                        usuario_nome=request.user.username,
                        acao=NodeRedSnapshot.Acao.RESTORE,
                        descricao=f'[FORÇADO] Restaurado snapshot #{snap.id}',
                        flows_json=snap.flows_json,
                        hash_sha=snap.hash_sha,
                        num_nodes=snap.num_nodes,
                        size_bytes=snap.size_bytes,
                        parent=None,
                        nodes_adicionados=0, nodes_removidos=0, nodes_modificados=0,
                    )
                    result = {
                        'ok': True, 'status_code': 200,
                        'snapshot_origem': snap.id,
                        'snapshot_evento': novo.id,
                        'mensagem': 'Restaurado em modo forçado.',
                    }
            except requests.RequestException as e:
                result = {'ok': False, 'status_code': 502, 'detail': str(e)}
    return Response(result, status=result.get('status_code', 200))
