from rest_framework.permissions import BasePermission, SAFE_METHODS

class PodeAlterarIntertravamento(BasePermission):
    """
    Leitura: qualquer usuário autenticado.
    Escrita (toggle/create/update): apenas grupos qualidade ou coordenacao.
    """
    GRUPOS_ESCRITA = ['qualidade', 'coordenacao']

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.groups.filter(
            name__in=self.GRUPOS_ESCRITA
        ).exists() or request.user.is_superuser

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class PodeSincronizarReceita(BasePermission):
    """
    Permissão para atualizar FormatoVariavel a partir de leituras do CLP
    (endpoint /api/recipe-monitor/formato/<id>/sincronizar/).

    Apenas membros dos grupos TIM, Engenharia ou Coordenação podem gravar
    valores lidos do CLP de volta na receita. Os nomes dos grupos seguem
    o padrão usado em outros pontos do sistema (ver settings/admin).

    Mensagem de erro intencionalmente verbosa: a rejeição é exibida ao
    operador no toast do frontend.
    """
    GRUPOS_AUTORIZADOS = ['TIM', 'Engenharia', 'Coordenacao', 'Coordenação']
    message = (
        'Apenas membros dos grupos TIM, Engenharia ou Coordenação podem '
        'atualizar a receita com valores lidos do CLP.'
    )

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return request.user.groups.filter(
            name__in=self.GRUPOS_AUTORIZADOS
        ).exists()
