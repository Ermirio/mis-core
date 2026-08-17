from rest_framework import serializers
from .models import (
    WaveAndretti, MetaVelocidadeLinha, LeituraVelocidade,
    CategoriaAcao, AcaoAndretti,
)


class WaveAndrettiSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaveAndretti
        fields = '__all__'


class MetaVelocidadeLinhaSerializer(serializers.ModelSerializer):
    linha_nome      = serializers.CharField(source='linha.nome', read_only=True)
    wave_nome       = serializers.CharField(source='wave.nome', read_only=True)
    formato_gramas   = serializers.SerializerMethodField()
    formato_display  = serializers.SerializerMethodField()
    ganho_percentual = serializers.FloatField(read_only=True)

    class Meta:
        model = MetaVelocidadeLinha
        fields = '__all__'

    def get_formato_gramas(self, obj):
        return obj.formato.gramas if obj.formato and obj.formato.gramas else None

    def get_formato_display(self, obj):
        if obj.formato:
            return f"{obj.formato.gramas}g" if obj.formato.gramas else obj.formato.nome
        return 'Geral'


class LeituraVelocidadeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeituraVelocidade
        fields = ['linha', 'meta', 'velocidade', 'fonte', 'formato_gramas']


class CategoriaAcaoSerializer(serializers.ModelSerializer):
    area_display = serializers.CharField(source='get_area_display', read_only=True)

    class Meta:
        model = CategoriaAcao
        fields = '__all__'


class AcaoAndrettiSerializer(serializers.ModelSerializer):
    linha_nome     = serializers.CharField(source='linha.nome', read_only=True)
    wave_nome      = serializers.CharField(source='wave.nome', read_only=True)
    area_display   = serializers.CharField(source='get_area_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    categoria_nome = serializers.CharField(source='categoria.nome', read_only=True)
    atrasada       = serializers.SerializerMethodField()

    class Meta:
        model = AcaoAndretti
        fields = '__all__'

    def get_atrasada(self, obj):
        from django.utils import timezone
        if obj.status in ('concluida', 'cancelada'):
            return False
        return obj.prazo_execucao < timezone.now().date()
