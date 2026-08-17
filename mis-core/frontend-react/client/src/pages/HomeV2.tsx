/**
 * HomeV2 — Factory-level overview, fiel à PoC 04_POC_UI.html.
 *
 * Layout (ISA-101):
 *   1. KPI strip 6 cards (OEE Fábrica, Disponibilidade, Performance, Qualidade,
 *      Give Away, Descarte) — cada um com valor, delta e sparkline.
 *   2. Grade de cards por ÁREA (Envase, Paletização, Utilities…) com
 *      OEE agregado, TPH, Descarte e sparkline colorido por estado.
 *   3. Duas colunas: gráfico de produção acumulada (turno atual) + painel de alertas ativos.
 */

import React, { useEffect, useMemo, useState } from "react";
import {
  LineChart, Line, ResponsiveContainer,
  CartesianGrid, XAxis, YAxis, Legend, Tooltip,
} from "recharts";
import { DJANGO_API_URL, FLASK_API_URL } from "@/config/api";

/* ============================================================
   Paleta ISA-101 (idêntica ao 04_POC_UI.html)
   ============================================================ */
const C = {
  bg:         "#f4f5f7",
  bgPanel:    "#ffffff",
  bgMuted:    "#e9ecef",
  border:     "#d7dbe0",
  text:       "#2c3138",
  textMuted:  "#657384",
  textWeak:   "#9ba3ad",
  accent:     "#3f5b7c",
  ok:         "#2d8659",
  warn:       "#c9932d",
  bad:        "#b53a2b",
  chartGrid:  "#e1e4e8",
};

/* ============================================================
   Tipos
   ============================================================ */
interface Linha {
  id: number | string;
  codigo?: string;
  nome: string;
  ativa?: boolean;
  area?: { id: number | string; nome: string } | string | null;
  area_nome?: string;
  meta_oee?: number;
}

interface LinhaKpi {
  oee: number | null;
  availability: number | null;
  performance: number | null;
  quality: number | null;
  give_away?: number | null;
  descarte?: number | null;
  velocidade_atual?: number | null;
  producao_turno?: number | null;
  tph?: number | null;
}

interface AreaSummary {
  label: string;
  emoji: string;
  linhaCount: number;
  oee: number | null;
  tph: number | null;
  descarte: number | null;
  status: "ok" | "warn" | "bad";
  sparkData: { v: number }[];
}

interface Alert {
  time: string;
  sev: "bad" | "warn";
  msg: string;
  ctx: string;
}

/* ============================================================
   RNG determinístico (mesmo seed da PoC: 42)
   ============================================================ */
function makeRng(seed: number) {
  let s = seed;
  return () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
}

function spark24(rng: () => number, base = 50, range = 40): { v: number }[] {
  return Array.from({ length: 24 }, () => ({ v: base + rng() * range }));
}

/* ============================================================
   Mock data — ativo quando banco vazio ou API offline
   ============================================================ */
const rnd = makeRng(42);

const MOCK_LINHAS: Linha[] = [
  { id: 1,  codigo: "L01", nome: "Linha 01", ativa: true, area: { id: 1, nome: "Envase" } },
  { id: 2,  codigo: "L02", nome: "Linha 02", ativa: true, area: { id: 1, nome: "Envase" } },
  { id: 3,  codigo: "L03", nome: "Linha 03", ativa: true, area: { id: 1, nome: "Envase" } },
  { id: 4,  codigo: "L04", nome: "Linha 04", ativa: true, area: { id: 1, nome: "Envase" } },
  { id: 5,  codigo: "L05", nome: "Linha 05", ativa: true, area: { id: 1, nome: "Envase" } },
  { id: 6,  codigo: "L06", nome: "Linha 06", ativa: true, area: { id: 2, nome: "Paletização" } },
  { id: 7,  codigo: "L07", nome: "Linha 07", ativa: true, area: { id: 2, nome: "Paletização" } },
  { id: 8,  codigo: "L08", nome: "Linha 08", ativa: true, area: { id: 2, nome: "Paletização" } },
  { id: 9,  codigo: "U01", nome: "Compressores", ativa: true, area: { id: 3, nome: "Utilities" } },
  { id: 10, codigo: "U02", nome: "Chiller",      ativa: true, area: { id: 3, nome: "Utilities" } },
];

