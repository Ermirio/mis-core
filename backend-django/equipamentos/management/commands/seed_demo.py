"""
seed_demo — popula o banco com fábrica, área, SKUs, linhas, equipamentos
e tags de coleta para o modo de simulação.

Idempotente: roda em todo startup quando MIS_MODE=demo. Não duplica.

Topologia simulada (fixa, independente do que estiver no banco):
    Fábrica DEMO → Área Envase
      Linha L01 (Soap Powder 1)
        E001  ENCHEDORA      ordem 1
        E002  BALANCA        ordem 2
        E003  ENCAIXOTADORA  ordem 3
        E004  PALETIZADOR    ordem 4
      Linha L02 (Soap Powder 2)
        E005..E008 (mesma cadeia)
      Linha L03 (Soap Powder 3)
        E009..E012

    SKUs: OMO 500 / OMO 1000 / OMO 1600 / OMO 2400  (formato em gramas)
"""

from __future__ import annotations

from datetime import time, date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone as dj_tz

from equipamentos.models import (
    Fabrica,
    Area,
    Produto,
    LinhaProducao,
    ConexaoOPC,
    Equipamento,
    TipoEquipamento,
    StatusEquipamento,
    TurnoProducao,
    CalendarioProducao,
    EventoEstadoEquipamento,
)
import random


SKUS = [
    ("OMO 500",  "OMO Sabão em Pó 500g",   Decimal("500"),   1.0),
    ("OMO 1000", "OMO Sabão em Pó 1000g",  Decimal("1000"),  1.0),
    ("OMO 1600", "OMO Sabão em Pó 1600g",  Decimal("1600"),  1.0),
    ("OMO 2400", "OMO Sabão em Pó 2400g",  Decimal("2400"),  1.0),
]


# 10 linhas × 4 equipamentos = 40 equipamentos. Velocidades variadas para que
# cada linha tenha perfil ligeiramente diferente nos dashboards.
TIPOS_EQ = [
    ("Enchedora",     TipoEquipamento.ENCHEDORA,     1),
    ("Balança",       TipoEquipamento.BALANCA,       2),
    ("Encaixotadora", TipoEquipamento.ENCAIXOTADORA, 3),
    ("Paletizador",   TipoEquipamento.PALETIZADOR,   4),
]

# Velocidade planejada de cada linha (unid/min)
VEL_POR_LINHA = [120.0, 100.0, 80.0, 110.0, 95.0, 130.0, 85.0, 105.0, 75.0, 115.0]

LINHAS_DEMO = []
_eq_counter = 1
for idx in range(10):
    n = idx + 1
    linha_codigo = f"L{n:02d}"
    linha_nome = f"Linha {n:02d} — Soap Powder {n}"
    vel = VEL_POR_LINHA[idx]
    equips = []
    for nome_base, tipo, ordem in TIPOS_EQ:
        equips.append((
            f"E{_eq_counter:03d}",
            f"{nome_base} {linha_codigo}",
            tipo,
            ordem,
            vel,
            vel * 1.15,
        ))
        _eq_counter += 1
    LINHAS_DEMO.append((linha_codigo, linha_nome, vel, equips))


