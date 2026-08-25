from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
from rest_framework.authentication import CSRFCheck
from rest_framework import exceptions

def enforce_csrf(request):
    """
    Enforce CSRF validation for session based/cookie based authentication.
    """
    check = CSRFCheck(request)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied('CSRF Failed: %s' % reason)

class CookieJWTAuthentication(JWTAuthentication):
    """
    Classe customizada que suporta obter o JWT tanto do Header (Bearer) quanto de um Cookie local.
    """
    def authenticate(self, request):
        header = self.get_header(request)
        
        # Se veio via Header, segue fluxo normal
        if header is not None:
            raw_token = self.get_raw_token(header)
        else:
            # Senão tenta pegar pelo cookie HttpOnly
            raw_token = request.COOKIES.get(settings.SIMPLE_JWT.get('AUTH_COOKIE', 'access_token'))
            
        if raw_token is None:
            return None

        # Valida token normally
        validated_token = self.get_validated_token(raw_token)
        
        # Opcional (se Auth Cookie SameSite não for Strict/Lax, forçar CSRF):
        # enforce_csrf(request)

        return self.get_user(validated_token), validated_token

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        # Bloqueia imediatamente um usuário expirado, mesmo que o JWT de
        # acesso tenha sido emitido antes da expiração/revogação.
        from equipamentos.access_policy import access_is_valid
        if not access_is_valid(user):
            raise exceptions.AuthenticationFailed(
                'Acesso expirado. Solicite a revalidação a um administrador.',
                code='user_access_expired',
            )
        return user
