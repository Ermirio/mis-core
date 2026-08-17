import React, { useState, useEffect } from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { AlertCircle, Trash2 } from 'lucide-react';
import { DJANGO_API_URL } from '@/config/api';
import LossFilterBar from './LossFilterBar';

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

// ISA-101 state color map — saturated only where it matters operationally
const STATE_COLORS: Record<string, string> = {
  'Produzindo':            ISA.ok,
  'Parado/Desligado':      ISA.bad,
  'Falha/Quebra':          ISA.bad,
  'Aguardando':            ISA.warn,
  'Bloqueado':             ISA.warn,
  'Setup':                 ISA.accent,
  'Manutenção':            ISA.accent,
  'Teste/Engenharia':      '#5a8fa3',
  'Falta Material':        ISA.warn,
  'Partindo':              ISA.ok,
  'Aguardando Condições':  ISA.warn,
  'Parando':               ISA.warn,
  'Outro':                 ISA.weak,
};

interface AnalysisData {
  periodo: string;
  total_waste: number;
  unit?: string;
  by_equipment: { name: string; value: number; share: number }[];
  by_state:     { id: string; label: string; value: number; share: number }[];
}

interface LossWasteProps { lineId?: string; mode?: 'line' | 'factory'; }

const CustomTooltip = ({ active, payload, unit }: any) => {
  if (!active || !payload?.length) return null;
  const fmt = (v: number) => unit === 'ton' ? `${v.toFixed(3)} t` : `${Math.round(v)} un`;
  return (
    <div style={{ background: ISA.bg, border: `1px solid ${ISA.border}`, borderRadius: 6,
      padding: '8px 12px', fontSize: 12, boxShadow: '0 4px 12px rgba(0,0,0,.1)' }}>
      <div style={{ fontWeight: 600, color: ISA.text }}>{payload[0].name}</div>
      <div style={{ color: payload[0].payload.fill, fontWeight: 700, marginTop: 2 }}>{fmt(payload[0].value)}</div>
    </div>
  );
};

