import React from 'react';
import { RefreshCw } from 'lucide-react';

const ISA = {
  bg:      '#ffffff',
  bgMuted: '#f4f5f7',
  bgHover: '#e9ecef',
  border:  '#d7dbe0',
  text:    '#2c3138',
  muted:   '#657384',
  accent:  '#3f5b7c',
  accentBg:'rgba(63, 91, 124, 0.08)',
} as const;

interface LossFilterBarProps {
  periodo: string;
  setPeriodo: (p: string) => void;
  isLoading: boolean;
  onRefresh?: () => void;
}

const OPTIONS = [
  { value: 'TURNO', label: 'Turno' },
  { value: 'DIA',   label: 'Hoje'  },
  { value: 'SEMANA',label: 'Semana'},
  { value: 'MES',   label: 'Mês'   },
];

const LossFilterBar: React.FC<LossFilterBarProps> = ({ periodo, setPeriodo, isLoading, onRefresh }) => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4,
      background: ISA.bgMuted, border: `1px solid ${ISA.border}`,
      borderRadius: 6, padding: 3 }}>
      {OPTIONS.map(opt => {
        const active = periodo === opt.value;
        return (
          <button
            key={opt.value}
            onClick={() => setPeriodo(opt.value)}
            disabled={isLoading}
            style={{
              padding: '4px 10px', border: 'none', borderRadius: 4, cursor: isLoading ? 'not-allowed' : 'pointer',
              fontSize: 12, fontWeight: active ? 600 : 400,
              background: active ? ISA.bg : 'transparent',
              color: active ? ISA.accent : ISA.muted,
              boxShadow: active ? '0 1px 3px rgba(0,0,0,.08)' : 'none',
              transition: 'all 100ms',
              opacity: isLoading ? 0.5 : 1,
            }}
          >
            {opt.label}
          </button>
        );
      })}
      {onRefresh && (
        <button
          onClick={onRefresh}
          disabled={isLoading}
          style={{
            marginLeft: 4, padding: '4px 6px', border: 'none', borderRadius: 4,
            background: 'transparent', color: ISA.muted, cursor: 'pointer',
            display: 'flex', alignItems: 'center',
          }}
          title="Atualizar"
        >
          <RefreshCw size={12} className={isLoading ? 'animate-spin' : ''} />
        </button>
      )}
    </div>
  );
};

export default LossFilterBar;
