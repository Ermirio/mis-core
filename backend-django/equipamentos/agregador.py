"""
Agregador de Dados - Converte dados em tempo real em métricas periódicas (InfluxDB)
====================================================================

Este módulo é responsável por:
1. Buscar dados do InfluxDB (tempo real)
2. Agregar em períodos (HORA, TURNO, DIA)
3. Calcular KPIs (OEE, Disponibilidade, Performance, Qualidade)
4. Salvar em InfluxDB (metricas_agregadas) com hierarquia (Equipamento -> Linha -> Área -> Fábrica)
"""

import logging
from datetime import datetime, timedelta, time
from django.utils import timezone
from django.db import models
from django.db.models import Sum, Avg
from influxdb import InfluxDBClient
from decouple import config

from .models import (
    Equipamento, LinhaProducao, Area, Fabrica,
    TurnoProducao, EventoEstadoEquipamento, HistoricoSKU
)
from .tonnage_utils import (
    calcular_toneladas,
    calcular_vazao_ton_hora,
    obter_formato_equipamento
)

logger = logging.getLogger('Agregador')

# Configuração InfluxDB
INFLUX_HOST = config('INFLUXDB_HOST', default='127.0.0.1')
INFLUX_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUX_DB = config('INFLUXDB_DATABASE', default='industrial_db')
INFLUX_USER = config('INFLUXDB_USER', default=None)
INFLUX_PASS = config('INFLUXDB_USER_PASSWORD', default=None)

influx_client = InfluxDBClient(
    host=INFLUX_HOST,
    port=INFLUX_PORT,
    username=INFLUX_USER,
    password=INFLUX_PASS,
    database=INFLUX_DB
)


