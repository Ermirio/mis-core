/**
 * ProcessVariablesContent.js - Componente para gestão de variáveis de processo em tempo real
 * 
 * Este componente oferece uma interface completa para monitoramento e controle
 * de variáveis de processo industrial em tempo real, incluindo:
 * - Gráficos dinâmicos de tendências
 * - Controles de setpoints
 * - Alarmes e alertas
 * - Botões de ação para controle do processo
 * 
 * @author Manus AI
 * @version 1.0.0
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Card, 
  Row, 
  Col, 
  Button, 
  Form, 
  Alert, 
  Badge, 
  Modal,
  ProgressBar,
  ButtonGroup,
  Spinner,
  InputGroup
} from 'react-bootstrap';
import { Line, Gauge } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { 
  FaThermometerHalf,
  FaTachometerAlt,
  FaWater,
  FaBolt,
  FaPlay,
  FaPause,
  FaStop,
  FaCog,
  FaExclamationTriangle,
  FaCheckCircle,
  FaInfoCircle,
  FaSyncAlt,
  FaChartLine,
  FaSliders,
  FaRobot,
  FaFlask,
  FaIndustry,
  FaGasPump
} from 'react-icons/fa';
import './ProcessVariablesContent.css';

// Registro dos componentes do Chart.js
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

/**
 * Componente principal para gestão de variáveis de processo
 */
