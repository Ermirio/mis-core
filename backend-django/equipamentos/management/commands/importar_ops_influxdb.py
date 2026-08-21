"""
Django Management Command: Importar OPs do InfluxDB
Importa Ordens de Produção existentes no InfluxDB para o MySQL
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from equipamentos.models import (
    OrdemProducao, LinhaProducao, Produto
)
from influxdb import InfluxDBClient


class Command(BaseCommand):
    help = 'Importa Ordens de Produção do InfluxDB para o MySQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=30,
            help='Número de dias para trás a buscar OPs (padrão: 30)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula a importação sem salvar no banco',
        )

    def handle(self, *args, **options):
        """Executa a importação"""
        
        dias = options['dias']
        dry_run = options['dry_run']
        
        # Conectar ao InfluxDB
        self.stdout.write('Conectando ao InfluxDB...')
        influx_client = InfluxDBClient(
            host='127.0.0.1',
            port=8086,
            database='industrial_db',  # Database correto
            username='admin',
            password='admin123'
        )
        
        # Calcular período
        data_fim = timezone.now()
        data_inicio = data_fim - timedelta(days=dias)
        
        self.stdout.write(f'Buscando OPs entre {data_inicio.date()} e {data_fim.date()}...')
        
        # Nova estratégia: Buscar OPs distintas usando SHOW TAG VALUES
        # depois buscar detalhes de cada OP
        query_ops = """
        SHOW TAG VALUES FROM producao WITH KEY = "ordem_producao"
        """
        
        try:
            result = influx_client.query(query_ops)
            values = list(result.get_points())
            
            if not values:
                self.stdout.write(self.style.WARNING('Nenhuma OP encontrada no InfluxDB'))
                return
            
            # Extrair códigos de OP
            ops_no_influx = [v['value'] for v in values if v['value'] and v['value'] != '']
            
            self.stdout.write(f'Encontradas {len(ops_no_influx)} OPs distintas no InfluxDB')
            
            ops_criadas = 0
            ops_existentes = 0
            erros = 0
            
            for codigo_op in ops_no_influx:
                try:
                    if not codigo_op or codigo_op == '':
                        continue
                    
                    # Verificar se OP já existe no MySQL
                    if OrdemProducao.objects.filter(codigo=codigo_op).exists():
                        ops_existentes += 1
                        self.stdout.write(
                            self.style.WARNING(f'  OP {codigo_op} já existe no MySQL')
                        )
                        continue
                    
                    # Buscar detalhes desta OP no InfluxDB (última entrada)
                    query_detalhes = f"""
                    SELECT linha_codigo, sku_codigo, formato_gramas
                    FROM producao
                    WHERE ordem_producao = '{codigo_op}'
                    ORDER BY time DESC
                    LIMIT 1
                    """
                    
                    result_detalhes = influx_client.query(query_detalhes)
                    detalhes_points = list(result_detalhes.get_points())
                    
                    if not detalhes_points:
                        self.stdout.write(
                            self.style.WARNING(f'  OP {codigo_op} sem detalhes no InfluxDB')
                        )
                        erros += 1
                        continue
                    
                    detalhe = detalhes_points[0]
                    codigo_linha = detalhe.get('linha_codigo', '')
                    codigo_sku = detalhe.get('sku_codigo', '')
                    formato = float(detalhe.get('formato_gramas', 0))
                    
                    # Valores padrão para metas (não disponíveis no InfluxDB)
                    meta_op = 10000
                    meta_turno = 3000
                    
                    # Buscar linha
                    try:
                        linha = LinhaProducao.objects.get(codigo=codigo_linha)
                    except LinhaProducao.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(f'  Linha {codigo_linha} não encontrada no MySQL')
                        )
                        erros += 1
                        continue
                    
                    # Buscar ou criar produto
                    produto, produto_criado = Produto.objects.get_or_create(
                        codigo=codigo_sku,
                        defaults={
                            'descricao': f'Produto {codigo_sku}',
                            'peso_unitario': formato or 0,
                            'ativo': True
                        }
                    )
                    
                    if produto_criado:
                        self.stdout.write(
                            self.style.SUCCESS(f'  Produto {codigo_sku} criado')
                        )
                    
                    
                    # Buscar última ocorrência desta OP para determinar status e datas
                    query_ultimo = f"""
                    SELECT FIRST(contagem_saida), LAST(contagem_saida)
                    FROM producao
                    WHERE ordem_producao = '{codigo_op}'
                    """
                    
                    result_ultimo = influx_client.query(query_ultimo)
                    ultimo_points = list(result_ultimo.get_points())
                    
                    if ultimo_points and ultimo_points[0].get('time'):
                        primeiro_time = datetime.fromisoformat(
                            ultimo_points[0].get('time', data_inicio.isoformat()).replace('Z', '+00:00')
                        )
                        data_inicio_real = primeiro_time
                        
                        # Se última vez vista foi há mais de 24h, considera concluída
                        if (data_fim - primeiro_time).total_seconds() > 86400:
                            status = 'CONCLUIDA'
                            data_fim_real = primeiro_time + timedelta(hours=24)
                        else:
                            status = 'PRODUZINDO'
                            data_fim_real = None
                    else:
                        status = 'PRODUZINDO'
                        data_inicio_real = None
                        data_fim_real = None
                    
                    if not dry_run:
                        # Criar OP
                        op = OrdemProducao.objects.create(
                            codigo=codigo_op,
                            linha=linha,
                            produto=produto,
                            meta_total=int(meta_op or 0),
                            meta_turno=int(meta_turno or 0),
                            formato_gramas=formato or produto.peso_unitario,
                            status=status,
                            data_planejada_inicio=data_inicio_real or data_inicio,
                            data_inicio_real=data_inicio_real,
                            data_fim_real=data_fim_real,
                            descricao=f'OP importada do InfluxDB em {timezone.now().date()}'
                        )
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ OP {codigo_op} criada - Linha: {codigo_linha} - '
                                f'SKU: {codigo_sku} - Status: {status}'
                            )
                        )
                        ops_criadas += 1
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f'[DRY-RUN] OP {codigo_op} - Linha: {codigo_linha} - '
                                f'SKU: {codigo_sku} - Status: {status}'
                            )
                        )
                        ops_criadas += 1
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'  Erro ao processar OP: {str(e)}')
                    )
                    erros += 1
            
            # Resumo
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS(f'Importação concluída:'))
            self.stdout.write(f'  OPs criadas: {ops_criadas}')
            self.stdout.write(f'  OPs já existentes: {ops_existentes}')
            self.stdout.write(f'  Erros: {erros}')
            self.stdout.write('='*60)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Erro ao consultar InfluxDB: {str(e)}')
            )
        finally:
            influx_client.close()
