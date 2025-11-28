# -*- coding: utf-8 -*-
"""
Management Command: sync_ops

Sincroniza OPs em produção com InfluxDB (Safety Net)

Execução:
    python manage.py sync_ops

Agendar via cron (a cada 5 minutos):
    */5 * * * * cd /caminho/projeto && python manage.py sync_ops >> /var/log/sync_ops.log 2>&1
"""

from django.core.management.base import BaseCommand
from influxdb import InfluxDBClient
from decimal import Decimal
from decouple import config
import logging

from equipamentos.models import OrdemProducao

logger = logging.getLogger(__name__)

# Configurações InfluxDB
INFLUX_HOST = config('INFLUXDB_HOST', default='127.0.0.1')
INFLUX_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUX_DB = config('INFLUXDB_DATABASE', default='industrial_db')
INFLUX_USER = config('INFLUXDB_USER', default=None)
INFLUX_PASS = config('INFLUXDB_USER_PASSWORD', default=None)


class Command(BaseCommand):
    help = 'Sincroniza OPs em produção com InfluxDB (Safety Net)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa sem salvar alterações (apenas mostra o que seria feito)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Modo DRY-RUN ativado - nenhuma alteração será salva'))
        
        try:
            # Conectar ao InfluxDB
            client = InfluxDBClient(
                host=INFLUX_HOST,
                port=INFLUX_PORT,
                username=INFLUX_USER,
                password=INFLUX_PASS,
                database=INFLUX_DB
            )
            
            # Buscar OPs em produção
            ops = OrdemProducao.objects.filter(status='PRODUZINDO')
            total_ops = ops.count()
            
            if total_ops == 0:
                self.stdout.write(self.style.SUCCESS('Nenhuma OP em produção para sincronizar'))
                return
            
            self.stdout.write(f'Encontradas {total_ops} OPs em produção')
            
            synced_count = 0
            error_count = 0
            
            for op in ops:
                try:
                    # Buscar último valor no InfluxDB
                    query = f'''
                        SELECT last("producao_acumulada_op") as final_value
                        FROM "producao" 
                        WHERE "ordem_producao" = '{op.codigo}'
                    '''
                    
                    result = client.query(query)
                    points = list(result.get_points())
                    
                    if points and points[0].get('final_value') is not None:
                        influx_value = Decimal(str(points[0]['final_value']))
                        current_value = op.producao_realizada or Decimal(0)
                        
                        # Atualizar se diferente (com margem de 0.001 ton)
                        if abs(influx_value - current_value) > Decimal('0.001'):
                            self.stdout.write(
                                self.style.WARNING(
                                    f'[SYNC] OP {op.codigo}: {current_value:.3f} -> {influx_value:.3f} ton'
                                )
                            )
                            
                            if not dry_run:
                                op.producao_realizada = influx_value
                                op.save()
                                logger.info(f'[SYNC] OP {op.codigo} atualizada: {current_value:.3f} -> {influx_value:.3f} ton')
                            
                            synced_count += 1
                        else:
                            self.stdout.write(
                                self.style.SUCCESS(f'[OK] OP {op.codigo}: {current_value:.3f} ton (sem mudanças)')
                            )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'[SKIP] OP {op.codigo}: sem dados no InfluxDB')
                        )
                        
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(f'[ERROR] OP {op.codigo}: {e}')
                    )
                    logger.error(f'[SYNC ERROR] OP {op.codigo}: {e}')
            
            # Resumo
            self.stdout.write('\n' + '='*50)
            self.stdout.write(self.style.SUCCESS(f'Total de OPs: {total_ops}'))
            self.stdout.write(self.style.SUCCESS(f'Sincronizadas: {synced_count}'))
            if error_count > 0:
                self.stdout.write(self.style.ERROR(f'Erros: {error_count}'))
            
            if dry_run:
                self.stdout.write(self.style.WARNING('\nModo DRY-RUN - nenhuma alteração foi salva'))
            
            client.close()
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro crítico: {e}'))
            logger.critical(f'[SYNC CRITICAL] Erro ao executar sync_ops: {e}')
            raise
