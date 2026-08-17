import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, LabelList,
} from 'recharts';
import { Loader2 } from 'lucide-react';

// ISA-101: saturated color only on deviation/alarm; neutral for base/planned
const ISA = {
  border: '#d7dbe0', muted: '#657384', weak: '#9ba3ad', text: '#2c3138',
  bgMuted: '#f4f5f7',
  accent: '#3f5b7c',   // planned stops (neutral)
  ok:     '#2d8659',   // good production
  warn:   '#c9932d',   // performance loss
  bad:    '#b53a2b',   // unplanned loss (alarm)
  off:    '#9ba3ad',   // base time (neutral)
  qual:   '#657384',   // quality loss (muted — small contributor usually)
} as const;

const CHART_COLORS = [ISA.off, ISA.accent, ISA.bad, ISA.warn, ISA.qual, ISA.ok];

interface LossWaterfallProps { data: any; isLoading: boolean; }

const CustomTooltip = ({ active, payload, label, totalTime }: any) => {
  if (!active || !payload?.length) return null;
  const color = payload[0].payload.color;
  const val   = payload[0].value;
  return (
    <div style={{ background: '#fff', border: `1px solid #d7dbe0`, borderRadius: 6,
      padding: '8px 12px', fontSize: 12, boxShadow: '0 4px 12px rgba(0,0,0,.1)' }}>
      <div style={{ fontWeight: 600, color: '#2c3138', marginBottom: 4 }}>{label}</div>
      <div style={{ color, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{val} min</div>
      {totalTime > 0 && (
        <div style={{ color: '#9ba3ad', marginTop: 2 }}>
          {((val / totalTime) * 100).toFixed(1)}% do total
        </div>
      )}
    </div>
  );
};

const LossWaterfallChart: React.FC<LossWaterfallProps> = ({ data, isLoading }) => {
  if (isLoading || !data) {
    return (
      <div style={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: ISA.bgMuted, borderRadius: 6 }}>
        <Loader2 size={24} color={ISA.muted} className="animate-spin" />
      </div>
    );
  }

  const chartData = [
    { name: 'Tempo Total',  value: parseFloat((data.total_time        || 0).toFixed(1)), color: CHART_COLORS[0] },
    { name: 'Planejado',    value: parseFloat((data.planned_loss      || 0).toFixed(1)), color: CHART_COLORS[1] },
    { name: 'Não Planej.',  value: parseFloat((data.unplanned_loss    || 0).toFixed(1)), color: CHART_COLORS[2] },
    { name: 'Performance',  value: parseFloat((data.performance_loss  || 0).toFixed(1)), color: CHART_COLORS[3] },
    { name: 'Qualidade',    value: parseFloat((data.quality_loss      || 0).toFixed(1)), color: CHART_COLORS[4] },
    { name: 'Prod. Boa',    value: parseFloat((data.good_production   || 0).toFixed(1)), color: CHART_COLORS[5] },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 280 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: ISA.muted, textTransform: 'uppercase',
        letterSpacing: '0.07em', marginBottom: 10 }}>
        Cascata de Perdas (min)
      </div>
      <div style={{ flex: 1 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 20, right: 16, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={ISA.border} vertical={false} />
            <XAxis dataKey="name" tick={{ fill: ISA.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: ISA.muted, fontSize: 11 }} axisLine={false} tickLine={false} width={36} />
            <Tooltip content={<CustomTooltip totalTime={data.total_time} />}
              cursor={{ fill: ISA.bgMuted }} />
            <Bar dataKey="value" radius={[3, 3, 0, 0]}>
              {chartData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              <LabelList dataKey="value" position="top" fill={ISA.muted} fontSize={11}
                formatter={(v: number) => v > 0 ? v : ''} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default LossWaterfallChart;
