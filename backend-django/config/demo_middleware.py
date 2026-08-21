"""
Middleware utilizado quando ALLOW_ANY_HOST=True (deploy VPN/Tailscale).

Isenta CSRF para rotas de API (/api/*, /flask-api/*, /api/v2/*) — estas usam JWT
e nunca dependem do cookie de sessão para autenticar.

NUNCA isenta /mis-core-admin/ — admin segue protegido por CSRF normal.
"""

from django.utils.deprecation import MiddlewareMixin


class DisableCSRFForApiMiddleware(MiddlewareMixin):
    EXEMPT_PREFIXES = ('/api/', '/flask-api/', '/api/v2/')

    def process_request(self, request):
        path = request.path_info or ''
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            setattr(request, '_dont_enforce_csrf_checks', True)
        return None
