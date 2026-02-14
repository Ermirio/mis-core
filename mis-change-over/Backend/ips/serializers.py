from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import (
    Produto, Linha, Equipamento, Variavel, Formato, FormatoVariavel, 
    ConfiguracaoEquipamentoVariavel, InkjetPrinter, Impressora, 
    ConexaoOPCUAServidor, DiscrepanciaSKU, TrocaSKU, LogEquipamentoTroca
)

# ==================== SERIALIZERS BASE ====================

class ConexaoOPCUAServidorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConexaoOPCUAServidor
        fields = ['id', 'nome', 'url', 'caminho_plc', 'timeout']

class VariavelSerializer(serializers.ModelSerializer):
    equipamentos_que_usam = serializers.PrimaryKeyRelatedField(
        queryset=Equipamento.objects.all(), 
        many=True, 
        required=False
    )
    equipamentos_nomes = serializers.SerializerMethodField()
    
    class Meta:
        model = Variavel
        fields = [
            'id', 'nome', 'tipo', 'descricao', 
            'equipamentos_que_usam', 'equipamentos_nomes'
        ]
    
    def get_equipamentos_nomes(self, obj):
        """Retorna os nomes dos equipamentos que usam esta variável"""
        return [eq.nome for eq in obj.equipamentos_que_usam.all()]

class EquipamentoSerializer(serializers.ModelSerializer):
    conexao_opcua = ConexaoOPCUAServidorSerializer(read_only=True)
    conexao_opcua_id = serializers.PrimaryKeyRelatedField(
        queryset=ConexaoOPCUAServidor.objects.all(), 
        source='conexao_opcua', 
        write_only=True,
        required=False
    )
    tipo_equipamento_display = serializers.CharField(source='get_tipo_equipamento_display', read_only=True)
    variaveis_utilizadas = VariavelSerializer(many=True, read_only=True)
    
    class Meta:
        model = Equipamento
        fields = [
            'id', 'nome', 'tipo_equipamento', 'tipo_equipamento_display',
            'conexao_opcua', 'conexao_opcua_id', 'ativa', 'variaveis_utilizadas'
        ]

class LinhaSerializer(serializers.ModelSerializer):
    equipamentos = EquipamentoSerializer(many=True, read_only=True)
    equipamentos_ids = serializers.PrimaryKeyRelatedField(
        queryset=Equipamento.objects.all(), 
        many=True, 
        write_only=True,
        source='equipamentos'
    )
    
    class Meta:
        model = Linha
        fields = [
            'id', 'nome', 'descricao', 'ativa',
            'equipamentos', 'equipamentos_ids'
        ]

class ImpressoraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Impressora
        fields = ['id', 'nome', 'ip', 'pasta_destino', 'ativa']

class InkjetPrinterSerializer(serializers.ModelSerializer):
    class Meta:
        model = InkjetPrinter
        fields = ['id', 'nome', 'ip_address', 'port', 'format_name', 'ativa']

# ==================== SERIALIZERS DE FORMATO ====================

class FormatoSerializer(serializers.ModelSerializer):
    variaveis = serializers.SerializerMethodField()
    produtos_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Formato
        fields = [
            'id', 'nome', 'descricao', 'variaveis', 'produtos_count',
            'criado_por', 'atualizado_por', 'criado_em', 'atualizado_em'
        ]
        read_only_fields = ['criado_por', 'atualizado_por', 'criado_em', 'atualizado_em']
    
    def get_variaveis(self, obj):
        """Retorna as variáveis do formato com seus valores"""
        formato_variaveis = obj.variaveis.all()
        return FormatoVariavelSerializer(formato_variaveis, many=True).data
    
    def get_produtos_count(self, obj):
        """Retorna a quantidade de produtos que usam este formato"""
        return obj.produtos.count()

class FormatoVariavelSerializer(serializers.ModelSerializer):
    formato = FormatoSerializer(read_only=True)
    formato_id = serializers.PrimaryKeyRelatedField(
        queryset=Formato.objects.all(), 
        source='formato', 
        write_only=True
    )
    variavel = VariavelSerializer(read_only=True)
    variavel_id = serializers.PrimaryKeyRelatedField(
        queryset=Variavel.objects.all(), 
        source='variavel', 
        write_only=True
    )
    variavel_nome = serializers.CharField(source='variavel.nome', read_only=True)
    variavel_tipo = serializers.CharField(source='variavel.tipo', read_only=True)
    
    class Meta:
        model = FormatoVariavel
        fields = [
            'id', 'formato', 'formato_id', 'variavel', 'variavel_id',
            'variavel_nome', 'variavel_tipo', 'valor',
            'criado_por', 'atualizado_por', 'criado_em', 'atualizado_em'
        ]
        read_only_fields = ['criado_por', 'atualizado_por', 'criado_em', 'atualizado_em']