export function LossWasteAnalysis({ lineId, mode = 'line' }: LossWasteProps) {
  const [periodo, setPeriodo] = useState('TURNO');
  const [data, setData]       = useState<AnalysisData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const fetchData = async (bg = false) => {
    if (!bg) setLoading(true);
    setError(null);
    try {
      const url = mode === 'factory'
        ? `${DJANGO_API_URL}/fabrica/waste-analysis/?periodo=${periodo}`
        : lineId
          ? `${DJANGO_API_URL}/linhas/${lineId}/waste-analysis/?periodo=${periodo}`
          : null;
      if (!url) return;
      const res = await fetch(url);
      if (!res.ok) throw new Error('Falha ao carregar dados de refugo');
      setData(await res.json());
    } catch (err: any) {
      if (!bg) setError(err.message);
    } finally {
      if (!bg) setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const iv = setInterval(() => fetchData(true), 30000);
    return () => clearInterval(iv);
  }, [lineId, mode, periodo]);

  const fmt = (v: number) => data?.unit === 'ton' ? `${v.toFixed(3)} t` : `${Math.round(v)} un`;

  const title = mode === 'factory' ? 'Análise Global de Perdas (Toneladas)' : 'Análise de Descarte';

  if (error) {
    return (
      <div style={{ background: ISA.bg, border: `1px solid ${ISA.border}`, borderRadius: 6,
        padding: 24, textAlign: 'center' }}>
        <AlertCircle size={28} color={ISA.bad} style={{ margin: '0 auto 8px' }} />
        <div style={{ color: ISA.bad, fontSize: 13, marginBottom: 12 }}>{error}</div>
        <button onClick={() => fetchData()} style={{
          padding: '5px 14px', borderRadius: 5, border: `1px solid ${ISA.border}`,
          background: ISA.bgMuted, color: ISA.muted, fontSize: 12, cursor: 'pointer',
        }}>Tentar Novamente</button>
      </div>
    );
  }

  return (
    <div style={{ background: ISA.bg, border: `1px solid ${ISA.border}`, borderRadius: 6, overflow: 'hidden' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 16px', borderBottom: `1px solid ${ISA.border}`, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ width: 32, height: 32, borderRadius: 6, background: ISA.badBg,
            border: `1px solid ${ISA.bad}30`, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
            <Trash2 size={14} color={ISA.bad} />
          </span>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14, color: ISA.text }}>{title}</div>
            <div style={{ fontSize: 11, color: ISA.muted, marginTop: 1 }}>
              Refugo acumulado por equipamento e correlação de estados
            </div>
          </div>
        </div>
        <LossFilterBar periodo={periodo} setPeriodo={setPeriodo} isLoading={loading}
          onRefresh={() => fetchData()} />
      </div>

      {/* Body */}
      <div style={{ padding: 16 }}>
        {loading && !data ? (
          <div style={{ height: 250, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ width: 28, height: 28, border: `3px solid ${ISA.border}`,
              borderTopColor: ISA.bad, borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
          </div>
        ) : !data ? (
          <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 13, color: ISA.muted }}>
            Nenhum dado disponível
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>

            {/* LEFT: Donut — Origem por Estado */}
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: ISA.muted, textTransform: 'uppercase',
                letterSpacing: '0.07em', marginBottom: 10 }}>
                Origem do Descarte por Estado
              </div>
              <div style={{ height: 240, position: 'relative' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={data.by_state}
                      dataKey="value"
                      nameKey="label"
                      cx="40%" cy="50%"
                      innerRadius={55} outerRadius={85}
                      paddingAngle={2}
                      stroke="none"
                      label={({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
                        if (percent < 0.05) return null;
                        const R = Math.PI / 180;
                        const r = innerRadius + (outerRadius - innerRadius) * 0.5;
                        const x = cx + r * Math.cos(-midAngle * R);
                        const y = cy + r * Math.sin(-midAngle * R);
                        return (
                          <text x={x} y={y} fill="#fff" textAnchor="middle"
                            dominantBaseline="central" fontSize={10} fontWeight={700}>
                            {`${(percent * 100).toFixed(0)}%`}
                          </text>
                        );
                      }}
                    >
                      {data.by_state.map((entry, i) => (
                        <Cell key={i} fill={STATE_COLORS[entry.label] || ISA.weak} />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip unit={data.unit} />} />
                    <Legend
                      layout="vertical" verticalAlign="middle" align="right"
                      iconType="circle" iconSize={7}
                      wrapperStyle={{ fontSize: 11, color: ISA.muted }}
                    />
                  </PieChart>
                </ResponsiveContainer>

                {/* Centro do donut */}
                <div style={{ position: 'absolute', top: '50%', left: '40%',
                  transform: 'translate(-50%, -50%)', textAlign: 'center', pointerEvents: 'none' }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: ISA.bad,
                    fontVariantNumeric: 'tabular-nums' }}>
                    {data.total_waste.toFixed(data.unit === 'ton' ? 3 : 0)}
                  </div>
                  <div style={{ fontSize: 10, color: ISA.muted }}>
                    {data.unit === 'ton' ? 'Toneladas' : 'Unidades'}
                  </div>
                </div>
              </div>
            </div>

            {/* RIGHT: Ranking de Equipamentos */}
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: ISA.muted, textTransform: 'uppercase',
                letterSpacing: '0.07em', marginBottom: 10 }}>
                Top Geradores de Refugo
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6,
                maxHeight: 230, overflowY: 'auto', paddingRight: 4 }}>
                {data.by_equipment.map((item, idx) => (
                  <div key={idx} style={{ background: ISA.bgMuted, border: `1px solid ${ISA.border}`,
                    borderRadius: 5, padding: '7px 10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between',
                      marginBottom: 5, alignItems: 'center' }}>
                      <span style={{ fontSize: 12, fontWeight: 500, color: ISA.text,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        maxWidth: '65%' }}>
                        {item.name}
                      </span>
                      <span style={{ fontSize: 12, fontWeight: 700, color: ISA.bad,
                        fontVariantNumeric: 'tabular-nums', flexShrink: 0 }}>
                        {fmt(item.value)}
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ flex: 1, height: 4, background: ISA.border, borderRadius: 99, overflow: 'hidden' }}>
                        <div style={{ height: '100%', borderRadius: 99, background: ISA.bad,
                          width: `${item.share}%`, opacity: 0.7 + (item.share / 100) * 0.3 }} />
                      </div>
                      <span style={{ fontSize: 10, color: ISA.muted, fontVariantNumeric: 'tabular-nums',
                        minWidth: 34, textAlign: 'right' }}>
                        {item.share.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        )}
      </div>
    </div>
  );
}
