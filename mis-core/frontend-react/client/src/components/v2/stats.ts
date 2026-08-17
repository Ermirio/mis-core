/**
 * stats.ts — utilitários de EDA (Exploratory Data Analysis) usados pelas pages
 * no padrão POC. Mantém os números explicáveis para um operador de planta sem
 * dependências adicionais (mantemos o bundle leve para o ambiente OT offline).
 *
 * Tudo respeita as regras do diagnóstico:
 *   1) OFF-mask: pontos com `off === 1` (equipamento desligado) viram `null`,
 *      não entram nas estatísticas e geram gap visual no gráfico (spanGaps:false).
 *   2) Delta para contadores acumulados: `applyDelta` converte série monotônica
 *      crescente em delta por janela.
 *
 * Não usar lodash aqui — operações simples, deterministas e auditáveis.
 */

export interface SeriesPoint { ts: Date | string; value: number; off?: 0 | 1; }

/** Aplica delta entre pontos sucessivos. Reseta para 0 quando OFF (evita
 *  picos artificiais entre desligar e ligar a máquina). */
export function applyDelta(series: SeriesPoint[]): SeriesPoint[] {
  const out: SeriesPoint[] = [];
  let prev: number | null = null;
  for (const p of series) {
    if (p.off === 1) {
      out.push({ ...p, value: 0 });
      prev = null;                // reseta — counter pode resetar no PLC após OFF
      continue;
    }
    const d = prev === null ? 0 : Math.max(0, p.value - prev);
    out.push({ ...p, value: d });
    prev = p.value;
  }
  return out;
}

/** Mascara pontos OFF como null (gera gaps no gráfico). */
export function maskOff<T extends SeriesPoint>(series: T[]): Array<T | (Omit<T, "value"> & { value: null })> {
  return series.map(p => p.off === 1 ? { ...p, value: null as any } : p);
}

/** Estatísticas descritivas (ignora null e off). */
export interface DescriptiveStats {
  n: number;
  mean: number | null;
  std: number | null;
  min: number | null;
  max: number | null;
  p50: number | null;
  p90: number | null;
  p99: number | null;
}

export function describe(values: Array<number | null | undefined>): DescriptiveStats {
  const v = values.filter((x): x is number => typeof x === "number" && Number.isFinite(x));
  if (!v.length) return { n: 0, mean: null, std: null, min: null, max: null, p50: null, p90: null, p99: null };
  const sorted = [...v].sort((a, b) => a - b);
  const sum = v.reduce((a, b) => a + b, 0);
  const mean = sum / v.length;
  const variance = v.reduce((a, b) => a + (b - mean) ** 2, 0) / v.length;
  const std = Math.sqrt(variance);
  const q = (p: number) => sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))];
  return {
    n: v.length, mean, std,
    min: sorted[0],
    max: sorted[sorted.length - 1],
    p50: q(.5), p90: q(.9), p99: q(.99),
  };
}

/** Histograma (free Sturges-ish). */
export function histogram(values: number[], bins = 14) {
  const v = values.filter(x => Number.isFinite(x));
  if (!v.length) return { labels: [], counts: [] };
  const min = Math.min(...v), max = Math.max(...v);
  if (min === max) return { labels: [min.toFixed(2)], counts: [v.length] };
  const step = (max - min) / bins;
  const labels: string[] = [];
  const counts = new Array(bins).fill(0);
  for (let b = 0; b < bins; b++) labels.push((min + b * step).toFixed(1));
  v.forEach(x => {
    let b = Math.floor((x - min) / step);
    if (b >= bins) b = bins - 1;
    counts[b]++;
  });
  return { labels, counts };
}

/** Boxplot stats por grupo (turno, SKU, etc.). */
export function boxStats(values: number[]) {
  const v = values.filter(x => Number.isFinite(x) && x > 0).sort((a, b) => a - b);
  if (!v.length) return { q1: 0, q2: 0, q3: 0, min: 0, max: 0, n: 0 };
  const q = (p: number) => v[Math.min(v.length - 1, Math.floor(p * v.length))];
  return { q1: q(.25), q2: q(.5), q3: q(.75), min: v[0], max: v[v.length - 1], n: v.length };
}

/** Formatadores comuns. */
export const fmt = {
  pct: (x: number | null | undefined, digits = 1) => {
    if (x === null || x === undefined || !Number.isFinite(x)) return "—";
    const v = x > 1 ? x : x * 100;
    return `${v.toFixed(digits)}%`;
  },
  num: (x: number | null | undefined, digits = 2) => {
    if (x === null || x === undefined || !Number.isFinite(x)) return "—";
    return x.toFixed(digits);
  },
  int: (x: number | null | undefined) => {
    if (x === null || x === undefined || !Number.isFinite(x)) return "—";
    return Math.round(x).toString();
  },
  ts: (d: Date | string) => {
    const x = typeof d === "string" ? new Date(d) : d;
    return x.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  },
};
