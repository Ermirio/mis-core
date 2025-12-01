from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import tonnage_views
from . import loss_analysis_views



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
router.register(r'eventos-parada', views.EventoParadaViewSet, basename='evento-parada')
router.register(r'iniciativas-estrategicas', views.StrategicInitiativeViewSet, basename='iniciativa-estrategica')

urlpatterns = [
    path('', include(router.urls)),
    
    # Endpoints especiais para o Coletor
    path('configuracao_coletor/', views.configuracao_coletor, name='configuracao-coletor'),
    path('metricas_consolidadas/', views.metricas_consolidadas, name='metricas-consolidadas'),
    path('metricas_fabrica_consolidadas/', views.metricas_fabrica_consolidadas, name='metricas-fabrica'),
    path("metricas_linha_consolidadas/", views.metricas_linha_consolidadas, name="metricas-linha-consolidadas"),
    path("full_equipment_status/", views.get_full_equipment_status, name="full-equipment-status"),
    path('metricas_equipamento_consolidadas/', views.metricas_equipamento_consolidadas, name='metricas-equipamento-consolidadas'),
    path('eventos_estado/', views.eventos_estado, name='eventos-estado'),
    
    # Endpoints de Importar/Exportar Excel
    path('linhas/exportar-excel/', views.exportar_linhas_excel, name='exportar-linhas-excel'),
    path('linhas/importar-excel/', views.importar_linhas_excel, name='importar-linhas-excel'),
    path('equipamentos/exportar-excel/', views.exportar_equipamentos_excel, name='exportar-equipamentos-excel'),
    path('equipamentos/importar-excel/', views.importar_equipamentos_excel, name='importar-equipamentos-excel'),
    path('produtos/exportar-excel/', views.exportar_produtos_excel, name='exportar-produtos-excel'),
    path('produtos/importar-excel/', views.importar_produtos_excel, name='importar-produtos-excel'),
    path('metricas/exportar-excel/', views.exportar_metricas_excel, name='exportar-metricas-excel'),
    path('metricas/importar-excel/', views.importar_metricas_excel, name='importar-metricas-excel'),
    path('ordens-producao/exportar-excel/', views.exportar_ordens_producao_excel, name='exportar-ordens-excel'),
    path('ordens-producao/importar-excel/', views.importar_ordens_producao_excel, name='importar-ordens-excel'),
    
    # Endpoints de Tonelagem
    path('linhas/<int:linha_id>/tonelagem-tempo-real/', tonnage_views.tonelagem_tempo_real, name='tonelagem-tempo-real'),
    path('linhas/<int:linha_id>/historico-tonelagem/', tonnage_views.historico_tonelagem, name='historico-tonelagem'),
    path('equipamentos/<int:equipamento_id>/tonelagem/', tonnage_views.tonelagem_por_equipamento, name='tonelagem-equipamento'),

    # Endpoints de Análise de Perdas
    path('linhas/<int:linha_id>/perdas-analise/', loss_analysis_views.perdas_analise, name='perdas-analise'),
    path('linhas/<int:linha_id>/planejado-vs-real/', loss_analysis_views.planejado_vs_real, name='planejado-vs-real'),
    path('linhas/<int:linha_id>/strategic-loss/', loss_analysis_views.strategic_loss_aggregation, name='strategic-loss'),
    path('linhas/<int:linha_id>/monthly-production-stats/', loss_analysis_views.monthly_production_stats, name='monthly-production-stats'),
    path('linhas/<int:linha_id>/monthly-op-history/', loss_analysis_views.monthly_op_history, name='monthly-op-history'),
    
    # Endpoints de Análise Avançada
    path('linhas/<int:linha_id>/analise/producao/', views.linha_analise_producao, name='linha-analise-producao'),
    path('linhas/<int:linha_id>/analise/velocidade/', views.linha_analise_velocidade, name='linha-analise-velocidade'),
    path('linhas/<int:linha_id>/analise/sku/', views.linha_analise_sku, name='linha-analise-sku'),
    
    # Endpoint de Histórico Detalhado
    path('linhas/<int:linha_id>/historico-detalhado/', views.historico_linha_detalhado, name='historico-detalhado'),
    
    # Endpoints de Vazão Necessária (Throughput Required)
    path('linhas/<int:linha_id>/vazao-necessaria/', views.vazao_necessaria_linha, name='vazao-necessaria-linha'),
    path('vazao-necessaria/', views.vazao_necessaria_todas_linhas, name='vazao-necessaria-todas'),
    path('dashboard/factory-manage/', views.dashboard_factory_manage, name='dashboard-factory-manage'),
]