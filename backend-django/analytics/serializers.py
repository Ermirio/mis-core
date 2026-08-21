from rest_framework import serializers
from .models import AnalyticsProfile


class AnalyticsProfileSerializer(serializers.ModelSerializer):
    """Serializer para perfis de Analytics com informações da linha"""
    linha_codigo = serializers.CharField(source='linha.codigo', read_only=True)
    linha_nome = serializers.CharField(source='linha.nome', read_only=True)
    
    class Meta:
        model = AnalyticsProfile
        fields = [
            'id', 'nome', 'descricao', 
            'linha', 'linha_codigo', 'linha_nome',
            'config', 
            'criado_em', 'atualizado_em', 'criado_por'
        ]
        read_only_fields = ['criado_em', 'atualizado_em']
    
    def validate_config(self, value):
        """Valida estrutura mínima do config JSON"""
        required_keys = ['selectedTags', 'hoursBack', 'activeTab']
        missing_keys = [key for key in required_keys if key not in value]
        
        if missing_keys:
            raise serializers.ValidationError(
                f"Campos obrigatórios ausentes no config: {', '.join(missing_keys)}"
            )
        
        return value
    
    def validate_nome(self, value):
        """Valida que nome não é vazio"""
        if not value.strip():
            raise serializers.ValidationError("Nome do perfil não pode ser vazio")
        return value.strip()
