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
// Infra — fetch wrapper com tratamento de 422 Pydantic
// ============================================================
class ApiError extends Error {
    status;
    detail;
    constructor(status, detail, msg) {
        super(msg);
        this.status = status;
        this.detail = detail;
    }
}
async function postJson(path, body) {
    const url = `${FASTAPI_V2_URL}${path}`;
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        let detail = null;
        try {
            detail = await res.json();
        }
        catch { /* body não-json */ }
        const msg = res.status === 422
            ? `Validação falhou (422): ${JSON.stringify(detail)}`
            : `${res.status} ${res.statusText}`;
        throw new ApiError(res.status, detail, msg);
    }
    return res.json();
}
async function getJson(path) {
    const res = await fetch(`${FASTAPI_V2_URL}${path}`);
    if (!res.ok)
        throw new ApiError(res.status, null, `${res.status} ${res.statusText}`);
    return res.json();
}
// ============================================================
// Endpoints — analyze (EDA)
// ============================================================
export const analyze = {
    /** POST /analyze/stats — descritiva + Cp/Cpk + histograma por variável. */
    stats: (q) => postJson("/analyze/stats", q),
    /** POST /analyze/timeseries — séries agregadas com UCL/LCL Shewhart. */
    timeseries: (q) => postJson("/analyze/timeseries", q),
    /** POST /analyze/correlation — pearson/spearman + scatter data. */
    correlation: (q) => postJson("/analyze/correlation", q),
};
// ============================================================
// Endpoints — kpis (SSOT ISO 22400-2)
// ============================================================
export const kpis = {
    oee: (req) => postJson("/kpis/oee", req),
    tph: (req) => postJson("/kpis/tph", req),
    lineTph: (equipment_tphs) => postJson("/kpis/tph/line", { equipment_tphs }),
    giveAway: (req) => postJson("/kpis/give-away", req),
};
// ============================================================
// Health
// ============================================================
export const health = {
    live: () => getJson("/healthz"),
    ready: () => getJson("/ready"),
};
export { ApiError };
