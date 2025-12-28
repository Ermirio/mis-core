import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import MainLayout from '@/components/layout/MainLayout';
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import {
    CalendarIcon, Loader2, RefreshCw,
    BarChart2, TrendingUp, Activity, ScatterChart as ScatterIcon, Grid,
    Settings, Filter, Download, ChevronsRight, Info, Plus, Trash2, Edit
} from "lucide-react";
import { format, subHours } from "date-fns";
import { ptBR } from "date-fns/locale";

const DJANGO_API = import.meta.env.VITE_DJANGO_API_URL;
const FLASK_API = import.meta.env.VITE_FLASK_API_URL;

interface Tag {
    id: number;
    nome: string; // Sensor name
    tag_influxdb: string; // Was node_id? No, Sensor has tag_influxdb
    equipamento_nome: string;
    equipamento_code: string;
    lsl?: number;
    usl?: number;
    nominal?: number;
}

interface Equipamento {
    id: number;
    nome: string;
    codigo: string;
    sensores: any[]; // Changed from tags_coleta
}

interface Linha {
    id: number;
    nome: string;
    codigo: string;
    equipamentos: Equipamento[];
}

interface TrendChart {
    id: number;
    name: string; // Added name
    selectedAliases: string[];
}

const LineAnalytics: React.FC = () => {
    const [linhas, setLinhas] = useState<Linha[]>([]);
    const [selectedLinhaId, setSelectedLinhaId] = useState<string>('');
    const [selectedTags, setSelectedTags] = useState<Tag[]>([]);

    // Time Range
    const [date, setDate] = useState<Date | undefined>(new Date());
    const [hoursBack, setHoursBack] = useState<string>('8'); // Default 8h

    // Data
    const [statsData, setStatsData] = useState<any[]>([]);
    const [correlationData, setCorrelationData] = useState<any>(null);
    const [timeseriesData, setTimeseriesData] = useState<any>(null); // New state
    const [trendCharts, setTrendCharts] = useState<TrendChart[]>([]); // Multi-chart state
    const [scatterX, setScatterX] = useState<string>('');
    const [scatterY, setScatterY] = useState<string>('');
    const [activeTab, setActiveTab] = useState<string>('stats');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Fetch Structure
    useEffect(() => {
        axios.get(`${DJANGO_API}/linhas/`)
            .then(res => setLinhas(res.data.results || res.data))
            .catch(err => console.error("Erro ao buscar linhas:", err));
    }, []);

    const handleRunAnalysis = async (mode: 'stats' | 'correlation' | 'timeseries') => {
        if (selectedTags.length === 0) {
            setError("Selecione pelo menos uma variável.");
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const end = new Date(); // Now
            const start = subHours(end, parseInt(hoursBack));

            const payload = {
                variables: selectedTags.map(t => ({
                    tag_influx: t.tag_influxdb, // Use correct field
                    equipamento_code: t.equipamento_code,
                    alias: `${t.equipamento_nome} - ${t.nome}`,
                    lsl: t.lsl,
                    usl: t.usl,
                    nominal: t.nominal
                })),
                start_time: start.toISOString(),
                end_time: end.toISOString()
            };

            let endpoint = '';
            if (mode === 'stats') endpoint = '/analyze/stats';
            else if (mode === 'correlation') endpoint = '/analyze/correlation';
            else endpoint = '/analyze/timeseries';

            const res = await axios.post(`${FLASK_API}${endpoint}`, payload);

            if (res.data && Array.isArray(res.data) && res.data.length > 0) {
                // Check if all are errors
                const allErrors = res.data.every((r: any) => r.error === 'No data found' || r.error === 'Empty data');
                if (allErrors) {
                    setError("Não há dados registrados para este período. Verifique se o equipamento estava operando (Status/Conexão).");
                    setLoading(false);
                    return;
                }
            }

            if (mode === 'stats') {
                setStatsData(res.data);
                setActiveTab('stats');
            } else if (mode === 'correlation') {
                console.log("Correlation Data:", res.data);
                setCorrelationData(res.data);
                setActiveTab('correlation');
            } else {
                console.log("Timeseries Data:", res.data);
                setTimeseriesData(res.data);
                // Initialize one chart with all variables
                setTrendCharts([{
                    id: Date.now(),
                    name: 'Painel Geral',
                    selectedAliases: Object.keys(res.data)
                }]);
                setActiveTab('trend');
            }

        } catch (err: any) {
            console.error("Erro na análise:", err);
            setError("Erro ao executar análise. Verifique se o servidor de banco de dados está online.");
        } finally {
            setLoading(false);
        }
    };

    // Helper to get all tags of selected line
    const getAvailableTags = () => {
        if (!selectedLinhaId) return [];
        const linha = linhas.find(l => l.id.toString() === selectedLinhaId);
        if (!linha) return [];

        // Flatten tags
        let tags: any[] = [];

        // Inject Standard Metrics for each equipment
        linha.equipamentos.forEach(eq => {
            // Standard Metrics
            const standardMetrics = [
                { nome: 'Velocidade', tag: 'velocidade_atual' },
                { nome: 'OEE', tag: 'oee' },
                { nome: 'Produção', tag: 'contagem_saida' },
                { nome: 'Descarte', tag: 'descarte' }
            ];

            standardMetrics.forEach(m => {
                tags.push({
                    id: `std-${eq.codigo}-${m.tag}`, // Unique ID
                    nome: m.nome,
                    tag_influxdb: m.tag,
                    equipamento_nome: eq.nome,
                    equipamento_code: eq.codigo,
                    lsl: undefined,
                    usl: undefined,
                    nominal: undefined
                });
            });

            // Dynamic Sensors from Django
            if (eq.sensores) {
                eq.sensores.forEach((s: any) => {
                    tags.push({
                        id: s.id,
                        nome: s.nome,
                        tag_influxdb: s.tag_influxdb,
                        equipamento_nome: eq.nome,
                        equipamento_code: eq.codigo,
                        lsl: s.lsl,
                        usl: s.usl,
                        nominal: s.nominal
                    });
                });
            }
        });
        return tags;
    };

    const toggleTag = (tag: any) => {
        if (selectedTags.find(t => t.id === tag.id)) {
            setSelectedTags(selectedTags.filter(t => t.id !== tag.id));
        } else {
            setSelectedTags([...selectedTags, tag]);
        }
    };

    const downloadCSV = () => {
        // Basic CSV Export of Timeseries Data
        if (!timeseriesData) return;

        // Find all timestamps across variables (union)
        // Actually, timeseriesData keys are Variable Aliases.
        // Each value has timestamps/values.
        // For simplicity, let's export the FIRST variable's timestamps if aligned?
        // Or just export JSON for now? User asked for CSV.

        let csvContent = "data:text/csv;charset=utf-8,";
        csvContent += "Time,Variable,Value\n";

        Object.entries(timeseriesData).forEach(([alias, data]: [string, any]) => {
            data.timestamps.forEach((t: string, i: number) => {
                csvContent += `${t},${alias},${data.values[i]}\n`;
            });
        });

        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", "analise_dados.csv");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    // Multi-Chart Handlers
    const addChart = () => {
        setTrendCharts([...trendCharts, {
            id: Date.now(),
            name: `Painel ${trendCharts.length + 1}`,
            selectedAliases: []
        }]);
    };

    const removeChart = (id: number) => {
        setTrendCharts(trendCharts.filter(c => c.id !== id));
    };

    const updateChartName = (id: number, newName: string) => {
        setTrendCharts(trendCharts.map(c => c.id === id ? { ...c, name: newName } : c));
    };

    const toggleChartVariable = (chartId: number, alias: string) => {
        setTrendCharts(trendCharts.map(c => {
            if (c.id === chartId) {
                const isSelected = c.selectedAliases.includes(alias);
                return {
                    ...c,
                    selectedAliases: isSelected
                        ? c.selectedAliases.filter(a => a !== alias)
                        : [...c.selectedAliases, alias]
                };
            }
            return c;
        }));
    };

    return (
        <div className="w-full h-full p-2 bg-slate-50/50 dark:bg-slate-950/50">
            <div className="flex h-[calc(100vh-80px)] gap-2">
                {/* Sidebar Filter */}
                <Card className="w-80 flex flex-col shadow-lg border-l-4 border-l-blue-600 dark:border-l-blue-500 rounded-lg">
                    <CardHeader className="pb-2">
                        <CardTitle className="flex items-center gap-2 text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-cyan-500">
                            <Settings className="h-6 w-6 text-blue-600" />
                            Configuração
                        </CardTitle>
                        <CardDescription>Parâmetros de Análise</CardDescription>
                    </CardHeader>
                    <CardContent className="flex-1 flex flex-col gap-4 overflow-hidden pt-2">
                        <div className="space-y-1">
                            <Label className="flex items-center gap-2 text-gray-700 dark:text-gray-200">
                                <Filter className="h-4 w-4" /> Linha
                            </Label>
                            <Select value={selectedLinhaId} onValueChange={setSelectedLinhaId}>
                                <SelectTrigger>
                                    <SelectValue placeholder="Selecione..." />
                                </SelectTrigger>
                                <SelectContent>
                                    {linhas.map(l => (
                                        <SelectItem key={l.id} value={l.id.toString()}>{l.nome}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div>
                            <Label>Período (Últimas Horas)</Label>
                            <Select value={hoursBack} onValueChange={setHoursBack}>
                                <SelectTrigger><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="1">1 Hora</SelectItem>
                                    <SelectItem value="4">4 Horas</SelectItem>
                                    <SelectItem value="8">8 Horas</SelectItem>
                                    <SelectItem value="24">24 Horas</SelectItem>
                                    <SelectItem value="168">7 Dias</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="flex-1 overflow-hidden flex flex-col">
                            <Label className="mb-2 flex items-center gap-2 text-gray-700 dark:text-gray-200">
                                <Activity className="h-4 w-4" /> Variáveis
                            </Label>
                            <ScrollArea className="flex-1 border rounded-md p-2 bg-slate-50 dark:bg-slate-900/50">
                                {getAvailableTags().map(tag => (
                                    <div
                                        key={tag.id}
                                        className="flex items-center space-x-2 mb-2 p-2 rounded hover:bg-white dark:hover:bg-slate-800 transition-colors cursor-pointer border border-transparent hover:border-slate-200 dark:hover:border-slate-700"
                                    >
                                        <Checkbox
                                            id={`tag-${tag.id}`}
                                            checked={!!selectedTags.find(t => t.id === tag.id)}
                                            onCheckedChange={() => toggleTag(tag)}
                                        />
                                        <label htmlFor={`tag-${tag.id}`} className="text-sm cursor-pointer flex-1 font-medium text-slate-700 dark:text-slate-300">
                                            {tag.equipamento_nome} - {tag.nome}
                                        </label>
                                    </div>
                                ))}
                                {selectedLinhaId && getAvailableTags().length === 0 && (
                                    <p className="text-sm text-gray-500">Nenhuma tag configurada.</p>
                                )}
                            </ScrollArea>
                        </div>
                    </CardContent>
                </Card>

                {/* Main Content */}
                <div className="flex-1 overflow-auto">
                    <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full h-full flex flex-col">
                        <div className="flex justify-between items-center mb-4 bg-white dark:bg-slate-900 p-2 rounded-lg shadow-sm border">
                            <TabsList className="grid grid-cols-5 gap-2 w-[600px]">
                                <TabsTrigger value="stats" className="flex items-center gap-2 data-[state=active]:bg-blue-100 dark:data-[state=active]:bg-blue-900/40 data-[state=active]:text-blue-700 dark:data-[state=active]:text-blue-300 transition-all">
                                    <BarChart2 className="h-4 w-4" /> Stats
                                </TabsTrigger>
                                <TabsTrigger value="trend" className="flex items-center gap-2 data-[state=active]:bg-emerald-100 dark:data-[state=active]:bg-emerald-900/40 data-[state=active]:text-emerald-700 dark:data-[state=active]:text-emerald-300 transition-all">
                                    <TrendingUp className="h-4 w-4" /> Tendência
                                </TabsTrigger>
                                <TabsTrigger value="spc" className="flex items-center gap-2 data-[state=active]:bg-amber-100 dark:data-[state=active]:bg-amber-900/40 data-[state=active]:text-amber-700 dark:data-[state=active]:text-amber-300 transition-all">
                                    <Activity className="h-4 w-4" /> SPC
                                </TabsTrigger>
                                <TabsTrigger value="scatter" className="flex items-center gap-2 data-[state=active]:bg-purple-100 dark:data-[state=active]:bg-purple-900/40 data-[state=active]:text-purple-700 dark:data-[state=active]:text-purple-300 transition-all">
                                    <ScatterIcon className="h-4 w-4" /> Dispersão
                                </TabsTrigger>
                                <TabsTrigger value="correlation" className="flex items-center gap-2 data-[state=active]:bg-pink-100 dark:data-[state=active]:bg-pink-900/40 data-[state=active]:text-pink-700 dark:data-[state=active]:text-pink-300 transition-all">
                                    <Grid className="h-4 w-4" /> Correlação
                                </TabsTrigger>
                            </TabsList>
                            <div className="flex gap-2">
                                <Button onClick={() => handleRunAnalysis('stats')} variant="secondary" size="sm">Stats</Button>
                                <Button onClick={() => handleRunAnalysis('timeseries')} variant="default" size="sm">Gerar Gráficos</Button>
                                <Button onClick={() => handleRunAnalysis('correlation')} variant="outline" size="sm">Correlação</Button>
                                {timeseriesData && (
                                    <Button onClick={downloadCSV} variant="ghost" size="sm">Exportar CSV</Button>
                                )}
                            </div>
                        </div>

                        {error && <div className="p-4 bg-red-100 text-red-700 rounded mb-4">{error}</div>}

                        {/* TABS CONTENT */}
                        <TabsContent value="stats" className="space-y-4">
                            {statsData.map((res, idx) => (
                                <Card key={idx}>
                                    <CardHeader>
                                        <CardTitle>{res.variable}</CardTitle>
                                        <div className="flex gap-4 text-sm text-gray-500">
                                            <span>Média: {res.stats.mean.toFixed(2)}</span>
                                            <span>Std: {res.stats.std.toFixed(2)}</span>
                                            {res.stats.cpk !== null && (
                                                <span className={res.stats.cpk < 1.33 ? 'text-red-500 font-bold' : 'text-green-600 font-bold'}>
                                                    Cpk: {res.stats.cpk.toFixed(2)}
                                                </span>
                                            )}
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <Plot
                                            data={[
                                                {
                                                    x: res.histogram.bins, // Note: bins length is N+1 usually, plot needs checking
                                                    y: res.histogram.counts,
                                                    type: 'bar',
                                                    name: 'Distribuição'
                                                }
                                            ]}
                                            layout={{
                                                width: undefined,
                                                height: 300,
                                                autosize: true,
                                                title: 'Histograma'
                                            }}
                                            useResizeHandler={true}
                                            className="w-full"
                                        />
                                    </CardContent>
                                </Card>
                            ))}
                            {statsData.length === 0 && !loading && (
                                <div className="flex items-center justify-center h-64 border-2 border-dashed rounded-lg text-gray-400">
                                    Selecione variáveis e clique em Analisar Estatísticas
                                </div>
                            )}
                        </TabsContent>

                        <TabsContent value="correlation">
                            {correlationData?.correlation_matrix && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Matriz de Correlação</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <Plot
                                            data={[
                                                {
                                                    z: correlationData.correlation_matrix.values,
                                                    x: correlationData.correlation_matrix.columns,
                                                    y: correlationData.correlation_matrix.columns,
                                                    type: 'heatmap',
                                                    colorscale: 'RdBu',
                                                    zmin: -1,
                                                    zmax: 1
                                                }
                                            ]}
                                            layout={{
                                                width: undefined,
                                                height: 600,
                                                title: 'Heatmap de Correlação (Pearson)',
                                                autosize: true
                                            }}
                                            useResizeHandler={true}
                                            className="w-full"
                                        />
                                    </CardContent>
                                </Card>
                            )}
                            {!correlationData && !loading && (
                                <div className="flex items-center justify-center h-64 border-2 border-dashed rounded-lg text-gray-400">
                                    Clique em Analisar Correlação para gerar a matriz
                                </div>
                            )}
                        </TabsContent>

                        {/* TREND TAB */}
                        <TabsContent value="trend">
                            {timeseriesData ? (
                                <div className="space-y-4">
                                    <div className="flex justify-end">
                                        <Button onClick={addChart} variant="outline" size="sm" className="gap-2">
                                            <Plus className="h-4 w-4" /> Adicionar Gráfico
                                        </Button>
                                    </div>

                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {trendCharts.map((chart, index) => (
                                            <Card key={chart.id} className="col-span-1 md:col-span-2 lg:col-span-1 shadow-md hover:shadow-lg transition-all border-l-4 border-l-emerald-500">
                                                <CardHeader className="flex flex-row items-center justify-between pb-2">
                                                    <CardTitle className="text-sm font-medium">{chart.name}</CardTitle>
                                                    <div className="flex items-center gap-2">
                                                        <Popover>
                                                            <PopoverTrigger asChild>
                                                                <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                                                    <Settings className="h-4 w-4" />
                                                                </Button>
                                                            </PopoverTrigger>
                                                            <PopoverContent className="w-64 p-2" align="end">
                                                                <div className="flex flex-col gap-2 mb-2">
                                                                    <Label htmlFor={`name-${chart.id}`} className="text-xs font-semibold text-gray-500">Nome do Painel</Label>
                                                                    <Input
                                                                        id={`name-${chart.id}`}
                                                                        value={chart.name}
                                                                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateChartName(chart.id, e.target.value)}
                                                                        className="h-7 text-sm"
                                                                    />
                                                                </div>
                                                                <div className="mb-2 font-medium text-xs text-gray-500 mt-2">Variáveis neste gráfico</div>
                                                                <ScrollArea className="h-40 border rounded bg-slate-50 dark:bg-slate-900/50">
                                                                    {Object.keys(timeseriesData).map(alias => (
                                                                        <div key={alias} className="flex items-center space-x-2 py-1 px-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded cursor-pointer" onClick={() => toggleChartVariable(chart.id, alias)}>
                                                                            <Checkbox
                                                                                checked={chart.selectedAliases.includes(alias)}
                                                                                onCheckedChange={() => toggleChartVariable(chart.id, alias)}
                                                                            />
                                                                            <span className="text-xs truncate" title={alias}>{alias}</span>
                                                                        </div>
                                                                    ))}
                                                                </ScrollArea>
                                                            </PopoverContent>
                                                        </Popover>
                                                        {trendCharts.length > 1 && (
                                                            <Button onClick={() => removeChart(chart.id)} variant="ghost" size="sm" className="h-8 w-8 p-0 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20">
                                                                <Trash2 className="h-4 w-4" />
                                                            </Button>
                                                        )}
                                                    </div>
                                                </CardHeader>
                                                <CardContent>
                                                    {chart.selectedAliases.length > 0 ? (
                                                        <Plot
                                                            data={chart.selectedAliases.map(alias => ({
                                                                x: timeseriesData[alias]?.timestamps || [],
                                                                y: timeseriesData[alias]?.values || [],
                                                                type: 'scatter',
                                                                mode: 'lines',
                                                                name: alias
                                                            }))}
                                                            layout={{
                                                                title: undefined,
                                                                autosize: true,
                                                                height: 350,
                                                                margin: { l: 40, r: 20, t: 20, b: 40 },
                                                                showlegend: true,
                                                                legend: { orientation: 'h', y: -0.2 }
                                                            }}
                                                            useResizeHandler={true}
                                                            className="w-full"
                                                        />
                                                    ) : (
                                                        <div className="h-[350px] flex flex-col items-center justify-center border-2 border-dashed rounded text-gray-400 gap-2">
                                                            <BarChart2 className="h-8 w-8 opacity-50" />
                                                            <span className="text-sm">Selecione variáveis nas configurações</span>
                                                        </div>
                                                    )}
                                                </CardContent>
                                            </Card>
                                        ))}
                                    </div>
                                </div>
                            ) : <div className="text-center p-8 text-gray-500">Clique em "Gerar Gráficos" para visualizar.</div>}
                        </TabsContent>

                        {/* SPC TAB */}
                        <TabsContent value="spc">
                            {timeseriesData ? (
                                <div className="space-y-4">
                                    {Object.entries(timeseriesData).map(([alias, d]: [string, any]) => (
                                        <Card key={alias}>
                                            <CardHeader><CardTitle>SPC - {alias}</CardTitle></CardHeader>
                                            <CardContent>
                                                <Plot
                                                    data={[
                                                        { x: d.timestamps, y: d.values, type: 'scatter', mode: 'lines+markers', name: 'Valor Real' },
                                                        { x: d.timestamps, y: Array(d.timestamps.length).fill(d.stats.mean), type: 'scatter', mode: 'lines', name: 'Média', line: { color: 'green', dash: 'dash' } },
                                                        { x: d.timestamps, y: Array(d.timestamps.length).fill(d.stats.ucl), type: 'scatter', mode: 'lines', name: 'UCL (+3σ)', line: { color: 'red' } },
                                                        { x: d.timestamps, y: Array(d.timestamps.length).fill(d.stats.lcl), type: 'scatter', mode: 'lines', name: 'LCL (-3σ)', line: { color: 'red' } },
                                                        // Plot LSL/USL if exist
                                                        ...(d.stats.usl ? [{ x: d.timestamps, y: Array(d.timestamps.length).fill(d.stats.usl), type: 'scatter' as const, mode: 'lines' as const, name: 'USL (Eng)', line: { color: 'orange', width: 3 } }] : []),
                                                        ...(d.stats.lsl ? [{ x: d.timestamps, y: Array(d.timestamps.length).fill(d.stats.lsl), type: 'scatter' as const, mode: 'lines' as const, name: 'LSL (Eng)', line: { color: 'orange', width: 3 } }] : [])
                                                    ]}
                                                    layout={{ title: `Carta de Controle: ${alias}`, autosize: true, height: 400 }}
                                                    useResizeHandler={true}
                                                    className="w-full"
                                                />
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            ) : <div className="text-center p-8 text-gray-500">Clique em "Gerar Gráficos" para visualizar.</div>}
                        </TabsContent>

                        {/* SCATTER TAB */}
                        <TabsContent value="scatter">
                            {timeseriesData ? (
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Dispersão X vs Y</CardTitle>
                                        <div className="flex gap-4">
                                            <div className="w-1/2">
                                                <Label>Eixo X</Label>
                                                <Select value={scatterX} onValueChange={setScatterX}>
                                                    <SelectTrigger><SelectValue placeholder="Selecione Variável X" /></SelectTrigger>
                                                    <SelectContent>
                                                        {Object.keys(timeseriesData).map(k => (
                                                            <SelectItem key={k} value={k}>{k}</SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="w-1/2">
                                                <Label>Eixo Y</Label>
                                                <Select value={scatterY} onValueChange={setScatterY}>
                                                    <SelectTrigger><SelectValue placeholder="Selecione Variável Y" /></SelectTrigger>
                                                    <SelectContent>
                                                        {Object.keys(timeseriesData).map(k => (
                                                            <SelectItem key={k} value={k}>{k}</SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        {scatterX && scatterY ? (
                                            <Plot
                                                data={[
                                                    {
                                                        x: timeseriesData[scatterX].values,
                                                        y: timeseriesData[scatterY].values,
                                                        mode: 'markers',
                                                        type: 'scatter',
                                                        marker: { color: 'blue', size: 8, opacity: 0.6 }
                                                    }
                                                ]}
                                                layout={{
                                                    title: `${scatterX} vs ${scatterY}`,
                                                    xaxis: { title: scatterX },
                                                    yaxis: { title: scatterY },
                                                    autosize: true,
                                                    height: 500
                                                }}
                                                useResizeHandler={true}
                                                className="w-full"
                                            />
                                        ) : <div className="p-8 text-center text-gray-500">Selecione as variáveis para os Eixos X e Y.</div>}
                                    </CardContent>
                                </Card>
                            ) : <div className="text-center p-8 text-gray-500">Clique em "Gerar Gráficos" para visualizar.</div>}
                        </TabsContent>

                    </Tabs>
                </div>
            </div>
        </div >
    );
};

export default LineAnalytics;
