/**
 * ValidacoesContent.js — Tela unificada de validações v9.0
 * Pipeline: SAP → Qualidade → Liberado
 * Abas: Aguardando Aprovação | Aprovados (histórico)
 * Paginação: 10 itens por aba
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import {
  FaCheckCircle, FaExclamationTriangle, FaHourglassHalf,
  FaLock, FaUnlock, FaSync, FaClipboardCheck, FaFlask,
  FaFileAlt, FaTimes, FaChevronLeft, FaChevronRight,
} from 'react-icons/fa';
import useAxios from '../hooks/useAxios';
import { useAuth } from '../context/AuthContext';

const PAGE_SIZE = 10;

// ── helpers ──────────────────────────────────────────────────────────────────

const ETAPA_LABEL = {
  aguarda_sap:       'Aguarda SAP',
  aguarda_qualidade: 'Aguarda Qualidade',
  sap_ok:            'SAP OK',
  liberado:          'Liberado',
};

const ETAPA_VARIANT = {
  aguarda_sap:       'danger',
  aguarda_qualidade: 'warning',
  sap_ok:            'info',
  liberado:          'success',
};

function etapaIcon(etapa) {
  switch (etapa) {
    case 'aguarda_sap':       return <FaLock className="me-1" />;
    case 'aguarda_qualidade': return <FaHourglassHalf className="me-1" />;
    case 'sap_ok':            return <FaFileAlt className="me-1" />;
    case 'liberado':          return <FaCheckCircle className="me-1" />;
    default:                  return null;
  }
}

function fmtSec(s) {
  if (s == null || isNaN(s)) return '—';
  const abs = Math.abs(s);
  const h = Math.floor(abs / 3600);
  const m = Math.floor((abs % 3600) / 60);
  const prefix = s < 0 ? '-' : '';
  return h > 0
    ? `${prefix}${h}h ${String(m).padStart(2, '0')}m`
    : `${prefix}${m}m`;
}

// ── Barra de progresso de CAIXAS (v11.0) ───────────────────────────────────────

function CaixasBar({ produzidas, meta, restantes, percentual, metaAtingida, status }) {
  if (!['pendente', 'expirado'].includes(status)) return null;
  if (!meta) {
    return (
      <div className="mt-2 text-muted" style={{ fontSize: '0.75rem' }}>
        Validação por caixas não configurada para este SKU/linha.
      </div>
    );
  }
  const pct = Math.min(100, Math.max(0, percentual || 0));
  const cor = metaAtingida || status === 'expirado'
    ? 'bg-danger'
    : pct >= 75
    ? 'bg-warning'
    : 'bg-success';

  return (
    <div className="mt-2">
      <div className="d-flex justify-content-between mb-1" style={{ fontSize: '0.75rem' }}>
        <span>Caixas produzidas (amostra)</span>
        <span className={metaAtingida ? 'text-danger fw-bold' : 'fw-semibold'}>
          {produzidas} / {meta} caixas
          {!metaAtingida && restantes > 0 && (
            <span className="text-muted"> (faltam {restantes})</span>
          )}
        </span>
      </div>
      <div className="progress" style={{ height: 10 }}>
        <div
          className={`progress-bar ${cor}`}
          style={{ width: `${pct}%`, transition: 'width 0.6s ease' }}
        >
          {pct >= 15 && <span style={{ fontSize: '0.65rem' }}>{pct}%</span>}
        </div>
      </div>
    </div>
  );
}

// ── PipelineBadge ─────────────────────────────────────────────────────────────

function PipelineBadge({ etapa }) {
  const variant = ETAPA_VARIANT[etapa] || 'secondary';
  return (
    <span className={`badge bg-${variant}`}>
      {etapaIcon(etapa)}{ETAPA_LABEL[etapa] || etapa}
    </span>
  );
}

// ── SAP Action card ───────────────────────────────────────────────────────────

function SAPCard({ item, podeLiberar, onLiberar }) {
  const [obs, setObs] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    await onLiberar(item.sku, item.linha || '', obs);
    setLoading(false);
    setObs('');
  }

  if (item.sap) {
    return (
      <div className="d-flex align-items-center gap-2 mt-2">
        <FaCheckCircle className="text-success" />
        <small className="text-muted">
          Liberado por <strong>{item.sap.liberado_por}</strong>{' '}
          em {new Date(item.sap.liberado_em).toLocaleString('pt-BR')}
          {item.sap.observacao && <> — {item.sap.observacao}</>}
        </small>
      </div>
    );
  }

  if (!podeLiberar) {
    return (
      <div className="d-flex align-items-center gap-2 mt-2 text-muted">
        <FaLock /> <small>Aguardando liberação do grupo SAP</small>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="mt-2 d-flex gap-2 align-items-end flex-wrap">
      <div className="flex-grow-1">
        <input
          className="form-control form-control-sm"
          placeholder="Observação (opcional)"
          value={obs}
          onChange={e => setObs(e.target.value)}
        />
      </div>
      <button className="btn btn-sm btn-success" disabled={loading} type="submit">
        {loading ? <FaSync className="spin" /> : <><FaUnlock className="me-1" />Liberar SAP</>}
      </button>
    </form>
  );
}

// ── Quality Action card ───────────────────────────────────────────────────────

function QualidadeCard({ item, podeAprovar, ehEngenheiro, onAprovar, onAprovarEngenheiro }) {
  const [loading, setLoading] = useState(false);
  const q = item.qualidade;

  if (!q) {
    if (ehEngenheiro) {
      return (
        <div className="mt-2">
          <small className="text-muted d-block mb-2">
            <FaHourglassHalf className="me-1" />Nenhuma troca realizada — engenheiro pode aprovar diretamente
          </small>
          <button
            className="btn btn-sm btn-warning"
            disabled={loading}
            onClick={async () => { setLoading(true); await onAprovarEngenheiro(); setLoading(false); }}
          >
            {loading ? <FaSync className="spin" /> : <><FaClipboardCheck className="me-1" />Aprovar (Bypass Engenheiro)</>}
          </button>
        </div>
      );
    }
    return (
      <div className="text-muted mt-2">
        <small><FaHourglassHalf className="me-1" />Qualidade iniciará após a primeira troca do SKU</small>
      </div>
    );
  }

  if (q.status === 'aprovado') {
    return (
      <div className="d-flex align-items-center gap-2 mt-2">
        <FaCheckCircle className="text-success" />
        <small className="text-muted">
          Aprovado por <strong>{q.aprovado_por}</strong>{' '}
          em {new Date(q.aprovado_em).toLocaleString('pt-BR')}
          {q.caixas_na_aprovacao != null && (
            <> — <strong>{q.caixas_na_aprovacao}</strong> caixas amostradas</>
          )}
        </small>
      </div>
    );
  }

  if (q.status === 'cancelado') {
    return (
      <div className="d-flex align-items-center gap-2 mt-2 text-muted">
        <FaTimes /><small> Cancelado — SKU substituído antes do prazo</small>
      </div>
    );
  }

  async function handleAprovar() {
    setLoading(true);
    await onAprovar(q.id);
    setLoading(false);
  }

  // Meta de caixas atingida → linha parada, aguardando aprovação da qualidade
  const paradoAguardando = q.meta_atingida || q.status === 'expirado';

  return (
    <div className="mt-2">
      <CaixasBar
        produzidas={q.caixas_produzidas}
        meta={q.quantidade_caixas_meta}
        restantes={q.caixas_restantes}
        percentual={q.percentual_caixas}
        metaAtingida={q.meta_atingida}
        status={q.status}
      />
      <div className="d-flex justify-content-between align-items-center mt-2 flex-wrap gap-2">
        <small className="text-muted">
          {paradoAguardando ? (
            <span className="badge bg-danger">
              <FaExclamationTriangle className="me-1" />Linha parada — aguardando validação
            </span>
          ) : (
            <>Meta: {q.quantidade_caixas_meta} caixas para validação</>
          )}
        </small>
        {podeAprovar && (
          <button
            className="btn btn-sm btn-primary"
            disabled={loading}
            onClick={handleAprovar}
          >
            {loading
              ? <FaSync className="spin" />
              : <><FaClipboardCheck className="me-1" />Aprovar Qualidade</>}
          </button>
        )}
      </div>
    </div>
  );
}

// ── SKU Card ──────────────────────────────────────────────────────────────────

function SkuCard({ item, selectedLine, podeLibSAP, podeAprQual, ehEngenheiro, onLiberarSAP, onAprovarQualidade, onAprovarQualidadeEngenheiro }) {
  const mostrarQualidade = item.sap || ehEngenheiro;
  return (
    <div className={`card h-100 border-${ETAPA_VARIANT[item.etapa] || 'secondary'}`}>
      <div className="card-body">
        <div className="d-flex justify-content-between align-items-start mb-1">
          <div>
            <strong className="d-block">{item.sku}</strong>
            <small className="text-muted">{item.descricao}</small>
          </div>
          <PipelineBadge etapa={item.etapa} />
        </div>

        <hr className="my-2" />

        {/* Step 1 — SAP */}
        <div className="mb-2">
          <div className="d-flex align-items-center gap-1 mb-1">
            <FaFileAlt className={item.sap ? 'text-success' : 'text-muted'} />
            <small className="fw-semibold">Lista Técnica SAP</small>
          </div>
          <SAPCard
            item={{ ...item, linha: selectedLine }}
            podeLiberar={podeLibSAP}
            onLiberar={onLiberarSAP}
          />
        </div>

        {/* Step 2 — Qualidade (engenheiro pode aprovar mesmo sem SAP ou sem troca prévia) */}
        {mostrarQualidade && (
          <div>
            <div className="d-flex align-items-center gap-1 mb-1">
              <FaFlask className={
                item.qualidade?.status === 'aprovado' ? 'text-success'
                : item.qualidade?.status === 'expirado' ? 'text-danger'
                : item.qualidade ? 'text-warning'
                : 'text-muted'
              } />
              <small className="fw-semibold">
                Validação Qualidade
                {ehEngenheiro && (
                  <span className="badge bg-warning text-dark ms-2" style={{ fontSize: '0.65rem' }}>
                    Bypass Engenheiro
                  </span>
                )}
              </small>
            </div>
            <QualidadeCard
              item={item}
              podeAprovar={podeAprQual}
              ehEngenheiro={ehEngenheiro}
              onAprovar={onAprovarQualidade}
              onAprovarEngenheiro={() => onAprovarQualidadeEngenheiro(item.sku, selectedLine)}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Pagination ────────────────────────────────────────────────────────────────

function Pagination({ page, totalPages, onChange }) {
  if (totalPages <= 1) return null;

  const pages = [];
  for (let i = 1; i <= totalPages; i++) pages.push(i);

  return (
    <nav className="d-flex justify-content-center align-items-center gap-1 mt-4">
      <button
        className="btn btn-sm btn-outline-secondary"
        disabled={page === 1}
        onClick={() => onChange(page - 1)}
      >
        <FaChevronLeft />
      </button>

      {pages.map(p => (
        <button
          key={p}
          className={`btn btn-sm ${p === page ? 'btn-primary' : 'btn-outline-secondary'}`}
          onClick={() => onChange(p)}
        >
          {p}
        </button>
      ))}

      <button
        className="btn btn-sm btn-outline-secondary"
        disabled={page === totalPages}
        onClick={() => onChange(page + 1)}
      >
        <FaChevronRight />
      </button>
    </nav>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

const ValidacoesContent = ({ selectedLine }) => {
  const api = useAxios();
  const apiRef = useRef(api);
  apiRef.current = api;
  const { user } = useAuth();

  const [pipeline, setPipeline] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);
  const [aba, setAba] = useState('pendentes'); // 'pendentes' | 'aprovados'
  const [pagePendentes, setPagePendentes] = useState(1);
  const [pageAprovados, setPageAprovados] = useState(1);

  const groups = user?.groups || [];
  const ehEngenheiro = groups.includes('Engenheiro');
  const podeLibSAP = groups.includes('SAP') || ehEngenheiro;
  const podeAprQual = groups.includes('Qualidade') || ehEngenheiro;

  // ── fetch ─────────────────────────────────────────────────────────────────

  const fetchPipeline = useCallback(async () => {
    if (!selectedLine) return;
    try {
      setLoading(true);
      setError(null);
      const res = await apiRef.current.get(`/validacoes/?linha=${selectedLine}`);
      setPipeline(res.data.pipeline || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao carregar validações.');
    } finally {
      setLoading(false);
    }
  }, [selectedLine]);

  useEffect(() => {
    fetchPipeline();
    const id = setInterval(fetchPipeline, 30_000);
    return () => clearInterval(id);
  }, [fetchPipeline]);

  // Resetar páginas ao trocar linha
  useEffect(() => {
    setPagePendentes(1);
    setPageAprovados(1);
  }, [selectedLine]);

  // ── split pipeline ────────────────────────────────────────────────────────

  const pendentes = pipeline.filter(i => i.etapa !== 'liberado');
  const aprovados = pipeline.filter(i => i.etapa === 'liberado');

  const totalPagesPendentes = Math.max(1, Math.ceil(pendentes.length / PAGE_SIZE));
  const totalPagesAprovados = Math.max(1, Math.ceil(aprovados.length / PAGE_SIZE));

  const paginaPendentes = pendentes.slice(
    (pagePendentes - 1) * PAGE_SIZE,
    pagePendentes * PAGE_SIZE,
  );
  const paginaAprovados = aprovados.slice(
    (pageAprovados - 1) * PAGE_SIZE,
    pageAprovados * PAGE_SIZE,
  );

  const itensDaAba = aba === 'pendentes' ? paginaPendentes : paginaAprovados;

  // ── actions ───────────────────────────────────────────────────────────────

  function showToast(msg, variant = 'success') {
    setToast({ msg, variant });
    setTimeout(() => setToast(null), 4000);
  }

  async function handleLiberarSAP(sku, linha, observacao) {
    try {
      const res = await apiRef.current.post('/validacoes/sap/liberar/', { sku, linha, observacao });
      const msg = res.data.criada
        ? `SAP liberado para ${sku}.`
        : `SAP já estava liberado para ${sku}.`;
      showToast(msg);
      await fetchPipeline();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Erro ao liberar SAP.', 'danger');
    }
  }

  async function handleAprovarQualidade(validacaoId) {
    try {
      await apiRef.current.post(`/validacoes/qualidade/${validacaoId}/aprovar/`);
      showToast('Qualidade aprovada com sucesso.');
      await fetchPipeline();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Erro ao aprovar qualidade.', 'danger');
    }
  }

  async function handleAprovarQualidadeEngenheiro(sku, linha) {
    try {
      await apiRef.current.post('/validacoes/qualidade/engenheiro-aprovar/', { sku, linha });
      showToast('Qualidade aprovada via bypass de engenheiro.');
      await fetchPipeline();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Erro ao aprovar.', 'danger');
    }
  }

  // ── render ────────────────────────────────────────────────────────────────

  if (!selectedLine) {
    return (
      <div className="p-4 text-center text-muted">
        <FaFlask size={32} className="mb-2" />
        <p>Selecione uma linha para ver as validações.</p>
      </div>
    );
  }

  return (
    <div className="p-3">
      {/* Toast */}
      {toast && (
        <div
          className={`alert alert-${toast.variant} alert-dismissible`}
          style={{ position: 'fixed', top: 16, right: 16, zIndex: 9999, minWidth: 300 }}
        >
          {toast.msg}
          <button className="btn-close" onClick={() => setToast(null)} />
        </div>
      )}

      {/* Header */}
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h5 className="mb-0">
          <FaFlask className="me-2 text-primary" />
          Validações — {selectedLine}
        </h5>
        <button className="btn btn-sm btn-outline-secondary" onClick={fetchPipeline} disabled={loading}>
          <FaSync className={loading ? 'spin me-1' : 'me-1'} />Atualizar
        </button>
      </div>

      {/* Error */}
      {error && <div className="alert alert-danger">{error}</div>}

      {/* Loading */}
      {loading && pipeline.length === 0 && (
        <div className="text-center text-muted py-5">
          <FaSync className="spin mb-2" size={24} />
          <p>Carregando pipeline…</p>
        </div>
      )}

      {/* Empty */}
      {!loading && pipeline.length === 0 && !error && (
        <div className="text-center text-muted py-5">
          <FaClipboardCheck size={32} className="mb-2" />
          <p>Nenhum SKU associado a esta linha.</p>
        </div>
      )}

      {pipeline.length > 0 && (
        <>
          {/* Abas */}
          <ul className="nav nav-tabs mb-3">
            <li className="nav-item">
              <button
                className={`nav-link ${aba === 'pendentes' ? 'active' : ''}`}
                onClick={() => setAba('pendentes')}
              >
                <FaHourglassHalf className="me-1" />
                Aguardando Aprovação
                {pendentes.length > 0 && (
                  <span className="badge bg-danger ms-2">{pendentes.length}</span>
                )}
              </button>
            </li>
            <li className="nav-item">
              <button
                className={`nav-link ${aba === 'aprovados' ? 'active' : ''}`}
                onClick={() => setAba('aprovados')}
              >
                <FaCheckCircle className="me-1" />
                Aprovados
                {aprovados.length > 0 && (
                  <span className="badge bg-success ms-2">{aprovados.length}</span>
                )}
              </button>
            </li>
          </ul>

          {/* Legend */}
          <div className="d-flex flex-wrap gap-2 mb-3">
            {Object.entries(ETAPA_LABEL)
              .filter(([key]) => aba === 'pendentes' ? key !== 'liberado' : key === 'liberado')
              .map(([key, label]) => (
                <span key={key} className={`badge bg-${ETAPA_VARIANT[key]}`}>
                  {etapaIcon(key)}{label}
                </span>
              ))}
          </div>

          {/* Empty tab state */}
          {itensDaAba.length === 0 && (
            <div className="text-center text-muted py-5">
              <FaClipboardCheck size={32} className="mb-2" />
              <p>
                {aba === 'pendentes'
                  ? 'Nenhum SKU aguardando aprovação.'
                  : 'Nenhum SKU aprovado ainda.'}
              </p>
            </div>
          )}

          {/* Cards */}
          <div className="row g-3">
            {itensDaAba.map(item => (
              <div key={item.sku} className="col-12 col-md-6 col-xl-4">
                <SkuCard
                  item={item}
                  selectedLine={selectedLine}
                  podeLibSAP={podeLibSAP}
                  podeAprQual={podeAprQual}
                  ehEngenheiro={ehEngenheiro}
                  onLiberarSAP={handleLiberarSAP}
                  onAprovarQualidade={handleAprovarQualidade}
                  onAprovarQualidadeEngenheiro={handleAprovarQualidadeEngenheiro}
                />
              </div>
            ))}
          </div>

          {/* Paginação */}
          {aba === 'pendentes' && (
            <Pagination
              page={pagePendentes}
              totalPages={totalPagesPendentes}
              onChange={setPagePendentes}
            />
          )}
          {aba === 'aprovados' && (
            <Pagination
              page={pageAprovados}
              totalPages={totalPagesAprovados}
              onChange={setPageAprovados}
            />
          )}

          {/* Contador */}
          {itensDaAba.length > 0 && (
            <p className="text-center text-muted mt-2" style={{ fontSize: '0.8rem' }}>
              {aba === 'pendentes'
                ? `${pendentes.length} SKU(s) aguardando — página ${pagePendentes} de ${totalPagesPendentes}`
                : `${aprovados.length} SKU(s) aprovados — página ${pageAprovados} de ${totalPagesAprovados}`}
            </p>
          )}
        </>
      )}

      <style>{`
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .nav-tabs .nav-link { cursor: pointer; border: none; background: none; }
        .nav-tabs .nav-link.active {
          border-bottom: 2px solid #0d6efd;
          font-weight: 600;
          color: #0d6efd;
        }
        .nav-tabs .nav-link:hover:not(.active) { color: #495057; }
      `}</style>
    </div>
  );
};

export default ValidacoesContent;
