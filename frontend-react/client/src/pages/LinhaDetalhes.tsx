import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ArrowLeft, Activity, TrendingUp, AlertTriangle, Clock, Filter, Package } from 'lucide-react';
import TonnageCard from '@/components/TonnageCard';
import ThroughputChart from '@/components/ThroughputChart';
import FilterBar from '@/components/FilterBar';
import ProductionChart from '@/components/ProductionChart';
import SpeedChart from '@/components/SpeedChart';
import SKUProductionChart from '@/components/SKUProductionChart';
import { fetchTonnageRealtime, fetchTonnageHistory, type TonnageRealtimeData, type TonnageHistoryData } from '@/services/tonnageApi';

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
    turno: string;
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
    ordem_producao?: string;
    meta_producao?: number;
    sku_codigo?: string;
    sku_descricao?: string;
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

interface Turno {
    id: number;
    nome: string;
    codigo: string;
    hora_inicio: string;
    hora_fim: string;
    ativo: boolean;
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
    const [turnoFiltro, setTurnoFiltro] = useState<string>('atual');
    const [diaFiltro, setDiaFiltro] = useState<string>(new Date().toISOString().split('T')[0]);
    const [skuFiltro, setSkuFiltro] = useState<string>('');
    const [opFiltro, setOpFiltro] = useState<string>('');
    const [turnos, setTurnos] = useState<Turno[]>([]);
    const [periodo, setPeriodo] = useState<'HORA' | 'TURNO' | 'DIA'>('TURNO');

    // Estados de tonelagem
    const [tonnageRealtime, setTonnageRealtime] = useState<TonnageRealtimeData | null>(null);
    const [tonnageHistory, setTonnageHistory] = useState<TonnageHistoryData | null>(null);
    const [tonnageLoading, setTonnageLoading] = useState(false);

    // Estado de Projeção
    const [projection, setProjection] = useState<any>(null);

    // Estados de análise
    const [periodoTipo, setPeriodoTipo] = useState<'rapido' | 'personalizado'>('rapido');
    const [periodoRapido, setPeriodoRapido] = useState('hoje');
    const [dataInicio, setDataInicio] = useState(new Date().toISOString().split('T')[0]);
    const [dataFim, setDataFim] = useState(new Date().toISOString().split('T')[0]);
    const [granularidade, setGranularidade] = useState<'hora' | 'turno' | 'dia' | 'semana'>('hora');
    const [dadosProducao, setDadosProducao] = useState<any[]>([]);
    const [dadosVelocidade, setDadosVelocidade] = useState<any[]>([]);
    const [dadosSKU, setDadosSKU] = useState<any[]>([]);
    const [analiseLoading, setAnaliseLoading] = useState(false);

    const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || 'http://127.0.0.1:8000/api';
    const FLASK_API_URL = import.meta.env.VITE_FLASK_API_URL || 'http://127.0.0.1:5000/api';

