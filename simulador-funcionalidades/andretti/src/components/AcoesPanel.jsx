import React, { useState } from 'react'
import { Plus, CheckCircle2, Clock3, Circle, XCircle, Calendar, User } from 'lucide-react'
import { areaConfig, statusConfig, linhas } from '../data/mockData'

function StatusBadge({ status }) {
  const cfg = statusConfig[status]
  if (!cfg) return null
  return (
    <span className="status-badge" style={{ background: cfg.corFundo, color: cfg.cor, border: `1px solid ${cfg.cor}40` }}>
      {status === 'aberta'       && <Circle size={10} />}
      {status === 'em_andamento' && <Clock3 size={10} />}
      {status === 'concluida'    && <CheckCircle2 size={10} />}
      {status === 'cancelada'    && <XCircle size={10} />}
      {cfg.label}
    </span>
  )
}

function AcaoItem({ acao, onStatusChange }) {
  const linha = linhas.find(l => l.id === acao.linhaId)
  const prazo = new Date(acao.prazoExecucao)
  const hoje  = new Date()
  const atrasada = acao.status !== 'concluida' && acao.status !== 'cancelada' && prazo < hoje

  return (
    <div className={`acao-item ${atrasada ? 'acao-item--atrasada' : ''}`}>
      <div className="acao-item-top">
        <p className="acao-descricao">{acao.descricao}</p>
        <StatusBadge status={acao.status} />
      </div>

      <div className="acao-meta-row">
        <span className="acao-meta-tag" style={{ background: linha?.cor + '20', color: linha?.cor }}>
          {linha?.nome}
        </span>
        <span className="acao-meta-tag acao-categoria">{acao.categoria}</span>
        {atrasada && <span className="acao-meta-tag acao-atrasada">⚠️ Atrasada</span>}
      </div>

      <div className="acao-footer-row">
        <span className="acao-info-item">
          <User size={11} /> {acao.responsavel}
        </span>
        <span className="acao-info-item" style={{ color: atrasada ? '#ef4444' : '#64748b' }}>
          <Calendar size={11} /> Prazo: {new Date(acao.prazoExecucao).toLocaleDateString('pt-BR')}
        </span>
        {acao.dataRealizada && (
          <span className="acao-info-item" style={{ color: '#22c55e' }}>
            <CheckCircle2 size={11} /> Realizada: {new Date(acao.dataRealizada).toLocaleDateString('pt-BR')}
          </span>
        )}
        <select
          className="acao-status-select"
          value={acao.status}
          onChange={e => onStatusChange(acao.id, e.target.value)}
        >
          <option value="aberta">Aberta</option>
          <option value="em_andamento">Em Andamento</option>
          <option value="concluida">Concluída</option>
          <option value="cancelada">Cancelada</option>
        </select>
      </div>
    </div>
  )
}