const MOCK_KPIS: Record<string, LinhaKpi> = {
  "1":  { oee: 0.87, availability: 0.91, performance: 0.96, quality: 0.99, give_away: 0.9,  descarte: 1.2, tph: 28, producao_turno: 23000 },
  "2":  { oee: 0.72, availability: 0.82, performance: 0.87, quality: 0.97, give_away: 1.4,  descarte: 2.1, tph: 20, producao_turno: 13800 },
  "3":  { oee: 0.48, availability: 0.58, performance: 0.81, quality: 0.95, give_away: 2.1,  descarte: 3.8, tph: 14, producao_turno: 11000 },
  "4":  { oee: 0.91, availability: 0.95, performance: 0.96, quality: 0.99, give_away: 0.7,  descarte: 0.9, tph: 30, producao_turno: 27500 },
  "5":  { oee: 0.68, availability: 0.79, performance: 0.85, quality: 0.96, give_away: 1.8,  descarte: 2.4, tph: 18, producao_turno: 0 },
  "6":  { oee: 0.83, availability: 0.89, performance: 0.92, quality: 0.98, give_away: null, descarte: 1.5, tph: 24, producao_turno: 11400 },
  "7":  { oee: null, availability: null, performance: null,  quality: null, give_away: null, descarte: null, tph: null, producao_turno: 0 },
  "8":  { oee: 0.41, availability: 0.51, performance: 0.79, quality: 0.97, give_away: null, descarte: 3.2, tph: 10, producao_turno: null },
  "9":  { oee: 0.94, availability: 0.97, performance: 0.97, quality: 1.00, give_away: null, descarte: 0.0, tph: 0,  producao_turno: null },
  "10": { oee: 0.92, availability: 0.96, performance: 0.96, quality: 0.99, give_away: null, descarte: 0.0, tph: 0,  producao_turno: null },
};

const MOCK_ALERTS: Alert[] = [
  { time: "13:47", sev: "bad",  msg: "Linha 03 — Falha na Encaixotadora (estado=FAULT)",           ctx: "Duração atual: 12 min · Operador notificado" },
  { time: "13:31", sev: "warn", msg: "Linha 02 — Give Away acima de +2 g/un por 10 min consecutivos", ctx: "Sugestão: verificar calibração da balança 02" },
  { time: "13:20", sev: "bad",  msg: "Linha 08 — OEE caiu abaixo de 50% no turno",                 ctx: "Principal ofensor: disponibilidade (7 microparadas)" },
  { time: "12:55", sev: "warn", msg: "Coletor OPC — latência acima de 500 ms para PLC Siemens-02", ctx: "Sem perda de dados (buffer local ativo)" },
  { time: "11:10", sev: "warn", msg: "Linha 05 — velocidade < 80% do nominal por 25 min",          ctx: "Possível gargalo upstream" },
  { time: "10:42", sev: "bad",  msg: "Linha 07 — OFFLINE (coletor sem conexão OPC há 4 min)",      ctx: "Reconexão em curso (tentativa 3/10)" },
  { time: "09:30", sev: "warn", msg: "Linha 01 — Refugo horário acima de 3% (limite 2,5%)",       ctx: "SKU: PET-500ml-regular" },
];

const PROD_LABELS = ["06:00", "07:00", "08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00"];
const MOCK_PROD_DATA = PROD_LABELS.map((time, i) => ({
  time,
  L01: [2.2, 4.8, 7.6, 10.1, 12.8, 15.2, 17.9, 20.3, 23.0][i],
  L02: [1.8, 3.6, 5.0, 6.2,  6.2,  8.4, 10.0, 12.1, 13.8][i],
  L04: [2.6, 5.4, 8.3, 11.3, 14.5, 17.8, 21.0, 24.3, 27.5][i],
  L06: [1.5, 3.1, 4.8, 6.0,  6.0,  7.1,  8.5, 10.0, 11.4][i],
}));
const PROD_LINE_COLORS: Record<string, string> = {
  L01: "#3f5b7c", L02: "#c9932d", L04: "#2d8659", L06: "#8a6ba8",
};

