"""
Django Management Command: Consolidar Turno
Consolida dados de produção do InfluxDB para MySQL ao fim de cada turno
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta, time as datetime_time
from equipamentos.models import (
    OrdemProducao, RegistroProducaoTurno, TurnoProducao,
    LinhaProducao, EventoEstadoEquipamento
)
from influxdb import InfluxDBClient


class Command(BaseCommand):
    help = 'Consolida dados de produção do InfluxDB para RegistroProducaoTurno no MySQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--data',
            type=str,
            help='Data específica a consolidar (formato: YYYY-MM-DD)',
        )
        parser.add_argument(
            '--turno',
            type=str,
            help='Código do turno específico (A, B, C)',
        )
        parser.add_argument(
            '--linha',
            type=str,
            help='Código da linha específica',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula a consolidação sem salvar no banco',
        )

    def handle(self, *args, **options):
        """Executa a consolidação"""
        
        # Conectar ao InfluxDB
        influx_client = InfluxDBClient(
            host='localhost',
            port=8086,
            database='monitoramento'
        )
        
        # Determinar data e turno
        if options['data']:
            data = datetime.strptime(options['data'], '%Y-%m-%d').date()
        else:
            # Se não especificado, consolida o turno anterior
            data = timezone.now().date()
        
        # Determinar turnos a processar
        if options['turno']:
            turnos = TurnoProducao.objects.filter(codigo=options['turno'], ativo=True)
        else:
            turnos = TurnoProducao.objects.filter(ativo=True)
        
        # Determinar linhas a processar
        if options['linha']:
            linhas = LinhaProducao.objects.filter(codigo=options['linha'], ativa=True)
        else:
            linhas = LinhaProducao.objects.filter(ativa=True)
        
        consolidados = 0
        erros = 0
        
        for linha in linhas:
            for turno in turnos:
                try:
                    # Buscar OP ativa para esta linha neste período
                    ops = OrdemProducao.objects.filter(
                        linha=linha,
                        status='PRODUZINDO',
                        data_inicio_real__lte=timezone.now()
                    )
                    
                    if not ops.exists():
                        self.stdout.write(
                            self.style.WARNING(
                                f'Nenhuma OP ativa encontrada para {linha.codigo} - {turno.codigo}'
                            )
                        )
                        continue
                    
                    op = ops.first()
                    
                    # Calcular intervalo do turno
                    inicio_turno = datetime.combine(data, turno.hora_inicio)
                    
                    # Se turno cruza meia-noite
                    if turno.hora_fim < turno.hora_inicio:
                        fim_turno = datetime.combine(data + timedelta(days=1), turno.hora_fim)
                    else:
                        fim_turno = datetime.combine(data, turno.hora_fim)
                    
                    # Buscar dados do InfluxDB
                    dados_influx = self._buscar_dados_influxdb(
                        influx_client,
                        linha,
                        inicio_turno,
                        fim_turno
                    )
                    
                    # Buscar tempos de estado dos equipamentos
                    tempos_estado = self._calcular_tempos_estado(
                        linha,
                        inicio_turno,
                        fim_turno
                    )
                    
                    # Combinar dados
                    dados_consolidados = {
                        **dados_influx,
                        **tempos_estado,
                        'tempo_programado_min': turno.duracao_horas * 60,
                    }
                    
                    if not options['dry_run']:
                        # Criar ou atualizar registro
                        registro, criado = RegistroProducaoTurno.objects.update_or_create(
                            ordem_producao=op,
                            data=data,
                            turno=turno,
                            defaults={
                                'linha': linha,
                                'produto': op.produto,
                                **dados_consolidados
                            }
                        )
                        
                        acao = 'Criado' if criado else 'Atualizado'
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'{acao}: {op.codigo} - {data} - Turno {turno.codigo} - '
                                f'Prod: {dados_consolidados.get("producao_unidades", 0)} un - '
                                f'OEE: {registro.oee:.1f}%'
                            )
                        )
                        consolidados += 1
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f'[DRY-RUN] {op.codigo} - {data} - Turno {turno.codigo} - '
                                f'Prod: {dados_consolidados.get("producao_unidades", 0)} un'
                            )
                        )
                        consolidados += 1
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Erro ao consolidar {linha.codigo} - {turno.codigo}: {str(e)}'
                        )
                    )
                    erros += 1
        
        # Resumo
        self.stdout.write(
            self.style.SUCCESS(f'\nConsolidação concluída: {consolidados} registros, {erros} erros')
        )
        
        influx_client.close()
    
    def _buscar_dados_influxdb(self, client, linha, inicio, fim):
        """Busca dados agregados do InfluxDB para o período"""
        
        # Query para somar produção do período
        query_producao = f"""
        SELECT 
            SUM(contagem_saida) as producao_unidades,
            SUM(toneladas_produzidas) as producao_toneladas,
            SUM(descarte) as refugo_unidades
        FROM metricas_linha
        WHERE 
            linha = '{linha.codigo}'
            AND time >= '{inicio.isoformat()}Z'
            AND time < '{fim.isoformat()}Z'
        """
        
        try:
            result = client.query(query_producao)
            points = list(result.get_points())
            
            if points:
                dados = points[0]
                return {
                    'producao_unidades': int(dados.get('producao_unidades') or 0),
                    'producao_toneladas': float(dados.get('producao_toneladas') or 0),
                    'refugo_unidades': int(dados.get('refugo_unidades') or 0),
                    'refugo_kg': float(dados.get('refugo_unidades') or 0) * 0.001,  # Placeholder
                }
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Erro ao buscar dados InfluxDB: {str(e)}')
            )
        
        return {
            'producao_unidades': 0,
            'producao_toneladas': 0,
            'refugo_unidades': 0,
            'refugo_kg': 0,
        }
    
    def _calcular_tempos_estado(self, linha, inicio, fim):
        """Calcula tempos agregados por estado dos equipamentos da linha"""
        
        # Agregar tempos de todos os equipamentos da linha
        tempos_totais = {
            'tempo_producao_min': 0,
            'tempo_parado_min': 0,
            'tempo_setup_min': 0,
            'tempo_disponivel_min': 0,
        }
        
        for equipamento in linha.equipamentos.all():
            tempos = EventoEstadoEquipamento.calcular_tempos_por_estado(
                equipamento,
                inicio,
                fim
            )
            
            # Somar tempos (usa o menor tempo entre equipamentos - bottleneck)
            # Para simplificar, vamos usar a média por enquanto
            if tempos_totais['tempo_producao_min'] == 0:
                tempos_totais = tempos
            else:
                # Média dos tempos
                for key in tempos_totais:
                    tempos_totais[key] = (tempos_totais[key] + tempos[key]) / 2
        
        # Calcular tempo disponível
        duracao_turno_min = (fim - inicio).total_seconds() / 60
        tempo_nao_programado = duracao_turno_min - sum([
            tempos_totais['tempo_producao_min'],
            tempos_totais['tempo_parado_min'],
            tempos_totais['tempo_setup_min'],
        ])
        
        tempos_totais['tempo_disponivel_min'] = max(0, duracao_turno_min - tempo_nao_programado)
        
        return tempos_totais