class ConfiguracaoEquipamentoVariavelSerializer(serializers.ModelSerializer):
    equipamento = EquipamentoSerializer(read_only=True)
    equipamento_id = serializers.PrimaryKeyRelatedField(
        queryset=Equipamento.objects.all(), 
        source='equipamento', 
        write_only=True
    )
    variavel_mestra = VariavelSerializer(read_only=True)
    variavel_mestra_id = serializers.PrimaryKeyRelatedField(
        queryset=Variavel.objects.all(), 
        source='variavel_mestra', 
        write_only=True
    )
    equipamento_nome = serializers.CharField(source='equipamento.nome', read_only=True)
    variavel_nome = serializers.CharField(source='variavel_mestra.nome', read_only=True)
    variavel_tipo = serializers.CharField(source='variavel_mestra.tipo', read_only=True)
    
    class Meta:
        model = ConfiguracaoEquipamentoVariavel
        fields = [
            'id', 'equipamento', 'equipamento_id', 'equipamento_nome',
            'variavel_mestra', 'variavel_mestra_id', 'variavel_nome', 'variavel_tipo',
            'tag_plc', 'criado_por', 'atualizado_por', 'criado_em', 'atualizado_em'
        ]
        read_only_fields = ['criado_por', 'atualizado_por', 'criado_em', 'atualizado_em']

# ==================== SERIALIZERS DE PRODUTO ====================

class ProdutoSerializer(serializers.ModelSerializer):
    linhas = LinhaSerializer(many=True, read_only=True)
    linhas_ids = serializers.PrimaryKeyRelatedField(
        queryset=Linha.objects.all(), 
        many=True, 
        write_only=True,
        source='linhas'
    )
    formato = FormatoSerializer(read_only=True)
    formato_id = serializers.PrimaryKeyRelatedField(
        queryset=Formato.objects.all(), 
        source='formato', 
        write_only=True,
        required=False
    )
    formato_nome = serializers.CharField(source='formato.nome', read_only=True)
    variaveis_formato = serializers.SerializerMethodField()
    
    class Meta:
        model = Produto
        fields = [
            'id', 'sku', 'descricao', 'dun14', 'ean', 'filme', 'validade',
            'id_ordem_prod', 'numero_op', 'quantidade_por_pallet', 'status_op', 'dataop_str',
            'formato', 'formato_id', 'formato_nome', 'variaveis_formato',
            'linhas', 'linhas_ids',
            'criado_por', 'atualizado_por', 'criado_em', 'atualizado_em'
        ]
        read_only_fields = ['criado_por', 'atualizado_por', 'criado_em', 'atualizado_em']
    
    def get_variaveis_formato(self, obj):
        """Retorna as variáveis do formato associado ao produto"""
        if obj.formato:
            return FormatoVariavelSerializer(obj.formato.variaveis.all(), many=True).data
        return []

# ==================== SERIALIZERS DE LOGS E TROCAS ====================