/* ============================================================
   Helpers
   ============================================================ */
function toNum(x: unknown): number | null {
  if (x === null || x === undefined || x === "") return null;
  const n = Number(x);
  return Number.isFinite(n) ? n : null;
}

function norm(x: number | null): number | null {
  if (x === null) return null;
  return x > 1 ? x / 100 : x;
}

function pctStr(x: number | null): string {
  if (x === null) return "—";
  const v = (x > 1 ? x : x * 100);
  return `${v.toFixed(1)}%`;
}

function extractArea(l: Linha): string {
  if (typeof l.area === "string" && l.area) return l.area;
  if (l.area && typeof l.area === "object" && "nome" in l.area) return l.area.nome;
  if (l.area_nome) return l.area_nome;
  return "Outras";
}

const AREA_BUCKETS: { match: RegExp; label: string; emoji: string }[] = [
  { match: /envas/i,       label: "Envase",        emoji: "🧴" },
  { match: /empac|pack/i,  label: "Empacotamento", emoji: "📦" },
  { match: /palet/i,       label: "Paletização",   emoji: "🧱" },
  { match: /rotul/i,       label: "Rotulagem",     emoji: "🏷️" },
  { match: /util|chiller|compress/i, label: "Utilities", emoji: "🔧" },
];

function bucketOf(areaName: string): { label: string; emoji: string } {
  for (const b of AREA_BUCKETS) if (b.match.test(areaName)) return { label: b.label, emoji: b.emoji };
  return { label: areaName || "Outras", emoji: "🏭" };
}

async function fetchLinhaKpi(linhaNome: string): Promise<LinhaKpi | null> {
  try {
    const r = await fetch(`${FLASK_API_URL}/api/linha/${encodeURIComponent(linhaNome)}/kpis`);
    if (!r.ok) return null;
    const d = await r.json();
    return {
      oee:           toNum(d.oee),
      availability:  toNum(d.availability),
      performance:   toNum(d.performance),
      quality:       toNum(d.quality),
      give_away:     toNum(d.give_away),
      descarte:      toNum(d.descarte ?? d.scrap),
      tph:           toNum(d.tph ?? d.producao_horaria),
      producao_turno:toNum(d.producao_turno),
    };
  } catch { return null; }
}

/* ============================================================
   Sub-componentes
   ============================================================ */

/** Sparkline mínima usando Recharts — sem eixos, sem tooltip */
const Spark: React.FC<{ data: { v: number }[]; color: string; fill?: boolean }> =
  ({ data, color, fill }) => (
    <ResponsiveContainer width="100%" height={26}>
      <LineChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
        <Line
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
          fill={fill ? `${color}20` : "none"}
        />
      </LineChart>
    </ResponsiveContainer>
  );

interface KpiCardProps {
  label: string;
  value: string;
  unit?: string;
  delta?: string;
  deltaDir?: "up" | "down" | "none";
  sparkColor: string;
  sparkData: { v: number }[];
}
const KpiCard: React.FC<KpiCardProps> = ({ label, value, unit, delta, deltaDir, sparkColor, sparkData }) => {
  const deltaColor = deltaDir === "up" ? C.ok : deltaDir === "down" ? C.bad : C.textMuted;
  const deltaIcon  = deltaDir === "up" ? "▲" : deltaDir === "down" ? "▼" : "";
  return (
    <div style={{
      background: C.bgPanel,
      border: `1px solid ${C.border}`,
      borderRadius: 6,
      padding: 12,
    }}>
      <div style={{ fontSize: 10, textTransform: "uppercase", color: C.textMuted, letterSpacing: "0.05em" }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 600, marginTop: 3, color: C.text, fontVariantNumeric: "tabular-nums" }}>
        {value}
        {unit && <span style={{ fontSize: 14, color: C.textMuted, marginLeft: 2 }}>{unit}</span>}
      </div>
      {delta && (
        <div style={{ fontSize: 11, marginTop: 3, color: deltaColor, fontVariantNumeric: "tabular-nums" }}>
          {deltaIcon} {delta}
        </div>
      )}
      <div style={{ marginTop: 6 }}>
        <Spark data={sparkData} color={sparkColor} />
      </div>
    </div>
  );
};

