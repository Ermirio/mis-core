/**
 * KpisContent.js - Componente para exibição de KPIs (Key Performance Indicators)
 * 
 * Este componente exibe os principais indicadores de performance para uma linha
 * de produção selecionada, incluindo gráficos, métricas em tempo real e barras
 * de percentual relevantes para o ambiente industrial.
 * 
 * Funcionalidades:
 * - Exibição de indicadores de produção (Produção, Eficiência, Downtime)
 * - Barras de percentual para OEE, disponibilidade, qualidade e performance
 * - Gráficos de status da linha e utilização de recursos
 * - Atualização automática dos dados
 * - Design responsivo com cards informativos
 * 
 * @author Manus AI
 * @version 2.2.0
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  ProgressBar, 
  Card, 
  Row, 
  Col, 
  Badge, 
  Alert, 
  Button,
  Spinner
} from 'react-bootstrap';
import { Doughnut, Line, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Filler
} from 'chart.js';
import { 
  FaChartLine, 
  FaCogs, 
  FaExclamationTriangle, 
  FaCheckCircle,
  FaArrowUp,
  FaArrowDown,
  FaMinus,
  FaSyncAlt,
  FaIndustry,
  FaClipboardCheck,
  FaClock,
  FaTools,
  FaThermometerHalf,
  FaBolt,
  FaWater,
  FaGasPump
} from 'react-icons/fa';
import './KpisContent.css';

// Registro dos componentes do Chart.js
ChartJS.register(
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Filler
);

/**
 * Componente principal para exibição de KPIs
 * 
 * @param {Object} props - Propriedades do componente
 * @param {string} props.selectedLine - Linha de produção selecionada
 */
