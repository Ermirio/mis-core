import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  LineChart, Line, BarChart, Bar,
  ResponsiveContainer, CartesianGrid, XAxis, YAxis,
  Tooltip, Legend, ReferenceLine,
} from 'recharts';
import { Loader2, RefreshCw, AlertCircle } from 'lucide-react';
import { FLASK_API_URL } from '@/config/api';

/* ========================= ISA-101 palette ========================= */
const C = {
  bg:        '#f4f5f7',
  bgPanel:   '#ffffff',
  bgMuted:   '#e9ecef',
  border:    '#d7dbe0',
  text:      '#2c3138',
  textMuted: '#657384',
  textWeak:  '#9ba3ad',
  accent:    '#3f5b7c',
  ok:        '#2d8659',
  warn:      '#c9932d',
  bad:       '#b53a2b',
  grid:      '#e1e4e8',
} as const;

/* ========================= Available variables ========================= */
interface VarDef { tag_influx: string; label: string; unit: string; lsl?: number; usl?: number; }

const AVAILABLE_VARS: VarDef[] = [
  { tag_influx: 'velocidade_atual',       label: 'Velocidade',      unit: 'u/min' },
  { tag_influx: 'oee_realtime',           label: 'OEE',             unit: '%' },
  { tag_influx: 'availability_realtime',  label: 'Disponibilidade', unit: '%' },
  { tag_influx: 'performance_realtime',   label: 'Performance',     unit: '%' },
  { tag_influx: 'quality_realtime',       label: 'Qualidade',       unit: '%' },
  { tag_influx: 'refugo_op_acumulado',    label: 'Refugo (Acum.)',  unit: 'un' },
  { tag_influx: 'temperatura',            label: 'Temperatura',     unit: '°C' },
  { tag_influx: 'pressao',                label: 'Pressão',         unit: 'bar' },
];

/* ========================= Time chips ========================= */
const CHIPS = [
  { label: '15 min', offsetMs: 15 * 60 * 1000,           gran: '1m'  },
  { label: '1 h',    offsetMs:      3600 * 1000,          gran: '5m'  },
  { label: '8 h',    offsetMs:  8 * 3600 * 1000,          gran: '10m' },
  { label: '24 h',   offsetMs: 24 * 3600 * 1000,          gran: '30m' },
  { label: '7 d',    offsetMs:  7 * 24 * 3600 * 1000,     gran: '1h'  },
];

/* ========================= Types ========================= */
interface TsData {
  timestamps: string[];
  values:     (number | null)[];
  stats: {
    mean: number; std: number;
    ucl: number;  lcl: number;
    lsl?: number | null; usl?: number | null; nominal?: number | null;
  };
}

interface AnalyticsTabProps { linhaId?: string; linhaNome?: string; }

/* ========================= Sub-components ========================= */
const ChartCard: React.FC<{ title: string; desc?: string; height?: number; children: React.ReactNode }> =
  ({ title, desc, height = 280, children }) => (
    <div style={{ background: C.bgPanel, border: `1px solid ${C.border}`, borderRadius: 6, padding: 12, display: 'flex', flexDirection: 'column' }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: C.text, marginBottom: desc ? 2 : 8 }}>{title}</div>
      {desc && <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 8 }}>{desc}</div>}
      <div style={{ height }}>{children}</div>
    </div>
  );

const Chip: React.FC<{ label: string; active: boolean; onClick: () => void }> = ({ label, active, onClick }) => (
  <button type="button" onClick={onClick} style={{
    border: `1px solid ${active ? C.accent : C.border}`,
    borderRadius: 20, padding: '3px 10px', fontSize: 11, cursor: 'pointer',
    background: active ? C.accent : C.bgPanel, color: active ? '#fff' : C.text,
    transition: 'all 0.15s',
  }}>{label}</button>
);

const Spinner = () => (
  <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <Loader2 size={24} color={C.textMuted} className="animate-spin" />
  </div>
);

/* ========================= Helpers ========================= */
const fmt16 = (d: Date) => d.toISOString().slice(0, 16);

