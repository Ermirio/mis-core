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
import { useNavigate } from "react-router-dom";
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

interface Equipamento {
  id: number | string;
  codigo: string;
  nome: string;
  linha: number | string;
  linha_nome?: string;
  linha_codigo?: string;
  status?: string;
}

interface FactoryLineMetric {
  linha_id: number | string;
  linha_codigo?: string;
  linha_nome?: string;
  oee?: number | string | null;
  disponibilidade?: number | string | null;
  availability?: number | string | null;
  performance?: number | string | null;
  qualidade?: number | string | null;
  quality?: number | string | null;
  give_away?: number | string | null;
  percentual_descarte?: number | string | null;
  descarte_percent?: number | string | null;
  descarte?: number | string | null;
  vazao_real_ton_hora?: number | string | null;
  tph?: number | string | null;
  toneladas_produzidas?: number | string | null;
  toneladas_produzidas_op?: number | string | null;
}

interface ProductionTimelinePoint {
  hora?: string;
  time?: string;
  realizado?: number | string | null;
}

interface ProductionPoint {
  time: string;
  timestamp: number;
  [key: string]: string | number;
}

interface DiagnosticAlert {
  rule?: string;
  severity?: "info" | "warning" | "critical" | string;
  message?: string;
  details?: unknown;
  timestamp?: string;
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
   Helpers
   ============================================================ */
function toNum(x: unknown): number | null {
  if (x === null || x === undefined || x === "") return null;
  const n = Number(x);
  return Number.isFinite(n) ? n : null;
}

function listFromApi<T>(data: unknown): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === "object" && Array.isArray((data as { results?: unknown }).results)) {
    return (data as { results: T[] }).results;
  }
  return [];
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${url}`);
  return response.json() as Promise<T>;
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

function lineChartKey(linha: Linha): string {
  return linha.codigo || linha.nome || `Linha ${linha.id}`;
}

function formatHourLabel(value: string | undefined): string {
  if (!value) return "--:--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 5);
  return date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function getLineColor(index: number): string {
  const palette = ["#3f5b7c", "#2d8659", "#c9932d", "#8a6ba8", "#b53a2b", "#4f7f8f", "#7a6a4f"];
  return palette[index % palette.length];
}

function mergeProductionSeries(series: Array<{ key: string; points: Array<{ timestamp: number; time: string; value: number }> }>): ProductionPoint[] {
  const rows = new Map<number, ProductionPoint>();
  for (const item of series) {
    for (const point of item.points) {
      const row = rows.get(point.timestamp) || { time: point.time, timestamp: point.timestamp };
      row[item.key] = point.value;
      rows.set(point.timestamp, row);
    }
  }
  return Array.from(rows.values()).sort((a, b) => Number(a.timestamp) - Number(b.timestamp));
}

function buildProductionSnapshot(linhas: Linha[], linhaKpis: Record<string, LinhaKpi>): ProductionPoint[] {
  const now = new Date();
  const row: ProductionPoint = {
    time: now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
    timestamp: now.getTime(),
  };

  for (const linha of linhas.slice(0, 6)) {
    const value = linhaKpis[String(linha.id)]?.producao_turno;
    if (value !== null && value !== undefined && Number.isFinite(value)) {
      row[lineChartKey(linha)] = value;
    }
  }

  return Object.keys(row).length > 2 ? [row] : [];
}

function productionKeys(data: ProductionPoint[]): string[] {
  const keys = new Set<string>();
  for (const row of data) {
    Object.keys(row).forEach((key) => {
      if (key !== "time" && key !== "timestamp") keys.add(key);
    });
  }
  return Array.from(keys);
}

async function fetchLinhaKpi(linhaNome: string): Promise<LinhaKpi | null> {
  try {
    // Flask-out Onda 3: /linha/<>/kpis migrado para Django.
    const d = await fetchJson<Record<string, unknown>>(`${DJANGO_API_URL}/linha/${encodeURIComponent(linhaNome)}/kpis`);
    const nested = d.kpis && typeof d.kpis === "object" ? d.kpis as Record<string, unknown> : d;
    return {
      oee:            toNum(d.oee ?? nested.oee ?? (d.gargalo as Record<string, unknown> | undefined)?.oee),
      availability:   toNum(d.availability ?? nested.availability ?? nested.disponibilidade),
      performance:    toNum(d.performance ?? nested.performance),
      quality:        toNum(d.quality ?? nested.quality ?? nested.qualidade),
      give_away:      toNum(d.give_away ?? nested.give_away),
      descarte:       toNum(d.descarte ?? d.scrap ?? nested.descarte_percent ?? nested.percentual_descarte ?? nested.descarte),
      tph:            toNum(d.tph ?? d.producao_horaria ?? nested.tph ?? nested.vazao_real_ton_hora),
      producao_turno: toNum(d.producao_turno ?? nested.producao_turno ?? nested.toneladas_produzidas),
    };
  } catch { return null; }
}

async function fetchFactoryLineKpis(): Promise<Record<string, LinhaKpi>> {
  const data = await fetchJson<unknown>(`${DJANGO_API_URL}/metricas_fabrica_consolidadas/`);
  const rows = listFromApi<FactoryLineMetric>(data);

  return Object.fromEntries(rows.map((row) => [
    String(row.linha_id),
    {
      oee: toNum(row.oee),
      availability: toNum(row.disponibilidade ?? row.availability),
      performance: toNum(row.performance),
      quality: toNum(row.qualidade ?? row.quality),
      give_away: toNum(row.give_away),
      descarte: toNum(row.percentual_descarte ?? row.descarte_percent ?? row.descarte),
      tph: toNum(row.vazao_real_ton_hora ?? row.tph),
      producao_turno: toNum(row.toneladas_produzidas ?? row.toneladas_produzidas_op),
    } satisfies LinhaKpi,
  ]));
}

async function fetchProductionSeries(linhas: Linha[]): Promise<ProductionPoint[]> {
  const series = await Promise.all(linhas.slice(0, 6).map(async (linha) => {
    try {
      const data = await fetchJson<{ timeline?: ProductionTimelinePoint[] }>(
        `${DJANGO_API_URL}/linhas/${encodeURIComponent(String(linha.id))}/planejado-vs-real/`
      );
      const points = (data.timeline || [])
        .map((point) => {
          const rawTime = point.hora || point.time;
          const timestamp = rawTime ? new Date(rawTime).getTime() : NaN;
          const value = toNum(point.realizado);
          if (!Number.isFinite(timestamp) || value === null) return null;
          return { timestamp, time: formatHourLabel(rawTime), value };
        })
        .filter((point): point is { timestamp: number; time: string; value: number } => point !== null);

      return points.length ? { key: lineChartKey(linha), points } : null;
    } catch {
      return null;
    }
  }));

  return mergeProductionSeries(series.filter((item): item is { key: string; points: Array<{ timestamp: number; time: string; value: number }> } => item !== null));
}

function normalizeAlertSeverity(severity: string | undefined): "bad" | "warn" {
  return severity === "critical" || severity === "error" || severity === "bad" ? "bad" : "warn";
}

async function fetchActiveAlerts(linhas: Linha[]): Promise<Alert[]> {
  const linhaIds = new Set(linhas.map((linha) => String(linha.id)));
  const equipamentosData = await fetchJson<unknown>(`${DJANGO_API_URL}/equipamentos/?page_size=10000`);
  const equipamentos = listFromApi<Equipamento>(equipamentosData)
    .filter((eq) => linhaIds.has(String(eq.linha)))
    .filter((eq) => !eq.status || eq.status === "ATIVO")
    .slice(0, 40);

  const alerts = await Promise.all(equipamentos.map(async (eq) => {
    try {
      const data = await fetchJson<{ alerts?: DiagnosticAlert[] }>(
        // Flask-out Onda 5: /diagnostics/alerts/<> migrado para Django.
        `${DJANGO_API_URL}/diagnostics/alerts/${encodeURIComponent(eq.codigo)}`
      );
      return (data.alerts || []).map((alert) => {
        const timestamp = alert.timestamp ? new Date(alert.timestamp) : new Date();
        return {
          time: timestamp.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
          sev: normalizeAlertSeverity(alert.severity),
          msg: `${eq.linha_nome || eq.linha_codigo || "Linha"} - ${eq.nome}: ${alert.message || alert.rule || "Alerta ativo"}`,
          ctx: alert.rule ? `Regra: ${alert.rule}` : `Equipamento: ${eq.codigo}`,
          timestamp: timestamp.getTime(),
        };
      });
    } catch {
      return [];
    }
  }));

  return alerts
    .flat()
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, 20)
    .map(({ timestamp: _timestamp, ...alert }) => alert);
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
  const navigate = useNavigate();
  const [linhas, setLinhas] = useState<Linha[]>([]);
  const [kpis,   setKpis]   = useState<Record<string, LinhaKpi>>({});
  const [productionData, setProductionData] = useState<ProductionPoint[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [dataNotice, setDataNotice] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const data = await fetchJson<unknown>(`${DJANGO_API_URL}/linhas/?page_size=10000`);
        const list: Linha[] = listFromApi<Linha>(data).filter((l: Linha) => l.ativa !== false);
        if (!alive) return;

        if (list.length === 0) {
          setLinhas([]);
          setKpis({});
          setProductionData([]);
          setAlerts([]);
          setDataNotice("Nenhuma linha ativa cadastrada foi encontrada no Django.");
          setLoading(false);
          return;
        }
        setLinhas(list);
        setDataNotice(null);

        const [factoryKpis, timelineData, activeAlerts] = await Promise.all([
          fetchFactoryLineKpis().catch(() => ({} as Record<string, LinhaKpi>)),
          fetchProductionSeries(list).catch(() => [] as ProductionPoint[]),
          fetchActiveAlerts(list).catch(() => [] as Alert[]),
        ]);

        const entries = await Promise.all(
          list.map(async (l) => {
            const k = factoryKpis[String(l.id)] ?? await fetchLinhaKpi(l.codigo || l.nome);
            return [String(l.id), k ?? { oee: null, availability: null, performance: null, quality: null }] as const;
          })
        );
        if (!alive) return;
        const nextKpis = Object.fromEntries(entries);
        setKpis(nextKpis);
        setProductionData(timelineData.length ? timelineData : buildProductionSnapshot(list, nextKpis));
        setAlerts(activeAlerts);
      } catch (error) {
        if (alive) {
          setLinhas([]);
          setKpis({});
          setProductionData([]);
          setAlerts([]);
          setDataNotice("Nao foi possivel carregar os dados reais da HOME. Verifique a API Django/Flask.");
        }
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
  const prodLineKeys = useMemo(() => productionKeys(productionData), [productionData]);

  // PR 14: Linhas que precisam atenção — top 3 piores OEE (com OEE conhecido).
  // Clicar leva para /linha/<codigo>/detalhes.
  const linhasAtencao = useMemo(() => {
    return linhas
      .map(l => {
        const k = kpis[String(l.id)];
        const oeeRaw = k?.oee;
        const oee = oeeRaw === null || oeeRaw === undefined ? null
          : (Number(oeeRaw) > 1 ? Number(oeeRaw) : Number(oeeRaw) * 100);
        return { linha: l, oee };
      })
      .filter(item => item.oee !== null && Number.isFinite(item.oee!))
      .sort((a, b) => (a.oee! - b.oee!))
      .slice(0, 3);
  }, [linhas, kpis]);

  // PR 17: Eventos das ultimas 4h (filtra alertas com timestamp recente).
  const eventos4h = useMemo(() => {
    const cutoff = Date.now() - 4 * 60 * 60 * 1000;
    return alerts.filter(a => {
      const t = a.time ? Date.parse(a.time) : NaN;
      return Number.isFinite(t) ? t >= cutoff : true; // sem timestamp: mantem
    });
  }, [alerts]);

  // PR 17: filtro "Visao por turno" (default desligado).
  const [filtroTurno, setFiltroTurno] = useState<boolean>(false);

  const prodLineColors = useMemo(
    () => Object.fromEntries(prodLineKeys.map((key, index) => [key, getLineColor(index)])),
    [prodLineKeys]
  );

  return (
    <div style={{ padding: "20px", background: C.bg, minHeight: "100vh", color: C.text, fontFamily: "system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif", fontSize: 14 }}>

      {/* ===== API state note ===== */}
      {dataNotice && (
        <div style={{ fontSize: 12, padding: "10px 14px", border: `1px dashed ${C.border}`, borderRadius: 6, background: "#fafafb", color: C.textMuted, marginBottom: 14 }}>
          <b style={{ color: C.text }}>Dados indisponiveis:</b> {dataNotice}
        </div>
      )}

      {/* ===== Toolbar: Visao por turno (PR 17) ===== */}
      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 12, color: C.textMuted }}>Visualizacao:</span>
        <button
          type="button"
          onClick={() => setFiltroTurno(false)}
          style={{
            fontSize: 12, padding: "4px 10px", borderRadius: 4, cursor: "pointer",
            border: `1px solid ${!filtroTurno ? C.accent : C.border}`,
            background: !filtroTurno ? C.accent : C.bgPanel,
            color: !filtroTurno ? "#fff" : C.text,
          }}
        >Total</button>
        <button
          type="button"
          onClick={() => setFiltroTurno(true)}
          style={{
            fontSize: 12, padding: "4px 10px", borderRadius: 4, cursor: "pointer",
            border: `1px solid ${filtroTurno ? C.accent : C.border}`,
            background: filtroTurno ? C.accent : C.bgPanel,
            color: filtroTurno ? "#fff" : C.text,
          }}
          title="Filtra eventos e alertas ao turno atual"
        >Turno atual</button>
      </div>

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

      {/* ===== Linhas que precisam atenção (PR 14) ===== */}
      {linhasAtencao.length > 0 && (
        <div style={{ marginTop: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", margin: "6px 0 10px" }}>
            <h2 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: C.text }}>Linhas que precisam atenção</h2>
            <span style={{ fontSize: 12, color: C.textMuted }}>Top 3 menor OEE • clique para detalhes</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(220px,1fr))", gap: 10 }}>
            {linhasAtencao.map(({ linha, oee }) => {
              const code = (linha.codigo || String(linha.id) || '').trim();
              const tone: "ok" | "warn" | "bad" =
                (oee ?? 0) >= 75 ? "ok" : (oee ?? 0) >= 55 ? "warn" : "bad";
              const toneColor = tone === "ok" ? C.ok : tone === "warn" ? C.warn : C.bad;
              return (
                <button
                  key={code || `linha-${linha.id}`}
                  type="button"
                  disabled={!code}
                  onClick={() => {
                    if (code) navigate(`/linha/${encodeURIComponent(code)}/detalhes`);
                  }}
                  style={{
                    background: C.bgPanel,
                    border: `1px solid ${C.border}`,
                    borderLeft: `3px solid ${toneColor}`,
                    borderRadius: 6,
                    padding: "10px 12px",
                    textAlign: "left",
                    cursor: "pointer",
                    display: "flex",
                    flexDirection: "column",
                    gap: 4,
                  }}
                  title={`OEE ${oee?.toFixed(1)}% — abrir detalhes da ${linha.nome}`}
                >
                  <span style={{ fontSize: 12, color: C.textMuted }}>{code}</span>
                  <span style={{ fontSize: 14, fontWeight: 600, color: C.text }}>{linha.nome}</span>
                  <span style={{ fontSize: 18, fontWeight: 700, color: toneColor }}>
                    {oee !== null ? `${oee.toFixed(1)}%` : "—"}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* ===== Eventos das ultimas 4h (PR 17) ===== */}
      <div style={{ marginTop: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", margin: "6px 0 10px" }}>
          <h2 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: C.text }}>
            Eventos das últimas 4h
            <span style={{ marginLeft: 8, fontSize: 11, padding: "1px 6px", borderRadius: 10, background: eventos4h.length > 0 ? "#f4dad6" : C.bgMuted, color: eventos4h.length > 0 ? C.bad : C.textMuted, fontWeight: 600 }}>
              {eventos4h.length}
            </span>
          </h2>
          <span style={{ fontSize: 12, color: C.textMuted }}>Paradas, descartes fora do padrão e perdas de comunicação</span>
        </div>
        <div style={{ background: C.bgPanel, border: `1px solid ${C.border}`, borderRadius: 6, padding: 10, maxHeight: 200, overflowY: "auto" }}>
          {eventos4h.length === 0 ? (
            <div style={{ color: C.textMuted, fontSize: 13, padding: 8, textAlign: "center" }}>
              Sem eventos relevantes na janela.
            </div>
          ) : (
            <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
              {eventos4h.slice(0, 20).map((e, i) => (
                <li key={i} style={{
                  display: "flex", gap: 10, padding: "6px 8px",
                  borderBottom: i < Math.min(19, eventos4h.length - 1) ? `1px solid ${C.bgMuted}` : "none",
                  fontSize: 12,
                }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: "50%", marginTop: 6, flexShrink: 0,
                    background: e.sev === "bad" ? C.bad : C.warn,
                  }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ color: C.text, fontWeight: 500 }}>{e.msg}</div>
                    <div style={{ color: C.textMuted, fontSize: 11 }}>
                      {e.ctx} {e.time && `· ${e.time}`}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* ===== 3. Two-col: produção + alertas ===== */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14, marginTop: 18 }}>

        {/* Produção acumulada */}
        <div style={{ background: C.bgPanel, border: `1px solid ${C.border}`, borderRadius: 6, padding: 14 }}>
          <h3 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600 }}>Produção acumulada por linha (turno atual)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={productionData} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.chartGrid} />
              <XAxis dataKey="time" tick={{ fontSize: 11, fill: C.textMuted }} />
              <YAxis tick={{ fontSize: 11, fill: C.textMuted }} label={{ value: "Produção (t)", angle: -90, position: "insideLeft", fontSize: 11, fill: C.textMuted, dx: -4 }} />
              <Tooltip
                contentStyle={{ fontSize: 12, borderColor: C.border }}
                labelStyle={{ color: C.text, fontWeight: 600 }}
              />
              <Legend iconSize={10} wrapperStyle={{ fontSize: 11, paddingTop: 4 }} />
              {prodLineKeys.map(l => (
                <Line key={l} type="monotone" dataKey={l} stroke={prodLineColors[l]}
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
              {alerts.filter(a => a.sev === "bad").length}
            </span>
          </h3>
          <ul style={{ padding: 0, margin: 0, maxHeight: 400, overflowY: "auto" }}>
            {alerts.length > 0
              ? alerts.map((a, i) => <AlertItem key={i} a={a} />)
              : <li style={{ padding: "10px 0", color: C.textMuted, fontSize: 12, listStyle: "none" }}>Nenhum alerta ativo retornado pelos diagnosticos.</li>}
          </ul>
        </div>
      </div>
    </div>
  );
};

export default HomeV2;