class AgregadorDados:
    """Classe principal para agregação de dados"""
    
    def __init__(self):
        self.influx_client = influx_client
    
    def obter_turno_atual(self, data: datetime = None) -> TurnoProducao:
        """Retorna o turno em andamento em uma data/hora específica."""
        if data is None:
            data = timezone.now()
        
        if timezone.is_aware(data):
            data = timezone.localtime(data)
            
        hora_atual = data.time()
        turnos = TurnoProducao.objects.filter(ativo=True).order_by('hora_inicio')
        
        for turno in turnos:
            if turno.hora_inicio <= hora_atual < turno.hora_fim:
                return turno
            if turno.hora_fim < turno.hora_inicio:
                if hora_atual >= turno.hora_inicio or hora_atual < turno.hora_fim:
                    return turno
        
        return turnos.first()
    
    def obter_intervalo_turno(self, turno: TurnoProducao, data: datetime) -> tuple:
        """Retorna (inicio, fim) de um turno em uma data específica."""
        data_base = data.date()
        
        inicio = timezone.make_aware(datetime.combine(data_base, turno.hora_inicio))
        fim = timezone.make_aware(datetime.combine(data_base, turno.hora_fim))
        
        if turno.hora_fim < turno.hora_inicio:
            if data.time() < turno.hora_fim:
                inicio = inicio - timedelta(days=1)
            else:
                fim = fim + timedelta(days=1)
        
        return inicio, fim
    
    def buscar_dados_influx(self, equipamento_codigo: str, inicio: datetime, fim: datetime) -> list:
        """Busca dados brutos de produção do InfluxDB."""
        try:
            query = f"""
                SELECT 
                    contagem_entrada,
                    contagem_saida,
                    descarte,
                    velocidade_atual
                FROM producao
                WHERE equipamento_codigo = '{equipamento_codigo}'
                AND time >= '{inicio.isoformat()}'
                AND time <= '{fim.isoformat()}'
                ORDER BY time ASC
            """
            result = self.influx_client.query(query)
            return list(result.get_points())
        except Exception as e:
            logger.error(f"Erro ao buscar dados do InfluxDB: {e}")
            return []

    def _escrever_influx(self, tags: dict, fields: dict, timestamp: datetime):
        """Escreve métricas agregadas no InfluxDB."""
        try:
            json_body = [
                {
                    "measurement": "metricas_agregadas",
                    "tags": tags,
                    "time": timestamp.isoformat(),
                    "fields": fields
                }
            ]
            self.influx_client.write_points(json_body)
        except Exception as e:
            logger.error(f"Erro ao escrever no InfluxDB: {e}")

    def _calcular_velocidade_media(self, dados: list) -> float:
        if not dados: return 0.0
        velocidades = [d.get('velocidade_atual', 0) for d in dados if d.get('velocidade_atual') is not None]
        if not velocidades: return 0.0
        return sum(velocidades) / len(velocidades)

    def _calcular_delta_com_resets(self, dados: list, key: str) -> int:
        if not dados: return 0
        total_delta = 0
        anterior = dados[0].get(key, 0) or 0
        
        for d in dados[1:]:
            atual = d.get(key, 0) or 0
            if atual < anterior:
                total_delta += atual
            else:
                total_delta += (atual - anterior)
            anterior = atual
            
        return int(total_delta)

    def obter_sku_ativo(self, linha: LinhaProducao, data_hora: datetime):
        return HistoricoSKU.objects.filter(
            linha=linha,
            data_inicio__lte=data_hora
        ).filter(
            models.Q(data_fim__gte=data_hora) | models.Q(data_fim__isnull=True)
        ).order_by('-data_inicio').first()

    def sincronizar_dados_producao(self, equipamento: Equipamento, data_hora: datetime):
        """Sincroniza SKU/OP do InfluxDB para MySQL (HistoricoSKU)."""
        try:
            query = f"""
                SELECT last("sku_codigo") as sku, last("ordem_producao") as op, last("op") as op_alt
                FROM producao
                WHERE equipamento_codigo = '{equipamento.codigo}'
                AND time <= '{data_hora.isoformat()}'
            """
            result = self.influx_client.query(query)
            points = list(result.get_points())
            
            if not points: return

            dados = points[0]
            sku_codigo = dados.get('sku')
            op_codigo = dados.get('op') or dados.get('op_alt')

            if not sku_codigo: return

            historico_atual = self.obter_sku_ativo(equipamento.linha, data_hora)
            
            novo_sku = False
            if not historico_atual:
                novo_sku = True
            elif str(historico_atual.produto.codigo) != str(sku_codigo):
                novo_sku = True
            elif op_codigo and historico_atual.ordem_producao != str(op_codigo):
                novo_sku = True
            
            if novo_sku:
                logger.info(f"Detectada mudança de produção: SKU={sku_codigo}, OP={op_codigo}")
                if historico_atual:
                    historico_atual.data_fim = data_hora
                    historico_atual.save()
                
                from .models import Produto
                produto = Produto.objects.filter(codigo=sku_codigo).first()
                if not produto:
                    produto = Produto.objects.create(
                        codigo=sku_codigo,
                        descricao=f"Produto Auto {sku_codigo}",
                        peso_unitario=1.0
                    )

                HistoricoSKU.objects.create(
                    linha=equipamento.linha,
                    produto=produto,
                    ordem_producao=op_codigo or f"OP-{datetime.now().strftime('%Y%m%d%H%M')}",
                    data_inicio=data_hora
                )
        except Exception as e:
            logger.error(f"Erro ao sincronizar dados de produção: {e}")

    # =========================================================================
    # CÁLCULO DE MÉTRICAS (EQUIPAMENTO)
    # =========================================================================

    def calcular_metricas_equipamento(self, equipamento: Equipamento, inicio: datetime, fim: datetime, periodo: str, turno_nome: str = None):
        """Calcula métricas de um equipamento e salva no InfluxDB."""
        dados = self.buscar_dados_influx(equipamento.codigo, inicio, fim)
        if not dados: return

        contagem_entrada = self._calcular_delta_com_resets(dados, 'contagem_entrada')
        contagem_saida = self._calcular_delta_com_resets(dados, 'contagem_saida')
        
        tempos = EventoEstadoEquipamento.calcular_tempos_por_estado(equipamento, inicio, fim)
        
        formato_gramas = obter_formato_equipamento(equipamento)
        toneladas = calcular_toneladas(contagem_saida, formato_gramas) if formato_gramas else 0.0
        vazao_ton_h = calcular_vazao_ton_hora(toneladas, tempos['tempo_producao']) if toneladas > 0 else 0.0
        
        historico_sku = self.obter_sku_ativo(equipamento.linha, fim)
        meta_producao = historico_sku.meta_producao if historico_sku else 0
        
        # OEE
        tempo_total_min = (fim - inicio).total_seconds() / 60.0
        velocidade_real = self._calcular_velocidade_media(dados)
        velocidade_planejada = equipamento.linha.velocidade_planejada
        
        disponibilidade = (tempos['tempo_producao'] / tempo_total_min * 100) if tempo_total_min > 0 else 0
        performance = (velocidade_real / velocidade_planejada * 100) if velocidade_planejada > 0 else 0
        descarte = max(0, contagem_entrada - contagem_saida)
        qualidade = ((contagem_saida - descarte) / contagem_saida * 100) if contagem_saida > 0 else 100
        oee = (disponibilidade * performance * qualidade) / 10000

        # Tags e Fields para InfluxDB
        tags = {
            "nivel": "equipamento",
            "codigo": equipamento.codigo,
            "linha_codigo": equipamento.linha.codigo,
            "periodo": periodo,
            "turno": turno_nome or ""
        }
        
        fields = {
            "producao": float(contagem_saida),
            "toneladas": float(toneladas),
            "meta": float(meta_producao),
            "meta_toneladas": float(meta_producao * (formato_gramas or 0) / 1_000_000),
            "oee": float(oee),
            "disponibilidade": float(disponibilidade),
            "performance": float(performance),
            "qualidade": float(qualidade),
            "vazao": float(vazao_ton_h),
            "velocidade_real": float(velocidade_real),
            "velocidade_planejada": float(velocidade_planejada),
            "tempo_producao": float(tempos['tempo_producao']),
            "tempo_parada": float(tempos['tempo_parada']),
            "tempo_setup": float(tempos['tempo_setup']),
            "descarte": float(descarte)
        }
        
        self._escrever_influx(tags, fields, inicio)
        logger.info(f"Métrica {periodo} salva (Influx): {equipamento.nome}")

    # =========================================================================
    # AGREGAÇÃO HIERÁRQUICA (GENÉRICA)
    # =========================================================================

    def _agregar_metricas_filhas(self, nivel_filho: str, codigo_pai: str, inicio: datetime, periodo: str, turno_nome: str = None) -> dict:
        """
        Busca métricas dos filhos no InfluxDB e agrega.
        Regras:
        - Soma: producao, toneladas, meta, tempo_producao, tempo_parada, descarte
        - Média Ponderada (por toneladas): oee, disponibilidade, performance, qualidade
        """
        # Query para buscar métricas dos filhos
        # Ex: Se pai é Linha L01, busca filhos com linha_codigo=L01 e nivel=equipamento
        
        filtro_pai = ""
        if nivel_filho == "equipamento":
            filtro_pai = f"AND linha_codigo = '{codigo_pai}'"
        elif nivel_filho == "linha":
            # Precisamos saber quais linhas pertencem à área. Influx não tem join.
            # Então buscamos códigos das linhas da área no MySQL
            area = Area.objects.filter(codigo=codigo_pai).first()
            if not area: return None
            linhas_codigos = [l.codigo for l in area.linhas.all()]
            if not linhas_codigos: return None
            lista_codigos = "|".join(linhas_codigos)
            filtro_pai = f"AND codigo =~ /^{lista_codigos}$/"
        elif nivel_filho == "area":
            fabrica = Fabrica.objects.filter(codigo=codigo_pai).first()
            if not fabrica: return None
            areas_codigos = [a.codigo for a in fabrica.areas.all()]
            if not areas_codigos: return None
            lista_codigos = "|".join(areas_codigos)
            filtro_pai = f"AND codigo =~ /^{lista_codigos}$/"

        turno_filter = f"AND turno = '{turno_nome}'" if turno_nome else ""
        
        query = f"""
            SELECT *
            FROM metricas_agregadas
            WHERE nivel = '{nivel_filho}'
            AND periodo = '{periodo}'
            AND time = '{inicio.isoformat()}'
            {filtro_pai}
            {turno_filter}
        """
        
        result = self.influx_client.query(query)
        pontos = list(result.get_points())
        
        if not pontos:
            return None

        # Inicializa acumuladores
        soma_absoluta = {
            "producao": 0.0, "toneladas": 0.0, "meta": 0.0, "meta_toneladas": 0.0, 
            "tempo_producao": 0.0, "tempo_parada": 0.0, "tempo_setup": 0.0, "descarte": 0.0
        }
        
        ponderados = {
            "oee": 0.0, "disponibilidade": 0.0, "performance": 0.0, "qualidade": 0.0
        }
        
        total_peso = 0.0
        
        for p in pontos:
            peso = p.get('toneladas', 0)
            # Fallback de peso: se toneladas for 0, usa tempo_producao, senão 1
            if peso <= 0:
                peso = p.get('tempo_producao', 0)
            if peso <= 0:
                peso = 1.0
                
            total_peso += peso
            
            # Soma Absoluta
            for k in soma_absoluta:
                soma_absoluta[k] += p.get(k, 0)
            
            # Acumula Ponderados
            for k in ponderados:
                ponderados[k] += (p.get(k, 0) * peso)
        
        # Finaliza médias ponderadas
        metricas_finais = soma_absoluta.copy()
        if total_peso > 0:
            for k in ponderados:
                metricas_finais[k] = ponderados[k] / total_peso
        else:
            # Se peso total for 0, faz média simples
            qtd = len(pontos)
            if qtd > 0:
                for k in ponderados:
                    metricas_finais[k] = sum(p.get(k, 0) for p in pontos) / qtd
        
        # Recalcula Vazão (Total Ton / Total Tempo Produção)
        if metricas_finais['tempo_producao'] > 0:
            metricas_finais['vazao'] = metricas_finais['toneladas'] / (metricas_finais['tempo_producao'] / 60.0)
        else:
            metricas_finais['vazao'] = 0.0
            
        return metricas_finais

    def calcular_agregacao_hierarquica(self, nivel_pai: str, codigo_pai: str, nivel_filho: str, inicio: datetime, periodo: str, turno_nome: str = None):
        """Calcula agregação de um nível superior e salva no InfluxDB."""
        
        metricas = self._agregar_metricas_filhas(nivel_filho, codigo_pai, inicio, periodo, turno_nome)
        
        if metricas:
            tags = {
                "nivel": nivel_pai,
                "codigo": codigo_pai,
                "periodo": periodo,
                "turno": turno_nome or ""
            }
            self._escrever_influx(tags, metricas, inicio)
            logger.info(f"Agregação {nivel_pai} ({codigo_pai}) concluída.")

    # =========================================================================
    # ORQUESTRADORES DE AGREGAÇÃO
    # =========================================================================

    def agregar_turno_atual(self):
        """Agrega dados do turno ATUAL em tempo real (frequência alta)"""
        agora = timezone.now()
        turno_atual = self.obter_turno_atual(agora)
        if not turno_atual: return
        
        inicio, _ = self.obter_intervalo_turno(turno_atual, agora)
        
        # 1. Equipamentos (Nível Base)
        for equipamento in Equipamento.objects.filter(status='ATIVO'):
            self.sincronizar_dados_producao(equipamento, agora)
            self.calcular_metricas_equipamento(equipamento, inicio, agora, 'TURNO', turno_atual.nome)
            
        # 2. Linhas (Agrega Equipamentos)
        for linha in LinhaProducao.objects.filter(ativa=True):
            self.calcular_agregacao_hierarquica('linha', linha.codigo, 'equipamento', inicio, 'TURNO', turno_atual.nome)
            
        # 3. Áreas (Agrega Linhas)
        for area in Area.objects.all():
            self.calcular_agregacao_hierarquica('area', area.codigo, 'linha', inicio, 'TURNO', turno_atual.nome)
            
        # 4. Fábricas (Agrega Áreas)
        for fabrica in Fabrica.objects.all():
            self.calcular_agregacao_hierarquica('fabrica', fabrica.codigo, 'area', inicio, 'TURNO', turno_atual.nome)

    def agregar_ultima_hora(self):
        """Agrega dados da última hora fechada."""
        agora = timezone.now()
        hora_inicio = agora.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        hora_fim = hora_inicio + timedelta(hours=1)
        
        # 1. Equipamentos
        for equipamento in Equipamento.objects.filter(status='ATIVO'):
            self.calcular_metricas_equipamento(equipamento, hora_inicio, hora_fim, 'HORA')
            
        # 2. Linhas
        for linha in LinhaProducao.objects.filter(ativa=True):
            self.calcular_agregacao_hierarquica('linha', linha.codigo, 'equipamento', hora_inicio, 'HORA')
            
        # 3. Áreas
        for area in Area.objects.all():
            self.calcular_agregacao_hierarquica('area', area.codigo, 'linha', hora_inicio, 'HORA')
            
        # 4. Fábricas
        for fabrica in Fabrica.objects.all():
            self.calcular_agregacao_hierarquica('fabrica', fabrica.codigo, 'area', hora_inicio, 'HORA')


# Instância global
agregador = AgregadorDados()