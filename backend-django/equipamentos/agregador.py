"""
Agregador de Dados - Converte dados em tempo real em métricas periódicas
====================================================================

Este módulo é responsável por:
1. Buscar dados do InfluxDB (tempo real)
2. Agregar em períodos (HORA, TURNO, DIA)
3. Calcular KPIs (OEE, Disponibilidade, Performance, Qualidade)
4. Salvar em Django/MySQL
"""

import logging
from datetime import datetime, timedelta, time
from django.utils import timezone
from django.db import models
from django.db.models import Sum, Avg
from influxdb import InfluxDBClient
from decouple import config

from .models import (
    MetricaProducao, Equipamento, LinhaProducao, 
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
        """
        Retorna o turno em andamento em uma data/hora específica.
        
        Args:
            data: datetime para verificar. Se None, usa agora.
        
        Returns:
            TurnoProducao ou None
        """
        if data is None:
            data = timezone.now()
        
        # Converter para horário local para comparar com horários dos turnos
        if timezone.is_aware(data):
            data = timezone.localtime(data)
            
        hora_atual = data.time()
        turnos = TurnoProducao.objects.filter(ativo=True).order_by('hora_inicio')
        
        for turno in turnos:
            if turno.hora_inicio <= hora_atual < turno.hora_fim:
                return turno
            # Caso especial: turno que cruza meia-noite (ex: 22:00 as 06:00)
            if turno.hora_fim < turno.hora_inicio:
                if hora_atual >= turno.hora_inicio or hora_atual < turno.hora_fim:
                    return turno
        
        # Se não encontrar turno ativo, retorna o primeiro (fallback)
        return turnos.first()
    
    def obter_intervalo_turno(self, turno: TurnoProducao, data: datetime) -> tuple:
        """
        Retorna (inicio, fim) de um turno em uma data específica.
        
        Args:
            turno: TurnoProducao
            data: datetime (usa apenas a data)
        
        Returns:
            (datetime_inicio, datetime_fim)
        """
        data_base = data.date()
        
        inicio = timezone.make_aware(
            datetime.combine(data_base, turno.hora_inicio)
        )
        fim = timezone.make_aware(
            datetime.combine(data_base, turno.hora_fim)
        )
        
        # Se hora_fim < hora_inicio, significa que turno passa pela meia-noite
        if turno.hora_fim < turno.hora_inicio:
            # Se a hora atual for menor que o fim, o início foi ontem
            if data.time() < turno.hora_fim:
                inicio = inicio - timedelta(days=1)
            else:
                # Se a hora atual for maior que o início, o fim é amanhã
                fim = fim + timedelta(days=1)
        
        return inicio, fim
    
    def buscar_dados_influx(self, equipamento_codigo: str, inicio: datetime, fim: datetime) -> list:
        """
        Busca dados do InfluxDB para um equipamento em um período.
        
        Args:
            equipamento_codigo: código do equipamento
            inicio: datetime inicial
            fim: datetime final
        
        Returns:
            Lista de pontos de dados
        """
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

    def _calcular_velocidade_media(self, dados: list) -> float:
        """Calcula velocidade média a partir de dados do InfluxDB"""
        if not dados:
            return 0.0
        
        velocidades = [d.get('velocidade_atual', 0) for d in dados if d.get('velocidade_atual') is not None]
        
        if not velocidades:
            return 0.0
        
        return sum(velocidades) / len(velocidades)

    def _calcular_delta_com_resets(self, dados: list, key: str) -> int:
        """
        Calcula o delta de um contador acumulativo, considerando resets.
        Se o valor atual for menor que o anterior, assume-se um reset.
        """
        if not dados:
            return 0
            
        total_delta = 0
        anterior = dados[0].get(key)
        if anterior is None:
            anterior = 0
        
        # Se o primeiro valor já for alto, não temos como saber quanto foi produzido antes dele no período
        # Mas para cálculo de delta dentro do período, começamos do primeiro ponto.
        
        for d in dados[1:]:
            atual = d.get(key)
            if atual is None:
                atual = 0
            
            if atual < anterior:
                # Reset detectado!
                # Assumimos que a produção foi: (acumulado até reset) + (novo acumulado)
                # Como não sabemos o valor máximo antes do reset, assumimos que 'anterior' era o máximo.
                # E que o reset foi para 0.
                # Então produção no intervalo de reset = atual.
                total_delta += atual
                # logger.debug(f"Reset detectado em {key}: {anterior} -> {atual}")
            else:
                total_delta += (atual - anterior)
                
            anterior = atual
            
        return int(total_delta)

    def obter_sku_ativo(self, linha: LinhaProducao, data_hora: datetime):
        """
        Retorna o HistóricoSKU ativo para a linha na data/hora informada.
        """
        return HistoricoSKU.objects.filter(
            linha=linha,
            data_inicio__lte=data_hora
        ).filter(
            models.Q(data_fim__gte=data_hora) | models.Q(data_fim__isnull=True)
        ).order_by('-data_inicio').first()

    def sincronizar_dados_producao(self, equipamento: Equipamento, data_hora: datetime):
        """
        Verifica no InfluxDB se houve mudança de SKU ou OP e atualiza o MySQL.
        """
        try:
            # Busca último registro de SKU e OP no InfluxDB
            query = f"""
                SELECT last("sku_codigo") as sku, last("ordem_producao") as op, last("op") as op_alt
                FROM producao
                WHERE equipamento_codigo = '{equipamento.codigo}'
                AND time <= '{data_hora.isoformat()}'
            """
            result = self.influx_client.query(query)
            points = list(result.get_points())
            
            if not points:
                return

            dados = points[0]
            sku_codigo = dados.get('sku')
            op_codigo = dados.get('op') or dados.get('op_alt')

            if not sku_codigo:
                return

            # Busca SKU ativo no MySQL
            historico_atual = self.obter_sku_ativo(equipamento.linha, data_hora)
            
            # Se não tem histórico ou mudou SKU/OP
            novo_sku = False
            if not historico_atual:
                novo_sku = True
            elif str(historico_atual.produto.codigo) != str(sku_codigo):
                novo_sku = True
            elif op_codigo and historico_atual.ordem_producao != str(op_codigo):
                novo_sku = True
            
            if novo_sku:
                logger.info(f"Detectada mudança de produção: SKU={sku_codigo}, OP={op_codigo}")
                
                # Fecha anterior
                if historico_atual:
                    historico_atual.data_fim = data_hora
                    historico_atual.save()
                
                # Busca ou cria produto
                from .models import Produto
                produto = Produto.objects.filter(codigo=sku_codigo).first()
                
                if not produto:
                    # Se produto não existe, cria automaticamente
                    logger.warning(f"Produto {sku_codigo} não encontrado. Criando automaticamente...")
                    produto = Produto.objects.create(
                        codigo=sku_codigo,
                        descricao=f"Produto Auto {sku_codigo}",
                        peso_unitario=1.0 # Valor padrão
                    )

                # Cria novo histórico
                HistoricoSKU.objects.create(
                    linha=equipamento.linha,
                    produto=produto,
                    ordem_producao=op_codigo or f"OP-{datetime.now().strftime('%Y%m%d%H%M')}",
                    data_inicio=data_hora
                )
                
        except Exception as e:
            logger.error(f"Erro ao sincronizar dados de produção: {e}")

    def calcular_metricas_hora(self, equipamento: Equipamento, data_hora: datetime):
        """
        Calcula métricas para uma hora específica.
        """
        # Define intervalo de 1 hora
        hora_inicio = data_hora.replace(minute=0, second=0, microsecond=0)
        hora_fim = hora_inicio + timedelta(hours=1)
        
        # Busca dados do InfluxDB
        dados = self.buscar_dados_influx(equipamento.codigo, hora_inicio, hora_fim)
        
        if not dados:
            logger.debug(f"Sem dados para {equipamento.nome} em {hora_inicio}")
            return
        
        # Calcula contagens considerando resets
        contagem_entrada = self._calcular_delta_com_resets(dados, 'contagem_entrada')
        contagem_saida = self._calcular_delta_com_resets(dados, 'contagem_saida')
        # Calcula tempos usando eventos de estado
        tempos = EventoEstadoEquipamento.calcular_tempos_por_estado(
            equipamento, hora_inicio, hora_fim
        )
        
        # Calcular tonelagem
        formato_gramas = obter_formato_equipamento(equipamento)
        toneladas = calcular_toneladas(contagem_saida, formato_gramas) if formato_gramas else 0.0
        vazao_ton_h = calcular_vazao_ton_hora(toneladas, tempos['tempo_producao']) if toneladas > 0 else 0.0
        
        # Sincroniza SKU e OP do InfluxDB (se disponível)
        self.sincronizar_dados_producao(equipamento, hora_fim)

        # Obter SKU e OP ativos (usando fim do período para pegar o que estava rodando)
        historico_sku = self.obter_sku_ativo(equipamento.linha, hora_fim)
        
        produto = historico_sku.produto if historico_sku else None
        ordem_producao = historico_sku.ordem_producao if historico_sku else ''
        meta_producao = historico_sku.meta_producao if historico_sku else 0
        
        # ===== CÁLCULO DE OEE =====
        tempo_disponivel = 60.0  # 1 hora em minutos
        velocidade_real = self._calcular_velocidade_media(dados)
        velocidade_planejada = equipamento.linha.velocidade_planejada
        
        # 1. Disponibilidade = (Tempo Produção / Tempo Disponível) * 100
        disponibilidade = (tempos['tempo_producao'] / tempo_disponivel * 100) if tempo_disponivel > 0 else 0
        
        # 2. Performance = (Velocidade Real / Velocidade Planejada) * 100
        performance = (velocidade_real / velocidade_planejada * 100) if velocidade_planejada > 0 else 0
        
        # 3. Descarte e Qualidade
        descarte = max(0, contagem_entrada - contagem_saida)
        qualidade = ((contagem_saida - descarte) / contagem_saida * 100) if contagem_saida > 0 else 100
        
        # 4. OEE = (Disponibilidade * Performance * Qualidade) / 10000
        oee = (disponibilidade * performance * qualidade) / 10000
        
        # Cria ou atualiza métrica
        metrica, created = MetricaProducao.objects.update_or_create(
            linha=equipamento.linha,
            equipamento=equipamento,
            data_hora=hora_inicio,
            periodo='HORA',
            defaults={
                'produto': produto,
                'ordem_producao': ordem_producao,
                'meta_producao': meta_producao,
                'contagem_entrada': contagem_entrada,
                'contagem_saida': contagem_saida,
                'descarte': descarte,
                'percentual_descarte': (descarte / contagem_entrada * 100) if contagem_entrada > 0 else 0,
                'velocidade_planejada': velocidade_planejada,
                'velocidade_real': velocidade_real,
                'tempo_programado': 60.0,  # 1 hora em minutos
                'tempo_disponivel': tempo_disponivel,
                'tempo_producao': tempos['tempo_producao'],
                'tempo_parada': tempos['tempo_parada'],
                'tempo_setup': tempos['tempo_setup'],
                'tempo_nao_programado': tempos['tempo_nao_programado'],
                'disponibilidade': disponibilidade,
                'performance': performance,
                'qualidade': qualidade,
                'oee': oee,
                # Campos de tonelagem
                'toneladas_produzidas': toneladas,
                'vazao_real_ton_hora': vazao_ton_h,
                'formato_gramas': formato_gramas
            }
        )
        
        logger.info(f"Métrica HORA criada: {equipamento.nome} - {hora_inicio}")
    
    def calcular_metricas_turno(self, equipamento: Equipamento, turno: TurnoProducao, data: datetime):
        """
        Calcula métricas para um turno específico.
        """
        turno_inicio, turno_fim = self.obter_intervalo_turno(turno, data)
        
        # Busca dados do InfluxDB
        dados = self.buscar_dados_influx(equipamento.codigo, turno_inicio, turno_fim)
        
        if not dados:
            logger.debug(f"Sem dados para {equipamento.nome} em {turno.nome}")
            return
        
        # Calcula contagens considerando resets
        contagem_entrada = self._calcular_delta_com_resets(dados, 'contagem_entrada')
        contagem_saida = self._calcular_delta_com_resets(dados, 'contagem_saida')
        
        # Calcula tempos usando eventos de estado
        tempos = EventoEstadoEquipamento.calcular_tempos_por_estado(
            equipamento, turno_inicio, turno_fim
        )
        
        # Calcular tonelagem
        formato_gramas = obter_formato_equipamento(equipamento)
        toneladas = calcular_toneladas(contagem_saida, formato_gramas) if formato_gramas else 0.0
        vazao_ton_h = calcular_vazao_ton_hora(toneladas, tempos['tempo_producao']) if toneladas > 0 else 0.0
        
        # Obter SKU e OP ativos
        historico_sku = self.obter_sku_ativo(equipamento.linha, turno_fim)
        
        produto = historico_sku.produto if historico_sku else None
        ordem_producao = historico_sku.ordem_producao if historico_sku else ''
        meta_producao = historico_sku.meta_producao if historico_sku else 0
        
        # ===== CÁLCULO DE OEE =====
        # Tempo disponível = Duração do turno em minutos
        tempo_disponivel = turno.duracao_horas * 60.0
        
        velocidade_real = self._calcular_velocidade_media(dados)
        velocidade_planejada = equipamento.linha.velocidade_planejada
        
        # 1. Disponibilidade
        disponibilidade = (tempos['tempo_producao'] / tempo_disponivel * 100) if tempo_disponivel > 0 else 0
        
        # 2. Performance
        performance = (velocidade_real / velocidade_planejada * 100) if velocidade_planejada > 0 else 0
        
        # 3. Descarte e Qualidade
        descarte = max(0, contagem_entrada - contagem_saida)
        qualidade = ((contagem_saida - descarte) / contagem_saida * 100) if contagem_saida > 0 else 100
        
        # 4. OEE
        oee = (disponibilidade * performance * qualidade) / 10000
        
        # Cria ou atualiza métrica
        metrica, created = MetricaProducao.objects.update_or_create(
            linha=equipamento.linha,
            equipamento=equipamento,
            data_hora=turno_inicio,
            periodo='TURNO',
            turno=turno.nome,
            defaults={
                'produto': produto,
                'ordem_producao': ordem_producao,
                'meta_producao': meta_producao,
                'contagem_entrada': contagem_entrada,
                'contagem_saida': contagem_saida,
                'descarte': descarte,
                'percentual_descarte': (descarte / contagem_entrada * 100) if contagem_entrada > 0 else 0,
                'velocidade_planejada': velocidade_planejada,
                'velocidade_real': velocidade_real,
                'tempo_programado': tempo_disponivel,
                'tempo_disponivel': tempo_disponivel,
                'tempo_producao': tempos['tempo_producao'],
                'tempo_parada': tempos['tempo_parada'],
                'tempo_setup': tempos['tempo_setup'],
                'tempo_nao_programado': tempos['tempo_nao_programado'],
                'disponibilidade': disponibilidade,
                'performance': performance,
                'qualidade': qualidade,
                'oee': oee,
                # Campos de tonelagem
                'toneladas_produzidas': toneladas,
                'vazao_real_ton_hora': vazao_ton_h,
                'formato_gramas': formato_gramas
            }
        )
        
        logger.info(f"Métrica TURNO criada: {equipamento.nome} - {turno.nome} - {data.date()}")
    
    def calcular_metricas_dia(self, equipamento: Equipamento, data: datetime):
        """
        Calcula métricas para um dia inteiro.
        """
        dia_inicio = timezone.make_aware(datetime.combine(data.date(), time.min))
        dia_fim = timezone.make_aware(datetime.combine(data.date(), time.max))
        
        # Busca dados do InfluxDB
        dados = self.buscar_dados_influx(equipamento.codigo, dia_inicio, dia_fim)
        
        if not dados:
            logger.debug(f"Sem dados para {equipamento.nome} em {data.date()}")
            return
        
        # Calcula contagens considerando resets
        contagem_entrada = self._calcular_delta_com_resets(dados, 'contagem_entrada')
        contagem_saida = self._calcular_delta_com_resets(dados, 'contagem_saida')
        
        # Calcula tempos usando eventos de estado
        tempos = EventoEstadoEquipamento.calcular_tempos_por_estado(
            equipamento, dia_inicio, dia_fim
        )
        
        # Calcular tonelagem
        formato_gramas = obter_formato_equipamento(equipamento)
        toneladas = calcular_toneladas(contagem_saida, formato_gramas) if formato_gramas else 0.0
        vazao_ton_h = calcular_vazao_ton_hora(toneladas, tempos['tempo_producao']) if toneladas > 0 else 0.0
        
        # Obter SKU e OP ativos
        historico_sku = self.obter_sku_ativo(equipamento.linha, dia_fim)
        produto = historico_sku.produto if historico_sku else None
        ordem_producao = historico_sku.ordem_producao if historico_sku else ''
        meta_producao = historico_sku.meta_producao if historico_sku else 0
        
        # Cria ou atualiza métrica
        metrica, created = MetricaProducao.objects.update_or_create(
            linha=equipamento.linha,
            equipamento=equipamento,
            data_hora=dia_inicio,
            periodo='DIA',
            defaults={
                'produto': produto,
                'ordem_producao': ordem_producao,
                'meta_producao': meta_producao,
                'contagem_entrada': contagem_entrada,
                'contagem_saida': contagem_saida,
                'velocidade_planejada': equipamento.linha.velocidade_planejada,
                'velocidade_real': self._calcular_velocidade_media(dados),
                'tempo_programado': 24 * 60.0,  # 24 horas em minutos
                'tempo_producao': tempos['tempo_producao'],
                'tempo_parada': tempos['tempo_parada'],
                'tempo_setup': tempos['tempo_setup'],
                'tempo_nao_programado': tempos['tempo_nao_programado'],
                # Campos de tonelagem
                'toneladas_produzidas': toneladas,
                'vazao_real_ton_hora': vazao_ton_h,
                'formato_gramas': formato_gramas
            }
        )
        
        logger.info(f"Métrica DIA criada: {equipamento.nome} - {data.date()}")

    def calcular_metricas_linha_hora(self, linha: LinhaProducao, data_hora: datetime):
        """
        Calcula métricas consolidadas da linha para uma hora específica.
        """
        hora_inicio = data_hora.replace(minute=0, second=0, microsecond=0)
        
        # Busca métricas de todos os equipamentos da linha
        metricas_equipamentos = MetricaProducao.objects.filter(
            linha=linha,
            equipamento__isnull=False,
            periodo='HORA',
            data_hora=hora_inicio
        )
        
        if not metricas_equipamentos.exists():
            return
        
        # Agrega dados
        contagem_entrada_total = metricas_equipamentos.aggregate(Sum('contagem_entrada'))['contagem_entrada__sum'] or 0
        contagem_saida_total = metricas_equipamentos.aggregate(Sum('contagem_saida'))['contagem_saida__sum'] or 0
        tempo_producao_total = metricas_equipamentos.aggregate(Sum('tempo_producao'))['tempo_producao__sum'] or 0
        tempo_parada_total = metricas_equipamentos.aggregate(Sum('tempo_parada'))['tempo_parada__sum'] or 0
        tempo_setup_total = metricas_equipamentos.aggregate(Sum('tempo_setup'))['tempo_setup__sum'] or 0
        tempo_nao_programado_total = metricas_equipamentos.aggregate(Sum('tempo_nao_programado'))['tempo_nao_programado__sum'] or 0
        velocidade_real_media = metricas_equipamentos.aggregate(Avg('velocidade_real'))['velocidade_real__avg'] or 0
        
        # Obter SKU e OP ativos (usando hora_inicio + 1h para pegar o fim)
        hora_fim = hora_inicio + timedelta(hours=1)
        historico_sku = self.obter_sku_ativo(linha, hora_fim)
        produto = historico_sku.produto if historico_sku else None
        ordem_producao = historico_sku.ordem_producao if historico_sku else ''
        meta_producao = historico_sku.meta_producao if historico_sku else 0
        
        # Cria ou atualiza métrica da linha
        MetricaProducao.objects.update_or_create(
            linha=linha,
            equipamento__isnull=True,
            data_hora=hora_inicio,
            periodo='HORA',
            defaults={
                'produto': produto,
                'ordem_producao': ordem_producao,
                'meta_producao': meta_producao,
                'contagem_entrada': int(contagem_entrada_total),
                'contagem_saida': int(contagem_saida_total),
                'velocidade_planejada': linha.velocidade_planejada,
                'velocidade_real': velocidade_real_media,
                'tempo_programado': 60.0,
                'tempo_producao': tempo_producao_total,
                'tempo_parada': tempo_parada_total,
                'tempo_setup': tempo_setup_total,
                'tempo_nao_programado': tempo_nao_programado_total,
            }
        )

    def calcular_metricas_linha_turno(self, linha: LinhaProducao, turno: TurnoProducao, data: datetime):
        """
        Calcula métricas consolidadas da linha para um turno específico.
        """
        turno_inicio, _ = self.obter_intervalo_turno(turno, data)
        
        # Busca métricas de todos os equipamentos da linha
        metricas_equipamentos = MetricaProducao.objects.filter(
            linha=linha,
            equipamento__isnull=False,
            periodo='TURNO',
            turno=turno.nome,
            data_hora=turno_inicio
        )
        
        if not metricas_equipamentos.exists():
            return
        
        # Agrega dados
        contagem_entrada_total = metricas_equipamentos.aggregate(Sum('contagem_entrada'))['contagem_entrada__sum'] or 0
        contagem_saida_total = metricas_equipamentos.aggregate(Sum('contagem_saida'))['contagem_saida__sum'] or 0
        tempo_producao_total = metricas_equipamentos.aggregate(Sum('tempo_producao'))['tempo_producao__sum'] or 0
        tempo_parada_total = metricas_equipamentos.aggregate(Sum('tempo_parada'))['tempo_parada__sum'] or 0
        tempo_setup_total = metricas_equipamentos.aggregate(Sum('tempo_setup'))['tempo_setup__sum'] or 0
        tempo_nao_programado_total = metricas_equipamentos.aggregate(Sum('tempo_nao_programado'))['tempo_nao_programado__sum'] or 0
        velocidade_real_media = metricas_equipamentos.aggregate(Avg('velocidade_real'))['velocidade_real__avg'] or 0
        
        # Obter SKU e OP ativos
        turno_inicio, turno_fim = self.obter_intervalo_turno(turno, data)
        historico_sku = self.obter_sku_ativo(linha, turno_fim)
        produto = historico_sku.produto if historico_sku else None
        ordem_producao = historico_sku.ordem_producao if historico_sku else ''
        meta_producao = historico_sku.meta_producao if historico_sku else 0
        
        # Cria ou atualiza métrica da linha
        MetricaProducao.objects.update_or_create(
            linha=linha,
            equipamento__isnull=True,
            data_hora=turno_inicio,
            periodo='TURNO',
            turno=turno.nome,
            defaults={
                'produto': produto,
                'ordem_producao': ordem_producao,
                'meta_producao': meta_producao,
                'contagem_entrada': int(contagem_entrada_total),
                'contagem_saida': int(contagem_saida_total),
                'velocidade_planejada': linha.velocidade_planejada,
                'velocidade_real': velocidade_real_media,
                'tempo_programado': turno.duracao_horas * 60.0,
                'tempo_producao': tempo_producao_total,
                'tempo_parada': tempo_parada_total,
                'tempo_setup': tempo_setup_total,
                'tempo_nao_programado': tempo_nao_programado_total,
            }
        )

    def calcular_metricas_linha_dia(self, linha: LinhaProducao, data: datetime):
        """
        Calcula métricas consolidadas da linha para um dia inteiro.
        """
        dia_inicio = timezone.make_aware(datetime.combine(data.date(), time.min))
        
        # Busca métricas de todos os equipamentos da linha
        metricas_equipamentos = MetricaProducao.objects.filter(
            linha=linha,
            equipamento__isnull=False,
            periodo='DIA',
            data_hora=dia_inicio
        )
        
        if not metricas_equipamentos.exists():
            return
        
        # Agrega dados
        contagem_entrada_total = metricas_equipamentos.aggregate(Sum('contagem_entrada'))['contagem_entrada__sum'] or 0
        contagem_saida_total = metricas_equipamentos.aggregate(Sum('contagem_saida'))['contagem_saida__sum'] or 0
        tempo_producao_total = metricas_equipamentos.aggregate(Sum('tempo_producao'))['tempo_producao__sum'] or 0
        tempo_parada_total = metricas_equipamentos.aggregate(Sum('tempo_parada'))['tempo_parada__sum'] or 0
        tempo_setup_total = metricas_equipamentos.aggregate(Sum('tempo_setup'))['tempo_setup__sum'] or 0
        tempo_nao_programado_total = metricas_equipamentos.aggregate(Sum('tempo_nao_programado'))['tempo_nao_programado__sum'] or 0
        velocidade_real_media = metricas_equipamentos.aggregate(Avg('velocidade_real'))['velocidade_real__avg'] or 0
        
        # Obter SKU e OP ativos
        dia_fim = timezone.make_aware(datetime.combine(data.date(), time.max))
        historico_sku = self.obter_sku_ativo(linha, dia_fim)
        produto = historico_sku.produto if historico_sku else None
        ordem_producao = historico_sku.ordem_producao if historico_sku else ''
        meta_producao = historico_sku.meta_producao if historico_sku else 0
        
        # Cria ou atualiza métrica da linha
        MetricaProducao.objects.update_or_create(
            linha=linha,
            equipamento__isnull=True,
            data_hora=dia_inicio,
            periodo='DIA',
            defaults={
                'produto': produto,
                'ordem_producao': ordem_producao,
                'meta_producao': meta_producao,
                'contagem_entrada': int(contagem_entrada_total),
                'contagem_saida': int(contagem_saida_total),
                'velocidade_planejada': linha.velocidade_planejada,
                'velocidade_real': velocidade_real_media,
                'tempo_programado': 24 * 60.0,
                'tempo_producao': tempo_producao_total,
                'tempo_parada': tempo_parada_total,
                'tempo_setup': tempo_setup_total,
                'tempo_nao_programado': tempo_nao_programado_total,
            }
        )

    def agregar_ultima_hora(self):
        """Agrega dados da última hora para todos os equipamentos e linhas"""
        logger.info("Iniciando agregação de HORA...")
        
        agora = timezone.now()
        hora_passada = agora - timedelta(hours=1)
        
        # Agrega equipamentos
        for equipamento in Equipamento.objects.filter(status='ATIVO'):
            self.calcular_metricas_hora(equipamento, hora_passada)
        
        # Agrega linhas (soma dos equipamentos)
        for linha in LinhaProducao.objects.filter(ativa=True):
            self.calcular_metricas_linha_hora(linha, hora_passada)
        
        logger.info("Agregação de HORA concluída")

    def agregar_ultimo_turno(self):
        """Agrega dados do último turno para todos os equipamentos e linhas"""
        logger.info("Iniciando agregação de TURNO...")
        
        agora = timezone.now()
        
        # Agrega equipamentos
        for turno in TurnoProducao.objects.filter(ativo=True):
            for equipamento in Equipamento.objects.filter(status='ATIVO'):
                self.calcular_metricas_turno(equipamento, turno, agora)
        
        # Agrega linhas (soma dos equipamentos)
        for turno in TurnoProducao.objects.filter(ativo=True):
            for linha in LinhaProducao.objects.filter(ativa=True):
                self.calcular_metricas_linha_turno(linha, turno, agora)
        
        logger.info("Agregação de TURNO concluída")

    def agregar_dia_anterior(self):
        """Agrega dados do dia anterior para todos os equipamentos e linhas"""
        logger.info("Iniciando agregação de DIA...")
        
        dia_anterior = timezone.now() - timedelta(days=1)
        
        # Agrega equipamentos
        for equipamento in Equipamento.objects.filter(status='ATIVO'):
            self.calcular_metricas_dia(equipamento, dia_anterior)
        
        # Agrega linhas (soma dos equipamentos)
        for linha in LinhaProducao.objects.filter(ativa=True):
            self.calcular_metricas_linha_dia(linha, dia_anterior)
        
        logger.info("Agregação de DIA concluída")

    def agregar_turno_atual(self):
        """Agrega dados do turno ATUAL em tempo real (frequência alta)"""
        # logger.debug("Iniciando agregação de TURNO ATUAL...")
        
        agora = timezone.now()
        turno_atual = self.obter_turno_atual(agora)
        
        if not turno_atual:
            return

        # 1. Sincronizar SKU/OP e Agregar Equipamentos
        for equipamento in Equipamento.objects.filter(status='ATIVO'):
            # Sincroniza SKU/OP do InfluxDB para MySQL
            self.sincronizar_dados_producao(equipamento, agora)
            # Calcula métricas parciais do turno
            self.calcular_metricas_turno(equipamento, turno_atual, agora)
            
        # 2. Agregar Linhas
        for linha in LinhaProducao.objects.filter(ativa=True):
            self.calcular_metricas_linha_turno(linha, turno_atual, agora)
            
        # logger.debug("Agregação de TURNO ATUAL concluída")


# Instância global
agregador = AgregadorDados()