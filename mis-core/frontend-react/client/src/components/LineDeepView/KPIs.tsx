import React from 'react';
import { AlertTriangle, TrendingUp, TrendingDown } from 'lucide-react';

const ISA = {
  bg:      '#ffffff',
  bgMuted: '#f4f5f7',
  border:  '#d7dbe0',
  text:    '#2c3138',
  muted:   '#657384',
  weak:    '#9ba3ad',
  accent:  '#3f5b7c',
  ok:      '#2d8659',  okBg:   '#e3efe7',
  warn:    '#c9932d',  warnBg: '#f4e8cf',
  bad:     '#b53a2b',  badBg:  '#f4dad6',
} as const;

function kpiColor(v: number): string {
  if (v >= 85) return ISA.ok;
  if (v >= 70) return ISA.warn;
  return ISA.bad;
}

interface KPIsProps {
  availability: number;
  performance: number;
  quality: number;
  bottleneck: { name: string; oee: number };
  ritmoAtual: number;
  ritmoNecessario: number;
  desvioProjetado: number;
  equipamentos?: Array<{ codigo: string; nome: string }>;
}

const KPIs: React.FC<KPIsProps> = ({
  availability, performance, quality, bottleneck,
  ritmoAtual, ritmoNecessario, desvioProjetado, equipamentos = [],
}) => {
  const friendlyName = equipamentos.find(eq => eq.codigo === bottleneck.name)?.nome || bottleneck.name;
  const displayName  = friendlyName !== bottleneck.name
    ? <>{friendlyName} <span style={{ fontWeight: 400, fontSize: 11, color: ISA.bad }}>({bottleneck.name})</span></>
    : bottleneck.name;

  const card: React.CSSProperties = {
    background: ISA.bg,
    border: `1px solid ${ISA.border}`,
    borderRadius: 6,
    padding: '16px 20px',
    marginBottom: 16,
  };

  const kpiCell = (label: string, value: number): React.CSSProperties => ({
    background: ISA.bgMuted,
    border: `1px solid ${ISA.border}`,
    borderRadius: 5,
    padding: '10px 12px',
  });

  return (
    <div style={card}>
      <div style={{ fontWeight: 600, fontSize: 14, color: ISA.text, marginBottom: 12 }}>KPIs da Linha</div>

      {/* A · P · Q grid — neutral cards; color only for the value itself */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 14 }}>
        {[
          { label: 'Disponibilidade', value: availability },
          { label: 'Performance',     value: performance  },
          { label: 'Qualidade',       value: quality      },
        ].map(({ label, value }) => (
          <div key={label} style={kpiCell(label, value)}>
            <div style={{ fontSize: 10, color: ISA.muted, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
              {label}
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, color: kpiColor(value), fontVariantNumeric: 'tabular-nums' }}>
              {value.toFixed(1)}%
            </div>
          </div>
        ))}
      </div>

      <div style={{ borderTop: `1px solid ${ISA.border}`, paddingTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        {/* Bottleneck — only place where bad/red is used continuously (real alarm) */}
        <div>
          <div style={{ fontSize: 11, color: ISA.muted, marginBottom: 6 }}>Gargalo Atual</div>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            background: ISA.badBg, border: `1px solid ${ISA.bad}`,
            borderRadius: 5, padding: '8px 10px', color: ISA.bad,
          }}>
            <AlertTriangle size={14} style={{ flexShrink: 0 }} />
            <span style={{ fontWeight: 600, fontSize: 12, flex: 1 }}>{displayName}</span>
            <span style={{ fontSize: 12, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
              {bottleneck.oee.toFixed(1)}%
            </span>
          </div>
        </div>

        {/* Ritmo / Desvio */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[
            { label: 'Ritmo Atual',     value: `${ritmoAtual.toFixed(1)} t/h`,     style: { color: ISA.text } },
            { label: 'Ritmo Necessário', value: `${ritmoNecessario.toFixed(1)} t/h`, style: { color: ISA.text } },
          ].map(({ label, value, style }) => (
            <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 12, color: ISA.muted }}>{label}</span>
              <span style={{ fontSize: 13, fontWeight: 600, fontVariantNumeric: 'tabular-nums', ...style }}>{value}</span>
            </div>
          ))}
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            borderTop: `1px solid ${ISA.border}`, paddingTop: 6,
          }}>
            <span style={{ fontSize: 12, color: ISA.muted }}>Desvio Projetado</span>
            <span style={{
              display: 'flex', alignItems: 'center', gap: 4, fontWeight: 700, fontSize: 13,
              fontVariantNumeric: 'tabular-nums',
              color: desvioProjetado >= 0 ? ISA.ok : ISA.bad,
            }}>
              {desvioProjetado < 0 ? <TrendingDown size={13} /> : <TrendingUp size={13} />}
              {desvioProjetado > 0 ? '+' : ''}{desvioProjetado.toFixed(1)} t
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default KPIs;
