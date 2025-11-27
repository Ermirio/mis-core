from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'linhas', views.LinhaProducaoViewSet, basename='linha')
router.register(r'equipamentos', views.EquipamentoViewSet, basename='equipamento')
router.register(r'conexoes-opc', views.ConexaoOPCViewSet, basename='conexao-opc')
router.register(r'tags-coleta', views.TagColetaViewSet, basename='tag-coleta')
router.register(r'sensores', views.SensorViewSet, basename='sensor')
router.register(r'metricas', views.MetricaProducaoViewSet, basename='metrica')
router.register(r'defeitos', views.DefeitoViewSet, basename='defeito')

# Novos endpoints
router.register(r'turnos', views.TurnoProducaoViewSet, basename='turno')
router.register(r'calendario', views.CalendarioProducaoViewSet, basename='calendario')
router.register(r'eventos-estado', views.EventoEstadoEquipamentoViewSet, basename='evento-estado')

urlpatterns = [
    path('', include(router.urls)),
    
    # Endpoints especiais para o Coletor
    path('configuracao_coletor/', views.configuracao_coletor, name='configuracao-coletor'),
    path('metricas_consolidadas/', views.metricas_consolidadas, name='metricas-consolidadas'),
    path('eventos_estado/', views.eventos_estado, name='eventos-estado'),  # NOVO
]
