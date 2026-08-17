/**
 * InsightsTrocasModal.js
 * Modal de analytics e insights de trocas de SKU por linha.
 * Exibe KPIs, tendência mensal, tempo médio de troca e top SKUs.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Modal, Row, Col, Card, Spinner, Alert, Badge, Table, Button
} from 'react-bootstrap';
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell
} from 'recharts';
import {
  FaChartBar, FaClock, FaCheckCircle, FaExchangeAlt,
  FaCalendarDay, FaCalendarAlt, FaSyncAlt, FaTrophy
} from 'react-icons/fa';

const API_BASE_URL = process.env.REACT_APP_TROCA_AUTOMATICA_BASE_URL || '/api';

// ─── Paleta de cores ────────────────────────────────────────────────────────
const COR_TROCAS = '#0d6efd';
const COR_SUCESSO = '#198754';
const COR_TEMPO = '#fd7e14';
const COR_SKU_BARS = [
  '#0d6efd', '#6610f2', '#6f42c1', '#d63384', '#dc3545',
  '#fd7e14', '#ffc107', '#198754', '#20c997', '#0dcaf0',
];

// ─── Card de KPI ────────────────────────────────────────────────────────────
const KpiCard = ({ icon: Icon, label, valor, sub, cor }) => (
  <Card className="h-100 shadow-sm" style={{ borderLeft: `4px solid ${cor}` }}>
    <Card.Body className="py-3 px-3">
      <div className="d-flex align-items-center mb-1">
        <Icon style={{ color: cor }} className="me-2" size={18} />
        <small className="text-muted fw-semibold text-uppercase" style={{ fontSize: '0.7rem' }}>
          {label}
        </small>
      </div>
      <div className="fs-3 fw-bold" style={{ color: cor, lineHeight: 1.1 }}>
        {valor}
      </div>
      {sub && <small className="text-muted">{sub}</small>}
    </Card.Body>
  </Card>
);

// ─── Tooltip customizado para os gráficos ───────────────────────────────────
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-dark text-white rounded p-2" style={{ fontSize: '0.8rem' }}>
      <p className="mb-1 fw-bold">{label}</p>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color }}>
          {p.name}: <strong>{p.value}</strong>
        </div>
      ))}
    </div>
  );
};

// ─── Componente principal ────────────────────────────────────────────────────
const InsightsTrocasModal = ({ show, onHide, selectedLine }) => {
  const [dados, setDados] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState(null);

  const buscarAnalytics = useCallback(async () => {
    if (!selectedLine) return;
    setCarregando(true);
    setErro(null);
    try {
      const resp = await fetch(`${API_BASE_URL}/analytics/trocas/${selectedLine}/`);
      if (!resp.ok) throw new Error(`Erro ${resp.status}: ${resp.statusText}`);
      const json = await resp.json();
      setDados(json);
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
    }
  }, [selectedLine]);

  useEffect(() => {
    if (show && selectedLine) buscarAnalytics();
  }, [show, selectedLine, buscarAnalytics]);

  const formatarTempo = (seg) => {
    if (!seg || seg === 0) return '—';
    if (seg < 60) return `${seg}s`;
    const m = Math.floor(seg / 60);
    const s = Math.round(seg % 60);
    return `${m}m ${s}s`;
  };

  const renderConteudo = () => {
    if (carregando) {
      return (
        <div className="text-center py-5">
          <Spinner animation="border" variant="primary" />
          <p className="mt-3 text-muted">Calculando insights para {selectedLine}...</p>
        </div>
      );
    }

    if (erro) {
      return (
        <Alert variant="danger" className="mt-2">
          <strong>Erro ao carregar analytics:</strong> {erro}
          <div className="mt-2">
            <Button size="sm" variant="outline-danger" onClick={buscarAnalytics}>
              Tentar novamente
            </Button>
          </div>
        </Alert>
      );
    }

    if (!dados) return null;

    const { resumo, tendencia_mensal, top_skus } = dados;
    const temTendencia = tendencia_mensal?.length > 0;
    const temTopSkus = top_skus?.length > 0;
    const temTempo = resumo.tempo_medio_seg > 0;

    return (
      <>
        {/* ── KPIs ── */}
        <Row className="g-3 mb-4">
          <Col xs={6} md={4} lg={2}>
            <KpiCard
              icon={FaCalendarDay}
              label="Hoje"
              valor={resumo.hoje.trocas}
              sub={`${resumo.hoje.taxa_sucesso}% sucesso`}
              cor={COR_TROCAS}
            />
          </Col>
          <Col xs={6} md={4} lg={2}>
            <KpiCard
              icon={FaExchangeAlt}
              label="Esta semana"
              valor={resumo.semana.trocas}
              sub={`${resumo.semana.taxa_sucesso}% sucesso`}
              cor="#6610f2"
            />
          </Col>
          <Col xs={6} md={4} lg={2}>
            <KpiCard
              icon={FaCalendarAlt}
              label="Este mês"
              valor={resumo.mes_atual.trocas}
              sub={`${resumo.mes_atual.taxa_sucesso}% sucesso`}
              cor="#6f42c1"
            />
          </Col>
          <Col xs={6} md={4} lg={2}>
            <KpiCard
              icon={FaChartBar}
              label="Este ano"
              valor={resumo.ano.trocas}
              sub={`${resumo.ano.taxa_sucesso}% sucesso`}
              cor="#d63384"
            />
          </Col>
          <Col xs={6} md={4} lg={2}>
            <KpiCard
              icon={FaCheckCircle}
              label="Total geral"
              valor={resumo.total_geral.trocas}
              sub={`${resumo.total_geral.taxa_sucesso}% sucesso`}
              cor={COR_SUCESSO}
            />
          </Col>
          <Col xs={6} md={4} lg={2}>
            <KpiCard
              icon={FaClock}
              label="Tempo médio"
              valor={formatarTempo(resumo.tempo_medio_seg)}
              sub="por troca"
              cor={COR_TEMPO}
            />
          </Col>
        </Row>

        {/* ── Gráficos de tendência ── */}
        {temTendencia && (
          <Row className="g-3 mb-4">
            <Col xs={12} lg={6}>
              <Card className="shadow-sm h-100">
                <Card.Header className="fw-semibold py-2 bg-light">
                  <FaChartBar className="me-2 text-primary" />
                  Trocas por mês (últimos 12 meses)
                </Card.Header>
                <Card.Body>
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={tendencia_mensal} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#dee2e6" />
                      <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="trocas" name="Trocas" fill={COR_TROCAS} radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </Card.Body>
              </Card>
            </Col>

            <Col xs={12} lg={6}>
              <Card className="shadow-sm h-100">
                <Card.Header className="fw-semibold py-2 bg-light">
                  <FaCheckCircle className="me-2 text-success" />
                  Taxa de sucesso por mês (%)
                </Card.Header>
                <Card.Body>
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={tendencia_mensal} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#dee2e6" />
                      <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Line
                        type="monotone"
                        dataKey="taxa_sucesso"
                        name="Taxa sucesso (%)"
                        stroke={COR_SUCESSO}
                        strokeWidth={2}
                        dot={{ r: 4 }}
                        activeDot={{ r: 6 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </Card.Body>
              </Card>
            </Col>

            {temTempo && (
              <Col xs={12}>
                <Card className="shadow-sm">
                  <Card.Header className="fw-semibold py-2 bg-light">
                    <FaClock className="me-2 text-warning" />
                    Tempo médio de troca por mês (segundos)
                  </Card.Header>
                  <Card.Body>
                    <ResponsiveContainer width="100%" height={200}>
                      <LineChart data={tendencia_mensal} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#dee2e6" />
                        <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} unit="s" />
                        <Tooltip content={<CustomTooltip />} />
                        <Legend wrapperStyle={{ fontSize: 12 }} />
                        <Line
                          type="monotone"
                          dataKey="tempo_medio"
                          name="Tempo médio (s)"
                          stroke={COR_TEMPO}
                          strokeWidth={2}
                          dot={{ r: 4 }}
                          activeDot={{ r: 6 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </Card.Body>
                </Card>
              </Col>
            )}
          </Row>
        )}

        {/* ── Top SKUs ── */}
        {temTopSkus && (
          <Row className="g-3">
            <Col xs={12} lg={5}>
              <Card className="shadow-sm h-100">
                <Card.Header className="fw-semibold py-2 bg-light">
                  <FaTrophy className="me-2 text-warning" />
                  Top SKUs — frequência de troca
                </Card.Header>
                <Card.Body style={{ padding: '0.75rem' }}>
                  <ResponsiveContainer width="100%" height={Math.max(200, top_skus.length * 36)}>
                    <BarChart
                      layout="vertical"
                      data={top_skus}
                      margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#dee2e6" />
                      <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                      <YAxis
                        type="category"
                        dataKey="sku"
                        width={70}
                        tick={{ fontSize: 11 }}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="trocas" name="Trocas" radius={[0, 3, 3, 0]}>
                        {top_skus.map((_, i) => (
                          <Cell key={i} fill={COR_SKU_BARS[i % COR_SKU_BARS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </Card.Body>
              </Card>
            </Col>

            <Col xs={12} lg={7}>
              <Card className="shadow-sm h-100">
                <Card.Header className="fw-semibold py-2 bg-light">
                  <FaTrophy className="me-2 text-warning" />
                  Detalhes top SKUs (últimos 12 meses)
                </Card.Header>
                <Card.Body className="p-0">
                  <Table striped hover responsive className="mb-0" style={{ fontSize: '0.85rem' }}>
                    <thead className="table-dark">
                      <tr>
                        <th>#</th>
                        <th>SKU</th>
                        <th>Descrição</th>
                        <th className="text-center">Trocas</th>
                        <th className="text-center">Sucesso</th>
                        <th className="text-center">T. Médio</th>
                      </tr>
                    </thead>
                    <tbody>
                      {top_skus.map((s, i) => (
                        <tr key={s.sku}>
                          <td>
                            <Badge
                              style={{ backgroundColor: COR_SKU_BARS[i % COR_SKU_BARS.length] }}
                            >
                              {i + 1}
                            </Badge>
                          </td>
                          <td>
                            <code style={{ fontSize: '0.8rem' }}>{s.sku}</code>
                          </td>
                          <td className="text-truncate" style={{ maxWidth: 200 }}>
                            {s.descricao}
                          </td>
                          <td className="text-center fw-bold">{s.trocas}</td>
                          <td className="text-center">
                            <Badge bg={s.taxa_sucesso >= 90 ? 'success' : s.taxa_sucesso >= 70 ? 'warning' : 'danger'}>
                              {s.taxa_sucesso}%
                            </Badge>
                          </td>
                          <td className="text-center text-muted">{formatarTempo(s.tempo_medio)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </Card.Body>
              </Card>
            </Col>
          </Row>
        )}

        {!temTendencia && !temTopSkus && (
          <Alert variant="info" className="text-center mt-2">
            Nenhum dado de tendência encontrado para {selectedLine} nos últimos 12 meses.
          </Alert>
        )}
      </>
    );
  };

  return (
    <Modal show={show} onHide={onHide} size="xl" fullscreen="lg-down" scrollable>
      <Modal.Header closeButton className="bg-dark text-white">
        <Modal.Title className="d-flex align-items-center gap-2">
          <FaChartBar />
          Insights de Trocas
          {selectedLine && (
            <Badge bg="primary" className="ms-1">
              {selectedLine}
            </Badge>
          )}
        </Modal.Title>
        <Button
          variant="outline-light"
          size="sm"
          className="ms-auto me-2"
          onClick={buscarAnalytics}
          disabled={carregando}
          title="Atualizar dados"
        >
          <FaSyncAlt className={carregando ? 'fa-spin' : ''} />
        </Button>
      </Modal.Header>
      <Modal.Body className="bg-light">
        {renderConteudo()}
      </Modal.Body>
    </Modal>
  );
};

export default InsightsTrocasModal;
