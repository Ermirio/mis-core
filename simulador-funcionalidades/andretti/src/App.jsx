import React, { useState } from 'react'
import { Clock, Gauge, ChevronDown, Zap, Trophy, AlertTriangle, CheckCircle } from 'lucide-react'
import LinhaCard from './components/LinhaCard.jsx'
import AcoesPanel from './components/AcoesPanel.jsx'
import NovaAcaoModal from './components/NovaAcaoModal.jsx'
import { useSimulatedSpeed } from './hooks/useSimulatedSpeed.js'
import {
  waves, linhas, metas, acoesIniciais, areaConfig
} from './data/mockData.js'

// ─── KPI Card ────────────────────────────────────────────────────────────────
function KpiCard({ icon: Icon, label, value, sub, cor }) {
  return (
    <div className="kpi-card" style={{ '--kpi-cor': cor }}>
      <div className="kpi-icon-wrap" style={{ background: cor + '20', color: cor }}>
        <Icon size={18} />
      </div>
      <div>
        <div className="kpi-value" style={{ color: cor }}>{value}</div>
        <div className="kpi-label">{label}</div>
        {sub && <div className="kpi-sub">{sub}</div>}
      </div>
    </div>
  )
}

// ─── App ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [waveAtiva, setWaveAtiva]       = useState(waves.find(w => w.ativa)?.id ?? waves[0].id)
  const [filtroLinha, setFiltroLinha]   = useState('todas')
  const [acoes, setAcoes]               = useState(acoesIniciais)
  const [modalArea, setModalArea]       = useState(null)

  const { velocidades, ultimaLeitura, atualizado } = useSimulatedSpeed(waveAtiva)

  const wave = waves.find(w => w.id === waveAtiva)

  // KPIs
  const metasDaWave = metas.filter(m => m.waveId === waveAtiva)
  const linhasAcimaMeta = metasDaWave.filter(m => {
    const v = velocidades[m.linhaId] ?? 0
    return v >= m.velocidadeMeta
  }).length
  const acoesAbertas    = acoes.filter(a => a.waveId === waveAtiva && a.status === 'aberta').length
  const acoesAndamento  = acoes.filter(a => a.waveId === waveAtiva && a.status === 'em_andamento').length
  const acoesConcluidas = acoes.filter(a => a.waveId === waveAtiva && a.status === 'concluida').length

  const linhasFiltradas = filtroLinha === 'todas'
    ? linhas
    : linhas.filter(l => l.id === Number(filtroLinha))

  function handleStatusChange(acaoId, novoStatus) {
    setAcoes(prev => prev.map(a =>
      a.id === acaoId
        ? {
            ...a,
            status: novoStatus,
            dataRealizada: novoStatus === 'concluida'
              ? new Date().toISOString().split('T')[0]
              : a.dataRealizada,
          }
        : a
    ))
  }

  function handleNovaAcao(novaAcao) {
    setAcoes(prev => [
      ...prev,
      { ...novaAcao, id: Date.now() },
    ])
    setModalArea(null)
  }

  return (
    <div className="app-root">
      {/* ── Simulator Banner ─────────────────────────────────── */}
      <div className="sim-banner">
        <Zap size={14} />
        SIMULADOR — dados mockados · velocidades OPC simuladas a cada 8s
      </div>

      {/* ── Header ───────────────────────────────────────────── */}
      <header className="app-header">
        <div className="app-header-left">
          <div className="app-logo">
            <span className="logo-emoji">🏎️</span>
            <div>
              <h1 className="app-title">ANDRETTI</h1>
              <p className="app-subtitle">Speed-Up Program · MIS Change Over</p>
            </div>
          </div>
        </div>

        <div className="app-header-right">
          {/* Wave selector */}
          <div className="wave-selector-wrap">
            <label className="wave-selector-label">
              <Gauge size={13} /> Wave ativa
            </label>
            <div className="wave-selector-box">
              <select
                className="wave-select"
                value={waveAtiva}
                onChange={e => setWaveAtiva(Number(e.target.value))}
              >
                {waves.map(w => (
                  <option key={w.id} value={w.id}>{w.nome}</option>
                ))}
              </select>
              <ChevronDown size={14} className="wave-select-icon" />
            </div>
            <span className="wave-dates">
              {wave && `${new Date(wave.dataInicio).toLocaleDateString('pt-BR')} → ${new Date(wave.dataFim).toLocaleDateString('pt-BR')}`}
            </span>
          </div>

          {/* Última leitura */}
          <div className="leitura-badge">
            <span className="live-dot" />
            <Clock size={12} />
            {ultimaLeitura}
          </div>
        </div>
      </header>

      <main className="app-main">
        {/* ── KPI Row ──────────────────────────────────────────── */}
        <div className="kpi-row">
          <KpiCard
            icon={Trophy}
            label="Linhas acima da meta"
            value={`${linhasAcimaMeta} / ${metasDaWave.length}`}
            sub="velocidade Andretti"
            cor="#22c55e"
          />
          <KpiCard
            icon={AlertTriangle}
            label="Ações abertas"
            value={acoesAbertas}
            sub="aguardando execução"
            cor="#ef4444"
          />
          <KpiCard
            icon={Clock}
            label="Em andamento"
            value={acoesAndamento}
            sub="sendo executadas"
            cor="#f59e0b"
          />
          <KpiCard
            icon={CheckCircle}
            label="Concluídas"
            value={acoesConcluidas}
            sub={`de ${acoes.filter(a => a.waveId === waveAtiva).length} total`}
            cor="#6366f1"
          />
        </div>

        {/* ── Filtro de linha ───────────────────────────────────── */}
        <div className="section-header">
          <h2 className="section-title">
            <Gauge size={16} /> Velocidades por Linha
          </h2>
          <div className="linha-filter">
            <button
              className={`filter-btn ${filtroLinha === 'todas' ? 'active' : ''}`}
              onClick={() => setFiltroLinha('todas')}
            >
              Todas
            </button>
            {linhas.map(l => (
              <button
                key={l.id}
                className={`filter-btn ${filtroLinha === String(l.id) ? 'active' : ''}`}
                style={filtroLinha === String(l.id) ? { background: l.cor, borderColor: l.cor } : { borderColor: l.cor + '60', color: l.cor }}
                onClick={() => setFiltroLinha(String(l.id))}
              >
                {l.nome}
              </button>
            ))}
          </div>
        </div>

        {/* ── Grid de Linhas ───────────────────────────────────── */}
        <div className="linhas-grid">
          {linhasFiltradas.map(linha => {
            const meta = metasDaWave.find(m => m.linhaId === linha.id)
            return (
              <LinhaCard
                key={linha.id}
                linha={linha}
                meta={meta}
                velocidadeAtual={velocidades[linha.id] ?? 0}
                atualizado={!!atualizado[linha.id]}
              />
            )
          })}
        </div>

        {/* ── Painel de Ações ───────────────────────────────────── */}
        <AcoesPanel
          acoes={acoes}
          waveId={waveAtiva}
          filtroLinha={filtroLinha}
          onStatusChange={handleStatusChange}
          onNovaAcao={area => setModalArea(area)}
        />
      </main>

      {/* ── Footer ───────────────────────────────────────────── */}
      <footer className="app-footer">
        <span>🏎️ Andretti Speed-Up Program</span>
        <span>·</span>
        <span>MIS Change Over — Simulador de Funcionalidades</span>
        <span>·</span>
        <span style={{ color: '#475569' }}>Dados mockados — sem conexão OPC real</span>
      </footer>

      {/* ── Modal Nova Ação ───────────────────────────────────── */}
      {modalArea && (
        <NovaAcaoModal
          areaInicial={modalArea}
          waveId={waveAtiva}
          onSalvar={handleNovaAcao}
          onFechar={() => setModalArea(null)}
        />
      )}
    </div>
  )
}
