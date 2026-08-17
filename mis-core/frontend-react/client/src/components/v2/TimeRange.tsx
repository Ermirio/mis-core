/**
 * TimeRangePicker — Range datetime estilo Grafana.
 *
 * Encapsula a interação que o diagnóstico apontou como faltante:
 *   - "Os filtros de tempos de analytics precisam ser baseados em data hora
 *      e não somente tempos fixos, bem semelhante ao como o grafana trabalha."
 *
 * Convenções de uso:
 *   - Mantemos quick-chips (15m, 1h, 8h, 24h, 7d) que substituem os tempos
 *     fixos antigos, mas o "from" e "to" são sempre os campos canônicos
 *     que vão pro backend (FastAPI v2 espera ISO 8601 UTC).
 *   - O componente NÃO faz fetch sozinho; emite onChange({ from, to, granularity })
 *     pra cada interação. Isso permite acoplar com qualquer page que tenha um
 *     useEffect dependente do range.
 */
import React from "react";

export interface TimeRange {
  from: Date;
  to: Date;
  granularity: "auto" | "1m" | "5m" | "10m" | "15m" | "30m" | "1h" | "1d";
}

interface Props {
  value: TimeRange;
  onChange: (r: TimeRange) => void;
  /** Mostra os switches "Ignorar OFF" e "Delta em contadores" */
  showAnalyticsSwitches?: boolean;
  ignoreOff?: boolean;
  delta?: boolean;
  onIgnoreOffChange?: (v: boolean) => void;
  onDeltaChange?: (v: boolean) => void;
  /** Botão de Refresh à direita */
  onRefresh?: () => void;
  loading?: boolean;
  extraRight?: React.ReactNode;
}

const QUICK = [
  { label: "15 min", h: 0.25 },
  { label: "1 h",    h: 1 },
  { label: "8 h",    h: 8 },
  { label: "24 h",   h: 24 },
  { label: "7 d",    h: 168 },
] as const;

function toLocalInputValue(d: Date): string {
  const tzOffset = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - tzOffset).toISOString().slice(0, 16);
}

export const TimeRangePicker: React.FC<Props> = ({
  value, onChange,
  showAnalyticsSwitches = false,
  ignoreOff = true, delta = true,
  onIgnoreOffChange, onDeltaChange,
  onRefresh, loading,
  extraRight,
}) => {
  const setQuick = (hours: number) => {
    const to = new Date();
    const from = new Date(to.getTime() - hours * 3600 * 1000);
    onChange({ ...value, from, to });
  };

  const isActiveChip = (hours: number) => {
    const span = (value.to.getTime() - value.from.getTime()) / 3600000;
    return Math.abs(span - hours) < 0.05;
  };

  return (
    <div className="isa-toolbar" role="toolbar" aria-label="Janela temporal">
      <label htmlFor="dtFrom">De</label>
      <input
        id="dtFrom"
        type="datetime-local"
        value={toLocalInputValue(value.from)}
        onChange={e => onChange({ ...value, from: new Date(e.target.value) })}
      />
      <label htmlFor="dtTo">Até</label>
      <input
        id="dtTo"
        type="datetime-local"
        value={toLocalInputValue(value.to)}
        onChange={e => onChange({ ...value, to: new Date(e.target.value) })}
      />
      <label htmlFor="gran">Granularidade</label>
      <select
        id="gran"
        value={value.granularity}
        onChange={e => onChange({ ...value, granularity: e.target.value as TimeRange["granularity"] })}
      >
        <option value="auto">auto</option>
        <option value="1m">1m</option>
        <option value="5m">5m</option>
        <option value="10m">10m</option>
        <option value="15m">15m</option>
        <option value="30m">30m</option>
        <option value="1h">1h</option>
        <option value="1d">1d</option>
      </select>

      <div className="isa-chips" style={{ marginLeft: 4 }}>
        {QUICK.map(q => (
          <button
            key={q.label}
            type="button"
            className={`isa-chip ${isActiveChip(q.h) ? "isa-chip--active" : ""}`}
            onClick={() => setQuick(q.h)}
          >
            {q.label}
          </button>
        ))}
      </div>

      {showAnalyticsSwitches && (
        <div className="isa-switches">
          <label className="isa-switch">
            <input
              type="checkbox"
              checked={ignoreOff}
              onChange={e => onIgnoreOffChange?.(e.target.checked)}
            />
            Ignorar OFF
          </label>
          <label className="isa-switch">
            <input
              type="checkbox"
              checked={delta}
              onChange={e => onDeltaChange?.(e.target.checked)}
            />
            Delta em contadores
          </label>
        </div>
      )}

      {(onRefresh || extraRight) && (
        <div style={{ marginLeft: showAnalyticsSwitches ? 8 : "auto", display: "flex", gap: 8 }}>
          {extraRight}
          {onRefresh && (
            <button
              type="button"
              className="ghost"
              onClick={onRefresh}
              disabled={loading}
              aria-label="Atualizar"
            >
              {loading ? "Atualizando…" : "↻ Atualizar"}
            </button>
          )}
        </div>
      )}
    </div>
  );
};

/** Helper: cria um range default (últimas 24h) */
export function defaultRange(): TimeRange {
  const to = new Date();
  const from = new Date(to.getTime() - 24 * 3600 * 1000);
  return { from, to, granularity: "15m" };
}
