import logging
from django.utils import timezone
from datetime import timedelta
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    WaveAndretti, MetaVelocidadeLinha, LeituraVelocidade,
    CategoriaAcao, AcaoAndretti,
)
from .serializers import (
    WaveAndrettiSerializer, MetaVelocidadeLinhaSerializer,
    LeituraVelocidadeCreateSerializer,
    CategoriaAcaoSerializer, AcaoAndrettiSerializer,
)
from ips.models import Linha

logger = logging.getLogger(__name__)


# ── Waves ───────────────────────────────────────────────────────────────────

class WaveList(generics.ListCreateAPIView):
    queryset = WaveAndretti.objects.all()
    serializer_class = WaveAndrettiSerializer


class WaveDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = WaveAndretti.objects.all()
    serializer_class = WaveAndrettiSerializer


# ── Metas ───────────────────────────────────────────────────────────────────

class MetaList(generics.ListCreateAPIView):
    serializer_class = MetaVelocidadeLinhaSerializer

    def get_queryset(self):
        qs = MetaVelocidadeLinha.objects.select_related('linha', 'wave', 'formato')
        wave_id = self.request.query_params.get('wave')
        if wave_id:
            qs = qs.filter(wave_id=wave_id)
        return qs


class MetaDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = MetaVelocidadeLinha.objects.select_related('linha', 'wave', 'formato')
    serializer_class = MetaVelocidadeLinhaSerializer


# ── Categorias ──────────────────────────────────────────────────────────────

class CategoriaList(generics.ListAPIView):
    serializer_class = CategoriaAcaoSerializer

    def get_queryset(self):
        qs = CategoriaAcao.objects.all()
        area = self.request.query_params.get('area')
        if area:
            qs = qs.filter(area=area)
        return qs


# ── Ações ───────────────────────────────────────────────────────────────────

class AcaoList(generics.ListCreateAPIView):
    serializer_class = AcaoAndrettiSerializer

    def get_queryset(self):
        qs = AcaoAndretti.objects.select_related('linha', 'wave', 'categoria', 'criado_por')
        wave_id = self.request.query_params.get('wave')
        linha_id = self.request.query_params.get('linha')
        area = self.request.query_params.get('area')
        status_filter = self.request.query_params.get('status')
        if wave_id:
            qs = qs.filter(wave_id=wave_id)
        if linha_id:
            qs = qs.filter(linha_id=linha_id)
        if area:
            qs = qs.filter(area=area)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def perform_create(self, serializer):
        serializer.save(criado_por=self.request.user)


class AcaoDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = AcaoAndretti.objects.select_related('linha', 'wave', 'categoria')
    serializer_class = AcaoAndrettiSerializer


