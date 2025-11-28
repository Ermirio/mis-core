"""
Management command para consolidar dados do InfluxDB no MySQL.
Agrega dados de produção em métricas horárias e de turno.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from influxdb import InfluxDBClient
from decouple import config
from equipamentos.models import MetricaProducao, LinhaProducao, Equipamento
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Consolida dados do InfluxDB (production) para MySQL (MetricaProducao)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--periodo',
            type=str,
            default='HORA',
            choices=['HORA', 'TURNO', 'DIA'],
            help='Período de consolidação'
        )
        parser.add_argument(
            '--horas',
            type=int,
            default=1,
            help='Quantas horas atrás consolidar'
        )

    def handle(self, *args, **options):
        periodo = options['periodo']
        horas_atras = options['horas']

        self.stdout.write(f"Iniciando consolidação {periodo} - últimas {horas_atras}h")

        # Conectar ao InfluxDB
        try:
            client = InfluxDBClient(
                host=config('INFLUXDB_HOST', default='localhost'),
                port=config('INFLUXDB_PORT', default=8086, cast=int),
                username=config('INFLUXDB_USER', default='admin'),
                password=config('INFLUXDB_USER_PASSWORD', default=''),
                database=config('INFLUXDB_DATABASE', default='industrial_db')
            )
            self.stdout.write(self.style.SUCCESS("✓ Conectado ao InfluxDB"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Erro ao conectar InfluxDB: {e}"))
            return

        # Consolidar por período
        if periodo == 'HORA':
            self.consolidar_horario(client, horas_atras)
        elif periodo == 'TURNO':
            self.consolidar_turno(client)
        elif periodo == 'DIA':
            self.consolidar_diario(client)

        self.stdout.write(self.style.SUCCESS("✓ Consolidação concluída"))

    def consolidar_horario(self, client, horas_atras=1):
        """Consolida dados da última hora"""
        
        # Calcular janela de tempo
        agora = datetime.now()
        inicio = agora - timedelta(hours=horas_atras)
        
        self.stdout.write(f"Consolidando de {inicio} até {agora}")

        # Query para agregar dados por equipamento e hora
        query = f"""
            SELECT 
                SUM(contagem_saida) as total_saida,
                SUM(contagem_entrada) as total_entrada,
                SUM(descarte) as total_descarte,
                MEAN(velocidade_atual) as vel_media,
                LAST(formato_gramas) as formato,
                LAST(planejado_op) as planejado
            FROM production
            WHERE time >= '{inicio.isoformat()}Z'
            AND time < '{agora.isoformat()}Z'
            GROUP BY time(1h), equipment, line, order_id, sku
        """

        try:
            result = client.query(query)
            
            registros_criados = 0
            
            for series in result:
                # Extrair tags
                tags = series[0][1]  # (measurement, tags)
                equipment_code = tags.get('equipment')
                line_code = tags.get('line')
                order_id = tags.get('order_id', '')
                sku = tags.get('sku', '')
                
                # Buscar objetos Django
                try:
                    linha = LinhaProducao.objects.get(codigo=line_code)
                    equipamento = Equipamento.objects.filter(codigo=equipment_code).first()
                except LinhaProducao.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"Linha {line_code} não encontrada"))
                    continue
                
                # Processar pontos de dados
                for point in series[1]:
                    data_hora = datetime.fromisoformat(point['time'].replace('Z', '+00:00'))
                    
                    # Calcular métricas
                    total_saida = int(point.get('total_saida') or 0)
                    total_entrada = int(point.get('total_entrada') or 0)
                    total_descarte = int(point.get('total_descarte') or 0)
                    vel_media = float(point.get('vel_media') or 0)
                    formato = float(point.get('formato') or 0)
                    planejado = float(point.get('planejado') or 0)
                    
                    # Calcular toneladas
                    toneladas = (total_saida * formato) / 1000000.0 if formato > 0 else 0
                    
                    # Calcular qualidade
                    qualidade = 100.0
                    if total_entrada > 0:
                        qualidade = ((total_entrada - total_descarte) / total_entrada) * 100
                    
                    # Criar ou atualizar métrica
                    metrica, created = MetricaProducao.objects.update_or_create(
                        linha=linha,
                        equipamento=equipamento,
                        data_hora=data_hora,
                        periodo='HORA',
                        defaults={
                            'ordem_producao': order_id,
                            'contagem_entrada': total_entrada,
                            'contagem_saida': total_saida,
                            'descarte': total_descarte,
                            'velocidade_real': vel_media,
                            'velocidade_planejada': planejado,
                            'toneladas_produzidas': toneladas,
                            'formato_gramas': formato,
                            'qualidade': qualidade,
                            'tempo_producao': 60,  # 1 hora em minutos
                        }
                    )
                    
                    if created:
                        registros_criados += 1
                        self.stdout.write(f"  ✓ {equipment_code} - {data_hora}: {toneladas:.2f} ton")
            
            self.stdout.write(self.style.SUCCESS(f"✓ {registros_criados} registros criados"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Erro na consolidação: {e}"))
            import traceback
            traceback.print_exc()

    def consolidar_turno(self, client):
        """Consolida dados do turno atual"""
        
        # Detectar turno atual
        hora_atual = datetime.now().hour
        if 6 <= hora_atual < 14:
            turno = 'A'
            inicio_turno = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
        elif 14 <= hora_atual < 22:
            turno = 'B'
            inicio_turno = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0)
        else:
            turno = 'C'
            if hora_atual >= 22:
                inicio_turno = datetime.now().replace(hour=22, minute=0, second=0, microsecond=0)
            else:
                inicio_turno = (datetime.now() - timedelta(days=1)).replace(hour=22, minute=0, second=0, microsecond=0)
        
        agora = datetime.now()
        
        self.stdout.write(f"Consolidando turno {turno} de {inicio_turno} até {agora}")

        # Query similar à horária, mas agrupando por turno
        query = f"""
            SELECT 
                SUM(contagem_saida) as total_saida,
                SUM(contagem_entrada) as total_entrada,
                SUM(descarte) as total_descarte,
                MEAN(velocidade_atual) as vel_media,
                LAST(formato_gramas) as formato,
                LAST(planejado_op) as planejado
            FROM production
            WHERE time >= '{inicio_turno.isoformat()}Z'
            AND time < '{agora.isoformat()}Z'
            AND shift = '{turno}'
            GROUP BY equipment, line, order_id, sku
        """

        try:
            result = client.query(query)
            
            registros_criados = 0
            
            for series in result:
                tags = series[0][1]
                equipment_code = tags.get('equipment')
                line_code = tags.get('line')
                order_id = tags.get('order_id', '')
                
                try:
                    linha = LinhaProducao.objects.get(codigo=line_code)
                    equipamento = Equipamento.objects.filter(codigo=equipment_code).first()
                except LinhaProducao.DoesNotExist:
                    continue
                
                for point in series[1]:
                    total_saida = int(point.get('total_saida') or 0)
                    total_entrada = int(point.get('total_entrada') or 0)
                    total_descarte = int(point.get('total_descarte') or 0)
                    vel_media = float(point.get('vel_media') or 0)
                    formato = float(point.get('formato') or 0)
                    
                    toneladas = (total_saida * formato) / 1000000.0 if formato > 0 else 0
                    qualidade = ((total_entrada - total_descarte) / total_entrada) * 100 if total_entrada > 0 else 100
                    
                    metrica, created = MetricaProducao.objects.update_or_create(
                        linha=linha,
                        equipamento=equipamento,
                        data_hora=inicio_turno,
                        periodo='TURNO',
                        turno=turno,
                        defaults={
                            'ordem_producao': order_id,
                            'contagem_entrada': total_entrada,
                            'contagem_saida': total_saida,
                            'descarte': total_descarte,
                            'velocidade_real': vel_media,
                            'toneladas_produzidas': toneladas,
                            'formato_gramas': formato,
                            'qualidade': qualidade,
                            'tempo_producao': 480,  # 8 horas em minutos
                        }
                    )
                    
                    if created:
                        registros_criados += 1
                        self.stdout.write(f"  ✓ {equipment_code} - Turno {turno}: {toneladas:.2f} ton")
            
            self.stdout.write(self.style.SUCCESS(f"✓ {registros_criados} registros de turno criados"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Erro na consolidação de turno: {e}"))

    def consolidar_diario(self, client):
        """Consolida dados do dia atual"""
        self.stdout.write("Consolidação diária não implementada ainda")
