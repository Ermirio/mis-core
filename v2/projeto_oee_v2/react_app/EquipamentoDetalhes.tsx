import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ArrowLeft, Activity, AlertCircle, CheckCircle, Clock, Gauge } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

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
  linha_codigo: string;
  velocidade_nominal: number;
  velocidade_maxima: number;
  meta_oee: number;
  temperatura_min?: number;
  temperatura_max?: number;
  pressao_min?: number;
  pressao_max?: number;
}

interface MetricaEquipamento {
  id: number;
  data_hora: string;
  periodo: string;
  contagem_entrada: number;
  contagem_saida: number;
  descarte: number;
  percentual_descarte: number;
  velocidade_planejada: number;
  velocidade_real: number;
  tempo_programado: number;
  tempo_disponivel: number;
  tempo_producao: number;
  tempo_parada: number;
  tempo_setup: number;
  tempo_nao_programado: number;
  disponibilidade: number;
  performance: number;
  qualidade: number;
  oee: number;
}

interface EventoEstado {
  id: number;
  equipamento: number;
  equipamento_nome: string;
  estado: string;
  estado_display: string;
  inicio: string;
  fim: string | null;
  duracao_segundos: number | null;
  origem: string;
  origem_display: string;
  observacao: string;
}

interface DadosTempoReal {
  equipamento: string;
  status: string;
  timestamp: string;
  medicoes: {
    contagem_entrada?: number;
    contagem_saida?: number;
    velocidade_atual?: number;
    estado?: number;
    temperatura?: number;
    pressao?: number;
    descarte?: number;
    percentual_descarte?: number;
  };
}

// ===== MAPEAMENTO DE ESTADOS =====

const ESTADOS_CONFIG = {
  RUN: { label: 'Produzindo', color: 'bg-green-500', textColor: 'text-green-700' },
  WAIT_PREV: { label: 'Aguardando Anterior', color: 'bg-yellow-500', textColor: 'text-yellow-700' },
  BLOCK_NEXT: { label: 'Bloqueado Próximo', color: 'bg-orange-500', textColor: 'text-orange-700' },
  FAULT: { label: 'Falha', color: 'bg-red-500', textColor: 'text-red-700' },
  SETUP: { label: 'Setup', color: 'bg-blue-500', textColor: 'text-blue-700' },
  TESTE_PROJ: { label: 'Teste', color: 'bg-purple-500', textColor: 'text-purple-700' },
  AGUARD_MNT: { label: 'Aguard. Manutenção', color: 'bg-pink-500', textColor: 'text-pink-700' },
  MANUTENCAO: { label: 'Manutenção', color: 'bg-gray-500', textColor: 'text-gray-700' },
  FALTA_MAT: { label: 'Falta Material', color: 'bg-amber-500', textColor: 'text-amber-700' },
  OUTRO: { label: 'Outro', color: 'bg-gray-400', textColor: 'text-gray-600' },
};

// ===== COMPONENTE PRINCIPAL =====