const ProcessVariablesContent = ({ selectedLine }) => {
  // ===== ESTADOS DO COMPONENTE =====
  
  /**
   * Estado para variáveis de processo
   */
  const [processVariables, setProcessVariables] = useState({
    temperature: { value: 0, setpoint: 75, min: 60, max: 90, unit: '°C', status: 'normal' },
    pressure: { value: 0, setpoint: 100, min: 80, max: 120, unit: 'PSI', status: 'normal' },
    flow: { value: 0, setpoint: 50, min: 30, max: 70, unit: 'L/min', status: 'normal' },
    level: { value: 0, setpoint: 80, min: 20, max: 100, unit: '%', status: 'normal' },
    ph: { value: 0, setpoint: 7.0, min: 6.5, max: 7.5, unit: 'pH', status: 'normal' },
    conductivity: { value: 0, setpoint: 1500, min: 1000, max: 2000, unit: 'µS/cm', status: 'normal' }
  });

  /**
   * Estado para histórico de dados
   */
  const [historicalData, setHistoricalData] = useState({
    temperature: [],
    pressure: [],
    flow: [],
    level: [],
    ph: [],
    conductivity: []
  });

  /**
   * Estado para controle do processo
   */
  const [processControl, setProcessControl] = useState({
    status: 'running', // running, paused, stopped
    mode: 'automatic', // automatic, manual
    recipe: 'Recipe_A',
    batchNumber: 'BATCH_001',
    startTime: new Date(),
    elapsedTime: 0
  });

  /**
   * Estado para alarmes ativos
   */
  const [activeAlarms, setActiveAlarms] = useState([]);

  /**
   * Estado para modal de configuração
   */
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [configVariable, setConfigVariable] = useState(null);

  /**
   * Estado para controle de atualização
   */
  const [isUpdating, setIsUpdating] = useState(true);
  const [updateInterval, setUpdateInterval] = useState(2000); // 2 segundos

  /**
   * Estado para timestamps
   */
  const [timestamps, setTimestamps] = useState([]);

  // ===== FUNÇÕES AUXILIARES =====

  /**
   * Gera valor simulado para uma variável
   */
  const generateSimulatedValue = useCallback((variable, currentValue) => {
    const { setpoint, min, max } = processVariables[variable];
    const noise = (Math.random() - 0.5) * 2; // Ruído de -1 a 1
    const trend = (setpoint - currentValue) * 0.1; // Tendência para o setpoint
    
    let newValue = currentValue + trend + noise;
    
    // Mantém dentro dos limites
    newValue = Math.max(min, Math.min(max, newValue));
    
    return parseFloat(newValue.toFixed(2));
  }, [processVariables]);

  /**
   * Determina o status de uma variável baseado nos limites
   */
  const getVariableStatus = useCallback((value, variable) => {
    const { setpoint, min, max } = processVariables[variable];
    const tolerance = (max - min) * 0.1; // 10% de tolerância
    
    if (value < min + tolerance || value > max - tolerance) {
      return 'warning';
    }
    if (value < min || value > max) {
      return 'alarm';
    }
    if (Math.abs(value - setpoint) > tolerance) {
      return 'deviation';
    }
    return 'normal';
  }, [processVariables]);

  /**
   * Atualiza as variáveis de processo
   */
  const updateProcessVariables = useCallback(() => {
    if (!isUpdating || processControl.status === 'stopped') return;

    const now = new Date();
    const timeString = now.toLocaleTimeString('pt-BR');

    setProcessVariables(prev => {
      const updated = { ...prev };
      const newAlarms = [];

      Object.keys(updated).forEach(variable => {
        const currentValue = updated[variable].value;
        const newValue = generateSimulatedValue(variable, currentValue);
        const status = getVariableStatus(newValue, variable);

        updated[variable] = {
          ...updated[variable],
          value: newValue,
          status
        };

        // Gera alarmes se necessário
        if (status === 'alarm') {
          newAlarms.push({
            id: `${variable}_${Date.now()}`,
            variable,
            message: `${variable.toUpperCase()}: Valor fora dos limites (${newValue}${updated[variable].unit})`,
            severity: 'high',
            timestamp: now
          });
        }
      });

      // Atualiza alarmes
      setActiveAlarms(prevAlarms => {
        const filteredAlarms = prevAlarms.filter(alarm => 
          Date.now() - alarm.timestamp.getTime() < 30000 // Remove alarmes após 30s
        );
        return [...filteredAlarms, ...newAlarms];
      });

      return updated;
    });

    // Atualiza histórico
    setHistoricalData(prev => {
      const updated = { ...prev };
      Object.keys(processVariables).forEach(variable => {
        const history = [...updated[variable]];
        history.push({
          time: timeString,
          value: processVariables[variable].value,
          timestamp: now
        });
        
        // Mantém apenas os últimos 20 pontos
        if (history.length > 20) {
          history.shift();
        }
        
        updated[variable] = history;
      });
      return updated;
    });

    // Atualiza timestamps
    setTimestamps(prev => {
      const updated = [...prev, timeString];
      return updated.length > 20 ? updated.slice(-20) : updated;
    });

    // Atualiza tempo decorrido
    setProcessControl(prev => ({
      ...prev,
      elapsedTime: Math.floor((now - prev.startTime) / 1000)
    }));
  }, [isUpdating, processControl.status, generateSimulatedValue, getVariableStatus, processVariables]);

  // ===== EFEITOS DO COMPONENTE =====

  /**
   * Efeito para atualização automática
   */
  useEffect(() => {
    if (!isUpdating) return;

    const interval = setInterval(updateProcessVariables, updateInterval);
    return () => clearInterval(interval);
  }, [updateProcessVariables, updateInterval, isUpdating]);

  /**
   * Efeito para inicialização dos dados
   */
  useEffect(() => {
    // Inicializa com valores próximos aos setpoints
    setProcessVariables(prev => {
      const updated = { ...prev };
      Object.keys(updated).forEach(variable => {
        const { setpoint } = updated[variable];
        updated[variable].value = setpoint + (Math.random() - 0.5) * 5;
      });
      return updated;
    });
  }, [selectedLine]);

  // ===== MANIPULADORES DE EVENTOS =====

  /**
   * Controla o processo (start/pause/stop)
   */
  const handleProcessControl = (action) => {
    setProcessControl(prev => {
      switch (action) {
        case 'start':
          return { ...prev, status: 'running', startTime: new Date(), elapsedTime: 0 };
        case 'pause':
          return { ...prev, status: 'paused' };
        case 'stop':
          return { ...prev, status: 'stopped', elapsedTime: 0 };
        default:
          return prev;
      }
    });
  };

  /**
   * Alterna modo de controle
   */
  const handleModeToggle = () => {
    setProcessControl(prev => ({
      ...prev,
      mode: prev.mode === 'automatic' ? 'manual' : 'automatic'
    }));
  };

  /**
   * Abre modal de configuração
   */
  const handleConfigVariable = (variable) => {
    setConfigVariable(variable);
    setShowConfigModal(true);
  };

  /**
   * Salva configuração de variável
   */
  const handleSaveConfig = (newSetpoint) => {
    if (configVariable) {
      setProcessVariables(prev => ({
        ...prev,
        [configVariable]: {
          ...prev[configVariable],
          setpoint: parseFloat(newSetpoint)
        }
      }));
    }
    setShowConfigModal(false);
    setConfigVariable(null);
  };

  /**
   * Remove alarme
   */
  const handleDismissAlarm = (alarmId) => {
    setActiveAlarms(prev => prev.filter(alarm => alarm.id !== alarmId));
  };

  // ===== DADOS PARA GRÁFICOS =====

  /**
   * Dados para gráfico de tendências
   */
  const trendChartData = useMemo(() => {
    const datasets = Object.keys(processVariables).map((variable, index) => {
      const colors = [
        '#3182ce', '#38a169', '#d69e2e', '#e53e3e', '#805ad5', '#319795'
      ];
      
      return {
        label: variable.charAt(0).toUpperCase() + variable.slice(1),
        data: historicalData[variable]?.map(point => point.value) || [],
        borderColor: colors[index],
        backgroundColor: colors[index] + '20',
        fill: false,
        tension: 0.4
      };
    });

    return {
      labels: timestamps,
      datasets
    };
  }, [historicalData, timestamps, processVariables]);

  /**
   * Opções para gráfico de tendências
   */
  const trendChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: 'Tendências das Variáveis de Processo'
      }
    },
    scales: {
      y: {
        beginAtZero: false,
        title: {
          display: true,
          text: 'Valores'
        }
      },
      x: {
        title: {
          display: true,
          text: 'Tempo'
        }
      }
    },
    animation: {
      duration: 0 // Desabilita animação para melhor performance
    }
  };

  // ===== FUNÇÕES DE UTILIDADE =====

  /**
   * Retorna a cor baseada no status
   */
  const getStatusColor = (status) => {
    switch (status) {
      case 'alarm': return 'danger';
      case 'warning': return 'warning';
      case 'deviation': return 'info';
      case 'normal': return 'success';
      default: return 'secondary';
    }
  };

  /**
   * Retorna o ícone baseado na variável
   */
  const getVariableIcon = (variable) => {
    switch (variable) {
      case 'temperature': return FaThermometerHalf;
      case 'pressure': return FaTachometerAlt;
      case 'flow': return FaWater;
      case 'level': return FaFlask;
      case 'ph': return FaFlask;
      case 'conductivity': return FaBolt;
      default: return FaCog;
    }
  };

  /**
   * Formata tempo decorrido
   */
  const formatElapsedTime = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // ===== RENDERIZAÇÃO CONDICIONAL =====

  if (!selectedLine) {
    return (
      <div className="no-line-selected">
        <FaIndustry className="no-line-icon" />
        <h3>Nenhuma Linha Selecionada</h3>
        <p>Selecione uma linha de produção para visualizar as variáveis de processo.</p>
      </div>
    );
  }

  // ===== RENDERIZAÇÃO PRINCIPAL =====
  return (
    <div className="process-variables-content">
      {/* Header */}
      <div className="content-header">
        <div className="header-info">
          <h2 className="section-title">
            <FaChartLine className="title-icon" />
            Variáveis de Processo - {selectedLine}
          </h2>
          <div className="header-meta">
            <Badge bg={processControl.status === 'running' ? 'success' : 
                      processControl.status === 'paused' ? 'warning' : 'danger'}>
              {processControl.status.toUpperCase()}
            </Badge>
            <Badge bg={processControl.mode === 'automatic' ? 'primary' : 'secondary'}>
              {processControl.mode.toUpperCase()}
            </Badge>
            <span className="elapsed-time">
              Tempo: {formatElapsedTime(processControl.elapsedTime)}
            </span>
          </div>
        </div>
        
        <div className="header-actions">
          <ButtonGroup>
            <Button 
              variant="success" 
              onClick={() => handleProcessControl('start')}
              disabled={processControl.status === 'running'}
            >
              <FaPlay className="me-1" />
              Start
            </Button>
            <Button 
              variant="warning" 
              onClick={() => handleProcessControl('pause')}
              disabled={processControl.status !== 'running'}
            >
              <FaPause className="me-1" />
              Pause
            </Button>
            <Button 
              variant="danger" 
              onClick={() => handleProcessControl('stop')}
            >
              <FaStop className="me-1" />
              Stop
            </Button>
          </ButtonGroup>
          
          <Button 
            variant={processControl.mode === 'automatic' ? 'primary' : 'outline-primary'}
            onClick={handleModeToggle}
          >
            <FaRobot className="me-1" />
            {processControl.mode === 'automatic' ? 'Auto' : 'Manual'}
          </Button>
          
          <Button 
            variant="outline-secondary"
            onClick={() => setIsUpdating(!isUpdating)}
          >
            {isUpdating ? <FaPause className="me-1" /> : <FaPlay className="me-1" />}
            {isUpdating ? 'Pausar' : 'Retomar'}
          </Button>
        </div>
      </div>

      {/* Alarmes Ativos */}
      {activeAlarms.length > 0 && (
        <Row className="mb-4">
          <Col>
            <div className="alarms-container">
              {activeAlarms.slice(0, 3).map((alarm) => (
                <Alert 
                  key={alarm.id} 
                  variant="danger" 
                  dismissible
                  onClose={() => handleDismissAlarm(alarm.id)}
                  className="alarm-item"
                >
                  <div className="alarm-content">
                    <FaExclamationTriangle className="alarm-icon" />
                    <div className="alarm-details">
                      <strong>{alarm.message}</strong>
                      <small className="alarm-time">
                        {alarm.timestamp.toLocaleTimeString('pt-BR')}
                      </small>
                    </div>
                  </div>
                </Alert>
              ))}
            </div>
          </Col>
        </Row>
      )}

      {/* Cards de Variáveis */}
      <Row className="mb-4">
        {Object.entries(processVariables).map(([variable, data]) => {
          const IconComponent = getVariableIcon(variable);
          const percentage = ((data.value - data.min) / (data.max - data.min)) * 100;
          
          return (
            <Col lg={4} md={6} key={variable} className="mb-3">
              <Card className={`variable-card ${data.status}-card`}>
                <Card.Body>
                  <div className="variable-header">
                    <div className="variable-icon">
                      <IconComponent />
                    </div>
                    <div className="variable-info">
                      <h6 className="variable-label">
                        {variable.charAt(0).toUpperCase() + variable.slice(1)}
                      </h6>
                      <h3 className="variable-value">
                        {data.value}{data.unit}
                      </h3>
                      <small className="variable-setpoint">
                        Setpoint: {data.setpoint}{data.unit}
                      </small>
                    </div>
                    <Button
                      variant="outline-secondary"
                      size="sm"
                      onClick={() => handleConfigVariable(variable)}
                    >
                      <FaCog />
                    </Button>
                  </div>
                  
                  <ProgressBar 
                    now={percentage}
                    variant={getStatusColor(data.status)}
                    className="variable-progress"
                  />
                  
                  <div className="variable-limits">
                    <small>
                      Min: {data.min}{data.unit} | Max: {data.max}{data.unit}
                    </small>
                  </div>
                  
                  <Badge 
                    bg={getStatusColor(data.status)}
                    className="status-badge"
                  >
                    {data.status.toUpperCase()}
                  </Badge>
                </Card.Body>
              </Card>
            </Col>
          );
        })}
      </Row>

      {/* Gráfico de Tendências */}
      <Row>
        <Col>
          <Card className="chart-card">
            <Card.Header>
              <div className="chart-header">
                <h5>
                  <FaChartLine className="me-2" />
                  Tendências em Tempo Real
                </h5>
                <div className="chart-controls">
                  <Form.Select 
                    size="sm" 
                    value={updateInterval}
                    onChange={(e) => setUpdateInterval(parseInt(e.target.value))}
                    style={{ width: 'auto' }}
                  >
                    <option value={1000}>1s</option>
                    <option value={2000}>2s</option>
                    <option value={5000}>5s</option>
                    <option value={10000}>10s</option>
                  </Form.Select>
                  {isUpdating && (
                    <Spinner animation="border" size="sm" variant="primary" />
                  )}
                </div>
              </div>
            </Card.Header>
            <Card.Body>
              <div className="chart-container-large">
                <Line data={trendChartData} options={trendChartOptions} />
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Modal de Configuração */}
      <Modal show={showConfigModal} onHide={() => setShowConfigModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>
            Configurar {configVariable?.charAt(0).toUpperCase() + configVariable?.slice(1)}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {configVariable && (
            <Form>
              <Form.Group className="mb-3">
                <Form.Label>Novo Setpoint</Form.Label>
                <InputGroup>
                  <Form.Control
                    type="number"
                    step="0.1"
                    defaultValue={processVariables[configVariable]?.setpoint}
                    id="newSetpoint"
                  />
                  <InputGroup.Text>
                    {processVariables[configVariable]?.unit}
                  </InputGroup.Text>
                </InputGroup>
              </Form.Group>
              
              <div className="config-info">
                <small className="text-muted">
                  Limites: {processVariables[configVariable]?.min} - {processVariables[configVariable]?.max} {processVariables[configVariable]?.unit}
                </small>
              </div>
            </Form>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowConfigModal(false)}>
            Cancelar
          </Button>
          <Button 
            variant="primary" 
            onClick={() => {
              const newSetpoint = document.getElementById('newSetpoint').value;
              handleSaveConfig(newSetpoint);
            }}
          >
            Salvar
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default ProcessVariablesContent;

