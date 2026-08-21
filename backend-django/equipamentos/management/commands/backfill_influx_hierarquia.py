"""
Backfill do InfluxDB para a Solução de Identidade Hierárquica.

Pontos escritos antes da Onda final da identidade têm apenas as tags
`equipment` e (talvez) `line`. As tags `factory` e `area` faltam.

Este comando percorre `production`, identifica pontos cuja tag
`factory` ou `area` está vazia, e os REESCREVE com as 4 tags
hierárquicas derivadas do cadastro Django (equipamento → linha →
área → fábrica).

Pontos órfãos (com `line` ou `equipment` que não casa com nenhum
cadastro Django) são movidos para a measurement `production_quarantine`
— não contaminam queries normais.

Uso:
    docker exec mis-core-django python manage.py backfill_influx_hierarquia
    docker exec mis-core-django python manage.py backfill_influx_hierarquia --since=7d
    docker exec mis-core-django python manage.py backfill_influx_hierarquia --dry-run
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone as _tz

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from equipamentos.influx_helpers import get_influx_client
from equipamentos.models import Equipamento

logger = logging.getLogger(__name__)


# Tamanho do lote para reescrita — evita estourar memória do Influx
BATCH_SIZE = 5000


class Command(BaseCommand):
    help = (
        "Backfill das tags hierárquicas no InfluxDB (factory, area). "
        "Pontos órfãos são movidos para `production_quarantine`."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--since',
            default='30d',
            help='Janela de tempo a processar (ex.: 30d, 7d, 24h). Default: 30d.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Só relata o que faria, sem reescrever pontos.',
        )
        parser.add_argument(
            '--batch',
            type=int,
            default=BATCH_SIZE,
            help=f'Tamanho do lote de pontos a reescrever (default {BATCH_SIZE}).',
        )

    def handle(self, *args, **options):
        since = options['since']
        dry_run = options['dry_run']
        batch_size = options['batch']

        client = get_influx_client()
        self.stdout.write(self.style.NOTICE(
            f"Backfill iniciado · janela={since} · dry_run={dry_run}"
        ))

        # 1. Constrói mapa equipment→(equipamento, linha, área, fábrica)
        eq_index = self._build_equipment_index()
        self.stdout.write(f"  {len(eq_index)} equipamentos indexados.")

        # 2. Conta pontos elegíveis
        elegible = self._count_eligible(client, since)
        self.stdout.write(f"  {elegible} pontos elegíveis em production.")

        if elegible == 0:
            self.stdout.write(self.style.SUCCESS("Nada a fazer."))
            return

        # 3. Processa em lotes
        total_processed = 0
        total_rewritten = 0
        total_quarantined = 0
        orphans_by_key = defaultdict(int)

        offset = 0
        while True:
            points = self._fetch_batch(client, since, offset, batch_size)
            if not points:
                break

            to_rewrite = []
            to_quarantine = []
            for p in points:
                resolved = self._resolve(eq_index, p)
                if resolved is None:
                    to_quarantine.append(p)
                    orphans_by_key[(p.get('line', '?'), p.get('equipment', '?'))] += 1
                else:
                    to_rewrite.append((p, resolved))

            if not dry_run:
                if to_rewrite:
                    self._rewrite(client, to_rewrite)
                if to_quarantine:
                    self._quarantine(client, to_quarantine)

            total_processed += len(points)
            total_rewritten += len(to_rewrite)
            total_quarantined += len(to_quarantine)
            offset += len(points)
            self.stdout.write(
                f"    lote: +{len(to_rewrite)} reescritos / "
                f"+{len(to_quarantine)} quarentena (total {total_processed})"
            )
            if len(points) < batch_size:
                break

        self.stdout.write(self.style.SUCCESS(
            f"Backfill concluído: {total_processed} processados, "
            f"{total_rewritten} reescritos, {total_quarantined} em quarentena."
        ))
        if orphans_by_key:
            self.stdout.write(self.style.WARNING("Pontos órfãos por (line, equipment):"))
            for (line, eq), n in sorted(orphans_by_key.items(), key=lambda x: -x[1])[:20]:
                self.stdout.write(f"  - {line}/{eq}: {n} pontos")

    # ----------------------------------------------------------------------
    def _build_equipment_index(self) -> dict:
        """Index (line_code, equipment_code) → dict com tags hierárquicas."""
        index = {}
        qs = (
            Equipamento.objects
            .select_related('linha', 'linha__area', 'linha__area__fabrica')
        )
        for eq in qs:
            linha = eq.linha
            area = linha.area if linha else None
            fabrica = area.fabrica if area else None
            key = (linha.codigo if linha else '', eq.codigo)
            index[key] = {
                'factory': fabrica.codigo if fabrica else '',
                'area': area.codigo if area else '',
                'line': linha.codigo if linha else '',
                'equipment': eq.codigo,
            }
        return index

    def _count_eligible(self, client, since: str) -> int:
        """Conta pontos em production no intervalo (independente das tags faltantes)."""
        sql = (
            f"SELECT COUNT(\"velocidade_atual\") FROM \"production\" "
            f"WHERE time > now() - {since}"
        )
        try:
            pts = list(client.query(sql).get_points())
            return int(pts[0].get('count') or 0) if pts else 0
        except Exception as e:
            logger.warning("Falha no count: %s", e)
            return 0

    def _fetch_batch(self, client, since: str, offset: int, limit: int) -> list:
        """Busca um lote de pontos com TODAS as colunas (incluindo tags)."""
        sql = (
            f"SELECT * FROM \"production\" "
            f"WHERE time > now() - {since} "
            f"ORDER BY time ASC LIMIT {limit} OFFSET {offset}"
        )
        try:
            rs = client.query(sql)
            return list(rs.get_points())
        except Exception as e:
            logger.warning("Falha no fetch batch (offset=%d): %s", offset, e)
            return []

    def _resolve(self, eq_index: dict, point: dict) -> dict | None:
        """Retorna as 4 tags hierárquicas se o ponto puder ser identificado.

        - Match exato em (line, equipment) → ✓
        - line vazia e equipment único em um cadastro → ✓ (raro)
        - sem match → None (vai para quarentena)
        """
        line = point.get('line') or ''
        equipment = point.get('equipment') or ''
        if not equipment:
            return None

        # Match exato
        if (line, equipment) in eq_index:
            return eq_index[(line, equipment)]

        # equipment sem line, mas único globalmente
        candidates = [v for k, v in eq_index.items() if k[1] == equipment]
        if len(candidates) == 1:
            return candidates[0]

        return None

    def _rewrite(self, client, batch: list[tuple[dict, dict]]) -> None:
        """Reescreve pontos com as 4 tags hierárquicas + fields preservados."""
        new_points = []
        for original, tags in batch:
            # Filtra campos que NÃO são tags (são fields)
            tag_keys = {'line', 'equipment', 'equipment_slug', 'shift',
                        'order_id', 'sku', 'factory', 'area'}
            fields = {k: v for k, v in original.items()
                      if k not in tag_keys and k != 'time' and v is not None}
            # Mescla tags hierárquicas + dimensões contextuais existentes
            new_tags = dict(tags)
            for ext_tag in ('shift', 'order_id', 'sku'):
                if original.get(ext_tag):
                    new_tags[ext_tag] = original[ext_tag]
            new_points.append({
                'measurement': 'production',
                'tags': new_tags,
                'time': original.get('time'),
                'fields': fields,
            })
        try:
            client.write_points(new_points)
        except Exception as e:
            logger.error("Falha ao reescrever lote: %s", e)
            raise

    def _quarantine(self, client, batch: list[dict]) -> None:
        """Move pontos órfãos para `production_quarantine` para análise."""
        new_points = []
        for original in batch:
            tag_keys = {'line', 'equipment', 'equipment_slug', 'shift',
                        'order_id', 'sku', 'factory', 'area'}
            fields = {k: v for k, v in original.items()
                      if k not in tag_keys and k != 'time' and v is not None}
            tags = {k: v for k, v in original.items()
                    if k in tag_keys and v is not None}
            new_points.append({
                'measurement': 'production_quarantine',
                'tags': tags,
                'time': original.get('time'),
                'fields': fields or {'placeholder': True},
            })
        try:
            client.write_points(new_points)
        except Exception as e:
            logger.error("Falha ao quarentenar lote: %s", e)
            raise
