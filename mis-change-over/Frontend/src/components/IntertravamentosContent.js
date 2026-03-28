import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  FaShieldAlt,
  FaCheckCircle,
  FaExclamationTriangle,
  FaTimesCircle,
  FaCog,
  FaIndustry,
  FaHistory,
  FaInfoCircle,
  FaPlug
} from 'react-icons/fa';
import useAxios from '../hooks/useAxios';
import './IntertravamentosContent.css';

const IntertravamentosContent = ({ selectedLine }) => {
  const api = useAxios();
  // Evita re-criação infinita do fetchData quando api muda a cada render
  const apiRef = useRef(api);
  apiRef.current = api;

  const [interlocks, setInterlocks] = useState({});
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Modal State
  const [modalOpen, setModalOpen] = useState(false);
  const [targetInterlock, setTargetInterlock] = useState(null);
  const [justification, setJustification] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // History Drawer State
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [historyData, setHistoryData] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Resync State
  const [resyncingId, setResyncingId] = useState(null);

  // Dependência apenas em selectedLine — api via ref para evitar loop infinito
  const fetchData = useCallback(async () => {
    if (!selectedLine) return;
    try {
      setLoading(prev => {
        // Só ativa loading na primeira carga (sem dados ainda)
        if (Object.keys(interlocks).length === 0) return true;
        return prev;
      });
      setError(null);

      const [summaryRes, itemsRes] = await Promise.all([
        apiRef.current.get(`/intertravamentos/status-summary/?linha=${selectedLine}`),
        apiRef.current.get(`/intertravamentos/por-linha/${selectedLine}/`),
      ]);

      setSummary(summaryRes.data);
      setInterlocks(itemsRes.data);
    } catch (err) {
      console.error("Erro ao carregar intertravamentos:", err);
      setError("Não foi possível carregar os dados. Verifique a conexão com o servidor.");
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedLine]);

  useEffect(() => {
    setInterlocks({});
    setSummary({});
    setLoading(true);
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleToggleClick = (item) => {
    setTargetInterlock(item);
    setJustification('');
    setModalOpen(true);
  };

  const submitToggle = async () => {
    if (!justification.trim() || !targetInterlock) return;
    try {
      setIsSubmitting(true);
      const payload = {
        habilitado: !targetInterlock.habilitado_software,
        observacao: justification.trim()
      };
      await apiRef.current.post(`/intertravamentos/${targetInterlock.id}/toggle/`, payload);
      setModalOpen(false);
      fetchData();
    } catch (err) {
      const msg = err.response?.data?.detail || err.response?.data?.error || "Erro ao alterar o estado. Tente novamente.";
      alert(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResync = async (item) => {
    setResyncingId(item.id);
    try {
      await apiRef.current.post(`/intertravamentos/${item.id}/resync/`);
      fetchData();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Erro ao sincronizar com o CLP.';
      alert(msg);
    } finally {
      setResyncingId(null);
    }
  };

  const openHistory = async (id) => {
    setDrawerOpen(true);
    setHistoryLoading(true);
    try {
      const res = await apiRef.current.get(`/intertravamentos/${id}/historico/`);
      setHistoryData(res.data);
    } catch (err) {
      console.error("Erro ao carregar histórico", err);
    } finally {
      setHistoryLoading(false);
    }
  };

  // ── Helpers de estado ──────────────────────────────────────────────────────
  const getCardState = (item) => {
    const swOn = item.habilitado_software;
    const opcOn = item.estado_opc;

    if (swOn && opcOn)   return 'ok';        // Ativo em ambos
    if (swOn && !opcOn)  return 'bypass';    // SW habilitado, CLP desabilitou
    if (!swOn && !opcOn) return 'clp-off';   // CLP desabilitou (software acompanhou ou desabilitado manualmente)
    if (!swOn && opcOn)  return 'sw-off';    // Desabilitado via software, CLP ainda ativo
    return 'ok';
  };

  const getStatusLabel = (state, item) => {
    switch (state) {
      case 'ok':      return { cls: 'active',   text: 'Monitoramento Ativo (CLP OK)' };
      case 'bypass':  return { cls: 'bypass',   text: 'ALERTA: CLP Desabilitou — Bypass Ativo!' };
      case 'clp-off': return { cls: 'clp',      text: `Desabilitado no CLP${!item.habilitado_software ? ' e Software' : ''}` };
      case 'sw-off':  return { cls: 'inactive', text: 'Desabilitado via Software (CLP Ativo)' };
      default:        return { cls: 'active',   text: 'OK' };
    }
  };

  const cardClassMap = {
    'ok':      'status-ok',
    'bypass':  'status-bypass',
    'clp-off': 'status-clp-off',
    'sw-off':  'status-offline',
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  if (!selectedLine) {
    return (
      <div className="intertravamentos-empty">
        <FaIndustry size={64} color="#CBD5E0" />
        <h3>Nenhuma Linha Selecionada</h3>
        <p>Selecione uma linha de produção para visualizar os intertravamentos.</p>
      </div>
    );
  }

  const hasData = Object.keys(interlocks).length > 0;
  const anyItems = hasData && Object.values(interlocks).some(arr => arr && arr.length > 0);

  return (
    <div className="intertravamentos-content">
      <div className="content-header">
        <div className="header-info">
          <h2 className="section-title">
            <FaShieldAlt className="title-icon" />
            Intertravamentos — {selectedLine}
          </h2>
          <span className="header-subtitle">
            Status em tempo real sincronizado com OPC UA. Alterações manuais requerem justificativa e são auditadas.
          </span>
        </div>
      </div>

      {error && (
        <div className="alert-error">{error}</div>
      )}

      {/* ── BADGES DE RESUMO ── */}
      <div className="stats-container">
        <div className="stat-badge habilitados">
          <FaCheckCircle className="stat-icon" color="var(--success-color)" />
          <div className="stat-info">
            <span className="stat-value">{summary.habilitados ?? '—'}</span>
            <span className="stat-label">Ativos no CLP</span>
          </div>
        </div>
        <div className="stat-badge desabilitados">
          <FaTimesCircle className="stat-icon" color="var(--warning-color)" />
          <div className="stat-info">
            <span className="stat-value">{summary.desabilitados_manual ?? '—'}</span>
            <span className="stat-label">Desab. Manual</span>
          </div>
        </div>
        <div className="stat-badge bypassed">
          <FaExclamationTriangle className="stat-icon" color="var(--error-color)" />
          <div className="stat-info">
            <span className="stat-value">{summary.bypassed_offline ?? '—'}</span>
            <span className="stat-label">Bypass CLP</span>
          </div>
        </div>
        <div className="stat-badge total">
          <FaCog className="stat-icon" color="var(--gray-500)" />
          <div className="stat-info">
            <span className="stat-value">{summary.total ?? '—'}</span>
            <span className="stat-label">Total</span>
          </div>
        </div>
      </div>

      {/* ── CONTEÚDO ── */}
      {loading && !hasData ? (
        <div className="loading-state">
          <div className="loading-spinner" />
          <span>Carregando dados estruturais...</span>
        </div>
      ) : !anyItems ? (
        <div className="empty-state">
          <FaPlug size={48} color="#CBD5E0" />
          <h3>Nenhum intertravamento cadastrado para {selectedLine}</h3>
          <p>Acesse o Admin para vincular controles a esta linha.</p>
        </div>
      ) : (
        Object.entries(interlocks).map(([areaName, itens]) => {
          if (!itens || itens.length === 0) return null;
          return (
            <div key={areaName} className="area-section">
              <h3 className="area-header">{areaName}</h3>
              <div className="interlocks-grid">
                {itens.map(item => {
                  const state = getCardState(item);
                  const status = getStatusLabel(state, item);
                  const cardCls = cardClassMap[state] || 'status-ok';

                  return (
                    <div key={item.id} className={`interlock-card ${cardCls}`}>
                      <div className="card-header">
                        <div className="card-title">
                          <div className="card-name-row">
                            <span className="card-name">{item.controle_nome}</span>
                            {item.controle_critico && (
                              <span className="badge-critico">Crítico</span>
                            )}
                          </div>
                          <span className="card-subtitle">{item.controle_area}</span>
                        </div>
                        <div className="toggle-container">
                          <span className="toggle-label">
                            {item.habilitado_software ? 'ON' : 'OFF'}
                          </span>
                          <label className="toggle-switch">
                            <input
                              type="checkbox"
                              checked={item.habilitado_software}
                              onChange={() => handleToggleClick(item)}
                            />
                            <span className="toggle-slider" />
                          </label>
                        </div>
                      </div>

                      <div className="card-body">
                        <div className="card-section">
                          <span className="card-section-label">Status CLP</span>
                          <div className={`status-indicator status-${status.cls}`}>
                            <span className={`status-dot dot-${status.cls}`} />
                            <span className="status-indicator-text">{status.text}</span>
                          </div>
                        </div>

                        {state === 'bypass' && (
                          <div className="bypass-alert-block">
                            <div className="bypass-alert-text">
                              <FaExclamationTriangle />
                              O CLP desativou este sensor após o último comando de habilitação. Alguém pode ter alterado o estado diretamente no CLP. Envie um novo comando para sincronizar.
                            </div>
                            <button
                              className="btn-resync"
                              onClick={() => handleResync(item)}
                              disabled={resyncingId === item.id}
                            >
                              <FaPlug />
                              {resyncingId === item.id ? 'Sincronizando...' : 'Sincronizar com CLP'}
                            </button>
                          </div>
                        )}

                        <div className="card-footer">
                          <span className="last-modified-text">
                            {item.modificado_por_nome
                              ? `Por: ${item.modificado_por_nome}`
                              : ''}
                          </span>
                          <button
                            className="btn-history"
                            onClick={() => openHistory(item.id)}
                          >
                            <FaHistory /> Histórico
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })
      )}

      {/* ── MODAL DE JUSTIFICATIVA ── */}
      {modalOpen && targetInterlock && (() => {
        const willEnable = !targetInterlock.habilitado_software;
        // Bypass real: software já habilitou E o CLP retornou desabilitado
        // → alguém acessou o CLP localmente e desativou sem passar pelo software
        const clpBypassAtivo = targetInterlock.habilitado_software && !targetInterlock.estado_opc;

        return (
          <div className="modal-overlay">
            <div className="justification-modal">
              <div className="modal-header">
                <h3>
                  <FaInfoCircle color="var(--primary-color)" />
                  {willEnable ? 'Habilitar' : 'Desabilitar'} Intertravamento
                </h3>
                <p>Controle: <strong>{targetInterlock.controle_nome}</strong></p>

                {clpBypassAtivo && (
                  <div className="modal-warn bypass-warn">
                    <FaExclamationTriangle />
                    <span>
                      O CLP está reportando este sensor como <strong>DESATIVADO</strong> apesar do software estar habilitado.
                      Isso indica que alguém alterou o estado diretamente no CLP. Ao desabilitar via software, o estado ficará consistente.
                    </span>
                  </div>
                )}

                {targetInterlock.controle_critico && (
                  <div className="modal-warn critico-warn">
                    <FaExclamationTriangle />
                    <span>
                      <strong>Controle crítico.</strong> Esta alteração será auditada e notificada aos supervisores.
                    </span>
                  </div>
                )}
              </div>

              <div className="form-group">
                <label htmlFor="justification">Justificativa (obrigatória)</label>
                <textarea
                  id="justification"
                  value={justification}
                  onChange={(e) => setJustification(e.target.value)}
                  placeholder="Ex: Necessário desabilitar para limpeza de linha. Autorizado por João Silva."
                  rows={4}
                />
              </div>

              <div className="modal-actions">
                <button
                  className="btn-cancel"
                  onClick={() => setModalOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancelar
                </button>
                <button
                  className={`btn-confirm ${!willEnable ? 'danger' : ''}`}
                  onClick={submitToggle}
                  disabled={!justification.trim() || isSubmitting}
                >
                  {isSubmitting ? 'Processando...' : 'Confirmar'}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* ── HISTORY DRAWER ── */}
      {drawerOpen && (
        <div className="history-drawer-overlay" onClick={() => setDrawerOpen(false)}>
          <div className="history-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <h3><FaHistory /> Histórico de Alterações</h3>
              <button className="btn-close" onClick={() => setDrawerOpen(false)}>&times;</button>
            </div>
            <div className="drawer-content">
              {historyLoading ? (
                <div className="loading-state"><div className="loading-spinner" /></div>
              ) : historyData.length === 0 ? (
                <div className="empty-history">Nenhum histórico registrado.</div>
              ) : (
                <div className="history-list">
                  {historyData.map((hist, idx) => (
                    <div
                      key={hist.id || idx}
                      className={`history-item ${hist.origem === 'OPC' ? 'opc-event' : ''}`}
                    >
                      <div className="history-meta">
                        <span className="history-user">
                          {hist.origem === 'OPC' ? '🔌 CLP/OPC UA' : (hist.usuario_nome || 'Sistema')}
                        </span>
                        <span>{new Date(hist.timestamp).toLocaleString('pt-BR')}</span>
                      </div>
                      <div className="history-change">
                        <span className={`status-tag ${hist.valor_anterior ? 'on' : 'off'}`}>
                          {hist.valor_anterior ? 'ON' : 'OFF'}
                        </span>
                        →
                        <span className={`status-tag ${hist.valor_novo ? 'on' : 'off'}`}>
                          {hist.valor_novo ? 'ON' : 'OFF'}
                        </span>
                        <span className="history-origin-badge origin-{hist.origem.toLowerCase()}">
                          {hist.origem}
                        </span>
                      </div>
                      {hist.observacao && (
                        <div className="history-obs">"{hist.observacao}"</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default IntertravamentosContent;
