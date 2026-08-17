/**
 * LineManagement — gerenciamento operacional de uma linha (visão consolidada).
 *
 * Reescrita para o padrão da POC ISA-101 (`04_POC_UI.html`):
 *   - Topbar com voltar, breadcrumb e refresh + auto-refresh switch
 *   - KPI strip 5 colunas (Equipamentos, Produzidas, Descartes, OEE, Velocidade)
 *   - Panel "Status dos Equipamentos" — tabela densa
 *   - Grid de cards detalhados por equipamento (campos planejados/SKU/OP)
 *
 * Mantém: fetch Flask `/linha/<id>/status`, mock fallback, auto-refresh 10s.
 */
import React, { useState, useEffect } from 'react';
import { ArrowLeft, RefreshCw, CheckCircle } from 'lucide-react';
import { useParams, useNavigate } from 'react-router-dom';
import { FLASK_API_URL } from '@/config/api';
import { mockLinhaStatus } from '@/mocks/demoData';
import { KpiStrip, KpiCard, Panel, Tag } from '@/components/v2';
import { fmt as numFmt } from '@/components/v2/stats';

interface EquipamentoStatus {
  equipamento: string;
  medicoes: {
    contagem_saida: number;
    contagem_entrada: number;
    velocidade_atual: number;
    descarte: number;
    percentual_descarte: number;
    formato_gramas: number;
    planejado_op: number;
    descricao: string;
    temperatura: number;
    pressao: number;
    oee: number;
    disponibilidade: number;
    performance: number;
    qualidade: number;
    sku_codigo?: string;
    ordem_producao?: string;
  };
}

interface LinhaStatusResponse {
  linha: string;
  timestamp: string;
  status: string;
  equipamentos: EquipamentoStatus[];
  agregados: {
    total_equipamentos: number;
    total_contagem_saida: number;
    total_descarte: number;
    media_oee: number;
    media_velocidade: number;
  };
}

