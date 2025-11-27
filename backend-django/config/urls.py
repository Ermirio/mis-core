from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('equipamentos.urls')),
    path('api/bi/', include('equipamentos.urls_bi')),  # Endpoints de BI (side-by-side)
]

