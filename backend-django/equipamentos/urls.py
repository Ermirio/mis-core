from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import tonnage_views
from . import loss_analysis_views
from . import waste_dashboard_views
from .giveaway_views import GiveAwaySummaryView
from .factory_tree_views import FactoryTreeView
from . import flask_replacement_views as flask_out
from . import analytics_views
from . import golden_state_views

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

    # Estado de Ouro por linha. As views, modelos e migrações já fazem parte
    # da imagem; estas rotas ficaram fora do urlpatterns e causavam 404.
    path('linhas/<int:linha_id>/golden-state/', golden_state_views.golden_state_linha, name='golden-state-linha'),
    path('linhas/<int:linha_id>/golden-state/capturar/', golden_state_views.golden_state_capturar, name='golden-state-capturar'),
    path('linhas/<int:linha_id>/golden-state/runs/', golden_state_views.golden_state_runs, name='golden-state-runs'),
    path('linhas/<int:linha_id>/golden-state/runs/<int:run_id>/', golden_state_views.golden_state_runs, name='golden-state-run-detail'),
    path('linhas/<int:linha_id>/golden-state/aplicar/', golden_state_views.golden_state_aplicar, name='golden-state-aplicar'),
    
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
    path('linhas/<int:linha_id>/waste-analysis/', loss_analysis_views.strategic_waste_analysis, name='strategic-waste-analysis'),
    path('linhas/<int:linha_id>/monthly-production-stats/', loss_analysis_views.monthly_production_stats, name='monthly-production-stats'),
    path('linhas/<int:linha_id>/monthly-op-history/', loss_analysis_views.monthly_op_history, name='monthly-op-history'),
    path('fabrica/perdas-analise/', loss_analysis_views.factory_loss_analysis, name='factory-loss-analysis'),
    path('fabrica/waste-analysis/', loss_analysis_views.factory_waste_analysis, name='factory-waste-analysis'),
    
    # Endpoints de Análise Avançada
    path('linhas/<int:linha_id>/analise/producao/', views.linha_analise_producao, name='linha-analise-producao'),
    path('linhas/<int:linha_id>/analise/velocidade/', views.linha_analise_velocidade, name='linha-analise-velocidade'),
    path('linhas/<int:linha_id>/analise/sku/', views.linha_analise_sku, name='linha-analise-sku'),
    
    # Endpoint de Histórico Detalhado
    path('linhas/<int:linha_id>/historico-detalhado/', views.historico_linha_detalhado, name='historico-detalhado'),
    
    # Endpoint de KPIs de Produção da Fábrica (Novo)
    path('production/window/throughput/', views.FactoryProductionView.as_view({'get': 'throughput'}), name='factory-production-throughput'),
    
    # === Dashboard de Análise de Descartes ===
    path('descartes/resumo/', waste_dashboard_views.WasteDashboardSummaryView.as_view(), name='waste-dashboard-summary'),
    path('descartes/linhas/', waste_dashboard_views.WasteLinhasDisponiveisView.as_view(), name='waste-linhas-disponiveis'),

    # === Dashboard de Give Away ===
    path('giveaway/resumo/', GiveAwaySummaryView.as_view(), name='giveaway-dashboard-summary'),

    # === Arvore hierarquica fabrica -> localizacao -> linha -> equipamento ===
    path('fabrica/arvore/', FactoryTreeView.as_view(), name='factory-tree'),

    # ============================================================
    # === Flask-out: endpoints portados (Onda 1) ===
    # Substituem /flask-api/{health,health/system,realtime/all}.
    # Frontend troca FLASK_API_URL por DJANGO_API_URL nas chamadas
    # destes endpoints e o Flask correspondente pode ser removido.
    # Aceitam URLs com e sem barra final para máxima compatibilidade.
    # ============================================================
    path('health', flask_out.flask_health, name='flask-out-health'),
    path('health/', flask_out.flask_health),
    path('health/system', flask_out.flask_health_system, name='flask-out-health-system'),
    path('health/system/', flask_out.flask_health_system),
    path('health/ready', flask_out.flask_health_ready, name='flask-out-health-ready'),
    path('health/ready/', flask_out.flask_health_ready),
    path('realtime/all', flask_out.flask_realtime_all, name='flask-out-realtime-all'),
    path('realtime/all/', flask_out.flask_realtime_all),

    # === Flask-out: Onda 2 - linha/<codigo>/{...} ===
    path('linha/<str:linha_nome>/status', flask_out.flask_linha_status, name='flask-out-linha-status'),
    path('linha/<str:linha_nome>/status/', flask_out.flask_linha_status),
    path('linha/<str:linha_nome>/overview-status', flask_out.flask_linha_overview_status, name='flask-out-linha-overview-status'),
    path('linha/<str:linha_nome>/overview-status/', flask_out.flask_linha_overview_status),
    path('linha/<str:linha_nome>/ole-realtime', flask_out.flask_linha_ole_realtime, name='flask-out-linha-ole-realtime'),
    path('linha/<str:linha_nome>/ole-realtime/', flask_out.flask_linha_ole_realtime),
    path('linha/<str:linha_nome>/historico', flask_out.flask_linha_historico, name='flask-out-linha-historico'),
    path('linha/<str:linha_nome>/historico/', flask_out.flask_linha_historico),

    # === Flask-out: Onda 3 - kpis_engine + factory_kpis_engine ===
    path('linha/<str:linha_nome>/kpis', flask_out.flask_linha_kpis, name='flask-out-linha-kpis'),
    path('linha/<str:linha_nome>/kpis/', flask_out.flask_linha_kpis),
    path('equipamento/<str:eq_codigo>/kpis', flask_out.flask_equipamento_kpis, name='flask-out-eq-kpis'),
    path('equipamento/<str:eq_codigo>/kpis/', flask_out.flask_equipamento_kpis),
    path('fabrica/kpis', flask_out.flask_fabrica_kpis, name='flask-out-fabrica-kpis'),
    path('fabrica/kpis/', flask_out.flask_fabrica_kpis),
    path('fabrica/mapa', flask_out.flask_fabrica_mapa, name='flask-out-fabrica-mapa'),
    path('fabrica/mapa/', flask_out.flask_fabrica_mapa),

    # === Flask-out: Onda 4 - dados de equipamento/operacao ===
    path('equipamento/dados/<str:codigo>', flask_out.flask_equipamento_dados, name='flask-out-eq-dados'),
    path('equipamento/dados/<str:codigo>/', flask_out.flask_equipamento_dados),
    path('operacao/dados/<str:codigo>', flask_out.flask_operacao_dados, name='flask-out-op-dados'),
    path('operacao/dados/<str:codigo>/', flask_out.flask_operacao_dados),
    path('equipamento/<str:codigo>/historico-detalhado', flask_out.flask_equipamento_historico_detalhado, name='flask-out-eq-historico'),
    path('equipamento/<str:codigo>/historico-detalhado/', flask_out.flask_equipamento_historico_detalhado),

    # === Flask-out: Onda 5 - diagnostics + golden-state ===
    path('diagnostics/alerts/<str:equipamento_codigo>', flask_out.flask_diagnostics_alerts, name='flask-out-diag-alerts'),
    path('diagnostics/alerts/<str:equipamento_codigo>/', flask_out.flask_diagnostics_alerts),
    path('diagnostics/capture/<str:equipamento_codigo>', flask_out.flask_diagnostics_capture, name='flask-out-diag-capture'),
    path('diagnostics/capture/<str:equipamento_codigo>/', flask_out.flask_diagnostics_capture),
    path('golden-state/apply', flask_out.flask_golden_state_apply, name='flask-out-gs-apply'),
    path('golden-state/apply/', flask_out.flask_golden_state_apply),
    path('golden-state/pending', flask_out.flask_golden_state_pending, name='flask-out-gs-pending'),
    path('golden-state/pending/', flask_out.flask_golden_state_pending),
    path('golden-state/callback', flask_out.flask_golden_state_callback, name='flask-out-gs-callback'),
    path('golden-state/callback/', flask_out.flask_golden_state_callback),
    path('golden-state/status/<str:batch_id>', flask_out.flask_golden_state_status, name='flask-out-gs-status'),
    path('golden-state/status/<str:batch_id>/', flask_out.flask_golden_state_status),

    # === Flask-out: Onda 6 - analyze/{stats,correlation,timeseries} ===
    path('analyze/stats', analytics_views.analyze_stats, name='flask-out-analyze-stats'),
    path('analyze/stats/', analytics_views.analyze_stats),
    path('analyze/correlation', analytics_views.analyze_correlation, name='flask-out-analyze-correlation'),
    path('analyze/correlation/', analytics_views.analyze_correlation),
    path('analyze/timeseries', analytics_views.analyze_timeseries, name='flask-out-analyze-timeseries'),
    path('analyze/timeseries/', analytics_views.analyze_timeseries),

    # === Flask-out: Onda 7 - ingestao + shift reset (caminho hot do coletor) ===
    path('dados/inserir', flask_out.flask_dados_inserir, name='flask-out-dados-inserir'),
    path('dados/inserir/', flask_out.flask_dados_inserir),
    path('shift/reset', flask_out.flask_shift_reset, name='flask-out-shift-reset'),
    path('shift/reset/', flask_out.flask_shift_reset),
]
