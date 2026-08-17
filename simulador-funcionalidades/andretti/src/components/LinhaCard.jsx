import React, { useState } from 'react'
import {
  AreaChart, Area, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis
} from 'recharts'
import { TrendingUp, Clock, Target } from 'lucide-react'
import { trendsIniciais } from '../data/mockData'

function getSpeedStatus(atual, meta) {
  const pct = (atual / meta) * 100
  if (pct >= 100) return { cor: '#22c55e', corGlow: '#22c55e40', label: 'Meta atingida!',  emoji: '🏎️' }
  if (pct >= 90)  return { cor: '#84cc16', corGlow: '#84cc1640', label: 'Quase lá!',       emoji: '🏎️' }
  if (pct >= 75)  return { cor: '#f59e0b', corGlow: '#f59e0b40', label: 'Acelerando...',   emoji: '🏃' }
  return             { cor: '#ef4444', corGlow: '#ef444440', label: 'Abaixo da meta',   emoji: '🐌' }
}

function SpeedBar({ label, emoji, velocidade, meta, isAndretti, accentCor }) {
  const escala = meta * 1.08
  const pctBar  = Math.min((velocidade / escala) * 100, 100)
  const pctMeta = (meta / escala) * 100
  const status  = isAndretti ? getSpeedStatus(velocidade, meta) : null
  const cor     = isAndretti ? status.cor : '#475569'

  return (
    <div className="speed-bar-row">
      <span className="speed-bar-emoji">{emoji}</span>
      <div className="speed-bar-track">
        <div
          className={`speed-bar-fill ${isAndretti ? 'animated' : ''}`}
          style={{
            width: `${pctBar}%`,
            background: isAndretti
              ? `linear-gradient(90deg, ${cor}99, ${cor})`
              : 'linear-gradient(90deg, #33415580, #334155)',
            boxShadow: isAndretti ? `0 0 12px ${cor}60` : 'none',
          }}
        />
        {isAndretti && (
          <div
            className="speed-bar-meta-marker"
            style={{ left: `${pctMeta}%`, borderColor: accentCor }}
            title={`Meta: ${meta} ppm`}
          />
        )}
      </div>
      <span className="speed-bar-value" style={{ color: isAndretti ? cor : '#64748b' }}>
        {velocidade} <span className="speed-bar-unit">ppm</span>
      </span>
    </div>
  )
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="trend-tooltip">
      <div className="trend-tooltip-time">{d.hora}</div>
      <div className="trend-tooltip-speed">{d.velocidade} ppm</div>
    </div>
  )
}

