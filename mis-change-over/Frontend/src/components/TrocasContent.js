/**
 * TrocasContent.js - Histórico de Trocas de Produtos
 * Inclui busca por SKU e acesso ao modal de Insights analíticos.
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Card, Table, Badge, Spinner, Alert, Form,
  InputGroup, Button, Row, Col
} from 'react-bootstrap';
import {
  FaHistory, FaInfoCircle, FaExclamationTriangle,
  FaSearch, FaChartBar, FaTimes
} from 'react-icons/fa';
import InsightsTrocasModal from './InsightsTrocasModal';
import InsightosFormatosModal from './InsightosFormatosModal';
import { FaLayerGroup } from 'react-icons/fa';

const API_BASE_URL = process.env.REACT_APP_TROCA_AUTOMATICA_BASE_URL || '/api';
const HISTORICO_TROCAS_ENDPOINT = process.env.REACT_APP_HISTORICO_TROCAS_ENDPOINT || '/linha/{line}';

const TrocasContent = ({ selectedLine }) => {
  const [historico, setHistorico] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [paginacao, setPaginacao] = useState(null);
  const [page, setPage] = useState(1);
  const [skuBusca, setSkuBusca] = useState('');
  const [skuFiltro, setSkuFiltro] = useState('');
  const [showInsights, setShowInsights] = useState(false);
  const [showInsightosFormatos, setShowInsightosFormatos] = useState(false);
  const debounceRef = useRef(null);

  // Dispara busca com debounce ao digitar
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setPage(1);
      setSkuFiltro(skuBusca.trim());
    }, 400);
    return () => clearTimeout(debounceRef.current);
  }, [skuBusca]);

  // Reinicia página ao trocar linha
  useEffect(() => {
    setPage(1);
    setSkuBusca('');
    setSkuFiltro('');
  }, [selectedLine]);

  useEffect(() => {
    if (!selectedLine) {
      setHistorico([]);
      setPaginacao(null);
      setError(null);
      return;
    }

    const fetchHistorico = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const perPage = 10;
        let url = `${API_BASE_URL}${HISTORICO_TROCAS_ENDPOINT.replace('{line}', selectedLine)}?page=${page}&per_page=${perPage}`;
        if (skuFiltro) url += `&sku=${encodeURIComponent(skuFiltro)}`;

        const response = await fetch(url);
        if (!response.ok) throw new Error(`Erro ${response.status}: ${response.statusText}`);

        const data = await response.json();
        if (data && Array.isArray(data.ultimas_trocas)) {
          setHistorico(data.ultimas_trocas);
          setPaginacao(data.paginacao || null);
        } else {
          setHistorico([]);
          setPaginacao(null);
        }
      } catch (err) {
        setError(err.message);
        setHistorico([]);
        setPaginacao(null);
      } finally {
        setIsLoading(false);
      }
    };

    fetchHistorico();
  }, [selectedLine, page, skuFiltro]);

  const formatarData = (dataIso) => {
    if (!dataIso) return 'Data inválida';
    try {
      return new Date(dataIso).toLocaleString('pt-BR', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    } catch {
      return dataIso;
    }
  };

  const renderContent = () => {
    if (!selectedLine) {
      return (
        <Alert variant="info" className="mt-3 text-center">
          <FaInfoCircle size={24} className="mb-2" />
          <br />
          Selecione uma linha no menu lateral para ver o histórico de trocas.
        </Alert>
      );
    }

    if (isLoading) {
      return (
        <div className="text-center p-5">
          <Spinner animation="border" variant="primary" />
          <p className="mt-2">
            Carregando histórico para <strong>{selectedLine}</strong>
            {skuFiltro && <> — SKU: <Badge bg="secondary">{skuFiltro}</Badge></>}...
          </p>
        </div>
      );
    }

    if (error) {
      return (
        <Alert variant="danger" className="mt-3 text-center">
          <FaExclamationTriangle size={24} className="mb-2" />
          <br />
          <strong>Erro ao carregar dados:</strong> {error}
        </Alert>
      );
    }

    if (historico.length === 0) {
      return (
        <Alert variant="secondary" className="mt-3 text-center">
          {skuFiltro
            ? <>Nenhuma troca encontrada para o SKU <strong>{skuFiltro}</strong> na linha <strong>{selectedLine}</strong>.</>
            : <>Nenhum histórico de troca encontrado para a linha <strong>{selectedLine}</strong>.</>
          }
        </Alert>
      );
    }

    return (
      <>
        <Table striped bordered hover responsive className="mt-3 mb-2">
          <thead className="table-dark">
            <tr>
              <th>SKU Trocado</th>
              <th>Descrição</th>
              <th>Data/Hora da Troca</th>
            </tr>
          </thead>
          <tbody>
            {historico.map((item, index) => (
              <tr key={item.id || item.data_hora || index}>
                <td><Badge bg="secondary">{item.sku_trocado}</Badge></td>
                <td>{item.descricao}</td>
                <td>{formatarData(item.data_hora)}</td>
              </tr>
            ))}
          </tbody>
        </Table>

        {paginacao && paginacao.total_pages > 1 && (
          <div className="d-flex justify-content-between align-items-center mt-1">
            <small className="text-muted">
              Página {paginacao.page} de {paginacao.total_pages}
              {' '}({paginacao.total_items} registros)
            </small>
            <div className="d-flex gap-2">
              <Button
                size="sm"
                variant="outline-secondary"
                disabled={!paginacao.has_previous}
                onClick={() => setPage(p => p - 1)}
              >
                ← Anterior
              </Button>
              <Button
                size="sm"
                variant="outline-secondary"
                disabled={!paginacao.has_next}
                onClick={() => setPage(p => p + 1)}
              >
                Próxima →
              </Button>
            </div>
          </div>
        )}
      </>
    );
  };

  return (
    <div className="p-4">
      <Card>
        <Card.Header>
          <Row className="align-items-center g-2">
            <Col>
              <h2 className="h5 mb-0 d-flex align-items-center flex-wrap gap-2">
                <FaHistory />
                Histórico de Troca de Produtos
                {selectedLine && <Badge bg="primary" className="fs-6">{selectedLine}</Badge>}
              </h2>
            </Col>
            {selectedLine && (
              <Col xs="auto">
                <Button
                  variant="outline-primary"
                  size="sm"
                  onClick={() => setShowInsights(true)}
                  title="Insights de trocas de SKU"
                >
                  <FaChartBar className="me-1" />
                  Insights Trocas
                </Button>
                <Button
                  variant="outline-success"
                  size="sm"
                  onClick={() => setShowInsightosFormatos(true)}
                  title="Insights de formatos — tempo ativo e toneladas"
                >
                  <FaLayerGroup className="me-1" />
                  Insights Formatos
                </Button>
              </Col>
            )}
          </Row>

          {selectedLine && (
            <div className="mt-2">
              <InputGroup size="sm" style={{ maxWidth: 340 }}>
                <InputGroup.Text>
                  <FaSearch />
                </InputGroup.Text>
                <Form.Control
                  placeholder="Filtrar por SKU..."
                  value={skuBusca}
                  onChange={e => setSkuBusca(e.target.value)}
                />
                {skuBusca && (
                  <Button
                    variant="outline-secondary"
                    onClick={() => setSkuBusca('')}
                    title="Limpar filtro"
                  >
                    <FaTimes />
                  </Button>
                )}
              </InputGroup>
            </div>
          )}
        </Card.Header>

        <Card.Body>
          {renderContent()}
        </Card.Body>
      </Card>

      <InsightsTrocasModal
        show={showInsights}
        onHide={() => setShowInsights(false)}
        selectedLine={selectedLine}
      />
      <InsightosFormatosModal
        show={showInsightosFormatos}
        onHide={() => setShowInsightosFormatos(false)}
        selectedLine={selectedLine}
      />
    </div>
  );
};

export default TrocasContent;
