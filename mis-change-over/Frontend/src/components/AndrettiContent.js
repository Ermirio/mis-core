/**
 * AndrettiContent.js — Módulo Andretti Speed-Up Program
 * Consome /api/andretti/* do backend Django.
 * URL base via env var REACT_APP_TROCA_AUTOMATICA_BASE_URL (sem hardcode).
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Modal, Form, Button, Spinner, Alert } from 'react-bootstrap';
import {
  AreaChart, Area, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis
} from 'recharts';
import {
  FaTachometerAlt, FaPlus, FaCheckCircle,
  FaClock, FaCircle, FaTimesCircle, FaCalendarAlt, FaUser,
  FaChevronDown, FaChevronUp, FaSync
} from 'react-icons/fa';
import './AndrettiContent.css';

// ── Config ───────────────────────────────────────────────────────────────────
const API_BASE = process.env.REACT_APP_TROCA_AUTOMATICA_BASE_URL || '/api';
const ANDRETTI = `${API_BASE}/andretti`;
const POLL_MS  = 60_000; // atualiza velocidades a cada 60s

// ── Helpers ──────────────────────────────────────────────────────────────────
function getToken() {
  try {
    const stored = localStorage.getItem('authTokens');
    return stored ? JSON.parse(stored).access : null;
  } catch {
    return null;
  }
}

async function apiFetch(path, opts = {}) {
  const token = getToken();
  const res = await fetch(`${ANDRETTI}${path}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.erro || err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

function getSpeedStatus(atual, meta) {
  if (!atual || !meta) return { cor: '#475569', label: 'Sem dados', emoji: '—', pct: null };
  const pct = (atual / meta) * 100;
  if (pct >= 100) return { cor: '#22c55e', label: 'Meta atingida!',  emoji: '🏎️', pct };
  if (pct >= 90)  return { cor: '#84cc16', label: 'Quase lá!',       emoji: '🏎️', pct };
  if (pct >= 75)  return { cor: '#f59e0b', label: 'Acelerando...',   emoji: '🏃', pct };
  return             { cor: '#ef4444', label: 'Abaixo da meta',   emoji: '🐌', pct };
}

const AREA_CFG = {
  manutencao:    { label: 'Manutenção',          icon: '🔧', cor: '#f59e0b', fundo: '#f59e0b18' },
  qualidade:     { label: 'Qualidade',            icon: '🔬', cor: '#8b5cf6', fundo: '#8b5cf618' },
  eng_projetos:  { label: 'Engenharia Projetos',  icon: '🏗️',  cor: '#3b82f6', fundo: '#3b82f618' },
  eng_processos: { label: 'Engenharia Processos', icon: '⚙️',  cor: '#10b981', fundo: '#10b98118' },
};

const STATUS_CFG = {
  aberta:       { label: 'Aberta',       cor: '#3b82f6', fundo: '#3b82f620' },
  em_andamento: { label: 'Em Andamento', cor: '#f59e0b', fundo: '#f59e0b20' },
  concluida:    { label: 'Concluída',    cor: '#22c55e', fundo: '#22c55e20' },
  cancelada:    { label: 'Cancelada',    cor: '#6b7280', fundo: '#6b728020' },
};

// ── Sub-componentes ───────────────────────────────────────────────────────────

function SpeedBar({ emoji, velocidade, meta, isAndretti, corLinha }) {
  const escala = meta * 1.08;
  const pctBar = Math.min((velocidade / escala) * 100, 100);
  const pctMeta = (meta / escala) * 100;
  const { cor } = isAndretti ? getSpeedStatus(velocidade, meta) : { cor: '#475569' };

  return (
    <div className="and-speed-bar-row">
      <span className="and-speed-emoji">{emoji}</span>
      <div className="and-speed-track">
        <div
          className="and-speed-fill"
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
            className="and-speed-meta-mark"
            style={{ left: `${pctMeta}%`, borderColor: corLinha }}
          />
        )}
      </div>
      <span className="and-speed-value" style={{ color: isAndretti ? cor : '#64748b' }}>
        {velocidade?.toFixed(1) ?? '—'} <span className="and-speed-unit">ppm</span>
      </span>
    </div>
  );
}

const TrendTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="and-trend-tooltip">
      <div className="and-trend-time">{d.hora}</div>
      <div className="and-trend-val">{d.velocidade} ppm</div>
    </div>
  );
};

function FormatoCard({ card, trend, loadingTrend, onExpandTrend, onRegistrarVelocidade }) {
  const [expanded, setExpanded] = useState(false);

  const velMeta   = card.velocidade_meta;
  const velPadrao = card.velocidade_padrao;
  const velAtual  = card.velocidade_atual;

  const { cor: statusCor, label, emoji, pct } = getSpeedStatus(velAtual, velMeta);
  const corLinha = '#6366f1';

  function toggle() {
    setExpanded(v => !v);
    if (!expanded) onExpandTrend(card.meta_id, card.linha_id, card.formato_gramas);
  }

  return (
    <div className="and-linha-card" style={{ '--lc': corLinha, '--sc': statusCor }}>
      <div className="and-linha-top-bar" style={{ background: corLinha }} />

      <div className="and-linha-header">
        <div>
          <span className="and-linha-badge" style={{ background: corLinha + '25', color: corLinha }}>
            {card.linha_nome}
          </span>
          <p className="and-linha-desc">{card.unidade || 'ppm'}</p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
          <span className="and-live-dot-wrap">
            <span className="and-live-dot" /> LIVE
          </span>
          <span style={{
            fontSize: '0.72rem', fontWeight: 700, padding: '2px 9px',
            borderRadius: 8, background: '#6366f120', color: '#818cf8',
            border: '1px solid #6366f140'
          }}>
            📦 {card.formato_display}
          </span>
        </div>
      </div>

      <div className="and-speed-display">
        <span className="and-speed-big-emoji">{emoji}</span>
        <div>
          <div className="and-speed-big-num" style={{ color: statusCor }}>
            {velAtual != null ? velAtual.toFixed(1) : '—'}
            <span className="and-speed-big-unit"> ppm</span>
          </div>
          <div className="and-speed-status" style={{ color: statusCor }}>{label}</div>
        </div>
        {pct != null && (
          <div className="and-pct-badge" style={{ color: statusCor, border: `1px solid ${statusCor}50`, background: statusCor + '18' }}>
            🎯 {pct.toFixed(1)}%
          </div>
        )}
      </div>

      <div className="and-bars-section">
        <div className="and-bars-labels">
          <span>Padrão</span>
          <span style={{ color: corLinha }}>Meta Andretti</span>
        </div>
        <SpeedBar emoji="🐌" velocidade={velPadrao} meta={velMeta} isAndretti={false} />
        <SpeedBar emoji="🏎️" velocidade={velAtual}  meta={velMeta} isAndretti corLinha={corLinha} />
        <div className="and-bars-meta-row">
          <span>Padrão: <b>{velPadrao?.toFixed(1) ?? '—'} ppm</b></span>
          <span style={{ color: corLinha }}>Meta: <b>{velMeta?.toFixed(1) ?? '—'} ppm</b></span>
        </div>
      </div>

      <div className="and-trend-section">
        <div className="and-trend-header">
          <span><FaTachometerAlt size={11} /> Tendência 24h</span>
          <button className="and-btn-expand" onClick={toggle}>
            {expanded ? <><FaChevronUp size={11} /> Ocultar</> : <><FaChevronDown size={11} /> Expandir</>}
          </button>
        </div>
        <div className={`and-sparkline ${expanded ? 'and-sparkline--expanded' : ''}`}>
          {loadingTrend ? (
            <div className="and-trend-loading"><Spinner size="sm" /></div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
                <defs>
                  <linearGradient id={`g-${card.meta_id}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={corLinha} stopOpacity={0.4} />
                    <stop offset="95%" stopColor={corLinha} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                {expanded && <XAxis dataKey="hora" tick={{ fill: '#475569', fontSize: 10 }} interval={3} />}
                {expanded && <YAxis tick={{ fill: '#475569', fontSize: 10 }} domain={['auto', 'auto']} />}
                <Tooltip content={<TrendTooltip />} />
                {velMeta && <ReferenceLine y={velMeta}   stroke={corLinha} strokeDasharray="4 3" strokeOpacity={0.7} />}
                {velPadrao && <ReferenceLine y={velPadrao} stroke="#475569" strokeDasharray="3 3" strokeOpacity={0.5} />}
                <Area
                  type="monotone" dataKey="velocidade"
                  stroke={corLinha} strokeWidth={1.5}
                  fill={`url(#g-${card.meta_id})`} dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="and-card-footer">
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <FaClock size={10} />
          {card.ultima_leitura
            ? `${card.fonte_leitura || 'OPC'}: ${new Date(card.ultima_leitura).toLocaleTimeString('pt-BR')}`
            : 'Sem leitura'}
        </span>
        <button
          className="and-btn-refresh"
          title="Registrar velocidade atual"
          onClick={() => onRegistrarVelocidade(card)}
          style={{ marginLeft: 'auto' }}
        >
          <FaTachometerAlt size={11} /> ✏️
        </button>
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  const cfg = STATUS_CFG[status];
  if (!cfg) return null;
  return (
    <span className="and-status-badge" style={{ color: cfg.cor, background: cfg.fundo, border: `1px solid ${cfg.cor}40` }}>
      {status === 'aberta'       && <FaCircle size={9} />}
      {status === 'em_andamento' && <FaClock size={9} />}
      {status === 'concluida'    && <FaCheckCircle size={9} />}
      {status === 'cancelada'    && <FaTimesCircle size={9} />}
      {cfg.label}
    </span>
  );
}

function AcaoItem({ acao, onStatusChange }) {
  const hoje = new Date();
  const prazo = new Date(acao.prazo_execucao);
  const atrasada = !['concluida', 'cancelada'].includes(acao.status) && prazo < hoje;

  return (
    <div className={`and-acao-item ${atrasada ? 'and-acao-item--late' : ''}`}>
      <div className="and-acao-top">
        <p className="and-acao-desc">{acao.descricao}</p>
        <StatusBadge status={acao.status} />
      </div>
      <div className="and-acao-tags">
        <span className="and-tag">{acao.linha_nome}</span>
        {acao.categoria_nome && <span className="and-tag">{acao.categoria_nome}</span>}
        {atrasada && <span className="and-tag and-tag--late">⚠️ Atrasada</span>}
      </div>
      <div className="and-acao-footer">
        <span className="and-acao-info"><FaUser size={10} /> {acao.responsavel}</span>
        <span className="and-acao-info" style={{ color: atrasada ? '#ef4444' : '#64748b' }}>
          <FaCalendarAlt size={10} />
          Prazo: {new Date(acao.prazo_execucao + 'T00:00:00').toLocaleDateString('pt-BR')}
        </span>
        {acao.data_realizada && (
          <span className="and-acao-info" style={{ color: '#22c55e' }}>
            <FaCheckCircle size={10} />
            Realizada: {new Date(acao.data_realizada + 'T00:00:00').toLocaleDateString('pt-BR')}
          </span>
        )}
        <select
          className="and-status-select"
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
  );
}

function AcoesPainel({ acoes, waveId, onStatusChange, onNovaAcao, filtroLinha }) {
  const areas = Object.keys(AREA_CFG);
  const [abaAtiva, setAbaAtiva] = useState(areas[0]);

  const acoesDaWave = acoes.filter(a => a.wave === waveId);
  const acoesDaAba  = acoesDaWave
    .filter(a => a.area === abaAtiva)
    .filter(a => filtroLinha === 'todas' || a.linha_nome === filtroLinha);

  const cfgAtiva = AREA_CFG[abaAtiva];

  const countPendentes = area =>
    acoesDaWave
      .filter(a => a.area === area && !['concluida', 'cancelada'].includes(a.status))
      .filter(a => filtroLinha === 'todas' || a.linha_nome === filtroLinha).length;

  const acoesFiltradas = acoesDaWave
    .filter(a => filtroLinha === 'todas' || a.linha_nome === filtroLinha);

  const totais = {
    abertas:    acoesFiltradas.filter(a => a.status === 'aberta').length,
    andamento:  acoesFiltradas.filter(a => a.status === 'em_andamento').length,
    concluidas: acoesFiltradas.filter(a => a.status === 'concluida').length,
  };

  return (
    <div className="and-acoes-painel">
      <div className="and-acoes-header">
        <div>
          <h2 className="and-acoes-title">Plano de Ações Andretti</h2>
          <p className="and-acoes-sub">Ações multi-área para sustentação do ganho de velocidade</p>
        </div>
        <div className="and-acoes-chips">
          <span className="and-chip" style={{ color: '#3b82f6', background: '#3b82f615' }}>
            <FaCircle size={9} /> {totais.abertas} abertas
          </span>
          <span className="and-chip" style={{ color: '#f59e0b', background: '#f59e0b15' }}>
            <FaClock size={9} /> {totais.andamento} em andamento
          </span>
          <span className="and-chip" style={{ color: '#22c55e', background: '#22c55e15' }}>
            <FaCheckCircle size={9} /> {totais.concluidas} concluídas
          </span>
        </div>
      </div>

      {/* Abas */}
      <div className="and-area-tabs">
        {areas.map(area => {
          const cfg = AREA_CFG[area];
          const ativa = abaAtiva === area;
          const n = countPendentes(area);
          return (
            <button
              key={area}
              className={`and-area-tab ${ativa ? 'and-area-tab--ativa' : ''}`}
              onClick={() => setAbaAtiva(area)}
              style={ativa
                ? { borderBottom: `2px solid ${cfg.cor}`, color: cfg.cor, background: cfg.fundo }
                : { borderBottom: '2px solid transparent' }
              }
            >
              <span>{cfg.icon}</span>
              <span className="and-area-tab-label">{cfg.label}</span>
              {n > 0 && (
                <span
                  className="and-area-tab-badge"
                  style={ativa ? { background: cfg.cor, color: '#fff' } : { background: cfg.cor + '30', color: cfg.cor }}
                >{n}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Toolbar */}
      <div className="and-area-toolbar" style={{ borderLeft: `3px solid ${cfgAtiva.cor}`, background: cfgAtiva.fundo }}>
        <span className="and-area-toolbar-title" style={{ color: cfgAtiva.cor }}>
          {cfgAtiva.icon} {cfgAtiva.label}
        </span>
        <div className="and-area-toolbar-counts">
          {acoesDaAba.filter(a => a.status === 'aberta').length > 0 &&
            <span className="and-count and-count--aberta">{acoesDaAba.filter(a => a.status === 'aberta').length} abertas</span>}
          {acoesDaAba.filter(a => a.status === 'em_andamento').length > 0 &&
            <span className="and-count and-count--andamento">{acoesDaAba.filter(a => a.status === 'em_andamento').length} em andamento</span>}
          {acoesDaAba.filter(a => a.status === 'concluida').length > 0 &&
            <span className="and-count and-count--concluida">{acoesDaAba.filter(a => a.status === 'concluida').length} concluídas</span>}
        </div>
        <button
          className="and-btn-nova-acao"
          style={{ color: cfgAtiva.cor, border: `1px solid ${cfgAtiva.cor}50` }}
          onClick={() => onNovaAcao(abaAtiva)}
        >
          <FaPlus size={11} /> Nova ação
        </button>
      </div>

      {/* Lista */}
      <div className="and-acoes-list">
        {acoesDaAba.length === 0 ? (
          <div className="and-acoes-empty">
            <span>{cfgAtiva.icon}</span>
            <p>Nenhuma ação cadastrada para esta área{filtroLinha !== 'todas' ? ' nesta linha' : ''}.</p>
            <button className="and-btn-empty" style={{ color: cfgAtiva.cor }} onClick={() => onNovaAcao(abaAtiva)}>
              <FaPlus size={12} /> Adicionar primeira ação
            </button>
          </div>
        ) : (
          acoesDaAba.map(a => <AcaoItem key={a.id} acao={a} onStatusChange={onStatusChange} />)
        )}
      </div>
    </div>
  );
}

// ── Modal Nova Ação ───────────────────────────────────────────────────────────

function NovaAcaoModal({ areaInicial, waveId, linhas, categorias, onSalvar, onFechar }) {
  const [form, setForm] = useState({
    area:           areaInicial || 'manutencao',
    linha:          linhas[0]?.linha_id || '',
    categoria:      '',
    descricao:      '',
    responsavel:    '',
    prazo_execucao: '',
    status:         'aberta',
  });
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState('');

  useEffect(() => {
    setForm(f => ({ ...f, area: areaInicial || 'manutencao', categoria: '' }));
  }, [areaInicial]);

  const catsFiltradas = categorias.filter(c => c.area === form.area);
  const cfg = AREA_CFG[form.area] || AREA_CFG.manutencao;

  async function salvar(e) {
    e.preventDefault();
    if (!form.descricao || !form.responsavel || !form.prazo_execucao) return;
    setSaving(true);
    setErro('');
    try {
      const payload = {
        ...form,
        linha: Number(form.linha),
        wave:  waveId,
        categoria: form.categoria ? Number(form.categoria) : null,
      };
      await onSalvar(payload);
    } catch (err) {
      setErro(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal show onHide={onFechar} centered className="and-modal">
      <Modal.Header style={{ borderBottom: `2px solid ${cfg.cor}40`, background: '#111526' }}>
        <Modal.Title style={{ color: '#f1f5f9', fontSize: 16 }}>
          {cfg.icon} Nova Ação — {cfg.label}
        </Modal.Title>
        <button className="and-modal-close" onClick={onFechar}>✕</button>
      </Modal.Header>
      <Modal.Body style={{ background: '#111526' }}>
        {erro && <Alert variant="danger" className="py-2">{erro}</Alert>}
        <Form onSubmit={salvar}>
          {/* Área */}
          <Form.Group className="mb-3">
            <Form.Label className="and-form-label">Área</Form.Label>
            <div className="and-area-selector">
              {Object.entries(AREA_CFG).map(([key, c]) => (
                <button
                  key={key} type="button"
                  className={`and-area-btn ${form.area === key ? 'and-area-btn--ativa' : ''}`}
                  style={form.area === key
                    ? { background: c.cor, color: '#fff', borderColor: c.cor }
                    : { borderColor: c.cor + '50', color: c.cor }
                  }
                  onClick={() => setForm(f => ({ ...f, area: key, categoria: '' }))}
                >
                  {c.icon} {c.label}
                </button>
              ))}
            </div>
          </Form.Group>

          <div className="and-form-row">
            <Form.Group className="mb-3 flex-1">
              <Form.Label className="and-form-label">Linha</Form.Label>
              <Form.Select className="and-input" value={form.linha}
                onChange={e => setForm(f => ({ ...f, linha: e.target.value }))}>
                {linhas.map(l => <option key={l.linha_id} value={l.linha_id}>{l.linha_nome}</option>)}
              </Form.Select>
            </Form.Group>
            <Form.Group className="mb-3 flex-1">
              <Form.Label className="and-form-label">Categoria</Form.Label>
              <Form.Select className="and-input" value={form.categoria}
                onChange={e => setForm(f => ({ ...f, categoria: e.target.value }))}>
                <option value="">Selecione...</option>
                {catsFiltradas.map(c => <option key={c.id} value={c.id}>{c.nome}</option>)}
              </Form.Select>
            </Form.Group>
          </div>

          <Form.Group className="mb-3">
            <Form.Label className="and-form-label">Descrição da Ação</Form.Label>
            <Form.Control as="textarea" rows={3} className="and-input"
              placeholder="Descreva a ação para aumentar a velocidade..."
              value={form.descricao} required
              onChange={e => setForm(f => ({ ...f, descricao: e.target.value }))} />
          </Form.Group>

          <div className="and-form-row">
            <Form.Group className="mb-3 flex-1">
              <Form.Label className="and-form-label">Responsável</Form.Label>
              <Form.Control className="and-input" placeholder="Nome" value={form.responsavel} required
                onChange={e => setForm(f => ({ ...f, responsavel: e.target.value }))} />
            </Form.Group>
            <Form.Group className="mb-3 flex-1">
              <Form.Label className="and-form-label">Prazo</Form.Label>
              <Form.Control type="date" className="and-input" value={form.prazo_execucao} required
                onChange={e => setForm(f => ({ ...f, prazo_execucao: e.target.value }))} />
            </Form.Group>
          </div>

          <div className="and-modal-actions">
            <Button variant="secondary" onClick={onFechar} disabled={saving}>Cancelar</Button>
            <Button type="submit" disabled={saving} style={{ background: cfg.cor, border: 'none' }}>
              {saving ? <Spinner size="sm" /> : <><FaPlus size={12} /> Adicionar</>}
            </Button>
          </div>
        </Form>
      </Modal.Body>
    </Modal>
  );
}

// ── Modal Nova Leitura de Velocidade ─────────────────────────────────────────
// Recebe `card` com contexto da meta (linha + formato).
// Sempre MANUAL — o operador informa a velocidade atual para aquele formato.

function NovaLeituraModal({ card, onSalvar, onFechar }) {
  const [velocidade, setVelocidade] = useState('');
  const [saving, setSaving]         = useState(false);
  const [erro, setErro]             = useState('');

  async function salvar(e) {
    e.preventDefault();
    const vel = parseFloat(velocidade);
    if (!vel || vel <= 0) { setErro('Velocidade deve ser maior que zero.'); return; }
    setSaving(true);
    setErro('');
    try {
      await onSalvar({
        linha:      card.linha_id,
        meta:       card.meta_id,
        velocidade: vel,
        fonte:      'MANUAL',
      });
    } catch (err) {
      setErro(err.message);
      setSaving(false);
    }
  }

  return (
    <Modal show onHide={onFechar} centered className="and-modal">
      <Modal.Header style={{ borderBottom: '2px solid #3b82f640', background: '#111526' }}>
        <Modal.Title style={{ color: '#f1f5f9', fontSize: 16 }}>
          <FaTachometerAlt size={14} style={{ marginRight: 6 }} />
          Registrar Velocidade Atual
        </Modal.Title>
        <button className="and-modal-close" onClick={onFechar}>✕</button>
      </Modal.Header>
      <Modal.Body style={{ background: '#111526' }}>
        {/* Contexto da meta */}
        <div style={{
          background: '#1e2538', borderRadius: 8, padding: '10px 14px',
          marginBottom: 16, fontSize: 13, color: '#94a3b8',
          borderLeft: '3px solid #6366f1',
        }}>
          <strong style={{ color: '#f1f5f9' }}>{card.linha_nome}</strong>
          {' · '}
          <span style={{ color: '#818cf8' }}>📦 {card.formato_display}</span>
          <div style={{ marginTop: 4, fontSize: 12 }}>
            Esta velocidade ficará como referência até você registrar um novo valor.
          </div>
        </div>

        {erro && <Alert variant="danger" className="py-2">{erro}</Alert>}

        <Form onSubmit={salvar}>
          <Form.Group className="mb-3">
            <Form.Label className="and-form-label">
              Velocidade atual ({card.unidade || 'ppm'})
            </Form.Label>
            <Form.Control
              type="number" min="0.01" step="0.01" className="and-input"
              placeholder={`Ex: ${card.velocidade_meta?.toFixed(0) || '320'}`}
              value={velocidade} required autoFocus
              onChange={e => setVelocidade(e.target.value)}
            />
            <Form.Text style={{ color: '#64748b' }}>
              Meta Andretti: <strong style={{ color: '#6366f1' }}>{card.velocidade_meta?.toFixed(1)} ppm</strong>
              {' · '}Padrão: {card.velocidade_padrao?.toFixed(1)} ppm
            </Form.Text>
          </Form.Group>

          <div className="and-modal-actions">
            <Button variant="secondary" onClick={onFechar} disabled={saving}>Cancelar</Button>
            <Button type="submit" disabled={saving} style={{ background: '#3b82f6', border: 'none' }}>
              {saving ? <Spinner size="sm" /> : <><FaCheckCircle size={12} /> Confirmar</>}
            </Button>
          </div>
        </Form>
      </Modal.Body>
    </Modal>
  );
}

// ── Componente principal ─────────────────────────────────────────────────────

export default function AndrettiContent({ selectedLine }) {
  const [waves, setWaves]           = useState([]);
  const [waveAtiva, setWaveAtiva]   = useState(null);
  const [dashboard, setDashboard]   = useState(null);
  const [acoes, setAcoes]           = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [trends, setTrends]         = useState({});
  const [loadingTrend, setLoadingTrend] = useState({});
  const [filtroLinha, setFiltroLinha]   = useState('todas');
  const [modalArea, setModalArea]       = useState(null);
  const [modalLeitura, setModalLeitura] = useState(null); // card ou null
  const [loading, setLoading]           = useState(true);
  const [erro, setErro]                 = useState('');
  const [ultimaAtt, setUltimaAtt]       = useState(null);
  const pollRef = useRef(null);

  // Sincroniza filtro com a linha selecionada no sidebar
  useEffect(() => {
    if (selectedLine) setFiltroLinha(selectedLine);
  }, [selectedLine]);

  // Carrega waves
  useEffect(() => {
    apiFetch('/waves/')
      .then(data => {
        setWaves(data);
        const ativa = data.find(w => w.ativa) || data[0];
        if (ativa) setWaveAtiva(ativa.id);
      })
      .catch(e => setErro(e.message));
  }, []);

  // Carrega categorias uma vez
  useEffect(() => {
    apiFetch('/categorias/').then(setCategorias).catch(() => {});
  }, []);

  const carregarDashboard = useCallback(async (wId) => {
    if (!wId) return;
    try {
      const d = await apiFetch(`/dashboard/?wave=${wId}`);
      setDashboard(d);
      setUltimaAtt(new Date().toLocaleTimeString('pt-BR'));
      setErro('');
    } catch (e) {
      setErro(e.message);
    }
  }, []);

  const carregarAcoes = useCallback(async (wId) => {
    if (!wId) return;
    try {
      const d = await apiFetch(`/acoes/?wave=${wId}`);
      setAcoes(Array.isArray(d) ? d : d.results || []);
    } catch (e) {
      console.warn('Erro ao carregar ações:', e.message);
    }
  }, []);

  // Carrega ao trocar wave
  useEffect(() => {
    if (!waveAtiva) return;
    setLoading(true);
    Promise.all([carregarDashboard(waveAtiva), carregarAcoes(waveAtiva)])
      .finally(() => setLoading(false));

    // Poll automático
    clearInterval(pollRef.current);
    pollRef.current = setInterval(() => carregarDashboard(waveAtiva), POLL_MS);
    return () => clearInterval(pollRef.current);
  }, [waveAtiva, carregarDashboard, carregarAcoes]);

  const carregarTrend = useCallback(async (metaId, linhaId, formatoGramas) => {
    if (trends[metaId]) return;
    setLoadingTrend(p => ({ ...p, [metaId]: true }));
    try {
      const fmtParam = formatoGramas ? `&formato_gramas=${formatoGramas}` : '';
      const d = await apiFetch(`/velocidade/trend/${linhaId}/?horas=24${fmtParam}`);
      setTrends(p => ({ ...p, [metaId]: d.dados }));
    } catch (e) {
      console.warn('Erro trend:', e.message);
    } finally {
      setLoadingTrend(p => ({ ...p, [metaId]: false }));
    }
  }, [trends]);

  async function handleStatusChange(acaoId, novoStatus) {
    try {
      await apiFetch(`/acoes/${acaoId}/`, {
        method: 'PATCH',
        body: JSON.stringify({ status: novoStatus }),
      });
      setAcoes(prev => prev.map(a =>
        a.id === acaoId
          ? { ...a, status: novoStatus,
              data_realizada: novoStatus === 'concluida' ? new Date().toISOString().split('T')[0] : a.data_realizada }
          : a
      ));
    } catch (e) {
      alert('Erro ao atualizar: ' + e.message);
    }
  }

  async function handleNovaAcao(payload) {
    const nova = await apiFetch('/acoes/', { method: 'POST', body: JSON.stringify(payload) });
    setAcoes(prev => [...prev, nova]);
    setModalArea(null);
  }

  async function handleNovaLeitura(payload) {
    await apiFetch('/velocidade/leitura-manual/', { method: 'POST', body: JSON.stringify(payload) });
    setModalLeitura(null);
    carregarDashboard(waveAtiva);
  }

  const wave = waves.find(w => w.id === waveAtiva);
  const cards = dashboard?.cards || [];

  // Linhas únicas para filtro (nome da linha)
  const linhasUnicas = [...new Map(cards.map(c => [c.linha_nome, { id: c.linha_id, nome: c.linha_nome }])).values()];

  const cardsFiltrados = filtroLinha === 'todas'
    ? cards
    : cards.filter(c => c.linha_nome === filtroLinha);

  const metasAcimaDaMeta = cards.filter(c =>
    c.velocidade_atual != null && c.velocidade_meta != null &&
    c.velocidade_atual >= c.velocidade_meta
  ).length;

  const acoesDaWave = acoes.filter(a => a.wave === waveAtiva);

  return (
    <div className="and-root">
      {/* Header */}
      <div className="and-header">
        <div className="and-header-left">
          <span className="and-logo-emoji">🏎️</span>
          <div>
            <h1 className="and-title">ANDRETTI</h1>
            <p className="and-subtitle">Speed-Up Program · MIS Change Over</p>
          </div>
        </div>
        <div className="and-header-right">
          {waves.length > 0 && (
            <div className="and-wave-wrap">
              <label className="and-wave-label"><FaTachometerAlt size={12} /> Wave</label>
              <select className="and-wave-select" value={waveAtiva || ''}
                onChange={e => setWaveAtiva(Number(e.target.value))}>
                {waves.map(w => <option key={w.id} value={w.id}>{w.nome}</option>)}
              </select>
              {wave && (
                <span className="and-wave-dates">
                  {new Date(wave.data_inicio).toLocaleDateString('pt-BR')} →{' '}
                  {new Date(wave.data_fim).toLocaleDateString('pt-BR')}
                </span>
              )}
            </div>
          )}
          <div className="and-live-badge">
            <span className="and-live-dot" />
            <FaClock size={11} />
            {ultimaAtt || '—'}
          </div>
          <button className="and-btn-refresh" onClick={() => carregarDashboard(waveAtiva)}
            disabled={loading} title="Atualizar agora">
            <FaSync size={13} className={loading ? 'spin' : ''} />
          </button>
        </div>
      </div>

      {/* Erros */}
      {erro && (
        <Alert variant="warning" className="mx-3 mt-2 py-2">
          ⚠️ {erro} — verifique a conectividade com o backend.
        </Alert>
      )}

      {/* Sem waves */}
      {!loading && waves.length === 0 && (
        <div className="and-empty-state">
          <span>🏁</span>
          <h3>Nenhuma Wave cadastrada</h3>
          <p>Acesse o <a href="/admin/programa_andretti/waveandretti/add/" target="_blank" rel="noreferrer">Django Admin</a> para criar a primeira Wave Andretti.</p>
        </div>
      )}

      {loading && waves.length > 0 && (
        <div className="and-loading"><Spinner /> Carregando dados...</div>
      )}

      {!loading && dashboard && (
        <>
          {/* KPIs */}
          <div className="and-kpi-row">
            <div className="and-kpi-card" style={{ '--kc': '#22c55e' }}>
              <div className="and-kpi-icon" style={{ background: '#22c55e20', color: '#22c55e' }}>🏆</div>
              <div>
                <div className="and-kpi-val" style={{ color: '#22c55e' }}>
                  {metasAcimaDaMeta}/{cards.length}
                </div>
                <div className="and-kpi-lbl">Linhas acima da meta</div>
              </div>
            </div>
            <div className="and-kpi-card" style={{ '--kc': '#ef4444' }}>
              <div className="and-kpi-icon" style={{ background: '#ef444420', color: '#ef4444' }}>⚠️</div>
              <div>
                <div className="and-kpi-val" style={{ color: '#ef4444' }}>
                  {acoesDaWave.filter(a => a.status === 'aberta').length}
                </div>
                <div className="and-kpi-lbl">Ações abertas</div>
              </div>
            </div>
            <div className="and-kpi-card" style={{ '--kc': '#f59e0b' }}>
              <div className="and-kpi-icon" style={{ background: '#f59e0b20', color: '#f59e0b' }}>⏳</div>
              <div>
                <div className="and-kpi-val" style={{ color: '#f59e0b' }}>
                  {acoesDaWave.filter(a => a.status === 'em_andamento').length}
                </div>
                <div className="and-kpi-lbl">Em andamento</div>
              </div>
            </div>
            <div className="and-kpi-card" style={{ '--kc': '#6366f1' }}>
              <div className="and-kpi-icon" style={{ background: '#6366f120', color: '#6366f1' }}>✅</div>
              <div>
                <div className="and-kpi-val" style={{ color: '#6366f1' }}>
                  {acoesDaWave.filter(a => a.status === 'concluida').length}
                </div>
                <div className="and-kpi-lbl">Concluídas</div>
              </div>
            </div>
          </div>

          {/* Filtro de linha */}
          <div className="and-section-header">
            <h2 className="and-section-title"><FaTachometerAlt size={15} /> Velocidades por Formato</h2>
            <div className="and-filtro">
              <button className={`and-filter-btn ${filtroLinha === 'todas' ? 'active' : ''}`}
                onClick={() => setFiltroLinha('todas')}>Todas</button>
              {linhasUnicas.map(l => (
                <button key={l.id}
                  className={`and-filter-btn ${filtroLinha === l.nome ? 'active' : ''}`}
                  onClick={() => setFiltroLinha(l.nome)}>
                  {l.nome}
                </button>
              ))}
            </div>
          </div>

          {/* Grid de cards por formato */}
          {cardsFiltrados.length === 0 ? (
            <div className="and-empty-state">
              <span>📊</span>
              <p>Nenhuma meta cadastrada para esta wave. Configure no <a href="/admin/programa_andretti/metavelocidadelinha/add/" target="_blank" rel="noreferrer">Admin Django</a>.</p>
            </div>
          ) : (
            <div className="and-linhas-grid">
              {cardsFiltrados.map(c => (
                <FormatoCard
                  key={c.meta_id}
                  card={c}
                  trend={trends[c.meta_id] || []}
                  loadingTrend={!!loadingTrend[c.meta_id]}
                  onExpandTrend={carregarTrend}
                  onRegistrarVelocidade={setModalLeitura}
                />
              ))}
            </div>
          )}

          {/* Painel de ações */}
          <AcoesPainel
            acoes={acoes}
            waveId={waveAtiva}
            filtroLinha={filtroLinha}
            onStatusChange={handleStatusChange}
            onNovaAcao={area => setModalArea(area)}
          />
        </>
      )}

      {/* Modal Leitura — aberto por card específico */}
      {modalLeitura && (
        <NovaLeituraModal
          card={modalLeitura}
          onSalvar={handleNovaLeitura}
          onFechar={() => setModalLeitura(null)}
        />
      )}

      {/* Modal Ação */}
      {modalArea && (
        <NovaAcaoModal
          areaInicial={modalArea}
          waveId={waveAtiva}
          linhas={linhasUnicas.map(l => ({ linha_id: l.id, linha_nome: l.nome }))}
          categorias={categorias}
          onSalvar={handleNovaAcao}
          onFechar={() => setModalArea(null)}
        />
      )}
    </div>
  );
}
