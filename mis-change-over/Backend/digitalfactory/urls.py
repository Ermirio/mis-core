from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('ips.urls')),  # Inclui as rotas do app ips
    path('', include('ips.urls'))  # Inclui as rotas do app ips
]
