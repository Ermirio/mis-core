"""
Módulo customizado para extrair JWT do header ou dos cookies criados pelo MIS Core IdP.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings

class CookieJWTAuthentication(JWTAuthentication):
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
        
        return self.get_user(validated_token), validated_token
