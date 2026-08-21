from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import AnalyticsProfile
from .serializers import AnalyticsProfileSerializer


class AnalyticsProfileViewSet(viewsets.ModelViewSet):
    """
    CRUD completo para perfis de Analytics.
    
    Endpoints disponíveis:
    - GET /analytics-profiles/ - Lista todos os perfis
    - GET /analytics-profiles/?linha=1 - Filtra perfis por linha
    - GET /analytics-profiles/{id}/ - Detalhes de um perfil
    - POST /analytics-profiles/ - Cria novo perfil
    - PUT/PATCH /analytics-profiles/{id}/ - Atualiza perfil
    - DELETE /analytics-profiles/{id}/ - Remove perfil
    - POST /analytics-profiles/{id}/duplicate/ - Duplica perfil existente
    """
    queryset = AnalyticsProfile.objects.all()
    serializer_class = AnalyticsProfileSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['nome', 'descricao']
    filterset_fields = ['linha']
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """
        Duplica um perfil existente com novo nome.
        
        Body: {"nome": "Novo Nome (Cópia)"}
        """
        original = self.get_object()
        new_name = request.data.get('nome', f"{original.nome} (Cópia)")
        
        # Cria duplicata
        duplicated = AnalyticsProfile.objects.create(
            nome=new_name,
            descricao=original.descricao,
            linha=original.linha,
            config=original.config,  # Cópia profunda automática do JSON
            criado_por=request.data.get('criado_por', '')
        )
        
        serializer = self.get_serializer(duplicated)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
