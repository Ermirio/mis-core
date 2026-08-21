/**
 * Átomos do Design System ISA-101 — usam exclusivamente as variáveis CSS de
 * styles/isa101.css. Cada átomo reproduz um bloco da POC (docs/blueprint).
 *
 * Convenção:
 *   - Componentes "burros" (sem fetch). Toda a lógica de dados fica nas pages.
 *   - className `isa-*` referencia o tema global. Nada de Tailwind hardcoded
 *     que conflite com a paleta da POC (esses casos quebram a coerência ISA).
 *   - Sparklines usam Chart.js (já presente no projeto via dashboard atual).
 */

import React, { useEffect, useRef } from "react";

// =====================================================================
// Panel
// =====================================================================
export const Panel: React.FC<{
  title?: React.ReactNode;
  desc?: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
  actions?: React.ReactNode;
}> = ({ title, desc, className = "", style, children, actions }) => (
  <div className={`isa-panel ${className}`} style={style}>
    {(title || actions) && (
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: title ? 8 : 0 }}>
        {title && <h3 style={{ margin: 0 }}>{title}</h3>}
        {actions}
      </div>
    )}
    {desc && <div style={{ fontSize: "var(--isa-fs-meta)", color: "var(--isa-text-muted)", marginBottom: 8 }}>{desc}</div>}
    {children}
  </div>
);

// =====================================================================
// SectionHead
// =====================================================================
export const SectionHead: React.FC<{ title: React.ReactNode; desc?: React.ReactNode; right?: React.ReactNode }> =
  ({ title, desc, right }) => (
  <div className="isa-section-head">
    <div>
      <h2>{title}</h2>
      {desc && <div className="isa-section-head__desc">{desc}</div>}
    </div>
    {right}
  </div>
);

// =====================================================================
// Note (banner explicativo da POC)
// =====================================================================
export const Note: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="isa-note">{children}</div>
);

// =====================================================================
// Tag (semântica)
// =====================================================================
export const Tag: React.FC<{ tone?: "ok" | "warn" | "bad" | "neutral"; children: React.ReactNode }> =
  ({ tone = "neutral", children }) => {
  const cls = tone === "neutral" ? "" : `isa-tag--${tone}`;
  return <span className={`isa-tag ${cls}`}>{children}</span>;
};

// =====================================================================
// StatusDot
// =====================================================================
export const StatusDot: React.FC<{ tone: "ok" | "warn" | "bad" | "off" }> = ({ tone }) => (
  <span className={`isa-dot isa-dot--${tone}`} aria-hidden="true" />
);

// =====================================================================
// KpiCard
// Reproduz o `.kpi` da POC: label, valor numérico grande com unidade
// pequena, delta (▲/▼) e sparkline opcional.
// =====================================================================
export interface KpiCardProps {
  label: string;
  value: string | number;
  unit?: string;
  delta?: { value: string; tone?: "up" | "down" | "neutral" };
  spark?: number[];                    // 24 pontos típicos
  sparkColor?: string;                 // default: --isa-accent
  ariaLabel?: string;
}

export const KpiCard: React.FC<KpiCardProps> = ({ label, value, unit, delta, spark, sparkColor, ariaLabel }) => {
  const ref = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => {
    if (!spark || !ref.current) return;
    let chart: any = null;
    let cancelled = false;
    (async () => {
      const Chart = (await import("chart.js/auto")).default;
      if (cancelled || !ref.current) return;
      const color = sparkColor || getCssVar("--isa-accent") || "#3f5b7c";
      chart = new Chart(ref.current, {
        type: "line",
        data: { labels: spark.map((_, i) => i), datasets: [{
          data: spark, borderColor: color, borderWidth: 1.5, pointRadius: 0,
          tension: .3, fill: true, backgroundColor: color + "20",
        }]},
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { enabled: false } },
          scales: { x: { display: false }, y: { display: false } },
          animation: false,
        },
      });
    })();
    return () => { cancelled = true; if (chart) chart.destroy(); };
  }, [spark, sparkColor]);

  return (
    <div className="isa-kpi" aria-label={ariaLabel || label}>
      <div className="isa-kpi__lbl">{label}</div>
      <div className="isa-kpi__val">
        {value}{unit && <small> {unit}</small>}
      </div>
      {delta && (
        <div className={`isa-kpi__delta ${delta.tone === "up" ? "isa-kpi__delta--up" : delta.tone === "down" ? "isa-kpi__delta--down" : ""}`}>
          {delta.value}
        </div>
      )}
      {spark && <div className="isa-kpi__spark"><canvas ref={ref} /></div>}
    </div>
  );
};

