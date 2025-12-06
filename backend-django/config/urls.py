from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def health_check(request):
    """Health check endpoint for Docker container monitoring"""
    return JsonResponse({"status": "healthy", "service": "django"})

urlpatterns = [
    path('api/health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('api/', include('equipamentos.urls')),
    path('api/bi/', include('equipamentos.urls_bi')),  # Endpoints de BI (side-by-side)
]
