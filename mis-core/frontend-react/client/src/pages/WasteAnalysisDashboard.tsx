import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
    Trash2, TrendingDown, Factory, AlertTriangle, RefreshCw,
    CalendarIcon, BarChart3, PieChart, LineChart, Download, Filter, ChevronDown
} from "lucide-react";
import { format, subDays } from "date-fns";
import { ptBR } from "date-fns/locale";
import Plot from 'react-plotly.js';
import axios from 'axios';

const DJANGO_API = import.meta.env.VITE_DJANGO_API_URL;

interface WasteData {
    periodo: string;
    periodo_label: string;
    consolidado: {
        descarte_tons: number;
        descarte_percentual: number;
        producao_tons: number;
        total_unidades: number;
    };
    por_linha: Array<{
        linha: string;
        codigo: string;
        descarte_tons: number;
        descarte_percentual: number;
        producao_tons: number;
        unidades_ruins: number;
    }>;
    top_equipamentos: Array<{
        equipamento: string;
        linha: string;
        unidades: number;
        tons: number;
        percentual: number;
    }>;
    linha_maior_descarte: {
        linha: string;
        descarte_tons: number;
        descarte_percentual: number;
    } | null;
    evolucao_temporal: Array<{
        hora: string;
        descarte: number;
        producao: number;
    }>;
    descarte_por_estado?: Array<{
        estado_code: number;
        estado_label: string;
        tons: number;
        percentual: number;
    }>;
}

interface LinhaOption {
    id: number;
    nome: string;
    codigo: string;
}