const LineManagement: React.FC = () => {
  const { linhaId } = useParams<{ linhaId: string }>();
  const navigate = useNavigate();

  const [linhaStatus, setLinhaStatus] = useState<LinhaStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [isDemo, setIsDemo] = useState(false);

  const fetchLinhaStatus = async () => {
    try {
      const response = await fetch(`${FLASK_API_URL}/linha/${linhaId}/status`);
      if (!response.ok) throw new Error(response.statusText);
      const data = await response.json();
      if (data?.equipamentos) {
        setLinhaStatus(data);
        setIsDemo(false);
      } else {
        setLinhaStatus(mockLinhaStatus(linhaId || 'ENV-01') as any);
        setIsDemo(true);
      }
    } catch (err) {
      console.error('LineManagement fetch falhou — usando mock', err);
      setLinhaStatus(mockLinhaStatus(linhaId || 'ENV-01') as any);
      setIsDemo(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLinhaStatus();
    if (autoRefresh) {
      const interval = setInterval(fetchLinhaStatus, 10000);
      return () => clearInterval(interval);
    }
  }, [linhaId, autoRefresh]);

  if (loading || !linhaStatus) {
    return (
      <div className="isa-root" style={{ padding: 32, textAlign: 'center', color: 'var(--isa-text-muted)' }}>
        Carregando dados da linha…
      </div>
    );
  }

  const { agregados, equipamentos } = linhaStatus;

  // Tone semântico para OEE — usado na tabela e nas tags
  const oeeTone = (v: number): 'ok' | 'warn' | 'bad' =>
    v >= 85 ? 'ok' : v >= 70 ? 'warn' : 'bad';

  return (
    <div className="isa-root" style={{ padding: '16px 20px', minHeight: '100vh' }}>
      {/* Topbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: 12, marginBottom: 14 }}>
        <div>
          <button
            type="button"
            onClick={() => navigate('/')}
            style={{ background: 'transparent', border: 0, color: 'var(--isa-text-muted)', cursor: 'pointer', fontSize: 'var(--isa-fs-body)', display: 'flex', alignItems: 'center', gap: 4, padding: '4px 0', marginBottom: 4 }}
          >
            <ArrowLeft size={14} /> Voltar
          </button>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: 'var(--isa-text)', display: 'flex', alignItems: 'center', gap: 8 }}>
            Gerenciamento de Linha · <span style={{ fontFamily: 'var(--isa-mono)', color: 'var(--isa-text-muted)', fontWeight: 400 }}>{linhaId}</span>
            {isDemo && <Tag tone="warn">SIMULAÇÃO</Tag>}
          </h1>
          <div style={{ marginTop: 2, fontSize: 'var(--isa-fs-default)', color: 'var(--isa-text-muted)' }}>
            Status consolidado · atualizado {new Date(linhaStatus.timestamp).toLocaleTimeString('pt-BR')}
          </div>
        </div>

        <div className="isa-toolbar" style={{ marginBottom: 0 }}>
          <label className="isa-switch">
            <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} />
            Auto-atualizar (10s)
          </label>
          <button type="button" onClick={fetchLinhaStatus}>
            <RefreshCw size={12} style={{ marginRight: 4, verticalAlign: -1 }} />
            Atualizar
          </button>
        </div>
      </div>

      {/* KPI strip 5 col — usa cols=4 e adicionamos Velocidade ocupando o último slot do strip de 5 */}
      <KpiStrip cols={4} style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
        <KpiCard label="Equipamentos Online" value={String(agregados.total_equipamentos)} />
        <KpiCard label="Peças Produzidas"   value={agregados.total_contagem_saida.toLocaleString('pt-BR')} unit="un" />
        <KpiCard label="Descartes"          value={String(agregados.total_descarte)} unit="un" />
        <KpiCard
          label="OEE Médio"
          value={numFmt.num(agregados.media_oee, 1)}
          unit="%"
          delta={{
            value: agregados.media_oee >= 85 ? 'No alvo' : agregados.media_oee >= 70 ? 'Atenção' : 'Crítico',
            tone: oeeTone(agregados.media_oee) === 'ok' ? 'up' : 'down',
          }}
        />
        <KpiCard label="Velocidade Média"   value={numFmt.num(agregados.media_velocidade, 0)} unit="un/min" />
      </KpiStrip>

      {/* Tabela de equipamentos */}
      <Panel title="Status dos Equipamentos">
        <div style={{ overflowX: 'auto' }}>
          <table className="isa-tbl">
            <thead>
              <tr>
                <th>Equipamento</th>
                <th>Status</th>
                <th style={{ textAlign: 'right' }}>Produzidas</th>
                <th style={{ textAlign: 'right' }}>Descartes</th>
                <th style={{ textAlign: 'right' }}>Velocidade</th>
                <th style={{ textAlign: 'right' }}>OEE</th>
                <th style={{ textAlign: 'right' }}>Temp</th>
                <th style={{ textAlign: 'right' }}>Pressão</th>
              </tr>
            </thead>
            <tbody>
              {equipamentos.map((eq, idx) => (
                <tr key={idx}>
                  <td style={{ fontWeight: 600 }}>{eq.equipamento}</td>
                  <td>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--isa-ok)', fontWeight: 600, fontSize: 'var(--isa-fs-meta)' }}>
                      <CheckCircle size={12} /> ONLINE
                    </span>
                  </td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>{eq.medicoes.contagem_saida.toLocaleString('pt-BR')}</td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--isa-bad)', fontWeight: 600 }}>{eq.medicoes.descarte}</td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{eq.medicoes.velocidade_atual} un/min</td>
                  <td style={{ textAlign: 'right' }}>
                    <Tag tone={oeeTone(eq.medicoes.oee)}>{eq.medicoes.oee.toFixed(1)}%</Tag>
                  </td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--isa-text-muted)' }}>{eq.medicoes.temperatura.toFixed(1)}°C</td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--isa-text-muted)' }}>{eq.medicoes.pressao.toFixed(2)} bar</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {/* Cards detalhados por equipamento */}
      <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 12 }}>
        {equipamentos.map((eq, idx) => (
          <Panel key={idx} title={eq.equipamento}>
            <dl style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, margin: 0 }}>
              {[
                ['Descrição',       eq.medicoes.descricao || '—'],
                ['SKU',             eq.medicoes.sku_codigo || '—'],
                ['Ordem Produção',  eq.medicoes.ordem_producao || '—'],
                ['Formato',         `${eq.medicoes.formato_gramas} g`],
                ['Disponibilidade', `${eq.medicoes.disponibilidade.toFixed(1)}%`],
                ['Performance',     `${eq.medicoes.performance.toFixed(1)}%`],
                ['Qualidade',       `${eq.medicoes.qualidade.toFixed(1)}%`],
                ['% Descarte',      <span style={{ color: 'var(--isa-bad)' }}>{eq.medicoes.percentual_descarte.toFixed(2)}%</span>],
              ].map(([lbl, val], i) => (
                <div key={i}>
                  <dt style={{ fontSize: 'var(--isa-fs-label)', color: 'var(--isa-text-muted)', textTransform: 'uppercase', margin: 0 }}>{lbl}</dt>
                  <dd style={{ fontSize: 'var(--isa-fs-default)', color: 'var(--isa-text)', fontWeight: 600, margin: '2px 0 0' }}>{val}</dd>
                </div>
              ))}
            </dl>
          </Panel>
        ))}
      </div>
    </div>
  );
};

export default LineManagement;
