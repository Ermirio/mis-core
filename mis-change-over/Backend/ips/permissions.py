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
