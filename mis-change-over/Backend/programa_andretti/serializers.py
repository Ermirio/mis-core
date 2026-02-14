from rest_framework import serializers
from .models import Formato, StartBortoletto, Estatisticas

class FormatoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Formato
        fields = '__all__'

class StartBortolettoSerializer(serializers.ModelSerializer):
    class Meta:
        model = StartBortoletto
        fields = '__all__'

class EstatisticasSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estatisticas
        fields = '__all__'