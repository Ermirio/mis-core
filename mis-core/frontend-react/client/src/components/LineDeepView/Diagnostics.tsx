import React from 'react';
import { AlertCircle, CheckCircle } from 'lucide-react';

const ISA = {
  bg:      '#ffffff',
  border:  '#d7dbe0',
  text:    '#2c3138',
  muted:   '#657384',
  ok:      '#2d8659',  okBg:   '#e3efe7',
  warn:    '#c9932d',  warnBg: '#f4e8cf',
} as const;

interface DiagnosticsProps {
  alerts?: string[];
}

const Diagnostics: React.FC<DiagnosticsProps> = ({ alerts = [] }) => {
  return (
    <div style={{ background: ISA.bg, border: `1px solid ${ISA.border}`, borderRadius: 6, padding: '14px 16px', marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontWeight: 600, fontSize: 14, color: ISA.text, marginBottom: 10 }}>
        <AlertCircle size={15} color={ISA.warn} />
        Diagnósticos Inteligentes
      </div>

      {alerts.length === 0 ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: ISA.ok }}>
          <CheckCircle size={13} />
          Nenhum alerta de diagnóstico no momento.
        </div>
      ) : (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {alerts.map((alert, idx) => (
            <li key={idx} style={{
              display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 12, color: ISA.text,
              background: ISA.warnBg, border: `1px solid ${ISA.warn}20`,
              borderLeft: `3px solid ${ISA.warn}`,
              padding: '7px 10px', borderRadius: '0 4px 4px 0',
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: '50%', background: ISA.warn,
                marginTop: 4, flexShrink: 0,
              }} />
              {alert}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default Diagnostics;
