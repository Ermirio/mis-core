/**
 * ReceitaMonitorContent — versão integrada (production-ready).
 *
 * Substitui a mock seedVariaveis() do protótipo (Receita Monitor.html / .jsx)
 * por chamadas reais ao Django + ao serviço mis-recipe-intelligent:
 *
 *   - GET  /api/recipe-monitor/linha/{nome}/formato-ativo/  (Django via useAxios)
 *       → formato REALMENTE rodando na máquina (OPC + fallback última troca)
 *         + valores da receita. Substitui o antigo dropdown de seleção manual,
 *         eliminando o risco de sincronizar no formato errado.
 *   - GET  /linhas/{nome}/snapshot              (recipe-monitor service)
 *       → estado atual + histórico
 *   - WS   /ws/linhas/{nome}/stream             (recipe-monitor service)
 *       → push de updates em tempo real
 *   - POST /linhas/{nome}/sincronizar           (recipe-monitor service)
 *       → repassado autenticado para Django PATCH (que revalida o formato ativo)
 *
 * Classificação (normal/atencao/alarme/semleitura) é refeita no frontend
 * porque depende do FORMATO detectado na máquina. O backend só sabe
 * tolerância e leitura atual; a receita vem do formato ativo.
 *
 * O JWT do operador é injetado automaticamente pelo useAxios (já tem
 * refresh automático). Para o WS, abrimos com query string ?token=...
 * porque headers customizados não são suportados no WebSocket browser API.
 * O serviço lê o token de Authorization header OU query param.
 */
import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  Card, Table, Button, Form, Modal, Spinner, Alert, InputGroup,
} from 'react-bootstrap';
import {
  AreaChart, Area, LineChart, Line, ReferenceLine, ReferenceArea,
  ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid,
} from 'recharts';
import {
  FaSyncAlt, FaCheckCircle, FaExclamationTriangle, FaExclamationCircle,
  FaQuestionCircle, FaChartLine, FaChevronDown, FaChevronUp,
  FaDatabase, FaMicrochip, FaServer, FaArrowUp, FaArrowDown, FaEquals,
  FaTimes, FaPlug, FaClock, FaInfoCircle, FaSearch, FaWaveSquare, FaArrowRight,
  FaLock,
} from 'react-icons/fa';
import useAxios from '../hooks/useAxios';
import { useAuth } from '../context/AuthContext';
import './ReceitaMonitorContent.css';

// URL base do serviço mis-recipe-intelligent.
//
// Resolução em ordem de prioridade:
//   1. REACT_APP_RECIPE_MONITOR_URL (build-time, .env)
//      Use isso em dev local quando o serviço roda em outra porta:
//      REACT_APP_RECIPE_MONITOR_URL=http://localhost:8100
//
//   2. Caminho relativo /recipe-monitor (default — produção atrás do proxy)
//      Funciona quando o nginx central (mis-core-proxy ou mis-change-over
//      proxy-nginx) tem location /recipe-monitor/ apontando para o serviço.
//      Mantém HTTPS, mesmo host, mesmo cookie — sem CORS.
function resolveRecipeMonitorBase() {
  const env = process.env.REACT_APP_RECIPE_MONITOR_URL;
  if (env && env.trim()) return env.replace(/\/+$/, '');
  // Default: mesmo host, caminho /recipe-monitor (atrás do proxy)
  if (typeof window !== 'undefined' && window.location) {
    return `${window.location.protocol}//${window.location.host}/recipe-monitor`;
  }
  return '/recipe-monitor';
}
const RM_BASE_URL = resolveRecipeMonitorBase();
const RM_WS_BASE_URL = RM_BASE_URL.replace(/^http/, 'ws');

const HIST_LEN = 60;

// Grupos autorizados a sincronizar receita com valores do CLP. Espelha o que
// está no backend (ips/permissions.py:PodeSincronizarReceita). O backend é
// quem realmente bloqueia — esta lista é só para UX (esconder/desabilitar
// o botão para quem não pode usar).
const GRUPOS_SYNC = ['TIM', 'Engenharia', 'Coordenacao', 'Coordenação'];

/* ════════════════════════════════════════════════════════════════════
   Palette + status definitions (idêntico ao protótipo JSX)
   ════════════════════════════════════════════════════════════════════ */
const C = {
  bg: '#f8f9fa', card: '#ffffff', border: '#dee2e6', borderStrong: '#ced4da',
  text1: '#212529', text2: '#495057', text3: '#6c757d',
  mono: "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
};

const STATUS = {
  alarme:     { key: 'alarme',     cor: '#dc3545', text: '#b02a37', bg: '#f8d7da', border: '#f1aeb5', label: 'Fora de faixa',      short: 'Fora de faixa',  Icon: FaExclamationCircle,   rank: 0 },
  atencao:    { key: 'atencao',    cor: '#ffc107', text: '#7a5c00', bg: '#fff3cd', border: '#ffe69c', label: 'Atenção / tolerado', short: 'Tolerado',       Icon: FaExclamationTriangle, rank: 1 },
  semleitura: { key: 'semleitura', cor: '#6c757d', text: '#5c636a', bg: '#e9ecef', border: '#ced4da', label: 'Sem leitura OPC',    short: 'Sem leitura',    Icon: FaQuestionCircle,      rank: 2 },
  normal:     { key: 'normal',     cor: '#28a745', text: '#1a7e34', bg: '#d1e7dd', border: '#a3cfbb', label: 'Dentro do tolerado', short: 'Normal',         Icon: FaCheckCircle,         rank: 3 },
};

