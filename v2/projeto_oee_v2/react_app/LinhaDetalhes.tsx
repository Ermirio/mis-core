import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ArrowLeft, Activity, TrendingUp, AlertTriangle, Clock } from 'lucide-react';

// ===== TIPOS =====

interface LinhaProducao {
  id: number;
  codigo: string;
  nome: string;
  descricao: string;
  localizacao: string;
  ativa: boolean;
  velocidade_planejada: number;
  meta_producao_hora: number;
  meta_producao_turno: number;
  meta_oee: number;
  equipamentos: Equipamento[];
}

interface Equipamento {
  id: number;
  nome: string;
  codigo: string;
  tipo: string;
  tipo_display: string;
  ordem_na_linha: number;
  status: string;
  velocidade_nominal: number;
  meta_oee: number;
}

interface MetricaLinha {
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

interface DadosTempoReal {
  equipamento: string;
  status: string;
  medicoes: {
    contagem_entrada?: number;
    contagem_saida?: number;
    velocidade_atual?: number;
    estado?: number;
    temperatura?: number;
    pressao?: number;
  };
}

// ===== COMPONENTE PRINCIPAL =====

const LinhaDetalhes: React.FC = () => {
  const { linhaId } = useParams<{ linhaId: string }>();
  const navigate = useNavigate();

  const [linha, setLinha] = useState<LinhaProducao | null>(null);
  const [metricaAtual, setMetricaAtual] = useState<MetricaLinha | null>(null);
  const [historico, setHistorico] = useState<MetricaLinha[]>([]);
  const [dadosTempoReal, setDadosTempoReal] = useState<Map<string, DadosTempoReal>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || 'http://localhost:8000/api';
  const FLASK_API_URL = import.meta.env.VITE_FLASK_API_URL || 'http://localhost:5000/api';

  // Busca dados da linha
  useEffect(() => {
    const fetchLinha = async () => {
      try {
        const response = await fetch(`${DJANGO_API_URL}/linhas/${linhaId}/`);
        if (!response.ok) throw new Error('Falha ao buscar dados da linha');
        const data = await response.json();
        setLinha(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Erro desconhecido');
      } finally {
        setLoading(false);
      }
    };

    fetchLinha();
  }, [linhaId, DJANGO_API_URL]);

  // Busca métrica atual da linha
  useEffect(() => {
    const fetchMetricaAtual = async () => {
      try {
        const response = await fetch(
          `${DJANGO_API_URL}/metricas/?linha_id=${linhaId}&periodo=HORA&ordering=-data_hora&limit=1`
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

    if (linhaId) {
      fetchMetricaAtual();
      const interval = setInterval(fetchMetricaAtual, 30000); // Atualiza a cada 30s
      return () => clearInterval(interval);
    }
  }, [linhaId, DJANGO_API_URL]);

  // Busca histórico de métricas
  useEffect(() => {
    const fetchHistorico = async () => {
      try {
        const response = await fetch(
          `${DJANGO_API_URL}/metricas/?linha_id=${linhaId}&periodo=HORA&ordering=-data_hora&limit=24`
        );
        if (!response.ok) throw new Error('Falha ao buscar histórico');
        const data = await response.json();
        setHistorico(data.results || []);
      } catch (err) {
        console.error('Erro ao buscar histórico:', err);
      }
    };

    if (linhaId) {
      fetchHistorico();
    }
  }, [linhaId, DJANGO_API_URL]);

  // Busca dados em tempo real dos equipamentos
  useEffect(() => {
    if (!linha || !linha.equipamentos) return;

    const fetchDadosTempoReal = async () => {
      const novosDados = new Map<string, DadosTempoReal>();

      for (const eq of linha.equipamentos) {
        try {
          const response = await fetch(`${FLASK_API_URL}/realtime/status/${eq.codigo}`);
          if (response.ok) {
            const data = await response.json();
            novosDados.set(eq.codigo, data);
          }
        } catch (err) {
          console.error(`Erro ao buscar dados de ${eq.codigo}:`, err);
        }
      }

      setDadosTempoReal(novosDados);
    };

    fetchDadosTempoReal();
    const interval = setInterval(fetchDadosTempoReal, 5000); // Atualiza a cada 5s
    return () => clearInterval(interval);
  }, [linha, FLASK_API_URL]);

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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Carregando dados da linha...</p>
        </div>
      </div>
    );
  }

  if (error || !linha) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-600">{error || 'Linha não encontrada'}</p>
          <Button onClick={() => navigate('/')} className="mt-4">
            Voltar
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {/* Header */}
      <div className="mb-6">
        <Button
          variant="ghost"
          onClick={() => navigate('/')}
          className="mb-4"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Voltar
        </Button>

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{linha.nome}</h1>
            <p className="text-gray-600 mt-1">
              {linha.codigo} • {linha.localizacao}
            </p>
          </div>
          <Badge variant={linha.ativa ? 'default' : 'secondary'}>
            {linha.ativa ? 'Ativa' : 'Inativa'}
          </Badge>
        </div>
      </div>

      {/* KPIs Principais */}
      {metricaAtual && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          {/* OEE */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                OEE Atual
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline">
                <span className={`text-3xl font-bold ${getOEETextColor(metricaAtual.oee)}`}>
                  {metricaAtual.oee.toFixed(1)}%
                </span>
                <span className="ml-2 text-sm text-gray-500">
                  Meta: {linha.meta_oee}%
                </span>
              </div>
              <div className="mt-2 h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={`h-full ${getOEEColor(metricaAtual.oee)}`}
                  style={{ width: `${Math.min(metricaAtual.oee, 100)}%` }}
                />
              </div>
            </CardContent>
          </Card>

          {/* Disponibilidade */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                Disponibilidade
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline">
                <span className="text-3xl font-bold text-blue-600">
                  {metricaAtual.disponibilidade.toFixed(1)}%
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Tempo produção: {formatarTempo(metricaAtual.tempo_producao)}
              </p>
            </CardContent>
          </Card>

          {/* Performance */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                Performance
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline">
                <span className="text-3xl font-bold text-purple-600">
                  {metricaAtual.performance.toFixed(1)}%
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Velocidade: {metricaAtual.velocidade_real.toFixed(1)} un/min
              </p>
            </CardContent>
          </Card>

          {/* Qualidade */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                Qualidade
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline">
                <span className="text-3xl font-bold text-green-600">
                  {metricaAtual.qualidade.toFixed(1)}%
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Descarte: {metricaAtual.percentual_descarte.toFixed(2)}%
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="equipamentos" className="space-y-4">
        <TabsList>
          <TabsTrigger value="equipamentos">Equipamentos</TabsTrigger>
          <TabsTrigger value="producao">Produção</TabsTrigger>
          <TabsTrigger value="tempos">Análise de Tempos</TabsTrigger>
          <TabsTrigger value="historico">Histórico</TabsTrigger>
        </TabsList>

        {/* Tab: Equipamentos */}
        <TabsContent value="equipamentos">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {linha.equipamentos
              .sort((a, b) => a.ordem_na_linha - b.ordem_na_linha)
              .map((eq) => {
                const dadosRT = dadosTempoReal.get(eq.codigo);
                const online = dadosRT?.status === 'online';

                return (
                  <Card
                    key={eq.id}
                    className="cursor-pointer hover:shadow-lg transition-shadow"
                    onClick={() => navigate(`/equipamento/${eq.id}`)}
                  >
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-lg">{eq.nome}</CardTitle>
                        <Badge variant={online ? 'default' : 'secondary'}>
                          {online ? 'Online' : 'Offline'}
                        </Badge>
                      </div>
                      <p className="text-sm text-gray-500">{eq.tipo_display}</p>
                    </CardHeader>
                    <CardContent>
                      {online && dadosRT?.medicoes && (
                        <div className="space-y-2 text-sm">
                          {dadosRT.medicoes.velocidade_atual !== undefined && (
                            <div className="flex justify-between">
                              <span className="text-gray-600">Velocidade:</span>
                              <span className="font-semibold">
                                {dadosRT.medicoes.velocidade_atual.toFixed(1)} un/min
                              </span>
                            </div>
                          )}
                          {dadosRT.medicoes.contagem_saida !== undefined && (
                            <div className="flex justify-between">
                              <span className="text-gray-600">Produção:</span>
                              <span className="font-semibold">
                                {dadosRT.medicoes.contagem_saida} un
                              </span>
                            </div>
                          )}
                          {dadosRT.medicoes.temperatura !== undefined && (
                            <div className="flex justify-between">
                              <span className="text-gray-600">Temperatura:</span>
                              <span className="font-semibold">
                                {dadosRT.medicoes.temperatura.toFixed(1)}°C
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                      {!online && (
                        <p className="text-sm text-gray-500">Sem dados recentes</p>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
          </div>
        </TabsContent>

        {/* Tab: Produção */}
        <TabsContent value="producao">
          {metricaAtual && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle>Contadores</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Entrada:</span>
                    <span className="text-2xl font-bold text-blue-600">
                      {metricaAtual.contagem_entrada.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Saída:</span>
                    <span className="text-2xl font-bold text-green-600">
                      {metricaAtual.contagem_saida.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Descarte:</span>
                    <span className="text-2xl font-bold text-red-600">
                      {metricaAtual.descarte.toLocaleString()}
                    </span>
                  </div>
                  <div className="pt-2 border-t">
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">% Descarte:</span>
                      <span className="text-xl font-semibold text-red-600">
                        {metricaAtual.percentual_descarte.toFixed(2)}%
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Velocidades</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Planejada:</span>
                    <span className="text-2xl font-bold text-gray-700">
                      {metricaAtual.velocidade_planejada.toFixed(1)} un/min
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Real:</span>
                    <span className="text-2xl font-bold text-purple-600">
                      {metricaAtual.velocidade_real.toFixed(1)} un/min
                    </span>
                  </div>
                  <div className="pt-2 border-t">
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">Eficiência:</span>
                      <span className="text-xl font-semibold text-purple-600">
                        {((metricaAtual.velocidade_real / metricaAtual.velocidade_planejada) * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* Tab: Análise de Tempos */}
        <TabsContent value="tempos">
          {metricaAtual && (
            <Card>
              <CardHeader>
                <CardTitle>Distribuição de Tempos (última hora)</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-sm font-medium text-green-700">Produção</span>
                      <span className="text-sm font-semibold text-green-700">
                        {formatarTempo(metricaAtual.tempo_producao)}
                      </span>
                    </div>
                    <div className="h-4 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-green-500"
                        style={{ width: `${(metricaAtual.tempo_producao / 60) * 100}%` }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-sm font-medium text-red-700">Parada</span>
                      <span className="text-sm font-semibold text-red-700">
                        {formatarTempo(metricaAtual.tempo_parada)}
                      </span>
                    </div>
                    <div className="h-4 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-red-500"
                        style={{ width: `${(metricaAtual.tempo_parada / 60) * 100}%` }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-sm font-medium text-yellow-700">Setup</span>
                      <span className="text-sm font-semibold text-yellow-700">
                        {formatarTempo(metricaAtual.tempo_setup)}
                      </span>
                    </div>
                    <div className="h-4 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-yellow-500"
                        style={{ width: `${(metricaAtual.tempo_setup / 60) * 100}%` }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-sm font-medium text-gray-700">Não Programado</span>
                      <span className="text-sm font-semibold text-gray-700">
                        {formatarTempo(metricaAtual.tempo_nao_programado)}
                      </span>
                    </div>
                    <div className="h-4 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gray-500"
                        style={{ width: `${(metricaAtual.tempo_nao_programado / 60) * 100}%` }}
                      />
                    </div>
                  </div>

                  <div className="pt-4 border-t">
                    <div className="flex justify-between">
                      <span className="font-medium">Tempo Disponível:</span>
                      <span className="font-semibold">{formatarTempo(metricaAtual.tempo_disponivel)}</span>
                    </div>
                    <div className="flex justify-between mt-2">
                      <span className="font-medium">Tempo Programado:</span>
                      <span className="font-semibold">{formatarTempo(metricaAtual.tempo_programado)}</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
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
                        Produção: {metrica.contagem_saida} un
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
      </Tabs>
    </div>
  );
};

export default LinhaDetalhes;
