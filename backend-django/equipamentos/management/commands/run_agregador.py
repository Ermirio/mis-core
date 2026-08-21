"""
Django Management Command: Run Agregador
Executa o agregador automaticamente em background
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
import time
import logging

# Importar função de agregação do agregador.py
import sys
import os

# Adiciona o diretório backend-django ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Executa o agregador de métricas automaticamente em background'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=3600,
            help='Intervalo em segundos entre agregações (padrão: 3600 = 1 hora)'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Executa apenas uma vez e sai'
        )

    def handle(self, *args, **options):
        interval = options['interval']
        run_once = options['once']

        self.stdout.write(self.style.SUCCESS('🚀 Iniciando Agregador Automático'))
        self.stdout.write(f'⏱️  Intervalo: {interval}s ({interval/3600:.1f}h)')

        if run_once:
            self.stdout.write('🔄 Modo: Execução única')
            self._executar_agregacao()
            return

        self.stdout.write('🔄 Modo: Contínuo (Ctrl+C para parar)')
        
        try:
            while True:
                self._executar_agregacao()
                
                self.stdout.write(f'😴 Aguardando {interval}s até próxima execução...')
                time.sleep(interval)
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n🛑 Parando agregador...'))

    def _executar_agregacao(self):
        """Executa uma rodada de agregação"""
        try:
            inicio = timezone.now()
            self.stdout.write(f'\n{"="*60}')
            self.stdout.write(f'⏰ Executando agregação: {inicio.strftime("%Y-%m-%d %H:%M:%S")}')
            self.stdout.write(f'{"="*60}')
            
            # Importa e executa agregador
            from agregador import agregar_todas_metricas
            
            resultado = agregar_todas_metricas()
            
            fim = timezone.now()
            duracao = (fim - inicio).total_seconds()
            
            self.stdout.write(self.style.SUCCESS(f'✅ Agregação concluída em {duracao:.2f}s'))
            
            if resultado:
                self.stdout.write(f'📊 Métricas criadas: {resultado.get("total", 0)}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erro na agregação: {e}'))
            logger.exception('Erro durante agregação')
