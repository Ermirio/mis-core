from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from .models import Formato, StartBortoletto, Estatisticas
from .serializers import FormatoSerializer, StartBortolettoSerializer, EstatisticasSerializer
from ips.models import Linha

class FormatoList(APIView):
    def post(self, request):
        serializer = FormatoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class StartBortolettoList(APIView):
    def post(self, request):
        serializer = StartBortolettoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            Estatisticas.objects.update_or_create(
                start_bortoletto=serializer.instance,
                defaults={'velocidade_real': None}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class EstatisticasDetail(APIView):
    def get(self, request, pk):
        estatistica = get_object_or_404(Estatisticas, pk=pk)
        serializer = EstatisticasSerializer(estatistica)
        return Response(serializer.data)

    def put(self, request, pk):
        estatistica = get_object_or_404(Estatisticas, pk=pk)
        serializer = EstatisticasSerializer(estatistica, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
def atualizar_dados(request):
    if request.method != "POST":
        return JsonResponse({"mensagem": "Método não permitido"}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        linhas_data = data.get("linhas", [])
        if not linhas_data:
            return JsonResponse({"mensagem": "Nenhuma linha fornecida"}, status=400)

        resultados = []
        for item in linhas_data:
            linha_nome = item.get("linha")
            gramas = item.get("gramas")
            velocidade_std = item.get("velocidade_std")
            velocidade_atual = item.get("velocidade_atual")
            velocidade_planejada_final = item.get("velocidade_planejada_final")
            velocidade_real = item.get("velocidade_real")
            data_inicio = item.get("data_inicio")

            linha = get_object_or_404(Linha, nome=linha_nome)
            formato, created = Formato.objects.get_or_create(
                gramas=gramas,
                defaults={'velocidade_std': velocidade_std}
            )
            start, created = StartBortoletto.objects.get_or_create(
                linha=linha,
                formato=formato,
                defaults={
                    'data_inicio': data_inicio,
                    'velocidade_atual': velocidade_atual,
                    'velocidade_planejada_final': velocidade_planejada_final
                }
            )
            estatistica, created = Estatisticas.objects.get_or_create(
                start_bortoletto=start,
                defaults={'velocidade_real': velocidade_real}
            )
            resultados.append({
                'formato': FormatoSerializer(formato).data,
                'start_bortoletto': StartBortolettoSerializer(start).data,
                'estatisticas': EstatisticasSerializer(estatistica).data
            })

        return JsonResponse({"mensagem": "Dados atualizados com sucesso", "data": resultados})
    except json.JSONDecodeError:
        return JsonResponse({"mensagem": "Erro ao decodificar JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"mensagem": f"Erro ao processar: {str(e)}"}, status=500)