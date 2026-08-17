/**
 * InsightosFormatosModal.js — Analytics de Formatos v9.0
 *
 * Exibe sessões de formato por linha:
 *   - Ranking por toneladas e tempo ativo
 *   - Tendência mensal de ton por formato
 *   - Formatos com sessões muito curtas (trocas excessivas)
 *   - Tabela detalhe com ton, horas, nº sessões, duração média
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Modal, Row, Col, Card, Spinner, Alert, Table, Button
} from 'react-bootstrap';
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell
} from 'recharts';
import {
  FaLayerGroup, FaClock, FaWeight, FaExchangeAlt,
  FaTrophy, FaExclamationTriangle, FaSyncAlt
} from 'react-icons/fa';
import useAxios from '../hooks/useAxios';

const PERIODOS = [
  { label: '30 dias',  value: 30  },
  { label: '90 dias',  value: 90  },
  { label: '180 dias', value: 180 },
  { label: '1 ano',    value: 365 },
];

const CORES = [
  '#0d6efd','#198754','#fd7e14','#6610f2','#dc3545',
  '#20c997','#ffc107','#0dcaf0','#d63384','#6f42c1',
];

// ── KPI card ─────────────────────────────────────────────────────────────────
const KpiCard = ({ icon: Icon, label, valor, sub, cor }) => (
  <Card className="h-100 shadow-sm" style={{ borderLeft: `4px solid ${cor}` }}>
    <Card.Body className="py-3 px-3">
      <div className="d-flex align-items-center mb-1">
        <Icon style={{ color: cor }} className="me-2" size={18} />
        <small className="text-muted fw-semibold text-uppercase" style={{ fontSize: '0.7rem' }}>
          {label}
        </small>
      </div>
      <div className="fs-3 fw-bold" style={{ color: cor, lineHeight: 1.1 }}>{valor}</div>
      {sub && <small className="text-muted">{sub}</small>}
    </Card.Body>
  </Card>
);

// ── Tooltip ───────────────────────────────────────────────────────────────────
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

// ── Main ──────────────────────────────────────────────────────────────────────
const InsightosFormatosModal = ({ show, onHide, selectedLine }) => {
  const api = useAxios();
  const apiRef = useRef(api);
  apiRef.current = api;

  const [dados, setDados] = useState(null);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState(null);
  const [periodo, setPeriodo] = useState(90);

  const fetchDados = useCallback(async () => {
    if (!selectedLine || !show) return;
    setLoading(true);
    setErro(null);
    try {
      const res = await apiRef.current.get(`/analytics/formatos/${selectedLine}/?periodo=${periodo}`);
      setDados(res.data);
    } catch (e) {
      setErro(e.response?.data?.detail || 'Erro ao carregar insights de formatos.');
    } finally {
      setLoading(false);
    }
  }, [selectedLine, show, periodo]);

  useEffect(() => { fetchDados(); }, [fetchDados]);

  // ── métricas totais ────────────────────────────────────────────────────────
  const totalTon    = dados?.sessoes_por_formato?.reduce((s, f) => s + f.ton_total, 0) ?? 0;
  const totalHoras  = dados?.sessoes_por_formato?.reduce((s, f) => s + f.tempo_total_h, 0) ?? 0;
  const nFormatos   = dados?.sessoes_por_formato?.length ?? 0;
  const topFormato  = dados?.top_formatos?.[0];

  // ── cores por formato ──────────────────────────────────────────────────────
  const corPorFormato = {};
  (dados?.formatos_unicos || []).forEach((f, i) => {
    corPorFormato[f] = CORES[i % CORES.length];
  });

  return (
    <Modal show={show} onHide={onHide} size="xl" scrollable>
      <Modal.Header closeButton className="bg-dark text-white">
        <Modal.Title>
          <FaLayerGroup className="me-2" />
          Insights de Formatos — {selectedLine}
        </Modal.Title>
      </Modal.Header>

      <Modal.Body>
        {/* Filtro período */}
        <div className="d-flex align-items-center gap-3 mb-4 flex-wrap">
          <span className="fw-semibold text-muted">Período:</span>
          {PERIODOS.map(p => (
            <Button
              key={p.value}
              size="sm"
              variant={periodo === p.value ? 'primary' : 'outline-secondary'}
              onClick={() => setPeriodo(p.value)}
            >
              {p.label}
            </Button>
          ))}
          <Button size="sm" variant="outline-secondary" onClick={fetchDados} disabled={loading}>
            <FaSyncAlt className={loading ? 'spin me-1' : 'me-1'} />
            Atualizar
          </Button>
        </div>

        {loading && (
          <div className="text-center py-5">
            <Spinner animation="border" variant="primary" />
            <p className="mt-2 text-muted">Calculando sessões de formato…</p>
          </div>
        )}

        {erro && <Alert variant="danger">{erro}</Alert>}

        {!loading && dados && (
          <>
            {/* KPIs globais */}
            <Row className="g-3 mb-4">
              <Col xs={6} md={3}>
                <KpiCard
                  icon={FaWeight}
                  label="Toneladas estimadas"
                  valor={`${totalTon.toFixed(1)} t`}
                  sub={`nos últimos ${periodo} dias`}
                  cor="#198754"
                />
              </Col>
              <Col xs={6} md={3}>
                <KpiCard
                  icon={FaClock}
                  label="Horas ativas (total)"
                  valor={`${totalHoras.toFixed(0)} h`}
                  sub="soma de todos os formatos"
                  cor="#0d6efd"
                />
              </Col>
              <Col xs={6} md={3}>
                <KpiCard
                  icon={FaLayerGroup}
                  label="Formatos ativos"
                  valor={nFormatos}
                  sub="com pelo menos 1 sessão"
                  cor="#6610f2"
                />
              </Col>
              <Col xs={6} md={3}>
                <KpiCard
                  icon={FaTrophy}
                  label="Formato líder"
                  valor={topFormato?.formato?.split('-')[0] ?? '—'}
                  sub={topFormato ? `${topFormato.ton_total.toFixed(1)} t — ${topFormato.tempo_total_h.toFixed(0)} h` : ''}
                  cor="#fd7e14"
                />
              </Col>
            </Row>

            {/* Gráfico: Toneladas por formato (barras) */}
            <Card className="mb-4 shadow-sm">
              <Card.Header className="fw-semibold">
                <FaWeight className="me-2 text-success" />
                Toneladas estimadas por formato
              </Card.Header>
              <Card.Body>
                {dados.sessoes_por_formato.length === 0 ? (
                  <p className="text-muted text-center py-3">Sem dados no período.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart
                      data={dados.sessoes_por_formato}
                      margin={{ top: 10, right: 20, left: 0, bottom: 60 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="formato"
                        tick={{ fontSize: 11 }}
                        angle={-35}
                        textAnchor="end"
                        interval={0}
                      />
                      <YAxis tick={{ fontSize: 11 }} unit=" t" />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="ton_total" name="Toneladas" radius={[4, 4, 0, 0]}>
                        {dados.sessoes_por_formato.map((entry, i) => (
                          <Cell key={entry.formato} fill={CORES[i % CORES.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </Card.Body>
            </Card>

            {/* Gráfico: Horas ativas por formato */}
            <Card className="mb-4 shadow-sm">
              <Card.Header className="fw-semibold">
                <FaClock className="me-2 text-primary" />
                Tempo ativo por formato (horas)
              </Card.Header>
              <Card.Body>
                {dados.sessoes_por_formato.length === 0 ? (
                  <p className="text-muted text-center py-3">Sem dados no período.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart
                      data={dados.sessoes_por_formato}
                      margin={{ top: 10, right: 20, left: 0, bottom: 60 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="formato"
                        tick={{ fontSize: 11 }}
                        angle={-35}
                        textAnchor="end"
                        interval={0}
                      />
                      <YAxis tick={{ fontSize: 11 }} unit=" h" />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="tempo_total_h" name="Horas ativas" radius={[4, 4, 0, 0]}>
                        {dados.sessoes_por_formato.map((entry, i) => (
                          <Cell key={entry.formato} fill={CORES[i % CORES.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </Card.Body>
            </Card>

            {/* Gráfico: Tendência mensal de ton por formato */}
            {dados.tendencia_mensal.length > 0 && dados.formatos_unicos.length > 0 && (
              <Card className="mb-4 shadow-sm">
                <Card.Header className="fw-semibold">
                  <FaExchangeAlt className="me-2 text-warning" />
                  Tendência mensal — toneladas por formato
                </Card.Header>
                <Card.Body>
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart
                      data={dados.tendencia_mensal}
                      margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} unit=" t" />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      {dados.formatos_unicos.map((fmt, i) => (
                        <Line
                          key={fmt}
                          type="monotone"
                          dataKey={fmt}
                          name={fmt}
                          stroke={CORES[i % CORES.length]}
                          strokeWidth={2}
                          dot={{ r: 3 }}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </Card.Body>
              </Card>
            )}

            {/* Alerta: formatos com sessões curtas */}
            {dados.ranking_curtos.length > 0 && (
              <Card className="mb-4 border-warning shadow-sm">
                <Card.Header className="fw-semibold text-warning">
                  <FaExclamationTriangle className="me-2" />
                  Formatos com sessões curtas — avaliar necessidade de troca
                </Card.Header>
                <Card.Body>
                  <p className="text-muted small mb-3">
                    Formatos abaixo ficam pouco tempo ativos por sessão.
                    Muitas trocas para pouco tempo de produção reduzem a eficiência da linha.
                  </p>
                  <Table size="sm" hover responsive>
                    <thead className="table-light">
                      <tr>
                        <th>Formato</th>
                        <th className="text-end">Sessões</th>
                        <th className="text-end">Duração média</th>
                        <th className="text-end">Total horas</th>
                        <th className="text-end">Total ton</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dados.ranking_curtos.map(r => (
                        <tr key={r.formato}>
                          <td><span className="badge bg-warning text-dark">{r.formato}</span></td>
                          <td className="text-end">{r.n_sessoes}</td>
                          <td className="text-end text-danger fw-semibold">{r.duracao_media_h.toFixed(1)} h</td>
                          <td className="text-end">{r.tempo_total_h.toFixed(1)} h</td>
                          <td className="text-end">{r.ton_total.toFixed(1)} t</td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </Card.Body>
              </Card>
            )}

            {/* Tabela detalhada */}
            <Card className="shadow-sm">
              <Card.Header className="fw-semibold">
                <FaLayerGroup className="me-2 text-secondary" />
                Detalhe por formato
              </Card.Header>
              <Card.Body className="p-0">
                <Table size="sm" hover responsive className="mb-0">
                  <thead className="table-dark">
                    <tr>
                      <th>#</th>
                      <th>Formato</th>
                      <th className="text-end">Vazão (kg/h)</th>
                      <th className="text-end">Sessões</th>
                      <th className="text-end">Tempo total</th>
                      <th className="text-end">Duração média</th>
                      <th className="text-end">Mais longa</th>
                      <th className="text-end">Mais curta</th>
                      <th className="text-end">Toneladas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dados.sessoes_por_formato.length === 0 && (
                      <tr>
                        <td colSpan={9} className="text-center text-muted py-3">
                          Sem dados no período selecionado.
                        </td>
                      </tr>
                    )}
                    {dados.sessoes_por_formato.map((r, i) => (
                      <tr key={r.formato}>
                        <td>
                          <span
                            className="badge"
                            style={{ backgroundColor: CORES[i % CORES.length] }}
                          >
                            {i + 1}
                          </span>
                        </td>
                        <td className="fw-semibold">{r.formato}</td>
                        <td className="text-end">{r.vazao_kg_hora.toLocaleString('pt-BR')}</td>
                        <td className="text-end">{r.n_sessoes}</td>
                        <td className="text-end">{r.tempo_total_h.toFixed(1)} h</td>
                        <td className="text-end">{r.duracao_media_h.toFixed(1)} h</td>
                        <td className="text-end">{r.sessao_mais_longa_h.toFixed(1)} h</td>
                        <td className="text-end">{r.sessao_mais_curta_h.toFixed(1)} h</td>
                        <td className="text-end fw-bold text-success">
                          {r.ton_total.toFixed(2)} t
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Card.Body>
            </Card>
          </>
        )}
      </Modal.Body>

      <Modal.Footer>
        <Button variant="secondary" onClick={onHide}>Fechar</Button>
      </Modal.Footer>

      <style>{`
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </Modal>
  );
};

export default InsightosFormatosModal;