const WasteAnalysisDashboard: React.FC = () => {
    const [linhasDisponiveis, setLinhasDisponiveis] = useState<LinhaOption[]>([]);
    const [linhasSelecionadas, setLinhasSelecionadas] = useState<string[]>(['todas']);
    const [periodo, setPeriodo] = useState<string>('TURNO');
    const [dateRange, setDateRange] = useState<{ from: Date; to: Date }>({
        from: subDays(new Date(), 7),
        to: new Date()
    });
    const [data, setData] = useState<WasteData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [autoRefresh, setAutoRefresh] = useState(true);

    // Carregar linhas disponíveis
    useEffect(() => {
        axios.get(`${DJANGO_API}/descartes/linhas/`)
            .then(res => setLinhasDisponiveis(res.data))
            .catch(err => console.error('Erro ao carregar linhas:', err));
    }, []);

    // Fetch dados
    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams();
            params.append('periodo', periodo);

            if (linhasSelecionadas.includes('todas') || linhasSelecionadas.length === 0) {
                params.append('linhas', 'todas');
            } else {
                params.append('linhas', linhasSelecionadas.join(','));
            }

            if (periodo === 'CUSTOM') {
                params.append('data_inicio', dateRange.from.toISOString());
                params.append('data_fim', dateRange.to.toISOString());
            }

            const res = await axios.get(`${DJANGO_API}/descartes/resumo/?${params.toString()}`);
            setData(res.data);
        } catch (err: any) {
            console.error('Erro:', err);
            setError(err.response?.data?.error || 'Erro ao carregar dados');
        } finally {
            setLoading(false);
        }
    }, [periodo, linhasSelecionadas, dateRange]);

    // Auto-refresh a cada 30s
    useEffect(() => {
        fetchData();
        if (autoRefresh && (periodo === 'TURNO' || periodo === 'DIA')) {
            const interval = setInterval(fetchData, 30000);
            return () => clearInterval(interval);
        }
    }, [fetchData, autoRefresh, periodo]);

    const toggleLinha = (codigo: string) => {
        if (codigo === 'todas') {
            setLinhasSelecionadas(['todas']);
        } else {
            setLinhasSelecionadas(prev => {
                const withoutTodas = prev.filter(c => c !== 'todas');
                if (withoutTodas.includes(codigo)) {
                    const next = withoutTodas.filter(c => c !== codigo);
                    return next.length === 0 ? ['todas'] : next;
                } else {
                    return [...withoutTodas, codigo];
                }
            });
        }
    };

    const exportCSV = () => {
        if (!data) return;
        let csv = "Linha,Descarte (tons),Descarte (%),Produção (tons),Unidades Ruins\n";
        data.por_linha.forEach(l => {
            csv += `${l.linha},${l.descarte_tons},${l.descarte_percentual},${l.producao_tons},${l.unidades_ruins}\n`;
        });
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `descartes_${periodo}_${format(new Date(), 'yyyy-MM-dd')}.csv`;
        a.click();
    };

    // Cores para estados
    const getEstadoColor = (label: string) => {
        const lower = label.toLowerCase();
        if (lower.includes('produzindo')) return '#22c55e'; // Green
        if (lower.includes('parado')) return '#ef4444'; // Red
        if (lower.includes('manutenção') || lower.includes('manutencao')) return '#8b5cf6'; // Purple
        if (lower.includes('aguardando') || lower.includes('block')) return '#f97316'; // Orange
        if (lower.includes('offline')) return '#64748b'; // Slate
        return '#94a3b8'; // Default Gray
    };

    return (
        <div className="w-full h-full p-4 bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900 overflow-auto">
            {/* Header */}
            <div className="flex flex-wrap justify-between items-center mb-6 gap-4">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2 text-slate-800 dark:text-white">
                        <Trash2 className="h-7 w-7 text-red-500" />
                        Análise de Descartes
                    </h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                        {data?.periodo_label || 'Selecione um período'}
                    </p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                    {/* Seletor de Linhas */}
                    <Popover>
                        <PopoverTrigger asChild>
                            <Button variant="outline" className="w-[200px] justify-between">
                                <span className="truncate">
                                    {linhasSelecionadas.includes('todas')
                                        ? 'Todas as Linhas'
                                        : `${linhasSelecionadas.length} linha(s)`
                                    }
                                </span>
                                <ChevronDown className="h-4 w-4 ml-2" />
                            </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-[250px] p-2">
                            <ScrollArea className="h-[200px]">
                                <div
                                    className="flex items-center gap-2 p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded cursor-pointer"
                                    onClick={() => toggleLinha('todas')}
                                >
                                    <Checkbox checked={linhasSelecionadas.includes('todas')} />
                                    <span className="font-medium">🏭 Todas as Linhas</span>
                                </div>
                                <div className="border-t my-2" />
                                {linhasDisponiveis.map(l => (
                                    <div
                                        key={l.codigo}
                                        className="flex items-center gap-2 p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded cursor-pointer"
                                        onClick={() => toggleLinha(l.codigo)}
                                    >
                                        <Checkbox checked={linhasSelecionadas.includes(l.codigo)} />
                                        <span>{l.nome}</span>
                                    </div>
                                ))}
                            </ScrollArea>
                        </PopoverContent>
                    </Popover>

                    {/* Seletor de Período */}
                    <Select value={periodo} onValueChange={setPeriodo}>
                        <SelectTrigger className="w-[150px]">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="TURNO">Turno Atual</SelectItem>
                            <SelectItem value="DIA">Hoje</SelectItem>
                            <SelectItem value="SEMANA">Esta Semana</SelectItem>
                            <SelectItem value="MES">Este Mês</SelectItem>
                            <SelectItem value="ANO">Este Ano</SelectItem>
                            <SelectItem value="CUSTOM">Personalizado</SelectItem>
                        </SelectContent>
                    </Select>

                    {/* Date Picker para período customizado */}
                    {periodo === 'CUSTOM' && (
                        <Popover>
                            <PopoverTrigger asChild>
                                <Button variant="outline" className="gap-2">
                                    <CalendarIcon className="h-4 w-4" />
                                    {format(dateRange.from, 'dd/MM')} - {format(dateRange.to, 'dd/MM')}
                                </Button>
                            </PopoverTrigger>
                            <PopoverContent className="w-auto p-0" align="end">
                                <Calendar
                                    mode="range"
                                    selected={{ from: dateRange.from, to: dateRange.to }}
                                    onSelect={(range) => range && setDateRange({ from: range.from || new Date(), to: range.to || new Date() })}
                                    locale={ptBR}
                                />
                            </PopoverContent>
                        </Popover>
                    )}

                    <Button onClick={fetchData} variant="default" size="sm" disabled={loading}>
                        <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                        Atualizar
                    </Button>

                    <Button onClick={exportCSV} variant="outline" size="sm" disabled={!data}>
                        <Download className="h-4 w-4 mr-2" />
                        CSV
                    </Button>
                </div>
            </div>

            {error && (
                <div className="bg-red-100 text-red-700 p-4 rounded-lg mb-4 flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5" />
                    {error}
                </div>
            )}

            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <Card className="bg-gradient-to-br from-red-500 to-red-600 text-white border-0 shadow-lg">
                    <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-red-100 text-sm font-medium">Descarte Total</p>
                                <p className="text-3xl font-bold">{data?.consolidado.descarte_tons.toFixed(3) || '0.000'} t</p>
                                <p className="text-red-200 text-xs mt-1">{data?.consolidado.total_unidades.toLocaleString() || 0} unidades</p>
                            </div>
                            <Trash2 className="h-12 w-12 text-red-300 opacity-50" />
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-gradient-to-br from-orange-500 to-amber-500 text-white border-0 shadow-lg">
                    <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-orange-100 text-sm font-medium">Percentual</p>
                                <p className="text-3xl font-bold">{data?.consolidado.descarte_percentual.toFixed(2) || '0.00'}%</p>
                                <p className="text-orange-200 text-xs mt-1">sobre produção total</p>
                            </div>
                            <TrendingDown className="h-12 w-12 text-orange-300 opacity-50" />
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-gradient-to-br from-emerald-500 to-green-600 text-white border-0 shadow-lg">
                    <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-emerald-100 text-sm font-medium">Produção Total</p>
                                <p className="text-3xl font-bold">{data?.consolidado.producao_tons.toFixed(2) || '0.00'} t</p>
                                <p className="text-emerald-200 text-xs mt-1">{data?.por_linha?.length || 0} linha(s)</p>
                            </div>
                            <Factory className="h-12 w-12 text-emerald-300 opacity-50" />
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-gradient-to-br from-rose-500 to-pink-600 text-white border-0 shadow-lg">
                    <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-rose-100 text-sm font-medium">Maior Descarte</p>
                                <p className="text-xl font-bold truncate">{data?.linha_maior_descarte?.linha || 'N/A'}</p>
                                <p className="text-rose-200 text-xs mt-1">
                                    {data?.linha_maior_descarte?.descarte_percentual.toFixed(2) || '0.00'}%
                                    ({data?.linha_maior_descarte?.descarte_tons.toFixed(3) || '0.000'} t)
                                </p>
                            </div>
                            <AlertTriangle className="h-12 w-12 text-rose-300 opacity-50" />
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Gráficos */}
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6 mb-6">
                {/* Comparação por Linha */}
                <Card className="shadow-lg lg:col-span-2 xl:col-span-1">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <BarChart3 className="h-5 w-5 text-blue-500" />
                            Descarte por Linha
                        </CardTitle>
                        <CardDescription>Comparação entre linhas selecionadas</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {data?.por_linha && data.por_linha.length > 0 ? (
                            <Plot
                                data={[
                                    {
                                        x: data.por_linha.map(l => l.linha),
                                        y: data.por_linha.map(l => l.descarte_tons),
                                        type: 'bar',
                                        name: 'Descarte (tons)',
                                        marker: { color: 'rgba(239, 68, 68, 0.8)' },
                                        text: data.por_linha.map(l => `${l.descarte_percentual.toFixed(2)}%`),
                                        textposition: 'outside'
                                    }
                                ]}
                                layout={{
                                    autosize: true,
                                    height: 300,
                                    margin: { l: 50, r: 20, t: 30, b: 80 },
                                    xaxis: { tickangle: -45 },
                                    yaxis: { title: 'Toneladas' },
                                    showlegend: false
                                }}
                                useResizeHandler
                                className="w-full"
                            />
                        ) : (
                            <div className="h-[300px] flex items-center justify-center text-slate-400">
                                Sem dados disponíveis
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Top Equipamentos */}
                <Card className="shadow-lg">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <PieChart className="h-5 w-5 text-purple-500" />
                            Top Geradores de Refugo
                        </CardTitle>
                        <CardDescription>Equipamentos com maior descarte</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {data?.top_equipamentos && data.top_equipamentos.length > 0 ? (
                            <Plot
                                data={[
                                    {
                                        labels: data.top_equipamentos.map(e => `${e.equipamento} (${e.linha})`),
                                        values: data.top_equipamentos.map(e => e.tons),
                                        type: 'pie',
                                        hole: 0.4,
                                        textinfo: 'percent',
                                        textposition: 'outside',
                                        marker: {
                                            colors: [
                                                '#ef4444', '#f97316', '#eab308', '#22c55e', '#14b8a6',
                                                '#3b82f6', '#8b5cf6', '#ec4899', '#64748b', '#0ea5e9'
                                            ]
                                        }
                                    }
                                ]}
                                layout={{
                                    autosize: true,
                                    height: 300,
                                    margin: { l: 20, r: 20, t: 30, b: 30 },
                                    showlegend: true,
                                    legend: { orientation: 'h', y: -0.2 }
                                }}
                                useResizeHandler
                                className="w-full"
                            />
                        ) : (
                            <div className="h-[300px] flex items-center justify-center text-slate-400">
                                Sem dados disponíveis
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Descarte por Estado (NOVO) */}
                <Card className="shadow-lg">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <PieChart className="h-5 w-5 text-orange-500" />
                            Descarte por Estado
                        </CardTitle>
                        <CardDescription>Associação com estado da máquina</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {data?.descarte_por_estado && data.descarte_por_estado.length > 0 ? (
                            <Plot
                                data={[
                                    {
                                        labels: data.descarte_por_estado.map(d => d.estado_label),
                                        values: data.descarte_por_estado.map(d => d.tons),
                                        type: 'pie',
                                        hole: 0.6,
                                        textinfo: 'percent',
                                        textposition: 'outside',
                                        marker: {
                                            colors: data.descarte_por_estado.map(d => getEstadoColor(d.estado_label))
                                        }
                                    }
                                ]}
                                layout={{
                                    autosize: true,
                                    height: 300,
                                    margin: { l: 20, r: 20, t: 30, b: 30 },
                                    showlegend: true,
                                    legend: { orientation: 'h', y: -0.2 }
                                }}
                                useResizeHandler
                                className="w-full"
                            />
                        ) : (
                            <div className="h-[300px] flex items-center justify-center text-slate-400">
                                Sem dados disponíveis
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Tabela Detalhada */}
            <Card className="shadow-lg">
                <CardHeader>
                    <CardTitle>Detalhamento por Linha</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b bg-slate-50 dark:bg-slate-800">
                                    <th className="text-left p-3 font-semibold">Linha</th>
                                    <th className="text-right p-3 font-semibold">Produção (t)</th>
                                    <th className="text-right p-3 font-semibold">Descarte (t)</th>
                                    <th className="text-right p-3 font-semibold">Descarte (%)</th>
                                    <th className="text-right p-3 font-semibold">Unidades</th>
                                    <th className="text-center p-3 font-semibold">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data?.por_linha?.map((linha, idx) => (
                                    <tr key={linha.codigo} className={`border-b ${idx % 2 === 0 ? 'bg-white dark:bg-slate-900' : 'bg-slate-50/50 dark:bg-slate-800/50'}`}>
                                        <td className="p-3 font-medium">{linha.linha}</td>
                                        <td className="p-3 text-right">{linha.producao_tons.toFixed(2)}</td>
                                        <td className="p-3 text-right text-red-600 font-semibold">{linha.descarte_tons.toFixed(4)}</td>
                                        <td className="p-3 text-right">
                                            <Badge variant={linha.descarte_percentual > 1 ? 'destructive' : linha.descarte_percentual > 0.5 ? 'secondary' : 'outline'}>
                                                {linha.descarte_percentual.toFixed(2)}%
                                            </Badge>
                                        </td>
                                        <td className="p-3 text-right">{linha.unidades_ruins.toLocaleString()}</td>
                                        <td className="p-3 text-center">
                                            {linha.descarte_percentual > 1 ? (
                                                <span className="text-red-500">⚠️ Alto</span>
                                            ) : linha.descarte_percentual > 0.5 ? (
                                                <span className="text-yellow-500">⚡ Atenção</span>
                                            ) : (
                                                <span className="text-green-500">✅ OK</span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                                {(!data?.por_linha || data.por_linha.length === 0) && (
                                    <tr>
                                        <td colSpan={6} className="p-8 text-center text-slate-400">
                                            Nenhum dado disponível para o período selecionado
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                            {data?.por_linha && data.por_linha.length > 0 && (
                                <tfoot>
                                    <tr className="bg-slate-100 dark:bg-slate-800 font-bold">
                                        <td className="p-3">TOTAL</td>
                                        <td className="p-3 text-right">{data.consolidado.producao_tons.toFixed(2)}</td>
                                        <td className="p-3 text-right text-red-600">{data.consolidado.descarte_tons.toFixed(4)}</td>
                                        <td className="p-3 text-right">{data.consolidado.descarte_percentual.toFixed(2)}%</td>
                                        <td className="p-3 text-right">{data.consolidado.total_unidades.toLocaleString()}</td>
                                        <td className="p-3"></td>
                                    </tr>
                                </tfoot>
                            )}
                        </table>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

export default WasteAnalysisDashboard;
