import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Activity,
  AlertCircle,
  CheckCircle,
  Clock,
  Filter,
  XCircle,
  ArrowLeft,
  Gauge,
  TrendingUp,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  Legend,
  ReferenceLine,
  BarChart,
  Bar,
  ComposedChart
} from 'recharts';
import { format, subHours } from 'date-fns';
import { DateRange } from "react-day-picker";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import StateTimelineChart from '@/components/StateTimelineChart';

// Configuração
const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || 'http://127.0.0.1:8000/api';
const FLASK_API_URL = import.meta.env.VITE_FLASK_API_URL || 'http://127.0.0.1:5000/api';

// ===== TIPOS =====

interface Equipamento {
  id: number;
  nome: string;
  codigo: string;
  tipo: string;
  tipo_display: string;
  status: string;
  status_display: string;
  linha: number;
  linha_nome: string;
  velocidade_nominal: number;
  temperatura_min?: number;
  temperatura_max?: number;
  pressao_min?: number;
  pressao_max?: number;
  meta_oee: number;
}

interface Metrica {
  id: number;
  data_hora: string;
  periodo: string;
  turno?: string;
  contagem_entrada: number;
  contagem_saida: number;
  descarte: number;
  percentual_descarte: number;
  velocidade_real: number;
  disponibilidade: number;
  performance: number;
  qualidade: number;
  oee: number;
  tempo_producao: number;
}

interface EventoEstado {
  id: number;
  estado: string;
  estado_display: string;
  inicio: string;
  fim?: string | null;
  duracao_segundos?: number;
  origem: string;
}

interface DadosTempoReal {
  status: string;
  timestamp: string;
  medicoes: {
    velocidade_atual: number;
    contagem_entrada: number;
    contagem_saida: number;
    descarte: number;
    percentual_descarte: number;
    temperatura: number;
    pressao: number;
    estado: string;
  };
}

interface TimelineData {
  time: string;
  velocidade: number;
  producao: number;
  descarte: number;
}

interface Turno {
  id: number;
  nome: string;
  codigo: string;
  hora_inicio: string;
  hora_fim: string;
  ativo: boolean;
}

