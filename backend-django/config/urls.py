from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from analytics.views import AnalyticsProfileViewSet
from config.auth_views import CookieTokenObtainPairView, CookieTokenRefreshView, CurrentUserView, LogoutView
from equipamentos import auth_gateway_views
from config.version_view import version_view

# Router para analytics
analytics_router = DefaultRouter()
analytics_router.register(r'analytics-profiles', AnalyticsProfileViewSet)

from django.http import JsonResponse
from django.views.decorators.cache import never_cache

@never_cache
def health_check(request):
    return JsonResponse({'status': 'ok'})

urlpatterns = [
    path('api/health/', health_check),
    path('api/version/', version_view, name='mis_version'),
    path('mis-core-admin/', admin.site.urls),

    # NOVAS ROTAS DE SSO / JWT via COOKIE
    path('api/auth/login/', CookieTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/logout/', LogoutView.as_view(), name='auth_logout'),
    path('api/auth/me/', CurrentUserView.as_view(), name='auth_me'),
    path('api/auth/admin-tools/', auth_gateway_views.check_admin_tools, name='auth_admin_tools'),

    path('api/', include('equipamentos.urls')),
    path('api/bi/', include('equipamentos.urls_bi')),  # Endpoints de BI (side-by-side)
    path('api/', include(analytics_router.urls)),  # Analytics profiles
]
