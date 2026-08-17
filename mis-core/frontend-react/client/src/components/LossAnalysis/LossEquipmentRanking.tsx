import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts';
import { Loader2 } from 'lucide-react';

const ISA = {
  bg:     '#ffffff', bgMuted: '#f4f5f7', border: '#d7dbe0',
  text:   '#2c3138', muted:   '#657384',
  accent: '#3f5b7c',  // planned
  warn:   '#c9932d',  // performance
  bad:    '#b53a2b',  // unplanned
} as const;

interface LossEquipmentRankingProps { data: any[]; isLoading: boolean; }

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const item = payload[0].payload;
  return (
    <div style={{ background: '#fff', border: `1px solid ${ISA.border}`, borderRadius: 6,
      padding: '8px 12px', fontSize: 12, boxShadow: '0 4px 12px rgba(0,0,0,.1)' }}>
      <div style={{ fontWeight: 600, color: ISA.text, marginBottom: 6 }}>{item.nome}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <span style={{ color: ISA.bad  }}>Não Planej.: {(item.breakdown?.unplanned   || 0).toFixed(1)} min</span>
        <span style={{ color: ISA.warn }}>Performance: {(item.breakdown?.performance || 0).toFixed(1)} min</span>
        <span style={{ color: ISA.accent }}>Planejado: {(item.breakdown?.planned     || 0).toFixed(1)} min</span>
        <div style={{ borderTop: `1px solid ${ISA.border}`, paddingTop: 4, marginTop: 2 }}>
          <span style={{ fontWeight: 700, color: ISA.text }}>Total: {(item.total_loss_min || 0).toFixed(1)} min</span>
        </div>
      </div>
    </div>
  );
};

const LossEquipmentRanking: React.FC<LossEquipmentRankingProps> = ({ data, isLoading }) => {
  if (isLoading) {
    return (
      <div style={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: ISA.bgMuted, borderRadius: 6 }}>
        <Loader2 size={24} color={ISA.muted} className="animate-spin" />
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div style={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: ISA.bgMuted, borderRadius: 6, fontSize: 13, color: ISA.muted }}>
        Nenhuma perda registrada no período.
      </div>
    );
  }

  const chartData = [...data]
    .sort((a, b) => b.total_loss_min - a.total_loss_min)
    .slice(0, 10);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 280 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: ISA.muted, textTransform: 'uppercase',
        letterSpacing: '0.07em', marginBottom: 10 }}>
        Top Equipamentos — Perdas
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 8 }}>
        {[['Não Plan.', ISA.bad], ['Performance', ISA.warn], ['Planejado', ISA.accent]].map(([l, c]) => (
          <span key={l} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: ISA.muted }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: c as string, flexShrink: 0 }} />
            {l}
          </span>
        ))}
      </div>

      <div style={{ flex: 1 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart layout="vertical" data={chartData}
            margin={{ top: 4, right: 24, left: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={ISA.border} horizontal={false} vertical={true} />
            <XAxis type="number" tick={{ fill: ISA.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis
              dataKey="nome" type="category"
              tick={{ fill: ISA.text, fontSize: 11 }} width={90} axisLine={false} tickLine={false}
              tickFormatter={v => v.length > 14 ? v.slice(0, 11) + '…' : v}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: ISA.bgMuted }} />
            <Bar dataKey="breakdown.unplanned"   stackId="a" fill={ISA.bad}    name="Não Planejado" radius={[0,0,0,0]} />
            <Bar dataKey="breakdown.performance" stackId="a" fill={ISA.warn}   name="Performance"  />
            <Bar dataKey="breakdown.planned"     stackId="a" fill={ISA.accent} name="Planejado"    radius={[0,3,3,0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default LossEquipmentRanking;
