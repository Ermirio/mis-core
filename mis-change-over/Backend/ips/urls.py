from django.urls import path, include
from . import views
from ips.views import OPCCoordinatorConfigView, ControleViewSet, IntertravamentoLinhaViewSet
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
 TokenRefreshView,
)

# ADICIONE A IMPORTAÇÃO DA SUA NOVA VIEW
# (Ajuste o caminho 'ips.serializers' se o seu arquivo estiver em outro app)
from ips.serializers import MyTokenObtainPairView

# ==================== URLs PRINCIPAIS ====================

router = DefaultRouter()
router.register(r'api/controles', ControleViewSet, basename='controle')
router.register(r'api/intertravamentos', IntertravamentoLinhaViewSet, basename='intertravamento')

urlpatterns = [
    path('', include(router.urls)),
    # Rotas de Autenticação JWT
    path('api/token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Página inicial
    path('', views.index, name='index'),
    
    # ==================== APIs REST ====================
    
    # API para produtos (antigo cadastro-produto-flex)
    path('api/produtos/', views.ProdutoList.as_view(), name='produto-list'),
    
    # API para formatos
    path('api/formatos/', views.FormatoList.as_view(), name='formato-list'),
    
    # API para equipamentos
    path('api/equipamentos/', views.EquipamentoList.as_view(), name='equipamento-list'),
    
    # ==================== FUNCIONALIDADES DE LINHA ====================
    
    # Linhas disponíveis
    path('api/linhas-disponiveis/', views.linhas_disponiveis, name='linhas_disponiveis'),
    
    # Detalhes de linha específica
    path('api/linha/<str:linha_nome>/', views.linha_detalhes, name='linha_detalhes'),

    # Analytics de trocas por linha
    path('api/analytics/trocas/<str:linha_nome>/', views.analytics_trocas, name='analytics_trocas'),
    
    # Buscar SKUs por linha
    path('buscar-skus/', views.buscar_skus, name='buscar_skus'),
    
    # ==================== TROCA DE SKU ====================
    
    # Função principal de troca de SKU
    path('api/trocar_sku/', views.trocar_sku, name='trocar_sku'),
    
    # ==================== SINCRONIZAÇÃO ====================
    
    # Sincronizar SKUs com sistema externo
    path('sincronizar-skus/', views.sincronizar_skus, name='sincronizar_skus'),
    
    # Visualizar ordens de produção
    path('orders/', views.orders_view, name='orders_view'),
    
    # ==================== DISCREPÂNCIAS ====================
    
    # Registrar discrepância de SKU
    path('registrar-discrepancia-sku/', views.registrar_discrepancia_sku, name='registrar_discrepancia_sku'),
    
    # ==================== INTEGRAÇÃO EXTERNA ====================
    
    # Executar função Django (teste)
    path('executar-funcao-django/', views.executar_funcao_django, name='executar_funcao_django'),
    
    # Enviar para Node-RED
    path('enviar-para-node-red/', views.enviar_para_node_red, name='enviar_para_node_red'),
    
    # ==================== HEALTH CHECK ====================
    
    # Health check da API
    path('api/health/', views.api_health, name='api_health'),
    
    # ==================== PÁGINAS DE TESTE ====================
    
    # Envio de SKU (teste)
    path('send-sku/', views.send_sku, name='send_sku'),
    
    # SKUs de teste (JSON)
    path('test-skus/', views.test_skus, name='test_skus'),
    
    # Página de teste para SKUs
    path('test-skus-page/', views.test_skus_page, name='test_skus_page'),
    
    path('api/opc-configs/', OPCCoordinatorConfigView.as_view(), name='opc-configs'),

    # ==================== VALIDAÇÕES v9.0 ====================
    path('api/validacoes/', views.validacoes_pipeline, name='validacoes_pipeline'),
    path('api/validacoes/sap/liberar/', views.validacoes_sap_liberar, name='validacoes_sap_liberar'),
    path('api/validacoes/qualidade/engenheiro-aprovar/', views.validacoes_qualidade_engenheiro_aprovar, name='validacoes_qualidade_engenheiro_aprovar'),
    path('api/validacoes/qualidade/<int:validacao_id>/aprovar/', views.validacoes_qualidade_aprovar, name='validacoes_qualidade_aprovar'),

    # ==================== STATUS DO PRODUTO v9.0 ====================
    path('api/status-produto/<str:linha_nome>/', views.status_produto, name='status_produto'),
    path('api/ultima-troca/<str:linha_nome>/', views.ultima_troca, name='ultima_troca'),

    # ==================== INSIGHTS DE FORMATOS v9.0 ====================
    path('api/analytics/formatos/<str:linha_nome>/', views.analytics_formatos, name='analytics_formatos'),

    # ==================== RECIPE MONITOR (mis-recipe-intelligent) ====================
    # Sincronismo CLP → FormatoVariavel. Permissão: TIM / Engenharia / Coordenação.
    path('api/recipe-monitor/formato/<int:formato_id>/sincronizar/',
         views.recipe_monitor_sincronizar,
         name='recipe_monitor_sincronizar'),
    path('api/recipe-monitor/linha/<str:linha_nome>/formato-ativo/',
         views.recipe_monitor_formato_ativo,
         name='recipe_monitor_formato_ativo'),

    # ==================== GESTÃO DE USUÁRIOS (item 3 — só superuser) ====================
    path('api/gestao-usuarios/', views.gestao_usuarios_listar, name='gestao_usuarios_listar'),
    path('api/gestao-usuarios/<int:user_id>/renovar/', views.gestao_usuarios_renovar, name='gestao_usuarios_renovar'),

    # ==================== COMUNICAÇÃO v9.2 ====================
    path('api/chat/mencoes/nao-lidas/', views.chat_mencoes_nao_lidas, name='chat_mencoes_nao_lidas'),
    path('api/chat/nao-lidas-por-linha/', views.chat_nao_lidas_por_linha, name='chat_nao_lidas_por_linha'),
    path('api/chat/usuarios/', views.chat_usuarios, name='chat_usuarios'),
    path('api/chat/<str:linha_nome>/', views.chat_mensagens, name='chat_mensagens'),
    path('api/chat/<str:linha_nome>/enviar/', views.chat_enviar, name='chat_enviar'),
    path('api/chat/<str:linha_nome>/resumir/', views.resumir_turno, name='resumir_turno'),
    path('api/chat/<str:linha_nome>/visualizar/', views.chat_marcar_visualizado, name='chat_marcar_visualizado'),
]

# ==================== COMENTÁRIOS SOBRE MUDANÇAS ====================

"""
PRINCIPAIS MUDANÇAS NAS URLs:

1. ROTAS REMOVIDAS (modelos obsoletos):
   - /parametros-processo-equipamento/ (ReceitaEquipamentoList)
   - /parametros-processo-enchedora/ (ReceitaEnchedoraList)
   - /cadastro-produto-flex/ (renomeado para /api/produtos/)

2. ROTAS ADICIONADAS (novos modelos):
   - /api/produtos/ (ProdutoList - antigo CadastroProdutoFlexList)
   - /api/formatos/ (FormatoList)
   - /api/equipamentos/ (EquipamentoList)

3. ROTAS MANTIDAS (funcionalidades preservadas):
   - / (index)
   - /linhas-disponiveis/ (linhas_disponiveis)
   - /linha/<str:linha_nome>/ (linha_detalhes)
   - /buscar-skus/ (buscar_skus)
   - /trocar-sku/ (trocar_sku - com nova lógica)
   - /sincronizar-skus/ (sincronizar_skus - adaptado)
   - /orders/ (orders_view)
   - /registrar-discrepancia-sku/ (registrar_discrepancia_sku)
   - /executar-funcao-django/ (executar_funcao_django)
   - /enviar-para-node-red/ (enviar_para_node_red)
   - /api/health/ (api_health)
   - /send-sku/ (send_sku)
   - /test-skus/ (test_skus)
   - /test-skus-page/ (test_skus_page)

4. ORGANIZAÇÃO:
   - URLs organizadas por categoria (APIs, funcionalidades, testes)
   - Comentários explicativos para facilitar manutenção
   - Nomes consistentes seguindo padrão Django

5. COMPATIBILIDADE:
   - Mantidas todas as rotas essenciais para funcionamento
   - Adaptação gradual possível (rotas antigas podem ser mantidas temporariamente)
   - Novos endpoints para funcionalidades expandidas

NOTAS IMPORTANTES:
- A rota /trocar-sku/ mantém a mesma URL mas usa a nova lógica baseada em Formato
- A sincronização agora cria apenas Produtos, sem receitas automáticas
- Novas APIs REST seguem padrão RESTful para melhor integração
- Health check mantido para monitoramento
- Funcionalidades de teste preservadas para desenvolvimento
"""