# ── Leitura manual de velocidade ────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def registrar_leitura_manual(request):
    """
    Registra leitura manual de velocidade vinculada a uma meta específica.
    Esta leitura se torna a velocidade atual exibida no card até ser substituída
    por uma nova leitura manual para a mesma meta.
    """
    serializer = LeituraVelocidadeCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    velocidade = serializer.validated_data.get('velocidade')
    if not velocidade or float(velocidade) <= 0:
        return Response(
            {'erro': 'Velocidade manual deve ser maior que zero.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    leitura = serializer.save(fonte='MANUAL')
    return Response(LeituraVelocidadeCreateSerializer(leitura).data, status=status.HTTP_201_CREATED)


# ── Dashboard ────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_andretti(request):
    """
    Retorna um card por MetaVelocidadeLinha (linha + formato).

    Query params:
        wave (int, obrigatório)
        linha_nome (str, opcional) — filtra por nome da linha (ex: L15)
    """
    wave_id = request.query_params.get('wave')
    if not wave_id:
        return Response({'erro': 'Parâmetro "wave" obrigatório.'}, status=400)

    try:
        wave = WaveAndretti.objects.get(pk=wave_id)
    except WaveAndretti.DoesNotExist:
        return Response({'erro': 'Wave não encontrada.'}, status=404)

    metas_qs = (
        MetaVelocidadeLinha.objects
        .filter(wave=wave)
        .select_related('linha', 'formato')
        .order_by('linha__nome', 'formato__gramas')
    )

    linha_nome = request.query_params.get('linha_nome')
    if linha_nome:
        metas_qs = metas_qs.filter(linha__nome=linha_nome)

    cards = []

    for meta in metas_qs:
        linha = meta.linha
        formato_gramas = (meta.formato.gramas if meta.formato and meta.formato.gramas else None)

        # Velocidade atual = última leitura MANUAL > 0 vinculada a esta meta.
        # Leituras OPC são usadas apenas no gráfico de tendência.
        ultima = (
            LeituraVelocidade.objects
            .filter(meta=meta, fonte='MANUAL', velocidade__gt=0)
            .order_by('-timestamp')
            .first()
        )
        vel_atual = float(ultima.velocidade) if ultima else None

        vel_meta = float(meta.velocidade_meta)
        vel_pad  = float(meta.velocidade_padrao)

        pct = None
        if vel_atual is not None and vel_meta:
            if vel_pad < vel_meta:
                pct = round(max(0, (vel_atual - vel_pad) / (vel_meta - vel_pad) * 100), 1)
            else:
                pct = round(vel_atual / vel_meta * 100, 1)

        cards.append({
            'meta_id':           meta.pk,
            'linha_id':          linha.pk,
            'linha_nome':        linha.nome,
            'formato_id':        meta.formato_id,
            'formato_gramas':    formato_gramas,
            'formato_display':   f"{formato_gramas}g" if formato_gramas else (meta.formato.nome if meta.formato else 'Geral'),
            'velocidade_padrao': vel_pad,
            'velocidade_meta':   vel_meta,
            'unidade':           meta.unidade,
            'ganho_percentual':  meta.ganho_percentual,
            'velocidade_atual':  vel_atual,
            'ultima_leitura':    ultima.timestamp.isoformat() if ultima else None,
            'fonte_leitura':     ultima.fonte if ultima else None,
            'pct_atingimento':   pct,
            'tag_velocidade_opc': linha.tag_velocidade_opc,
            'tag_formato_opc':   linha.tag_formato_opc,
        })

    return Response({
        'wave':  WaveAndrettiSerializer(wave).data,
        'cards': cards,
    })


# ── Trend de velocidade ──────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def trend_velocidade(request, linha_id):
    """
    Últimas leituras de velocidade de uma linha, opcionalmente filtradas por formato.

    Query params:
        horas (int, default=24)
        formato_gramas (int, opcional)
    """
    try:
        linha = Linha.objects.get(pk=linha_id)
    except Linha.DoesNotExist:
        return Response({'erro': 'Linha não encontrada.'}, status=404)

    horas = min(int(request.query_params.get('horas', 24)), 168)
    desde = timezone.now() - timedelta(hours=horas)

    # Trend usa apenas leituras OPC (automáticas) para mostrar comportamento real da linha.
    qs = LeituraVelocidade.objects.filter(
        linha=linha, fonte='OPC', timestamp__gte=desde,
        velocidade__isnull=False, velocidade__gt=0,
    )
    fmt = request.query_params.get('formato_gramas')
    if fmt:
        qs = qs.filter(formato_gramas=int(fmt))

    leituras = qs.order_by('timestamp').values('timestamp', 'velocidade', 'fonte', 'formato_gramas')

    dados = [
        {
            'hora':           l['timestamp'].strftime('%H:%M'),
            'timestamp':      l['timestamp'].isoformat(),
            'velocidade':     float(l['velocidade']),
            'fonte':          l['fonte'],
            'formato_gramas': l['formato_gramas'],
        }
        for l in leituras
    ]
    return Response({'linha': linha.nome, 'horas': horas, 'dados': dados})