const KpisContent = ({ selectedLine }) => {
  // ===== ESTADOS DO COMPONENTE =====
  
  /**
   * Estado para dados dos KPIs principais
   */
  const [kpiData, setKpiData] = useState({
    oee: 0, // Overall Equipment Effectiveness
    availability: 0, // Disponibilidade
    performance: 0, // Performance
    quality: 0, // Qualidade
    production: 0, // Produção atual
    target: 0, // Meta de produção
    downtime: 0, // Tempo de parada
    efficiency: 0, // Eficiência geral
    defectRate: 0, // Taxa de defeitos
    cycleTime: 0, // Tempo de ciclo
    throughput: 0 // Taxa de produção
  });

  /**
   * Estado para dados de recursos e utilidades
   */
  const [resourceData, setResourceData] = useState({
    energy: 0, // Consumo de energia
    water: 0, // Consumo de água
    gas: 0, // Consumo de gás
    temperature: 0, // Temperatura
    pressure: 0, // Pressão
    vibration: 0 // Vibração
  });

  /**
   * Estado para histórico de produção
   */
  const [productionHistory, setProductionHistory] = useState([]);

  /**
   * Estado para controle de carregamento
   */
  const [isLoading, setIsLoading] = useState(true);

  /**
   * Estado para alertas
   */
  const [alerts, setAlerts] = useState([]);

  /**
   * Estado para última atualização
   */
  const [lastUpdate, setLastUpdate] = useState(new Date());

  // ===== FUNÇÕES AUXILIARES =====

  /**
   * Gera dados simulados de KPIs baseados na linha selecionada
   */
  const generateKpiData = useCallback((lineId) => {
    const lineNumber = parseInt(lineId?.replace('L', '') || '1', 10);
    const baseSeed = lineNumber * 100;
    
    // Simula dados realistas de OEE e componentes
    const availability = Math.max(75, Math.min(98, 85 + Math.random() * 10));
    const performance = Math.max(70, Math.min(95, 80 + Math.random() * 12));
    const quality = Math.max(85, Math.min(99, 92 + Math.random() * 6));
    const oee = (availability * performance * quality) / 10000;
    
    const production = Math.floor(800 + (baseSeed % 300) + Math.random() * 150);
    const target = 1000 + (lineNumber * 25);
    const efficiency = (production / target) * 100;
    const downtime = Math.max(0, Math.min(25, 15 - Math.random() * 10));
    const defectRate = Math.max(0.5, Math.min(8, 5 - Math.random() * 3));
    const cycleTime = Math.max(45, Math.min(90, 60 + Math.random() * 20));
    const throughput = Math.floor(production / 8); // Por hora

    return {
      oee: Math.round(oee * 10) / 10,
      availability: Math.round(availability * 10) / 10,
      performance: Math.round(performance * 10) / 10,
      quality: Math.round(quality * 10) / 10,
      production,
      target,
      downtime: Math.round(downtime * 10) / 10,
      efficiency: Math.round(efficiency * 10) / 10,
      defectRate: Math.round(defectRate * 10) / 10,
      cycleTime: Math.round(cycleTime),
      throughput
    };
  }, []);

  /**
   * Gera dados simulados de recursos
   */
  const generateResourceData = useCallback((lineId) => {
    const lineNumber = parseInt(lineId?.replace('L', '') || '1', 10);
    
    return {
      energy: Math.max(60, Math.min(95, 75 + Math.random() * 15)), // % da capacidade
      water: Math.max(40, Math.min(85, 60 + Math.random() * 20)),
      gas: Math.max(50, Math.min(90, 70 + Math.random() * 15)),
      temperature: Math.max(65, Math.min(85, 72 + Math.random() * 8)), // °C
      pressure: Math.max(80, Math.min(120, 95 + Math.random() * 20)), // PSI
      vibration: Math.max(0.1, Math.min(2.5, 1.2 + Math.random() * 0.8)) // mm/s
    };
  }, []);

  /**
   * Gera histórico de produção das últimas 12 horas
   */
  const generateProductionHistory = useCallback((lineId) => {
    const history = [];
    const now = new Date();
    
    for (let i = 11; i >= 0; i--) {
      const timestamp = new Date(now);
      timestamp.setHours(timestamp.getHours() - i);
      
      const kpis = generateKpiData(lineId);
      
      history.push({
        time: timestamp.getHours(),
        oee: kpis.oee,
        availability: kpis.availability,
        performance: kpis.performance,
        quality: kpis.quality,
        production: Math.floor(kpis.production / 8) // Por hora
      });
    }
    
    return history;
  }, [generateKpiData]);

  /**
   * Gera alertas baseados nos dados de KPI
   */
  const generateAlerts = useCallback((kpiData, resourceData) => {
    const alerts = [];
    
    if (kpiData.oee < 70) {
      alerts.push({
        type: 'danger',
        title: 'OEE Crítico',
        message: `OEE atual (${kpiData.oee}%) está abaixo do limite mínimo de 70%`,
        priority: 'alta'
      });
    }
    
    if (kpiData.availability < 80) {
      alerts.push({
        type: 'warning',
        title: 'Disponibilidade Baixa',
        message: `Disponibilidade (${kpiData.availability}%) precisa de atenção`,
        priority: 'media'
      });
    }
    
    if (resourceData.temperature > 80) {
      alerts.push({
        type: 'warning',
        title: 'Temperatura Elevada',
        message: `Temperatura atual (${resourceData.temperature}°C) acima do normal`,
        priority: 'media'
      });
    }
    
    if (resourceData.vibration > 2.0) {
      alerts.push({
        type: 'danger',
        title: 'Vibração Excessiva',
        message: `Vibração (${resourceData.vibration} mm/s) indica possível problema mecânico`,
        priority: 'alta'
      });
    }
    
    return alerts;
  }, []);

  /**
   * Carrega todos os dados para a linha selecionada
   */
  const loadData = useCallback(async () => {
    if (!selectedLine) return;
    
    setIsLoading(true);
    
    try {
      // Simula delay de carregamento
      await new Promise(resolve => setTimeout(resolve, 500));
      
      const kpis = generateKpiData(selectedLine);
      const resources = generateResourceData(selectedLine);
      const history = generateProductionHistory(selectedLine);
      const alertsData = generateAlerts(kpis, resources);
      
      setKpiData(kpis);
      setResourceData(resources);
      setProductionHistory(history);
      setAlerts(alertsData);
      setLastUpdate(new Date());
      
    } catch (error) {
      console.error('Erro ao carregar dados de KPI:', error);
    } finally {
      setIsLoading(false);
    }
  }, [selectedLine, generateKpiData, generateResourceData, generateProductionHistory, generateAlerts]);

  // ===== EFEITOS DO COMPONENTE =====

  /**
   * Carrega dados quando a linha muda
   */
  useEffect(() => {
    loadData();
  }, [loadData]);

  /**
   * Atualização automática a cada 30 segundos
   */
  useEffect(() => {
    const interval = setInterval(() => {
      if (!isLoading) {
        loadData();
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [isLoading, loadData]);

  // ===== DADOS PARA GRÁFICOS =====

  /**
   * Dados para gráfico de OEE (Doughnut)
   */
  const oeeChartData = useMemo(() => ({
    labels: ['Disponibilidade', 'Performance', 'Qualidade'],
    datasets: [{
      data: [kpiData.availability, kpiData.performance, kpiData.quality],
      backgroundColor: [
        '#3182ce', // Azul para disponibilidade
        '#38a169', // Verde para performance
        '#d69e2e'  // Amarelo para qualidade
      ],
      borderColor: [
        '#2c5282',
        '#2f855a',
        '#b7791f'
      ],
      borderWidth: 2
    }]
  }), [kpiData]);

  /**
   * Dados para gráfico de histórico (Line)
   */
  const historyChartData = useMemo(() => ({
    labels: productionHistory.map(item => `${item.time}h`),
    datasets: [
      {
        label: 'OEE (%)',
        data: productionHistory.map(item => item.oee),
        borderColor: '#3182ce',
        backgroundColor: 'rgba(49, 130, 206, 0.1)',
        fill: true,
        tension: 0.4
      },
      {
        label: 'Produção (un/h)',
        data: productionHistory.map(item => item.production),
        borderColor: '#38a169',
        backgroundColor: 'rgba(56, 161, 105, 0.1)',
        fill: false,
        tension: 0.4,
        yAxisID: 'y1'
      }
    ]
  }), [productionHistory]);

  /**
   * Opções para gráfico de histórico
   */
  const historyChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: 'Histórico de Performance (12h)'
      }
    },
    scales: {
      y: {
        type: 'linear',
        display: true,
        position: 'left',
        max: 100,
        title: {
          display: true,
          text: 'OEE (%)'
        }
      },
      y1: {
        type: 'linear',
        display: true,
        position: 'right',
        title: {
          display: true,
          text: 'Produção (un/h)'
        },
        grid: {
          drawOnChartArea: false,
        },
      }
    }
  };

  // ===== FUNÇÕES DE UTILIDADE =====

  /**
   * Retorna a cor da barra de progresso baseada no valor
   */
  const getProgressVariant = (value, thresholds = { good: 80, warning: 60 }) => {
    if (value >= thresholds.good) return 'success';
    if (value >= thresholds.warning) return 'warning';
    return 'danger';
  };

  /**
   * Retorna ícone de tendência baseado no valor
   */
  const getTrendIcon = (value, target = 80) => {
    if (value > target + 5) return <FaArrowUp className="trend-up" />;
    if (value < target - 5) return <FaArrowDown className="trend-down" />;
    return <FaMinus className="trend-stable" />;
  };

  /**
   * Formata valores numéricos
   */
  const formatValue = (value, unit = '%', decimals = 1) => {
    return `${value.toFixed(decimals)}${unit}`;
  };

  // ===== RENDERIZAÇÃO CONDICIONAL =====

  if (!selectedLine) {
    return (
      <div className="no-line-selected">
        <FaIndustry className="no-line-icon" />
        <h3>Nenhuma Linha Selecionada</h3>
        <p>Selecione uma linha de produção para visualizar os KPIs.</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="loading-container">
        <Spinner animation="border" variant="primary" size="lg" />
        <h4>Carregando KPIs...</h4>
        <p>Buscando dados da linha {selectedLine}</p>
      </div>
    );
  }

  // ===== RENDERIZAÇÃO PRINCIPAL =====
  return (
    <div className="kpis-content">
      {/* Header */}
      <div className="content-header">
        <div className="header-info">
          <h2 className="section-title">
            <FaChartLine className="title-icon" />
            KPIs - {selectedLine}
          </h2>
          <div className="header-meta">
            <span className="last-update">
              Última atualização: {lastUpdate.toLocaleTimeString('pt-BR')}
            </span>
          </div>
        </div>
        
        <div className="header-actions">
          <Button variant="outline-primary" size="sm" onClick={loadData}>
            <FaSyncAlt className="me-1" />
            Atualizar
          </Button>
        </div>
      </div>

      {/* Alertas */}
      {alerts.length > 0 && (
        <Row className="mb-4">
          <Col>
            <div className="alerts-container">
              {alerts.map((alert, index) => (
                <Alert key={index} variant={alert.type} className="alert-item">
                  <div className="alert-content">
                    <strong>{alert.title}</strong>
                    <p>{alert.message}</p>
                    <Badge bg={alert.priority === 'alta' ? 'danger' : 'warning'}>
                      {alert.priority}
                    </Badge>
                  </div>
                </Alert>
              ))}
            </div>
          </Col>
        </Row>
      )}

      {/* Cards de KPIs Principais */}
      <Row className="mb-4">
        {/* OEE Card */}
        <Col lg={3} md={6} className="mb-3">
          <Card className="kpi-card oee-card">
            <Card.Body>
              <div className="kpi-header">
                <div className="kpi-icon">
                  <FaCogs />
                </div>
                <div className="kpi-info">
                  <h6 className="kpi-label">OEE</h6>
                  <h3 className="kpi-value">{formatValue(kpiData.oee)}</h3>
                  <div className="kpi-trend">
                    {getTrendIcon(kpiData.oee, 75)}
                    <small>Overall Equipment Effectiveness</small>
                  </div>
                </div>
              </div>
              <ProgressBar 
                now={kpiData.oee}
                variant={getProgressVariant(kpiData.oee, { good: 75, warning: 60 })}
                className="kpi-progress"
              />
              <div className="kpi-components">
                <small>
                  A: {formatValue(kpiData.availability)} | 
                  P: {formatValue(kpiData.performance)} | 
                  Q: {formatValue(kpiData.quality)}
                </small>
              </div>
            </Card.Body>
          </Card>
        </Col>

        {/* Disponibilidade Card */}
        <Col lg={3} md={6} className="mb-3">
          <Card className="kpi-card availability-card">
            <Card.Body>
              <div className="kpi-header">
                <div className="kpi-icon">
                  <FaClock />
                </div>
                <div className="kpi-info">
                  <h6 className="kpi-label">Disponibilidade</h6>
                  <h3 className="kpi-value">{formatValue(kpiData.availability)}</h3>
                  <div className="kpi-trend">
                    {getTrendIcon(kpiData.availability, 85)}
                    <small>Tempo operacional</small>
                  </div>
                </div>
              </div>
              <ProgressBar 
                now={kpiData.availability}
                variant={getProgressVariant(kpiData.availability, { good: 85, warning: 75 })}
                className="kpi-progress"
              />
              <div className="kpi-details">
                <small>Downtime: {formatValue(kpiData.downtime)}%</small>
              </div>
            </Card.Body>
          </Card>
        </Col>

        {/* Performance Card */}
        <Col lg={3} md={6} className="mb-3">
          <Card className="kpi-card performance-card">
            <Card.Body>
              <div className="kpi-header">
                <div className="kpi-icon">
                  <FaIndustry />
                </div>
                <div className="kpi-info">
                  <h6 className="kpi-label">Performance</h6>
                  <h3 className="kpi-value">{formatValue(kpiData.performance)}</h3>
                  <div className="kpi-trend">
                    {getTrendIcon(kpiData.performance, 80)}
                    <small>Velocidade de produção</small>
                  </div>
                </div>
              </div>
              <ProgressBar 
                now={kpiData.performance}
                variant={getProgressVariant(kpiData.performance, { good: 80, warning: 70 })}
                className="kpi-progress"
              />
              <div className="kpi-details">
                <small>Ciclo: {kpiData.cycleTime}s | Taxa: {kpiData.throughput} un/h</small>
              </div>
            </Card.Body>
          </Card>
        </Col>

        {/* Qualidade Card */}
        <Col lg={3} md={6} className="mb-3"> 
          <Card className="kpi-card quality-card">
            <Card.Body>
              <div className="kpi-header">
                <div className="kpi-icon">
                  <FaClipboardCheck />
                  
                </div>
                <div className="kpi-info">
                  <h6 className="kpi-label">Qualidade</h6>
                  <h3 className="kpi-value">{formatValue(kpiData.quality)}</h3>
                  <div className="kpi-trend">
                    {getTrendIcon(kpiData.quality, 90)}
                    <small>Taxa de aprovação</small>
                  </div>
                </div>
              </div>
              <ProgressBar 
                now={kpiData.quality}
                variant={getProgressVariant(kpiData.quality, { good: 90, warning: 85 })}
                className="kpi-progress"
              />
              <div className="kpi-details">
                <small>Defeitos: {formatValue(kpiData.defectRate)}%</small>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Cards de Recursos e Utilidades */}
      <Row className="mb-4">
        <Col>
          <Card className="resources-card">
            <Card.Header>
              <h5>
                <FaTools className="me-2" />
                Recursos e Utilidades
              </h5>
            </Card.Header>
            <Card.Body>
              <Row>
                {/* Energia */}
                <Col lg={2} md={4} sm={6} className="mb-3">
                  <div className="resource-item">
                    <div className="resource-header">
                      <FaBolt className="resource-icon energy-icon" />
                      <span className="resource-label">Energia</span>
                    </div>
                    <div className="resource-value">
                      {formatValue(resourceData.energy)}
                    </div>
                    <ProgressBar 
                      now={resourceData.energy}
                      variant={getProgressVariant(resourceData.energy, { good: 70, warning: 50 })}
                      size="sm"
                      className="resource-progress"
                    />
                  </div>
                </Col>

                {/* Água */}
                <Col lg={2} md={4} sm={6} className="mb-3">
                  <div className="resource-item">
                    <div className="resource-header">
                      <FaWater className="resource-icon water-icon" />
                      <span className="resource-label">Água</span>
                    </div>
                    <div className="resource-value">
                      {formatValue(resourceData.water)}
                    </div>
                    <ProgressBar 
                      now={resourceData.water}
                      variant={getProgressVariant(resourceData.water, { good: 60, warning: 40 })}
                      size="sm"
                      className="resource-progress"
                    />
                  </div>
                </Col>

                {/* Gás */}
                <Col lg={2} md={4} sm={6} className="mb-3">
                  <div className="resource-item">
                    <div className="resource-header">
                      <FaGasPump className="resource-icon gas-icon" />
                      <span className="resource-label">Gás</span>
                    </div>
                    <div className="resource-value">
                      {formatValue(resourceData.gas)}
                    </div>
                    <ProgressBar 
                      now={resourceData.gas}
                      variant={getProgressVariant(resourceData.gas, { good: 70, warning: 50 })}
                      size="sm"
                      className="resource-progress"
                    />
                  </div>
                </Col>

                {/* Temperatura */}
                <Col lg={2} md={4} sm={6} className="mb-3">
                  <div className="resource-item">
                    <div className="resource-header">
                      <FaThermometerHalf className="resource-icon temp-icon" />
                      <span className="resource-label">Temperatura</span>
                    </div>
                    <div className="resource-value">
                      {formatValue(resourceData.temperature, '°C', 0)}
                    </div>
                    <ProgressBar 
                      now={(resourceData.temperature / 100) * 100}
                      variant={resourceData.temperature > 80 ? 'danger' : 
                              resourceData.temperature > 75 ? 'warning' : 'success'}
                      size="sm"
                      className="resource-progress"
                    />
                  </div>
                </Col>

                {/* Pressão */}
                <Col lg={2} md={4} sm={6} className="mb-3">
                  <div className="resource-item">
                    <div className="resource-header">
                      <FaCogs className="resource-icon pressure-icon" />
                      <span className="resource-label">Pressão</span>
                    </div>
                    <div className="resource-value">
                      {formatValue(resourceData.pressure, ' PSI', 0)}
                    </div>
                    <ProgressBar 
                      now={(resourceData.pressure / 120) * 100}
                      variant={resourceData.pressure > 110 ? 'danger' : 
                              resourceData.pressure > 100 ? 'warning' : 'success'}
                      size="sm"
                      className="resource-progress"
                    />
                  </div>
                </Col>

                {/* Vibração */}
                <Col lg={2} md={4} sm={6} className="mb-3">
                  <div className="resource-item">
                    <div className="resource-header">
                      <FaCogs className="resource-icon vibration-icon" />
                      <span className="resource-label">Vibração</span>
                    </div>
                    <div className="resource-value">
                      {formatValue(resourceData.vibration, ' mm/s')}
                    </div>
                    <ProgressBar 
                      now={(resourceData.vibration / 2.5) * 100}
                      variant={resourceData.vibration > 2.0 ? 'danger' : 
                              resourceData.vibration > 1.5 ? 'warning' : 'success'}
                      size="sm"
                      className="resource-progress"
                    />
                  </div>
                </Col>
              </Row>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Gráficos */}
      <Row>
        <Col lg={6}>
          <Card className="chart-card">
            <Card.Header>
              <h5>Componentes do OEE</h5>
            </Card.Header>
            <Card.Body>
              <div className="chart-container">
                <Doughnut 
                  data={oeeChartData} 
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                      legend: {
                        position: 'bottom'
                      }
                    }
                  }}
                />
              </div>
            </Card.Body>
          </Card>
        </Col>
        
        <Col lg={6}>
          <Card className="chart-card">
            <Card.Header>
              <h5>Histórico de Performance</h5>
            </Card.Header>
            <Card.Body>
              <div className="chart-container">
                <Line 
                  data={historyChartData} 
                  options={historyChartOptions}
                />
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default KpisContent;

