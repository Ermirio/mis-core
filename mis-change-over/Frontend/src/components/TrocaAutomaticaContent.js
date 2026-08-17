/**
 * @file TrocaAutomaticaContent.js
 * @description Componente React para gerenciamento de sincronização de SKUs e histórico de trocas.
 * Esta versão inclui funcionalidades avançadas como paginação, feedback de usuário aprimorado
 * e integração com configurações centralizadas via variáveis de ambiente.
 *
 * @version 6.2.8 - Implementação de Autenticação JWT e Autorização.
 * @author Process Engineer
 */

// Importações de React e Hooks
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useAuth } from '../context/AuthContext'; // NOVO: Importar useAuth
import useAxios from '../hooks/useAxios'; // NOVO: Importar useAxios
import { trocaAutomaticaService } from '../services/trocaAutomaticaService'; // NOVO: Importar Service

// Importações de Bootstrap e Ícones
import {
  Card, Button, Table, Modal, Spinner, Alert, Form, InputGroup, Badge,
  Row, Col, Container, Toast, ToastContainer, ProgressBar, Accordion,
  Tabs, Tab, Pagination
} from 'react-bootstrap';
import {
  FaSyncAlt, FaPaperPlane, FaSearch, FaInfoCircle, FaExclamationTriangle,
  FaHistory, FaCheckCircle, FaTimesCircle, FaWifi, FaClock, FaDatabase,
  FaChartLine, FaFilter, FaCogs, FaPrint, FaIndustry,
  FaHourglassHalf, FaRedo
} from 'react-icons/fa';

// --- Constantes de configuração ---
const DJANGO_HEALTH_CHECK_INTERVAL = parseInt(process.env.REACT_APP_DJANGO_HEALTH_CHECK_INTERVAL, 10) || 30000;
const DJANGO_HEALTH_CHECK_TIMEOUT = parseInt(process.env.REACT_APP_DJANGO_HEALTH_CHECK_TIMEOUT, 10) || 15000;
const DEFAULT_PAGE_SIZE = parseInt(process.env.REACT_APP_DEFAULT_PAGE_SIZE, 10) || 10;
const POST_TROCA_RELOAD_DELAY = parseInt(process.env.REACT_APP_POST_TROCA_RELOAD_DELAY, 10) || 1000;
const TOAST_DURATION = parseInt(process.env.REACT_APP_TOAST_DURATION, 10) || 5000;

// Componente auxiliar para destacar texto na busca
const HighlightText = ({ text, highlight }) => {
  if (!highlight || !text) return text;
  const parts = text.toString().split(new RegExp(`(${highlight})`, 'gi'));
  return (
    <>
      {parts.map((part, i) =>
        part.toLowerCase() === highlight.toLowerCase() ?
          <span key={i} className="bg-warning text-dark px-1 rounded">{part}</span> : part
      )}
    </>
  );
};

