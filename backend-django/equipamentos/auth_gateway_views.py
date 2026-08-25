"""
Auth-gateway para ferramentas externas (Node-RED, Grafana, etc).

O nginx faz `auth_request` para os endpoints aqui ANTES de fazer proxy
para a ferramenta. O endpoint retorna:
  - 200: usuário tem permissão → nginx libera e injeta o header de
         confiança X-MIS-Authorized
  - 401/403: usuário sem sessão ou sem permissão → nginx bloqueia e
         redireciona para /admin/login/?next=...

Vantagem do padrão:
  - Configuração 100% no admin Django (grupos + permissões)
  - Sem mexer no settings.js do Node-RED
  - Ferramenta interna fica blindada (porta privada, só acessível via gateway)

Para conceder acesso a um usuário:
  Admin Django › Usuários › [usuário] › Permissões de usuário ›
  procurar "Pode acessar Node-RED" (ou grupo "Operadores Node-RED").
"""
from __future__ import annotations

import json
import logging

from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from .access_policy import access_is_valid, is_mis_admin

logger = logging.getLogger(__name__)


def _check(request, perm_codename: str | None = None) -> HttpResponse:
    """Lógica comum: precisa estar logado E ter a permissão.
    Retorna 401 (sem sessão) ou 403 (sem permissão) — nginx trata
    cada código diferente: 401 → redireciona para login.

    Quando autorizado, devolve o header X-MIS-User para o nginx
    propagar ao upstream (Node-RED), o que permite auditoria de quem
    fez o deploy via histórico.
    """
    if not request.user.is_authenticated:
        return HttpResponse(status=401)
    # Ferramentas administrativas são reservadas a administradores do MIS.
    # Permissões legadas individuais não bastam mais para atravessar o gateway.
    if access_is_valid(request.user) and is_mis_admin(request.user):
        resp = HttpResponse(status=200)
        resp['X-MIS-User'] = request.user.username
        return resp
    return HttpResponseForbidden('Sem permissão para esta ferramenta')


def check_nodered(request):
    return _check(request, 'access_nodered')


def check_grafana(request):
    return _check(request, 'access_grafana')


def check_chronograf(request):
    return _check(request, 'access_chronograf')


def check_emqx(request):
    return _check(request, 'access_emqx')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_admin_tools(request):
    """Subrequest JWT-aware usado pelo nginx em todas as ferramentas."""
    return _check(request)


# -----------------------------------------------------------------------------
# adminAuth do Node-RED — fonte de verdade no admin Django.
#
# settings.js do Node-RED chama estes dois endpoints em vez de manter
# `users:[...]` estático. Assim, criar/editar/desativar usuário do Node-RED
# é feito 100% pelo admin Django (modelo NodeRedUser), sem editar arquivo
# de configuração nem rodar `node-red-admin hash-pw`.
#
# Segurança: os endpoints só são acessíveis dentro da rede docker
# (`mis-core-network`). O nginx não publica nada em /api/auth/nodered/*
# para o mundo externo. Mesmo assim, o body só é aceito como JSON e o
# CSRF é dispensado porque a chamada vem do container Node-RED (sem
# sessão Django).
# -----------------------------------------------------------------------------


def _user_payload(user) -> dict:
    """Formato esperado pelo `adminAuth` do Node-RED."""
    return {
        'username': user.username,
        'permissions': user.get_permissions(),
    }


@csrf_exempt
@require_POST
def nodered_authenticate(request):
    """POST /api/auth/nodered/authenticate/

    Body JSON: {"username": "...", "password": "..."}
    Resposta 200: {"username": "...", "permissions": "*" | "read" | [...]}
    Resposta 401: vazio (credenciais inválidas ou usuário inativo)
    """
    # Import tardio para evitar import cíclico no carregamento de urls.
    from .models import NodeRedUser

    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, TypeError):
        return HttpResponse(status=400)

    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not username or not password:
        return HttpResponse(status=401)

    try:
        user = NodeRedUser.objects.get(username=username, ativo=True)
    except NodeRedUser.DoesNotExist:
        # Não distinguimos "usuário não existe" de "senha errada" no retorno
        # para não vazar enumeração de usuários.
        logger.info('Node-RED auth: usuário "%s" inexistente ou inativo', username)
        return HttpResponse(status=401)

    if not user.check_password(password):
        logger.info('Node-RED auth: senha incorreta para "%s"', username)
        return HttpResponse(status=401)

    # Sucesso — registra último login para auditoria.
    user.ultimo_login_em = timezone.now()
    user.save(update_fields=['ultimo_login_em', 'atualizado_em'])
    return JsonResponse(_user_payload(user))


@csrf_exempt
@require_POST
def nodered_user(request):
    """POST /api/auth/nodered/user/

    Body JSON: {"username": "..."}
    Resposta 200: {"username": "...", "permissions": ...}
    Resposta 404: vazio (usuário não existe ou está inativo)

    Usado pelo Node-RED após validação de token de sessão para
    obter as permissões do usuário sem precisar revalidar senha.
    """
    from .models import NodeRedUser

    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, TypeError):
        return HttpResponse(status=400)

    username = (data.get('username') or '').strip()
    if not username:
        return HttpResponse(status=404)

    try:
        user = NodeRedUser.objects.get(username=username, ativo=True)
    except NodeRedUser.DoesNotExist:
        return HttpResponse(status=404)

    return JsonResponse(_user_payload(user))
