import { mapEstado } from '@/utils/equipmentStateUtils';
import { Clock } from 'lucide-react';
import { safeNumber, safeString, normalizeEstado } from '@/utils/dataValidation';

// ISA-101 palette — saturated colors only for alarm/deviation conditions
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

function oeeStyle(v: number): React.CSSProperties {
  if (v >= 85) return { color: ISA.ok, fontWeight: 700 };
  if (v >= 70) return { color: ISA.warn, fontWeight: 700 };
  return { color: ISA.bad, fontWeight: 700 };
}

function descarteBadgeStyle(perc: number): React.CSSProperties {
  if (perc < 2)  return { background: ISA.okBg,   color: ISA.ok,   border: `1px solid ${ISA.ok}` };
  if (perc < 5)  return { background: ISA.warnBg,  color: ISA.warn, border: `1px solid ${ISA.warn}` };
  return               { background: ISA.badBg,   color: ISA.bad,  border: `1px solid ${ISA.bad}` };
}

interface EquipmentCardProps {
  nome: string;
  funcao?: string;
  estado: number | string;
  oee: number;
  velocidadeAtual: number;
  velocidadeNominal: number;
  boas: number;
  ruins: number;
  ultimaParada: string;
}

const EquipmentCard: React.FC<EquipmentCardProps> = (props) => {
  const nome             = safeString(props.nome, 'Equipamento');
  const funcao           = props.funcao ? safeString(props.funcao, '') : undefined;
  const estadoNormalizado = normalizeEstado(props.estado);
  const oee              = safeNumber(props.oee, 0);
  const velocidadeAtual  = safeNumber(props.velocidadeAtual, 0);
  const velocidadeNominal = safeNumber(props.velocidadeNominal, 100);
  const boas             = safeNumber(props.boas, 0);
  const ruins            = safeNumber(props.ruins, 0);
  const ultimaParada     = safeString(props.ultimaParada, 'N/A');

  const total            = boas + ruins;
  const percDescarte     = total > 0 ? (ruins / total) * 100 : 0;
  const estadoInfo       = mapEstado(estadoNormalizado);

  const card: React.CSSProperties = {
    background: ISA.bg,
    border: `1px solid ${ISA.border}`,
    borderRadius: 6,
    padding: '14px 16px',
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  };

  const row: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  };

  const label: React.CSSProperties = { fontSize: 12, color: ISA.muted };
  const divider: React.CSSProperties = { borderTop: `1px solid ${ISA.border}`, margin: '2px 0' };

  return (
    <div style={card}>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14, color: ISA.text }}>{nome}</div>
          {funcao && <div style={{ fontSize: 11, color: ISA.weak, marginTop: 1 }}>{funcao}</div>}
        </div>
        <span style={{
          display: 'flex', alignItems: 'center', gap: 4,
          padding: '3px 9px', borderRadius: 12, fontSize: 11, fontWeight: 600,
          background: estadoInfo.corFundo, color: estadoInfo.corHex,
        }}>
          <span style={{ fontSize: 12 }}>{estadoInfo.icon}</span>
          {estadoInfo.nome.toUpperCase()}
        </span>
      </div>

      <div style={divider} />

      {/* OEE */}
      <div style={row}>
        <span style={label}>OEE</span>
        <span style={oeeStyle(oee)}>{oee.toFixed(1)}%</span>
      </div>

      {/* Velocidade */}
      <div style={row}>
        <span style={label}>Velocidade</span>
        <span style={{ fontWeight: 600, fontSize: 13, color: ISA.text }}>
          {velocidadeAtual.toFixed(0)}{' '}
          <span style={{ color: ISA.weak, fontSize: 11 }}>/ {velocidadeNominal} ppm</span>
        </span>
      </div>

      {/* Boas / Ruins */}
      <div style={row}>
        <span style={label}>Boas / Ruins</span>
        <span style={{ fontSize: 13 }}>
          <span style={{ fontWeight: 700, color: ISA.ok }}>{boas.toLocaleString()}</span>
          <span style={{ color: ISA.border, margin: '0 5px' }}>|</span>
          <span style={{ fontWeight: 700, color: ISA.bad }}>{ruins.toLocaleString()}</span>
        </span>
      </div>

      {/* Descarte */}
      <div style={row}>
        <span style={{ fontSize: 11, color: ISA.weak }}>Descarte</span>
        <span style={{
          padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 700,
          ...descarteBadgeStyle(percDescarte),
        }}>
          {percDescarte.toFixed(2)}%
        </span>
      </div>

      <div style={divider} />

      {/* Última parada */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: ISA.weak }}>
        <Clock size={11} />
        Última Parada: {ultimaParada}
      </div>
    </div>
  );
};

export default EquipmentCard;