const TrocaAutomaticaContent = ({ selectedLine }) => {
  const { authTokens } = useAuth(); // NOVO: Obter tokens do contexto
  const api = useAxios(); // NOVO: Usar o hook useAxios

  // --- Estados do Componente ---
  const [skus, setSkus] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [feedback, setFeedback] = useState({ message: '', type: '' });

  const [djangoStatus, setDjangoStatus] = useState('checking');
  const [lastCheck, setLastCheck] = useState(null);

  const [showModal, setShowModal] = useState(false);
  const [selectedSku, setSelectedSku] = useState(null);
  const [sendingTroca, setSendingTroca] = useState(false);
  const [modalError, setModalError] = useState(null);
  const [progress, setProgress] = useState(0); // NOVO: Progresso da troca
  const [retryMode, setRetryMode] = useState(false); // NOVO: Modo de re-tentativa
  const [showPrimeiraRodadaAviso, setShowPrimeiraRodadaAviso] = useState(false); // Aviso primeira rodada

  const [historico, setHistorico] = useState([]);
  const [loadingHistorico, setLoadingHistorico] = useState(false);
  const [activeTab, setActiveTab] = useState('sincronizar');

  const [paginacao, setPaginacao] = useState({
    page: 1,
    per_page: DEFAULT_PAGE_SIZE,
    total_pages: 1,
    total_items: 0,
    has_next: false,
    has_previous: false,
    start_index: 0,
    end_index: 0
  });

  const [toasts, setToasts] = useState([]);
  const [stats, setStats] = useState({ total: 0, ativos: 0, sincronizados: 0 });

  // --- Funções Auxiliares (com useCallback e dependências estritas) ---

  const addToast = useCallback((message, type = 'info', duration = TOAST_DURATION) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(toast => toast.id !== id));
    }, duration);
  }, []); // TOAST_DURATION é uma constante, não é uma dependência dinâmica.

  const checkDjangoStatus = useCallback(async () => {
    const isConnected = await trocaAutomaticaService.checkHealth();
    setDjangoStatus(isConnected ? 'connected' : 'disconnected');
    setLastCheck(new Date());
    return isConnected;
  }, []);

  const formatDate = useCallback((dateString) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleString('pt-BR');
    } catch {
      return dateString;
    }
  }, []);

  const getStatusText = useCallback((resumo_execucao) => {
    if (!resumo_execucao || resumo_execucao.total_equipamentos === 0) {
      return 'Sem Status';
    }
    if (resumo_execucao.taxa_sucesso === 100) {
      return 'Sucesso Total';
    } else if (resumo_execucao.taxa_sucesso > 0 && resumo_execucao.taxa_sucesso < 100) {
      return 'Sucesso Parcial';
    } else {
      return 'Falha Total';
    }
  }, []);

  const getStatusIcon = useCallback((status) => {
    switch (status) {
      case 'success': return <FaCheckCircle className="text-success" />;
      case 'warning': return <FaExclamationTriangle className="text-warning" />;
      case 'danger': return <FaTimesCircle className="text-danger" />;
      default: return <FaHourglassHalf className="text-secondary" />;
    }
  }, []);

  const getEquipmentIcon = useCallback((tipo) => {
    switch (tipo) {
      case 'enchedora': return <FaIndustry className="text-primary" />;
      case 'equipamento': return <FaCogs className="text-info" />;
      case 'inkjetprinter': return <FaPrint className="text-secondary" />;
      case 'impressora_3m': return <FaPrint className="text-secondary" />;
      case 'impressora_inkjet': return <FaPrint className="text-secondary" />;
      default: return <FaCogs className="text-muted" />;
    }
  }, []);

  const handleCloseModal = useCallback(() => {
    setSelectedSku(null);
    setShowModal(false);
    setSendingTroca(false);
    setModalError(null);
    setProgress(0);
    setRetryMode(false);
    setShowPrimeiraRodadaAviso(false);
  }, []);

  const handleShowModal = useCallback((sku) => {
    setSelectedSku(sku);
    if (!sku.ja_rodou_nesta_linha) {
      setShowPrimeiraRodadaAviso(true);
    } else {
      setShowModal(true);
    }
  }, []);

  // loadHistorico precisa ser definido ANTES de handleConfirmSend
  const loadHistorico = useCallback(async (page = 1, perPage = DEFAULT_PAGE_SIZE) => {
    if (!selectedLine) {
      setHistorico([]);
      addToast("Selecione uma linha para carregar o histórico.", 'warning');
      return;
    }
    if (djangoStatus !== 'connected') {
      // Optional: try anyway or respect status.
    }

    setLoadingHistorico(true);
    try {
      const data = await trocaAutomaticaService.getHistorico(api, selectedLine, page, perPage);

      const historicoData = data.ultimas_trocas || [];
      const paginacaoData = data.paginacao || {};

      setHistorico(historicoData);
      setPaginacao(paginacaoData);

      if (historicoData.length > 0) {
        addToast(`Histórico carregado: ${historicoData.length} trocas (página ${page} de ${paginacaoData.total_pages}).`, 'info');
      } else {
        addToast(`Nenhum histórico encontrado para a página ${page}.`, 'info');
      }
    } catch (err) {
      console.error("Erro loadHistorico:", err);
      setHistorico([]);
      setPaginacao(prev => ({ ...prev, total_items: 0, total_pages: 1, page: 1 }));
      addToast('Erro ao carregar histórico.', 'danger');
    } finally {
      setLoadingHistorico(false);
    }
  }, [selectedLine, djangoStatus, addToast, api]);

  const handleSyncSkus = useCallback(async () => {
    if (!selectedLine) {
      setError("Por favor, selecione uma linha primeiro na barra lateral.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setFeedback({ message: '', type: '' });

    try {
      const data = await trocaAutomaticaService.getSkus(api, selectedLine);
      const skusData = data.skus || [];
      setSkus(skusData);

      const total = skusData.length;
      const ativos = skusData.filter(sku => sku.status_op === 'Ativa').length;
      setStats({ total, ativos, sincronizados: total });

      setFeedback({
        message: data.mensagem || `${total} SKUs sincronizados com sucesso! (${ativos} ativos).`,
        type: 'success'
      });
      addToast(data.mensagem || `Sincronização concluída: ${total} SKUs encontrados.`, 'success');

    } catch (err) {
      const msg = err.response?.data?.mensagem || err.message;
      setError(`Erro na sincronização de SKUs: ${msg}`);
      setSkus([]);
      addToast(`Erro na sincronização: ${msg}.`, 'danger');
    } finally {
      setIsLoading(false);
    }
  }, [selectedLine, djangoStatus, addToast, api]);

  const filteredSkus = useMemo(() => {
    if (!searchTerm) return skus;
    const term = searchTerm.toLowerCase();
    return skus.filter(sku =>
      sku.numero_op && sku.numero_op.toLowerCase().includes(term)
    );
  }, [skus, searchTerm]);

  const handlePageChange = useCallback((newPage) => {
    loadHistorico(newPage, paginacao.per_page);
  }, [loadHistorico, paginacao.per_page]);

  const handlePerPageChange = useCallback((newPerPage) => {
    loadHistorico(1, parseInt(newPerPage));
  }, [loadHistorico]);

  const handleConfirmSend = useCallback(async () => {
    if (!selectedSku || !selectedLine) {
      setModalError("SKU ou linha não selecionada.");
      return;
    }

    setSendingTroca(true);
    setModalError(null);
    setError(null);
    setFeedback({ message: '', type: '' });
    setProgress(10); // Iniciar progresso

    // Simulação de progresso enquanto aguarda a resposta
    const progressInterval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 90) return prev;
        return prev + Math.random() * 10;
      });
    }, 500);

    try {
      const payload = {
        linha: selectedLine,
        sku: selectedSku.codigo_sku,
        descricao: selectedSku.descricao_sku,
        dun14: selectedSku.dun14,
        validade: selectedSku.validade,
        numero_op: selectedSku.numero_op,
        retry: retryMode
      };

      const data = await trocaAutomaticaService.trocarSku(api, payload);

      clearInterval(progressInterval);
      setProgress(100);

      if (data.sucesso) {
        setFeedback({
          message: data.mensagem || `${data.resumo_execucao.sucessos}/${data.resumo_execucao.total_equipamentos} equipamentos configurados com sucesso.`,
          type: 'success'
        });
        addToast(data.mensagem || `Troca de ${selectedSku.codigo_sku} realizada.`, 'success');
      } else {
        setFeedback({
          message: data.mensagem || `${data.resumo_execucao.falhas} equipamentos com problemas.`,
          type: 'warning'
        });
        addToast(data.mensagem || `Troca parcial.`, 'warning');
      }

      setTimeout(() => {
        loadHistorico(paginacao.page, paginacao.per_page);
      }, POST_TROCA_RELOAD_DELAY);

      // Pequeno delay para fechar o modal e mostrar 100%
      setTimeout(() => {
        handleCloseModal();
      }, 500);

    } catch (err) {
      clearInterval(progressInterval);
      setProgress(0);
      const errorMessage = err.response?.data?.mensagem || err.message || "Erro desconhecido";
      setModalError(errorMessage);
      addToast(errorMessage, 'danger');
    } finally {
      // setSendingTroca(false); // Movido para dentro do sucesso/erro ou timeout
    }
  }, [selectedSku, selectedLine, api, addToast, loadHistorico, paginacao.page, paginacao.per_page, handleCloseModal, retryMode]);

  const handleRetry = useCallback((troca) => {
    // Tenta encontrar o SKU na lista atual ou cria um objeto parcial
    const skuToRetry = {
      codigo_sku: troca.sku_trocado,
      descricao_sku: troca.descricao,
    };

    // Tenta preencher com dados da lista de SKUs se disponível para ter dados completos
    const fullSku = skus.find(s => s.codigo_sku === troca.sku_trocado);

    setSelectedSku(fullSku || skuToRetry);
    setRetryMode(true);
    setShowModal(true);
  }, [skus]);

  const renderPaginacao = useCallback(() => {
    if (paginacao.total_pages <= 1 && paginacao.total_items <= paginacao.per_page) return null;

    const items = [];
    const currentPage = paginacao.page;
    const totalPages = paginacao.total_pages;

    items.push(
      <Pagination.First
        key="first"
        disabled={!paginacao.has_previous}
        onClick={() => handlePageChange(1)}
      />
    );
    items.push(
      <Pagination.Prev
        key="prev"
        disabled={!paginacao.has_previous}
        onClick={() => handlePageChange(currentPage - 1)}
      />
    );

    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, startPage + 4);
    if (endPage - startPage < 4) {
      startPage = Math.max(1, endPage - 4);
    }
    for (let page = startPage; page <= endPage; page++) {
      items.push(
        <Pagination.Item
          key={page}
          active={page === currentPage}
          onClick={() => handlePageChange(page)}
        >
          {page}
        </Pagination.Item>
      );
    }

    items.push(
      <Pagination.Next
        key="next"
        disabled={!paginacao.has_next}
        onClick={() => handlePageChange(currentPage + 1)}
      />
    );
    items.push(
      <Pagination.Last
        key="last"
        disabled={!paginacao.has_next}
        onClick={() => handlePageChange(totalPages)}
      />
    );

    return (
      <div className="d-flex justify-content-between align-items-center mt-3">
        <div className="d-flex align-items-center">
          <small className="text-muted me-3">
            Mostrando {paginacao.start_index} a {paginacao.end_index} de {paginacao.total_items} trocas
          </small>
          <Form.Select
            size="sm"
            style={{ width: 'auto' }}
            value={paginacao.per_page}
            onChange={(e) => handlePerPageChange(parseInt(e.target.value))}
          >
            <option value={5}>5 por página</option>
            <option value={10}>10 por página</option>
            <option value={20}>20 por página</option>
            <option value={50}>50 por página</option>
          </Form.Select>
        </div>
        <Pagination className="mb-0">
          {items}
        </Pagination>
      </div>
    );
  }, [paginacao, handlePageChange, handlePerPageChange]);

  // Renderização do Histórico
  const renderHistorico = () => (
    <>
      <Row className="align-items-center mb-4">
        <Col>
          <h5 className="mb-0 fw-bold text-dark">
            <FaHistory className="me-2 text-secondary" />
            Histórico de Trocas com Detalhes de Execução
          </h5>
          <small className="text-muted">
            Visualize o status detalhado de cada equipamento em cada troca
            {paginacao.total_items > 0 && (
              <> • Total: {paginacao.total_items} trocas registradas</>
            )}
          </small>
        </Col>
        <Col xs="auto">
          <Button
            variant="outline-secondary"
            onClick={() => loadHistorico(paginacao.page, paginacao.per_page)}
            disabled={loadingHistorico}
          >
            <FaSyncAlt className={loadingHistorico ? 'rotating' : ''} />
          </Button>
        </Col>
      </Row>

      {loadingHistorico ? (
        <div className="text-center p-4">
          <Spinner size="lg" className="text-secondary" />
          <p className="mt-2 text-muted">Carregando histórico...</p>
        </div>
      ) : historico.length > 0 ? (
        <div>
          {historico.map((troca, index) => (
            <Card key={troca.id} className="mb-4 border-0 shadow-sm">
              <Card.Body>
                <Row className="align-items-center mb-3">
                  <Col>
                    <div className="d-flex align-items-center mb-2">
                      {getStatusIcon(troca.status_visual)}
                      <strong className="text-primary ms-2 me-3 fs-5">{troca.sku_trocado}</strong>
                      <Badge
                        bg={troca.status_visual}
                        className="me-2 px-3 py-2"
                      >
                        {getStatusText(troca.resumo_execucao)}
                      </Badge>
                      {troca.resumo_execucao && troca.resumo_execucao.falhas > 0 && (
                        <Badge bg="warning" text="dark" className="px-2 py-1">
                          <FaExclamationTriangle className="me-1" />
                          Com Problemas
                        </Badge>
                      )}
                    </div>
                    <p className="mb-2 text-dark">{troca.descricao}</p>
                    <div className="d-flex align-items-center text-muted">
                      <FaClock className="me-1" size={12} />
                      <small className="me-4">{formatDate(troca.data_hora)}</small>
                      {/* NOVO: Exibir nome do usuário */}
                      <small className="me-4">
                        <strong>Usuário:</strong> {troca.usuario_nome || 'N/A'}
                      </small>
                      {troca.resumo_execucao && (
                        <>
                          <small className="me-4">
                            <strong>Equipamentos:</strong> {troca.resumo_execucao.sucessos}/{troca.resumo_execucao.total_equipamentos}
                          </small>
                          <small className="me-4">
                            <strong>Taxa de Sucesso:</strong> {troca.resumo_execucao.taxa_sucesso}%
                          </small>
                          <small>
                            <strong>Tempo:</strong> {troca.resumo_execucao.tempo_execucao?.toFixed(2) || 0}s
                          </small>
                        </>
                      )}
                    </div>
                  </Col>
                  {/* Botão de Re-tentar Falhas */}
                  {troca.resumo_execucao && troca.resumo_execucao.taxa_sucesso < 100 && (
                    <Col xs="auto">
                      <Button
                        variant="outline-warning"
                        size="sm"
                        onClick={() => handleRetry(troca)}
                        title="Tentar novamente para equipamentos com falha"
                      >
                        <FaRedo className="me-1" /> Re-tentar Falhas
                      </Button>
                    </Col>
                  )}
                </Row>

                {troca.equipamentos_logs && troca.equipamentos_logs.length > 0 && (
                  <div className="mt-3">
                    <h6 className="text-muted mb-3">
                      <FaCogs className="me-2" />
                      Detalhes por Equipamento:
                    </h6>
                    <Row>
                      {troca.equipamentos_logs.map((eq, eqIndex) => (
                        <Col md={6} lg={4} key={eqIndex} className="mb-3">
                          <Card className={`border-0 h-100 ${eq.sucesso ? 'bg-light' : 'bg-light border-start border-warning border-3'}`}>
                            <Card.Body className="py-3 px-3">
                              <div className="d-flex align-items-center mb-2">
                                {getEquipmentIcon(eq.tipo)}
                                <strong className="ms-2 me-auto">{eq.nome}</strong>
                                <Badge
                                  bg={eq.sucesso ? 'success' : 'warning'}
                                  size="sm"
                                >
                                  {eq.sucesso ? 'OK' : 'Problema'}
                                </Badge>
                              </div>
                              <small className="text-muted d-block mb-2">{eq.mensagem}</small>

                              {eq.variaveis_total > 0 && (
                                <div className="mb-2">
                                  <small className="text-muted d-block">
                                    Variáveis: {eq.variaveis_escritas}/{eq.variaveis_total}
                                  </small>
                                  <ProgressBar
                                    now={(eq.variaveis_escritas / eq.variaveis_total) * 100}
                                    size="sm"
                                    variant={eq.sucesso ? 'success' : 'warning'}
                                    style={{ height: '4px' }}
                                  />
                                </div>
                              )}

                              {eq.tempo_execucao && (
                                <small className="text-muted">
                                  <FaClock className="me-1" />
                                  {eq.tempo_execucao.toFixed(2)}s
                                </small>
                              )}

                              {eq.erros && eq.erros.length > 0 && (
                                <details className="mt-2">
                                  <summary className="text-danger small cursor-pointer">
                                    Ver erros ({eq.erros.length})
                                  </summary>
                                  <div className="mt-1">
                                    {eq.erros.map((erro, errIndex) => (
                                      <small key={errIndex} className="text-danger d-block" style={{ fontSize: '0.7rem' }}>
                                        • {erro}
                                      </small>
                                    ))}
                                  </div>
                                </details>
                              )}
                            </Card.Body>
                          </Card>
                        </Col>
                      ))}
                    </Row>
                  </div>
                )}
              </Card.Body>
            </Card>
          ))}

          {renderPaginacao()}
        </div>
      ) : (
        <div className="text-center py-5">
          <FaHistory size={48} className="text-muted mb-3 opacity-50" />
          <h5 className="text-muted">Sem Histórico</h5>
          <p className="text-muted">Nenhuma troca de SKU foi registrada para a linha {selectedLine}.</p>
        </div>
      )}
    </>
  );

  // --- Efeitos (Hooks) ---

  useEffect(() => {
    checkDjangoStatus();
    const interval = setInterval(checkDjangoStatus, DJANGO_HEALTH_CHECK_INTERVAL);
    return () => clearInterval(interval);
  }, [checkDjangoStatus]);

  useEffect(() => {
    setSkus([]);
    setSearchTerm('');
    setError(null);
    setFeedback({ message: '', type: '' });
    setHistorico([]);
    setStats({ total: 0, ativos: 0, sincronizados: 0 });
    setPaginacao(prev => ({ ...prev, page: 1 }));
  }, [selectedLine]);

  useEffect(() => {
    if (selectedLine && activeTab === 'historico') {
      loadHistorico(1, DEFAULT_PAGE_SIZE);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedLine, activeTab]);


  // --- Renderização do Componente (JSX) ---
  return (
    <Container fluid className="p-4 bg-light min-vh-100">
      <Row className="mb-4">
        <Col>
          <Card className="border-0 shadow-lg bg-gradient-primary text-white">
            <Card.Body className="py-3">
              <Row className="align-items-center">
                <Col>
                  <h3 className="mb-1 fw-bold">
                    <FaChartLine className="me-3" />
                    Troca Automática de SKU
                  </h3>
                  <p className="mb-0 opacity-75">
                    Linha {selectedLine || 'Não Selecionada'} • Sistema Industrial MIS
                  </p>
                </Col>
                <Col xs="auto">
                  <div className="d-flex align-items-center gap-3">
                    <Badge
                      bg={djangoStatus === 'connected' ? 'success' : djangoStatus === 'checking' ? 'warning' : 'danger'}
                      className="px-3 py-2 fs-6"
                    >
                      <FaWifi className="me-2" />
                      {djangoStatus === 'connected' ? 'Online' : djangoStatus === 'checking' ? 'Verificando' : 'Offline'}
                    </Badge>
                    {lastCheck && (
                      <small className="opacity-75">
                        <FaClock className="me-1" />
                        {lastCheck.toLocaleTimeString()}
                      </small>
                    )}
                  </div>
                </Col>
              </Row>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {stats.total > 0 && (
        <Row className="mb-4">
          <Col md={4}>
            <Card className="border-0 shadow-sm h-100">
              <Card.Body className="text-center">
                <FaDatabase className="text-primary mb-2" size={24} />
                <h4 className="mb-1 text-primary">{stats.total}</h4>
                <small className="text-muted">SKUs Sincronizados</small>
              </Card.Body>
            </Card>
          </Col>
          <Col md={4}>
            <Card className="border-0 shadow-sm h-100">
              <Card.Body className="text-center">
                <FaCheckCircle className="text-success mb-2" size={24} />
                <h4 className="mb-1 text-success">{stats.ativos}</h4>
                <small className="text-muted">Ordens Ativas</small>
              </Card.Body>
            </Card>
          </Col>
          <Col md={4}>
            <Card className="border-0 shadow-sm h-100">
              <Card.Body className="text-center">
                <FaHistory className="text-info mb-2" size={24} />
                <h4 className="mb-1 text-info">{paginacao.total_items}</h4>
                <small className="text-muted">Trocas Registradas</small>
              </Card.Body>
            </Card>
          </Col>
        </Row>
      )}

      {feedback.message && (
        <Alert
          variant={feedback.type}
          dismissible
          onClose={() => setFeedback({ message: '', type: '' })}
          className="shadow-sm"
        >
          {feedback.type === 'success' ? <FaCheckCircle className="me-2" /> : <FaTimesCircle className="me-2" />}
          {feedback.message}
        </Alert>
      )}

      {error && (
        <Alert variant="danger" dismissible onClose={() => setError(null)} className="shadow-sm">
          <FaExclamationTriangle className="me-2" />
          {error}
        </Alert>
      )}

      <Row>
        <Col>
          <Card className="border-0 shadow-lg">
            <Card.Header className="bg-white border-bottom-0 py-3">
              <Tabs
                activeKey={activeTab}
                onSelect={(k) => setActiveTab(k)}
                className="border-0"
              >
                <Tab eventKey="sincronizar" title={
                  <span><FaSyncAlt className="me-2" />Sincronizar & Trocar</span>
                }>
                </Tab>
                <Tab eventKey="historico" title={
                  <span><FaHistory className="me-2" />Histórico Detalhado</span>
                }>
                </Tab>
              </Tabs>
            </Card.Header>

            <Card.Body className="p-4">
              {!selectedLine ? (
                <div className="text-center py-5">
                  <FaInfoCircle size={48} className="text-muted mb-3" />
                  <h5 className="text-muted">Selecione uma Linha</h5>
                  <p className="text-muted">Escolha uma linha na barra lateral para acessar as funcionalidades.</p>
                </div>
              ) : (
                <>
                  {activeTab === 'sincronizar' && (
                    <>
                      <Row className="align-items-center mb-4">
                        <Col>
                          <h5 className="mb-0 fw-bold text-dark">
                            <FaSyncAlt className="me-2 text-primary" />
                            Ordens de Produção Disponíveis
                          </h5>
                        </Col>
                        <Col xs="auto">
                          <Button
                            variant="primary"
                            onClick={handleSyncSkus}
                            disabled={isLoading}
                            className="px-4 shadow-sm"
                          >
                            <FaSyncAlt className={isLoading ? 'rotating me-2' : 'me-2'} />
                            {isLoading ? 'Sincronizando...' : 'Sincronizar'}
                          </Button>
                        </Col>
                      </Row>

                      <Row className="mb-4">
                        <Col md={8}>
                          <InputGroup size="lg">
                            <InputGroup.Text className="bg-light border-end-0">
                              <FaSearch className="text-muted" />
                            </InputGroup.Text>
                            <Form.Control
                              type="text"
                              placeholder="    Digite a Ordem de Produção (OP) para filtrar..."
                              value={searchTerm}
                              onChange={(e) => setSearchTerm(e.target.value)}
                              className="border-start-0 shadow-sm"
                            />
                            {searchTerm && (
                              <Button
                                variant="outline-secondary"
                                onClick={() => setSearchTerm('')}
                              >
                                ×
                              </Button>
                            )}
                          </InputGroup>
                        </Col>
                        <Col md={4} className="d-flex align-items-center">
                          <div className="text-muted">
                            <FaFilter className="me-2" />
                            <strong>{filteredSkus.length}</strong> de <strong>{skus.length}</strong> Ordens
                          </div>
                        </Col>
                      </Row>

                      <div className="table-responsive">
                        {isLoading ? (
                          <div className="text-center py-5">
                            <Spinner animation="border" size="lg" className="text-primary" />
                            <p className="mt-3 text-muted">Carregando SKUs da linha {selectedLine}...</p>
                            <ProgressBar animated now={100} className="mt-2" style={{ height: '4px' }} />
                          </div>
                        ) : skus.length > 0 ? (
                          <Table hover className="align-middle">
                            <thead className="table-dark">
                              <tr>
                                <th className="fw-bold">Nº OP</th>
                                <th className="fw-bold">Descrição</th>
                                <th className="fw-bold">Data OP</th>
                                <th className="fw-bold">Status</th>
                                <th className="fw-bold text-center">Ação</th>
                              </tr>
                            </thead>
                            <tbody>
                              {filteredSkus.map((sku, index) => (
                                <tr
                                  key={sku.id_ordem_prod || index}
                                  className={`border-bottom${!sku.ja_rodou_nesta_linha ? ' table-warning' : ''}`}
                                >
                                  <td>
                                    <div className="d-flex align-items-center gap-2">
                                      <code><HighlightText text={sku.numero_op} highlight={searchTerm} /></code>
                                      {!sku.ja_rodou_nesta_linha && (
                                        <Badge bg="warning" text="dark" title="Este SKU nunca rodou nesta linha">
                                          Novo nesta linha
                                        </Badge>
                                      )}
                                    </div>
                                  </td>
                                  <td>
                                    <div className="text-truncate" style={{ maxWidth: '220px' }} title={sku.descricao_sku}>
                                      {sku.descricao_sku}
                                    </div>
                                  </td>
                                  <td><small>{sku.dataop}</small></td>
                                  <td>
                                    <Badge
                                      bg={sku.status_op === 'Ativa' ? 'success' : 'secondary'}
                                      className="px-2 py-1"
                                    >
                                      {sku.status_op}
                                    </Badge>
                                  </td>
                                  <td className="text-center">
                                    <Button
                                      variant="primary"
                                      size="sm"
                                      onClick={() => handleShowModal(sku)}
                                      disabled={!authTokens} // NOVO: Desabilitar se não autenticado
                                      className="px-3 shadow-sm"
                                    >
                                      <FaPaperPlane className="me-1" /> Trocar
                                    </Button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </Table>
                        ) : (
                          <div className="text-center py-5">
                            <FaDatabase size={48} className="text-muted mb-3" />
                            <h5 className="text-muted">Nenhum SKU Encontrado</h5>
                            <p className="text-muted">Clique em "Sincronizar" para buscar as ordens de produção.</p>
                          </div>
                        )}
                      </div>
                    </>
                  )}

                  {activeTab === 'historico' && renderHistorico()}
                </>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Modal de aviso: SKU nunca rodou nesta linha */}
      <Modal show={showPrimeiraRodadaAviso} onHide={() => setShowPrimeiraRodadaAviso(false)} centered>
        <Modal.Header closeButton className="border-0" style={{ background: '#fff3cd' }}>
          <Modal.Title className="fw-bold text-warning-emphasis">
            <FaExclamationTriangle className="me-2 text-warning" />
            Atenção — SKU Novo nesta Linha
          </Modal.Title>
        </Modal.Header>
        <Modal.Body className="px-4 py-3">
          <p className="mb-2">
            O SKU <strong className="text-primary">{selectedSku?.codigo_sku}</strong> —{' '}
            <span className="text-muted">{selectedSku?.descricao_sku}</span> —{' '}
            <strong>nunca foi rodado nesta linha</strong>.
          </p>
          <p className="mb-0">
            Fique atento a possíveis ajustes de qualidade, parâmetros de equipamento e
            regulagens específicas para este produto neste equipamento.
          </p>
        </Modal.Body>
        <Modal.Footer className="border-0">
          <Button variant="secondary" onClick={() => setShowPrimeiraRodadaAviso(false)}>
            Cancelar
          </Button>
          <Button
            variant="warning"
            onClick={() => {
              setShowPrimeiraRodadaAviso(false);
              setShowModal(true);
            }}
          >
            <FaCheckCircle className="me-2" />
            Estou ciente — Prosseguir
          </Button>
        </Modal.Footer>
      </Modal>

      <Modal show={showModal} onHide={handleCloseModal} centered size="lg">
        <Modal.Header closeButton className="bg-gradient-warning text-dark border-0">
          <Modal.Title className="fw-bold">
            <FaExclamationTriangle className="me-2" />
            {retryMode ? 'Re-tentar Troca de SKU' : 'Confirmar Troca de SKU'}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body className="p-4">
          <Alert variant={retryMode ? "warning" : "info"} className="border-0 bg-light">
            <FaInfoCircle className="me-2" />
            {retryMode
              ? `Esta ação irá tentar configurar novamente os equipamentos da Linha **${selectedLine}** para o SKU selecionado.`
              : `Esta ação irá configurar **todos os equipamentos** da Linha **${selectedLine}** com os parâmetros do SKU selecionado.`
            }
          </Alert>

          {selectedSku && (
            <Accordion defaultActiveKey="0">
              <Accordion.Item eventKey="0">
                <Accordion.Header>
                  <strong>Detalhes do SKU: {selectedSku.codigo_sku}</strong>
                </Accordion.Header>
                <Accordion.Body>
                  <Table bordered className="mb-0">
                    <tbody>
                      <tr>
                        <td className="w-25 bg-light fw-bold">SKU:</td>
                        <td><strong className="text-primary">{selectedSku.codigo_sku}</strong></td>
                      </tr>
                      <tr>
                        <td className="bg-light fw-bold">Descrição:</td>
                        <td>{selectedSku.descricao_sku}</td>
                      </tr>
                      <tr>
                        <td className="bg-light fw-bold">DUN14:</td>
                        <td><code>{selectedSku.dun14}</code></td>
                      </tr>
                      <tr>
                        <td className="bg-light fw-bold">Validade:</td>
                        <td>{selectedSku.validade} dias</td>
                      </tr>
                      <tr>
                        <td className="bg-light fw-bold">Nº OP:</td>
                        <td><code>{selectedSku.numero_op}</code></td>
                      </tr>
                      <tr>
                        <td className="bg-light fw-bold">Status OP:</td>
                        <td>
                          <Badge bg={selectedSku.status_op === 'Ativa' ? 'success' : 'secondary'}>
                            {selectedSku.status_op}
                          </Badge>
                        </td>
                      </tr>
                    </tbody>
                  </Table>
                </Accordion.Body>
              </Accordion.Item>
            </Accordion>
          )}

          {modalError && (
            <Alert variant="danger" className="mt-3">
              <FaExclamationTriangle className="me-2" />
              {modalError}
            </Alert>
          )}

          {sendingTroca && (
            <div className="mt-3">
              <div className="d-flex justify-content-between mb-1">
                <small className="text-muted">Processando troca...</small>
                <small className="text-muted">{Math.round(progress)}%</small>
              </div>
              <ProgressBar animated now={progress} className="mb-2" variant={progress === 100 ? "success" : "primary"} />
              <small className="text-muted">
                {progress === 100 ? "Concluído!" : "Enviando configurações para os equipamentos..."}
              </small>
            </div>
          )}
        </Modal.Body>
        <Modal.Footer className="border-0">
          <Button variant="secondary" onClick={handleCloseModal}>
            Cancelar
          </Button>
          <Button
            variant="primary"
            onClick={handleConfirmSend}
            disabled={sendingTroca || !authTokens} // NOVO: Desabilitar se não autenticado
            className="px-4"
          >
            {sendingTroca ? (
              <>
                <Spinner size="sm" className="me-2" />
                Enviando...
              </>
            ) : (
              <>
                <FaPaperPlane className="me-2" />
                {retryMode ? 'Confirmar Re-tentativa' : 'Confirmar Troca'}
              </>
            )}
          </Button>
        </Modal.Footer>
      </Modal>

      <ToastContainer position="top-end" className="p-3">
        {toasts.map(toast => (
          <Toast key={toast.id} show={true} delay={TOAST_DURATION} autohide>
            <Toast.Header>
              <strong className="me-auto">Sistema MIS</strong>
            </Toast.Header>
            <Toast.Body className={`text-${toast.type === 'danger' ? 'danger' : toast.type === 'success' ? 'success' : 'info'}`}>
              {toast.message}
            </Toast.Body>
          </Toast>
        ))}
      </ToastContainer>

      <style jsx>{`
        .rotating {
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .bg-gradient-primary {
          background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
        }

        .bg-gradient-warning {
          background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%);
        }

        .table-responsive {
          border-radius: 0.5rem;
          overflow: hidden;
        }

        .card {
          transition: transform 0.2s ease-in-out;
        }

        .card:hover {
          transform: translateY(-2px);
        }

        .cursor-pointer {
          cursor: pointer;
        }
      `}</style>
    </Container>
  );
};

export default TrocaAutomaticaContent;