    // Busca dados da linha
    useEffect(() => {
        const fetchLinha = async () => {
            setLoading(true);
            setError(null);
            setLinha(null);

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

        if (linhaId) {
            fetchLinha();
        }
    }, [linhaId]);

    // Busca turnos disponíveis
    useEffect(() => {
        const fetchTurnos = async () => {
            try {
                const response = await fetch(`${DJANGO_API_URL}/turnos/?ativo=true`);
                if (response.ok) {
                    const data = await response.json();
                    const turnos = Array.isArray(data) ? data : data.results || [];
                    setTurnos(turnos);
                }
            } catch (err) {
                console.error('Erro ao buscar turnos:', err);
            }
        };

        fetchTurnos();
    }, []);

    // Busca métrica atual da linha com filtros corretos
    useEffect(() => {
        const fetchMetricaAtual = async () => {
            try {
                // Constrói URL com parâmetros corretos
                const params = new URLSearchParams({
                    linha_id: linhaId || '',
                    periodo: periodo,
                });

                // Adiciona filtro de turno se aplicável
                if (periodo === 'TURNO' || periodo === 'HORA') {
                    params.append('turno', turnoFiltro);
                }

                // Adiciona filtro de data se aplicável
                if (periodo === 'DIA' || periodo === 'HORA') {
                    params.append('data_inicio', `${diaFiltro}T00:00:00Z`);
                    params.append('data_fim', `${diaFiltro}T23:59:59Z`);
                }

                const url = `${DJANGO_API_URL}/metricas_linha_consolidadas/?${params.toString()}`;

                const response = await fetch(url);
                if (!response.ok) throw new Error('Falha ao buscar métrica atual');

                const data = await response.json();
                if (data.metricas && data.metricas.length > 0) {
                    setMetricaAtual(data.metricas[0]);
                } else {
                    setMetricaAtual(null);
                }
            } catch (err) {
                console.error('Erro ao buscar métrica atual:', err);
            }
        };

        if (linhaId) {
            fetchMetricaAtual();
            const interval = setInterval(fetchMetricaAtual, 10000); // Atualiza a cada 10s
            return () => clearInterval(interval);
        }
    }, [linhaId, turnoFiltro, diaFiltro, periodo]);

    // Busca histórico de métricas DETALHADO (com SKU/OP)
    useEffect(() => {
        const fetchHistorico = async () => {
            try {
                const params = new URLSearchParams({
                    periodo: 'TURNO',
                    limit: '50' // Aumentado limite
                });

                // Adiciona filtro de data se aplicável
                params.append('data_inicio', `${diaFiltro}T00:00:00Z`);
                params.append('data_fim', `${diaFiltro}T23:59:59Z`);

                // Novos filtros
                if (turnoFiltro && turnoFiltro !== 'atual') {
                    params.append('turno', turnoFiltro);
                }
                if (skuFiltro) {
                    params.append('sku', skuFiltro);
                }
                if (opFiltro) {
                    params.append('op', opFiltro);
                }

                const url = `${DJANGO_API_URL}/linhas/${linhaId}/historico-detalhado/?${params.toString()}`;

                const response = await fetch(url);
                if (!response.ok) throw new Error('Falha ao buscar histórico');

                const data = await response.json();
                setHistorico(data.dados || []);
            } catch (err) {
                console.error('Erro ao buscar histórico:', err);
            }
        };

        if (linhaId) {
            fetchHistorico();
        }
    }, [linhaId, diaFiltro, turnoFiltro, skuFiltro, opFiltro]); // Adicionado dependências

    // Busca Projeção
    useEffect(() => {
        const fetchProjection = async () => {
            if (!linhaId) return;
            try {
                const response = await fetch(`${DJANGO_API_URL}/linhas/${linhaId}/projection/`);
                if (response.ok) {
                    const data = await response.json();
                    setProjection(data);
                }
            } catch (err) {
                console.error('Erro ao buscar projeção:', err);
            }
        };

        fetchProjection();
        const interval = setInterval(fetchProjection, 30000);
        return () => clearInterval(interval);
    }, [linhaId, DJANGO_API_URL]);

    // Busca dados de tonelagem
    useEffect(() => {
        const fetchTonnageData = async () => {
            if (!linhaId) return;

            setTonnageLoading(true);
            try {
                const id = parseInt(linhaId);

                // Buscar dados em tempo real
                const realtimeData = await fetchTonnageRealtime(id);
                setTonnageRealtime(realtimeData);

                // Buscar histórico
                const historyData = await fetchTonnageHistory(
                    id,
                    periodo,
                    periodo === 'DIA' ? diaFiltro : undefined,
                    periodo === 'DIA' ? diaFiltro : undefined,
                    periodo === 'TURNO' && turnoFiltro !== 'atual' ? turnoFiltro : undefined
                );
                setTonnageHistory(historyData);

            } catch (err) {
                console.error('Erro ao buscar dados de tonelagem:', err);
            } finally {
                setTonnageLoading(false);
            }
        };

        fetchTonnageData();
        // Atualizar a cada 30 segundos
        const interval = setInterval(fetchTonnageData, 30000);
        return () => clearInterval(interval);
    }, [linhaId, periodo, turnoFiltro, diaFiltro]);

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

    // Funções de análise
    const calcularPeriodoRapido = (tipo: string): { dataInicio: string; dataFim: string } => {
        const agora = new Date();
        const dataFim = agora.toISOString();
        let dataInicio: Date;

        switch (tipo) {
            case 'ultima_hora':
                dataInicio = new Date(agora.getTime() - 60 * 60 * 1000);
                break;
            case 'hoje':
                dataInicio = new Date(agora.setHours(0, 0, 0, 0));
                break;
            case 'ontem':
                const ontem = new Date(agora);
                ontem.setDate(ontem.getDate() - 1);
                ontem.setHours(0, 0, 0, 0);
                dataInicio = ontem;
                break;
            case 'ultimos_7_dias':
                dataInicio = new Date(agora.getTime() - 7 * 24 * 60 * 60 * 1000);
                break;
            case 'ultimos_30_dias':
                dataInicio = new Date(agora.getTime() - 30 * 24 * 60 * 60 * 1000);
                break;
            default:
                return { dataInicio: '', dataFim: '' };
        }

        return {
            dataInicio: dataInicio.toISOString(),
            dataFim
        };
    };

    const fetchDadosAnalise = async () => {
        if (!linhaId) return;

        setAnaliseLoading(true);
        try {
            const id = parseInt(linhaId);

            // Calcula período
            let inicio = dataInicio;
            let fim = dataFim;

            if (periodoTipo === 'rapido' && periodoRapido !== 'turno_atual' && periodoRapido !== 'turno_anterior') {
                const periodo = calcularPeriodoRapido(periodoRapido);
                inicio = periodo.dataInicio;
                fim = periodo.dataFim;
            }

            // Busca dados em paralelo
            const [producaoRes, velocidadeRes, skuRes] = await Promise.all([
                fetch(`${DJANGO_API_URL}/linhas/${id}/analise/producao/?${new URLSearchParams({
                    ...(inicio && { data_inicio: inicio }),
                    ...(fim && { data_fim: fim }),
                    granularidade: granularidade
                })}`),
                fetch(`${DJANGO_API_URL}/linhas/${id}/analise/velocidade/?${new URLSearchParams({
                    ...(inicio && { data_inicio: inicio }),
                    ...(fim && { data_fim: fim }),
                    granularidade: granularidade
                })}`),
                fetch(`${DJANGO_API_URL}/linhas/${id}/analise/sku/?${new URLSearchParams({
                    ...(inicio && { data_inicio: inicio }),
                    ...(fim && { data_fim: fim })
                })}`)
            ]);

            const [producao, velocidade, sku] = await Promise.all([
                producaoRes.json(),
                velocidadeRes.json(),
                skuRes.json()
            ]);

            setDadosProducao(producao.dados || []);
            setDadosVelocidade(velocidade.dados || []);
            setDadosSKU(sku.dados || []);

        } catch (err) {
            console.error('Erro ao buscar dados de análise:', err);
        } finally {
            setAnaliseLoading(false);
        }
    };

    const aplicarFiltros = () => {
        fetchDadosAnalise();
    };

    const limparFiltros = () => {
        setPeriodoTipo('rapido');
        setPeriodoRapido('turno_atual');
        setGranularidade('turno');
        setDataInicio(new Date().toISOString().split('T')[0]);
        setDataFim(new Date().toISOString().split('T')[0]);
    };

    const exportarDados = () => {
        console.log('Exportar dados...');
    };

    // useEffect para buscar dados de análise
    useEffect(() => {
        if (linhaId) {
            fetchDadosAnalise();
        }
    }, [linhaId]);


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
                    <AlertTriangle className="w-12 h-12 text-red-600 mx-auto mb-4" />
                    <p className="text-red-600 mb-4">{error || 'Linha não encontrada'}</p>
                    <Button onClick={() => navigate(-1)}>Voltar</Button>
                </div>
            </div>
        );
    }

    return (
        <div className="w-full h-screen flex flex-col bg-gray-50">
            {/* Header */}
            <div className="bg-white border-b border-gray-200 p-4 flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => navigate(-1)}
                    >
                        <ArrowLeft className="w-5 h-5" />
                    </Button>
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">{linha.nome}</h1>
                        <p className="text-sm text-gray-500">{linha.codigo}</p>
                    </div>
                </div>
                <Badge variant={linha.ativa ? 'default' : 'secondary'}>
                    {linha.ativa ? 'Ativa' : 'Inativa'}
                </Badge>
            </div>

            {/* Filtros */}
            <div className="bg-white border-b border-gray-200 p-4 flex gap-4 items-end">
                <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 mb-2">Período</label>
                    <Select value={periodo} onValueChange={(value) => setPeriodo(value as 'HORA' | 'TURNO' | 'DIA')}>
                        <SelectTrigger className="w-full">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="HORA">Hora</SelectItem>
                            <SelectItem value="TURNO">Turno</SelectItem>
                            <SelectItem value="DIA">Dia</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {(periodo === 'TURNO' || periodo === 'HORA') && (
                    <div className="flex-1">
                        <label className="block text-sm font-medium text-gray-700 mb-2">Turno</label>
                        <Select value={turnoFiltro} onValueChange={setTurnoFiltro}>
                            <SelectTrigger className="w-full">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="atual">Turno Atual</SelectItem>
                                {turnos.map(turno => (
                                    <SelectItem key={turno.id} value={turno.nome}>
                                        {turno.nome}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                )}

                {(periodo === 'DIA' || periodo === 'HORA') && (
                    <div className="flex-1">
                        <label className="block text-sm font-medium text-gray-700 mb-2">Data</label>
                        <input
                            type="date"
                            value={diaFiltro}
                            onChange={(e) => setDiaFiltro(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        />
                    </div>
                )}
            </div>

            {/* Conteúdo Principal */}
            {/* Conteúdo Principal */}
            <div className="flex-1 p-6 overflow-auto">
                <Tabs defaultValue="visao-geral" className="w-full">
                    <TabsList className="mb-6">
                        <TabsTrigger value="visao-geral">Visão Geral</TabsTrigger>
                        <TabsTrigger value="analise">Análise</TabsTrigger>
                        <TabsTrigger value="tonelagem">Tonelagem</TabsTrigger>
                        <TabsTrigger value="equipamentos">Equipamentos</TabsTrigger>
                        <TabsTrigger value="historico">Histórico</TabsTrigger>
                    </TabsList>

                    {/* ABA VISÃO GERAL */}
                    <TabsContent value="visao-geral" className="space-y-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                            {/* Card OEE */}
                            <Card>
                                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                    <CardTitle className="text-sm font-medium">OEE</CardTitle>
                                    <Activity className="h-4 w-4 text-muted-foreground" />
                                </CardHeader>
                                <CardContent>
                                    <div className={`text-2xl font-bold ${getOEEColor(metricaAtual?.oee || 0)}`}>
                                        {metricaAtual?.oee?.toFixed(1) || '0.0'}%
                                    </div>
                                    <p className="text-sm font-semibold text-muted-foreground mt-1">
                                        Meta: {linha.meta_oee}%
                                    </p>
                                </CardContent>
                            </Card>

                            {/* Card Tonelagem Resumido */}
                            <TonnageCard
                                toneladas={tonnageRealtime?.toneladas_hora_atual || 0}
                                vazao={tonnageRealtime?.vazao_real || 0}
                                meta={tonnageRealtime?.meta_vazao || undefined}
                                formato={tonnageRealtime?.formato_atual || undefined}
                                periodo="hora"
                                loading={tonnageLoading}
                            />
                        </div>

                        {/* Projeção e OP */}
                        {projection && (
                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-sm font-medium">Produção & Projeção</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="flex justify-between items-center mb-4">
                                        <div>
                                            <p className="text-xs text-muted-foreground">Ordem de Produção</p>
                                            <p className="text-lg font-bold text-purple-700">{metricaAtual?.ordem_producao || projection.op || 'N/A'}</p>
                                        </div>
                                        <div className="text-right">
                                            <p className="text-xs text-muted-foreground">Status</p>
                                            <Badge variant={
                                                projection.status === 'AHEAD' ? 'default' :
                                                    projection.status === 'ON_TRACK' ? 'secondary' :
                                                        projection.status === 'RISK' ? 'outline' : 'destructive'
                                            }>
                                                {projection.status}
                                            </Badge>
                                        </div>
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex justify-between text-sm">
                                            <span>Produzido: <strong>{metricaAtual?.contagem_saida?.toLocaleString() || projection.produzido?.toLocaleString() || '-'}</strong></span>
                                            <span>Meta: <strong>{metricaAtual?.meta_producao?.toLocaleString() || projection.meta?.toLocaleString() || '-'}</strong></span>
                                        </div>
                                        <div className="relative h-2 bg-gray-100 rounded-full overflow-hidden">
                                            <div
                                                className="absolute h-full bg-blue-500"
                                                style={{ width: `${Math.min(((projection.produzido || 0) / (projection.meta || 1)) * 100, 100)}%` }}
                                            />
                                            <div
                                                className="absolute h-full bg-blue-300 opacity-50"
                                                style={{ width: `${Math.min(((projection.projecao_realista || 0) / (projection.meta || 1)) * 100, 100)}%` }}
                                            />
                                        </div>
                                        <div className="flex justify-between text-xs text-muted-foreground">
                                            <span>Proj. Realista: {projection.projecao_realista?.toLocaleString() ?? '-'}</span>
                                            <span>Proj. Otimista: {projection.projecao_otimista?.toLocaleString() ?? '-'}</span>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* Métrica Atual Detalhada */}
                        {metricaAtual && (
                            <Card>
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <Activity className="w-5 h-5" />
                                        Métrica Atual ({periodo})
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="space-y-4">
                                        <div className="grid grid-cols-2 gap-4">
                                            <div>
                                                <p className="text-sm text-gray-500">Entrada</p>
                                                <p className="text-2xl font-bold">{metricaAtual.contagem_entrada}</p>
                                            </div>
                                            <div>
                                                <p className="text-sm text-gray-500">Saída</p>
                                                <p className="text-2xl font-bold">{metricaAtual.contagem_saida}</p>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-2 gap-4">
                                            <div>
                                                <p className="text-sm text-gray-500">Velocidade Real</p>
                                                <p className="text-lg font-semibold">{metricaAtual.velocidade_real.toFixed(2)} un/min</p>
                                            </div>
                                            <div>
                                                <p className="text-sm text-gray-500">Velocidade Planejada</p>
                                                <p className="text-lg font-semibold">{metricaAtual.velocidade_planejada} un/min</p>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-2 gap-4">
                                            <div>
                                                <p className="text-sm text-gray-500">Tempo Produção</p>
                                                <p className="text-lg font-semibold">{formatarTempo(metricaAtual.tempo_producao)}</p>
                                            </div>
                                            <div>
                                                <p className="text-sm text-gray-500">Tempo Parada</p>
                                                <p className="text-lg font-semibold">{formatarTempo(metricaAtual.tempo_parada)}</p>
                                            </div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        )}
                    </TabsContent>

                    {/* ABA ANÁLISE */}
                    <TabsContent value="analise" className="space-y-6">
                        {/* Filtros */}
                        <FilterBar
                            periodoTipo={periodoTipo}
                            setPeriodoTipo={setPeriodoTipo}
                            periodoRapido={periodoRapido}
                            setPeriodoRapido={setPeriodoRapido}
                            dataInicio={dataInicio}
                            setDataInicio={setDataInicio}
                            dataFim={dataFim}
                            setDataFim={setDataFim}
                            granularidade={granularidade}
                            setGranularidade={setGranularidade}
                            turno={turnoFiltro}
                            setTurno={setTurnoFiltro}
                            turnos={turnos}
                            onAplicar={aplicarFiltros}
                            onLimpar={limparFiltros}
                            onExportar={exportarDados}
                        />

                        {/* Gráficos */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <ProductionChart
                                data={dadosProducao}
                                meta={linha?.meta_producao_turno}
                                periodo={granularidade}
                                loading={analiseLoading}
                            />

                            <SpeedChart
                                data={dadosVelocidade}
                                periodo={granularidade}
                                loading={analiseLoading}
                            />
                        </div>

                        <SKUProductionChart
                            data={dadosSKU}
                            loading={analiseLoading}
                        />
                    </TabsContent>

                    {/* ABA TONELAGEM */}
                    <TabsContent value="tonelagem" className="space-y-6">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            {/* Card Principal com Vazão Atual */}
                            <Card>
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm font-medium text-gray-500">
                                        Tonelagem e Vazão Atual
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="space-y-3">
                                        <div>
                                            <p className="text-xs text-muted-foreground">Toneladas (Hora)</p>
                                            <div className="text-3xl font-bold text-gray-900">
                                                {tonnageRealtime?.toneladas_hora_atual?.toFixed(3) || '0.000'} t
                                            </div>
                                        </div>
                                        <div className="pt-2 border-t">
                                            <p className="text-xs text-muted-foreground">Vazão Atual</p>
                                            <div className="text-2xl font-semibold text-blue-600">
                                                {tonnageRealtime?.vazao_real?.toFixed(1) || '0.0'} t/h
                                            </div>
                                        </div>
                                        {tonnageRealtime?.formato_atual && (
                                            <div className="pt-2 border-t">
                                                <p className="text-xs text-muted-foreground">Formato</p>
                                                <div className="text-lg font-medium text-gray-700">
                                                    {tonnageRealtime.formato_atual}g
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Card Histórico (Turno/Dia) */}
                            <Card>
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm font-medium text-gray-500">
                                        Total no Período ({periodo})
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="text-3xl font-bold text-gray-900">
                                        {tonnageHistory?.toneladas_total?.toFixed(3) || '0.000'} t
                                    </div>
                                    <p className="text-sm text-gray-500 mt-1">
                                        Vazão Média: {tonnageHistory?.vazao_media?.toFixed(3) || '0.000'} t/h
                                    </p>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Gráfico de Vazão */}
                        <ThroughputChart
                            data={tonnageHistory?.dados.map(d => ({
                                timestamp: d.data_hora,
                                vazao: parseFloat(d.vazao_real_ton_hora.toString()),
                                toneladas: parseFloat(d.toneladas_produzidas.toString())
                            })) || []}
                            meta={tonnageRealtime?.meta_vazao || undefined}
                            periodo={periodo.toLowerCase() as 'hora' | 'turno' | 'dia'}
                            loading={tonnageLoading}
                        />
                    </TabsContent>

                    {/* ABA EQUIPAMENTOS */}
                    <TabsContent value="equipamentos">
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <TrendingUp className="w-5 h-5" />
                                    Equipamentos da Linha
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-3">
                                    {linha.equipamentos.map(eq => {
                                        const dadosEq = dadosTempoReal.get(eq.codigo);
                                        return (
                                            <div
                                                key={eq.id}
                                                className="p-3 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50"
                                                onClick={() => navigate(`/equipamento/${eq.id}`)}
                                            >
                                                <div className="flex justify-between items-start mb-2">
                                                    <div>
                                                        <p className="font-semibold text-gray-900">{eq.nome}</p>
                                                        <p className="text-xs text-gray-500">{eq.codigo}</p>
                                                    </div>
                                                    <Badge variant={eq.status === 'ATIVO' ? 'default' : 'secondary'}>
                                                        {eq.status}
                                                    </Badge>
                                                </div>
                                                {dadosEq && (
                                                    <div className="text-xs text-gray-600">
                                                        <p>Status: {dadosEq.status}</p>
                                                        {dadosEq.medicoes?.velocidade_atual && (
                                                            <p>Velocidade: {dadosEq.medicoes.velocidade_atual} un/min</p>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* ABA HISTÓRICO */}
                    <TabsContent value="historico" className="space-y-6">
                        <Card>
                            <CardHeader>
                                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                                    <div>
                                        <CardTitle className="flex items-center gap-2">
                                            <Clock className="w-5 h-5" />
                                            Histórico Detalhado
                                        </CardTitle>
                                        <p className="text-sm text-muted-foreground">
                                            Histórico de métricas consolidadas
                                        </p>
                                    </div>

                                    {/* Filtros da Tabela */}
                                    <div className="flex flex-wrap gap-2 items-end">
                                        <div className="w-32">
                                            <label className="text-xs font-medium text-gray-500 mb-1 block">Data</label>
                                            <input
                                                type="date"
                                                value={diaFiltro}
                                                onChange={(e) => setDiaFiltro(e.target.value)}
                                                className="w-full px-2 py-1 text-sm border rounded"
                                            />
                                        </div>
                                        <div className="w-32">
                                            <label className="text-xs font-medium text-gray-500 mb-1 block">Turno</label>
                                            <Select value={turnoFiltro} onValueChange={setTurnoFiltro}>
                                                <SelectTrigger className="h-8 text-sm">
                                                    <SelectValue placeholder="Turno" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="atual">Todos</SelectItem>
                                                    {turnos.map(t => (
                                                        <SelectItem key={t.id} value={t.nome}>{t.nome}</SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="w-32">
                                            <label className="text-xs font-medium text-gray-500 mb-1 block">SKU</label>
                                            <input
                                                type="text"
                                                placeholder="Filtrar SKU..."
                                                value={skuFiltro}
                                                onChange={(e) => setSkuFiltro(e.target.value)}
                                                className="w-full px-2 py-1 text-sm border rounded h-8"
                                            />
                                        </div>
                                        <div className="w-32">
                                            <label className="text-xs font-medium text-gray-500 mb-1 block">OP</label>
                                            <input
                                                type="text"
                                                placeholder="Filtrar OP..."
                                                value={opFiltro}
                                                onChange={(e) => setOpFiltro(e.target.value)}
                                                className="w-full px-2 py-1 text-sm border rounded h-8"
                                            />
                                        </div>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="h-8"
                                            onClick={() => {
                                                setSkuFiltro('');
                                                setOpFiltro('');
                                                setTurnoFiltro('atual');
                                                setDiaFiltro(new Date().toISOString().split('T')[0]);
                                            }}
                                        >
                                            Limpar
                                        </Button>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {historico.length > 0 ? (
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-sm">
                                            <thead>
                                                <tr className="border-b bg-gray-50">
                                                    <th className="text-left py-3 px-3 font-semibold">Data/Hora</th>
                                                    <th className="text-left py-3 px-3 font-semibold">Turno</th>
                                                    <th className="text-left py-3 px-3 font-semibold">SKU</th>
                                                    <th className="text-left py-3 px-3 font-semibold">OP</th>
                                                    <th className="text-right py-3 px-3 font-semibold">Produção</th>
                                                    <th className="text-right py-3 px-3 font-semibold">Descarte</th>
                                                    <th className="text-right py-3 px-3 font-semibold">Disp.</th>
                                                    <th className="text-right py-3 px-3 font-semibold">Perf.</th>
                                                    <th className="text-right py-3 px-3 font-semibold">Qual.</th>
                                                    <th className="text-right py-3 px-3 font-semibold">OEE</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {historico.map((metrica, idx) => (
                                                    <tr key={metrica.id || idx} className="border-b hover:bg-gray-50">
                                                        <td className="py-2 px-3">
                                                            {new Date(metrica.data_hora).toLocaleString('pt-BR', {
                                                                day: '2-digit',
                                                                month: '2-digit',
                                                                hour: '2-digit',
                                                                minute: '2-digit'
                                                            })}
                                                        </td>
                                                        <td className="py-2 px-3">
                                                            <Badge variant="outline" className="text-xs">
                                                                {metrica.turno || '-'}
                                                            </Badge>
                                                        </td>
                                                        <td className="py-2 px-3 text-xs">
                                                            {metrica.sku_codigo || '-'}
                                                        </td>
                                                        <td className="py-2 px-3 text-xs font-medium text-purple-700">
                                                            {metrica.ordem_producao || '-'}
                                                        </td>
                                                        <td className="text-right py-2 px-3 font-medium">
                                                            {metrica.contagem_saida?.toLocaleString() || '0'}
                                                        </td>
                                                        <td className="text-right py-2 px-3 text-red-600">
                                                            {metrica.descarte || '0'}
                                                        </td>
                                                        <td className="text-right py-2 px-3">
                                                            <span className={metrica.disponibilidade >= 85 ? 'text-green-600' : 'text-orange-600'}>
                                                                {metrica.disponibilidade?.toFixed(1) || '0.0'}%
                                                            </span>
                                                        </td>
                                                        <td className="text-right py-2 px-3">
                                                            <span className={metrica.performance >= 85 ? 'text-green-600' : 'text-orange-600'}>
                                                                {metrica.performance?.toFixed(1) || '0.0'}%
                                                            </span>
                                                        </td>
                                                        <td className="text-right py-2 px-3">
                                                            <span className={metrica.qualidade >= 95 ? 'text-green-600' : 'text-orange-600'}>
                                                                {metrica.qualidade?.toFixed(1) || '0.0'}%
                                                            </span>
                                                        </td>
                                                        <td className="text-right py-2 px-3">
                                                            <span className={`font-bold ${getOEEColor(metrica.oee || 0)}`}>
                                                                {metrica.oee?.toFixed(1) || '0.0'}%
                                                            </span>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                ) : (
                                    <div className="text-center py-8 text-gray-500">
                                        <Clock className="w-12 h-12 mx-auto mb-2 opacity-50" />
                                        <p>Nenhum histórico disponível para o período selecionado</p>
                                        <p className="text-xs mt-1">Ajuste os filtros para visualizar dados</p>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>
            </div>
        </div >
    );
};

export default LinhaDetalhes;