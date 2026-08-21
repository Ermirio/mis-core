import React from 'react';
import { Activity, Box, Package, Tag, Zap, Scale } from 'lucide-react';

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
  off:     '#9ba3ad',  offBg:  '#e9ecef',
} as const;

function statusStyle(status: string): React.CSSProperties {
  const s = status.toLowerCase();
  if (s.includes('produzindo'))                          return { background: ISA.okBg,   color: ISA.ok,   border: `1px solid ${ISA.ok}` };
  if (s.includes('parada') || s.includes('parado'))     return { background: ISA.badBg,  color: ISA.bad,  border: `1px solid ${ISA.bad}` };
  if (s.includes('falha') || s.includes('quebra'))      return { background: ISA.badBg,  color: ISA.bad,  border: `1px solid ${ISA.bad}` };
  if (s.includes('manut') || s.includes('setup'))       return { background: ISA.warnBg, color: ISA.warn, border: `1px solid ${ISA.warn}` };
  if (s.includes('aguardando'))                         return { background: ISA.warnBg, color: ISA.warn, border: `1px solid ${ISA.warn}` };
  if (s.includes('offline') || s.includes('comunica'))  return { background: ISA.offBg,  color: ISA.off,  border: `1px solid ${ISA.border}` };
  return { background: ISA.bgMuted, color: ISA.muted, border: `1px solid ${ISA.border}` };
}

function oleStyle(v: number): React.CSSProperties {
  if (v >= 85) return { color: ISA.ok,   fontWeight: 700, fontSize: 36 };
  if (v >= 70) return { color: ISA.warn, fontWeight: 700, fontSize: 36 };
  return             { color: ISA.bad,  fontWeight: 700, fontSize: 36 };
}

interface HeaderProps {
  linha: string;
  op: string;
  sku: string;
  produto: string;
  cuc: string;
  equipamentosOnline: number;
  totalEquipamentos: number;
  vazao: number;
  ole: number;
  status?: string;
  formato?: number;
}

const Header: React.FC<HeaderProps> = ({
  linha, op, sku, produto, cuc,
  equipamentosOnline, totalEquipamentos,
  vazao, ole, status = 'Em Produção', formato = 0,
}) => {
  const meta: React.CSSProperties = { fontSize: 10, color: ISA.muted, textTransform: 'uppercase', letterSpacing: '0.05em' };
  const val:  React.CSSProperties = { fontWeight: 600, fontSize: 13, color: ISA.text };

  return (
    <div style={{ background: ISA.bg, border: `1px solid ${ISA.border}`, borderRadius: 6, padding: '16px 20px', marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>

        {/* Left */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: ISA.text }}>{linha}</h1>
            <span style={{
              padding: '3px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600,
              textTransform: 'uppercase', ...statusStyle(status),
            }}>
              {status}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: '8px 20px' }}>
            {[
              { icon: <Tag   size={13} />, label: 'OP',      value: op },
              { icon: <Package size={13} />, label: 'SKU',   value: sku },
              { icon: <Box   size={13} />, label: 'Produto', value: produto },
              { icon: <Activity size={13} />, label: 'Vazão', value: `${vazao.toFixed(1)} t/h` },
              { icon: <Scale size={13} />, label: 'Formato', value: formato ? `${formato}g` : 'N/A' },
            ].map(({ icon, label, value }) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                <span style={{ color: ISA.weak, flexShrink: 0 }}>{icon}</span>
                <div>
                  <div style={meta}>{label}</div>
                  <div style={{ ...val, maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={value}>
                    {value}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 12, fontSize: 12, color: ISA.muted, flexWrap: 'wrap' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <Zap size={12} color={ISA.ok} />
              Equipamentos Online:&nbsp;
              <span style={{ fontWeight: 600, color: ISA.text }}>{equipamentosOnline} de {totalEquipamentos}</span>
            </span>
            <span style={{ color: ISA.border }}>|</span>
            <span>CUC: <span style={{ fontFamily: 'ui-monospace, monospace', color: ISA.text }}>{cuc}</span></span>
          </div>
        </div>

        {/* OEE badge */}
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          padding: '12px 20px', background: ISA.bgMuted, border: `1px solid ${ISA.border}`,
          borderRadius: 8, minWidth: 140, flexShrink: 0,
        }}>
          <div style={{ fontSize: 11, color: ISA.muted, fontWeight: 500, marginBottom: 2 }}>OLE (OMAC)</div>
          <div style={{ ...oleStyle(ole), fontVariantNumeric: 'tabular-nums' }}>{ole.toFixed(1)}%</div>
          <div style={{ fontSize: 10, color: ISA.weak, marginTop: 2 }}>Eficiência da Linha</div>
        </div>

      </div>
    </div>
  );
};

export default Header;