const TIPO_META = {
  REAL:   { cor: '#0d6efd', desc: 'Ponto flutuante' },
  DINT:   { cor: '#6610f2', desc: 'Inteiro 32 bits' },
  UDINT:  { cor: '#6610f2', desc: 'Inteiro 32 bits sem sinal' },
  INT:    { cor: '#6610f2', desc: 'Inteiro 16 bits' },
  UINT:   { cor: '#6610f2', desc: 'Inteiro 16 bits sem sinal' },
  BOOL:   { cor: '#198754', desc: 'Booleano' },
  STRING: { cor: '#fd7e14', desc: 'Texto' },
};

/* ════════════════════════════════════════════════════════════════════
   Helpers
   ════════════════════════════════════════════════════════════════════ */
const NUM_TYPES = new Set(['REAL', 'DINT', 'UDINT', 'INT', 'UINT']);
const isNumeric = (t) => NUM_TYPES.has(t);

function fmtVal(v, tipo, casas = 2) {
  if (v === null || v === undefined) return '—';
  if (tipo === 'BOOL') {
    if (typeof v === 'boolean') return v ? 'TRUE' : 'FALSE';
    if (typeof v === 'string') return v.toUpperCase();
    return v ? 'TRUE' : 'FALSE';
  }
  if (tipo === 'STRING') return String(v);
  if (!isNumeric(tipo)) return String(v);
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  if (tipo !== 'REAL') return Math.round(n).toLocaleString('pt-BR');
  return n.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

function fmtHora(d) {
  return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// Data + hora completas (dd/mm HH:MM:SS) — usada na "última atualização" e
// no tooltip do gráfico, para mostrar também o DIA em que o valor mudou.
function fmtDataHora(d) {
  const data = d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
  return `${data} ${fmtHora(d)}`;
}

/** Parse de valor (string vinda do Django ou já tipado vindo do WS) para o tipo. */
function parseValor(raw, tipo) {
  if (raw === null || raw === undefined) return null;
  if (tipo === 'BOOL') {
    if (typeof raw === 'boolean') return raw;
    if (typeof raw === 'number') return raw !== 0;
    const s = String(raw).trim().toLowerCase();
    return ['true', '1', 'yes', 'on'].includes(s);
  }
  if (tipo === 'STRING') return String(raw);
  if (isNumeric(tipo)) {
    const n = Number(raw);
    return Number.isNaN(n) ? null : n;
  }
  return raw;
}

/** Espelha app/classifier.py — DEVE bater 1:1 com o backend. */
function classificar(v) {
  if (v.atual === null || v.atual === undefined) return STATUS.semleitura;
  if (v.tipo === 'BOOL' || v.tipo === 'STRING') {
    return v.atual === v.receita ? STATUS.normal : STATUS.alarme;
  }
  if (v.receita === null || v.receita === undefined) return STATUS.semleitura;
  const a = Number(v.atual);
  const r = Number(v.receita);
  if (Number.isNaN(a) || Number.isNaN(r)) return STATUS.alarme;
  const desvio = Math.abs(a - r);
  const tol = v.tolerancia;
  if (tol === null || tol === undefined || tol <= 0) {
    const epsilon = v.tipo === 'REAL' ? 1e-9 : 0.5;
    return desvio < epsilon ? STATUS.normal : STATUS.alarme;
  }
  if (desvio <= tol) return STATUS.normal;
  if (desvio <= tol * 2) return STATUS.atencao;
  return STATUS.alarme;
}

function delta(v) {
  if (v.atual === null || v.atual === undefined) return null;
  if (v.tipo === 'BOOL' || v.tipo === 'STRING') return v.atual === v.receita ? 0 : 1;
  if (v.receita === null || v.receita === undefined) return null;
  return Number(v.atual) - Number(v.receita);
}

/* ════════════════════════════════════════════════════════════════════
   Sub-componentes visuais (mesmas regras do protótipo)
   ════════════════════════════════════════════════════════════════════ */

function StatusBadge({ status, size = 'md' }) {
  const Icon = status.Icon;
  const pad = size === 'sm' ? '2px 8px' : '3px 10px';
  const fs = size === 'sm' ? 11 : 12;
  return (
    <span
      className="rm-status-badge"
      style={{ color: status.text, background: status.bg, border: `1px solid ${status.border}`, padding: pad, fontSize: fs }}
    >
      <Icon size={fs} color={status.cor} /> {status.short}
    </span>
  );
}

function DeltaCell({ v, status }) {
  const d = delta(v);
  if (d === null) return <span style={{ color: C.text3, fontFamily: C.mono }}>—</span>;
  if (v.tipo === 'BOOL' || v.tipo === 'STRING') {
    const igual = d === 0;
    return (
      <span style={{ fontFamily: C.mono, fontSize: 13, fontWeight: 600,
        color: igual ? STATUS.normal.text : STATUS.alarme.text,
        display: 'inline-flex', alignItems: 'center', gap: 5 }}>
        {igual ? <FaEquals size={11} /> : <FaTimes size={11} />}
        {igual ? 'igual' : 'difere'}
      </span>
    );
  }
  const casas = v.tipo === 'REAL' ? (v.tolerancia && v.tolerancia < 0.1 ? 3 : 2) : 0;
  const sinal = d > 0 ? '+' : '';
  const pct = v.receita !== 0 ? (d / v.receita) * 100 : null;
  const zero = Math.abs(d) < (v.tipo === 'REAL' ? 0.0005 : 0.5);
  const Arrow = zero ? FaEquals : d > 0 ? FaArrowUp : FaArrowDown;
  return (
    <span style={{ fontFamily: C.mono, fontSize: 13, fontWeight: 600, color: status.text,
      display: 'inline-flex', alignItems: 'center', gap: 5, justifyContent: 'flex-end' }}>
      <Arrow size={10} color={status.cor} />
      {sinal}{fmtVal(d, v.tipo, casas)}
      {pct !== null && <span style={{ color: C.text3, fontWeight: 500, fontSize: 11 }}>({sinal}{pct.toFixed(1)}%)</span>}
    </span>
  );
}

function Sparkline({ v, status }) {
  if (!isNumeric(v.tipo)) {
    return <span style={{ color: C.text3, fontSize: 11, fontFamily: C.mono }}>n/d</span>;
  }
  if (v.atual === null) {
    return <span style={{ color: STATUS.semleitura.text, fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      <FaPlug size={11} /> sem sinal</span>;
  }
  // Sort defensivo por timestamp — garante ordem cronológica mesmo se o
  // backend mudar de comportamento ou WS chegar fora de ordem.
  const data = [...(v.historico || [])]
    .sort((a, b) => a.t - b.t)
    .slice(-24)
    .map((p) => ({
      t: p.t, valor: typeof p.valor === 'number' ? p.valor : Number(p.valor),
    }));
  return (
    <LineChart width={120} height={34} data={data} margin={{ top: 4, right: 2, left: 2, bottom: 2 }}>
      {v.receita !== null && v.receita !== undefined && (
        <ReferenceLine y={Number(v.receita)} stroke={C.text3} strokeDasharray="2 2" strokeOpacity={0.55} />
      )}
      <Line type="monotone" dataKey="valor" stroke={status.cor} strokeWidth={1.6} dot={false} isAnimationActive={false} connectNulls />
    </LineChart>
  );
}

function TrendPanel({ v }) {
  if (!isNumeric(v.tipo)) {
    return (
      <div className="rm-trend-na">
        <FaInfoCircle size={14} />
        Variável do tipo <b>{v.tipo}</b> — sem gráfico de tendência. Estado atual:&nbsp;
        <b style={{ fontFamily: C.mono }}>{fmtVal(v.atual, v.tipo)}</b> · receita:&nbsp;
        <b style={{ fontFamily: C.mono }}>{fmtVal(v.receita, v.tipo)}</b>
      </div>
    );
  }
  const tol = v.tolerancia || 0;
  const r = Number(v.receita) || 0;
  // Sort defensivo por timestamp — garante ordem cronológica mesmo se o
  // backend mudar de comportamento ou WS chegar fora de ordem.
  const data = [...(v.historico || [])]
    .sort((a, b) => a.t - b.t)
    .map((p) => ({
      t: p.t,
      hora: fmtHora(new Date(p.t)),
      valor: typeof p.valor === 'number' ? p.valor : Number(p.valor),
    }));
  const vals = data.map((d) => d.valor).filter((x) => !Number.isNaN(x));
  const dataMin = vals.length ? Math.min(...vals) : r - tol;
  const dataMax = vals.length ? Math.max(...vals) : r + tol;
  const lo = Math.min(dataMin, r - tol * 2.5);
  const hi = Math.max(dataMax, r + tol * 2.5);
  const pad = (hi - lo) * 0.08 || 1;
  const domain = [Number((lo - pad).toFixed(3)), Number((hi + pad).toFixed(3))];
  const gid = `rm-grad-${v.id}`;
  const st = classificar(v);

  return (
    <div className="rm-trend-wrap">
      <div className="rm-trend-head">
        <span className="rm-trend-title"><FaChartLine size={13} /> Tendência — últimas {HIST_LEN} leituras OPC</span>
        <span className="rm-trend-legend">
          <span><i className="rm-leg-line" /> Receita ({fmtVal(r, v.tipo, 2)} {v.unidade})</span>
          {tol > 0 && <>
            <span><i className="rm-leg-band rm-leg-band--g" /> Tolerância ±{fmtVal(tol, v.tipo, tol < 0.1 ? 3 : 2)}</span>
            <span><i className="rm-leg-band rm-leg-band--y" /> Atenção ±{fmtVal(tol * 2, v.tipo, tol < 0.1 ? 3 : 2)}</span>
          </>}
        </span>
      </div>
      <div style={{ width: '100%', height: 230 }}>
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 8, right: 18, left: 0, bottom: 26 }}>
            <defs>
              <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={st.cor} stopOpacity={0.28} />
                <stop offset="100%" stopColor={st.cor} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#e9ecef" strokeDasharray="3 3" vertical={false} />
            {tol > 0 && <>
              <ReferenceArea y1={r - tol * 2} y2={r + tol * 2} fill="#ffc107" fillOpacity={0.10} ifOverflow="extendDomain" />
              <ReferenceArea y1={r - tol}     y2={r + tol}     fill="#28a745" fillOpacity={0.14} ifOverflow="extendDomain" />
            </>}
            <ReferenceLine y={r} stroke="#495057" strokeDasharray="6 4" strokeWidth={1.4}
              label={{ value: 'receita', position: 'right', fill: '#495057', fontSize: 11 }} />
            {/* Eixo X TEMPORAL (numérico): a posição horizontal é proporcional
                ao tempo real do relógio, não ao índice do ponto. Sem isso, leituras
                OPC esparsas (subscription só dispara em mudança de valor) ficavam
                espaçadas por índice e o rótulo fixo não batia com o tooltip. */}
            <XAxis
              dataKey="t"
              type="number"
              scale="time"
              domain={['dataMin', 'dataMax']}
              tick={{ fill: C.text3, fontSize: 10 }}
              angle={-45}
              textAnchor="end"
              height={40}
              tickMargin={6}
              tickCount={6}
              tickFormatter={(ms) => fmtHora(new Date(ms))}
            />
            <YAxis domain={domain} tick={{ fill: C.text3, fontSize: 11, fontFamily: C.mono }} width={56}
              allowDecimals tickFormatter={(t) => fmtVal(t, v.tipo, tol > 0 && tol < 0.1 ? 2 : 1)} />
            {/* labelFormatter: o label agora é epoch ms (dataKey="t"), então
                formatamos para HH:MM:SS no cabeçalho do tooltip. */}
            <Tooltip
              isAnimationActive={false}
              labelFormatter={(ms) => fmtDataHora(new Date(ms))}
              formatter={(val) => [fmtVal(val, v.tipo, tol > 0 && tol < 0.1 ? 3 : 2), v.unidade || 'valor']}
            />
            <Area type="monotone" dataKey="valor" stroke={st.cor} strokeWidth={2}
              fill={`url(#${gid})`} dot={false} isAnimationActive={false} connectNulls={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function SummaryCard({ status, count, active, onClick }) {
  const Icon = status.Icon;
  return (
    <button
      className={`rm-sum-card ${active ? 'rm-sum-card--on' : ''}`}
      onClick={onClick}
      style={active ? { borderColor: status.cor, boxShadow: `inset 0 0 0 1px ${status.cor}` } : null}
    >
      <span className="rm-sum-icon" style={{ background: status.bg, color: status.cor }}><Icon size={18} color={status.cor} /></span>
      <span className="rm-sum-meta">
        <span className="rm-sum-count" style={{ color: status.text }}>{count}</span>
        <span className="rm-sum-label">{status.label}</span>
      </span>
    </button>
  );
}

/* ════════════════════════════════════════════════════════════════════
   SyncModal — confirmação antes de gravar receita
   ════════════════════════════════════════════════════════════════════ */
function SyncModal({ formato, variaveis, onConfirm, onClose, saving }) {
  // Apenas variáveis com leitura que difere da receita atual
  const mudancas = variaveis.filter((v) => {
    if (v.atual === null || v.atual === undefined) return false;
    if (v.receita === null || v.receita === undefined) return true;
    if (v.tipo === 'BOOL' || v.tipo === 'STRING') return v.atual !== v.receita;
    return Math.abs(Number(v.atual) - Number(v.receita)) > (v.tipo === 'REAL' ? 1e-6 : 0.5);
  });

  return (
    <Modal show onHide={saving ? undefined : onClose} centered size="lg" backdrop="static">
      <Modal.Header className="rm-modal-head">
        <div>
          <Modal.Title className="rm-modal-title"><FaSyncAlt size={15} /> Atualizar receita com valores do CLP</Modal.Title>
          <div className="rm-modal-sub">Formato <b>{formato?.nome || '—'}</b> · {mudancas.length} variáve{mudancas.length === 1 ? 'l será alterada' : 'is serão alteradas'}</div>
        </div>
        {!saving && <button className="rm-modal-close" onClick={onClose} aria-label="Fechar"><FaTimes size={16} /></button>}
      </Modal.Header>
      <Modal.Body className="rm-modal-body">
        {mudancas.length === 0 ? (
          <div className="rm-modal-empty">
            <FaCheckCircle size={32} color={STATUS.normal.cor} />
            <p>Nenhuma divergência. A receita já corresponde aos valores lidos no CLP.</p>
          </div>
        ) : (
          <>
            <Alert variant="warning" className="rm-modal-alert">
              <FaExclamationTriangle size={14} /> Esta ação grava os valores atuais do CLP como a nova receita do formato. Confira cada mudança.
            </Alert>
            <div className="rm-modal-table-wrap">
              <table className="rm-modal-table">
                <thead>
                  <tr>
                    <th>Variável</th><th>Equipamento</th>
                    <th className="rm-num">Receita atual</th><th></th>
                    <th className="rm-num">Novo valor (CLP)</th><th className="rm-num">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {mudancas.map((v) => {
                    const d = isNumeric(v.tipo) && v.receita !== null && v.receita !== undefined
                      ? Number(v.atual) - Number(v.receita) : null;
                    const casas = v.tipo === 'REAL' ? (v.tolerancia && v.tolerancia < 0.1 ? 3 : 2) : 0;
                    return (
                      <tr key={v.id}>
                        <td><span className="rm-mt-name">{v.nome}</span><span className="rm-mt-unit"> {v.unidade}</span></td>
                        <td className="rm-mt-equip">{v.equip}</td>
                        <td className="rm-num rm-mt-old">{fmtVal(v.receita, v.tipo, casas)}</td>
                        <td className="rm-mt-arrow"><FaArrowRight size={12} color={C.text3} /></td>
                        <td className="rm-num rm-mt-new">{fmtVal(v.atual, v.tipo, casas)}</td>
                        <td className="rm-num" style={{ color: d > 0 ? STATUS.alarme.text : d < 0 ? '#0d6efd' : C.text3, fontWeight: 600 }}>
                          {d === null ? '—' : `${d > 0 ? '+' : ''}${fmtVal(d, v.tipo, casas)}`}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Modal.Body>
      <Modal.Footer className="rm-modal-foot">
        <Button variant="outline-secondary" onClick={onClose} disabled={saving}>Cancelar</Button>
        <Button variant="primary" onClick={() => onConfirm(mudancas)} disabled={saving || mudancas.length === 0} className="rm-btn-confirm">
          {saving ? <><Spinner size="sm" animation="border" /> Gravando…</> : <><FaCheckCircle size={13} /> Confirmar atualização</>}
        </Button>
      </Modal.Footer>
    </Modal>
  );
}

/* ════════════════════════════════════════════════════════════════════
   ReceitaMonitorContent
   ════════════════════════════════════════════════════════════════════ */
function ReceitaMonitorContent({ selectedLine }) {
  const api = useAxios();
  const apiRef = useRef(api);
  apiRef.current = api;
  const { authTokens, user } = useAuth();

  // Verifica se o usuário pode sincronizar (espelha o backend para boa UX).
  // O backend permanece a fonte da verdade — esta checagem só esconde/desabilita
  // o botão para quem não pode usar, evitando o "clica e ganha 403".
  const podeSincronizar = useMemo(() => {
    if (!user) return false;
    const groups = Array.isArray(user.groups) ? user.groups : [];
    return groups.some((g) => GRUPOS_SYNC.includes(g));
  }, [user]);

  // Superuser vê detalhes técnicos (stack OPC UA); usuário comum vê status
  // genérico. Vem do claim is_superuser do JWT.
  const isSuperuser = !!(user && user.is_superuser);

  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);
  const [snapshot, setSnapshot]     = useState(null);
  // Formato detectado na máquina (OPC / última troca). Substitui a seleção manual.
  const [formatoAtivo, setFormatoAtivo] = useState(null);
  const [opcOnline, setOpcOnline]   = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [filtro, setFiltro]         = useState(null);
  const [busca, setBusca]           = useState('');
  const [showSync, setShowSync]     = useState(false);
  const [saving, setSaving]         = useState(false);
  const [toast, setToast]           = useState(null);
  const wsRef = useRef(null);

  /* ── Carregamento inicial: snapshot + formatos ────────────────── */
  useEffect(() => {
    if (!selectedLine) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setSnapshot(null);

    const token = authTokens?.access;
    const headers = token ? { Authorization: `Bearer ${token}` } : {};

    Promise.all([
      fetch(`${RM_BASE_URL}/linhas/${selectedLine}/snapshot`, { headers })
        .then((r) => {
          if (!r.ok) throw new Error(`Recipe Monitor retornou ${r.status}`);
          return r.json();
        }),
      // Formato ATIVO detectado na máquina (OPC + fallback última troca).
      // Substitui a seleção manual — evita sincronizar no formato errado.
      apiRef.current.get(`/api/recipe-monitor/linha/${selectedLine}/formato-ativo/`),
    ])
      .then(([snap, faRes]) => {
        if (cancelled) return;
        setSnapshot(snap);
        setOpcOnline(!!snap.opc_online);
        setLastUpdate(snap.ultima_atualizacao_ms ? new Date(snap.ultima_atualizacao_ms) : new Date());
        setFormatoAtivo(faRes.data || null);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error('[ReceitaMonitor] erro carregando:', err);
        setError(err.message || 'Falha ao carregar dados do monitor');
        setLoading(false);
      });

    return () => { cancelled = true; };
  }, [selectedLine, authTokens?.access]);

  /* ── WebSocket: assina updates em tempo real ──────────────────── */
  useEffect(() => {
    if (!selectedLine || !snapshot) return;
    const token = authTokens?.access;
    const url = `${RM_WS_BASE_URL}/ws/linhas/${selectedLine}/stream${token ? `?token=${encodeURIComponent(token)}` : ''}`;

    let ws;
    try {
      ws = new WebSocket(url);
    } catch (e) {
      console.warn('[ReceitaMonitor] falha abrindo WS:', e);
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => console.log('[ReceitaMonitor] WS conectado em', selectedLine);
    ws.onerror = (e) => console.warn('[ReceitaMonitor] WS error:', e);
    ws.onclose = () => console.log('[ReceitaMonitor] WS desconectado de', selectedLine);

    ws.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }
      if (msg.tipo === 'update') {
        setSnapshot((prev) => {
          if (!prev) return prev;
          const variaveis = prev.variaveis.map((v) => {
            if (v.id !== msg.variavel_id) return v;
            // Insere o novo ponto na posição correta (caso WS chegue fora de ordem).
            const novo = { t: msg.timestamp_ms, valor: msg.valor };
            const hist = [...(v.historico || []), novo].sort((a, b) => a.t - b.t);
            if (hist.length > HIST_LEN) hist.splice(0, hist.length - HIST_LEN);
            return { ...v, atual: msg.valor, historico: hist, ultima_leitura_ms: msg.timestamp_ms };
          });
          return { ...prev, variaveis, ultima_atualizacao_ms: msg.timestamp_ms };
        });
        setLastUpdate(new Date(msg.timestamp_ms));
      } else if (msg.tipo === 'opc_status') {
        setOpcOnline(!!msg.online);
      }
      // ignora 'hello' e 'ping'
    };

    return () => {
      try { ws.close(); } catch {} // eslint-disable-line
    };
  }, [selectedLine, snapshot ? true : false, authTokens?.access]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Enriquecimento: aplica receita + tolerância da config ────── */
  // O formato é o DETECTADO na máquina — não há seleção manual.
  const formatoDetectado = formatoAtivo?.detectado ? formatoAtivo.formato : null;
  const formatoSelecionado = formatoDetectado; // nome mantido p/ o resto do componente

  const receitaPorVariavelId = useMemo(() => {
    if (!formatoSelecionado) return {};
    const m = {};
    (formatoSelecionado.variaveis || []).forEach((fv) => {
      const variavelId = fv.variavel?.id ?? fv.variavel_id;
      if (variavelId !== undefined) m[variavelId] = fv.valor;
    });
    return m;
  }, [formatoSelecionado]);

  const variaveisEnriquecidas = useMemo(() => {
    if (!snapshot) return [];
    return snapshot.variaveis.map((v) => {
      const receitaRaw = receitaPorVariavelId[v.id];
      const receita = receitaRaw !== undefined ? parseValor(receitaRaw, v.tipo) : null;
      const enriquecida = { ...v, receita };
      return { ...enriquecida, _status: classificar(enriquecida) };
    });
  }, [snapshot, receitaPorVariavelId]);

  const contagem = useMemo(() => {
    const c = { alarme: 0, atencao: 0, semleitura: 0, normal: 0 };
    variaveisEnriquecidas.forEach((v) => { c[v._status.key]++; });
    return c;
  }, [variaveisEnriquecidas]);

  const visiveis = useMemo(() => {
    let arr = variaveisEnriquecidas;
    if (filtro) arr = arr.filter((v) => v._status.key === filtro);
    if (busca.trim()) {
      const q = busca.trim().toLowerCase();
      arr = arr.filter((v) =>
        v.nome.toLowerCase().includes(q) ||
        v.equip.toLowerCase().includes(q) ||
        (v.clp || '').toLowerCase().includes(q)
      );
    }
    return [...arr].sort((a, b) => a._status.rank - b._status.rank || a.nome.localeCompare(b.nome));
  }, [variaveisEnriquecidas, filtro, busca]);

  const alarmes = variaveisEnriquecidas.filter((v) => v._status.key === 'alarme');

  /* ── Sincronizar ──────────────────────────────────────────────── */
  const handleConfirmSync = useCallback(async (mudancas) => {
    if (!formatoSelecionado) return;
    setSaving(true);
    try {
      const token = authTokens?.access;
      const headers = {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      };
      const body = {
        formato_id: formatoSelecionado.id,
        observacao: `Sincronizado via Recipe Monitor (linha ${selectedLine})`,
        variaveis: mudancas.map((v) => ({ variavel_id: v.id, valor: v.atual })),
      };
      const res = await fetch(`${RM_BASE_URL}/linhas/${selectedLine}/sincronizar`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : (data.detail?.detail || JSON.stringify(data));
        throw new Error(detail || `HTTP ${res.status}`);
      }
      setToast({
        tipo: 'success',
        msg: `Receita "${formatoSelecionado.nome}" atualizada — ${data.total_atualizadas || mudancas.length} variável(is) gravada(s).`,
      });
      // Reflete localmente as mudanças no formato detectado (otimista)
      setFormatoAtivo((prev) => {
        if (!prev?.formato || prev.formato.id !== formatoSelecionado.id) return prev;
        const updMap = Object.fromEntries(mudancas.map((m) => [m.id, m.atual]));
        return {
          ...prev,
          formato: {
            ...prev.formato,
            variaveis: (prev.formato.variaveis || []).map((fv) => {
              const id = fv.variavel?.id ?? fv.variavel_id;
              return updMap[id] !== undefined ? { ...fv, valor: String(updMap[id]) } : fv;
            }),
          },
        };
      });
      setShowSync(false);
    } catch (e) {
      console.error('[ReceitaMonitor] sincronizar falhou:', e);
      setToast({ tipo: 'danger', msg: `Falha ao gravar: ${e.message}` });
    } finally {
      setSaving(false);
    }
  }, [formatoSelecionado, selectedLine, authTokens?.access]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(t);
  }, [toast]);

  /* ── Render ───────────────────────────────────────────────────── */
  if (!selectedLine) {
    return (
      <div className="rm-root rm-center">
        <Alert variant="info">Selecione uma linha na lateral para começar.</Alert>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="rm-root rm-center">
        <div className="rm-loading-box">
          <Spinner animation="border" variant="primary" />
          <div className="rm-loading-txt">Conectando ao Recipe Monitor…</div>
          <div className="rm-loading-sub">Carregando variáveis da linha {selectedLine}</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rm-root rm-center">
        <Alert variant="danger">
          <Alert.Heading>Erro ao carregar o monitor</Alert.Heading>
          <p>{error}</p>
          <hr />
          <small className="text-muted">Verifique se o serviço <code>mis-recipe-intelligent</code> está rodando em <code>{RM_BASE_URL}</code> e se a linha <b>{selectedLine}</b> tem equipamentos OPC configurados no Django.</small>
        </Alert>
      </div>
    );
  }

  return (
    <div className="rm-root">
      <Card className="rm-card rm-header-card">
        <Card.Body className="rm-header">
          <div className="rm-header-left">
            <span className="rm-header-icon"><FaWaveSquare size={22} /></span>
            <div>
              <h1 className="rm-title">Monitor de Receita <span className="rm-title-sep">·</span> <span className="rm-title-line">{selectedLine}</span></h1>
              <div className="rm-subtitle">Sincronismo receita × CLP em tempo real · MIS Change Over</div>
            </div>
          </div>
          <div className="rm-header-right">
            {/* Usuário comum vê status genérico ("Sistema OK"); superuser vê o
                detalhe técnico ("OPC UA Conectado"). Não expõe a stack para
                operadores. */}
            <div className={`rm-opc ${opcOnline ? 'rm-opc--on' : 'rm-opc--off'}`}
                 title={isSuperuser ? 'Estado da conexão OPC UA' : 'Estado do sistema'}>
              <FaServer size={13} />
              {isSuperuser ? (
                <>
                  <span>OPC UA</span> <span className="rm-opc-dot" />
                  {opcOnline ? 'Conectado' : 'Offline'}
                </>
              ) : (
                <>
                  <span className="rm-opc-dot" />
                  {opcOnline ? 'Sistema OK' : 'Sistema indisponível'}
                </>
              )}
            </div>
            <div className="rm-live">
              <span className="rm-live-dot" />
              <FaClock size={12} />
              <span className="rm-live-time">{lastUpdate ? fmtDataHora(lastUpdate) : '—'}</span>
            </div>
          </div>
        </Card.Body>
      </Card>

      {toast && (
        <Alert variant={toast.tipo} className="rm-toast" dismissible onClose={() => setToast(null)}>
          <FaCheckCircle size={15} /> {toast.msg}
        </Alert>
      )}

      <div className="rm-strip">
        <div className="rm-summary">
          <SummaryCard status={STATUS.alarme}     count={contagem.alarme}     active={filtro === 'alarme'}     onClick={() => setFiltro(filtro === 'alarme' ? null : 'alarme')} />
          <SummaryCard status={STATUS.atencao}    count={contagem.atencao}    active={filtro === 'atencao'}    onClick={() => setFiltro(filtro === 'atencao' ? null : 'atencao')} />
          <SummaryCard status={STATUS.semleitura} count={contagem.semleitura} active={filtro === 'semleitura'} onClick={() => setFiltro(filtro === 'semleitura' ? null : 'semleitura')} />
          <SummaryCard status={STATUS.normal}     count={contagem.normal}     active={filtro === 'normal'}     onClick={() => setFiltro(filtro === 'normal' ? null : 'normal')} />
        </div>

        <Card className="rm-card rm-sync-card">
          <Card.Body className="rm-sync">
            <div className="rm-sync-label"><FaDatabase size={13} /> Sincronismo de receita</div>

            {/* Formato TRAVADO no que está rodando na máquina — sem seleção manual */}
            {formatoDetectado ? (
              <div className="rm-formato-lock" title="Formato detectado automaticamente na máquina">
                <div className="rm-formato-lock-top">
                  <FaLock size={11} />
                  <span className="rm-formato-lock-nome">{formatoDetectado.nome}</span>
                </div>
                <div className="rm-formato-lock-meta">
                  {formatoAtivo?.sku && <span className="rm-formato-lock-sku">SKU {formatoAtivo.sku}</span>}
                  <span className="rm-formato-lock-fonte">
                    {formatoAtivo?.fonte === 'opc'
                      ? 'detectado via OPC (SKU na máquina)'
                      : 'detectado via última troca'}
                  </span>
                </div>
              </div>
            ) : (
              <div className="rm-formato-lock rm-formato-lock--none" title="Não foi possível detectar o formato">
                <div className="rm-formato-lock-top">
                  <FaExclamationCircle size={11} />
                  <span className="rm-formato-lock-nome">Formato não detectado</span>
                </div>
                <div className="rm-formato-lock-meta">
                  <span className="rm-formato-lock-fonte">
                    {formatoAtivo?.mensagem || 'Realize uma troca de SKU nesta linha para habilitar o sincronismo.'}
                  </span>
                </div>
              </div>
            )}

            <Button className="rm-sync-btn" variant="primary"
              onClick={() => setShowSync(true)}
              disabled={!opcOnline || !formatoDetectado || !podeSincronizar}
              title={!podeSincronizar
                ? 'Você não tem permissão para sincronizar (grupos: TIM, Engenharia, Coordenação)'
                : (!opcOnline ? 'OPC offline' : (!formatoDetectado ? 'Formato da máquina não detectado' : ''))}>
              <FaSyncAlt size={13} /> Atualizar receita com valores do CLP
            </Button>
            {!podeSincronizar && (
              <small style={{ color: C.text3, fontSize: 11, marginTop: 4 }}>
                <FaInfoCircle size={10} /> Acesso restrito aos grupos TIM, Engenharia e Coordenação.
              </small>
            )}
          </Card.Body>
        </Card>
      </div>

      {alarmes.length > 0 && (
        <div className="rm-alarm-banner">
          <div className="rm-alarm-head">
            <FaExclamationCircle size={16} color="#fff" />
            {alarmes.length} variáve{alarmes.length === 1 ? 'l fora de faixa' : 'is fora de faixa'} — ação requerida
          </div>
          <div className="rm-alarm-list">
            {alarmes.map((v) => (
              <button key={v.id} className="rm-alarm-chip" onClick={() => { setFiltro(null); setBusca(''); setExpandedId(v.id); }}>
                <b>{v.nome}</b>
                <span>{v.equip}</span>
                <span className="rm-alarm-val">{fmtVal(v.atual, v.tipo, v.tolerancia && v.tolerancia < 0.1 ? 3 : 2)} {v.unidade}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {!opcOnline && (
        <Alert variant="danger" className="rm-opc-alert">
          <FaPlug size={15} />
          {isSuperuser ? (
            <> <b>Sem comunicação com o CLP via OPC UA.</b> Os valores em tempo real estão indisponíveis — exibindo apenas os valores da receita cadastrada.</>
          ) : (
            <> <b>Sistema temporariamente indisponível.</b> Os valores em tempo real estão indisponíveis — exibindo apenas os valores da receita cadastrada.</>
          )}
        </Alert>
      )}

      <Card className="rm-card rm-table-card">
        <div className="rm-table-toolbar">
          <div className="rm-table-title"><FaMicrochip size={15} /> Variáveis monitoradas <span className="rm-count">{visiveis.length}/{variaveisEnriquecidas.length}</span></div>
          <div className="rm-toolbar-right">
            {filtro && <button className="rm-clear-filter" onClick={() => setFiltro(null)}><FaTimes size={10} /> {STATUS[filtro].label}</button>}
            <InputGroup className="rm-search">
              <InputGroup.Text className="rm-search-icon"><FaSearch size={12} /></InputGroup.Text>
              <Form.Control placeholder="Buscar variável, equipamento ou CLP…" value={busca} onChange={(e) => setBusca(e.target.value)} />
            </InputGroup>
          </div>
        </div>

        <div className="rm-table-scroll">
          <Table className="rm-table" hover responsive>
            <thead>
              <tr>
                <th className="rm-th-status">Status</th>
                <th>Variável</th>
                <th>Equipamento</th>
                <th className="rm-th-tipo">Tipo</th>
                <th className="rm-num">Receita<span className="rm-th-sub">cadastrada</span></th>
                <th className="rm-num">Valor atual<span className="rm-th-sub">OPC UA</span></th>
                <th className="rm-num">Delta</th>
                <th className="rm-th-trend">Tendência</th>
                <th className="rm-th-exp"></th>
              </tr>
            </thead>
            <tbody>
              {visiveis.length === 0 && (
                <tr><td colSpan={9} className="rm-empty-row"><FaSearch size={20} /><span>Nenhuma variável corresponde ao filtro.</span></td></tr>
              )}
              {visiveis.map((v) => {
                const st = v._status;
                const isExp = expandedId === v.id;
                const casas = v.tipo === 'REAL' ? (v.tolerancia && v.tolerancia < 0.1 ? 3 : 2) : 0;
                const tipoMeta = TIPO_META[v.tipo] || { cor: '#6c757d' };
                return (
                  <React.Fragment key={v.id}>
                    <tr
                      className={`rm-row ${isExp ? 'rm-row--exp' : ''} ${st.key === 'alarme' ? 'rm-row--alarme' : ''}`}
                      style={st.key === 'alarme' || st.key === 'atencao'
                        ? { boxShadow: `inset 4px 0 0 ${st.cor}` } : null}
                      onClick={() => setExpandedId(isExp ? null : v.id)}
                    >
                      <td><StatusBadge status={st} /></td>
                      <td>
                        <div className="rm-var-name">{v.nome}</div>
                        {v.unidade && <div className="rm-var-unit">unidade: {v.unidade}</div>}
                      </td>
                      <td>
                        <div className="rm-equip">{v.equip}</div>
                        <div className="rm-equip-clp"><FaMicrochip size={9} /> {v.clp || '—'}</div>
                      </td>
                      <td><span className="rm-tipo" style={{ color: tipoMeta.cor, borderColor: tipoMeta.cor + '55', background: tipoMeta.cor + '12' }}>{v.tipo}</span></td>
                      <td className="rm-num rm-val-receita">{fmtVal(v.receita, v.tipo, casas)} {isNumeric(v.tipo) && v.unidade && <span className="rm-val-u">{v.unidade}</span>}</td>
                      <td className="rm-num">
                        {v.atual === null || v.atual === undefined
                          ? <span className="rm-noread"><FaQuestionCircle size={12} color={STATUS.semleitura.cor} /> sem leitura</span>
                          : <span className="rm-val-atual" style={{ color: st.text }}>{fmtVal(v.atual, v.tipo, casas)} {isNumeric(v.tipo) && v.unidade && <span className="rm-val-u">{v.unidade}</span>}</span>}
                      </td>
                      <td className="rm-num"><DeltaCell v={v} status={st} /></td>
                      <td className="rm-td-trend" onClick={(e) => e.stopPropagation()}><Sparkline v={v} status={st} /></td>
                      <td className="rm-td-exp">
                        <span className="rm-exp-btn" title={isExp ? 'Recolher' : 'Ver tendência'}>{isExp ? <FaChevronUp size={12} /> : <FaChevronDown size={12} />}</span>
                      </td>
                    </tr>
                    {isExp && (
                      <tr className="rm-exp-row">
                        <td colSpan={9}><TrendPanel v={v} /></td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </Table>
        </div>
        <div className="rm-table-foot">
          <span><FaInfoCircle size={11} /> Clique em uma linha para ver a tendência. Valores atualizam em tempo real via WebSocket.</span>
          <span className="rm-foot-formato"><FaDatabase size={11} /> Receita ativa: <b>{formatoSelecionado?.nome || '—'}</b></span>
        </div>
      </Card>

      {showSync && formatoSelecionado && (
        <SyncModal
          formato={formatoSelecionado}
          variaveis={variaveisEnriquecidas}
          onConfirm={handleConfirmSync}
          onClose={() => setShowSync(false)}
          saving={saving}
        />
      )}
    </div>
  );
}

export default ReceitaMonitorContent;
