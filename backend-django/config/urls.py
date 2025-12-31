from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from analytics.views import AnalyticsProfileViewSet

# Router para analytics
analytics_router = DefaultRouter()
analytics_router.register(r'analytics-profiles', AnalyticsProfileViewSet)


from django.http import JsonResponse
def health_check(request):
    return JsonResponse({'status': 'ok'})

urlpatterns = [
    path('api/health/', health_check),
    path('mis-core-admin/', admin.site.urls),
    path('api/', include('equipamentos.urls')),
    path('api/bi/', include('equipamentos.urls_bi')),  # Endpoints de BI (side-by-side)
    path('api/', include(analytics_router.urls)),  # Analytics profiles
]