function buildHistogram(values: (number | null)[]): { x: string; freq: number }[] {
  const valid = values.filter((v): v is number => v != null && !isNaN(v) && v > 0);
  if (valid.length < 4) return [];
  const mn = Math.min(...valid), mx = Math.max(...valid);
  if (mx === mn) return [{ x: mn.toFixed(2), freq: valid.length }];
  const bins = Math.min(16, Math.max(5, Math.ceil(Math.sqrt(valid.length))));
  const step = (mx - mn) / bins;
  const counts = new Array(bins).fill(0);
  valid.forEach(v => {
    let b = Math.floor((v - mn) / step);
    if (b >= bins) b = bins - 1;
    counts[b]++;
  });
  return counts.map((freq, i) => ({ x: (mn + i * step).toFixed(2), freq }));
}

function buildBoxplot(timestamps: string[], values: (number | null)[]): { turno: string; q1: number; q2: number; q3: number }[] {
  const byShift: Record<string, number[]> = { T1: [], T2: [], T3: [] };
  timestamps.forEach((ts, i) => {
    const v = values[i];
    if (v == null || isNaN(v) || v <= 0) return;
    const h = new Date(ts).getHours();
    if (h >= 6 && h < 14)       byShift.T1.push(v);
    else if (h >= 14 && h < 22) byShift.T2.push(v);
    else                         byShift.T3.push(v);
  });
  return (['T1', 'T2', 'T3'] as const).map(turno => {
    const arr = byShift[turno];
    if (arr.length === 0) return { turno, q1: 0, q2: 0, q3: 0 };
    const s = [...arr].sort((a, b) => a - b);
    const q = (p: number) => s[Math.floor(p * s.length)] ?? 0;
    return { turno, q1: q(0.25), q2: q(0.5) - q(0.25), q3: q(0.75) - q(0.5) };
  });
}