const EquipamentoDetalhes: React.FC = () => {
  const { equipamentoId } = useParams<{ equipamentoId: string }>();
  const navigate = useNavigate();

  const [equipamento, setEquipamento] = useState<Equipamento | null>(null);
  const [dadosTempoReal, setDadosTempoReal] = useState<DadosTempoReal | null>(null);
  const [metricaAtual, setMetricaAtual] = useState<Metrica | null>(null);
  const [historico, setHistorico] = useState<Metrica[]>([]);
  const [eventos, setEventos] = useState<EventoEstado[]>([]);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [online, setOnline] = useState(false);
  const [timelineData, setTimelineData] = useState<Metrica[]>([]);
  const [timelineDate, setTimelineDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [loadingTimeline, setLoadingTimeline] = useState(false);
  const [debugInfo, setDebugInfo] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filtros
  const [periodo, setPeriodo] = useState<'HORA' | 'TURNO' | 'DIA'>('HORA'); // Mudado para HORA pois há dados
  const [turnoFiltro, setTurnoFiltro] = useState<string>("atual");
  const [diaFiltro, setDiaFiltro] = useState<string>(new Date().toISOString().split('T')[0]);

  const chartDateRange = useMemo(() => {
    if (!diaFiltro) return undefined;
    const from = new Date(`${diaFiltro}T00:00:00`);
    const to = new Date(`${diaFiltro}T23:59:59`);
    return { from, to };
  }, [diaFiltro]);

  // Combina histórico com ponto em tempo real e calcula velocidade baseada em produção
  const historicoComTempoReal = useMemo(() => {
    if (!historico || historico.length === 0) return [];

    // Adiciona velocidade calculada (baseada em produção) a cada ponto
    const historicoComCalculo = historico.map(ponto => ({
      ...ponto,
      // Velocidade Calculada = Saída / 60 minutos (assumindo período de 1 hora)
      velocidade_calculada: ponto.contagem_saida ? ponto.contagem_saida / 60 : 0,
    }));

    // Se não houver dados em tempo real, retorna histórico com cálculo
    if (!dadosTempoReal || !dadosTempoReal.medicoes) return historicoComCalculo;

    // Adiciona ponto atual se for do dia de hoje
    const hoje = new Date().toISOString().split('T')[0];
    if (diaFiltro === hoje) {
      const pontoAtual = {
        data_hora: new Date().toISOString(),
        velocidade_real: dadosTempoReal.medicoes.velocidade_atual || 0,
        velocidade_calculada: dadosTempoReal.medicoes.velocidade_atual || 0, // Tempo real usa sensor
        velocidade_planejada: equipamento?.velocidade_nominal || 100,
        contagem_entrada: dadosTempoReal.medicoes.contagem_entrada || 0,
        contagem_saida: dadosTempoReal.medicoes.contagem_saida || 0,
      };
      return [...historicoComCalculo, pontoAtual];
    }

    return historicoComCalculo;
  }, [historico, dadosTempoReal, diaFiltro, equipamento]);
  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: subHours(new Date(), 24 * 7), // 7 dias atrás
    to: new Date(),
  });

  // Timeline navigation state
  const [timelineWindow, setTimelineWindow] = useState(0);
  const timelineWindowSize = 24 * 60 * 60 * 1000;

  // Pagination for events
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Busca dados do equipamento
  useEffect(() => {
    const fetchEquipamento = async () => {
      setLoading(true);
      setError(null);
      setEquipamento(null);

      try {
        const response = await fetch(`${DJANGO_API_URL}/equipamentos/${equipamentoId}/`);
        if (!response.ok) throw new Error('Falha ao buscar dados do equipamento');
        const data = await response.json();
        setEquipamento(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Erro desconhecido');
      } finally {
        setLoading(false);
      }
    };

    if (equipamentoId) {
      fetchEquipamento();
    }
  }, [equipamentoId, DJANGO_API_URL]);

  // Busca turnos disponíveis
  useEffect(() => {
    const fetchTurnos = async () => {
      try {
        const url = `${DJANGO_API_URL}/turnos/?ativo=true`;
        console.log('🔍 [TURNOS] Fetching URL:', url);
        const response = await fetch(url);
        console.log('🔍 [TURNOS] Status:', response.status);

        if (!response.ok) throw new Error('Falha ao buscar turnos');
        const data = await response.json();
        const turnos = Array.isArray(data) ? data : data.results || [];
        setTurnos(turnos);
      } catch (err) {
        console.error('Erro ao buscar turnos:', err);
      }
    };

    fetchTurnos();
  }, [DJANGO_API_URL]);

  // Busca dados em tempo real
  useEffect(() => {
    if (!equipamento) return;

    const fetchDadosTempoReal = async () => {
      try {
        const response = await fetch(`${FLASK_API_URL}/realtime/status/${equipamento.codigo}`);
        if (response.ok) {
          const data = await response.json();
          setDadosTempoReal(data);

          const agora = new Date().getTime();
          const timestampLeitura = new Date(data.timestamp).getTime();
          const diferencaSegundos = (agora - timestampLeitura) / 1000;
          setOnline(diferencaSegundos <= 10);
        }
      } catch (err) {
        console.error('Erro ao buscar dados em tempo real:', err);
        setOnline(false);
      }
    };

    fetchDadosTempoReal();
    const interval = setInterval(fetchDadosTempoReal, 1000);
    return () => clearInterval(interval);
  }, [equipamento, FLASK_API_URL]);

  // Busca métrica atual - HORA para turno atual, TURNO para turnos específicos
  useEffect(() => {
    const fetchMetricaAtual = async () => {
      try {
        if (!equipamentoId) return;

        // Determina período baseado no filtro de turno
        const periodo = turnoFiltro === 'atual' ? 'HORA' : 'TURNO';

        const params = new URLSearchParams({
          equipamento_id: equipamentoId,
          periodo: periodo,
        });

        // Adiciona filtros de data
        params.append('data_inicio', `${diaFiltro}T00:00:00Z`);
        params.append('data_fim', `${diaFiltro}T23:59:59Z`);

        // Se turno específico, adiciona nome do turno
        if (turnoFiltro !== 'atual') {
          const turnoSelecionado = turnos.find(t => t.id.toString() === turnoFiltro);
          if (turnoSelecionado) {
            params.append('turno', turnoSelecionado.nome);
          }
        }

        const url = `${DJANGO_API_URL}/metricas_equipamento_consolidadas/?${params.toString()}`;

        console.log('🔍 [METRICA] Fetching:', url);
        console.log('📊 [METRICA] Filters:', { diaFiltro, turnoFiltro });

        const response = await fetch(url);
        if (!response.ok) throw new Error('Falha ao buscar métrica atual');
        const data = await response.json();

        console.log('✅ [METRICA] Response:', data);
        setDebugInfo(`Métrica: ${data.metricas?.length || 0} resultados`);

        if (data.metricas && data.metricas.length > 0) {
          setMetricaAtual(data.metricas[0]);
        } else {
          setMetricaAtual(null);
        }
      } catch (err) {
        console.error('❌ [METRICA] Erro:', err);
        setDebugInfo(`Erro ao buscar métrica: ${err}`);
      }
    };

    if (equipamentoId) {
      fetchMetricaAtual();
      const interval = setInterval(fetchMetricaAtual, 10000);
      return () => clearInterval(interval);
    }
  }, [equipamentoId, turnoFiltro, diaFiltro, DJANGO_API_URL]);

  // Busca histórico de métricas - sempre HORA para mostrar detalhamento
  useEffect(() => {
    const fetchHistorico = async () => {
      try {
        if (!equipamentoId) return;

        const params = new URLSearchParams({
          equipamento_id: equipamentoId,
          periodo: 'HORA', // Sempre HORA para tabela detalhada
        });

        // Adiciona filtro de data
        params.append('data_inicio', `${diaFiltro}T00:00:00Z`);
        params.append('data_fim', `${diaFiltro}T23:59:59Z`);

        // Se turno específico, filtra por turno
        if (turnoFiltro !== 'atual') {
          const turnoSelecionado = turnos.find(t => t.id.toString() === turnoFiltro);
          if (turnoSelecionado) {
            params.append('turno', turnoSelecionado.nome);
          }
        }

        const url = `${DJANGO_API_URL}/metricas_equipamento_consolidadas/?${params.toString()}`;

        const response = await fetch(url);
        if (!response.ok) throw new Error('Falha ao buscar histórico');
        const data = await response.json();

        setHistorico(data.metricas || []);
      } catch (err) {
        console.error('Erro ao buscar histórico:', err);
      }
    };

    if (equipamentoId) {
      fetchHistorico();
    }
  }, [equipamentoId, diaFiltro, DJANGO_API_URL]);

  // Busca eventos de estado
  useEffect(() => {
    const fetchEventos = async () => {
      try {
        if (!equipamentoId) return;

        const params = new URLSearchParams({
          equipamento_id: equipamentoId,
          ordering: '-inicio',
          limit: '100',
        });

        // Usa diaFiltro para filtrar eventos
        if (diaFiltro) {
          params.append('data_inicio', `${diaFiltro}T00:00:00Z`);
          params.append('data_fim', `${diaFiltro}T23:59:59Z`);
        }

        const url = `${DJANGO_API_URL}/eventos-estado/?${params.toString()}`;

        const response = await fetch(url);
        if (!response.ok) throw new Error('Falha ao buscar eventos');
        const data = await response.json();

        setEventos(Array.isArray(data) ? data : data.results || []);
      } catch (err) {
        console.error('Erro ao buscar eventos:', err);
      }
    };

    if (equipamentoId) {
      fetchEventos();
      const interval = setInterval(fetchEventos, 30000); // Atualiza a cada 30s
      return () => clearInterval(interval);
    }
  }, [equipamentoId, diaFiltro, DJANGO_API_URL]);

  // Busca métricas HORA para Timeline
  useEffect(() => {
    const fetchTimelineData = async () => {
      try {
        if (!equipamentoId) return;

        setLoadingTimeline(true);

        const params = new URLSearchParams({
          equipamento_id: equipamentoId,
          periodo: 'HORA',
        });

        // Adiciona filtro de data para Timeline
        params.append('data_inicio', `${timelineDate}T00:00:00Z`);
        params.append('data_fim', `${timelineDate}T23:59:59Z`);

        const url = `${DJANGO_API_URL}/metricas_equipamento_consolidadas/?${params.toString()}`;

        const response = await fetch(url);
        if (!response.ok) throw new Error('Falha ao buscar dados da timeline');
        const data = await response.json();

        // Ordenar por data_hora
        const metricas = (data.metricas || []).sort((a: Metrica, b: Metrica) =>
          new Date(a.data_hora).getTime() - new Date(b.data_hora).getTime()
        );

        setTimelineData(metricas);
      } catch (err) {
        console.error('Erro ao buscar dados da timeline:', err);
        setTimelineData([]);
      } finally {
        setLoadingTimeline(false);
      }
    };

    if (equipamentoId) {
      fetchTimelineData();
    }
  }, [equipamentoId, timelineDate, DJANGO_API_URL]);

  // Funções auxiliares
  const getOEEColor = (oee: number): string => {
    if (oee >= 85) return 'bg-green-500';
    if (oee >= 70) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getOEETextColor = (oee: number): string => {
    if (oee >= 85) return 'text-green-600';
    if (oee >= 70) return 'text-yellow-600';
    return 'text-red-600';
  };

  const formatarTempo = (minutos: number): string => {
    const horas = Math.floor(minutos / 60);
    const mins = Math.floor(minutos % 60);
    return `${horas}h ${mins}m`;
  };

  const paginatedEventos = eventos.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );
  const totalPages = Math.ceil(eventos.length / itemsPerPage);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Carregando dados do equipamento...</p>
        </div>
      </div>
    );
  }

  if (error || !equipamento) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-600 mx-auto mb-4" />
          <p className="text-red-600 mb-4">{error || 'Equipamento não encontrado'}</p>
          <Button onClick={() => navigate(-1)}>Voltar</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-4 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate(-1)}
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{equipamento.nome}</h1>
            <p className="text-sm text-gray-500">{equipamento.codigo} • {equipamento.linha_nome}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={online ? 'default' : 'secondary'}>
            {online ? '🟢 Online' : '🔴 Offline'}
          </Badge>
          <Badge variant={equipamento.status === 'ATIVO' ? 'default' : 'secondary'}>
            {equipamento.status}
          </Badge>
        </div>
      </div>

      {/* Filtros Simplificados: Apenas Data + Turno */}
      <div className="bg-white border-b border-gray-200 p-4 flex gap-4 items-end flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-sm font-medium text-gray-700 mb-2">Data</label>
          <input
            type="date"
            value={diaFiltro}
            onChange={(e) => setDiaFiltro(e.target.value)}
            max={new Date().toISOString().split('T')[0]}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex-1 min-w-[250px]">
          <label className="block text-sm font-medium text-gray-700 mb-2">Turno</label>
          <Select value={turnoFiltro} onValueChange={setTurnoFiltro}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="atual">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                  Turno Atual (Tempo Real)
                </div>
              </SelectItem>
              {turnos.map(turno => (
                <SelectItem key={turno.id} value={String(turno.id)}>
                  {turno.nome} ({turno.hora_inicio.slice(0, 5)} - {turno.hora_fim.slice(0, 5)})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Conteúdo Principal */}
      <div className="p-4">
        <Tabs defaultValue="timeline-velocidade" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="timeline-velocidade">Timeline de Velocidade</TabsTrigger>
            <TabsTrigger value="historico-turnos">Histórico de Turnos</TabsTrigger>
            <TabsTrigger value="timeline-estados">Timeline de Estados</TabsTrigger>
            <TabsTrigger value="eventos-estado">Eventos de Estado</TabsTrigger>
          </TabsList>

          {/* ABA: TIMELINE DE VELOCIDADE */}
          <TabsContent value="timeline-velocidade" className="space-y-4">
            {/* Dados em Tempo Real */}
            {dadosTempoReal && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Gauge className="w-5 h-5" />
                    Dados em Tempo Real
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <div>
                      <p className="text-sm text-gray-500">Velocidade</p>
                      <p className="text-2xl font-bold">{(dadosTempoReal.medicoes.velocidade_atual ?? 0).toFixed(2)}</p>
                      <p className="text-xs text-gray-500">un/min</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Temperatura</p>
                      <p className="text-2xl font-bold">{(dadosTempoReal.medicoes.temperatura ?? 0).toFixed(1)}</p>
                      <p className="text-xs text-gray-500">°C</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Pressão</p>
                      <p className="text-2xl font-bold">{(dadosTempoReal.medicoes.pressao ?? 0).toFixed(2)}</p>
                      <p className="text-xs text-gray-500">bar</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Gráfico de Velocidade */}
            {historico.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Timeline de Velocidade</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={historicoComTempoReal}>
                        <defs>
                          <linearGradient id="colorVelocidade" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                          dataKey="data_hora"
                          tickFormatter={(value) => format(new Date(value), 'HH:mm')}
                        />
                        <YAxis />
                        <Tooltip
                          labelFormatter={(value) => format(new Date(value), 'dd/MM HH:mm')}
                        />
                        <Legend />
                        <Area
                          type="monotone"
                          dataKey="velocidade_real"
                          stroke="#3b82f6"
                          fillOpacity={1}
                          fill="url(#colorVelocidade)"
                          name="Velocidade Real (Sensor)"
                        />
                        <Line
                          type="monotone"
                          dataKey="velocidade_calculada"
                          stroke="#10b981"
                          strokeWidth={2}
                          dot={{ r: 3 }}
                          name="Velocidade Calculada (Produção)"
                        />
                        <Line
                          type="monotone"
                          dataKey="velocidade_planejada"
                          stroke="#22c55e"
                          strokeWidth={2}
                          strokeDasharray="5 5"
                          dot={false}
                          name="Velocidade Nominal"
                          data={historico.map(h => ({ ...h, velocidade_planejada: equipamento?.velocidade_nominal }))}
                        />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* ABA: HISTÓRICO DE TURNOS */}
          <TabsContent value="historico-turnos" className="space-y-4">
            {/* Métrica Atual */}
            {metricaAtual && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Activity className="w-5 h-5" />
                    Métrica Atual ({periodo})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <p className="text-sm text-gray-500">Entrada</p>
                      <p className="text-2xl font-bold">{metricaAtual.contagem_entrada}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Saída</p>
                      <p className="text-2xl font-bold">{metricaAtual.contagem_saida}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Velocidade Real</p>
                      <p className="text-lg font-semibold">{(metricaAtual.velocidade_real ?? 0).toFixed(2)} un/min</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Descarte</p>
                      <p className="text-lg font-semibold text-red-600">{(metricaAtual.percentual_descarte ?? 0).toFixed(2)}%</p>
                    </div>
                  </div>
                  <div className={`mt-4 p-3 rounded-lg ${getOEEColor(metricaAtual.oee || 0)}`}>
                    <p className="text-sm text-white font-medium">OEE</p>
                    <p className={`text-3xl font-bold ${getOEETextColor(metricaAtual.oee || 0)}`}>
                      {(metricaAtual.oee || 0).toFixed(1)}%
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Dados em Tempo Real */}
            {dadosTempoReal && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Gauge className="w-5 h-5" />
                    Dados em Tempo Real
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <div>
                      <p className="text-sm text-gray-500">Velocidade</p>
                      <p className="text-2xl font-bold">{(dadosTempoReal.medicoes.velocidade_atual ?? 0).toFixed(2)}</p>
                      <p className="text-xs text-gray-500">un/min</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Temperatura</p>
                      <p className="text-2xl font-bold">{(dadosTempoReal.medicoes.temperatura ?? 0).toFixed(1)}</p>
                      <p className="text-xs text-gray-500">°C</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Pressão</p>
                      <p className="text-2xl font-bold">{(dadosTempoReal.medicoes.pressao ?? 0).toFixed(2)}</p>
                      <p className="text-xs text-gray-500">bar</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Histórico de Métricas */}
            {historico.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Clock className="w-5 h-5" />
                    Histórico de Métricas (Últimas 24h)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-2 px-2">Data/Hora</th>
                          <th className="text-right py-2 px-2">Entrada</th>
                          <th className="text-right py-2 px-2">Saída</th>
                          <th className="text-right py-2 px-2">Vel. Real</th>
                          <th className="text-right py-2 px-2">Descarte</th>
                          <th className="text-right py-2 px-2">OEE</th>
                        </tr>
                      </thead>
                      <tbody>
                        {historico.map(metrica => (
                          <tr key={metrica.id} className="border-b hover:bg-gray-50">
                            <td className="py-2 px-2">{new Date(metrica.data_hora).toLocaleString('pt-BR')}</td>
                            <td className="text-right py-2 px-2">{metrica.contagem_entrada}</td>
                            <td className="text-right py-2 px-2">{metrica.contagem_saida}</td>
                            <td className="text-right py-2 px-2">{(metrica.velocidade_real ?? 0).toFixed(2)}</td>
                            <td className="text-right py-2 px-2 text-red-600">{(metrica.percentual_descarte ?? 0).toFixed(2)}%</td>
                            <td className={`text-right py-2 px-2 font-semibold ${getOEETextColor(metrica.oee || 0)}`}>
                              {(metrica.oee || 0).toFixed(1)}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* ABA: ESTADOS */}
          {/* ABA: TIMELINE DE ESTADOS */}
          <TabsContent value="timeline-estados" className="space-y-4">
            {/* Timeline de Estados */}
            <Card>
              <CardHeader>
                <CardTitle>Timeline de Estados</CardTitle>
              </CardHeader>
              <CardContent>
                <StateTimelineChart eventos={eventos} dateRange={chartDateRange} />
              </CardContent>
            </Card>
          </TabsContent>

          {/* ABA: EVENTOS DE ESTADO */}
          <TabsContent value="eventos-estado" className="space-y-4">
            {/* Eventos de Estado */}
            {eventos.length > 0 ? (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <AlertCircle className="w-5 h-5" />
                    Eventos de Estado
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {paginatedEventos.map(evento => (
                      <div key={evento.id} className="p-3 border border-gray-200 rounded-lg">
                        <div className="flex justify-between items-start">
                          <div>
                            <p className="font-semibold">{evento.estado_display}</p>
                            <p className="text-xs text-gray-500">
                              {new Date(evento.inicio).toLocaleString('pt-BR')}
                            </p>
                          </div>
                          <Badge variant="outline">{evento.origem}</Badge>
                        </div>
                        {evento.duracao_segundos && (
                          <p className="text-sm text-gray-600 mt-2">
                            Duração: {Math.floor(evento.duracao_segundos / 60)}m {evento.duracao_segundos % 60}s
                          </p>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Paginação */}
                  {totalPages > 1 && (
                    <div className="flex justify-center gap-2 mt-4">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                        disabled={currentPage === 1}
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </Button>
                      <span className="text-sm text-gray-600">
                        Página {currentPage} de {totalPages}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                        disabled={currentPage === totalPages}
                      >
                        <ChevronRight className="w-4 h-4" />
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardContent className="p-8 text-center text-gray-500">
                  Nenhum evento registrado para esta data.
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* ABA: TIMELINE */}
          <TabsContent value="timeline" className="space-y-4">
            {/* Filtro de Data para Timeline */}
            <Card>
              <CardHeader>
                <CardTitle>Filtros da Timeline</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <label htmlFor="timeline-date" className="text-sm font-medium">
                      Data:
                    </label>
                    <input
                      id="timeline-date"
                      type="date"
                      value={timelineDate}
                      onChange={(e) => setTimelineDate(e.target.value)}
                      className="px-3 py-2 border border-gray-300 rounded-md dark:border-gray-600 dark:bg-gray-800"
                    />
                  </div>
                  {loadingTimeline && (
                    <div className="text-sm text-gray-500">Carregando...</div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Gráfico de Velocidade */}
            {timelineData.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Velocidade ao Longo do Tempo</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={timelineData}>
                        <defs>
                          <linearGradient id="colorVelocidadeTimeline" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                          dataKey="data_hora"
                          tickFormatter={(value) => format(new Date(value), 'HH:mm')}
                          angle={-45}
                          textAnchor="end"
                          height={80}
                        />
                        <YAxis
                          label={{ value: 'Velocidade (un/min)', angle: -90, position: 'insideLeft' }}
                        />
                        <Tooltip
                          labelFormatter={(value) => format(new Date(value), 'dd/MM/yyyy HH:mm')}
                          formatter={(value: number) => [`${value.toFixed(2)} un/min`, 'Velocidade Real']}
                        />
                        <Legend />
                        <Area
                          type="monotone"
                          dataKey="velocidade_real"
                          stroke="#3b82f6"
                          fillOpacity={1}
                          fill="url(#colorVelocidadeTimeline)"
                          name="Velocidade Real"
                        />
                        <Line
                          type="monotone"
                          dataKey="velocidade_nominal"
                          stroke="#10b981"
                          strokeDasharray="5 5"
                          dot={false}
                          name="Velocidade Planejada"
                          data={timelineData.map(h => ({ ...h, velocidade_nominal: equipamento?.velocidade_nominal }))}
                        />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Gráfico de Produção */}
            {timelineData.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Produção ao Longo do Tempo</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={timelineData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                          dataKey="data_hora"
                          tickFormatter={(value) => format(new Date(value), 'HH:mm')}
                          angle={-45}
                          textAnchor="end"
                          height={80}
                        />
                        <YAxis
                          label={{ value: 'Unidades', angle: -90, position: 'insideLeft' }}
                        />
                        <Tooltip
                          labelFormatter={(value) => format(new Date(value), 'dd/MM/yyyy HH:mm')}
                          formatter={(value: number, name: string) => {
                            const labels: { [key: string]: string } = {
                              'contagem_entrada': 'Entrada',
                              'contagem_saida': 'Saída (Boas)',
                              'descarte': 'Descarte'
                            };
                            return [`${value} unidades`, labels[name] || name];
                          }}
                        />
                        <Legend />
                        <Area
                          type="monotone"
                          dataKey="contagem_entrada"
                          stackId="1"
                          stroke="#8b5cf6"
                          fill="#8b5cf6"
                          name="Entrada"
                          fillOpacity={0.6}
                        />
                        <Area
                          type="monotone"
                          dataKey="contagem_saida"
                          stackId="1"
                          stroke="#10b981"
                          fill="#10b981"
                          name="Saída (Boas)"
                          fillOpacity={0.6}
                        />
                        <Area
                          type="monotone"
                          dataKey="descarte"
                          stackId="1"
                          stroke="#ef4444"
                          fill="#ef4444"
                          name="Descarte"
                          fillOpacity={0.6}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Gráfico de Descarte */}
            {timelineData.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Descarte e Percentual ao Longo do Tempo</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={timelineData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                          dataKey="data_hora"
                          tickFormatter={(value) => format(new Date(value), 'HH:mm')}
                          angle={-45}
                          textAnchor="end"
                          height={80}
                        />
                        <YAxis
                          yAxisId="left"
                          label={{ value: 'Descarte (unidades)', angle: -90, position: 'insideLeft' }}
                        />
                        <YAxis
                          yAxisId="right"
                          orientation="right"
                          label={{ value: 'Percentual (%)', angle: 90, position: 'insideRight' }}
                        />
                        <Tooltip
                          labelFormatter={(value) => format(new Date(value), 'dd/MM/yyyy HH:mm')}
                          formatter={(value: number, name: string) => {
                            if (name === 'descarte') {
                              return [`${value} unidades`, 'Descarte'];
                            }
                            return [`${value.toFixed(2)}%`, 'Percentual Descarte'];
                          }}
                        />
                        <Legend />
                        <Bar
                          yAxisId="left"
                          dataKey="descarte"
                          fill="#ef4444"
                          name="Descarte (unidades)"
                        />
                        <Line
                          yAxisId="right"
                          type="monotone"
                          dataKey="percentual_descarte"
                          stroke="#f59e0b"
                          name="% Descarte"
                          strokeWidth={2}
                          dot={{ r: 3 }}
                          activeDot={{ r: 5 }}
                        />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Resumo Estatístico */}
            {timelineData.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Resumo do Período</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-blue-600">
                        {timelineData.reduce((sum, m) => sum + (m.contagem_entrada || 0), 0).toLocaleString()}
                      </div>
                      <div className="text-sm text-gray-500">Total Entrada</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-600">
                        {timelineData.reduce((sum, m) => sum + (m.contagem_saida || 0), 0).toLocaleString()}
                      </div>
                      <div className="text-sm text-gray-500">Total Saída (Boas)</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-red-600">
                        {timelineData.reduce((sum, m) => sum + (m.descarte || 0), 0).toLocaleString()}
                      </div>
                      <div className="text-sm text-gray-500">Total Descarte</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-purple-600">
                        {timelineData.length > 0
                          ? (timelineData.reduce((sum, m) => sum + (m.velocidade_real || 0), 0) / timelineData.length).toFixed(2)
                          : '0.00'}
                      </div>
                      <div className="text-sm text-gray-500">Velocidade Média</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Mensagem quando não há dados */}
            {!loadingTimeline && timelineData.length === 0 && (
              <Card>
                <CardContent className="py-8">
                  <p className="text-gray-500 text-center">
                    Nenhum dado disponível para a data selecionada. Tente selecionar outra data.
                  </p>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default EquipamentoDetalhes;