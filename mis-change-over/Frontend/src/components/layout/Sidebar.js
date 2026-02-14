import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Button, Form, Offcanvas, Spinner, Alert, Badge } from 'react-bootstrap';
import {
  FaSearch,
  FaIndustry,
  FaChevronDown,
  FaChevronUp,
  FaTimes,
  FaExclamationTriangle,
  FaSyncAlt,
  FaBoxOpen,
  FaWind,
  FaWineBottle
} from 'react-icons/fa';
import './Sidebar.css';
import './SidebarCategories.css'; // <<-- IMPORTANTE: Importe o novo arquivo CSS aqui!

// REMOVA ESTA LINHA: import config from 'C:/Users/admin/Documents/GitHub/IPS-React/avancando-ract/src/components/config.js';

// Use a URL da API diretamente de process.env
// Se a variável de ambiente não estiver definida, use um valor padrão para desenvolvimento
const API_BASE_URL = process.env.REACT_APP_SIDEBAR_API_BASE_URL || '/api';

const Sidebar = ({ selectedLine, onSelectLine, visible }) => {
  const [linhas, setLinhas] = useState([]);
  const [cartucho, setCartucho] = useState([]);
  const [flexiveis, setFlexiveis] = useState([]);
  const [liquidos, setLiquidos] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedSections, setExpandedSections] = useState({
    cartucho: true,
    flexiveis: true,
    liquidos: true,
  });
  const [showOffcanvas, setShowOffcanvas] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [retryCount, setRetryCount] = useState(0);

  const normalizarLinha = useCallback((linha) => {
    if (typeof linha === 'string' && linha.startsWith('L')) return linha;
    return `L${String(linha).padStart(2, '0')}`;
  }, []);

  const processarDadosAPI = useCallback((data) => {
    const normalizarArray = (arr) => (arr || []).map(normalizarLinha);
    const linhasAtivas = normalizarArray(data.linhas);
    const setLinhasAtivas = new Set(linhasAtivas);

    const defsFlexiveis = normalizarArray(data.flexiveis || []);
    const defsCartucho = normalizarArray(data.cartucho || []);
    const defsLiquidos = normalizarArray(data.liquidos || []);

    const linhasFlexiveis = defsFlexiveis.filter(linha => setLinhasAtivas.has(linha));
    const linhasCartucho = defsCartucho.filter(linha => setLinhasAtivas.has(linha));
    const linhasLiquidos = defsLiquidos.filter(linha => setLinhasAtivas.has(linha));

    return {
      todasLinhas: linhasAtivas.sort(),
      flexiveis: linhasFlexiveis.sort(),
      cartucho: linhasCartucho.sort(),
      liquidos: linhasLiquidos.sort(),
    };
  }, [normalizarLinha]);

  const buscarDadosAPI = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/linhas-disponiveis/`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        signal: AbortSignal.timeout(8000)
      });
      if (!response.ok) throw new Error(`Erro HTTP ${response.status}: ${response.statusText}`);

      const data = await response.json();
      console.log('Dados recebidos da API:', data); // Debug

      const dadosProcessados = processarDadosAPI(data);
      console.log('Dados processados:', dadosProcessados); // Debug

      setLinhas(dadosProcessados.todasLinhas);
      setFlexiveis(dadosProcessados.flexiveis);
      setCartucho(dadosProcessados.cartucho);
      setLiquidos(dadosProcessados.liquidos); // Atualiza o estado de líquidos
      setLastUpdate(new Date());
      setRetryCount(0);
    } catch (err) {
      console.error('Erro ao buscar linhas:', err);
      setError(`Erro ao carregar linhas: ${err.message}`);
      if (retryCount < 3) {
        setRetryCount(prev => prev + 1);
        setTimeout(() => buscarDadosAPI(), 3000);
      } else {
        setError('Não foi possível conectar à API.');
        setLinhas([]);
        setFlexiveis([]);
        setCartucho([]);
        setLiquidos([]); // Limpa também as linhas de líquidos em caso de erro persistente
      }
    } finally {
      setIsLoading(false);
    }
  }, [processarDadosAPI, retryCount]); // Dependência API_BASE_URL não é necessária aqui se for constante global

  const filtrarLinhas = useCallback((linhas) => {
    if (!searchTerm) return linhas;
    return linhas.filter(linha =>
      linha.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [searchTerm]);

  const cartuchoFiltrado = useMemo(() => filtrarLinhas(cartucho), [cartucho, filtrarLinhas]);
  const flexiveisFiltrado = useMemo(() => filtrarLinhas(flexiveis), [flexiveis, filtrarLinhas]);
  const liquidosFiltrado = useMemo(() => filtrarLinhas(liquidos), [liquidos, filtrarLinhas]); // Novo memo para linhas de líquidos

  useEffect(() => {
    buscarDadosAPI();
  }, [buscarDadosAPI]); // Adicione buscarDadosAPI como dependência para useCallback

  const handleSelectLine = (linha) => {
    onSelectLine(linha);
    if (window.innerWidth < 992) setShowOffcanvas(false);
  };

  const toggleSection = (section) => setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  const handleSearchChange = (e) => setSearchTerm(e.target.value);
  const handleClearSearch = () => setSearchTerm('');
  const handleShowOffcanvas = () => setShowOffcanvas(true);
  const handleCloseOffcanvas = () => setShowOffcanvas(false);
  const handleRefresh = () => {
    setRetryCount(0);
    buscarDadosAPI();
  };

  const renderLoading = () => (
    <div className="sidebar-loading">
      <Spinner animation="border" />
      <span>Carregando...</span>
    </div>
  );

  const renderError = () => (
    <div className="sidebar-error">
      <FaExclamationTriangle className="error-icon" />
      <h5>Erro</h5>
      <p>{error}</p>
      <Button variant="light" onClick={handleRefresh}>
        <FaSyncAlt className="me-2" /> Tentar Novamente
      </Button>
    </div>
  );

  const renderEmpty = () => (
    <div className="sidebar-empty">
      <FaIndustry className="empty-icon" />
      <h5>Nenhuma Linha</h5>
      <p>Nenhuma linha ativa retornada.</p>
      <Button variant="light" onClick={handleRefresh}>
        <FaSyncAlt className="me-2" /> Atualizar
      </Button>
    </div>
  );

  const renderSidebarContent = () => (
    <div className="sidebar-nav">
      <div className="sidebar-search">
        <div className="search-input-container">
          <FaSearch className="search-icon" />
          <Form.Control
            type="text"
            placeholder="    Buscar linha..."
            value={searchTerm}
            onChange={handleSearchChange}
            className="search-input"
          />
          {searchTerm && (
            <button className="clear-search" onClick={handleClearSearch}>
              <FaTimes />
            </button>
          )}
        </div>
      </div>

      {/* SEÇÃO CARTUCHO - COM ESTILOS DE COR */}
      <div className="sidebar-section cartucho-bg"> {/* Adicionada classe de background */}
        <button
          className="sidebar-section-header cartucho-header" /* Adicionada classe de header */
          onClick={() => toggleSection('cartucho')}
        >
          <span>
            <FaBoxOpen className="section-icon" />
            Cartucho
            {cartuchoFiltrado.length > 0 && (
              <Badge bg="secondary" className="ms-2">
                {/* {cartuchoFiltrado.length} */}
              </Badge>
            )}
          </span>
          {expandedSections.cartucho ? <FaChevronUp /> : <FaChevronDown />}
        </button>
        {expandedSections.cartucho && (
          <div className="sidebar-section-content open">
            {cartuchoFiltrado.length > 0 ? (
              cartuchoFiltrado.map(linha => (
                <button
                  key={linha}
                  className={`sidebar-link cartucho-link ${selectedLine === linha ? 'active' : ''}`} /* Adicionada classe de link */
                  onClick={() => handleSelectLine(linha)}
                >
                  <FaIndustry className="sidebar-icon" />
                  <span className="line-label">{linha}</span>
                </button>
              ))
            ) : (
              <div className="no-results">
                {searchTerm ? 'Nenhum resultado' : 'Nenhuma linha disponível'}
              </div>
            )}
          </div>
        )}
      </div>

      {/* SEÇÃO FLEXÍVEIS - COM ESTILOS DE COR */}
      <div className="sidebar-section flexiveis-bg"> {/* Adicionada classe de background */}
        <button
          className="sidebar-section-header flexiveis-header" /* Adicionada classe de header */
          onClick={() => toggleSection('flexiveis')}
        >
          <span>
            <FaWind className="section-icon" />
            Flexíveis
            {flexiveisFiltrado.length > 0 && (
              <Badge bg="secondary" className="ms-2">
                {/* {flexiveisFiltrado.length} */}
              </Badge>
            )}
          </span>
          {expandedSections.flexiveis ? <FaChevronUp /> : <FaChevronDown />}
        </button>
        {expandedSections.flexiveis && (
          <div className="sidebar-section-content open">
            {flexiveisFiltrado.length > 0 ? (
              flexiveisFiltrado.map(linha => (
                <button
                  key={linha}
                  className={`sidebar-link flexiveis-link ${selectedLine === linha ? 'active' : ''}`} /* Adicionada classe de link */
                  onClick={() => handleSelectLine(linha)}
                >
                  <FaIndustry className="sidebar-icon" />
                  <span className="line-label">{linha}</span>
                </button>
              ))
            ) : (
              <div className="no-results">
                {searchTerm ? 'Nenhum resultado' : 'Nenhuma linha disponível'}
              </div>
            )}
          </div>
        )}
      </div>

      {/* NOVA SEÇÃO LÍQUIDOS - COM ESTILOS DE COR */}
      <div className="sidebar-section liquidos-bg"> {/* Adicionada classe de background */}
        <button
          className="sidebar-section-header liquidos-header" /* Adicionada classe de header */
          onClick={() => toggleSection('liquidos')}
        >
          <span>
            <FaWineBottle className="section-icon" /> {/* Ícone da garrafa */}
            Líquidos
            {liquidosFiltrado.length > 0 && (
              <Badge bg="secondary" className="ms-2">
                {/* {liquidosFiltrado.length} */}
              </Badge>
            )}
          </span>
          {expandedSections.liquidos ? <FaChevronUp /> : <FaChevronDown />}
        </button>
        {expandedSections.liquidos && (
          <div className="sidebar-section-content open">
            {liquidosFiltrado.length > 0 ? (
              liquidosFiltrado.map(linha => (
                <button
                  key={linha}
                  className={`sidebar-link liquidos-link ${selectedLine === linha ? 'active' : ''}`} /* Adicionada classe de link */
                  onClick={() => handleSelectLine(linha)}
                >
                  <FaIndustry className="sidebar-icon" />
                  <span className="line-label">{linha}</span>
                </button>
              ))
            ) : (
              <div className="no-results">
                {searchTerm ? 'Nenhum resultado' : 'Nenhuma linha disponível'}
              </div>
            )}
          </div>
        )}
      </div>

      {/* FOOTER COM INFORMAÇÕES */}
      <div className="sidebar-footer">
        <div className="sidebar-info">
          <small>
            Última atualização: <strong>
              {lastUpdate ? lastUpdate.toLocaleTimeString('pt-BR') : 'Nunca'}
            </strong>
          </small>
          <div className="mt-1">
            <small className="me-3">
              Cartucho: <Badge bg="light" text="dark">{cartucho.length}</Badge>
            </small>
            <small className="me-3">
              Flexíveis: <Badge bg="light" text="dark">{flexiveis.length}</Badge>
            </small>
            <small>
              Líquidos: <Badge bg="light" text="dark">{liquidos.length}</Badge>
            </small>
          </div>
          <small className="mt-1 d-block">
            Total: <Badge bg="primary">{linhas.length}</Badge> linhas ativas
          </small>
        </div>
        <Button
          variant="outline-secondary"
          size="sm"
          onClick={handleRefresh}
          disabled={isLoading}
          className="mt-2"
        >
          {isLoading ? (
            <>
              <Spinner size="sm" className="me-1" />
              Atualizando...
            </>
          ) : (
            <>
              <FaSyncAlt className="me-1" />
              Atualizar Linhas
            </>
          )}
        </Button>
      </div>
    </div>
  );

  const renderDesktopSidebar = () => (
    <div className={`sidebar ${!visible ? 'd-none d-lg-block' : ''}`}>
      <div className="sidebar-header">
        <h4>
          <FaIndustry className="me-2" />
          Linhas de Produção
        </h4>
      </div>
      {isLoading && linhas.length === 0 ? renderLoading() :
        error ? renderError() :
          linhas.length === 0 && !isLoading ? renderEmpty() :
            renderSidebarContent()}
    </div>
  );

  const renderMobileOffcanvas = () => (
    <Offcanvas
      show={showOffcanvas}
      onHide={handleCloseOffcanvas}
      placement="start"
      className="sidebar-offcanvas"
    >
      <Offcanvas.Header closeButton>
        <Offcanvas.Title>
          <FaIndustry className="me-2" />
          Linhas de Produção
        </Offcanvas.Title>
      </Offcanvas.Header>
      <Offcanvas.Body className="p-0">
        {isLoading && linhas.length === 0 ? renderLoading() :
          error ? renderError() :
            linhas.length === 0 && !isLoading ? renderEmpty() :
              renderSidebarContent()}
      </Offcanvas.Body>
    </Offcanvas>
  );

  return (
    <>
      {renderDesktopSidebar()}
      <Button
        variant="primary"
        className="sidebar-toggle d-lg-none"
        onClick={handleShowOffcanvas}
      >
        <FaIndustry />
      </Button>
      {renderMobileOffcanvas()}
    </>
  );
};

export default Sidebar;