class Command(BaseCommand):
    help = "Popula o banco com a topologia de DEMO (fábrica/linhas/SKUs/equipamentos). Idempotente."

    @transaction.atomic
    def handle(self, *args, **opts):
        self.stdout.write(self.style.NOTICE("==> seed_demo: criando topologia de simulação"))

        fab, _ = Fabrica.objects.get_or_create(
            codigo="F001",
            defaults={"nome": "Fábrica DEMO", "localizacao": "Ambiente de Demonstração"},
        )
        area, _ = Area.objects.get_or_create(
            codigo="A001",
            defaults={"fabrica": fab, "nome": "Envase"},
        )

        # SKUs
        for codigo, descricao, peso, fator in SKUS:
            Produto.objects.update_or_create(
                codigo=codigo,
                defaults={
                    "descricao": descricao,
                    "peso_unitario": peso,
                    "fator_conversao": fator,
                    "ativo": True,
                },
            )

        # Conexão OPC fictícia (necessária para alguns helpers, não usada em demo)
        conexao, _ = ConexaoOPC.objects.get_or_create(
            nome="DEMO-SIMULADOR",
            defaults={
                "url_servidor": "opc.tcp://demo:0",
                "ativa": False,
            },
        )

        for linha_codigo, linha_nome, vel_planejada, equipamentos in LINHAS_DEMO:
            # Meta em toneladas/turno assumindo SKU médio de 1500g (média entre 500-2400)
            meta_ton_turno = Decimal(str(round(vel_planejada * 60 * 8 * 1.5 / 1000.0, 3)))
            meta_ton_hora = Decimal(str(round(vel_planejada * 60 * 1.5 / 1000.0, 3)))
            linha, _ = LinhaProducao.objects.update_or_create(
                codigo=linha_codigo,
                defaults={
                    "nome": linha_nome,
                    "area": area,
                    "conexao_padrao": conexao,
                    "localizacao": f"Envase / {linha_nome}",
                    "ativa": True,
                    "velocidade_planejada": vel_planejada,
                    "meta_producao_hora": int(vel_planejada * 60),
                    "meta_producao_turno": int(vel_planejada * 60 * 8),
                    "meta_toneladas_hora": meta_ton_hora,
                    "meta_toneladas_turno": meta_ton_turno,
                    "meta_oee": 85.0,
                },
            )

            for codigo, nome, tipo, ordem, vel_nom, vel_max in equipamentos:
                # Equipamento.save() já chama ensure_default_tags_for_equipment()
                eq, created = Equipamento.objects.update_or_create(
                    codigo=codigo,
                    defaults={
                        "linha": linha,
                        "nome": nome,
                        "tipo": tipo,
                        "ordem_na_linha": ordem,
                        "localizacao": f"{linha_nome} / posição {ordem}",
                        "status": StatusEquipamento.ATIVO,
                        "velocidade_nominal": vel_nom,
                        "velocidade_maxima": vel_max,
                        "meta_oee": 85.0,
                    },
                )
                marker = "criado" if created else "ok"
                self.stdout.write(f"   [{marker}] {linha_codigo}/{codigo} {nome}")

        # ============================================================
        # Turnos A / B / C (cobrindo 24h)
        # ============================================================
        turnos_def = [
            ("Turno A", "A", time(6, 0),  time(14, 0), 8.0),
            ("Turno B", "B", time(14, 0), time(22, 0), 8.0),
            ("Turno C", "C", time(22, 0), time(6, 0),  8.0),
        ]
        turnos: dict[str, TurnoProducao] = {}
        for nome, cod, h_ini, h_fim, dur in turnos_def:
            t, _ = TurnoProducao.objects.update_or_create(
                codigo=cod,
                defaults={
                    "nome": nome, "hora_inicio": h_ini, "hora_fim": h_fim,
                    "duracao_horas": dur, "ativo": True,
                },
            )
            turnos[cod] = t

        # ============================================================
        # Calendário: 14 dias (7 passado + 7 futuro) × 10 linhas × 3 turnos
        # ============================================================
        hoje = dj_tz.localdate()
        criados = 0
        for delta in range(-7, 8):
            d = hoje + timedelta(days=delta)
            for linha in LinhaProducao.objects.filter(ativa=True):
                meta = max(1, int((linha.meta_toneladas_turno or 0) * 1000)
                           or linha.meta_producao_turno or 50000)
                for t in turnos.values():
                    _, created = CalendarioProducao.objects.update_or_create(
                        data=d, linha=linha, turno=t,
                        defaults={"programado": True, "meta_producao_turno": meta},
                    )
                    if created:
                        criados += 1
        self.stdout.write(f"   [calendario] {criados} entradas criadas em 14d × 10 linhas × 3 turnos")

        # ============================================================
        # Eventos de estado — histórico de 7 dias para timeline
        # ============================================================
        rng = random.Random(42)
        # Estados ponderados (mais RUN, alguns paradas)
        # (estado_code, peso, dur_min, dur_max em segundos)
        STATE_DECK = [
            ("RUN",        70, 1800, 7200),
            ("PARTINDO",    8,   60,  300),
            ("BLOCK_NEXT",  5,   30,  180),
            ("WAIT_PREV",   5,   30,  180),
            ("FAULT",       4,  120,  900),
            ("SETUP",       3,  600, 1800),
            ("FALTA_MAT",   2,  300, 1200),
            ("PARANDO",     2,   60,  180),
            ("MANUTENCAO",  1, 1800, 7200),
        ]
        # Limpa eventos antigos para evitar acúmulo entre runs
        EventoEstadoEquipamento.objects.filter(origem='SISTEMA').delete()

        agora = dj_tz.now()
        inicio = agora - timedelta(days=7)
        eventos_criados = 0
        for eq in Equipamento.objects.filter(status=StatusEquipamento.ATIVO):
            t = inicio
            while t < agora:
                estado = rng.choices(
                    [s[0] for s in STATE_DECK],
                    weights=[s[1] for s in STATE_DECK],
                )[0]
                dur_min, dur_max = next((s[2], s[3]) for s in STATE_DECK if s[0] == estado)
                dur = timedelta(seconds=rng.randint(dur_min, dur_max))
                fim = min(t + dur, agora)
                EventoEstadoEquipamento.objects.create(
                    equipamento=eq, estado=estado,
                    inicio=t, fim=fim if fim < agora else None,
                    origem='SISTEMA',
                )
                t = fim
                eventos_criados += 1
        self.stdout.write(f"   [eventos]    {eventos_criados} transições de estado criadas em 7d")

        self.stdout.write(self.style.SUCCESS("==> seed_demo concluído."))
