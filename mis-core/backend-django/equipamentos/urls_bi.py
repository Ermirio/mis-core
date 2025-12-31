"""
URLs de BI (Business Intelligence)
Rotas side-by-side para não interferir nas APIs existentes
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_bi import (
    OrdemProducaoViewSet,
    RegistroProducaoTurnoViewSet,
    ProducaoBIViewSet
)

# Router para ViewSets
router = DefaultRouter()
router.register(r'ordens-producao', OrdemProducaoViewSet, basename='ordemproducao')
router.register(r'registros-turno', RegistroProducaoTurnoViewSet, basename='registroproducaoturno')
router.register(r'producao', ProducaoBIViewSet, basename='producao-bi')

urlpatterns = [
    path('', include(router.urls)),
]