const AreaCard: React.FC<{ area: AreaSummary }> = ({ area }) => {
  const statusColor = area.status === "ok" ? C.ok : area.status === "warn" ? C.warn : C.bad;
  const badgeBg     = area.status === "ok" ? "#e3efe7" : area.status === "warn" ? "#f4e8cf" : "#f4dad6";
  return (
    <div style={{
      background: C.bgPanel,
      border: `1px solid ${C.border}`,
      borderRadius: 6,
      padding: 12,
      cursor: "pointer",
      transition: "box-shadow 0.12s",
    }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = "0 1px 4px rgba(0,0,0,.08)")}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = "none")}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14 }}>{area.emoji} {area.label}</div>
          <div style={{ fontSize: 11, color: C.textMuted, marginTop: 1 }}>
            {area.linhaCount} {area.linhaCount === 1 ? "linha" : "linhas"}
          </div>
        </div>
        <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 10, background: badgeBg, color: statusColor, fontWeight: 600 }}>
          {area.status.toUpperCase()}
        </span>
      </div>
      <div style={{ display: "flex", gap: 14, marginTop: 8, fontSize: 11, color: C.textMuted }}>
        <span>
          <b style={{ display: "block", color: C.text, fontSize: 14, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
            {area.oee !== null ? `${(area.oee > 1 ? area.oee : area.oee * 100).toFixed(1)}%` : "—"}
          </b>OEE
        </span>
        <span>
          <b style={{ display: "block", color: C.text, fontSize: 14, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
            {area.tph !== null ? area.tph.toFixed(0) : "—"}
          </b>TPH
        </span>
        <span>
          <b style={{ display: "block", color: C.text, fontSize: 14, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
            {area.descarte !== null ? `${area.descarte.toFixed(1)}%` : "—"}
          </b>Descarte
        </span>
      </div>
      <div style={{ marginTop: 8 }}>
        <Spark data={area.sparkData} color={statusColor} />
      </div>
    </div>
  );
};

const AlertItem: React.FC<{ a: Alert }> = ({ a }) => {
  const dotColor = a.sev === "bad" ? C.bad : C.warn;
  return (
    <li style={{
      padding: "8px 0",
      borderBottom: `1px solid ${C.border}`,
      fontSize: 12,
      display: "flex",
      gap: 10,
      alignItems: "flex-start",
      listStyle: "none",
    }}>
      <span style={{ color: C.textMuted, fontFamily: "monospace", fontSize: 11, minWidth: 38 }}>{a.time}</span>
      <span style={{ marginTop: 4, flexShrink: 0 }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", display: "inline-block", background: dotColor }} />
      </span>
      <div>
        <div>{a.msg}</div>
        <div style={{ color: C.textMuted, fontSize: 11, marginTop: 2 }}>{a.ctx}</div>
      </div>
    </li>
  );
};

/* ============================================================
   Componente principal
   ============================================================ */
const HomeV2: React.FC = () => {
  const [linhas, setLinhas] = useState<Linha[]>([]);
  const [kpis,   setKpis]   = useState<Record<string, LinhaKpi>>({});
  const [loading, setLoading] = useState(true);
  const [isDemo,  setIsDemo]  = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const resp = await fetch(`${DJANGO_API_URL}/linhas/`);
        const data = await resp.json();
        const list: Linha[] = (data.results || data || []).filter((l: Linha) => l.ativa !== false);
        if (!alive) return;

        if (list.length === 0) {
          setLinhas(MOCK_LINHAS);
          setKpis(MOCK_KPIS);
          setIsDemo(true);
          setLoading(false);
          return;
        }
        setLinhas(list);
        const entries = await Promise.all(
          list.map(async (l) => {
            const k = await fetchLinhaKpi(l.nome || String(l.codigo));
            return [String(l.id), k ?? { oee: null, availability: null, performance: null, quality: null }] as const;
          })
        );
        if (!alive) return;
        setKpis(Object.fromEntries(entries));
      } catch {
        if (alive) { setLinhas(MOCK_LINHAS); setKpis(MOCK_KPIS); setIsDemo(true); }
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  /* --- Factory-wide KPI aggregation --- */
  const factoryKpi = useMemo(() => {
    const vals = Object.values(kpis);
    function avg(getter: (k: LinhaKpi) => number | null | undefined): number | null {
      const ns = vals.map(getter).filter((x): x is number => x !== null && x !== undefined && Number.isFinite(x));
      return ns.length ? ns.reduce((a, b) => a + b, 0) / ns.length : null;
    }
    const ga = avg(k => k.give_away);
    return {
      oee:          avg(k => norm(k.oee)),
      availability: avg(k => norm(k.availability)),
      performance:  avg(k => norm(k.performance)),
      quality:      avg(k => norm(k.quality)),
      giveAway:     ga,
      descarte:     avg(k => k.descarte !== undefined && k.descarte !== null ? (k.descarte > 1 ? k.descarte / 100 : k.descarte) : null),
    };
  }, [kpis]);

  /* --- Area summaries --- */
  const areas = useMemo<AreaSummary[]>(() => {
    const areaMap = new Map<string, { label: string; emoji: string; ids: string[] }>();
    for (const l of linhas) {
      const bn = bucketOf(extractArea(l));
      if (!areaMap.has(bn.label)) areaMap.set(bn.label, { ...bn, ids: [] });
      areaMap.get(bn.label)!.ids.push(String(l.id));
    }
    const r = makeRng(77);
    return Array.from(areaMap.values()).map(({ label, emoji, ids }) => {
      const aKpis = ids.map(id => kpis[id]).filter(Boolean);
      function aAvg(getter: (k: LinhaKpi) => number | null | undefined): number | null {
        const ns = aKpis.map(getter).filter((x): x is number => x !== null && x !== undefined && Number.isFinite(x));
        return ns.length ? ns.reduce((a, b) => a + b, 0) / ns.length : null;
      }
      const oee  = aAvg(k => norm(k.oee));
      const tph  = aAvg(k => k.tph ?? null);
      const desc = aAvg(k => k.descarte !== undefined && k.descarte !== null ? (k.descarte > 1 ? k.descarte / 100 : k.descarte) : null);
      const oeeV = oee !== null ? (oee > 1 ? oee / 100 : oee) : null;
      const status: "ok" | "warn" | "bad" =
        oeeV === null ? "warn" : oeeV >= 0.75 ? "ok" : oeeV >= 0.55 ? "warn" : "bad";
      const sparkData = spark24(r, 60, 30);
      return { label, emoji, linhaCount: ids.length, oee, tph, descarte: desc !== null ? desc * 100 : null, status, sparkData };
    }).sort((a, b) => a.label.localeCompare(b.label));
  }, [linhas, kpis]);

  /* --- Sparklines for KPI strip --- */
  const rKpi = useMemo(() => makeRng(42), []);
  const sparks = useMemo(() => ({
    oee:    spark24(rKpi, 70, 20),
    avail:  spark24(rKpi, 78, 15),
    perf:   spark24(rKpi, 88, 10),
    qual:   spark24(rKpi, 95, 8),
    ga:     spark24(rKpi, 40, 30),
    scrap:  spark24(rKpi, 30, 25),
  }), []); // eslint-disable-line react-hooks/exhaustive-deps

  const p = (v: number | null) => v !== null ? `${(v > 1 ? v : v * 100).toFixed(1)}` : "—";

  return (
    <div style={{ padding: "20px", background: C.bg, minHeight: "100vh", color: C.text, fontFamily: "system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif", fontSize: 14 }}>

      {/* ===== ISA-101 note + demo badge ===== */}
      {isDemo && (
        <div style={{ fontSize: 12, padding: "10px 14px", border: `1px dashed ${C.border}`, borderRadius: 6, background: "#fafafb", color: C.textMuted, marginBottom: 14 }}>
          <b style={{ color: C.text }}>Modo simulação:</b> banco vazio ou API offline — dados de demonstração. Conecte o OPC e cadastre as linhas para ver dados reais.
        </div>
      )}

      {/* ===== 1. KPI Strip ===== */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6,1fr)", gap: 10, marginBottom: 18 }}>
        <KpiCard label="OEE Fábrica"   value={p(factoryKpi.oee)}          unit="%" delta="▲ 2.1 vs ontem" deltaDir="up"   sparkColor={C.accent} sparkData={sparks.oee}   />
        <KpiCard label="Disponibilidade" value={p(factoryKpi.availability)} unit="%" delta="▼ 1.4"          deltaDir="down" sparkColor={C.accent} sparkData={sparks.avail} />
        <KpiCard label="Performance"   value={p(factoryKpi.performance)}   unit="%" delta="▲ 0.3"          deltaDir="up"   sparkColor={C.accent} sparkData={sparks.perf}  />
        <KpiCard label="Qualidade"     value={p(factoryKpi.quality)}       unit="%"                                        sparkColor={C.accent} sparkData={sparks.qual}  />
        <KpiCard label="Give Away"     value={factoryKpi.giveAway !== null ? `+${(factoryKpi.giveAway).toFixed(1)}` : "—"} unit="g/un" delta="+0.3g vs meta" deltaDir="down" sparkColor={C.warn} sparkData={sparks.ga} />
        <KpiCard label="Descarte"      value={factoryKpi.descarte !== null ? `${(factoryKpi.descarte * 100).toFixed(1)}` : "—"} unit="%" delta="▼ 0.4" deltaDir="up" sparkColor={C.bad} sparkData={sparks.scrap} />
      </div>

      {/* ===== 2. Visão por Área ===== */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", margin: "6px 0 10px" }}>
        <h2 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: C.text }}>Visão por Área</h2>
        <span style={{ fontSize: 12, color: C.textMuted }}>Clique em uma área para fazer drill-down</span>
      </div>

      {loading ? (
        <p style={{ color: C.textMuted, padding: 8 }}>Carregando…</p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(320px,1fr))", gap: 10 }}>
          {areas.map(a => <AreaCard key={a.label} area={a} />)}
        </div>
      )}

      {/* ===== 3. Two-col: produção + alertas ===== */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14, marginTop: 18 }}>

        {/* Produção acumulada */}
        <div style={{ background: C.bgPanel, border: `1px solid ${C.border}`, borderRadius: 6, padding: 14 }}>
          <h3 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600 }}>Produção acumulada por linha (turno atual)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={MOCK_PROD_DATA} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.chartGrid} />
              <XAxis dataKey="time" tick={{ fontSize: 11, fill: C.textMuted }} />
              <YAxis tick={{ fontSize: 11, fill: C.textMuted }} label={{ value: "Produção (t)", angle: -90, position: "insideLeft", fontSize: 11, fill: C.textMuted, dx: -4 }} />
              <Tooltip
                contentStyle={{ fontSize: 12, borderColor: C.border }}
                labelStyle={{ color: C.text, fontWeight: 600 }}
              />
              <Legend iconSize={10} wrapperStyle={{ fontSize: 11, paddingTop: 4 }} />
              {Object.keys(PROD_LINE_COLORS).map(l => (
                <Line key={l} type="monotone" dataKey={l} stroke={PROD_LINE_COLORS[l]}
                  strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Alertas ativos */}
        <div style={{ background: C.bgPanel, border: `1px solid ${C.border}`, borderRadius: 6, padding: 14 }}>
          <h3 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600 }}>
            Alertas ativos
            <span style={{ marginLeft: 8, fontSize: 10, padding: "1px 6px", borderRadius: 10, background: "#f4dad6", color: C.bad, fontWeight: 600 }}>
              {MOCK_ALERTS.filter(a => a.sev === "bad").length}
            </span>
          </h3>
          <ul style={{ padding: 0, margin: 0, maxHeight: 400, overflowY: "auto" }}>
            {MOCK_ALERTS.map((a, i) => <AlertItem key={i} a={a} />)}
          </ul>
        </div>
      </div>
    </div>
  );
};

export default HomeV2;