function getCssVar(name: string): string {
  if (typeof document === "undefined") return "";
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// =====================================================================
// KpiStrip (wrapper de N KPIs)
// =====================================================================
export const KpiStrip: React.FC<{
  cols?: 3 | 4 | 6;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ cols = 6, children, style }) => (
  <div className={`isa-kpi-strip ${cols !== 6 ? `isa-kpi-strip--${cols}` : ""}`} style={style}>
    {children}
  </div>
);

// =====================================================================
// ChartCard (canvas wrapper 340px)
// =====================================================================
export const ChartCard: React.FC<{
  title: React.ReactNode;
  desc?: React.ReactNode;
  tag?: { label: string; tone?: "ok" | "warn" | "bad" };
  children: React.ReactNode;     // o canvas / Plot
  height?: number;
}> = ({ title, desc, tag, children, height }) => (
  <div className="isa-chart-card" style={height ? { height } : undefined}>
    <h4 className="isa-chart-card__title">
      <span>{title}</span>
      {tag && <Tag tone={tag.tone}>{tag.label}</Tag>}
    </h4>
    {desc && <div className="isa-chart-card__desc">{desc}</div>}
    <div className="isa-chart-card__body">{children}</div>
  </div>
);

// =====================================================================
// ChartRow
// =====================================================================
export const ChartRow: React.FC<{ cols?: 1 | 2 | 3; children: React.ReactNode }> = ({ cols = 2, children }) => (
  <div className={`isa-chart-row ${cols === 3 ? "isa-chart-row--triple" : cols === 1 ? "isa-chart-row--single" : ""}`}>
    {children}
  </div>
);

// =====================================================================
// StatsGrid (EDA — n, média, std, p50, p90, p99)
// =====================================================================
export const StatsGrid: React.FC<{
  stats: Array<{ label: string; value: React.ReactNode }>;
}> = ({ stats }) => (
  <div className="isa-stats-grid">
    {stats.map((s, i) => (
      <div key={i} className="isa-stat">
        <div className="isa-stat__lbl">{s.label}</div>
        <div className="isa-stat__val">{s.value}</div>
      </div>
    ))}
  </div>
);

// =====================================================================
// EquipmentHeader
// =====================================================================
export const EquipmentHeader: React.FC<{
  initials: string;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  state?: { label: string; tone: "run" | "stop" | "warn" | "off" };
  right?: React.ReactNode;
}> = ({ initials, title, subtitle, state, right }) => (
  <div className="isa-eq-head">
    <div className="isa-eq-head__avatar">{initials.slice(0, 2).toUpperCase()}</div>
    <div className="isa-eq-head__info">
      <div className="isa-eq-head__title">{title}</div>
      {subtitle && <div className="isa-eq-head__sub">{subtitle}</div>}
    </div>
    {state && <div className={`isa-eq-head__state isa-eq-head__state--${state.tone}`}>{state.label}</div>}
    {right}
  </div>
);

