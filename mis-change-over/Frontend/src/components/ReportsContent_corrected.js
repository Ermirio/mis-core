/**
 * ReportsContent.js - Componente para sistema de relatórios
 * 
 * Este componente oferece uma interface completa para geração de relatórios
 * industriais, incluindo:
 * - Seleção de tipos de relatório
 * - Configuração de parâmetros e filtros
 * - Geração de relatórios em PDF
 * - Visualização de dados em gráficos
 * - Histórico de relatórios gerados
 * 
 * @author Manus AI
 * @version 1.0.0
 */

import React, { useState, useCallback, useMemo } from 'react';
import { 
  Card, 
  Row, 
  Col, 
  Button, 
  Form, 
  Alert, 
  Badge, 
  Modal,
  Table,
  ProgressBar,
  ButtonGroup,
  Spinner,
  InputGroup,
  Accordion
} from 'react-bootstrap';
import { Bar, Line, Pie, Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { 
  FaFileAlt,
  FaDownload,
  FaEye,
  FaCalendarAlt,
  FaFilter,
  FaCog,
  FaChartBar,
  FaChartLine,
  FaChartPie,
  FaTable,
  FaIndustry,
  FaClipboardList,
  FaFileExport,
  FaPrint,
  FaShare,
  FaHistory,
  FaPlus,
  FaTrash,
  FaEdit,
  FaSearch,
  FaInfoCircle // CORREÇÃO: Adicionada importação do ícone que estava faltando
} from 'react-icons/fa';
import './ReportsContent.css';

// Registro dos componentes do Chart.js
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

/**
 * Componente principal para sistema de relatórios
 */
const ReportsContent = ({ selectedLine }) => {
  // ===== ESTADOS DO COMPONENTE =====
  
  /**
   * Estado para tipo de relatório selecionado
   */
  const [selectedReportType, setSelectedReportType] = useState('production');
  
  /**
   * Estado para parâmetros do relatório
   */
  const [reportParams, setReportParams] = useState({
    dateRange: 'last7days',
    startDate: '',
    endDate: '',
    includeCharts: true,
    includeDetails: true,
    format: 'pdf',
    groupBy: 'day'
  });
  
  /**
   * Estado para dados do relatório
   */
  const [reportData, setReportData] = useState(null);
  
  /**
   * Estado para controle de geração
   */
  const [isGenerating, setIsGenerating] = useState(false);
  
  /**
   * Estado para histórico de relatórios
   */
  const [reportHistory, setReportHistory] = useState([
    {
      id: 'RPT001',
      name: 'Relatório de Produção - Semana 48',
      type: 'production',
      line: 'L01',
      createdAt: new Date(Date.now() - 86400000 * 2),
      size: '2.3 MB',
      status: 'completed'
    },
    {
      id: 'RPT002',
      name: 'Análise de Qualidade - Novembro',
      type: 'quality',
      line: 'L02',
      createdAt: new Date(Date.now() - 86400000 * 5),
      size: '1.8 MB',
      status: 'completed'
    },
    {
      id: 'RPT003',
      name: 'KPIs Mensais - Outubro',
      type: 'kpi',
      line: 'L01',
      createdAt: new Date(Date.now() - 86400000 * 30),
      size: '3.1 MB',
      status: 'completed'
    }
  ]);
  
  /**
   * Estado para modal de visualização
   */
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  
  /**
   * Estado para filtros
   */
  const [filters, setFilters] = useState({
    search: '',
    type: 'all',
    status: 'all'
  });

  // ===== TIPOS DE RELATÓRIO =====
  
  const reportTypes = {
    production: {
      name: 'Relatório de Produção',
      description: 'Análise detalhada da produção, incluindo volumes, eficiência e downtime',
      icon: FaIndustry,
      color: 'primary'
    },
    quality: {
      name: 'Relatório de Qualidade',
      description: 'Métricas de qualidade, defeitos e conformidade',
      icon: FaClipboardList,
      color: 'success'
    },
    kpi: {
      name: 'Relatório de KPIs',
      description: 'Indicadores chave de performance e OEE',
      icon: FaChartBar,
      color: 'info'
    },
    maintenance: {
      name: 'Relatório de Manutenção',
      description: 'Histórico de manutenções, preventivas e corretivas',
      icon: FaCog,
      color: 'warning'
    },
    process: {
      name: 'Relatório de Processo',
      description: 'Variáveis de processo, tendências e alarmes',
      icon: FaChartLine,
      color: 'secondary'
    }
  };

  // ===== FUNÇÕES AUXILIARES =====

  /**
   * Gera dados simulados baseados no tipo de relatório
   */
  const generateReportData = useCallback((type, params) => {
    const days = params.dateRange === 'last7days' ? 7 : 
                 params.dateRange === 'last30days' ? 30 : 
                 params.dateRange === 'last90days' ? 90 : 7;
    
    const data = [];
    const labels = [];
    
    for (let i = days - 1; i >= 0; i--) {
      const date = new Date();
      date.setDate(date.getDate() - i);
      labels.push(date.toLocaleDateString('pt-BR'));
      
      switch (type) {
        case 'production':
          data.push({
            date: date.toISOString(),
            produced: Math.floor(800 + Math.random() * 400),
            target: 1000,
            efficiency: 75 + Math.random() * 20,
            downtime: Math.random() * 10,
            oee: 70 + Math.random() * 25
          });
          break;
          
        case 'quality':
          data.push({
            date: date.toISOString(),
            approved: Math.floor(900 + Math.random() * 100),
            rejected: Math.floor(Math.random() * 50),
            rework: Math.floor(Math.random() * 30),
            defectRate: Math.random() * 5,
            firstPass: 90 + Math.random() * 8
          });
          break;
          
        case 'kpi':
          data.push({
            date: date.toISOString(),
            oee: 70 + Math.random() * 25,
            availability: 85 + Math.random() * 10,
            performance: 80 + Math.random() * 15,
            quality: 90 + Math.random() * 8,
            productivity: 75 + Math.random() * 20
          });
          break;
          
        case 'maintenance':
          data.push({
            date: date.toISOString(),
            preventive: Math.floor(Math.random() * 3),
            corrective: Math.floor(Math.random() * 2),
            mtbf: 120 + Math.random() * 80,
            mttr: 2 + Math.random() * 4,
            cost: 1000 + Math.random() * 5000
          });
          break;
          
        case 'process':
          data.push({
            date: date.toISOString(),
            temperature: 70 + Math.random() * 15,
            pressure: 95 + Math.random() * 20,
            flow: 45 + Math.random() * 15,
            alarms: Math.floor(Math.random() * 5),
            deviations: Math.floor(Math.random() * 10)
          });
          break;
          
        default:
          data.push({});
      }
    }
    
    return { data, labels };
  }, []);

  /**
   * Gera gráficos baseados no tipo de relatório
   */
  const generateCharts = useCallback((type, data, labels) => {
    const charts = [];
    
    switch (type) {
      case 'production':
        charts.push({
          type: 'bar',
          title: 'Produção vs Meta',
          data: {
            labels,
            datasets: [
              {
                label: 'Produzido',
                data: data.map(d => d.produced),
                backgroundColor: 'rgba(49, 130, 206, 0.8)',
                borderColor: 'rgba(49, 130, 206, 1)',
                borderWidth: 1
              },
              {
                label: 'Meta',
                data: data.map(d => d.target),
                backgroundColor: 'rgba(229, 62, 62, 0.8)',
                borderColor: 'rgba(229, 62, 62, 1)',
                borderWidth: 1
              }
            ]
          }
        });
        
        charts.push({
          type: 'line',
          title: 'Eficiência e OEE',
          data: {
            labels,
            datasets: [
              {
                label: 'Eficiência (%)',
                data: data.map(d => d.efficiency),
                borderColor: 'rgba(56, 161, 105, 1)',
                backgroundColor: 'rgba(56, 161, 105, 0.1)',
                fill: true,
                tension: 0.4
              },
              {
                label: 'OEE (%)',
                data: data.map(d => d.oee),
                borderColor: 'rgba(214, 158, 46, 1)',
                backgroundColor: 'rgba(214, 158, 46, 0.1)',
                fill: true,
                tension: 0.4
              }
            ]
          }
        });
        break;
        
      case 'quality':
        charts.push({
          type: 'doughnut',
          title: 'Distribuição de Qualidade',
          data: {
            labels: ['Aprovados', 'Rejeitados', 'Retrabalho'],
            datasets: [{
              data: [
                data.reduce((sum, d) => sum + d.approved, 0),
                data.reduce((sum, d) => sum + d.rejected, 0),
                data.reduce((sum, d) => sum + d.rework, 0)
              ],
              backgroundColor: [
                'rgba(56, 161, 105, 0.8)',
                'rgba(229, 62, 62, 0.8)',
                'rgba(214, 158, 46, 0.8)'
              ],
              borderColor: [
                'rgba(56, 161, 105, 1)',
                'rgba(229, 62, 62, 1)',
                'rgba(214, 158, 46, 1)'
              ],
              borderWidth: 2
            }]
          }
        });
        
        charts.push({
          type: 'line',
          title: 'Taxa de Defeitos',
          data: {
            labels,
            datasets: [{
              label: 'Taxa de Defeitos (%)',
              data: data.map(d => d.defectRate),
              borderColor: 'rgba(229, 62, 62, 1)',
              backgroundColor: 'rgba(229, 62, 62, 0.1)',
              fill: true,
              tension: 0.4
            }]
          }
        });
        break;
        
      case 'kpi':
        charts.push({
          type: 'line',
          title: 'Componentes do OEE',
          data: {
            labels,
            datasets: [
              {
                label: 'Disponibilidade (%)',
                data: data.map(d => d.availability),
                borderColor: 'rgba(49, 130, 206, 1)',
                backgroundColor: 'rgba(49, 130, 206, 0.1)',
                fill: false,
                tension: 0.4
              },
              {
                label: 'Performance (%)',
                data: data.map(d => d.performance),
                borderColor: 'rgba(56, 161, 105, 1)',
                backgroundColor: 'rgba(56, 161, 105, 0.1)',
                fill: false,
                tension: 0.4
              },
              {
                label: 'Qualidade (%)',
                data: data.map(d => d.quality),
                borderColor: 'rgba(214, 158, 46, 1)',
                backgroundColor: 'rgba(214, 158, 46, 0.1)',
                fill: false,
                tension: 0.4
              }
            ]
          }
        });
        break;
        
      default:
        break;
    }
    
    return charts;
  }, []);

  /**
   * Calcula estatísticas resumidas
   */
  const calculateSummary = useCallback((type, data) => {
    if (!data || data.length === 0) return {};
    
    switch (type) {
      case 'production':
        return {
          totalProduced: data.reduce((sum, d) => sum + d.produced, 0),
          avgEfficiency: data.reduce((sum, d) => sum + d.efficiency, 0) / data.length,
          avgOEE: data.reduce((sum, d) => sum + d.oee, 0) / data.length,
          totalDowntime: data.reduce((sum, d) => sum + d.downtime, 0),
          targetAchievement: (data.reduce((sum, d) => sum + d.produced, 0) / data.reduce((sum, d) => sum + d.target, 0)) * 100
        };
        
      case 'quality':
        return {
          totalApproved: data.reduce((sum, d) => sum + d.approved, 0),
          totalRejected: data.reduce((sum, d) => sum + d.rejected, 0),
          avgDefectRate: data.reduce((sum, d) => sum + d.defectRate, 0) / data.length,
          avgFirstPass: data.reduce((sum, d) => sum + d.firstPass, 0) / data.length,
          qualityIndex: 100 - (data.reduce((sum, d) => sum + d.defectRate, 0) / data.length)
        };
        
      case 'kpi':
        return {
          avgOEE: data.reduce((sum, d) => sum + d.oee, 0) / data.length,
          avgAvailability: data.reduce((sum, d) => sum + d.availability, 0) / data.length,
          avgPerformance: data.reduce((sum, d) => sum + d.performance, 0) / data.length,
          avgQuality: data.reduce((sum, d) => sum + d.quality, 0) / data.length,
          avgProductivity: data.reduce((sum, d) => sum + d.productivity, 0) / data.length
        };
        
      default:
        return {};
    }
  }, []);

  // ===== MANIPULADORES DE EVENTOS =====

  /**
   * Gera o relatório
   */
  const handleGenerateReport = async () => {
    setIsGenerating(true);
    
    try {
      // Simula tempo de geração
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const { data, labels } = generateReportData(selectedReportType, reportParams);
      const charts = generateCharts(selectedReportType, data, labels);
      const summary = calculateSummary(selectedReportType, data);
      
      const reportData = {
        type: selectedReportType,
        params: reportParams,
        data,
        labels,
        charts,
        summary,
        generatedAt: new Date(),
        line: selectedLine
      };
      
      setReportData(reportData);
      
      // Adiciona ao histórico
      const newReport = {
        id: `RPT${String(reportHistory.length + 1).padStart(3, '0')}`,
        name: `${reportTypes[selectedReportType].name} - ${new Date().toLocaleDateString('pt-BR')}`,
        type: selectedReportType,
        line: selectedLine,
        createdAt: new Date(),
        size: `${(Math.random() * 3 + 1).toFixed(1)} MB`,
        status: 'completed'
      };
      
      setReportHistory(prev => [newReport, ...prev]);
      
    } catch (error) {
      console.error('Erro ao gerar relatório:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  /**
   * Visualiza relatório
   */
  const handlePreviewReport = () => {
    setShowPreviewModal(true);
  };

  /**
   * Baixa relatório
   */
  const handleDownloadReport = () => {
    // Simula download
    const blob = new Blob(['Conteúdo do relatório simulado'], { type: 'application/pdf' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `relatorio_${selectedReportType}_${selectedLine}_${new Date().toISOString().split('T')[0]}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  /**
   * Filtra histórico de relatórios
   */
  const filteredHistory = useMemo(() => {
    return reportHistory.filter(report => {
      const matchesSearch = report.name.toLowerCase().includes(filters.search.toLowerCase()) ||
                           report.id.toLowerCase().includes(filters.search.toLowerCase());
      const matchesType = filters.type === 'all' || report.type === filters.type;
      const matchesStatus = filters.status === 'all' || report.status === filters.status;
      
      return matchesSearch && matchesType && matchesStatus;
    });
  }, [reportHistory, filters]);

  // ===== RENDERIZAÇÃO CONDICIONAL =====

  if (!selectedLine) {
    return (
      <div className="no-line-selected">
        <FaIndustry className="no-line-icon" />
        <h3>Nenhuma Linha Selecionada</h3>
        <p>Selecione uma linha de produção para gerar relatórios.</p>
      </div>
    );
  }

  // ===== RENDERIZAÇÃO PRINCIPAL =====
  return (
    <div className="reports-content">
      {/* Header */}
      <div className="content-header">
        <div className="header-info">
          <h2 className="section-title">
            <FaFileAlt className="title-icon" />
            Sistema de Relatórios - {selectedLine}
          </h2>
          <p className="section-description">
            Gere relatórios detalhados com dados de produção, qualidade e performance
          </p>
        </div>
      </div>

      <Row>
        {/* Painel de Configuração */}
        <Col lg={4}>
          <Card className="config-card">
            <Card.Header>
              <h5>
                <FaCog className="me-2" />
                Configuração do Relatório
              </h5>
            </Card.Header>
            <Card.Body>
              {/* Tipo de Relatório */}
              <Form.Group className="mb-3">
                <Form.Label>Tipo de Relatório</Form.Label>
                {Object.entries(reportTypes).map(([key, type]) => {
                  const IconComponent = type.icon;
                  return (
                    <div key={key} className="report-type-option">
                      <Form.Check
                        type="radio"
                        id={`report-${key}`}
                        name="reportType"
                        value={key}
                        checked={selectedReportType === key}
                        onChange={(e) => setSelectedReportType(e.target.value)}
                        label={
                          <div className="report-type-label">
                            <div className="report-type-header">
                              <IconComponent className={`report-type-icon text-${type.color}`} />
                              <strong>{type.name}</strong>
                            </div>
                            <small className="text-muted">{type.description}</small>
                          </div>
                        }
                      />
                    </div>
                  );
                })}
              </Form.Group>

              {/* Período */}
              <Form.Group className="mb-3">
                <Form.Label>Período</Form.Label>
                <Form.Select
                  value={reportParams.dateRange}
                  onChange={(e) => setReportParams(prev => ({ ...prev, dateRange: e.target.value }))}
                >
                  <option value="last7days">Últimos 7 dias</option>
                  <option value="last30days">Últimos 30 dias</option>
                  <option value="last90days">Últimos 90 dias</option>
                  <option value="custom">Período personalizado</option>
                </Form.Select>
              </Form.Group>

              {/* Opções */}
              <Form.Group className="mb-3">
                <Form.Label>Opções</Form.Label>
                <div className="report-options">
                  <Form.Check
                    type="checkbox"
                    id="includeCharts"
                    label="Incluir gráficos"
                    checked={reportParams.includeCharts}
                    onChange={(e) => setReportParams(prev => ({ ...prev, includeCharts: e.target.checked }))}
                  />
                  <Form.Check
                    type="checkbox"
                    id="includeDetails"
                    label="Incluir detalhes"
                    checked={reportParams.includeDetails}
                    onChange={(e) => setReportParams(prev => ({ ...prev, includeDetails: e.target.checked }))}
                  />
                </div>
              </Form.Group>

              {/* Formato */}
              <Form.Group className="mb-4">
                <Form.Label>Formato</Form.Label>
                <Form.Select
                  value={reportParams.format}
                  onChange={(e) => setReportParams(prev => ({ ...prev, format: e.target.value }))}
                >
                  <option value="pdf">PDF</option>
                  <option value="excel">Excel</option>
                  <option value="csv">CSV</option>
                </Form.Select>
              </Form.Group>

              {/* Botões de Ação */}
              <div className="action-buttons">
                <Button
                  variant="primary"
                  onClick={handleGenerateReport}
                  disabled={isGenerating}
                  className="w-100 mb-2"
                >
                  {isGenerating ? (
                    <>
                      <Spinner animation="border" size="sm" className="me-2" />
                      Gerando...
                    </>
                  ) : (
                    <>
                      <FaPlus className="me-2" />
                      Gerar Relatório
                    </>
                  )}
                </Button>
                
                {reportData && (
                  <>
                    <Button
                      variant="outline-primary"
                      onClick={handlePreviewReport}
                      className="w-100 mb-2"
                    >
                      <FaEye className="me-2" />
                      Visualizar
                    </Button>
                    
                    <Button
                      variant="success"
                      onClick={handleDownloadReport}
                      className="w-100"
                    >
                      <FaDownload className="me-2" />
                      Baixar PDF
                    </Button>
                  </>
                )}
              </div>
            </Card.Body>
          </Card>
        </Col>

        {/* Painel Principal */}
        <Col lg={8}>
          {/* Visualização do Relatório */}
          {reportData && (
            <Card className="preview-card mb-4">
              <Card.Header>
                <h5>
                  <FaEye className="me-2" />
                  Prévia do Relatório
                </h5>
              </Card.Header>
              <Card.Body>
                {/* Resumo */}
                <div className="report-summary mb-4">
                  <h6>Resumo Executivo</h6>
                  <Row>
                    {Object.entries(reportData.summary).map(([key, value]) => (
                      <Col md={6} lg={4} key={key} className="mb-2">
                        <div className="summary-item">
                          <small className="summary-label">
                            {key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())}
                          </small>
                          <div className="summary-value">
                            {typeof value === 'number' ? value.toFixed(1) : value}
                            {key.includes('Rate') || key.includes('Efficiency') || key.includes('OEE') || key.includes('Performance') || key.includes('Quality') || key.includes('Availability') ? '%' : ''}
                          </div>
                        </div>
                      </Col>
                    ))}
                  </Row>
                </div>

                {/* Gráficos */}
                {reportParams.includeCharts && reportData.charts.length > 0 && (
                  <div className="report-charts">
                    <h6>Análise Gráfica</h6>
                    <Row>
                      {reportData.charts.map((chart, index) => (
                        <Col md={6} key={index} className="mb-4">
                          <div className="chart-preview">
                            <h6 className="chart-title">{chart.title}</h6>
                            <div className="chart-container">
                              {chart.type === 'bar' && <Bar data={chart.data} options={{ responsive: true, maintainAspectRatio: false }} />}
                              {chart.type === 'line' && <Line data={chart.data} options={{ responsive: true, maintainAspectRatio: false }} />}
                              {chart.type === 'doughnut' && <Doughnut data={chart.data} options={{ responsive: true, maintainAspectRatio: false }} />}
                              {chart.type === 'pie' && <Pie data={chart.data} options={{ responsive: true, maintainAspectRatio: false }} />}
                            </div>
                          </div>
                        </Col>
                      ))}
                    </Row>
                  </div>
                )}
              </Card.Body>
            </Card>
          )}

          {/* Histórico de Relatórios */}
          <Card className="history-card">
            <Card.Header>
              <div className="history-header">
                <h5>
                  <FaHistory className="me-2" />
                  Histórico de Relatórios
                </h5>
                
                {/* Filtros */}
                <div className="history-filters">
                  <InputGroup size="sm">
                    <InputGroup.Text>
                      <FaSearch />
                    </InputGroup.Text>
                    <Form.Control
                      type="text"
                      placeholder="Buscar..."
                      value={filters.search}
                      onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
                    />
                  </InputGroup>
                  
                  <Form.Select
                    size="sm"
                    value={filters.type}
                    onChange={(e) => setFilters(prev => ({ ...prev, type: e.target.value }))}
                  >
                    <option value="all">Todos os tipos</option>
                    {Object.entries(reportTypes).map(([key, type]) => (
                      <option key={key} value={key}>{type.name}</option>
                    ))}
                  </Form.Select>
                </div>
              </div>
            </Card.Header>
            <Card.Body>
              <Table responsive hover>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Nome</th>
                    <th>Tipo</th>
                    <th>Linha</th>
                    <th>Data</th>
                    <th>Tamanho</th>
                    <th>Status</th>
                    <th>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredHistory.map((report) => (
                    <tr key={report.id}>
                      <td>
                        <code>{report.id}</code>
                      </td>
                      <td>{report.name}</td>
                      <td>
                        <Badge bg={reportTypes[report.type]?.color || 'secondary'}>
                          {reportTypes[report.type]?.name || report.type}
                        </Badge>
                      </td>
                      <td>
                        <Badge bg="outline-primary">{report.line}</Badge>
                      </td>
                      <td>{report.createdAt.toLocaleDateString('pt-BR')}</td>
                      <td>{report.size}</td>
                      <td>
                        <Badge bg={report.status === 'completed' ? 'success' : 'warning'}>
                          {report.status === 'completed' ? 'Concluído' : 'Processando'}
                        </Badge>
                      </td>
                      <td>
                        <ButtonGroup size="sm">
                          <Button variant="outline-primary" title="Visualizar">
                            <FaEye />
                          </Button>
                          <Button variant="outline-success" title="Baixar">
                            <FaDownload />
                          </Button>
                          <Button variant="outline-secondary" title="Compartilhar">
                            <FaShare />
                          </Button>
                        </ButtonGroup>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              
              {filteredHistory.length === 0 && (
                <div className="no-reports">
                  <FaFileAlt className="no-reports-icon" />
                  <p>Nenhum relatório encontrado</p>
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Modal de Visualização */}
      <Modal show={showPreviewModal} onHide={() => setShowPreviewModal(false)} size="xl">
        <Modal.Header closeButton>
          <Modal.Title>Visualização do Relatório</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {reportData && (
            <div className="report-preview">
              <div className="report-header">
                <h4>{reportTypes[reportData.type].name}</h4>
                <p>Linha: {reportData.line} | Período: {reportData.params.dateRange}</p>
                <p>Gerado em: {reportData.generatedAt.toLocaleString('pt-BR')}</p>
              </div>
              
              <div className="report-content">
                {/* Conteúdo do relatório seria renderizado aqui */}
                <Alert variant="info">
                  <FaInfoCircle className="me-2" />
                  Esta é uma prévia do relatório. O documento completo será gerado no formato selecionado.
                </Alert>
              </div>
            </div>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowPreviewModal(false)}>
            Fechar
          </Button>
          <Button variant="primary" onClick={handleDownloadReport}>
            <FaDownload className="me-2" />
            Baixar PDF
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default ReportsContent;

