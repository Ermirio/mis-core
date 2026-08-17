from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('ips.urls')),
    path('api/andretti/', include('programa_andretti.urls')),
    path('', include('ips.urls')),
]