class LogEquipamentoTrocaSerializer(serializers.ModelSerializer):
    tipo_equipamento_display = serializers.CharField(source='get_tipo_equipamento_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    taxa_sucesso_variaveis = serializers.SerializerMethodField()
    
    class Meta:
        model = LogEquipamentoTroca
        fields = [
            'id', 'tipo_equipamento', 'tipo_equipamento_display', 'nome_equipamento',
            'status', 'status_display', 'mensagem', 'erro_detalhado',
            'variaveis_escritas', 'variaveis_total', 'taxa_sucesso_variaveis',
            'tempo_execucao', 'ip_equipamento', 'conexao_opcua', 'data_hora'
        ]
    
    def get_taxa_sucesso_variaveis(self, obj):
        """Retorna a taxa de sucesso das variáveis"""
        return obj.get_taxa_sucesso_variaveis()

class TrocaSKUSerializer(serializers.ModelSerializer):
    logs_equipamentos = LogEquipamentoTrocaSerializer(many=True, read_only=True)
    resumo_execucao = serializers.SerializerMethodField()
    status_visual = serializers.SerializerMethodField()
    
    usuario_nome = serializers.CharField(source='usuario.username', read_only=True)
    
    class Meta:
        model = TrocaSKU
        fields = [
            'id', 'linha', 'sku_trocado', 'descricao', 'data_hora', 'sucesso',
            'detalhes', 'equipamentos_processados', 'equipamentos_sucesso', 'equipamentos_falha',
            'dun14', 'validade', 'numero_op', 'usuario', 'usuario_nome', 'ip_origem', 'tempo_execucao',
            'logs_equipamentos', 'resumo_execucao', 'status_visual'
        ]
        read_only_fields = [
            'data_hora', 'equipamentos_processados', 'equipamentos_sucesso', 
            'equipamentos_falha', 'tempo_execucao'
        ]
    
    def get_resumo_execucao(self, obj):
        """Retorna o resumo da execução"""
        return obj.get_resumo_execucao()
    
    def get_status_visual(self, obj):
        """Retorna o status visual"""
        return obj.get_status_visual()

class DiscrepanciaSKUSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiscrepanciaSKU
        fields = [
            'id', 'linha', 'sku_esperado', 'sku_atual', 'data_hora', 
            'resolvida', 'observacoes'
        ]
        read_only_fields = ['data_hora']

# ==================== SERIALIZERS PARA VIEWS ESPECÍFICAS ====================

class ProdutoResumoSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listagens de produtos"""
    formato_nome = serializers.CharField(source='formato.nome', read_only=True)
    linhas_nomes = serializers.SerializerMethodField()
    
    class Meta:
        model = Produto
        fields = [
            'id', 'sku', 'descricao', 'dun14', 'validade', 'numero_op',
            'formato_nome', 'linhas_nomes'
        ]
    
    def get_linhas_nomes(self, obj):
        """Retorna os nomes das linhas associadas"""
        return [linha.nome for linha in obj.linhas.all()]

class EquipamentoResumoSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listagens de equipamentos"""
    tipo_equipamento_display = serializers.CharField(source='get_tipo_equipamento_display', read_only=True)
    conexao_opcua_nome = serializers.CharField(source='conexao_opcua.nome', read_only=True)
    
    class Meta:
        model = Equipamento
        fields = [
            'id', 'nome', 'tipo_equipamento', 'tipo_equipamento_display',
            'conexao_opcua_nome', 'ativa'
        ]

class LinhaStatusSerializer(serializers.ModelSerializer):
    """Serializer para status das linhas"""
    ultimo_sku_enviado = serializers.SerializerMethodField()
    status_equipamentos = serializers.SerializerMethodField()
    equipamentos_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Linha
        fields = [
            'id', 'nome', 'descricao', 'ativa',
            'ultimo_sku_enviado', 'status_equipamentos', 'equipamentos_count'
        ]
    
    def get_ultimo_sku_enviado(self, obj):
        """Retorna informações do último SKU enviado"""
        return obj.get_ultimo_sku_enviado()
    
    def get_status_equipamentos(self, obj):
        """Retorna status dos equipamentos"""
        return obj.get_status_equipamentos()
    
    def get_equipamentos_count(self, obj):
        """Retorna contagem de equipamentos por tipo"""
        return {
            'total': obj.equipamentos.count(),
            'ativos': obj.equipamentos.filter(ativa=True).count(),
            'enchedoras': obj.equipamentos.filter(tipo_equipamento='ENCHEDORA').count(),
            'dosadoras': obj.equipamentos.filter(tipo_equipamento='DOSADORA').count(),
            'seladoras': obj.equipamentos.filter(tipo_equipamento='SELADORA').count(),
            'outros': obj.equipamentos.filter(tipo_equipamento='OUTRO_PLC').count(),
        }

# ==================== SERIALIZERS PARA TROCA DE SKU ====================

class TrocaSKURequestSerializer(serializers.Serializer):
    """Serializer para requisições de troca de SKU"""
    linha = serializers.CharField(max_length=10)
    sku = serializers.CharField(max_length=50)
    codigo_sku = serializers.CharField(max_length=50, required=False, allow_blank=True)
    dun14 = serializers.CharField(max_length=50, required=False, allow_blank=True)
    validade = serializers.CharField(max_length=50, required=False, allow_blank=True)
    descricao = serializers.CharField(max_length=200)
    dia = serializers.CharField(max_length=20, required=False, allow_blank=True)
    hora = serializers.CharField(max_length=20, required=False, allow_blank=True)
    usuario_id = serializers.IntegerField(required=False, allow_null=True)
    numero_op = serializers.CharField(max_length=50, required=False, allow_blank=True)

class TrocaSKUResponseSerializer(serializers.Serializer):
    """Serializer para respostas de troca de SKU"""
    mensagem = serializers.CharField()
    sucesso = serializers.BooleanField()
    resumo_execucao = serializers.DictField()
    erros = serializers.ListField(child=serializers.CharField(), required=False)
    troca_id = serializers.IntegerField(required=False)

# ==================== SERIALIZERS PARA SINCRONIZAÇÃO ====================

class SincronizacaoSKUSerializer(serializers.Serializer):
    """Serializer para dados de sincronização de SKUs"""
    codigo_sku = serializers.CharField(max_length=50)
    descricao_sku = serializers.CharField(max_length=200)
    dataop = serializers.CharField(max_length=50, required=False, allow_blank=True)
    id_ordem_prod = serializers.CharField(max_length=50, required=False, allow_blank=True)
    numero_op = serializers.CharField(max_length=50, required=False, allow_blank=True)
    dun14 = serializers.CharField(max_length=50, required=False, allow_blank=True)
    validade = serializers.CharField(max_length=50, required=False, allow_blank=True)
    quantidade_por_pallet = serializers.CharField(max_length=50, required=False, allow_blank=True)
    status_op = serializers.CharField(max_length=50, required=False, allow_blank=True)



# Serializer para as variáveis configuradas de um equipamento
class VariavelOPCConfigSerializer(serializers.ModelSerializer):
    # 'nome_variavel_mestra' corresponde ao campo 'nome' do seu modelo Variavel
    nome_variavel_mestra = serializers.CharField(source='variavel_mestra.nome', read_only=True)
    # 'tipo_variavel_mestra' corresponde ao campo 'tipo' do seu modelo Variavel
    tipo_variavel_mestra = serializers.CharField(source='variavel_mestra.tipo', read_only=True)

    class Meta:
        model = ConfiguracaoEquipamentoVariavel # Seu modelo ConfiguracaoEquipamentoVariavel
        fields = ['nome_variavel_mestra', 'tipo_variavel_mestra', 'tag_plc']

# Serializer para os equipamentos, incluindo suas configurações OPC
class EquipamentoOPCSerializer(serializers.ModelSerializer):
    # Relacionamento ForeignKey para ConexaoOPCUAServidor
    conexao_opcua_url = serializers.CharField(source='conexao_opcua.url', read_only=True)
    conexao_opcua_caminho_plc = serializers.CharField(source='conexao_opcua.caminho_plc', read_only=True)
    conexao_opcua_nome = serializers.CharField(source='conexao_opcua.nome', read_only=True)

    # Relacionamento reverse ManyToOne com ConfiguracaoEquipamentoVariavel (related_name='configuracoes_variaveis')
    variaveis_configuradas = VariavelOPCConfigSerializer(many=True, read_only=True)

    class Meta:
        model = Equipamento
        fields = [
            'nome',
            'tipo_equipamento',
            'conexao_opcua_nome', # Nome da conexão OPC
            'conexao_opcua_url', # URL do servidor OPC
            'conexao_opcua_caminho_plc', # Caminho PLC base
            'variaveis_configuradas'
        ]

class VariavelOPCConfigSerializer(serializers.ModelSerializer):
    nome_variavel_mestra = serializers.CharField(source='variavel_mestra.nome', read_only=True)
    tipo_variavel_mestra = serializers.CharField(source='variavel_mestra.tipo', read_only=True)

    class Meta:
        model = ConfiguracaoEquipamentoVariavel
        fields = ['nome_variavel_mestra', 'tipo_variavel_mestra', 'tag_plc']

class EquipamentoOPCSerializer(serializers.ModelSerializer):
    conexao_opcua_url = serializers.CharField(source='conexao_opcua.url', read_only=True)
    conexao_opcua_caminho_plc = serializers.CharField(source='conexao_opcua.caminho_plc', read_only=True)
    conexao_opcua_nome = serializers.CharField(source='conexao_opcua.nome', read_only=True)

    # CORREÇÃO: Use 'configuracoes_variaveis' para corresponder ao related_name do modelo
    configuracoes_variaveis = VariavelOPCConfigSerializer(many=True, read_only=True) # <-- LINHA AJUSTADA

    class Meta:
        model = Equipamento
        fields = [
            'nome',
            'tipo_equipamento',
            'conexao_opcua_nome',
            'conexao_opcua_url',
            'conexao_opcua_caminho_plc',
            'configuracoes_variaveis' # <-- CAMPO AJUSTADO AQUI TAMBÉM
        ]

class LinhaOPCConfigSerializer(serializers.ModelSerializer):
    equipamentos = EquipamentoOPCSerializer(many=True, read_only=True)

    class Meta:
        model = Linha
        fields = ['nome', 'equipamentos']
        
        


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        # Pega o token padrão (só com user_id)
        token = super().get_token(user)

        # --- Adiciona informações customizadas ---
        token['username'] = user.username

        # Pega o primeiro grupo do usuário (ex: "Operador")
        group = user.groups.first()
        if group:
            token['group'] = group.name
        else:
            token['group'] = None
        # ----------------------------------------

        return token

# Crie uma View customizada que usa esse Serializer
class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer