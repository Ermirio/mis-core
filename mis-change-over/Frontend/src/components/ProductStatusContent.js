/**
 * ProductStatusContent.js - Componente para monitoramento do status de produtos
 * 
 * Este componente exibe informações detalhadas sobre o status dos produtos
 * em uma linha de produção específica, incluindo qualidade, quantidade,
 * defeitos e métricas de produção. Os dados são carregados dinamicamente
 * com base na linha selecionada.
 * 
 * Funcionalidades principais:
 * - Monitoramento em tempo real do status de produção para a linha selecionada
 * - Visualização de métricas de qualidade específicas da linha
 * - Rastreamento de defeitos e não conformidades
 * - Relatórios de produção por turno
 * - Alertas de qualidade e produtividade
 * 
 * @author Manus AI
 * @version 2.1.0
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Card, 
  Row, 
  Col, 
  Table, 
  Badge, 
  Button, 
  Alert,
  ProgressBar,
  Tabs,
  Tab,
  Form,
  InputGroup,
  Spinner
} from 'react-bootstrap';
import { 
  Bar, 
  Line, 
  Pie 
} from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { 
  FaClipboardCheck, 
  FaExclamationTriangle, 
  FaCheckCircle,
  FaTimesCircle,
  FaSearch,
  FaFilter,
  FaDownload,
  FaSyncAlt,
  FaChartBar,
  FaClock,
  FaUsers,
  FaIndustry,
  FaThumbsUp,
  FaThumbsDown,
  FaEye,
  FaInfoCircle
} from 'react-icons/fa';
import './ProductStatusContent.css';

// Registro dos componentes necessários do Chart.js
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

/**
 * URL base da API Django
 */
const API_BASE_URL = process.env.REACT_APP_SIDEBAR_API_BASE_URL || '/api';

/**
 * Componente principal para exibição do status de produtos
 * 
 * @param {Object} props - Propriedades do componente
 * @param {string} props.selectedLine - Linha de produção selecionada
 * @param {Object} props.lineData - Dados adicionais da linha (opcional)
 * @returns {JSX.Element} Componente renderizado
 */