/* ========================= Main component ========================= */
const AnalyticsTab: React.FC<AnalyticsTabProps> = ({ linhaId, linhaNome }) => {
  const initNow = new Date();
  const [dtFrom,      setDtFrom]      = useState(fmt16(new Date(+initNow - 24 * 3600000)));
  const [dtTo,        setDtTo]        = useState(fmt16(initNow));
  const [gran,        setGran]        = useState('30m');
  const [activeChip,  setActiveChip]  = useState('24 h');
  const [ignoreOff,   setIgnoreOff]   = useState(true);
  const [deltaMode,   setDeltaMode]   = useState(true);
  const [selectedVar, setSelectedVar] = useState('velocidade_atual');
  const [selectedEq,  setSelectedEq]  = useState('');

  const [equipmentList, setEquipmentList] = useState<string[]>([]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState<string | null>(null);
  const [tsData,   setTsData]   = useState<TsData | null>(null);

  /* Fetch equipment list */
  useEffect(() => {
    if (!linhaId) return;
    fetch(`${FLASK_API_URL}/linha/${encodeURIComponent(linhaId)}/status`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (!d?.equipamentos) return;
        const codes = (d.equipamentos as { nome: string }[]).map(e => e.nome).filter(Boolean);
        setEquipmentList(codes);
        setSelectedEq(prev => prev || codes[0] || '');
      })
      .catch(() => {});
  }, [linhaId]);

  /* Apply time chip */
  const applyChip = useCallback((chip: typeof CHIPS[0]) => {
    const to = new Date();
    setDtFrom(fmt16(new Date(+to - chip.offsetMs)));
    setDtTo(fmt16(to));
    setGran(chip.gran);
    setActiveChip(chip.label);
  }, []);

  /* Fetch timeseries from Flask analytics endpoint */
  const fetchData = useCallback(async () => {
    if (!selectedVar || !selectedEq) return;
    setLoading(true);
    setError(null);
    try {
      const varCfg = AVAILABLE_VARS.find(v => v.tag_influx === selectedVar);
      const alias  = varCfg?.label ?? selectedVar;
      const res = await fetch(`${FLASK_API_URL}/analyze/timeseries`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          variables: [{
            tag_influx:       selectedVar,
            equipamento_code: selectedEq,
            alias,
            lsl: varCfg?.lsl,
            usl: varCfg?.usl,
          }],
          start_time:  new Date(dtFrom).toISOString(),
          end_time:    new Date(dtTo).toISOString(),
          ignore_off:  ignoreOff,
          apply_delta: deltaMode,
          granularity: gran,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      const varData: TsData = json[alias] ?? (Object.values(json)[0] as TsData);
      if (!varData?.timestamps?.length) throw new Error('Sem dados para o período selecionado');
      setTsData(varData);
    } catch (err: any) {
      setError(err.message ?? 'Erro desconhecido');
      setTsData(null);
    } finally {
      setLoading(false);
    }
  }, [selectedVar, selectedEq, dtFrom, dtTo, gran, ignoreOff, deltaMode]);

  useEffect(() => { fetchData(); }, [fetchData]);

  /* Chart data — timestamps kept in original chronological order from InfluxDB */
  const chartData = useMemo(() => {
    if (!tsData?.timestamps?.length) return [];
    return tsData.timestamps.map((ts, i) => {
      const d    = new Date(ts);
      const date = d.toLocaleDateString ('pt-BR', { day: '2-digit', month: '2-digit' });
      const time = d.toLocaleTimeString ('pt-BR', { hour: '2-digit', minute: '2-digit' });
      return { ts, label: `${date} ${time}`, v: tsData.values[i] };
    });
  }, [tsData]);

  /* Sparse X-axis ticks — max 8 labels regardless of data volume */
  const xTicks = useMemo(() => {
    if (chartData.length < 2) return [];
    const step = Math.max(1, Math.floor(chartData.length / 8));
    return chartData.filter((_, i) => i % step === 0).map(d => d.label);
  }, [chartData]);

  const histData = useMemo(() => buildHistogram(tsData?.values ?? []), [tsData]);
  const boxData  = useMemo(() => tsData ? buildBoxplot(tsData.timestamps, tsData.values) : [], [tsData]);

  const statsItems = useMemo(() => {
    if (!tsData) return [];
    const valid = (tsData.values.filter((v): v is number => v != null && !isNaN(v))).sort((a, b) => a - b);
    if (!valid.length) return [];
    const q = (p: number) => valid[Math.floor(p * valid.length)] ?? 0;
    const { mean, std } = tsData.stats;
    return [
      { l: 'n (amostras)',  v: valid.length.toString() },
      { l: 'Média',         v: mean.toFixed(2) },
      { l: 'Desvio padrão', v: std.toFixed(2)  },
      { l: 'p50 (mediana)', v: q(0.50).toFixed(2) },
      { l: 'p90',           v: q(0.90).toFixed(2) },
      { l: 'p99',           v: q(0.99).toFixed(2) },
    ];
  }, [tsData]);

  const varCfg = AVAILABLE_VARS.find(v => v.tag_influx === selectedVar);
  const unit   = varCfg?.unit ?? '';
  const tick   = { fontSize: 10, fill: C.textMuted };

  const selectStyle: React.CSSProperties = {
    fontSize: 12, padding: '5px 8px', border: `1px solid ${C.border}`,
    borderRadius: 6, background: C.bgPanel, color: C.text,
  };

  return (
    <div style={{ fontFamily: 'system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif', fontSize: 14, color: C.text }}>

      {/* Toolbar */}
      <div style={{ background: C.bgPanel, border: `1px solid ${C.border}`, borderRadius: 6,
        padding: '10px 12px', display: 'flex', flexWrap: 'wrap', alignItems: 'center',
        gap: 10, marginBottom: 14 }}>

        {/* Variable selector */}
        <label style={{ fontSize: 11, color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Variável</label>
        <select value={selectedVar} onChange={e => setSelectedVar(e.target.value)} style={selectStyle}>
          {AVAILABLE_VARS.map(v => <option key={v.tag_influx} value={v.tag_influx}>{v.label}</option>)}
        </select>

        {/* Equipment selector */}
        <label style={{ fontSize: 11, color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Equipamento</label>
        {equipmentList.length > 0 ? (
          <select value={selectedEq} onChange={e => setSelectedEq(e.target.value)} style={selectStyle}>
            {equipmentList.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        ) : (
          <input value={selectedEq} onChange={e => setSelectedEq(e.target.value)}
            placeholder="Código (ex: E001)" style={{ ...selectStyle, width: 110 }} />
        )}

        {/* Date range */}
        <label style={{ fontSize: 11, color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.04em' }}>De</label>
        <input type="datetime-local" value={dtFrom} onChange={e => { setDtFrom(e.target.value); setActiveChip(''); }}
          style={selectStyle} />
        <label style={{ fontSize: 11, color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Até</label>
        <input type="datetime-local" value={dtTo} onChange={e => { setDtTo(e.target.value); setActiveChip(''); }}
          style={selectStyle} />

        {/* Granularity */}
        <select value={gran} onChange={e => setGran(e.target.value)} style={selectStyle}>
          {['auto', '1m', '5m', '10m', '30m', '1h', '1d'].map(g => <option key={g} value={g}>{g}</option>)}
        </select>

        {/* Quick chips */}
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {CHIPS.map(c => (
            <Chip key={c.label} label={c.label} active={activeChip === c.label} onClick={() => applyChip(c)} />
          ))}
        </div>

        {/* Toggles + refresh */}
        <div style={{ display: 'flex', gap: 14, marginLeft: 'auto', fontSize: 12, alignItems: 'center' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', userSelect: 'none' }}>
            <input type="checkbox" checked={ignoreOff} onChange={e => setIgnoreOff(e.target.checked)}
              style={{ accentColor: C.accent }} />
            Ignorar OFF
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', userSelect: 'none' }}>
            <input type="checkbox" checked={deltaMode} onChange={e => setDeltaMode(e.target.checked)}
              style={{ accentColor: C.accent }} />
            Delta (contadores)
          </label>
          <button type="button" onClick={fetchData} disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: 5, border: `1px solid ${C.border}`,
              borderRadius: 6, padding: '4px 10px', background: C.bgPanel, color: C.textMuted,
              fontSize: 12, cursor: loading ? 'default' : 'pointer' }}>
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            Atualizar
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
          background: '#fdf2f1', border: `1px solid ${C.bad}40`, borderRadius: 6,
          color: C.bad, fontSize: 13, marginBottom: 14 }}>
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* Main trend chart */}
      <ChartCard
        title={`${varCfg?.label ?? selectedVar}${selectedEq ? ` — ${selectedEq}` : ''}`}
        desc={linhaNome ? `Linha ${linhaNome} · ${unit} · ordem cronológica ↑` : `${unit} · ordem cronológica ↑`}
        height={300}
      >
        {loading && !tsData ? <Spinner /> : chartData.length === 0 ? (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 13, color: C.textMuted }}>Nenhum dado disponível</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
              <XAxis dataKey="label" tick={tick} ticks={xTicks} interval="preserveStartEnd" />
              <YAxis tick={tick} label={{ value: unit, angle: -90, position: 'insideLeft', ...tick }} />
              <Tooltip
                contentStyle={{ fontSize: 11, background: C.bgPanel, border: `1px solid ${C.border}` }}
                formatter={(v: any) => [`${typeof v === 'number' ? v.toFixed(2) : v} ${unit}`, varCfg?.label ?? selectedVar]}
                labelFormatter={(l: string) => `⏱ ${l}`}
              />
              {/* SPC control limits from API stats */}
              {tsData?.stats?.ucl != null && (
                <ReferenceLine y={tsData.stats.ucl} stroke={C.bad} strokeDasharray="4 4"
                  label={{ value: 'UCL', position: 'right', fontSize: 10, fill: C.bad }} />
              )}
              {tsData?.stats?.lcl != null && tsData.stats.lcl > 0 && (
                <ReferenceLine y={tsData.stats.lcl} stroke={C.warn} strokeDasharray="4 4"
                  label={{ value: 'LCL', position: 'right', fontSize: 10, fill: C.warn }} />
              )}
              {tsData?.stats?.mean != null && (
                <ReferenceLine y={tsData.stats.mean} stroke={C.textWeak} strokeDasharray="2 4"
                  label={{ value: 'x̄', position: 'right', fontSize: 10, fill: C.textWeak }} />
              )}
              {tsData?.stats?.usl != null && (
                <ReferenceLine y={tsData.stats.usl} stroke={C.bad} strokeWidth={1.5}
                  label={{ value: 'USL', position: 'right', fontSize: 10, fill: C.bad }} />
              )}
              {tsData?.stats?.lsl != null && (
                <ReferenceLine y={tsData.stats.lsl} stroke={C.ok}
                  label={{ value: 'LSL', position: 'right', fontSize: 10, fill: C.ok }} />
              )}
              <Line type="monotone" dataKey="v" stroke={C.accent} strokeWidth={1.5}
                dot={chartData.length < 60 ? { r: 2, fill: C.accent } : false}
                connectNulls={false} isAnimationActive={false}
                name={varCfg?.label ?? selectedVar} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </ChartCard>

      {/* Row: histogram + boxplot */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, margin: '12px 0' }}>

        <ChartCard title="Distribuição de frequência"
          desc={`Histograma — ${unit}${ignoreOff ? ' · OFF excluído' : ''}`} height={240}>
          {loading && !tsData ? <Spinner /> : histData.length === 0 ? (
            <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 12, color: C.textMuted }}>Sem dados</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={histData} margin={{ top: 4, right: 8, left: 0, bottom: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
                <XAxis dataKey="x" tick={tick} label={{ value: unit, position: 'insideBottom', offset: -16, ...tick }} />
                <YAxis tick={tick} label={{ value: 'freq.', angle: -90, position: 'insideLeft', ...tick }} />
                <Tooltip contentStyle={{ fontSize: 11, background: C.bgPanel, border: `1px solid ${C.border}` }}
                  formatter={(v: any) => [v, 'ocorrências']} />
                <Bar dataKey="freq" fill={C.accent} isAnimationActive={false} name="frequência" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Boxplot por turno"
          desc="T1 06–14 h · T2 14–22 h · T3 22–06 h (barras: Q1 / Mediana / Q3−Q2)" height={240}>
          {loading && !tsData ? <Spinner /> : boxData.every(b => b.q1 === 0 && b.q2 === 0 && b.q3 === 0) ? (
            <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 12, color: C.textMuted }}>Sem dados suficientes por turno</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={boxData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
                <XAxis dataKey="turno" tick={tick} />
                <YAxis tick={tick} label={{ value: unit, angle: -90, position: 'insideLeft', ...tick }} />
                <Tooltip contentStyle={{ fontSize: 11, background: C.bgPanel, border: `1px solid ${C.border}` }}
                  formatter={(v: any, name: string) => [`${typeof v === 'number' ? v.toFixed(2) : v} ${unit}`, name]} />
                <Legend iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="q1" fill={`${C.accent}44`} stackId="box" name="Q1"         isAnimationActive={false} />
                <Bar dataKey="q2" fill={C.ok}             stackId="box" name="Mediana"    isAnimationActive={false} />
                <Bar dataKey="q3" fill={`${C.accent}99`} stackId="box" name="Q3−Mediana" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      {/* Stats grid */}
      {statsItems.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 8 }}>
          {statsItems.map(s => (
            <div key={s.l} style={{ background: C.bgPanel, border: `1px solid ${C.border}`,
              borderRadius: 6, padding: '8px 10px' }}>
              <div style={{ fontSize: 10, color: C.textMuted, textTransform: 'uppercase',
                letterSpacing: '0.04em', marginBottom: 4 }}>{s.l}</div>
              <div style={{ fontSize: 17, fontWeight: 600, fontVariantNumeric: 'tabular-nums',
                color: C.text }}>{s.v}</div>
            </div>
          ))}
        </div>
      )}

      {/* No equipment fallback */}
      {!selectedEq && !loading && (
        <div style={{ padding: '20px 0', textAlign: 'center', fontSize: 13, color: C.textMuted }}>
          Selecione um equipamento para visualizar dados analíticos.
        </div>
      )}
    </div>
  );
};

export default AnalyticsTab;