const EquipamentoDetalhes: React.FC = () => {
  const { equipamentoId } = useParams<{ equipamentoId: string }>();
  const navigate = useNavigate();

  const [equipamento, setEquipamento] = useState<Equipamento | null>(null);
  const [metricaAtual, setMetricaAtual] = useState<MetricaEquipamento | null>(null);
  const [historico, setHistorico] = useState<MetricaEquipamento[]>([]);
  const [eventos, setEventos] = useState<EventoEstado[]>([]);
  const [dadosTempoReal, setDadosTempoReal] = useState<DadosTempoReal | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || 'http://localhost:8000/api';
  const FLASK_API_URL = import.meta.env.VITE_FLASK_API_URL || 'http://localhost:5000/api';

  // Busca dados do equipamento
  useEffect(() => {
    const fetchEquipamento = async () => {
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

    fetchEquipamento();
  }, [equipamentoId, DJANGO_API_URL]);

  // Busca métrica atual
  useEffect(() => {
    const fetchMetricaAtual = async () => {
      try {
        const response = await fetch(
          `${DJANGO_API_URL}/metricas/?equipamento_id=${equipamentoId}&periodo=HORA&ordering=-data_hora&limit=1`
        );
        if (!response.ok) throw new Error('Falha ao buscar métrica atual');
        const data = await response.json();
        if (data.results && data.results.length > 0) {
          setMetricaAtual(data.results[0]);
        }
      } catch (err) {
        console.error('Erro ao buscar métrica atual:', err);
      }
    };

    if (equipamentoId) {
      fetchMetricaAtual();
      const interval = setInterval(fetchMetricaAtual, 30000);
      return () => clearInterval(interval);
    }
  }, [equipamentoId, DJANGO_API_URL]);

  // Busca histórico
  useEffect(() => {
    const fetchHistorico = async () => {
      try {
        const response = await fetch(
          `${DJANGO_API_URL}/metricas/?equipamento_id=${equipamentoId}&periodo=HORA&ordering=-data_hora&limit=24`
        );
        if (!response.ok) throw new Error('Falha ao buscar histórico');
        const data = await response.json();
        setHistorico(data.results || []);
      } catch (err) {
        console.error('Erro ao buscar histórico:', err);
      }
    };

    if (equipamentoId) {
      fetchHistorico();
    }
  }, [equipamentoId, DJANGO_API_URL]);

  // Busca eventos de estado
  useEffect(() => {
    const fetchEventos = async () => {
      try {
        const response = await fetch(
          `${DJANGO_API_URL}/eventos-estado/?equipamento_id=${equipamentoId}&ordering=-inicio&limit=50`
        );
        if (!response.ok) throw new Error('Falha ao buscar eventos');
        const data = await response.json();
        setEventos(data.results || []);
      } catch (err) {
        console.error('Erro ao buscar eventos:', err);
      }
    };

    if (equipamentoId) {
      fetchEventos();
      const interval = setInterval(fetchEventos, 10000);
      return () => clearInterval(interval);
    }
  }, [equipamentoId, DJANGO_API_URL]);

  // Busca dados em tempo real
  useEffect(() => {
    if (!equipamento) return;

    const fetchDadosTempoReal = async () => {
      try {
        const response = await fetch(`${FLASK_API_URL}/realtime/status/${equipamento.codigo}`);
        if (response.ok) {
          const data = await response.json();
          setDadosTempoReal(data);
        }
      } catch (err) {
        console.error('Erro ao buscar dados em tempo real:', err);
      }
    };

    fetchDadosTempoReal();
    const interval = setInterval(fetchDadosTempoReal, 3000);
    return () => clearInterval(interval);
  }, [equipamento, FLASK_API_URL]);

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

  const formatarDuracao = (segundos: number | null): string => {
    if (!segundos) return '-';
    const horas = Math.floor(segundos / 3600);
    const minutos = Math.floor((segundos % 3600) / 60);
    const segs = segundos % 60;
    
    if (horas > 0) return `${horas}h ${minutos}m`;
    if (minutos > 0) return `${minutos}m ${segs}s`;
    return `${segs}s`;
  };

  const getEstadoAtual = (): string => {
    const eventoAberto = eventos.find(e => !e.fim);
    if (eventoAberto) {
      return eventoAberto.estado;
    }
    return 'OUTRO';
  };

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
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-600">{error || 'Equipamento não encontrado'}</p>
          <Button onClick={() => navigate('/')} className="mt-4">
            Voltar
          </Button>
        </div>
      </div>
    );
  }

  const estadoAtual = getEstadoAtual();
  const estadoConfig = ESTADOS_CONFIG[estadoAtual] || ESTADOS_CONFIG.OUTRO;
  const online = dadosTempoReal?.status === 'online';

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {/* Header */}
      <div className="mb-6">
        <Button
          variant="ghost"
          onClick={() => navigate(`/linha/${equipamento.linha}`)}
          className="mb-4"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Voltar para {equipamento.linha_nome}
        </Button>

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{equipamento.nome}</h1>
            <p className="text-gray-600 mt-1">
              {equipamento.codigo} • {equipamento.tipo_display} • {equipamento.linha_nome}
            </p>
          </div>
          <div className="flex gap-2">
            <Badge variant={online ? 'default' : 'secondary'}>
              {online ? 'Online' : 'Offline'}
            </Badge>
            <Badge className={estadoConfig.color}>
              {estadoConfig.label}
            </Badge>
          </div>
        </div>
      </div>

      {/* Dados em Tempo Real */}
      {online && dadosTempoReal?.medicoes && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          {dadosTempoReal.medicoes.velocidade_atual !== undefined && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600 flex items-center">
                  <Gauge className="mr-2 h-4 w-4" />
                  Velocidade Atual
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-purple-600">
                  {dadosTempoReal.medicoes.velocidade_atual.toFixed(1)}
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  un/min (nominal: {equipamento.velocidade_nominal})
                </p>
              </CardContent>
            </Card>
          )}

          {dadosTempoReal.medicoes.contagem_saida !== undefined && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600 flex items-center">
                  <CheckCircle className="mr-2 h-4 w-4" />
                  Produção
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-green-600">
                  {dadosTempoReal.medicoes.contagem_saida.toLocaleString()}
                </div>
                <p className="text-xs text-gray-500 mt-1">unidades produzidas</p>
              </CardContent>
            </Card>
          )}

          {dadosTempoReal.medicoes.temperatura !== undefined && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600 flex items-center">
                  <Activity className="mr-2 h-4 w-4" />
                  Temperatura
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-orange-600">
                  {dadosTempoReal.medicoes.temperatura.toFixed(1)}°C
                </div>
                {equipamento.temperatura_min && equipamento.temperatura_max && (
                  <p className="text-xs text-gray-500 mt-1">
                    Faixa: {equipamento.temperatura_min}°C - {equipamento.temperatura_max}°C
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {dadosTempoReal.medicoes.pressao !== undefined && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600 flex items-center">
                  <Activity className="mr-2 h-4 w-4" />
                  Pressão
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-blue-600">
                  {dadosTempoReal.medicoes.pressao.toFixed(1)} PSI
                </div>
                {equipamento.pressao_min && equipamento.pressao_max && (
                  <p className="text-xs text-gray-500 mt-1">
                    Faixa: {equipamento.pressao_min} - {equipamento.pressao_max} PSI
                  </p>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* KPIs */}
      {metricaAtual && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">OEE</CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`text-3xl font-bold ${getOEETextColor(metricaAtual.oee)}`}>
                {metricaAtual.oee.toFixed(1)}%
              </div>
              <p className="text-xs text-gray-500 mt-1">Meta: {equipamento.meta_oee}%</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Disponibilidade</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-blue-600">
                {metricaAtual.disponibilidade.toFixed(1)}%
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {formatarTempo(metricaAtual.tempo_producao)} produzindo
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Performance</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-purple-600">
                {metricaAtual.performance.toFixed(1)}%
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {metricaAtual.velocidade_real.toFixed(1)} un/min
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Qualidade</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-green-600">
                {metricaAtual.qualidade.toFixed(1)}%
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {metricaAtual.percentual_descarte.toFixed(2)}% descarte
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="eventos" className="space-y-4">
        <TabsList>
          <TabsTrigger value="eventos">Eventos de Estado</TabsTrigger>
          <TabsTrigger value="historico">Histórico OEE</TabsTrigger>
          <TabsTrigger value="grafico">Gráfico</TabsTrigger>
        </TabsList>

        {/* Tab: Eventos */}
        <TabsContent value="eventos">
          <Card>
            <CardHeader>
              <CardTitle>Histórico de Estados</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {eventos.map((evento) => {
                  const config = ESTADOS_CONFIG[evento.estado] || ESTADOS_CONFIG.OUTRO;
                  const emAndamento = !evento.fim;

                  return (
                    <div
                      key={evento.id}
                      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${config.color}`} />
                        <div>
                          <p className="font-medium">{config.label}</p>
                          <p className="text-sm text-gray-500">
                            {new Date(evento.inicio).toLocaleString('pt-BR')}
                            {emAndamento && ' (em andamento)'}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold">
                          {formatarDuracao(evento.duracao_segundos)}
                        </p>
                        <p className="text-xs text-gray-500">{evento.origem_display}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab: Histórico */}
        <TabsContent value="historico">
          <Card>
            <CardHeader>
              <CardTitle>Histórico OEE (últimas 24 horas)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {historico.map((metrica) => (
                  <div
                    key={metrica.id}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div>
                      <p className="font-medium">
                        {new Date(metrica.data_hora).toLocaleString('pt-BR')}
                      </p>
                      <p className="text-sm text-gray-500">
                        Produção: {metrica.contagem_saida} un • Descarte: {metrica.descarte} un
                      </p>
                    </div>
                    <div className="text-right">
                      <p className={`text-2xl font-bold ${getOEETextColor(metrica.oee)}`}>
                        {metrica.oee.toFixed(1)}%
                      </p>
                      <p className="text-xs text-gray-500">
                        A: {metrica.disponibilidade.toFixed(0)}% • 
                        P: {metrica.performance.toFixed(0)}% • 
                        Q: {metrica.qualidade.toFixed(0)}%
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab: Gráfico */}
        <TabsContent value="grafico">
          <Card>
            <CardHeader>
              <CardTitle>Evolução OEE</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={[...historico].reverse()}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="data_hora"
                    tickFormatter={(value) => new Date(value).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                  />
                  <YAxis domain={[0, 100]} />
                  <Tooltip
                    labelFormatter={(value) => new Date(value).toLocaleString('pt-BR')}
                    formatter={(value: number) => `${value.toFixed(1)}%`}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="oee" stroke="#8b5cf6" name="OEE" strokeWidth={2} />
                  <Line type="monotone" dataKey="disponibilidade" stroke="#3b82f6" name="Disponibilidade" />
                  <Line type="monotone" dataKey="performance" stroke="#a855f7" name="Performance" />
                  <Line type="monotone" dataKey="qualidade" stroke="#10b981" name="Qualidade" />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default EquipamentoDetalhes;
