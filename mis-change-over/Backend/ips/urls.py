from django.urls import path, include
from . import views
from ips.views import OPCCoordinatorConfigView
from rest_framework_simplejwt.views import (
 TokenRefreshView,
)

# ADICIONE A IMPORTAÇÃO DA SUA NOVA VIEW
# (Ajuste o caminho 'ips.serializers' se o seu arquivo estiver em outro app)
from ips.serializers import MyTokenObtainPairView

# ==================== URLs PRINCIPAIS ====================

urlpatterns = [
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

