import React, { useState, useEffect } from 'react';
import { TreeDeciduous, RefreshCw } from 'lucide-react';
import LossFilterBar from './LossFilterBar';
import LossWaterfallChart from './LossWaterfallChart';
import LossEquipmentRanking from './LossEquipmentRanking';

const ISA = {
  bg:      '#ffffff',
  bgMuted: '#f4f5f7',
  border:  '#d7dbe0',
  text:    '#2c3138',
  muted:   '#657384',
  accent:  '#3f5b7c',
  bad:     '#b53a2b',  badBg:  '#f4dad6',
  ok:      '#2d8659',
  warn:    '#c9932d',
  off:     '#9ba3ad',
} as const;

interface LossTreeCardProps { linhaId: number; djangoUrl: string; }

const LossTreeCard: React.FC<LossTreeCardProps> = ({ linhaId, djangoUrl }) => {
  const [periodo, setPeriodo]   = useState('TURNO');
  const [data, setData]         = useState<any>(null);
  const [isLoading, setLoading] = useState(false);
  const [error, setError]       = useState<string | null>(null);

  const fetchLossData = async (initial = false) => {
    if (!linhaId) return;
    if (initial) setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${djangoUrl}/linhas/${linhaId}/perdas-analise/?periodo=${periodo}`);
      if (!res.ok) throw new Error('Falha ao buscar dados de perdas');
      setData(await res.json());
    } catch (err: any) {
      if (initial) setError(err.message);
    } finally {
      if (initial) setLoading(false);
    }
  };

  useEffect(() => {
    fetchLossData(true);
    const iv = setInterval(() => fetchLossData(false), 5000);
    return () => clearInterval(iv);
  }, [linhaId, periodo, djangoUrl]);

  const legendItems = [
    { label: 'Produção Boa',       color: ISA.ok     },
    { label: 'Planejado (Setup)',   color: ISA.accent  },
    { label: 'Não Planejado',      color: ISA.bad     },
    { label: 'Performance',        color: ISA.warn    },
    { label: 'Qualidade',          color: ISA.off     },
  ];

  return (
    <div style={{ background: ISA.bg, border: `1px solid ${ISA.border}`, borderRadius: 6, overflow: 'hidden' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 16px', borderBottom: `1px solid ${ISA.border}`, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ width: 32, height: 32, borderRadius: 6, background: ISA.bgMuted,
            border: `1px solid ${ISA.border}`, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
            <TreeDeciduous size={15} color={ISA.accent} />
          </span>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14, color: ISA.text }}>
              Árvore de Perdas Consolidada
            </div>
            <div style={{ fontSize: 11, color: ISA.muted, marginTop: 1 }}>
              Análise de disponibilidade, performance e qualidade
            </div>
          </div>
        </div>

        <LossFilterBar
          periodo={periodo}
          setPeriodo={setPeriodo}
          isLoading={isLoading}
          onRefresh={() => fetchLossData(true)}
        />
      </div>

      {/* Body */}
      <div style={{ padding: '16px' }}>
        {error ? (
          <div style={{ background: ISA.badBg, border: `1px solid ${ISA.bad}`,
            borderRadius: 5, padding: '10px 14px', color: ISA.bad, fontSize: 13 }}>
            Erro ao carregar: {error}
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            <LossWaterfallChart data={data?.waterfall}         isLoading={isLoading} />
            <LossEquipmentRanking data={data?.equipment_ranking} isLoading={isLoading} />
          </div>
        )}

        {/* Legend */}
        <div style={{ marginTop: 14, display: 'flex', gap: 16, flexWrap: 'wrap', justifyContent: 'center' }}>
          {legendItems.map(({ label, color }) => (
            <span key={label} style={{ display: 'flex', alignItems: 'center', gap: 5,
              fontSize: 11, color: ISA.muted }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
              {label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};

export default LossTreeCard;
