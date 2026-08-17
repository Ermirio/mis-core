/**
 * ProductStatusContent.js — Status do Produto v9.4
 * KPIs ISA 101 em tempo real via OPC UA.
 * Auto-refresh a cada 5 segundos.
 * v9.4: painel colapsável de variáveis enviadas na última troca (ISA 101).
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  FaPlay, FaClock, FaLock, FaExclamationTriangle,
  FaSync, FaFlask, FaBox, FaWeightHanging,
  FaTachometerAlt, FaTrashAlt, FaIndustry, FaCheckCircle,
  FaWifi, FaTimesCircle, FaChevronDown, FaChevronRight,
  FaPrint, FaMicrochip, FaCheck, FaTimes,
} from 'react-icons/fa';
import useAxios from '../hooks/useAxios';

// ── ISA 101 status config ─────────────────────────────────────────────────────

const STATUS_CONFIG = {
  10: { label: 'Rodando',    color: '#28a745', bg: '#d4edda', icon: <FaPlay /> },
  20: { label: 'Aguardando', color: '#ffc107', bg: '#fff3cd', icon: <FaClock /> },
  30: { label: 'Bloqueado',  color: '#fd7e14', bg: '#fde8d0', icon: <FaLock /> },
  40: { label: 'Falha',      color: '#dc3545', bg: '#f8d7da', icon: <FaExclamationTriangle /> },
};

const STATUS_DESCONHECIDO = { label: '—', color: '#6c757d', bg: '#f8f9fa', icon: <FaIndustry /> };

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtNum(val, decimals = 1, suffix = '') {
  if (val == null || isNaN(val)) return '—';
  return Number(val).toFixed(decimals) + suffix;
}

function fmtSec(s) {
  if (s == null || isNaN(s)) return '—';
  const abs = Math.abs(s);
  const h = Math.floor(abs / 3600);
  const m = Math.floor((abs % 3600) / 60);
  const ss = Math.floor(abs % 60);
  const prefix = s < 0 ? '-' : '';
  if (h > 0) return `${prefix}${h}h ${String(m).padStart(2, '0')}m`;
  return `${prefix}${m}m ${String(ss).padStart(2, '0')}s`;
}

// ── Status Banner ─────────────────────────────────────────────────────────────

function StatusBanner({ statusCodigo, skuAtual, opcConfigurado }) {
  const cfg = STATUS_CONFIG[statusCodigo] ?? STATUS_DESCONHECIDO;

  return (
    <div
      className="d-flex align-items-center justify-content-between p-3 rounded mb-3"
      style={{ background: cfg.bg, border: `2px solid ${cfg.color}` }}
    >
      <div className="d-flex align-items-center gap-3">
        <span style={{ fontSize: '2.5rem', color: cfg.color }}>{cfg.icon}</span>
        <div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: cfg.color, lineHeight: 1 }}>
            {cfg.label}
          </div>
          <small className="text-muted">Status da Linha</small>
        </div>
      </div>

      <div className="text-end">
        {skuAtual ? (
          <>
            <div style={{ fontSize: '1.2rem', fontWeight: 600 }}>{skuAtual}</div>
            <small className="text-muted">SKU em operação</small>
          </>
        ) : (
          <small className="text-muted">SKU não identificado</small>
        )}
      </div>

      <div className="text-end">
        {opcConfigurado ? (
          <span className="badge bg-success"><FaWifi className="me-1" />OPC Online</span>
        ) : (
          <span className="badge bg-secondary"><FaTimesCircle className="me-1" />OPC não configurado</span>
        )}
      </div>
    </div>
  );
}

// ── KPI Card ──────────────────────────────────────────────────────────────────

function KpiCard({ icon, label, value, unit, highlight }) {
  return (
    <div
      className="card h-100 text-center"
      style={highlight ? { border: '2px solid #dc3545' } : {}}
    >
      <div className="card-body py-3">
        <div style={{ fontSize: '1.5rem', color: '#6c757d', marginBottom: 4 }}>{icon}</div>
        <div style={{ fontSize: '1.8rem', fontWeight: 700, lineHeight: 1.1 }}>
          {value}
          {unit && <small style={{ fontSize: '0.7rem', fontWeight: 400, marginLeft: 4 }}>{unit}</small>}
        </div>
        <div style={{ fontSize: '0.75rem', color: '#6c757d', marginTop: 4 }}>{label}</div>
      </div>
    </div>
  );
}

// ── Quality Timer Card ────────────────────────────────────────────────────────

function QualityTimerCard({ validacao }) {
  if (!validacao) return null;

  const pct = Math.min(100, Math.max(0, validacao.percentual_consumido || 0));
  const expirado = validacao.status === 'expirado' || validacao.tempo_restante_s < 0;
  const cor = expirado ? '#dc3545' : pct >= 75 ? '#ffc107' : '#28a745';

  return (
    <div className={`card mb-3 border-${expirado ? 'danger' : 'warning'}`}>
      <div className="card-body">
        <div className="d-flex justify-content-between align-items-center mb-2">
          <div className="d-flex align-items-center gap-2">
            <FaFlask style={{ color: cor }} />
            <strong>Validação de Qualidade</strong>
            <span className="badge" style={{ background: cor }}>
              {validacao.status_display}
            </span>
          </div>
          <small className="text-muted">SKU: {validacao.sku}</small>
        </div>

        <div className="progress mb-2" style={{ height: 12 }}>
          <div
            className="progress-bar"
            style={{ width: `${pct}%`, background: cor, transition: 'width 1s linear' }}
          />
        </div>

        <div className="d-flex justify-content-between">
          <small>Acumulado: <strong>{fmtSec(validacao.tempo_acumulado_s)}</strong> / {validacao.prazo_minutos} min</small>
          <small className={expirado ? 'text-danger fw-bold' : ''}>
            {expirado
              ? `Prazo esgotado ${fmtSec(Math.abs(validacao.tempo_restante_s))} atrás`
              : `Restam ${fmtSec(validacao.tempo_restante_s)}`}
          </small>
        </div>
      </div>
    </div>
  );
}

// ── ISA 101 color palette ─────────────────────────────────────────────────────

const ISA_OK   = { color: '#155724', bg: '#d4edda', border: '#28a745' };
const ISA_FAIL = { color: '#721c24', bg: '#f8d7da', border: '#dc3545' };
const ISA_WARN = { color: '#856404', bg: '#fff3cd', border: '#ffc107' };
const ISA_GRAY = { color: '#495057', bg: '#f8f9fa', border: '#6c757d' };

function equipStyle(status) {
  if (status === 'sucesso')         return ISA_OK;
  if (status === 'falha')           return ISA_FAIL;
  if (status === 'timeout')         return ISA_WARN;
  return ISA_GRAY; // nao_configurado
}

function tipoIcon(tipo) {
  if (tipo === 'impressora_3m' || tipo === 'impressora_inkjet') return <FaPrint />;
  return <FaMicrochip />;
}

// ── Equipment accordion card ──────────────────────────────────────────────────

function EquipCard({ log }) {
  const [open, setOpen] = useState(false);
  const s = equipStyle(log.status);
  const det = log.variaveis_detalhes || [];

  return (
    <div
      className="mb-2 rounded"
      style={{ border: `1px solid ${s.border}`, overflow: 'hidden' }}
    >
      {/* Header — clicável */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-100 text-start d-flex align-items-center gap-2 px-3 py-2"
        style={{
          background: s.bg, color: s.color, border: 'none', cursor: 'pointer',
          fontWeight: 600, fontSize: '0.88rem',
        }}
      >
        <span style={{ fontSize: '1rem' }}>{tipoIcon(log.tipo_equipamento)}</span>
        <span className="flex-grow-1">{log.nome_equipamento}</span>
        <span className="badge" style={{ background: s.border, color: '#fff', fontWeight: 500 }}>
          {log.variaveis_escritas}/{log.variaveis_total} vars
        </span>
        {log.tempo_execucao != null && (
          <small style={{ opacity: 0.75 }}>{log.tempo_execucao}s</small>
        )}
        {open ? <FaChevronDown size={12} /> : <FaChevronRight size={12} />}
      </button>

      {/* Detail table — collapsible */}
      {open && (
        <div style={{ background: '#fff', padding: '8px 12px' }}>
          {det.length === 0 ? (
            <small className="text-muted">Sem detalhe de variáveis registrado.</small>
          ) : (
            <table className="table table-sm table-borderless mb-0" style={{ fontSize: '0.8rem' }}>
              <thead>
                <tr style={{ color: '#6c757d', borderBottom: '1px solid #dee2e6' }}>
                  <th style={{ width: '30%' }}>Variável</th>
                  <th style={{ width: '30%' }}>Tag / Destino</th>
                  <th style={{ width: '30%' }}>Valor Enviado</th>
                  <th style={{ width: '10%', textAlign: 'center' }}>OK</th>
                </tr>
              </thead>
              <tbody>
                {det.map((v, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={{ fontWeight: 500 }}>{v.nome}</td>
                    <td style={{ color: '#6c757d', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                      {v.tag_plc || '—'}
                    </td>
                    <td style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {v.valor ?? '—'}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      {v.sucesso
                        ? <FaCheck style={{ color: '#28a745' }} />
                        : <FaTimes style={{ color: '#dc3545' }} />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {log.mensagem && (
            <small className="text-muted d-block mt-1">{log.mensagem}</small>
          )}
        </div>
      )}
    </div>
  );
}

// ── Última troca panel ────────────────────────────────────────────────────────

function UltimaTrocaPanel({ troca, logs }) {
  const [panelOpen, setPanelOpen] = useState(false);

  if (!troca) return null;

  const data = new Date(troca.data_hora).toLocaleString('pt-BR');
  const tudo_ok = logs.every(l => l.status === 'sucesso');
  const ps = tudo_ok ? ISA_OK : ISA_FAIL;

  return (
    <div className="card mb-3" style={{ border: `1px solid ${ps.border}` }}>
      {/* Panel header */}
      <button
        onClick={() => setPanelOpen(o => !o)}
        className="card-header d-flex align-items-center gap-2 w-100 text-start"
        style={{
          background: ps.bg, color: ps.color, border: 'none', cursor: 'pointer',
          fontWeight: 600,
        }}
      >
        <FaIndustry />
        <span className="flex-grow-1">
          Última Troca — <strong>{troca.sku}</strong>
          <small className="ms-2 fw-normal" style={{ opacity: 0.8 }}>{troca.descricao}</small>
        </span>
        <small style={{ opacity: 0.7 }}>{data}</small>
        <span className="badge ms-2" style={{ background: ps.border, color: '#fff' }}>
          {troca.equipamentos_sucesso}/{troca.equipamentos_processados} equip.
        </span>
        {panelOpen ? <FaChevronDown size={13} /> : <FaChevronRight size={13} />}
      </button>

      {panelOpen && (
        <div className="card-body py-2">
          {logs.length === 0 ? (
            <p className="text-muted mb-0">Nenhum log de equipamento registrado.</p>
          ) : (
            logs.map((log, i) => <EquipCard key={i} log={log} />)
          )}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

const REFRESH_MS = 5000;

const ProductStatusContent = ({ selectedLine }) => {
  const api = useAxios();
  const apiRef = useRef(api);
  apiRef.current = api;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [ultimaTroca, setUltimaTroca] = useState({ troca: null, logs: [] });

  const fetchStatus = useCallback(async () => {
    if (!selectedLine) return;
    try {
      setLoading(prev => data == null ? true : prev);
      const res = await apiRef.current.get(`/status-produto/${selectedLine}/`);
      setData(res.data);
      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao carregar status.');
    } finally {
      setLoading(false);
    }
  }, [selectedLine]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchUltimaTroca = useCallback(async () => {
    if (!selectedLine) return;
    try {
      const res = await apiRef.current.get(`/ultima-troca/${selectedLine}/`);
      setUltimaTroca({ troca: res.data.troca, logs: res.data.logs || [] });
    } catch (_) {}
  }, [selectedLine]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setData(null);
    setUltimaTroca({ troca: null, logs: [] });
    fetchStatus();
    fetchUltimaTroca();
    const id = setInterval(fetchStatus, REFRESH_MS);
    // ultima troca muda apenas quando uma troca ocorre — refresh a cada 30s é suficiente
    const id2 = setInterval(fetchUltimaTroca, 30000);
    return () => { clearInterval(id); clearInterval(id2); };
  }, [fetchStatus, fetchUltimaTroca]);

  // ── render ──────────────────────────────────────────────────────────────────

  if (!selectedLine) {
    return (
      <div className="p-4 text-center text-muted">
        <FaIndustry size={32} className="mb-2" />
        <p>Selecione uma linha para ver o status.</p>
      </div>
    );
  }

  if (loading && !data) {
    return (
      <div className="p-4 text-center text-muted">
        <FaSync className="spin mb-2" size={24} />
        <p>Carregando…</p>
      </div>
    );
  }

  if (error && !data) {
    return <div className="alert alert-danger m-3">{error}</div>;
  }

  const d = data || {};

  return (
    <div className="p-3">
      {/* Header */}
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h5 className="mb-0">
          <FaIndustry className="me-2 text-primary" />
          Status do Produto — {selectedLine}
        </h5>
        <div className="d-flex align-items-center gap-2">
          {lastUpdate && (
            <small className="text-muted">
              Atualizado: {lastUpdate.toLocaleTimeString('pt-BR')}
            </small>
          )}
          <button className="btn btn-sm btn-outline-secondary" onClick={fetchStatus} disabled={loading}>
            <FaSync className={loading ? 'spin me-1' : 'me-1'} />Atualizar
          </button>
        </div>
      </div>

      {/* Status banner */}
      <StatusBanner
        statusCodigo={d.status_codigo}
        skuAtual={d.sku_atual}
        opcConfigurado={d.opc_configurado}
      />

      {/* Quality timer (shown if active) */}
      <QualityTimerCard validacao={d.validacao_qualidade} />

      {/* KPI grid */}
      <div className="row g-3 mb-3">
        <div className="col-6 col-sm-4 col-xl-2">
          <KpiCard
            icon={<FaTachometerAlt />}
            label="Velocidade"
            value={fmtNum(d.velocidade, 0)}
            unit="un/min"
          />
        </div>
        <div className="col-6 col-sm-4 col-xl-2">
          <KpiCard
            icon={<FaWeightHanging />}
            label="Giveaway"
            value={fmtNum(d.giveaway, 2)}
            unit="g"
            highlight={d.giveaway > 5}
          />
        </div>
        <div className="col-6 col-sm-4 col-xl-2">
          <KpiCard
            icon={<FaTrashAlt />}
            label="Descartes Turno"
            value={fmtNum(d.descarte_turno, 0)}
            unit="un"
            highlight={d.descarte_turno > 100}
          />
        </div>
        <div className="col-6 col-sm-4 col-xl-2">
          <KpiCard
            icon={<FaWeightHanging />}
            label="Peso Médio"
            value={fmtNum(d.peso_medio, 1)}
            unit="g"
          />
        </div>
        <div className="col-6 col-sm-4 col-xl-2">
          <KpiCard
            icon={<FaBox />}
            label="Caixas Turno"
            value={fmtNum(d.caixas_turno, 0)}
          />
        </div>
        <div className="col-6 col-sm-4 col-xl-2">
          <KpiCard
            icon={<FaIndustry />}
            label="Toneladas Turno"
            value={fmtNum(d.toneladas_turno, 3)}
            unit="t"
          />
        </div>
      </div>

      {/* Última troca — variáveis enviadas por equipamento */}
      <UltimaTrocaPanel troca={ultimaTroca.troca} logs={ultimaTroca.logs} />

      {/* OPC not configured notice */}
      {!d.opc_configurado && (
        <div className="alert alert-secondary">
          <FaTimesCircle className="me-2" />
          Tags OPC não configuradas para esta linha. Configure o servidor OPC e as tags no Admin
          (Linhas → Status do Produto — Tags OPC v9.0).
        </div>
      )}

      {/* Validation OK badge */}
      {d.opc_configurado && !d.validacao_qualidade && d.status_codigo === 10 && (
        <div className="alert alert-success">
          <FaCheckCircle className="me-2" />
          Linha em operação — nenhuma validação de qualidade pendente.
        </div>
      )}

      <style>{`
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};

export default ProductStatusContent;