export default function AcoesPanel({ acoes, waveId, filtroLinha, onStatusChange, onNovaAcao }) {
  const areas = Object.keys(areaConfig)
  const [abaAtiva, setAbaAtiva] = useState(areas[0])

  const acoesDaWave = acoes.filter(a => a.waveId === waveId)

  const totalAbertas    = acoesDaWave.filter(a => a.status === 'aberta').length
  const totalAndamento  = acoesDaWave.filter(a => a.status === 'em_andamento').length
  const totalConcluidas = acoesDaWave.filter(a => a.status === 'concluida').length

  // Ações da aba ativa, com filtro de linha
  const acoesDaAba = acoesDaWave
    .filter(a => a.area === abaAtiva)
    .filter(a => filtroLinha === 'todas' || a.linhaId === Number(filtroLinha))

  const cfgAtiva = areaConfig[abaAtiva]

  // Contagem por área (para badges nas abas)
  function countArea(area) {
    return acoesDaWave
      .filter(a => a.area === area)
      .filter(a => filtroLinha === 'todas' || a.linhaId === Number(filtroLinha))
      .filter(a => a.status !== 'concluida' && a.status !== 'cancelada')
      .length
  }

  return (
    <div className="acoes-panel">
      {/* ── Cabeçalho ───────────────────────────────────────── */}
      <div className="acoes-panel-header">
        <div>
          <h2 className="acoes-panel-title">Plano de Ações Andretti</h2>
          <p className="acoes-panel-subtitle">
            Ações multi-área para sustentação do ganho de velocidade
          </p>
        </div>
        <div className="acoes-summary-chips">
          <span className="summary-chip" style={{ color: '#3b82f6', background: '#3b82f615' }}>
            <Circle size={11} /> {totalAbertas} abertas
          </span>
          <span className="summary-chip" style={{ color: '#f59e0b', background: '#f59e0b15' }}>
            <Clock3 size={11} /> {totalAndamento} em andamento
          </span>
          <span className="summary-chip" style={{ color: '#22c55e', background: '#22c55e15' }}>
            <CheckCircle2 size={11} /> {totalConcluidas} concluídas
          </span>
        </div>
      </div>

      {/* ── Abas de área ────────────────────────────────────── */}
      <div className="area-tabs">
        {areas.map(area => {
          const cfg    = areaConfig[area]
          const ativa  = abaAtiva === area
          const pendentes = countArea(area)
          return (
            <button
              key={area}
              className={`area-tab ${ativa ? 'area-tab--ativa' : ''}`}
              onClick={() => setAbaAtiva(area)}
              style={ativa
                ? { borderBottom: `2px solid ${cfg.cor}`, color: cfg.cor, background: cfg.corFundo }
                : { borderBottom: '2px solid transparent' }
              }
            >
              <span className="area-tab-icon">{cfg.icon}</span>
              <span className="area-tab-label">{cfg.label}</span>
              {pendentes > 0 && (
                <span
                  className="area-tab-badge"
                  style={ativa
                    ? { background: cfg.cor, color: '#fff' }
                    : { background: cfg.cor + '30', color: cfg.cor }
                  }
                >
                  {pendentes}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* ── Conteúdo da aba ativa ────────────────────────────── */}
      <div className="area-tab-content">
        {/* Barra de ação da área */}
        <div
          className="area-tab-toolbar"
          style={{ borderLeft: `3px solid ${cfgAtiva.cor}`, background: cfgAtiva.corFundo }}
        >
          <span className="area-tab-toolbar-title" style={{ color: cfgAtiva.cor }}>
            {cfgAtiva.icon} {cfgAtiva.label}
          </span>
          <div className="area-tab-toolbar-counts">
            {acoesDaAba.filter(a => a.status === 'aberta').length > 0 && (
              <span className="area-count area-count--aberta">
                {acoesDaAba.filter(a => a.status === 'aberta').length} abertas
              </span>
            )}
            {acoesDaAba.filter(a => a.status === 'em_andamento').length > 0 && (
              <span className="area-count area-count--andamento">
                {acoesDaAba.filter(a => a.status === 'em_andamento').length} em andamento
              </span>
            )}
            {acoesDaAba.filter(a => a.status === 'concluida').length > 0 && (
              <span className="area-count area-count--concluida">
                {acoesDaAba.filter(a => a.status === 'concluida').length} concluídas
              </span>
            )}
          </div>
          <button
            className="btn-nova-acao"
            style={{ color: cfgAtiva.cor, border: `1px solid ${cfgAtiva.cor}50` }}
            onClick={() => onNovaAcao(abaAtiva)}
          >
            <Plus size={13} /> Nova ação
          </button>
        </div>

        {/* Lista de ações */}
        <div className="area-accordion-body">
          {acoesDaAba.length === 0 ? (
            <div className="area-empty">
              <span>{cfgAtiva.icon}</span>
              <p>Nenhuma ação cadastrada para esta área{filtroLinha !== 'todas' ? ' nesta linha' : ''}.</p>
              <button
                className="btn-nova-acao-empty"
                style={{ color: cfgAtiva.cor }}
                onClick={() => onNovaAcao(abaAtiva)}
              >
                <Plus size={14} /> Adicionar primeira ação
              </button>
            </div>
          ) : (
            acoesDaAba.map(acao => (
              <AcaoItem key={acao.id} acao={acao} onStatusChange={onStatusChange} />
            ))
          )}
        </div>
      </div>
    </div>
  )
}
