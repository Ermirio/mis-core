"""
Endpoint que retorna a hierarquia fabrica -> localizacao -> linha -> equipamento
para o sinotico do FactoryManagementPanel (item 15 do plano).

Substitui o uso de posicoes x,y do antigo /fabrica/mapa por uma arvore
que reflete o cadastro real. Real-time de estado/OEE pode ser
sobreposto no frontend via outro endpoint.
"""
from collections import defaultdict
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Fabrica, LinhaProducao


class FactoryTreeView(APIView):
    """GET /api/fabrica/arvore/

    Retorna lista de fabricas com agrupamento por localizacao -> linha ->
    equipamentos. Ordenacao por codigo da fabrica, depois nome da
    localizacao, depois codigo da linha.
    """

    def get(self, request):
        linhas_qs = (
            LinhaProducao.objects
            .filter(ativa=True)
            .select_related('area', 'area__fabrica')
            .prefetch_related('equipamentos')
            .order_by('area__fabrica__codigo', 'localizacao', 'codigo')
        )

        # estrutura: {fabrica_id: {fabrica, localizacoes: {localizacao_nome: [linhas]}}}
        tree = {}

        for linha in linhas_qs:
            fabrica = linha.area.fabrica if linha.area else None
            fab_key = fabrica.id if fabrica else 0
            if fab_key not in tree:
                tree[fab_key] = {
                    'fabrica': {
                        'id': fabrica.id if fabrica else None,
                        'codigo': fabrica.codigo if fabrica else 'SEM-FABRICA',
                        'nome': fabrica.nome if fabrica else 'Sem fabrica',
                        'localizacao': fabrica.localizacao if fabrica else '',
                    },
                    'localizacoes': defaultdict(list),
                }
            localizacao = (linha.localizacao or 'Sem localização').strip() or 'Sem localização'
            equipamentos = [
                {
                    'id': eq.id,
                    'codigo': eq.codigo,
                    'nome': eq.nome,
                    'tipo': eq.tipo,
                    'ordem_na_linha': eq.ordem_na_linha,
                    'status': eq.status,
                }
                for eq in sorted(linha.equipamentos.all(), key=lambda e: (e.ordem_na_linha, e.codigo))
            ]
            tree[fab_key]['localizacoes'][localizacao].append({
                'id': linha.id,
                'codigo': linha.codigo,
                'nome': linha.nome,
                'area_nome': linha.area.nome if linha.area else None,
                'meta_oee': linha.meta_oee,
                'equipamentos': equipamentos,
            })

        # Serializa em lista mantendo ordem (defaultdict preserva ordem de insercao em Py3.7+)
        resultado = []
        for fab_id in sorted(tree.keys(), key=lambda k: tree[k]['fabrica']['codigo']):
            entry = tree[fab_id]
            localizacoes = []
            for nome_loc in sorted(entry['localizacoes'].keys()):
                localizacoes.append({
                    'nome': nome_loc,
                    'linhas': entry['localizacoes'][nome_loc],
                })
            resultado.append({
                'fabrica': entry['fabrica'],
                'localizacoes': localizacoes,
            })

        return Response(resultado)