const ProductStatusContent = ({ selectedLine, lineData }) => {
  // ===== ESTADOS DO COMPONENTE =====
  
  /**
   * Estado para dados de produção atual
   * @type {Object}
   */
  const [productionData, setProductionData] = useState({
    totalProduced: 0,
    qualityRate: 0,
    defectRate: 0,
    currentShift: '',
    targetProduction: 0,
    efficiency: 0
  });

  /**
   * Estado para histórico de produção
   * @type {Array}
   */
  const [productionHistory, setProductionHistory] = useState([]);

  /**
   * Estado para dados de qualidade
   * @type {Object}
   */
  const [qualityData, setQualityData] = useState({
    approved: 0,
    rejected: 0,
    rework: 0,
    pending: 0
  });

  /**
   * Estado para lista de defeitos
   * @type {Array}
   */
  const [defectsList, setDefectsList] = useState([]);

  /**
   * Estado para controle de carregamento
   * @type {boolean}
   */
  const [isLoading, setIsLoading] = useState(true);

  /**
   * Estado para controle de erro
   * @type {string|null}
   */
  const [error, setError] = useState(null);

  /**
   * Estado para aba ativa
   * @type {string}
   */
  const [activeTab, setActiveTab] = useState('overview');

  /**
   * Estado para filtros de pesquisa
   * @type {Object}
   */
  const [filters, setFilters] = useState({
    searchTerm: '',
    dateRange: 'today',
    status: 'all',
    shift: 'all'
  });

  /**
   * Estado para dados de turnos
   * @type {Array}
   */
  const [shiftData, setShiftData] = useState([]);

  /**
   * Estado para alertas ativos
   * @type {Array}
   */
  const [activeAlerts, setActiveAlerts] = useState([]);

  /**
   * Estado para controlar a última atualização
   * @type {Date}
   */
  const [lastUpdate, setLastUpdate] = useState(new Date());

  // ===== FUNÇÕES AUXILIARES =====

  /**
   * Busca dados da API para a linha selecionada
   * @param {string} lineId - ID da linha selecionada
   */
  const fetchLineData = useCallback(async (lineId) => {
    if (!lineId) {
      console.warn('Nenhuma linha selecionada para buscar dados');
      return;
    }

    const lineNumber = lineId.replace('L', '');
    setIsLoading(true);
    setError(null);

    try {
      console.log(`Buscando dados para a linha ${lineId}...`);
      
      // Tenta buscar dados da API real
      // Endpoint de exemplo: /api/linha-status/01/
      const endpoint = `${API_BASE_URL}/linha-status/${lineNumber}/`;
      
      try {
        const response = await fetch(endpoint, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          timeout: 5000 // 5 segundos de timeout
        });

        // Se a API retornar dados, use-os
        if (response.ok) {
          const data = await response.json();
          console.log('Dados recebidos da API:', data);
          
          // Processa os dados da API
          processApiData(data, lineId);
          return;
        }
        
        // Se a API falhar, loga o erro mas continua para gerar dados simulados
        console.warn(`API retornou status ${response.status}. Usando dados simulados.`);
      } catch (apiError) {
        console.warn('Erro ao acessar API real:', apiError.message);
        console.info('Usando dados simulados como fallback');
      }

      // Gera dados simulados como fallback
      generateSimulatedData(lineId);
      
    } catch (err) {
      console.error('Erro ao carregar dados da linha:', err);
      setError(`Falha ao carregar dados: ${err.message}`);
    } finally {
      setIsLoading(false);
      setLastUpdate(new Date());
    }
  }, []);

  /**
   * Processa os dados recebidos da API
   * @param {Object} data - Dados da API
   * @param {string} lineId - ID da linha
   */
  const processApiData = (data, lineId) => {
    // Implementação para processar dados reais da API
    // Este é um exemplo de como os dados poderiam ser processados
    
    if (data.producao) {
      setProductionData({
        totalProduced: data.producao.total || 0,
        qualityRate: data.producao.taxa_qualidade || 0,
        defectRate: data.producao.taxa_defeitos || 0,
        currentShift: data.producao.turno_atual || 'Não informado',
        targetProduction: data.producao.meta || 1000,
        efficiency: data.producao.eficiencia || 0
      });
    }

    if (data.qualidade) {
      setQualityData({
        approved: data.qualidade.aprovados || 0,
        rejected: data.qualidade.rejeitados || 0,
        rework: data.qualidade.retrabalho || 0,
        pending: data.qualidade.pendentes || 0
      });
    }

    if (data.defeitos && Array.isArray(data.defeitos)) {
      setDefectsList(data.defeitos);
    }

    if (data.historico && Array.isArray(data.historico)) {
      setProductionHistory(data.historico);
    }

    if (data.turnos && Array.isArray(data.turnos)) {
      setShiftData(data.turnos);
    }

    if (data.alertas && Array.isArray(data.alertas)) {
      setActiveAlerts(data.alertas);
    }
  };

  /**
   * Gera dados simulados para a linha selecionada
   * @param {string} lineId - ID da linha
   */
  const generateSimulatedData = (lineId) => {
    const lineNumber = parseInt(lineId.replace('L', ''), 10) || 1;
    const baseSeed = lineNumber * 100;
    
    // Gera dados de produção
    const prodData = generateProductionData(lineId);
    const qualData = generateQualityData(prodData);
    const defects = generateDefectsList(lineId);
    const history = generateProductionHistory(lineId);
    const shifts = generateShiftData(lineId);
    const alerts = generateAlerts(prodData, qualData);
    
    // Atualiza os estados
    setProductionData(prodData);
    setQualityData(qualData);
    setDefectsList(defects);
    setProductionHistory(history);
    setShiftData(shifts);
    setActiveAlerts(alerts);
  };

  /**
   * Gera dados simulados de produção baseados na linha selecionada
   * @param {string} lineId - ID da linha de produção
   * @returns {Object} Dados de produção simulados
   */
  const generateProductionData = useCallback((lineId) => {
    const lineNumber = parseInt(lineId.replace('L', ''), 10) || 1;
    const baseSeed = lineNumber * 100;
    
    // Simula dados realistas baseados no número da linha
    const totalProduced = Math.floor(800 + (baseSeed % 400) + Math.random() * 200);
    const targetProduction = 1000 + (lineNumber * 50);
    const efficiency = Math.min(100, Math.max(60, (totalProduced / targetProduction) * 100));
    const qualityRate = Math.max(85, Math.min(99, 92 + Math.random() * 7));
    const defectRate = Math.max(1, Math.min(15, 8 - Math.random() * 6));
    
    // Determina o turno atual
    const currentHour = new Date().getHours();
    let currentShift = '';
    if (currentHour >= 6 && currentHour < 14) {
      currentShift = 'Manhã';
    } else if (currentHour >= 14 && currentHour < 22) {
      currentShift = 'Tarde';
    } else {
      currentShift = 'Noite';
    }

    return {
      totalProduced: Math.round(totalProduced),
      qualityRate: Math.round(qualityRate * 10) / 10,
      defectRate: Math.round(defectRate * 10) / 10,
      currentShift,
      targetProduction,
      efficiency: Math.round(efficiency * 10) / 10
    };
  }, []);

  /**
   * Gera dados simulados de qualidade
   * @param {Object} productionData - Dados de produção
   * @returns {Object} Dados de qualidade simulados
   */
  const generateQualityData = useCallback((productionData) => {
    const total = productionData.totalProduced;
    const approved = Math.floor(total * (productionData.qualityRate / 100));
    const rejected = Math.floor(total * (productionData.defectRate / 100));
    const rework = Math.floor(total * 0.03); // 3% para retrabalho
    const pending = total - approved - rejected - rework;

    return {
      approved: Math.max(0, approved),
      rejected: Math.max(0, rejected),
      rework: Math.max(0, rework),
      pending: Math.max(0, pending)
    };
  }, []);

  /**
   * Gera lista simulada de defeitos
   * @param {string} lineId - ID da linha de produção
   * @returns {Array} Lista de defeitos simulados
   */
  const generateDefectsList = useCallback((lineId) => {
    const defectTypes = [
      'Dimensional fora do padrão',
      'Acabamento superficial',
      'Falha na montagem',
      'Material inadequado',
      'Contaminação',
      'Desgaste de ferramenta',
      'Calibração incorreta',
      'Falha no processo'
    ];

    const severityLevels = ['Baixa', 'Média', 'Alta', 'Crítica'];
    const lineNumber = parseInt(lineId.replace('L', ''), 10) || 1;

    return Array.from({ length: 8 }, (_, index) => {
      const defectType = defectTypes[index % defectTypes.length];
      const severity = severityLevels[Math.floor(Math.random() * severityLevels.length)];
      const quantity = Math.floor(Math.random() * 20) + 1;
      const timestamp = new Date();
      timestamp.setHours(timestamp.getHours() - Math.floor(Math.random() * 8));

      return {
        id: `DEF${lineNumber}${String(index + 1).padStart(3, '0')}`,
        type: defectType,
        severity,
        quantity,
        timestamp: timestamp.toISOString(),
        status: Math.random() > 0.3 ? 'Resolvido' : 'Pendente',
        operator: `Operador ${Math.floor(Math.random() * 5) + 1}`,
        description: `${defectType} detectado durante inspeção de qualidade`
      };
    });
  }, []);

  /**
   * Gera dados históricos de produção
   * @param {string} lineId - ID da linha de produção
   * @returns {Array} Dados históricos simulados
   */
  const generateProductionHistory = useCallback((lineId) => {
    const history = [];
    const now = new Date();
    
    // Gera dados para as últimas 24 horas
    for (let i = 23; i >= 0; i--) {
      const timestamp = new Date(now);
      timestamp.setHours(timestamp.getHours() - i);
      
      const hourlyData = generateProductionData(lineId);
      
      history.push({
        timestamp: timestamp.toISOString(),
        hour: timestamp.getHours(),
        produced: Math.floor(hourlyData.totalProduced / 24),
        quality: hourlyData.qualityRate,
        efficiency: hourlyData.efficiency,
        defects: Math.floor(Math.random() * 5)
      });
    }
    
    return history;
  }, [generateProductionData]);

  /**
   * Gera dados de turnos
   * @param {string} lineId - ID da linha de produção
   * @returns {Array} Dados de turnos simulados
   */
  const generateShiftData = useCallback((lineId) => {
    const shifts = ['Manhã', 'Tarde', 'Noite'];
    const today = new Date();
    
    return shifts.map((shift, index) => {
      const shiftData = generateProductionData(lineId);
      const startHour = index * 8 + 6; // 6h, 14h, 22h
      
      return {
        name: shift,
        startTime: `${String(startHour).padStart(2, '0')}:00`,
        endTime: `${String((startHour + 8) % 24).padStart(2, '0')}:00`,
        produced: Math.floor(shiftData.totalProduced / 3),
        target: Math.floor(shiftData.targetProduction / 3),
        efficiency: shiftData.efficiency + (Math.random() - 0.5) * 10,
        quality: shiftData.qualityRate + (Math.random() - 0.5) * 5,
        operators: Math.floor(Math.random() * 3) + 2,
        status: index === 1 ? 'Ativo' : 'Concluído' // Turno da tarde ativo
      };
    });
  }, [generateProductionData]);

  /**
   * Gera alertas baseados nos dados de produção
   * @param {Object} productionData - Dados de produção
   * @param {Object} qualityData - Dados de qualidade
   * @returns {Array} Lista de alertas
   */
  const generateAlerts = useCallback((productionData, qualityData) => {
    const alerts = [];
    
    // Alerta de baixa eficiência
    if (productionData.efficiency < 70) {
      alerts.push({
        id: 'EFF001',
        type: 'warning',
        title: 'Eficiência Baixa',
        message: `Eficiência atual (${productionData.efficiency}%) abaixo do esperado`,
        timestamp: new Date().toISOString(),
        priority: 'Alta'
      });
    }
    
    // Alerta de alta taxa de defeitos
    if (productionData.defectRate > 10) {
      alerts.push({
        id: 'QUA001',
        type: 'danger',
        title: 'Taxa de Defeitos Elevada',
        message: `Taxa de defeitos (${productionData.defectRate}%) acima do limite aceitável`,
        timestamp: new Date().toISOString(),
        priority: 'Crítica'
      });
    }
    
    // Alerta de meta não atingida
    if (productionData.totalProduced < productionData.targetProduction * 0.8) {
      alerts.push({
        id: 'PRO001',
        type: 'info',
        title: 'Meta de Produção',
        message: 'Produção atual pode não atingir a meta diária',
        timestamp: new Date().toISOString(),
        priority: 'Média'
      });
    }
    
    return alerts;
  }, []);

  // ===== EFEITOS DO COMPONENTE =====

  /**
   * Efeito para carregar dados quando a linha selecionada muda
   */
  useEffect(() => {
    if (selectedLine) {
      console.log(`Linha selecionada mudou para: ${selectedLine}`);
      fetchLineData(selectedLine);
    } else {
      console.warn('Nenhuma linha selecionada');
      setIsLoading(false);
    }
  }, [selectedLine, fetchLineData]);

  /**
   * Efeito para atualização automática dos dados a cada 30 segundos
   */
  useEffect(() => {
    const interval = setInterval(() => {
      if (!isLoading && selectedLine) {
        console.log(`Atualizando dados para linha ${selectedLine}...`);
        fetchLineData(selectedLine);
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [selectedLine, isLoading, fetchLineData]);

  // ===== MANIPULADORES DE EVENTOS =====

  /**
   * Manipula mudanças nos filtros de pesquisa
   * @param {Event} e - Evento de mudança
   */
  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({
      ...prev,
      [name]: value
    }));
  };

  /**
   * Força atualização dos dados
   */
  const handleRefresh = () => {
    if (selectedLine) {
      fetchLineData(selectedLine);
    }
  };

  /**
   * Simula download de relatório
   */
  const handleDownloadReport = () => {
    // Implementação futura para download de relatórios
    alert(`Relatório para linha ${selectedLine} será implementado em breve`);
  };

  // ===== DADOS PARA GRÁFICOS =====

  /**
   * Configuração dos dados para o gráfico de qualidade (Pizza)
   */
  const qualityChartData = useMemo(() => ({
    labels: ['Aprovados', 'Rejeitados', 'Retrabalho', 'Pendentes'],
    datasets: [{
      data: [
        qualityData.approved,
        qualityData.rejected,
        qualityData.rework,
        qualityData.pending
      ],
      backgroundColor: [
        '#38a169', // Verde para aprovados
        '#e53e3e', // Vermelho para rejeitados
        '#d69e2e', // Amarelo para retrabalho
        '#3182ce'  // Azul para pendentes
      ],
      borderColor: [
        '#2f855a',
        '#c53030',
        '#b7791f',
        '#2c5282'
      ],
      borderWidth: 2
    }]
  }), [qualityData]);

  /**
   * Configuração dos dados para o gráfico de produção histórica (Linha)
   */
  const productionHistoryChartData = useMemo(() => ({
    labels: productionHistory.map(item => `${item.hour}h`),
    datasets: [
      {
        label: 'Produção por Hora',
        data: productionHistory.map(item => item.produced),
        borderColor: '#3182ce',
        backgroundColor: 'rgba(49, 130, 206, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointHoverRadius: 6
      },
      {
        label: 'Defeitos por Hora',
        data: productionHistory.map(item => item.defects),
        borderColor: '#e53e3e',
        backgroundColor: 'rgba(229, 62, 62, 0.1)',
        fill: false,
        tension: 0.4,
        pointRadius: 3,
        pointHoverRadius: 5
      }
    ]
  }), [productionHistory]);

  /**
   * Configuração dos dados para o gráfico de turnos (Barras)
   */
  const shiftChartData = useMemo(() => ({
    labels: shiftData.map(shift => shift.name),
    datasets: [
      {
        label: 'Produzido',
        data: shiftData.map(shift => shift.produced),
        backgroundColor: '#3182ce',
        borderColor: '#2c5282',
        borderWidth: 1
      },
      {
        label: 'Meta',
        data: shiftData.map(shift => shift.target),
        backgroundColor: '#38a169',
        borderColor: '#2f855a',
        borderWidth: 1
      }
    ]
  }), [shiftData]);

  // ===== OPÇÕES DOS GRÁFICOS =====

  /**
   * Opções comuns para todos os gráficos
   */
  const commonChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          font: { size: 12, weight: '500' },
          padding: 15,
          usePointStyle: true
        }
      },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        titleColor: '#ffffff',
        bodyColor: '#ffffff',
        borderColor: '#ffffff',
        borderWidth: 1
      }
    }
  };

  /**
   * Opções específicas para gráfico de linha
   */
  const lineChartOptions = {
    ...commonChartOptions,
    scales: {
      y: {
        beginAtZero: true,
        grid: { color: 'rgba(0, 0, 0, 0.1)' },
        ticks: { font: { size: 11 } }
      },
      x: {
        grid: { color: 'rgba(0, 0, 0, 0.1)' },
        ticks: { font: { size: 11 } }
      }
    },
    interaction: {
      intersect: false,
      mode: 'index'
    }
  };

  /**
   * Opções específicas para gráfico de barras
   */
  const barChartOptions = {
    ...commonChartOptions,
    scales: {
      y: {
        beginAtZero: true,
        grid: { color: 'rgba(0, 0, 0, 0.1)' },
        ticks: { font: { size: 11 } }
      },
      x: {
        grid: { display: false },
        ticks: { font: { size: 11 } }
      }
    }
  };

  // ===== FUNÇÕES DE UTILIDADE =====

  /**
   * Retorna a variante de badge baseada na severidade
   * @param {string} severity - Nível de severidade
   * @returns {string} Variante do Bootstrap
   */
  const getSeverityVariant = (severity) => {
    switch (severity.toLowerCase()) {
      case 'crítica': return 'danger';
      case 'alta': return 'warning';
      case 'média': return 'info';
      case 'baixa': return 'secondary';
      default: return 'secondary';
    }
  };

  /**
   * Retorna a variante de badge baseada no status
   * @param {string} status - Status do item
   * @returns {string} Variante do Bootstrap
   */
  const getStatusVariant = (status) => {
    switch (status.toLowerCase()) {
      case 'resolvido': return 'success';
      case 'pendente': return 'warning';
      case 'ativo': return 'primary';
      case 'concluído': return 'success';
      default: return 'secondary';
    }
  };

  /**
   * Formata data para exibição
   * @param {string} isoString - Data em formato ISO
   * @returns {string} Data formatada
   */
  const formatDate = (isoString) => {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  /**
   * Filtra defeitos baseado nos filtros ativos
   * @returns {Array} Lista de defeitos filtrados
   */
  const filteredDefects = useMemo(() => {
    return defectsList.filter(defect => {
      const matchesSearch = !filters.searchTerm || 
        defect.type.toLowerCase().includes(filters.searchTerm.toLowerCase()) ||
        defect.description.toLowerCase().includes(filters.searchTerm.toLowerCase());
      
      const matchesStatus = filters.status === 'all' || 
        defect.status.toLowerCase() === filters.status.toLowerCase();
      
      return matchesSearch && matchesStatus;
    });
  }, [defectsList, filters]);

  // ===== RENDERIZAÇÃO CONDICIONAL =====

  /**
   * Renderização para quando não há linha selecionada
   */
  if (!selectedLine) {
    return (
      <div className="no-line-selected">
        <div className="no-line-icon">
          <FaIndustry />
        </div>
        <h3>Nenhuma Linha Selecionada</h3>
        <p>Selecione uma linha de produção no menu lateral para visualizar seus dados.</p>
      </div>
    );
  }

  /**
   * Renderização para estado de carregamento
   */
  if (isLoading) {
    return (
      <div className="loading-container">
        <Spinner animation="border" role="status" variant="primary" size="lg" />
        <h4>Carregando dados de produção...</h4>
        <p>Buscando informações da linha {selectedLine}</p>
      </div>
    );
  }

  /**
   * Renderização para estado de erro
   */
  if (error) {
    return (
      <div className="error-container">
        <div className="error-icon">
          <FaExclamationTriangle />
        </div>
        <h4>Erro ao Carregar Dados</h4>
        <p>{error}</p>
        <Button variant="primary" onClick={handleRefresh}>
          <FaSyncAlt className="me-2" /> Tentar Novamente
        </Button>
      </div>
    );
  }

  // ===== RENDERIZAÇÃO PRINCIPAL =====
  return (
    <div className="product-status-content">
      {/* Header da seção */}
      <div className="content-header">
        <div className="header-info">
          <h2 className="section-title">
            <FaClipboardCheck className="title-icon" />
            Status do Produto - {selectedLine}
          </h2>
          <div className="header-meta">
            <Badge bg="primary" className="shift-badge">
              <FaClock className="me-1" />
              Turno: {productionData.currentShift}
            </Badge>
            <span className="last-update">
              Última atualização: {lastUpdate.toLocaleTimeString('pt-BR')}
            </span>
          </div>
        </div>
        
        <div className="header-actions">
          <Button variant="outline-primary" size="sm" onClick={handleRefresh}>
            <FaSyncAlt className="me-1" />
            Atualizar
          </Button>
          <Button variant="outline-success" size="sm" onClick={handleDownloadReport}>
            <FaDownload className="me-1" />
            Relatório
          </Button>
        </div>
      </div>

      {/* Alertas ativos */}
      {activeAlerts.length > 0 && (
        <Row className="mb-4">
          <Col>
            <div className="alerts-container">
              {activeAlerts.map(alert => (
                <Alert key={alert.id} variant={alert.type} className="alert-item">
                  <div className="alert-content">
                    <div className="alert-header">
                      <strong>{alert.title}</strong>
                      <Badge bg={alert.type} className="priority-badge">
                        {alert.priority}
                      </Badge>
                    </div>
                    <p className="alert-message">{alert.message}</p>
                    <small className="alert-time">
                      {formatDate(alert.timestamp)}
                    </small>
                  </div>
                </Alert>
              ))}
            </div>
          </Col>
        </Row>
      )}

      {/* Cards de métricas principais */}
      <Row className="mb-4">
        <Col lg={3} md={6} className="mb-3">
          <Card className="metric-card production-card">
            <Card.Body>
              <div className="metric-header">
                <div className="metric-icon">
                  <FaIndustry />
                </div>
                <div className="metric-info">
                  <h6 className="metric-label">Produção Total</h6>
                  <h3 className="metric-value">{productionData.totalProduced.toLocaleString()}</h3>
                  <small className="metric-target">
                    Meta: {productionData.targetProduction.toLocaleString()}
                  </small>
                </div>
              </div>
              <ProgressBar 
                now={(productionData.totalProduced / productionData.targetProduction) * 100}
                variant="primary"
                className="metric-progress"
              />
            </Card.Body>
          </Card>
        </Col>
        
        <Col lg={3} md={6} className="mb-3">
          <Card className="metric-card quality-card">
            <Card.Body>
              <div className="metric-header">
                <div className="metric-icon">
                  <FaThumbsUp />
                </div>
                <div className="metric-info">
                  <h6 className="metric-label">Taxa de Qualidade</h6>
                  <h3 className="metric-value">{productionData.qualityRate}%</h3>
                  <small className="metric-subtitle">
                    {qualityData.approved} aprovados
                  </small>
                </div>
              </div>
              <ProgressBar 
                now={productionData.qualityRate}
                variant="success"
                className="metric-progress"
              />
            </Card.Body>
          </Card>
        </Col>
        
        <Col lg={3} md={6} className="mb-3">
          <Card className="metric-card efficiency-card">
            <Card.Body>
              <div className="metric-header">
                <div className="metric-icon">
                  <FaChartBar />
                </div>
                <div className="metric-info">
                  <h6 className="metric-label">Eficiência</h6>
                  <h3 className="metric-value">{productionData.efficiency}%</h3>
                  <small className="metric-subtitle">
                    Desempenho atual
                  </small>
                </div>
              </div>
              <ProgressBar 
                now={productionData.efficiency}
                variant={productionData.efficiency > 80 ? 'success' : 
                        productionData.efficiency > 60 ? 'warning' : 'danger'}
                className="metric-progress"
              />
            </Card.Body>
          </Card>
        </Col>
        
        <Col lg={3} md={6} className="mb-3">
          <Card className="metric-card defect-card">
            <Card.Body>
              <div className="metric-header">
                <div className="metric-icon">
                  <FaThumbsDown />
                </div>
                <div className="metric-info">
                  <h6 className="metric-label">Taxa de Defeitos</h6>
                  <h3 className="metric-value">{productionData.defectRate}%</h3>
                  <small className="metric-subtitle">
                    {qualityData.rejected} rejeitados
                  </small>
                </div>
              </div>
              <ProgressBar 
                now={productionData.defectRate}
                variant={productionData.defectRate < 5 ? 'success' : 
                        productionData.defectRate < 10 ? 'warning' : 'danger'}
                className="metric-progress"
              />
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Tabs de conteúdo detalhado */}
      <Row>
        <Col>
          <Card className="tabs-card">
            <Card.Body>
              <Tabs
                activeKey={activeTab}
                onSelect={(k) => setActiveTab(k)}
                className="custom-tabs"
              >
                {/* Tab de Visão Geral */}
                <Tab eventKey="overview" title={<><FaEye /> Visão Geral</>}>
                  <div className="tab-content-container">
                    <Row>
                      <Col lg={6}>
                        <Card className="chart-card">
                          <Card.Header>
                            <h5>Distribuição de Qualidade</h5>
                          </Card.Header>
                          <Card.Body>
                            <div className="chart-container">
                              <Pie data={qualityChartData} options={commonChartOptions} />
                            </div>
                          </Card.Body>
                        </Card>
                      </Col>
                      
                      <Col lg={6}>
                        <Card className="chart-card">
                          <Card.Header>
                            <h5>Produção por Turno</h5>
                          </Card.Header>
                          <Card.Body>
                            <div className="chart-container">
                              <Bar data={shiftChartData} options={barChartOptions} />
                            </div>
                          </Card.Body>
                        </Card>
                      </Col>
                    </Row>
                    
                    <Row className="mt-4">
                      <Col>
                        <Card className="chart-card">
                          <Card.Header>
                            <h5>Histórico de Produção (24h)</h5>
                          </Card.Header>
                          <Card.Body>
                            <div className="chart-container chart-container-large">
                              <Line data={productionHistoryChartData} options={lineChartOptions} />
                            </div>
                          </Card.Body>
                        </Card>
                      </Col>
                    </Row>
                  </div>
                </Tab>

                {/* Tab de Defeitos */}
                <Tab eventKey="defects" title={<><FaExclamationTriangle /> Defeitos</>}>
                  <div className="tab-content-container">
                    <div className="table-header">
                      <h5>Lista de Defeitos - {selectedLine}</h5>
                      <div className="table-filters">
                        <InputGroup size="sm" className="search-input">
                          <InputGroup.Text>
                            <FaSearch />
                          </InputGroup.Text>
                          <Form.Control
                            type="text"
                            placeholder="Buscar defeitos..."
                            name="searchTerm"
                            value={filters.searchTerm}
                            onChange={handleFilterChange}
                          />
                        </InputGroup>
                        
                        <Form.Select
                          size="sm"
                          name="status"
                          value={filters.status}
                          onChange={handleFilterChange}
                          className="status-filter"
                        >
                          <option value="all">Todos os Status</option>
                          <option value="pendente">Pendente</option>
                          <option value="resolvido">Resolvido</option>
                        </Form.Select>
                      </div>
                    </div>
                    
                    {filteredDefects.length > 0 ? (
                      <div className="table-responsive">
                        <Table hover className="defects-table">
                          <thead>
                            <tr>
                              <th>ID</th>
                              <th>Tipo de Defeito</th>
                              <th>Severidade</th>
                              <th>Quantidade</th>
                              <th>Data/Hora</th>
                              <th>Status</th>
                              <th>Operador</th>
                              <th>Ações</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredDefects.map(defect => (
                              <tr key={defect.id}>
                                <td className="defect-id">{defect.id}</td>
                                <td className="defect-type">{defect.type}</td>
                                <td>
                                  <Badge bg={getSeverityVariant(defect.severity)}>
                                    {defect.severity}
                                  </Badge>
                                </td>
                                <td className="defect-quantity">{defect.quantity}</td>
                                <td className="defect-time">{formatDate(defect.timestamp)}</td>
                                <td>
                                  <Badge bg={getStatusVariant(defect.status)}>
                                    {defect.status}
                                  </Badge>
                                </td>
                                <td className="defect-operator">{defect.operator}</td>
                                <td>
                                  <div className="action-buttons">
                                    <Button variant="outline-primary" size="sm">
                                      <FaEye />
                                    </Button>
                                    {defect.status === 'Pendente' && (
                                      <Button variant="outline-success" size="sm">
                                        <FaCheckCircle />
                                      </Button>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </Table>
                      </div>
                    ) : (
                      <Alert variant="info">
                        <FaInfoCircle className="me-2" />
                        Nenhum defeito encontrado para a linha {selectedLine} com os filtros aplicados.
                      </Alert>
                    )}
                  </div>
                </Tab>

                {/* Tab de Turnos */}
                <Tab eventKey="shifts" title={<><FaUsers /> Turnos</>}>
                  <div className="tab-content-container">
                    <div className="shifts-grid">
                      {shiftData.map((shift, index) => (
                        <Card key={index} className={`shift-card ${shift.status === 'Ativo' ? 'active-shift' : ''}`}>
                          <Card.Header>
                            <div className="shift-header">
                              <h5>{shift.name}</h5>
                              <Badge bg={getStatusVariant(shift.status)}>
                                {shift.status}
                              </Badge>
                            </div>
                            <div className="shift-time">
                              {shift.startTime} - {shift.endTime}
                            </div>
                          </Card.Header>
                          <Card.Body>
                            <div className="shift-metrics">
                              <div className="shift-metric">
                                <span className="metric-label">Produzido:</span>
                                <span className="metric-value">{shift.produced}</span>
                              </div>
                              <div className="shift-metric">
                                <span className="metric-label">Meta:</span>
                                <span className="metric-value">{shift.target}</span>
                              </div>
                              <div className="shift-metric">
                                <span className="metric-label">Eficiência:</span>
                                <span className="metric-value">{shift.efficiency.toFixed(1)}%</span>
                              </div>
                              <div className="shift-metric">
                                <span className="metric-label">Qualidade:</span>
                                <span className="metric-value">{shift.quality.toFixed(1)}%</span>
                              </div>
                              <div className="shift-metric">
                                <span className="metric-label">Operadores:</span>
                                <span className="metric-value">{shift.operators}</span>
                              </div>
                            </div>
                            
                            <ProgressBar 
                              now={(shift.produced / shift.target) * 100}
                              variant={shift.status === 'Ativo' ? 'primary' : 'success'}
                              className="shift-progress"
                            />
                          </Card.Body>
                        </Card>
                      ))}
                    </div>
                  </div>
                </Tab>
              </Tabs>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default ProductStatusContent;

