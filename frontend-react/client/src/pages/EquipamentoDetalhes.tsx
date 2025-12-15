import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Activity,
  AlertCircle,
  Clock,
  ArrowLeft,
  Gauge,
  ChevronLeft,
  ChevronRight,
  Calendar,
  Layers
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
  ComposedChart
} from 'recharts';
import {
  format,
  subHours,
  subDays,
  startOfDay,
  endOfDay,
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
  addHours,
  isSameDay
} from 'date-fns';
import { ptBR } from 'date-fns/locale';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import StateTimelineChart from '@/components/StateTimelineChart';
import DiagnosticsPanel from '@/components/GoldenState/DiagnosticsPanel';
import VariablesTab from '@/components/EquipamentoDetalhes/VariablesTab';
import { mapEstado } from '@/utils/equipmentStateUtils';

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
  meta_oee: number;
}

interface Metrica {
  id: number;
  data_hora: string;
  periodo: string;
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
  [key: string]: any; // Allow dynamic keys
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
    oee_realtime?: number;
  };
}

interface Turno {
  id: number;
  nome: string;
  hora_inicio: string;
  hora_fim: string;
}

// ===== COMPONENTE PRINCIPAL =====

const EquipamentoDetalhes: React.FC = () => {
  const { equipamentoId } = useParams<{ equipamentoId: string }>();
  const navigate = useNavigate();

  // Estados de Dados
  const [equipamento, setEquipamento] = useState<Equipamento | null>(null);
  const [dadosTempoReal, setDadosTempoReal] = useState<DadosTempoReal | null>(null);
  const [historico, setHistorico] = useState<Metrica[]>([]);
  const [eventos, setEventos] = useState<EventoEstado[]>([]);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [online, setOnline] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Estados de Filtro Avançado
  const [filterType, setFilterType] = useState<'turno_atual' | 'turno_especifico' | 'dia' | 'semana' | 'mes'>('turno_atual');
  const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [selectedTurnoId, setSelectedTurnoId] = useState<string>('');
  const [isConsolidated, setIsConsolidated] = useState(false);

  // Paginação
  const [histPage, setHistPage] = useState(1);
  const histItemsPerPage = 10;
  const [eventPage, setEventPage] = useState(1);
  const eventItemsPerPage = 10;

  // Busca Equipamento e Turnos
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // Equipamento
        const eqResp = await fetch(`${DJANGO_API_URL}/equipamentos/${equipamentoId}/`);
        if (!eqResp.ok) throw new Error('Falha ao buscar equipamento');
        setEquipamento(await eqResp.json());

        // Turnos
        const turnosResp = await fetch(`${DJANGO_API_URL}/turnos/`);
        if (turnosResp.ok) {
          const turnosData = await turnosResp.json();
          const listaTurnos = Array.isArray(turnosData) ? turnosData : turnosData.results || [];
          setTurnos(listaTurnos);
          if (listaTurnos.length > 0) setSelectedTurnoId(String(listaTurnos[0].id));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Erro desconhecido');
      } finally {
        setLoading(false);
      }
    };
    if (equipamentoId) fetchData();
  }, [equipamentoId]);

  // Busca Dados Tempo Real
  useEffect(() => {
    if (!equipamento) return;
    const fetchRealtime = async () => {
      try {
        const response = await fetch(`${FLASK_API_URL}/equipamento/dados/${equipamento.codigo}`);
        if (response.ok) {
          const data = await response.json();

          // Adapter: Backend (/equipamento/dados) -> Frontend (DadosTempoReal)
          const adaptedData: DadosTempoReal = {
            status: data.estado_atual,
            timestamp: data.timestamp,
            medicoes: {
              velocidade_atual: data.velocidade_atual,
              contagem_entrada: 0,
              contagem_saida: data.pecas_produzidas,
              descarte: data.refugos,
              percentual_descarte: data.pecas_produzidas > 0 ? (data.refugos / (data.pecas_produzidas + data.refugos)) * 100 : 0,
              temperatura: data.sensores?.find((s: any) => s.nome.toLowerCase().includes('temp'))?.valor || 0,
              pressao: data.sensores?.find((s: any) => s.nome.toLowerCase().includes('press'))?.valor || 0,
              estado: data.estado_atual,
              oee_realtime: data.oee_atual
            }
          };

          setDadosTempoReal(adaptedData);
          const diff = (new Date().getTime() - new Date(data.timestamp).getTime()) / 1000;
          setOnline(Math.abs(diff) <= 120);
        }
      } catch (e) { setOnline(false); }
    };
    fetchRealtime();
    const interval = setInterval(fetchRealtime, 2000);
    return () => clearInterval(interval);
  }, [equipamento]);

  // Calcula Intervalo de Tempo (Start/End) baseado no Filtro
  const timeRange = useMemo(() => {
    const now = new Date();
    let start = startOfDay(now);
    let end = endOfDay(now);
    let interval = '1h'; // Default aggregation

    const refDate = new Date(selectedDate + 'T00:00:00');

    switch (filterType) {
      case 'turno_atual':
        // Tenta encontrar o turno atual baseado na hora atual
        let foundTurno = false;
        if (turnos.length > 0) {
          const currentHour = now.getHours();
          const currentMinute = now.getMinutes();
          const currentTimeVal = currentHour * 60 + currentMinute;

          for (const t of turnos) {
            const [hIni, mIni] = t.hora_inicio.split(':').map(Number);
            const [hFim, mFim] = t.hora_fim.split(':').map(Number);

            let startVal = hIni * 60 + mIni;
            let endVal = hFim * 60 + mFim;

            let isCurrent = false;
            if (startVal > endVal) {
              // Turno cruza meia-noite
              if (currentTimeVal >= startVal || currentTimeVal < endVal) {
                isCurrent = true;
              }
            } else {
              // Turno normal
              if (currentTimeVal >= startVal && currentTimeVal < endVal) {
                isCurrent = true;
              }
            }

            if (isCurrent) {
              start = new Date(now);
              start.setHours(hIni, mIni, 0, 0);

              end = new Date(now);
              end.setHours(hFim, mFim, 0, 0);

              // Se cruza meia noite
              if (startVal > endVal) {
                // Se estamos antes da meia noite (ex: 23h), o fim é amanhã
                if (currentTimeVal >= startVal) {
                  end = addHours(end, 24);
                } else {
                  // Se estamos depois da meia noite (ex: 02h), o início foi ontem
                  start = subHours(start, 24);
                }
              }
              foundTurno = true;
              break;
            }
          }
        }

        if (!foundTurno) {
          // Fallback se não achar turno ou sem turnos cadastrados
          start = subHours(now, 8);
          end = now;
        }
        interval = '1h';
        break;
      case 'turno_especifico':
        // Lógica para pegar horário do turno selecionado no dia selecionado
        if (selectedTurnoId && turnos.length > 0) {
          const turno = turnos.find(t => String(t.id) === selectedTurnoId);
          if (turno) {
            // Parse horas (HH:MM:SS)
            const [hIni, mIni] = turno.hora_inicio.split(':').map(Number);
            const [hFim, mFim] = turno.hora_fim.split(':').map(Number);

            start = new Date(refDate);
            start.setHours(hIni, mIni, 0);

            end = new Date(refDate);
            end.setHours(hFim, mFim, 0);

            // Se fim < inicio, é dia seguinte
            if (end < start) end = addHours(end, 24);

            interval = '1h';
          }
        }
        break;
      case 'dia':
        start = startOfDay(refDate);
        end = endOfDay(refDate);
        interval = '1h';
        break;
      case 'semana':
        start = startOfWeek(refDate, { weekStartsOn: 1 }); // Segunda
        end = endOfWeek(refDate, { weekStartsOn: 1 });
        interval = '1d';
        break;
      case 'mes':
        start = startOfMonth(refDate);
        end = endOfMonth(refDate);
        interval = '1d';
        break;
    }

    // Se consolidado, override interval
    if (isConsolidated) interval = 'total';

    return { start, end, interval };
  }, [filterType, selectedDate, selectedTurnoId, isConsolidated, turnos]);

  // Busca Histórico
  // Busca Histórico (Auto-Refresh)
  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    const fetchHistorico = async (isPolling = false) => {
      if (!equipamento) return;
      try {
        // Se estiver no turno atual, sempre atualiza o 'end' para agora para pegar dados recentes
        const currentEnd = filterType === 'turno_atual' ? new Date() : timeRange.end;

        const params = new URLSearchParams({
          start: timeRange.start.toISOString(),
          end: currentEnd.toISOString(),
          interval: timeRange.interval
        });

        const response = await fetch(`${FLASK_API_URL}/equipamento/${equipamento.codigo}/historico-detalhado?${params.toString()}`);
        if (!response.ok) throw new Error('Erro ao buscar histórico');
        const data = await response.json();

        const mapped: Metrica[] = data.historico.map((h: any, idx: number) => ({
          ...h, // Spread all dynamic fields
          id: idx,
          data_hora: h.data_hora,
          periodo: filterType,
          contagem_entrada: h.entrada,
          contagem_saida: h.producao,
          descarte: h.descarte,
          percentual_descarte: h.producao > 0 ? (h.descarte / (h.producao + h.descarte)) * 100 : 0,
          velocidade_real: h.velocidade_media,
          disponibilidade: h.disponibilidade,
          performance: h.performance,
          qualidade: h.qualidade,
          oee: h.oee,
          tempo_producao: 0
        }));

        setHistorico(mapped);

        // Reset pagination only on fresh load/filter change, not on background poll
        if (!isPolling) setHistPage(1);

      } catch (err) { console.error(err); }
    };

    fetchHistorico(); // Initial load

    // Setup polling only for 'turno_atual'
    if (filterType === 'turno_atual') {
      intervalId = setInterval(() => {
        fetchHistorico(true);
      }, 5000);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [equipamento, timeRange, filterType]);

  // Busca Eventos
  useEffect(() => {
    const fetchEventos = async () => {
      if (!equipamentoId) return;
      try {
        const params = new URLSearchParams({
          equipamento_id: equipamentoId,
          ordering: '-inicio',
          limit: '100',
          data_inicio: timeRange.start.toISOString(),
          data_fim: timeRange.end.toISOString()
        });
        const response = await fetch(`${DJANGO_API_URL}/eventos-estado/?${params.toString()}`);
        if (response.ok) {
          const data = await response.json();
          setEventos(Array.isArray(data) ? data : data.results || []);
          setEventPage(1);
        }
      } catch (err) { console.error(err); }
    };
    fetchEventos();
  }, [equipamentoId, timeRange]);

  // Métrica Atual Display
  const metricaAtualDisplay = useMemo(() => {
    // Se Turno Atual e não consolidado, tenta mostrar Realtime
    if (filterType === 'turno_atual' && !isConsolidated && dadosTempoReal) {
      return {
        producao: dadosTempoReal.medicoes.contagem_saida,
        velocidade: dadosTempoReal.medicoes.velocidade_atual,
        descarte_perc: dadosTempoReal.medicoes.percentual_descarte,
        oee: dadosTempoReal.medicoes.oee_realtime || 0
      };
    }
    // Senão, mostra o primeiro item do histórico (mais recente ou o consolidado)
    if (historico.length > 0) {
      // Se consolidado, deve ter apenas 1 item
      const item = isConsolidated ? historico[0] : historico[historico.length - 1]; // Ou o mais recente? A API retorna ordenado?
      // Assumindo que API retorna cronológico (antigo -> novo). Se queremos o "atual" ou "total", pegamos o último ou o único.
      // Se for consolidado, historico[0] é o total.
      // Se for detalhado, queremos o último ponto (mais recente).
      const target = isConsolidated ? historico[0] : historico[historico.length - 1];

      return {
        producao: target.contagem_saida,
        velocidade: target.velocidade_real,
        descarte_perc: target.percentual_descarte,
        oee: target.oee
      };
    }
    return null;
  }, [filterType, isConsolidated, dadosTempoReal, historico]);

  // Gráfico
  const chartData = useMemo(() => {
    // Se consolidado, gráfico não faz muito sentido (1 ponto), mas mostramos barras
    return historico;
  }, [historico]);

  // Paginação
  const paginatedHist = historico.slice((histPage - 1) * histItemsPerPage, histPage * histItemsPerPage);
  const totalHistPages = Math.ceil(historico.length / histItemsPerPage);
  const paginatedEvents = eventos.slice((eventPage - 1) * eventItemsPerPage, eventPage * eventItemsPerPage);
  const totalEventPages = Math.ceil(eventos.length / eventItemsPerPage);

  // Helpers
  const getOEEColor = (v: number) => v >= 85 ? 'text-green-600' : v >= 70 ? 'text-yellow-600' : 'text-red-600';

  if (loading) return <div className="p-8 text-center">Carregando...</div>;
  if (!equipamento) return <div className="p-8 text-center text-red-600">Equipamento não encontrado</div>;

  return (
    <div className="w-full min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-4 sticky top-0 z-10 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{equipamento.nome}</h1>
              <p className="text-sm text-gray-500">{equipamento.codigo} • {equipamento.linha_nome}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={online ? 'default' : 'secondary'}>{online ? '🟢 Online' : '🔴 Offline'}</Badge>
          </div>
        </div>

        {/* BARRA DE FILTROS AVANÇADA */}
        <div className="flex flex-wrap items-center gap-4 bg-gray-50 p-3 rounded-lg border border-gray-200">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-gray-500" />
            <span className="text-sm font-medium text-gray-700">Filtros:</span>
          </div>

          {/* Tipo de Período */}
          <Select value={filterType} onValueChange={(v: any) => setFilterType(v)}>
            <SelectTrigger className="w-[180px] bg-white">
              <SelectValue placeholder="Período" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="turno_atual">Turno Atual</SelectItem>
              <SelectItem value="turno_especifico">Outros Turnos</SelectItem>
              <SelectItem value="dia">Dia</SelectItem>
              <SelectItem value="semana">Semana</SelectItem>
              <SelectItem value="mes">Mês</SelectItem>
            </SelectContent>
          </Select>

          {/* Controles Condicionais */}
          {filterType !== 'turno_atual' && (
            <div className="flex items-center gap-2">
              <Input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="w-[150px] bg-white"
              />
              {filterType === 'turno_especifico' && (
                <Select value={selectedTurnoId} onValueChange={setSelectedTurnoId}>
                  <SelectTrigger className="w-[150px] bg-white">
                    <SelectValue placeholder="Selecione Turno" />
                  </SelectTrigger>
                  <SelectContent>
                    {turnos.map(t => (
                      <SelectItem key={t.id} value={String(t.id)}>{t.nome}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
          )}

          <div className="h-6 w-px bg-gray-300 mx-2" />

          {/* Toggle Agrupamento */}
          <div className="flex items-center gap-2">
            <Label htmlFor="consol-mode" className="text-sm text-gray-600">Detalhado</Label>
            <Switch
              id="consol-mode"
              checked={isConsolidated}
              onCheckedChange={setIsConsolidated}
            />
            <Label htmlFor="consol-mode" className="text-sm text-gray-600">Consolidado</Label>
          </div>
        </div>
      </div>

      {/* Conteúdo */}
      <div className="p-4 space-y-4">
        {/* Card de Métricas (Resumo do Período) */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500 uppercase tracking-wider">
              {isConsolidated ? 'Resumo Consolidado' : 'Métrica Atual / Recente'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-2xl font-bold">{(metricaAtualDisplay?.velocidade ?? 0).toFixed(1)}</p>
                <p className="text-xs text-gray-500">Velocidade (un/min)</p>
              </div>
              <div>
                <p className="text-2xl font-bold">{metricaAtualDisplay?.producao ?? 0}</p>
                <p className="text-xs text-gray-500">Produção (un)</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-red-600">{(metricaAtualDisplay?.descarte_perc ?? 0).toFixed(1)}%</p>
                <p className="text-xs text-gray-500">Descarte</p>
              </div>
              <div>
                <p className={`text-2xl font-bold ${getOEEColor(metricaAtualDisplay?.oee || 0)}`}>
                  {(metricaAtualDisplay?.oee || 0).toFixed(1)}%
                </p>
                <p className="text-xs text-gray-500">OEE</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Tabs defaultValue="grafico">
          <TabsList>
            <TabsTrigger value="grafico">Gráfico</TabsTrigger>
            <TabsTrigger value="variaveis">Variáveis</TabsTrigger>
            <TabsTrigger value="tabela">Tabela</TabsTrigger>
            <TabsTrigger value="estados">Estados</TabsTrigger>
            <TabsTrigger value="eventos">Eventos</TabsTrigger>
            <TabsTrigger value="diagnosticos">Diagnósticos</TabsTrigger>
          </TabsList>

          <TabsContent value="variaveis">
            <VariablesTab
              equipamento={equipamento}
              historico={historico}
              timeRange={timeRange}
              isConsolidated={isConsolidated}
            />
          </TabsContent>

          <TabsContent value="diagnosticos" className="space-y-4">
            <DiagnosticsPanel equipamentoCodigo={equipamento.codigo} />
          </TabsContent>

          <TabsContent value="grafico" className="h-[400px]">
            <Card className="h-full">
              <CardHeader><CardTitle>Evolução ({isConsolidated ? 'Total' : 'Detalhada'})</CardTitle></CardHeader>
              <CardContent className="h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="data_hora"
                      tickFormatter={(v) => {
                        if (isConsolidated) return 'Total';
                        return format(new Date(v), filterType === 'mes' ? 'dd/MM' : 'HH:mm');
                      }}
                    />
                    <YAxis yAxisId="left" />
                    <YAxis yAxisId="right" orientation="right" domain={[0, 100]} />
                    <Tooltip labelFormatter={(v) => isConsolidated ? 'Período' : format(new Date(v), 'dd/MM HH:mm')} />
                    <Legend />
                    <Area yAxisId="left" type="monotone" dataKey="velocidade_real" fill="#3b82f6" stroke="#3b82f6" fillOpacity={0.3} name="Velocidade" />
                    <Line yAxisId="right" type="monotone" dataKey="oee" stroke="#10b981" strokeWidth={2} name="OEE %" />
                  </ComposedChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="tabela">
            <Card>
              <CardContent className="pt-4">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-2">Data/Hora</th>
                      <th className="text-right p-2">Produção</th>
                      <th className="text-right p-2">Velocidade</th>
                      <th className="text-right p-2">OEE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedHist.map((m, i) => (
                      <tr key={i} className="border-b hover:bg-gray-50">
                        <td className="p-2">
                          {isConsolidated ? 'Total do Período' : format(new Date(m.data_hora), 'dd/MM/yyyy HH:mm')}
                        </td>
                        <td className="text-right p-2">{m.contagem_saida}</td>
                        <td className="text-right p-2">{m.velocidade_real.toFixed(1)}</td>
                        <td className={`text-right p-2 font-bold ${getOEEColor(m.oee)}`}>{m.oee.toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {/* Paginação Tabela */}
                {totalHistPages > 1 && (
                  <div className="flex justify-center gap-2 mt-4">
                    <Button variant="outline" size="sm" onClick={() => setHistPage(p => Math.max(1, p - 1))} disabled={histPage === 1}><ChevronLeft className="w-4 h-4" /></Button>
                    <span className="text-sm py-2">Página {histPage} de {totalHistPages}</span>
                    <Button variant="outline" size="sm" onClick={() => setHistPage(p => Math.min(totalHistPages, p + 1))} disabled={histPage === totalHistPages}><ChevronRight className="w-4 h-4" /></Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="estados">
            <Card>
              <CardContent className="pt-4">
                <StateTimelineChart
                  eventos={eventos}
                  dateRange={{ from: timeRange.start, to: timeRange.end }}
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="eventos">
            <Card>
              <CardContent className="pt-4 space-y-2">
                {paginatedEvents.map((e, i) => {
                  const st = mapEstado(e.estado);
                  return (
                    <div key={i} className="flex items-center justify-between p-2 border rounded hover:bg-gray-50">
                      <div className="flex items-center gap-3">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: st.corHex }} />
                        <div>
                          <p className="font-medium">{st.nome}</p>
                          <p className="text-xs text-gray-500">{format(new Date(e.inicio), 'dd/MM HH:mm:ss')}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-gray-500">Duração</p>
                        <p className="text-sm font-mono">
                          {e.duracao_segundos ? `${Math.floor(e.duracao_segundos / 60)}m ${e.duracao_segundos % 60}s` : '-'}
                        </p>
                      </div>
                    </div>
                  );
                })}
                {/* Paginação Eventos */}
                {totalEventPages > 1 && (
                  <div className="flex justify-center gap-2 mt-4">
                    <Button variant="outline" size="sm" onClick={() => setEventPage(p => Math.max(1, p - 1))} disabled={eventPage === 1}><ChevronLeft className="w-4 h-4" /></Button>
                    <span className="text-sm py-2">Página {eventPage} de {totalEventPages}</span>
                    <Button variant="outline" size="sm" onClick={() => setEventPage(p => Math.min(totalEventPages, p + 1))} disabled={eventPage === totalEventPages}><ChevronRight className="w-4 h-4" /></Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default EquipamentoDetalhes;