// =====================================================================
// AlertList — lista densa estilo POC
// =====================================================================
export interface AlertItem {
  time: string;
  sev: "ok" | "warn" | "bad" | "off";
  msg: React.ReactNode;
  ctx?: React.ReactNode;
}
export const AlertList: React.FC<{ items: AlertItem[]; emptyMsg?: string }> = ({ items, emptyMsg }) => {
  if (!items.length) {
    return <p style={{ color: "var(--isa-text-muted)", fontSize: "var(--isa-fs-body)", padding: "8px 0", margin: 0 }}>
      {emptyMsg || "Sem alertas ativos."}
    </p>;
  }
  return (
    <ul className="isa-alerts">
      {items.map((a, i) => (
        <li key={i}>
          <span className="isa-alerts__time">{a.time}</span>
          <span className="isa-alerts__sev"><StatusDot tone={a.sev} /></span>
          <div style={{ flex: 1 }}>
            <div className="isa-alerts__msg">{a.msg}</div>
            {a.ctx && <div className="isa-alerts__ctx">{a.ctx}</div>}
          </div>
        </li>
      ))}
    </ul>
  );
};

// =====================================================================
// AreaCard (drill-down) — estilo POC `.area-card`
// =====================================================================
export const AreaCard: React.FC<{
  name: string;
  sub: string;
  meta: Array<{ value: React.ReactNode; label: string }>;
  status?: "ok" | "warn" | "bad";
  onClick?: () => void;
  href?: string;          // link interno
  spark?: number[];
}> = ({ name, sub, meta, status, onClick, href, spark }) => {
  const ref = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => {
    if (!spark || !ref.current) return;
    let chart: any = null;
    let cancelled = false;
    (async () => {
      const Chart = (await import("chart.js/auto")).default;
      if (cancelled || !ref.current) return;
      const c = status === "ok" ? "#2d8659" : status === "warn" ? "#c9932d" : status === "bad" ? "#b53a2b" : "#3f5b7c";
      chart = new Chart(ref.current, {
        type: "line",
        data: { labels: spark.map((_, i) => i), datasets: [{
          data: spark, borderColor: c, borderWidth: 1.5, pointRadius: 0,
          tension: .3, fill: true, backgroundColor: c + "18",
        }]},
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { enabled: false } },
          scales: { x: { display: false }, y: { display: false } },
          animation: false,
        },
      });
    })();
    return () => { cancelled = true; if (chart) chart.destroy(); };
  }, [spark, status]);

  const inner = (
    <>
      <div className="isa-area-card__head">
        <div>
          <div className="isa-area-card__name">{name}</div>
          <div className="isa-area-card__sub">{sub}</div>
        </div>
        {status && <Tag tone={status}>{status.toUpperCase()}</Tag>}
      </div>
      <div className="isa-area-card__meta">
        {meta.map((m, i) => (<span key={i}><b>{m.value}</b>{m.label}</span>))}
      </div>
      {spark && <div className="isa-area-card__spark"><canvas ref={ref} /></div>}
    </>
  );

  if (href) return <a href={href} className="isa-area-card">{inner}</a>;
  return <div className="isa-area-card" role={onClick ? "button" : undefined} onClick={onClick} tabIndex={onClick ? 0 : undefined}>{inner}</div>;
};

// =====================================================================
// Tabs — controle simples para Home/Analytics/Equipment/Losses
// =====================================================================
export interface Tab { id: string; label: string }
export const Tabs: React.FC<{ tabs: Tab[]; active: string; onChange: (id: string) => void }> = ({ tabs, active, onChange }) => (
  <div className="isa-tabs" role="tablist">
    {tabs.map(t => (
      <button
        key={t.id}
        role="tab"
        type="button"
        aria-selected={active === t.id}
        className={`isa-tab ${active === t.id ? "isa-tab--active" : ""}`}
        onClick={() => onChange(t.id)}
      >
        {t.label}
      </button>
    ))}
  </div>
);

// =====================================================================
// Topbar (breadcrumb + actions)
// =====================================================================
export const Topbar: React.FC<{
  breadcrumb: React.ReactNode;
  meta?: React.ReactNode;
  actions?: React.ReactNode;
}> = ({ breadcrumb, meta, actions }) => (
  <div className="isa-topbar">
    <div className="isa-breadcrumb">{breadcrumb}</div>
    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
      {meta && <span style={{ fontSize: "var(--isa-fs-meta)", color: "var(--isa-text-muted)" }}>{meta}</span>}
      {actions}
    </div>
  </div>
);
