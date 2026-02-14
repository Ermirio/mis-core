/**
 * HistoricoDataContent.js - Componente para visualização de dados históricos
 * 
 * Integra com o serviço OPC e InfluxDB para mostrar dados históricos
 * com controles de play/pause, zoom temporal e análise de tendências.
 * 
 * @author Process Engineer
 * @version 1.0.0 - Integração InfluxDB
 */

import React, { useState, useEffect, useRef } from 'react';
import { Card, Button, Form, Alert, Badge, ButtonGroup, Spinner } from 'react-bootstrap';
import { 
  FaPlay, FaPause, FaStop, FaChartLine, FaDownload, FaSync,
  FaClock, FaCalendarAlt, FaFilter, FaExpand, FaCompress
} from 'react-icons/fa';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, 
  ResponsiveContainer, AreaChart, Area, BarChart, Bar
} from 'recharts';
import './HistoricoDataContent.css';

const HistoricoDataContent = ({ selectedLine }) => {
  // Estados do componente
  const [dadosHistoricos, setDadosHistoricos] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('');
  
  // Configurações de tempo
  const [periodoSelecionado, setPeriodoSelecionado] = useState('-1h');
  const [variavelSelecionada, setVariavelSelecionada] = useState('');
  const [tipoGrafico, setTipoGrafico] = useState('line');
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState(30); // segundos
  
  // Estados de controle
  const [kpisTempoReal, setKpisTempoReal] = useState({});
  const [variaveisDisponiveis, setVariaveisDisponiveis] = useState([]);
  const [statusConexao, setStatusConexao] = useState('offline');
  const [fullScreen, setFullScreen] = useState(false);
  
  // Refs
  const intervalRef = useRef(null);
  const chartContainerRef = useRef(null);

  // Opções de período
  const opcoesPeriodo = [
    { value: '-15m', label: 'Últimos 15 min' },
    { value: '-1h', label: 'Última hora' },
    { value: '-4h', label: 'Últimas 4 horas' },
    { value: '-12h', label: 'Últimas 12 horas' },
    { value: '-1d', label: 'Último dia' },
    { value: '-7d', label: 'Última semana' }
  ];

  // Variáveis disponíveis para seleção
  const variaveisOpcoes = [
    { value: '', label: 'Todas as variáveis' },
    { value: 'OEE', label: 'OEE (%)' },
    { value: 'Eficiencia', label: 'Eficiência (%)' },
    { value: 'Disponibilidade', label: 'Disponibilidade (%)' },
    { value: 'Performance', label: 'Performance (%)' },
    { value: 'Qualidade', label: 'Qualidade (%)' },
    { value: 'Temperatura', label: 'Temperatura (°C)' },
    { value: 'Pressao', label: 'Pressão (bar)' },
    { value: 'Velocidade', label: 'Velocidade (ppm)' },
    { value: 'Producao_Atual', label: 'Produção Atual' }
  ];

  // Carregar dados quando linha ou configurações mudam
  useEffect(() => {
    if (selectedLine) {
      carregarDadosHistoricos();
      carregarKpisTempoReal();
      verificarStatusConexao();
    }
  }, [selectedLine, periodoSelecionado, variavelSelecionada]);

  // Controle de auto-refresh
  useEffect(() => {
    if (autoRefresh && selectedLine) {
      intervalRef.current = setInterval(() => {
        carregarDadosHistoricos();
        carregarKpisTempoReal();
      }, refreshInterval * 1000);
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [autoRefresh, refreshInterval, selectedLine]);

  const verificarStatusConexao = async () => {
    try {
      const response = await fetch('/api/opc/status/');
      if (response.ok) {
        setStatusConexao('online');
      } else {
        setStatusConexao('offline');
      }
    } catch (error) {
      setStatusConexao('offline');
    }
  };

  const carregarDadosHistoricos = async () => {
    try {
      setIsLoading(true);
      setMessage('');

      const params = new URLSearchParams({
        start: periodoSelecionado,
        end: 'now()'
      });

      if (variavelSelecionada) {
        params.append('variavel', variavelSelecionada);
      }

      const response = await fetch(`/api/opc/dados-historicos/${selectedLine}/?${params}`);
      
      if (response.ok) {
        const data = await response.json();
        
        // Processar dados para o gráfico
        const dadosProcessados = processarDadosParaGrafico(data.dados);
        setDadosHistoricos(dadosProcessados);
        
        // Extrair variáveis disponíveis
        const variaveis = [...new Set(data.dados.map(d => d.variavel))];
        setVariaveisDisponiveis(variaveis);
        
        setMessage(`Carregados ${data.total_pontos} pontos de dados`);
        setMessageType('success');
      } else {
        const errorData = await response.json();
        setMessage(`Erro ao carregar dados: ${errorData.erro}`);
        setMessageType('danger');
      }
    } catch (error) {
      console.error('Erro ao carregar dados históricos:', error);
      setMessage('Erro de conexão ao carregar dados históricos');
      setMessageType('danger');
    } finally {
      setIsLoading(false);
    }
  };

  const carregarKpisTempoReal = async () => {
    try {
      const response = await fetch(`/api/opc/kpis-tempo-real/${selectedLine}/`);
      
      if (response.ok) {
        const data = await response.json();
        setKpisTempoReal(data.kpis);
      }
    } catch (error) {
      console.error('Erro ao carregar KPIs:', error);
    }
  };

  const processarDadosParaGrafico = (dados) => {
    // Agrupar dados por timestamp
    const dadosAgrupados = {};
    
    dados.forEach(ponto => {
      const timestamp = new Date(ponto.timestamp).getTime();
      const timeKey = Math.floor(timestamp / (60 * 1000)) * 60 * 1000; // Agrupar por minuto
      
      if (!dadosAgrupados[timeKey]) {
        dadosAgrupados[timeKey] = {
          timestamp: timeKey,
          time: new Date(timeKey).toLocaleTimeString('pt-BR', { 
            hour: '2-digit', 
            minute: '2-digit' 
          })
        };
      }
      
      // Adicionar valor da variável
      const nomeVariavel = ponto.variavel;
      dadosAgrupados[timeKey][nomeVariavel] = ponto.valor;
    });
    
    // Converter para array e ordenar por timestamp
    return Object.values(dadosAgrupados).sort((a, b) => a.timestamp - b.timestamp);
  };

  const togglePlayPause = () => {
    setIsPlaying(!isPlaying);
    setAutoRefresh(!autoRefresh);
  };

  const stopRefresh = () => {
    setIsPlaying(false);
    setAutoRefresh(false);
  };

  const exportarDados = () => {
    const csvContent = "data:text/csv;charset=utf-8," 
      + "Timestamp,Variavel,Valor,Equipamento\n"
      + dadosHistoricos.map(row => 
          Object.keys(row)
            .filter(key => key !== 'timestamp' && key !== 'time')
            .map(variavel => `${row.time},${variavel},${row[variavel]},${selectedLine}`)
            .join('\n')
        ).join('\n');

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `historico_${selectedLine}_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const toggleFullScreen = () => {
    setFullScreen(!fullScreen);
    if (!fullScreen) {
      if (chartContainerRef.current?.requestFullscreen) {
        chartContainerRef.current.requestFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
  };

  const renderGrafico = () => {
    if (dadosHistoricos.length === 0) {
      return (
        <div className="text-center p-4">
          <Alert variant="info">
            Nenhum dado disponível para o período selecionado
          </Alert>
        </div>
      );
    }

    const cores = [
      '#8884d8', '#82ca9d', '#ffc658', '#ff7300', '#00ff00', 
      '#ff0000', '#0000ff', '#ffff00', '#ff00ff', '#00ffff'
    ];

    const variaveisParaExibir = variavelSelecionada 
      ? [variavelSelecionada] 
      : variaveisDisponiveis.slice(0, 5); // Limitar a 5 variáveis

    switch (tipoGrafico) {
      case 'area':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <AreaChart data={dadosHistoricos}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Legend />
              {variaveisParaExibir.map((variavel, index) => (
                <Area
                  key={variavel}
                  type="monotone"
                  dataKey={variavel}
                  stackId="1"
                  stroke={cores[index % cores.length]}
                  fill={cores[index % cores.length]}
                  fillOpacity={0.6}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        );

      case 'bar':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={dadosHistoricos.slice(-20)}> {/* Últimos 20 pontos */}
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Legend />
              {variaveisParaExibir.map((variavel, index) => (
                <Bar
                  key={variavel}
                  dataKey={variavel}
                  fill={cores[index % cores.length]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        );

      default: // line
        return (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={dadosHistoricos}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Legend />
              {variaveisParaExibir.map((variavel, index) => (
                <Line
                  key={variavel}
                  type="monotone"
                  dataKey={variavel}
                  stroke={cores[index % cores.length]}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        );
    }
  };

  return (
    <div className={`historico-data-content ${fullScreen ? 'fullscreen' : ''}`}>
      <Card>
        <Card.Header className="d-flex justify-content-between align-items-center">
          <h5 className="mb-0">
            <FaChartLine className="me-2" />
            Dados Históricos - {selectedLine}
          </h5>
          <div className="d-flex align-items-center gap-2">
            <Badge bg={statusConexao === 'online' ? 'success' : 'danger'}>
              {statusConexao === 'online' ? 'Online' : 'Offline'}
            </Badge>
            {Object.keys(kpisTempoReal).length > 0 && (
              <Badge bg="info">
                OEE: {kpisTempoReal.OEE?.valor || 'N/A'}%
              </Badge>
            )}
          </div>
        </Card.Header>

        <Card.Body>
          {message && (
            <Alert variant={messageType} className="mb-3">
              {message}
            </Alert>
          )}

          {/* Controles */}
          <div className="row mb-4">
            <div className="col-md-3">
              <Form.Group>
                <Form.Label>Período</Form.Label>
                <Form.Select
                  value={periodoSelecionado}
                  onChange={(e) => setPeriodoSelecionado(e.target.value)}
                >
                  {opcoesPeriodo.map(opcao => (
                    <option key={opcao.value} value={opcao.value}>
                      {opcao.label}
                    </option>
                  ))}
                </Form.Select>
              </Form.Group>
            </div>

            <div className="col-md-3">
              <Form.Group>
                <Form.Label>Variável</Form.Label>
                <Form.Select
                  value={variavelSelecionada}
                  onChange={(e) => setVariavelSelecionada(e.target.value)}
                >
                  {variaveisOpcoes.map(opcao => (
                    <option key={opcao.value} value={opcao.value}>
                      {opcao.label}
                    </option>
                  ))}
                </Form.Select>
              </Form.Group>
            </div>

            <div className="col-md-2">
              <Form.Group>
                <Form.Label>Tipo de Gráfico</Form.Label>
                <Form.Select
                  value={tipoGrafico}
                  onChange={(e) => setTipoGrafico(e.target.value)}
                >
                  <option value="line">Linha</option>
                  <option value="area">Área</option>
                  <option value="bar">Barras</option>
                </Form.Select>
              </Form.Group>
            </div>

            <div className="col-md-4">
              <Form.Label>Controles</Form.Label>
              <div className="d-flex gap-2">
                <ButtonGroup>
                  <Button
                    variant={isPlaying ? "success" : "outline-success"}
                    onClick={togglePlayPause}
                    disabled={isLoading}
                  >
                    {isPlaying ? <FaPause /> : <FaPlay />}
                  </Button>
                  <Button
                    variant="outline-danger"
                    onClick={stopRefresh}
                    disabled={!isPlaying}
                  >
                    <FaStop />
                  </Button>
                </ButtonGroup>

                <Button
                  variant="outline-primary"
                  onClick={carregarDadosHistoricos}
                  disabled={isLoading}
                >
                  {isLoading ? <Spinner size="sm" /> : <FaSync />}
                </Button>

                <Button
                  variant="outline-info"
                  onClick={exportarDados}
                  disabled={dadosHistoricos.length === 0}
                >
                  <FaDownload />
                </Button>

                <Button
                  variant="outline-secondary"
                  onClick={toggleFullScreen}
                >
                  {fullScreen ? <FaCompress /> : <FaExpand />}
                </Button>
              </div>
            </div>
          </div>

          {/* Auto-refresh settings */}
          {isPlaying && (
            <div className="row mb-3">
              <div className="col-md-6">
                <Form.Group>
                  <Form.Label>
                    <FaClock className="me-1" />
                    Intervalo de Atualização: {refreshInterval}s
                  </Form.Label>
                  <Form.Range
                    min="5"
                    max="300"
                    step="5"
                    value={refreshInterval}
                    onChange={(e) => setRefreshInterval(parseInt(e.target.value))}
                  />
                </Form.Group>
              </div>
            </div>
          )}

          {/* Gráfico */}
          <div ref={chartContainerRef} className="chart-container">
            {renderGrafico()}
          </div>

          {/* KPIs em tempo real */}
          {Object.keys(kpisTempoReal).length > 0 && (
            <div className="mt-4">
              <h6>KPIs em Tempo Real</h6>
              <div className="row">
                {Object.entries(kpisTempoReal).map(([kpi, dados]) => (
                  <div key={kpi} className="col-md-2 mb-2">
                    <Card className="text-center">
                      <Card.Body className="py-2">
                        <div className="h6 mb-0">{dados.valor}</div>
                        <small className="text-muted">{kpi}</small>
                      </Card.Body>
                    </Card>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Informações do dataset */}
          {dadosHistoricos.length > 0 && (
            <div className="mt-3">
              <small className="text-muted">
                <FaFilter className="me-1" />
                {dadosHistoricos.length} pontos de dados | 
                Variáveis: {variaveisDisponiveis.join(', ')} |
                Período: {opcoesPeriodo.find(p => p.value === periodoSelecionado)?.label}
              </small>
            </div>
          )}
        </Card.Body>
      </Card>
    </div>
  );
};

export default HistoricoDataContent;

