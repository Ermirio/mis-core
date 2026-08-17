/**
 * DateRangePicker — seletor de janela temporal estilo Grafana.
 *
 * POR QUE ESTE COMPONENTE EXISTE:
 *   O Analytics legado só oferece "Últimas 24h / 7d / 30d" (fixo). Para um
 *   engenheiro de processo investigando causa-raiz, isso é limitante — ele
 *   precisa "recortar o turno da noite de 12/04" ou "olhar de 06:00 a 08:00"
 *   quando o RE aconteceu. Este componente resolve isso.
 *
 * SAÍDA: objeto `TimeRange` no formato que o FastAPI v2 consome (ver
 *        backend-fastapi/app/schemas/time_range.py).
 *
 *   modo "quick"   -> { last: "24h" }                        (shorthand)
 *   modo "custom"  -> { start: "2026-...", end: "2026-..." } (ISO-8601 UTC)
 *
 * DESIGN:
 *   - Quick-ranges no topo (cliques = um passo, o caso mais comum).
 *   - Custom abre um pequeno painel inline (sem modal — desloca menos foco).
 *   - Exibe a duração efetiva ("24h 00m") pra confirmar a leitura.
 */

import React, { useMemo, useState } from "react";
import type { TimeRange } from "@/api/v2";

// -----------------------------------------------------------------------------
// Props
// -----------------------------------------------------------------------------
interface Props {
  value: TimeRange;
  onChange: (tr: TimeRange) => void;
  /** Se verdadeiro, mostra label "Intervalo:" à esquerda. */
  showLabel?: boolean;
  className?: string;
}

// -----------------------------------------------------------------------------
// Quick ranges — atalhos mais pedidos em chão de fábrica
// -----------------------------------------------------------------------------
const QUICK: Array<{ label: string; value: string }> = [
  { label: "15m",  value: "15m" },
  { label: "1h",   value: "1h"  },
  { label: "3h",   value: "3h"  },
  { label: "8h",   value: "8h"  },   // 1 turno
  { label: "24h",  value: "24h" },   // 1 dia
  { label: "7d",   value: "7d"  },
  { label: "30d",  value: "30d" },
];

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------
function toLocalInput(iso?: string): string {
  // input type=datetime-local espera "YYYY-MM-DDTHH:mm" (sem TZ)
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const tz = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - tz).toISOString().slice(0, 16);
}

function fromLocalInput(v: string): string | undefined {
  // converte "2026-04-23T08:00" (local) -> ISO UTC
  if (!v) return undefined;
  const d = new Date(v);
  return isNaN(d.getTime()) ? undefined : d.toISOString();
}

function formatDuration(tr: TimeRange): string {
  if (tr.last) return tr.last;
  if (!tr.start || !tr.end) return "—";
  const d = Math.max(0, (new Date(tr.end).getTime() - new Date(tr.start).getTime()) / 1000);
  if (d < 60) return `${Math.round(d)}s`;
  if (d < 3600) return `${Math.floor(d / 60)}m`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ${Math.floor((d % 3600) / 60).toString().padStart(2, "0")}m`;
  return `${Math.floor(d / 86400)}d ${Math.floor((d % 86400) / 3600)}h`;
}

// -----------------------------------------------------------------------------
// Componente
// -----------------------------------------------------------------------------
const DateRangePicker: React.FC<Props> = ({ value, onChange, showLabel = true, className = "" }) => {
  const [custom, setCustom] = useState(false);

  const isQuick = !!value.last;
  const activeQuick = isQuick ? value.last : null;
  const duration = useMemo(() => formatDuration(value), [value]);

  const handleQuick = (last: string) => {
    setCustom(false);
    onChange({ last, granularity: value.granularity ?? "auto" });
  };

  const handleCustomStart = (v: string) => {
    const start = fromLocalInput(v);
    onChange({ start, end: value.end ?? new Date().toISOString(), granularity: value.granularity ?? "auto" });
  };
  const handleCustomEnd = (v: string) => {
    const end = fromLocalInput(v) ?? new Date().toISOString();
    onChange({ start: value.start ?? new Date(Date.now() - 3600_000).toISOString(), end, granularity: value.granularity ?? "auto" });
  };

  return (
    <div className={`drp ${className}`}>
      {showLabel && <span className="drp__label">Intervalo:</span>}

      <div className="drp__quick" role="group" aria-label="Intervalos rápidos">
        {QUICK.map((q) => (
          <button
            key={q.value}
            type="button"
            className={`drp__chip ${activeQuick === q.value ? "drp__chip--active" : ""}`}
            onClick={() => handleQuick(q.value)}
            title={`Últimos ${q.label}`}
          >
            {q.label}
          </button>
        ))}
        <button
          type="button"
          className={`drp__chip ${custom ? "drp__chip--active" : ""}`}
          onClick={() => setCustom((s) => !s)}
          title="Definir intervalo customizado"
        >
          Custom
        </button>
      </div>

      <span className="drp__duration" aria-live="polite">
        <strong>{duration}</strong>
      </span>

      {custom && (
        <div className="drp__custom" role="group" aria-label="Intervalo customizado">
          <label>
            <span>De</span>
            <input
              type="datetime-local"
              value={toLocalInput(value.start)}
              onChange={(e) => handleCustomStart(e.target.value)}
            />
          </label>
          <label>
            <span>Até</span>
            <input
              type="datetime-local"
              value={toLocalInput(value.end)}
              onChange={(e) => handleCustomEnd(e.target.value)}
            />
          </label>
        </div>
      )}

      <style>{`
        .drp { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 13px; }
        .drp__label { color: #8794a3; font-weight: 500; }
        .drp__quick { display: flex; gap: 4px; flex-wrap: wrap; }
        .drp__chip {
          border: 1px solid #dfe4eb;
          background: #fff;
          color: #344054;
          padding: 4px 10px;
          border-radius: 6px;
          cursor: pointer;
          font-size: 12px;
          line-height: 1.4;
          transition: background 80ms ease, color 80ms ease, border-color 80ms ease;
        }
        .drp__chip:hover { background: #eef2f7; }
        .drp__chip--active {
          background: #eaf2fb;
          border-color: #4a90e2;
          color: #1a4478;
          font-weight: 600;
        }
        .drp__duration {
          color: #667085;
          font-variant-numeric: tabular-nums;
          margin-left: auto;
          font-size: 12px;
        }
        .drp__custom {
          display: flex;
          gap: 8px;
          width: 100%;
          padding-top: 4px;
          flex-wrap: wrap;
        }
        .drp__custom label {
          display: flex;
          flex-direction: column;
          font-size: 11px;
          color: #667085;
          gap: 2px;
        }
        .drp__custom input {
          font: inherit;
          padding: 4px 6px;
          border: 1px solid #dfe4eb;
          border-radius: 6px;
          background: #fff;
        }
      `}</style>
    </div>
  );
};

export default DateRangePicker;
