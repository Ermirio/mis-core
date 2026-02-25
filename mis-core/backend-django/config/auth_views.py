from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.conf import settings
from decouple import config

class CookieTokenObtainPairView(TokenObtainPairView):
    """
    View de Login que retorna os tokens também via Cookies seguros HttpOnly (.mis.local).
    """
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            access_token = response.data.get('access')
            refresh_token = response.data.get('refresh')
            
            samesite = settings.SIMPLE_JWT.get('AUTH_COOKIE_SAMESITE', 'Lax')
            domain = config('SESSION_COOKIE_DOMAIN', default=None)
            is_secure = settings.SIMPLE_JWT.get('AUTH_COOKIE_SECURE', False)

            # Seta o Access Token
            if access_token:
                response.set_cookie(
                    key=settings.SIMPLE_JWT.get('AUTH_COOKIE', 'access_token'),
                    value=access_token,
                    expires=settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME'),
                    secure=is_secure,
                    httponly=True,
                    samesite=samesite,
                    domain=domain,
                    path='/'
                )

            # Seta o Refresh Token
            if refresh_token:
                response.set_cookie(
                    key='refresh_token',
                    value=refresh_token,
                    expires=settings.SIMPLE_JWT.get('REFRESH_TOKEN_LIFETIME'),
                    secure=is_secure,
                    httponly=True,
                    samesite=samesite,
                    domain=domain,
                    path='/'
                )
        return response

class CookieTokenRefreshView(TokenRefreshView):
    """
    View de Refresh que lê o refresh_token do cookie e seta o novo access_token no cookie.
    """
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')
        
        if refresh_token and 'refresh' not in request.data:
            # Injeta o token na requisição caso venha apenas pelo cookie (Front pode omitir)
            request.data['refresh'] = refresh_token
            
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            access_token = response.data.get('access')
            samesite = settings.SIMPLE_JWT.get('AUTH_COOKIE_SAMESITE', 'Lax')
            domain = config('SESSION_COOKIE_DOMAIN', default=None)
            is_secure = settings.SIMPLE_JWT.get('AUTH_COOKIE_SECURE', False)

            if access_token:
                response.set_cookie(
                    key=settings.SIMPLE_JWT.get('AUTH_COOKIE', 'access_token'),
                    value=access_token,
                    expires=settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME'),
                    secure=is_secure,
                    httponly=True,
                    samesite=samesite,
                    domain=domain,
                    path='/'
                )
        return response

class LogoutView(APIView):
    """
    Limpa os cookies gerados no domínio local.
    """
    permission_classes = [IsAuthenticated] # Opcionalmente pode ser Any se for open logout

    def post(self, request):
        response = Response({"detail": "Logout successful"}, status=status.HTTP_200_OK)
        domain = config('SESSION_COOKIE_DOMAIN', default=None)
        
        # Zera os cookies
        response.delete_cookie(settings.SIMPLE_JWT.get('AUTH_COOKIE', 'access_token'), domain=domain, path='/')
        response.delete_cookie('refresh_token', domain=domain, path='/')
        
        return response
