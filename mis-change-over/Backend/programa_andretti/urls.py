from django.urls import path
from .views import VelocidadeLinhaList, VelocidadeLinhaDetail, atualizar_velocidades

urlpatterns = [
    path('velocidades/', VelocidadeLinhaList.as_view(), name='velocidade-linha-list'),
    path('velocidades/<int:pk>/', VelocidadeLinhaDetail.as_view(), name='velocidade-linha-detail'),
    path('atualizar-velocidades/', atualizar_velocidades, name='atualizar-velocidades'),
]