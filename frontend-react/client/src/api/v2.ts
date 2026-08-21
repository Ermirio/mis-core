/**
 * src/api/v2.ts  —  Cliente HTTP tipado para o FastAPI v2.
 *
 * POR QUE ESTE ARQUIVO EXISTE (vs chamar fetch direto):
 *   - Evita "stringly-typed" payloads espalhados em dezenas de componentes;
 *   - Centraliza tratamento de erro (422 Pydantic -> mensagem legível);
 *   - Facilita o dia em que migrarmos Flask -> FastAPI COMPLETAMENTE
 *     (basta apontar DJANGO_API_URL = FASTAPI_V2_URL).
 *
 * PADRÃO DE URL: as rotas do FastAPI v2 espelham o Flask (ex.: /analyze/stats),
 * portanto o consumo em código fica VISUALMENTE igual. O que muda é o base URL.
 */
import { FASTAPI_V2_URL } from "@/config/api";

// ============================================================
// Tipos (espelham os schemas Pydantic em backend-fastapi/app/schemas/)
// ============================================================

/** Janela temporal estilo Grafana. */
export interface TimeRange {
  /** ISO-8601; alternativa a `last`. */
  start?: string;
  /** ISO-8601 ou a string "now". */
  end?: string;
  /** Shorthand retrocompat: "15m" | "1h" | "24h" | "7d" | "30d". */
  last?: string;
  /** "auto" (default) | "5s" | "1m" | ... | "1d". */
  granularity?:
    | "auto" | "5s" | "10s" | "30s" | "1m" | "5m" | "10m" | "30m" | "1h" | "1d";
}

export interface VariableRef {
  tag_influx: string;
  equipamento_code: string;
  alias?: string;
  lsl?: number;
  usl?: number;
  nominal?: number;
}

export interface AnalyticsQuery {
  variables: VariableRef[];
  time_range: TimeRange;
  /**
   * OFF-mask:
   *  - undefined/null  → usa default seguro (FAULT, TEST, MAINTENANCE, ...)
   *  - []              → NÃO filtra (comportamento explícito, ex.: auditoria)
   *  - ["FAULT", ...]  → filtra apenas estes estados
   */
  exclude_states?: string[] | null;
}

export interface DescriptiveStats {
  mean: number; std: number; min: number; max: number;
  median: number; p90: number; p99: number; count: number;
  cp?: number | null; cpk?: number | null;
}

export interface VariableStatsResult {
  variable: string;
  n_unique: number;
  is_discrete: boolean;
  stats: DescriptiveStats;
  histogram: { counts: number[]; bins: number[] };
}

export interface TimeSeriesPoint {
  timestamps: string[];
  values: (number | null)[];
  stats: Record<string, number | null>;
}

export interface CorrelationResponse {
  correlation_matrix: {
    columns: string[];
    values: number[][];
    p_values: number[][];
    method: "pearson" | "spearman";
    n_points: number;
    resample_rule: string;
  };
  scatter_data: Record<string, number[]>;
}

// ============================================================
// Infra — fetch wrapper com tratamento de 422 Pydantic
// ============================================================

class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, msg: string) {
    super(msg);
    this.status = status;
    this.detail = detail;
  }
}

async function postJson<TReq, TRes>(path: string, body: TReq): Promise<TRes> {
  const url = `${FASTAPI_V2_URL}${path}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    let detail: unknown = null;
    try { detail = await res.json(); } catch { /* body não-json */ }
    const msg =
      res.status === 422
        ? `Validação falhou (422): ${JSON.stringify(detail)}`
        : `${res.status} ${res.statusText}`;
    throw new ApiError(res.status, detail, msg);
  }
  return res.json() as Promise<TRes>;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${FASTAPI_V2_URL}${path}`);
  if (!res.ok) throw new ApiError(res.status, null, `${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// ============================================================
// Endpoints — analyze (EDA)
// ============================================================
export const analyze = {
  /** POST /analyze/stats — descritiva + Cp/Cpk + histograma por variável. */
  stats: (q: AnalyticsQuery) =>
    postJson<AnalyticsQuery, VariableStatsResult[]>("/analyze/stats", q),

  /** POST /analyze/timeseries — séries agregadas com UCL/LCL Shewhart. */
  timeseries: (q: AnalyticsQuery) =>
    postJson<AnalyticsQuery, Record<string, TimeSeriesPoint>>("/analyze/timeseries", q),

  /** POST /analyze/correlation — pearson/spearman + scatter data. */
  correlation: (q: AnalyticsQuery & { method?: "pearson" | "spearman" }) =>
    postJson<typeof q, CorrelationResponse>("/analyze/correlation", q),
};

// ============================================================
// Endpoints — kpis (SSOT ISO 22400-2)
// ============================================================
export const kpis = {
  oee: (req: {
    actual_production_time_s: number;
    planned_production_time_s: number;
    total_count: number;
    good_count: number;
    ideal_cycle_time_s: number;
  }) => postJson<typeof req, {
    availability: number; performance: number; performance_raw: number;
    quality: number; quality_valid: boolean; oee: number; oee_valid: boolean;
  }>("/kpis/oee", req),

  tph: (req: { velocity_upm: number; formato_g: number }) =>
    postJson<typeof req, { tph: number }>("/kpis/tph", req),

  lineTph: (equipment_tphs: number[]) =>
    postJson<{ equipment_tphs: number[] }, { tph: number }>("/kpis/tph/line", { equipment_tphs }),

  giveAway: (req: {
    avg_weight_g: number; target_weight_g: number;
    production_count: number; inmetro_tolerance_pct?: number;
  }) => postJson<typeof req, { kg_total: number; pct: number; samples: number }>(
    "/kpis/give-away", req,
  ),
};

// ============================================================
// Health
// ============================================================
export const health = {
  live: () => getJson<{ status: string; version: string; uptime_s: number; now: string }>("/healthz"),
  ready: () => getJson<{ status: string; checks: Record<string, string> }>("/ready"),
};

export { ApiError };
