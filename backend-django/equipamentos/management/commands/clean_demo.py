"""
clean_demo — remove a topologia de simulação do banco.

NUNCA é executado automaticamente. Operador roda manualmente quando quiser
limpar resquícios de uma rodada em MIS_MODE=demo:

    docker compose exec django python manage.py clean_demo --dry-run   # só lista
    docker compose exec django python manage.py clean_demo --backup    # dump SQL + apaga
    docker compose exec django python manage.py clean_demo --no-input  # apaga direto

Critério de identificação (CONSERVADOR):
    - Fábrica com codigo='F001' E nome='Fábrica DEMO' (criada pelo seed_demo)
    - Conexão OPC com nome exato 'DEMO-SIMULADOR'
    - Eventos com origem='SISTEMA' vinculados aos equipamentos da fábrica demo
    - Linhas/Equipamentos vinculados à Fábrica DEMO (sem assumir código)
    - Produtos OMO 500/1000/1600/2400 NUNCA são removidos
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from equipamentos.models import (
    Fabrica,
    Area,
    LinhaProducao,
    Equipamento,
    ConexaoOPC,
    EventoEstadoEquipamento,
    CalendarioProducao,
    OrdemProducao,
)


class Command(BaseCommand):
    help = (
        "Remove a topologia DEMO (Fábrica F001 + dependências). "
        "Manual, com confirmação e backup opcional. NUNCA roda no boot."
    )

    DEMO_FAB_CODE = "F001"
    DEMO_FAB_NOME = "Fábrica DEMO"
    DEMO_CONEXAO_NOME = "DEMO-SIMULADOR"

    AFFECTED_TABLES = [
        "equipamentos_fabrica", "equipamentos_area", "equipamentos_linhaproducao",
        "equipamentos_equipamento", "equipamentos_tagcoleta", "equipamentos_sensor",
        "equipamentos_conexaoopc", "equipamentos_ordemproducao",
        "equipamentos_calendarioproducao", "equipamentos_eventoestadoequipamento",
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Só lista o que seria removido, sem apagar nada.',
        )
        parser.add_argument(
            '--backup', action='store_true',
            help='Antes de apagar, gera dump SQL em /app/backups/ '
                 '(rollback: mysql ... < /app/backups/<arquivo>.sql).',
        )
        parser.add_argument(
            '--no-input', action='store_true',
            help='Não pede confirmação interativa (assume sim).',
        )

    # ------------------------------------------------------------------
    def _contar_artefatos(self):
        fab = Fabrica.objects.filter(
            codigo=self.DEMO_FAB_CODE, nome=self.DEMO_FAB_NOME
        ).first()
        if not fab:
            return None
        linhas = LinhaProducao.objects.filter(area__fabrica=fab)
        linha_ids = list(linhas.values_list('id', flat=True))
        eqs = Equipamento.objects.filter(linha_id__in=linha_ids)
        eq_ids = list(eqs.values_list('id', flat=True))
        return {
            'fabrica': fab,
            'areas': fab.areas.count(),
            'linhas': linhas.count(),
            'equipamentos': eqs.count(),
            'OPs': OrdemProducao.objects.filter(linha_id__in=linha_ids).count(),
            'calendario': CalendarioProducao.objects.filter(linha_id__in=linha_ids).count(),
            'eventos_sistema': EventoEstadoEquipamento.objects.filter(
                equipamento_id__in=eq_ids, origem='SISTEMA'
            ).count(),
            'conexao_demo': ConexaoOPC.objects.filter(nome=self.DEMO_CONEXAO_NOME).count(),
            '_linha_ids': linha_ids,
            '_eq_ids': eq_ids,
        }

    def _dump_sql(self):
        """Gera mysqldump das tabelas afetadas. Volume `django_static` é o único
        persistente do container; usamos /app/backups/ em vez."""
        backup_dir = "/app/backups"
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{backup_dir}/pre_clean_demo_{ts}.sql"

        db = settings.DATABASES['default']
        if db.get('ENGINE') != 'django.db.backends.mysql':
            self.stdout.write(self.style.WARNING(
                "   [backup] DB não é MySQL; backup mysqldump não suportado nesta configuração."
            ))
            return None

        cmd = [
            "mysqldump",
            f"-h{db['HOST']}", f"-P{db.get('PORT', '3306')}",
            f"-u{db['USER']}", f"-p{db['PASSWORD']}",
            "--single-transaction", "--skip-lock-tables", "--no-tablespaces",
            db['NAME'], *self.AFFECTED_TABLES,
        ]
        try:
            with open(fname, 'w', encoding='utf-8') as f:
                r = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, check=False)
            if r.returncode != 0:
                self.stdout.write(self.style.ERROR(
                    f"   [backup] mysqldump falhou (rc={r.returncode}): {r.stderr.decode(errors='ignore')}"
                ))
                return None
            size_kb = os.path.getsize(fname) // 1024
            self.stdout.write(self.style.SUCCESS(
                f"   [backup] {fname} ({size_kb} KB) — rollback: "
                f"`mysql -u{db['USER']} -p {db['NAME']} < {fname}`"
            ))
            return fname
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING(
                "   [backup] mysqldump não encontrado no container; pulando backup."
            ))
            return None

    # ------------------------------------------------------------------
    def handle(self, *args, **opts):
        contagem = self._contar_artefatos()
        if not contagem:
            self.stdout.write("==> clean_demo: nenhum artefato de demo encontrado.")
            return

        self.stdout.write(self.style.NOTICE("==> clean_demo: artefatos detectados:"))
        for k in ('areas', 'linhas', 'equipamentos', 'OPs', 'calendario',
                  'eventos_sistema', 'conexao_demo'):
            self.stdout.write(f"     {k}: {contagem[k]}")

        if opts['dry_run']:
            self.stdout.write(self.style.SUCCESS("==> dry-run: nada apagado."))
            return

        if not opts['no_input']:
            try:
                resp = input("   Confirma remoção destes artefatos? [s/N] ")
            except EOFError:
                resp = ''
            if resp.strip().lower() not in ('s', 'sim', 'y', 'yes'):
                self.stdout.write("==> Cancelado pelo operador.")
                return

        if opts['backup']:
            self._dump_sql()

        with transaction.atomic():
            fab = contagem['fabrica']
            linha_ids = contagem['_linha_ids']
            eq_ids = contagem['_eq_ids']

            EventoEstadoEquipamento.objects.filter(
                equipamento_id__in=eq_ids, origem='SISTEMA'
            ).delete()
            CalendarioProducao.objects.filter(linha_id__in=linha_ids).delete()
            OrdemProducao.objects.filter(linha_id__in=linha_ids).delete()
            Equipamento.objects.filter(id__in=eq_ids).delete()
            LinhaProducao.objects.filter(id__in=linha_ids).delete()
            ConexaoOPC.objects.filter(nome=self.DEMO_CONEXAO_NOME).delete()
            fab.delete()  # cascade leva áreas

        self.stdout.write(self.style.SUCCESS("==> clean_demo concluído."))
