from django.urls import path
from .views import (
    WaveList, WaveDetail,
    MetaList, MetaDetail,
    CategoriaList,
    AcaoList, AcaoDetail,
    registrar_leitura_manual,
    dashboard_andretti, trend_velocidade,
)

urlpatterns = [
    # Waves
    path('waves/',          WaveList.as_view(),   name='andretti-wave-list'),
    path('waves/<int:pk>/', WaveDetail.as_view(), name='andretti-wave-detail'),

    # Metas de velocidade
    path('metas/',          MetaList.as_view(),   name='andretti-meta-list'),
    path('metas/<int:pk>/', MetaDetail.as_view(), name='andretti-meta-detail'),

    # Categorias
    path('categorias/', CategoriaList.as_view(), name='andretti-categoria-list'),

    # Ações
    path('acoes/',          AcaoList.as_view(),   name='andretti-acao-list'),
    path('acoes/<int:pk>/', AcaoDetail.as_view(), name='andretti-acao-detail'),

    # Velocidade
    path('velocidade/leitura-manual/',            registrar_leitura_manual, name='andretti-leitura-manual'),
    path('velocidade/trend/<int:linha_id>/',       trend_velocidade,         name='andretti-trend'),

    # Dashboard
    path('dashboard/', dashboard_andretti, name='andretti-dashboard'),
]
