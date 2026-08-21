import React from 'react';

const ISA = {
  bg:      '#ffffff',
  bgTrack: '#e9ecef',
  border:  '#d7dbe0',
  text:    '#2c3138',
  muted:   '#657384',
  accent:  '#3f5b7c',
  ok:      '#2d8659',
  warn:    '#c9932d',
  bad:     '#b53a2b',  badBg: '#f4dad6',
} as const;

interface ProgressProps {
  producaoReal: number;
  producaoEsperada: number;
  projecao: number;
  metaTurno: number;
  tempoDecorridoPerc: number;
}

const Progress: React.FC<ProgressProps> = ({
  producaoReal, producaoEsperada, projecao, metaTurno, tempoDecorridoPerc,
}) => {
  const safe   = (v: number) => (metaTurno > 0 ? Math.min((v / metaTurno) * 100, 100) : 0);
  const percR  = safe(producaoReal);
  const percE  = safe(producaoEsperada);
  const percP  = safe(projecao);
  const atraso = producaoReal - producaoEsperada;
  const ahead  = projecao >= metaTurno;

  const card: React.CSSProperties = {
    background: ISA.bg, border: `1px solid ${ISA.border}`, borderRadius: 6,
    padding: '16px 20px', marginBottom: 16,
  };
  const barTrack: React.CSSProperties = {
    width: '100%', background: ISA.bgTrack, borderRadius: 99, height: 8, overflow: 'hidden', position: 'relative',
  };
  const bar = (color: string, perc: number): React.CSSProperties => ({
    height: '100%', borderRadius: 99, width: `${perc}%`,
    background: color, transition: 'width 500ms ease',
  });

  const rowLabel: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', marginBottom: 5, alignItems: 'center' };
  const labelSm = (color: string): React.CSSProperties => ({ fontSize: 12, fontWeight: 600, color });

  return (
    <div style={card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <span style={{ fontWeight: 600, fontSize: 14, color: ISA.text }}>Progresso do Turno</span>
        <span style={{ fontSize: 12, color: ISA.muted }}>
          Meta: <span style={{ fontWeight: 600, color: ISA.text }}>{metaTurno.toFixed(1)} t</span>
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

        {/* Produção Real — accent (neutro, não é alarme) */}
        <div>
          <div style={rowLabel}>
            <span style={labelSm(ISA.accent)}>Produção Real</span>
            <span style={{ ...labelSm(ISA.accent), fontVariantNumeric: 'tabular-nums' }}>{producaoReal.toFixed(3)} t</span>
          </div>
          <div style={barTrack}>
            <div style={bar(ISA.accent, percR)} />
          </div>
        </div>

        {/* Esperado — muted */}
        <div>
          <div style={rowLabel}>
            <span style={labelSm(ISA.muted)}>Esperado (Até Agora)</span>
            <span style={{ ...labelSm(ISA.muted), fontVariantNumeric: 'tabular-nums' }}>{producaoEsperada.toFixed(3)} t</span>
          </div>
          <div style={{ ...barTrack, position: 'relative' }}>
            <div style={bar('#9ba3ad', percE)} />
          </div>
          {atraso < -0.001 && (
            <div style={{ fontSize: 11, fontWeight: 700, color: ISA.bad, textAlign: 'right', marginTop: 3 }}>
              Atraso: {Math.abs(atraso).toFixed(2)} t
            </div>
          )}
        </div>

        {/* Projeção — ok se vai bater a meta, warn se não */}
        <div>
          <div style={rowLabel}>
            <span style={labelSm(ahead ? ISA.ok : ISA.warn)}>Projeção (Fim do Turno)</span>
            <span style={{ ...labelSm(ahead ? ISA.ok : ISA.warn), fontVariantNumeric: 'tabular-nums' }}>{projecao.toFixed(1)} t</span>
          </div>
          <div style={barTrack}>
            <div style={bar(ahead ? ISA.ok : ISA.warn, percP)} />
          </div>
        </div>

      </div>
    </div>
  );
};

export default Progress;