export default function LinhaCard({ linha, meta, velocidadeAtual, atualizado }) {
  const [showTrend, setShowTrend] = useState(false)
  const trend = trendsIniciais[linha.id] || []
  const pctMeta = meta ? Math.round((velocidadeAtual / meta.velocidadeMeta) * 100) : 0
  const status = meta ? getSpeedStatus(velocidadeAtual, meta.velocidadeMeta) : null

  if (!meta) {
    return (
      <div className="linha-card linha-card--sem-meta">
        <div className="linha-card-header">
          <span className="linha-badge" style={{ background: linha.cor + '30', color: linha.cor }}>
            {linha.nome}
          </span>
        </div>
        <p className="sem-meta-msg">Sem meta cadastrada para esta wave.</p>
      </div>
    )
  }

  return (
    <div
      className={`linha-card ${atualizado ? 'linha-card--pulse' : ''}`}
      style={{ '--linha-cor': linha.cor, '--status-cor': status.cor }}
    >
      {/* ── Header ─────────────────────────────────────────── */}
      <div className="linha-card-header">
        <div>
          <span className="linha-badge" style={{ background: linha.cor + '25', color: linha.cor }}>
            {linha.nome}
          </span>
          <p className="linha-descricao">{linha.descricao}</p>
        </div>
        <div className="linha-live-badge">
          <span className="live-dot" />
          LIVE
        </div>
      </div>

      {/* ── Velocidade atual grande ─────────────────────────── */}
      <div className="linha-speed-display">
        <span className="linha-speed-emoji">{status.emoji}</span>
        <div>
          <div
            className={`linha-speed-number ${atualizado ? 'speed-flash' : ''}`}
            style={{ color: status.cor, textShadow: `0 0 20px ${status.corGlow}` }}
          >
            {velocidadeAtual}
            <span className="linha-speed-unit"> ppm</span>
          </div>
          <div className="linha-speed-status" style={{ color: status.cor }}>
            {status.label}
          </div>
        </div>
        <div className="linha-pct-badge" style={{ background: status.cor + '20', color: status.cor, border: `1px solid ${status.cor}50` }}>
          <Target size={12} />
          {pctMeta}%
        </div>
      </div>

      {/* ── Barras de velocidade ────────────────────────────── */}
      <div className="speed-bars-container">
        <div className="speed-bar-label-row">
          <span className="speed-bar-legend">Padrão</span>
          <span className="speed-bar-legend andretti-label" style={{ color: linha.cor }}>Andretti</span>
        </div>

        <SpeedBar
          emoji="🐌"
          velocidade={meta.velocidadePadrao}
          meta={meta.velocidadeMeta}
          isAndretti={false}
        />
        <SpeedBar
          emoji="🏎️"
          velocidade={velocidadeAtual}
          meta={meta.velocidadeMeta}
          isAndretti
          accentCor={linha.cor}
        />

        <div className="speed-meta-info">
          <span style={{ color: '#64748b' }}>Padrão: <b style={{ color: '#94a3b8' }}>{meta.velocidadePadrao} ppm</b></span>
          <span style={{ color: linha.cor }}>Meta Wave: <b>{meta.velocidadeMeta} ppm</b></span>
        </div>
      </div>

      {/* ── Sparkline ──────────────────────────────────────── */}
      <div className="sparkline-container">
        <div className="sparkline-header">
          <span className="sparkline-title">
            <TrendingUp size={12} /> Tendência 24h
          </span>
          <button
            className="btn-trend"
            onClick={() => setShowTrend(!showTrend)}
          >
            {showTrend ? 'Ocultar' : 'Expandir'}
          </button>
        </div>

        <div className={`sparkline-chart ${showTrend ? 'sparkline-expanded' : ''}`}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trend} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
              <defs>
                <linearGradient id={`grad-${linha.id}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={linha.cor} stopOpacity={0.4} />
                  <stop offset="95%" stopColor={linha.cor} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              {showTrend && <XAxis dataKey="hora" tick={{ fill: '#475569', fontSize: 10 }} interval={3} />}
              {showTrend && <YAxis tick={{ fill: '#475569', fontSize: 10 }} domain={['auto', 'auto']} />}
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={meta.velocidadeMeta}   stroke={linha.cor} strokeDasharray="4 3" strokeOpacity={0.7} />
              <ReferenceLine y={meta.velocidadePadrao} stroke="#475569"   strokeDasharray="3 3" strokeOpacity={0.5} />
              <Area
                type="monotone"
                dataKey="velocidade"
                stroke={linha.cor}
                strokeWidth={1.5}
                fill={`url(#grad-${linha.id})`}
                dot={false}
                animationDuration={400}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {showTrend && (
          <div className="trend-legend">
            <span><span style={{ color: linha.cor }}>━━</span> Real</span>
            <span><span style={{ color: linha.cor }}>╌╌</span> Meta</span>
            <span><span style={{ color: '#475569' }}>╌╌</span> Padrão</span>
          </div>
        )}
      </div>

      {/* ── Rodapé ─────────────────────────────────────────── */}
      <div className="linha-card-footer">
        <Clock size={11} />
        Última leitura OPC simulada
      </div>
    </div>
  )
}
