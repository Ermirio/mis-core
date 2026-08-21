"""
simulador.py — Gerador de dados realistas para o MIS Core em MODO DEMO.

Substitui a leitura OPC UA por um stream sintético cobrindo TODAS as rotas
do analytics: linha, equipamentos, estados, OEE, árvore de perdas e CUC.

Design:
-------
- Topologia FIXA, espelhando o seed Django (`manage.py seed_demo`):
  3 linhas × 4 equipamentos cada, SKUs OMO 500/1000/1600/2400.
- Cada equipamento tem uma máquina de estados independente que evolui ao longo
  do tempo:
      Rodando → micro-paradas eventuais (BLOCK_NEXT/WAIT_PREV/FAULT)
      Partindo (com descarte alto) → Rodando
      Parando (planejado, descarte zero) → Aguardando início de turno
      Setup (troca de SKU) a cada N horas
- Velocidade, contagens e descarte correlacionam com o estado:
      RUN          → velocidade ≈ nominal × ruído gaussiano, descarte baixo
      PARTINDO     → velocidade rampa, descarte alto (transientes)
      FAULT/SETUP  → velocidade 0, contagem parada
- OPs (ordens de produção) são geradas sequencialmente, com troca de SKU.
- Output: dicts no MESMO formato que `coletor.coletar_dados_equipamento` produz,
  prontos para POST em Flask `/api/dados/inserir` e Django metadata sync.

Como usar:
----------
    from simulador import SimuladorEquipamentos

    sim = SimuladorEquipamentos()
    while True:
        pacote = sim.passo()   # avança 1 ciclo (INTERVALO_COLETA segundos)
        # POST pacote para Flask
        await asyncio.sleep(INTERVALO_COLETA)

    # Pré-popular 7 dias:
    sim.backfill_influxdb(client, dias=7)
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("Simulador")


# ---------------------------------------------------------------------------
# Mapeamento dos estados (alinhado com coletor.MAPEAMENTO_ESTADOS)
# ---------------------------------------------------------------------------
ESTADO_RUN = 1
ESTADO_WAIT_PREV = 2
ESTADO_BLOCK_NEXT = 3
ESTADO_FAULT = 4
ESTADO_SETUP = 5
ESTADO_TESTE_PROJ = 6
ESTADO_AGUARD_MNT = 7
ESTADO_MANUTENCAO = 8
ESTADO_FALTA_MAT = 9
ESTADO_PARTINDO = 11
ESTADO_PARANDO = 12

ESTADO_TXT = {
    1: "RUN", 2: "WAIT_PREV", 3: "BLOCK_NEXT", 4: "FAULT",
    5: "SETUP", 6: "TESTE_PROJ", 7: "AGUARD_MNT", 8: "MANUTENCAO",
    9: "FALTA_MAT", 11: "PARTINDO", 12: "PARANDO",
}


# ---------------------------------------------------------------------------
# Topologia (precisa bater com seed_demo.py do Django)
# ---------------------------------------------------------------------------
SKUS_DEMO = [
    # (codigo, descricao, formato_g, cuc)
    ("OMO 500",  "OMO Sabão em Pó 500g",  500.0,  0.85),
    ("OMO 1000", "OMO Sabão em Pó 1000g", 1000.0, 1.55),
    ("OMO 1600", "OMO Sabão em Pó 1600g", 1600.0, 2.40),
    ("OMO 2400", "OMO Sabão em Pó 2400g", 2400.0, 3.45),
]

# Construção paramétrica: 10 linhas (L01..L10), cada linha com 4 equipamentos.
# IMPORTANTE: precisa bater 1:1 com seed_demo.py (mesma quantidade, mesmos códigos).
_TIPOS = ["ENCHEDORA", "BALANCA", "ENCAIXOTADORA", "PALETIZADOR"]
_VEL_POR_LINHA = [120.0, 100.0, 80.0, 110.0, 95.0, 130.0, 85.0, 105.0, 75.0, 115.0]

LINHAS_DEMO: List[Tuple[str, str, float, List[Tuple[str, str, int, float]]]] = []
_eq_counter = 1
for _idx in range(10):
    _n = _idx + 1
    _linha = f"L{_n:02d}"
    _vel = _VEL_POR_LINHA[_idx]
    _equips = []
    for _ordem, _tipo in enumerate(_TIPOS, start=1):
        _equips.append((f"E{_eq_counter:03d}", _tipo, _ordem, _vel))
        _eq_counter += 1
    LINHAS_DEMO.append((_linha, f"Linha {_n:02d}", _vel, _equips))


# ---------------------------------------------------------------------------
# Parâmetros de comportamento (perfil realista)
# ---------------------------------------------------------------------------
# Probabilidade por ciclo (a cada INTERVALO_COLETA s) — calibrado para dar
# OEE ~75-85% no agregado e árvore de perdas variada.
P_MICRO_FAULT     = 0.0008   # falha curta espontânea
P_BLOCK_NEXT      = 0.0015   # bloqueio do equipamento seguinte
P_WAIT_PREV       = 0.0015   # aguardando equipamento anterior
P_FALTA_MAT       = 0.0003   # falta de material
P_AGUARD_MNT      = 0.0001   # aguardando manutenção

# Duração média (em segundos) de cada estado de parada
DUR_PARTINDO      = (60, 300)     # 1-5 min
DUR_FAULT         = (120, 900)    # 2-15 min
DUR_BLOCK_NEXT    = (30, 180)
DUR_WAIT_PREV     = (30, 180)
DUR_SETUP         = (600, 1800)   # 10-30 min troca de SKU
DUR_FALTA_MAT     = (300, 1200)
DUR_MANUTENCAO    = (1800, 7200)
DUR_PARANDO       = (60, 180)
DUR_OP            = (3600 * 3, 3600 * 8)  # OP dura 3-8h

# Descarte por estado (% da produção bruta)
DESCARTE_PCT = {
    ESTADO_RUN:       (0.005, 0.025),   # 0.5-2.5% regime
    ESTADO_PARTINDO:  (0.05,  0.20),    # 5-20% transiente alto
    ESTADO_SETUP:     (0.0,   0.0),
    ESTADO_FAULT:     (0.0,   0.0),
}


# ---------------------------------------------------------------------------
# Estado de um equipamento simulado
# ---------------------------------------------------------------------------
@dataclass
class EquipState:
    codigo: str
    linha: str
    tipo: str
    ordem: int
    vel_nominal: float

    estado: int = ESTADO_PARTINDO
    estado_ate: float = 0.0          # epoch s — quando o estado atual termina
    contagem_saida: int = 0
    contagem_entrada: int = 0
    descarte_total: int = 0
    velocidade_atual: float = 0.0
    op_codigo: str = ""
    op_inicio: float = 0.0
    op_fim: float = 0.0
    sku_codigo: str = "OMO 1000"
    sku_descricao: str = "OMO Sabão em Pó 1000g"
    formato_gramas: float = 1000.0
    cuc: float = 1.55
    planejado_op: int = 50000


@dataclass
class LinhaSim:
    codigo: str
    nome: str
    vel_planejada: float
    equipamentos: List[EquipState] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Simulador principal
# ---------------------------------------------------------------------------
class SimuladorEquipamentos:
    def __init__(self, rng_seed: Optional[int] = None):
        self.rng = random.Random(rng_seed)
        self._op_counter = 1
        self.linhas: List[LinhaSim] = []
        self._construir_topologia()
        self._inicializar_ops()

    # -----------------------------------------------------------------
    # Setup
    # -----------------------------------------------------------------
    def _construir_topologia(self):
        for lcod, lnome, vel_pl, equips in LINHAS_DEMO:
            linha = LinhaSim(codigo=lcod, nome=lnome, vel_planejada=vel_pl)
            for ecod, tipo, ordem, vnom in equips:
                eq = EquipState(
                    codigo=ecod, linha=lcod, tipo=tipo, ordem=ordem, vel_nominal=vnom,
                )
                linha.equipamentos.append(eq)
            self.linhas.append(linha)

    def _proxima_op_codigo(self) -> str:
        cod = f"OP-DEMO-{self._op_counter:05d}"
        self._op_counter += 1
        return cod

    def _escolher_sku(self) -> Tuple[str, str, float, float]:
        return self.rng.choice(SKUS_DEMO)

    def _inicializar_ops(self):
        now = self._now()
        for linha in self.linhas:
            sku = self._escolher_sku()
            op_codigo = self._proxima_op_codigo()
            dur = self.rng.uniform(*DUR_OP)
            planejado = int(linha.vel_planejada * 60 * (dur / 3600))
            for eq in linha.equipamentos:
                eq.sku_codigo = sku[0]
                eq.sku_descricao = sku[1]
                eq.formato_gramas = sku[2]
                eq.cuc = sku[3]
                eq.op_codigo = op_codigo
                eq.op_inicio = now
                eq.op_fim = now + dur
                eq.planejado_op = planejado
                eq.estado = ESTADO_PARTINDO
                eq.estado_ate = now + self.rng.uniform(*DUR_PARTINDO)

    # -----------------------------------------------------------------
    # Tempo
    # -----------------------------------------------------------------
    def _now(self) -> float:
        return datetime.now(tz=timezone.utc).timestamp()

    # -----------------------------------------------------------------
    # Máquina de estados por equipamento
    # -----------------------------------------------------------------
    def _transicionar(self, eq: EquipState, now: float, intervalo: float):
        # 1) Se estado atual ainda não terminou e não é RUN, mantém
        if eq.estado != ESTADO_RUN and now < eq.estado_ate:
            return

        # 2) Se OP terminou, faz SETUP e abre nova OP
        if now >= eq.op_fim and eq.estado != ESTADO_SETUP:
            eq.estado = ESTADO_SETUP
            eq.estado_ate = now + self.rng.uniform(*DUR_SETUP)
            return

        if eq.estado == ESTADO_SETUP and now >= eq.estado_ate:
            sku = self._escolher_sku()
            linha = self._linha_de(eq)
            op_codigo = self._proxima_op_codigo()
            dur = self.rng.uniform(*DUR_OP)
            planejado = int(linha.vel_planejada * 60 * (dur / 3600))
            # Sincronizar TODOS os equipamentos da mesma linha na mesma OP/SKU
            for eq2 in linha.equipamentos:
                eq2.sku_codigo = sku[0]
                eq2.sku_descricao = sku[1]
                eq2.formato_gramas = sku[2]
                eq2.cuc = sku[3]
                eq2.op_codigo = op_codigo
                eq2.op_inicio = now
                eq2.op_fim = now + dur
                eq2.planejado_op = planejado
                eq2.estado = ESTADO_PARTINDO
                eq2.estado_ate = now + self.rng.uniform(*DUR_PARTINDO)
            return

        # 3) Eventos espontâneos (somente saindo de RUN ou PARTINDO concluindo)
        if eq.estado == ESTADO_PARTINDO and now >= eq.estado_ate:
            eq.estado = ESTADO_RUN
            return

        if eq.estado == ESTADO_RUN:
            r = self.rng.random()
            if r < P_MICRO_FAULT:
                eq.estado = ESTADO_FAULT
                eq.estado_ate = now + self.rng.uniform(*DUR_FAULT)
            elif r < P_MICRO_FAULT + P_BLOCK_NEXT:
                eq.estado = ESTADO_BLOCK_NEXT
                eq.estado_ate = now + self.rng.uniform(*DUR_BLOCK_NEXT)
            elif r < P_MICRO_FAULT + P_BLOCK_NEXT + P_WAIT_PREV:
                eq.estado = ESTADO_WAIT_PREV
                eq.estado_ate = now + self.rng.uniform(*DUR_WAIT_PREV)
            elif r < P_MICRO_FAULT + P_BLOCK_NEXT + P_WAIT_PREV + P_FALTA_MAT:
                eq.estado = ESTADO_FALTA_MAT
                eq.estado_ate = now + self.rng.uniform(*DUR_FALTA_MAT)
            elif r < P_MICRO_FAULT + P_BLOCK_NEXT + P_WAIT_PREV + P_FALTA_MAT + P_AGUARD_MNT:
                eq.estado = ESTADO_AGUARD_MNT
                eq.estado_ate = now + self.rng.uniform(*DUR_AGUARD_MNT) if False else now + 600
            return

        # 4) Estado de parada terminou → volta para PARTINDO breve
        if eq.estado in (ESTADO_FAULT, ESTADO_BLOCK_NEXT, ESTADO_WAIT_PREV,
                         ESTADO_FALTA_MAT, ESTADO_AGUARD_MNT, ESTADO_MANUTENCAO) \
                and now >= eq.estado_ate:
            eq.estado = ESTADO_PARTINDO
            eq.estado_ate = now + self.rng.uniform(*DUR_PARTINDO)

    def _linha_de(self, eq: EquipState) -> LinhaSim:
        for l in self.linhas:
            if l.codigo == eq.linha:
                return l
        raise KeyError(eq.linha)

    # -----------------------------------------------------------------
    # Geração de medições (correlacionadas com o estado)
    #
    # Variáveis de processo simuladas com correlações *fisicamente
    # plausíveis* para que o Analytics e a matriz de correlação produzam
    # algo interessante de explorar:
    #
    #   • velocidade ↑   →  temperatura ↑   (mais atrito/aquecimento)
    #   • temperatura ↑  →  umidade ↓       (secagem mais agressiva)
    #   • pressao ↑      →  ultimo_peso ↑   (dosagem excessiva = give-away ↑)
    #   • estado=PARTINDO →  desvio amplo em peso e pressao
    #   • temperatura muito alta → defeitos/descarte sobe
    # -----------------------------------------------------------------
    def _gerar_medicoes(self, eq: EquipState, intervalo: float) -> Dict:
        # === Cinemática (vel / produção) ===
        if eq.estado == ESTADO_RUN:
            vel = max(0.0, self.rng.gauss(eq.vel_nominal, eq.vel_nominal * 0.05))
            produzido = vel / 60.0 * intervalo
            descarte_pct = self.rng.uniform(*DESCARTE_PCT[ESTADO_RUN])
        elif eq.estado == ESTADO_PARTINDO:
            progresso = 1.0 - max(0.0, (eq.estado_ate - self._now())) / max(1.0, DUR_PARTINDO[1])
            progresso = max(0.0, min(1.0, progresso))
            vel = eq.vel_nominal * progresso * self.rng.uniform(0.6, 1.0)
            produzido = vel / 60.0 * intervalo
            descarte_pct = self.rng.uniform(*DESCARTE_PCT[ESTADO_PARTINDO])
        else:
            vel = 0.0
            produzido = 0.0
            descarte_pct = 0.0

        # === Process vars com correlações ===
        # Fração da nominal (1.0 ≈ regime; <1.0 desacelerado; 0 parado)
        vel_frac = vel / eq.vel_nominal if eq.vel_nominal else 0.0
        rodando = eq.estado == ESTADO_RUN
        partindo = eq.estado == ESTADO_PARTINDO

        # temperatura: 38 + 18*vel_frac + ruído + offset por partindo
        base_temp = 38.0 + 18.0 * vel_frac
        if partindo:
            base_temp += self.rng.uniform(-4.0, 6.0)
        temperatura = max(20.0, self.rng.gauss(base_temp, 1.2))

        # pressao: 2.4 + 1.0*vel_frac + spike em partindo
        base_pres = 2.4 + 1.0 * vel_frac
        if partindo:
            base_pres += self.rng.uniform(-0.6, 0.9)
        pressao = max(0.3, self.rng.gauss(base_pres, 0.10))

        # umidade: anti-correlacionada com temperatura
        base_umid = 12.5 - 0.12 * (temperatura - 38.0)
        umidade = max(2.0, min(20.0, self.rng.gauss(base_umid, 0.5)))

        # ultimo_peso: alvo + viés positivo (~+1.0%) + ruído + amplifica
        # quando pressao está acima da média (over-dose)
        peso_alvo = eq.formato_gramas
        bias_pressao = (pressao - (2.4 + 1.0)) * 0.6  # g por unidade de pressao acima do nominal
        ultimo_peso = self.rng.gauss(peso_alvo * 1.010, peso_alvo * 0.006) + bias_pressao
        if partindo:
            ultimo_peso += self.rng.uniform(-peso_alvo * 0.04, peso_alvo * 0.04)

        # Process vars adicionais (todas correlacionadas)
        # corrente_motor (A): proporcional a velocidade × pressao (carga)
        corrente_motor = max(0.0, self.rng.gauss(8.0 + 12.0 * vel_frac + 1.5 * (pressao - 2.4), 0.8))
        # vibracao (mm/s): aumenta com vel; spike em partindo/fault
        base_vib = 1.2 + 2.8 * vel_frac
        if partindo:
            base_vib += self.rng.uniform(0.5, 2.0)
        vibracao = max(0.05, self.rng.gauss(base_vib, 0.3))
        # ph_dosagem: leve drift inversamente com pressao (sistema químico)
        ph_dosagem = max(5.0, min(12.0, self.rng.gauss(8.5 - 0.3 * (pressao - 2.4), 0.15)))
        # fluxo_ar (m3/h): forte correlação com velocidade
        fluxo_ar = max(0.0, self.rng.gauss(40.0 + 80.0 * vel_frac, 4.0))
        # tensao_rede (V): pouca variação, ~440V, leve queda em alta carga
        tensao_rede = self.rng.gauss(440.0 - corrente_motor * 0.3, 1.5)
        # condutividade (uS/cm): proporcional a umidade
        condutividade = max(0.0, self.rng.gauss(120.0 + 8.0 * umidade, 5.0))

        # temperatura muito alta → descarte extra
        if temperatura > 60.0 and rodando:
            descarte_pct += min(0.05, (temperatura - 60.0) * 0.01)
        # vibracao alta → descarte adicional (peças tortas)
        if vibracao > 4.5 and rodando:
            descarte_pct += min(0.04, (vibracao - 4.5) * 0.015)

        produzido_int = int(round(produzido))
        descarte_int = int(round(produzido * descarte_pct))
        entrada_int = produzido_int + descarte_int

        eq.contagem_saida += produzido_int
        eq.contagem_entrada += entrada_int
        eq.descarte_total += descarte_int
        eq.velocidade_atual = vel

        return {
            "estado_maquina":     eq.estado,
            "velocidade_atual":   round(vel, 2),
            "velocidade_real":    round(vel, 2),
            "contagem_saida":     eq.contagem_saida,
            "contagem_entrada":   eq.contagem_entrada,
            "descarte":           eq.descarte_total,
            "ordem_producao":     eq.op_codigo,
            "sku_codigo":         eq.sku_codigo,
            "descricao":          eq.sku_descricao,
            "formato":            eq.formato_gramas,
            "formato_gramas":     eq.formato_gramas,
            "planejado_op":       eq.planejado_op,
            "cuc":                eq.cuc,
            # Process vars principais (nomes alinhados com AVAILABLE_VARS do frontend)
            "temperatura":        round(temperatura, 2),
            "pressao":            round(pressao, 3),
            "umidade":            round(umidade, 2),
            "ultimo_peso":        round(ultimo_peso, 2),
            # Process vars adicionais (correlações físicas — ver _gerar_medicoes)
            "corrente_motor":     round(corrente_motor, 2),
            "vibracao":           round(vibracao, 3),
            "ph_dosagem":         round(ph_dosagem, 2),
            "fluxo_ar":           round(fluxo_ar, 1),
            "tensao_rede":        round(tensao_rede, 1),
            "condutividade":      round(condutividade, 1),
        }

    # -----------------------------------------------------------------
    # API pública
    # -----------------------------------------------------------------
    def passo(self, intervalo_s: float = 2.0, agora: Optional[float] = None) -> List[Dict]:
        """
        Avança a simulação em `intervalo_s` segundos e devolve a lista de
        payloads (um por equipamento) prontos para POST no Flask /dados/inserir.
        """
        now = agora if agora is not None else self._now()
        pacote: List[Dict] = []
        ts_iso = datetime.fromtimestamp(now, tz=timezone.utc).isoformat().replace("+00:00", "Z")

        for linha in self.linhas:
            for eq in linha.equipamentos:
                self._transicionar(eq, now, intervalo_s)
                medicoes = self._gerar_medicoes(eq, intervalo_s)
                pacote.append({
                    "equipamento_codigo": eq.codigo,
                    "linha_codigo":       linha.codigo,
                    "medicoes":           medicoes,
                    "timestamp":          ts_iso,
                })
        return pacote

    # -----------------------------------------------------------------
    # Pré-popular histórico via InfluxDB direto
    # -----------------------------------------------------------------
    def backfill_influxdb(self, influx_client, dias: int = 7, intervalo_s: int = 60) -> int:
        """
        Escreve N dias de histórico direto na measurement `production` do InfluxDB.
        Usa step de `intervalo_s` (default 60s — agregação minuto, ~10k pts/dia/eq).

        Retorna o número total de pontos escritos.
        """
        total = 0
        start_real = self._now()
        now_simulado = start_real - dias * 86400

        # Reseta para começar do passado
        for linha in self.linhas:
            for eq in linha.equipamentos:
                eq.contagem_saida = 0
                eq.contagem_entrada = 0
                eq.descarte_total = 0
                eq.estado = ESTADO_PARTINDO
                eq.estado_ate = now_simulado + self.rng.uniform(*DUR_PARTINDO)
                eq.op_inicio = now_simulado
                eq.op_fim = now_simulado + self.rng.uniform(*DUR_OP)

        logger.info(f"📜 Backfill InfluxDB: {dias}d × step {intervalo_s}s")
        batch: List[Dict] = []
        BATCH_SIZE = 5000

        # Acumuladores de turno/OP por equipamento — resetam no rollover.
        # IMPORTANTE: a chave do turno inclui a DATA (yyyy-mm-dd-turno) para
        # zerar a cada novo turno calendário, evitando acumular 7d no
        # toneladas_turno que o OLE-realtime usa como producao_real.
        acum: Dict[str, Dict] = {
            eq.codigo: {"turno": "", "op": "", "prod_t": 0, "ref_t": 0, "prod_op": 0, "ref_op": 0}
            for linha in self.linhas for eq in linha.equipamentos
        }

        while now_simulado < start_real:
            _dt = datetime.fromtimestamp(now_simulado, tz=timezone.utc)
            turno_letra = self._turno_de(now_simulado)
            turno_atual = f"{_dt.date().isoformat()}_{turno_letra}"
            for linha in self.linhas:
                for eq in linha.equipamentos:
                    prev_count = eq.contagem_saida
                    prev_desc = eq.descarte_total
                    self._transicionar(eq, now_simulado, intervalo_s)
                    m = self._gerar_medicoes(eq, intervalo_s)
                    delta_prod = max(0, eq.contagem_saida - prev_count)
                    delta_desc = max(0, eq.descarte_total - prev_desc)

                    a = acum[eq.codigo]
                    if a["turno"] != turno_atual:
                        a["turno"] = turno_atual
                        a["prod_t"] = 0
                        a["ref_t"] = 0
                        # IMPORTANTE: reset dos contadores PLC simulados a cada
                        # virada de turno — modela um PLC que reseta contagem
                        # por turno. Sem isso, contagem_saida cresce 7d sem
                        # parar e Flask interpreta como produção do turno atual.
                        eq.contagem_saida = 0
                        eq.contagem_entrada = 0
                        eq.descarte_total = 0
                    if a["op"] != eq.op_codigo:
                        a["op"] = eq.op_codigo
                        a["prod_op"] = 0
                        a["ref_op"] = 0
                    a["prod_t"] += delta_prod
                    a["ref_t"] += delta_desc
                    a["prod_op"] += delta_prod
                    a["ref_op"] += delta_desc

                    # OEE correlacionado com estado/velocidade
                    if eq.estado == ESTADO_RUN:
                        availability = self.rng.uniform(90.0, 98.0)
                        performance = max(0.0, min(105.0, (eq.velocidade_atual / eq.vel_nominal) * 100.0)) if eq.vel_nominal else 0.0
                        quality = max(0.0, 100.0 - (delta_desc / max(delta_prod, 1)) * 100.0)
                    elif eq.estado == ESTADO_PARTINDO:
                        availability = self.rng.uniform(60.0, 80.0)
                        performance = max(0.0, min(105.0, (eq.velocidade_atual / eq.vel_nominal) * 100.0)) if eq.vel_nominal else 0.0
                        quality = self.rng.uniform(75.0, 90.0)
                    else:
                        availability = 0.0
                        performance = 0.0
                        quality = 0.0
                    oee = availability * performance * quality / 10000.0

                    ts_iso = datetime.fromtimestamp(
                        now_simulado, tz=timezone.utc
                    ).isoformat().replace("+00:00", "Z")

                    # IMPORTANTE: tipos casam com o schema do Flask /dados/inserir.
                    fields = {
                        "velocidade_atual":          int(m["velocidade_atual"]),
                        "estado_maquina":            int(m["estado_maquina"]),
                        "contagem_saida":            int(m["contagem_saida"]),
                        "contagem_entrada":          int(m["contagem_entrada"]),
                        "descarte":                  int(m["descarte"]),
                        "planejado_op":              int(m["planejado_op"]),
                        "formato_gramas":            float(m["formato_gramas"]),
                        # Acumulados (waste dashboard / KPIs)
                        "producao_turno_acumulada":  int(a["prod_t"]),
                        "refugo_turno_acumulado":    int(a["ref_t"]),
                        "descarte_turno_acumulado":  int(a["ref_t"]),
                        "producao_op_acumulada":     int(a["prod_op"]),
                        "refugo_op_acumulado":       int(a["ref_op"]),
                        "toneladas_op":              round(a["prod_op"] * eq.formato_gramas / 1_000_000.0, 4),
                        "toneladas_turno":           round(a["prod_t"] * eq.formato_gramas / 1_000_000.0, 4),
                        # OEE
                        "oee_realtime":              round(oee, 2),
                        "availability_realtime":     round(availability, 2),
                        "performance_realtime":      round(performance, 2),
                        "quality_realtime":          round(quality, 2),
                        # Giveaway
                        "ultimo_peso":               float(m["ultimo_peso"]),
                        # Process vars (correlacionados — ver _gerar_medicoes)
                        "temperatura":               float(m["temperatura"]),
                        "pressao":                   float(m["pressao"]),
                        "umidade":                   float(m["umidade"]),
                        "corrente_motor":            float(m["corrente_motor"]),
                        "vibracao":                  float(m["vibracao"]),
                        "ph_dosagem":                float(m["ph_dosagem"]),
                        "fluxo_ar":                  float(m["fluxo_ar"]),
                        "tensao_rede":               float(m["tensao_rede"]),
                        "condutividade":             float(m["condutividade"]),
                        # Metadata como strings
                        "ordem_producao_field":      str(m["ordem_producao"]),
                        "sku_codigo_field":          str(m["sku_codigo"]),
                        "timestamp_medicao":         float(now_simulado),
                    }
                    batch.append({
                        "measurement": "production",
                        "tags": {
                            "line":      eq.linha,
                            "equipment": eq.codigo,
                            "shift":     turno_letra,
                            "order_id":  eq.op_codigo,
                            "sku":       eq.sku_codigo,
                        },
                        "time":   ts_iso,
                        "fields": fields,
                    })
                    if len(batch) >= BATCH_SIZE:
                        influx_client.write_points(batch)
                        total += len(batch)
                        batch = []

            now_simulado += intervalo_s

        if batch:
            influx_client.write_points(batch)
            total += len(batch)

        logger.info(f"📜 Backfill concluído: {total} pontos escritos.")
        return total

    @staticmethod
    def _turno_de(epoch: float) -> str:
        h = datetime.fromtimestamp(epoch, tz=timezone.utc).hour
        if 6 <= h < 14:
            return "A"
        if 14 <= h < 22:
            return "B"
        return "C"

    # -----------------------------------------------------------------
    # Metadata / eventos de estado (formato idêntico ao coletor real)
    # -----------------------------------------------------------------
    def transicoes_estado(self, anteriores: Dict[str, int]) -> List[Tuple[str, str]]:
        """
        Retorna lista de (equipamento_codigo, estado_txt) onde o estado MUDOU
        em relação ao snapshot `anteriores`. Atualiza `anteriores` in-place.
        """
        out: List[Tuple[str, str]] = []
        for linha in self.linhas:
            for eq in linha.equipamentos:
                prev = anteriores.get(eq.codigo)
                if prev != eq.estado:
                    out.append((eq.codigo, ESTADO_TXT.get(eq.estado, "OUTRO")))
                    anteriores[eq.codigo] = eq.estado
        return out

    def metadata_atual(self) -> List[Dict]:
        """Snapshot de metadata por equipamento (para sync_metadata)."""
        out = []
        for linha in self.linhas:
            for eq in linha.equipamentos:
                out.append({
                    "equipamento_codigo": eq.codigo,
                    "op_codigo":          eq.op_codigo,
                    "sku_codigo":         eq.sku_codigo,
                    "descricao":          eq.sku_descricao,
                    "formato":            eq.formato_gramas,
                    "meta_producao":      eq.planejado_op,
                })
        return out
