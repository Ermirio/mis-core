import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
import axios from 'axios';
import { ProfileManager } from '@/components/Analytics/ProfileManager';
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
    Settings, Filter, Download, ChevronsRight, Info, Plus, Trash2, Edit,
    Box, Layers
} from "lucide-react";
import { format, subHours } from "date-fns";
import { ptBR } from "date-fns/locale";

import { DJANGO_API_URL as DJANGO_API, FLASK_API_URL as FLASK_API } from '@/config/api';

const ESTADO_VALUE_MAPPING: Record<number, { label: string; color: string }> = {
    1:   { label: 'Produzindo',              color: '#16a34a' },
    2:   { label: 'Aguard. Anterior',        color: '#06b6d4' },
    3:   { label: 'Seguinte Bloqueado',      color: '#f97316' },
    4:   { label: 'Falha / Parado',          color: '#dc2626' },
    5:   { label: 'Setup / Troca SKU',       color: '#a855f7' },
    6:   { label: 'Teste de Projeto',        color: '#0ea5e9' },
    7:   { label: 'Aguard. Manutenção',      color: '#78716c' },
    8:   { label: 'Em Manutenção',           color: '#991b1b' },
    9:   { label: 'Falta de Material',       color: '#d97706' },
    11:  { label: 'Partindo',               color: '#84cc16' },
    12:  { label: 'Aguard. Condições',      color: '#64748b' },
    13:  { label: 'Parando',               color: '#f59e0b' },
    999: { label: 'Offline',               color: '#6b7280' },
};

interface Tag {
    id: number;
    nome: string; // Sensor name
    tag_influxdb: string; // Was node_id? No, Sensor has tag_influxdb
    equipamento_nome: string;
    equipamento_code: string;
    linha_nome: string; // Nome da linha para alias legível
    lsl?: number;
    usl?: number;
    nominal?: number;
    isStandard?: boolean;
    isDiscrete?: boolean;           // ← NOVO: flag para variável discreta/categórica
    valueMapping?: Record<number, { label: string; color: string }>;  // ← NOVO: mapeamento valor→legenda
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

// ... (imports remain)
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";

// --- Componente isolado para a Matriz de Correlação ---
// Resolve problema de contexto JSX em closures/IIFEs dentro de componentes grandes
interface CorrMatrixProps {
    matrix: {
        columns: string[];
        values: number[][];
        p_values: number[][];
        method: string;
        n_points: number;
        resample_rule: string;
    };
    corrMinFilter: number;
    pvalToStars: (p: number) => string;
    timeseriesData: any;
    setScatterX: (v: string) => void;
    setScatterY: (v: string) => void;
    setActiveTab: (v: string) => void;
    handleRunAnalysis: (mode: 'stats' | 'correlation' | 'timeseries') => Promise<void>;
}

const CorrMatrixPlot = ({
    matrix, corrMinFilter, pvalToStars, timeseriesData,
    setScatterX, setScatterY, setActiveTab, handleRunAnalysis
}: CorrMatrixProps): React.ReactElement => {
    const { columns, values, p_values, method } = matrix;

    const textMatrix = values.map((row: number[], i: number) =>
        row.map((v: number, j: number) => {
            if (i === j) return '1.00';
            if (Math.abs(v) < corrMinFilter) return '';
            const stars = p_values ? pvalToStars(p_values[i][j]) : '';
            return `${(v * 100).toFixed(1)}%${stars}`;
        })
    );


    const hoverMatrix = values.map((row: number[], i: number) =>
        row.map((v: number, j: number) => {
            const p = p_values?.[i]?.[j];
            const pStr = (p !== undefined && i !== j)
                ? `<br>p-value: ${p < 0.0001 ? '<0.0001' : p.toFixed(4)}${pvalToStars(p) ? ` ${pvalToStars(p)}` : ' (ns)'}`
                : '';
            return `<b>${columns[j]}</b> x <b>${columns[i]}</b><br>r = ${v.toFixed(4)}${pStr}`;
        })
    );

    const handleClick = (data: any) => {
        const pt = data?.points?.[0];
        if (!pt) return;
        const xVar = pt.x as string;
        const yVar = pt.y as string;
        if (xVar === yVar) return;
        setScatterX(xVar);
        setScatterY(yVar);
        if (timeseriesData?.[xVar] && timeseriesData?.[yVar]) {
            setActiveTab('scatter');
        } else {
            handleRunAnalysis('timeseries').then(() => setActiveTab('scatter'));
        }
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle>
                    Matriz de Correlação — {method === 'spearman' ? 'Spearman' : 'Pearson'}
                </CardTitle>
                <CardDescription className="text-xs">
                    Clique numa célula para abrir o gráfico de dispersão do par. Células em branco estão abaixo do filtro mínimo.
                </CardDescription>
            </CardHeader>
            <CardContent>
                <Plot
                    data={[{
                        z: values,
                        x: columns,
                        y: columns,
                        type: 'heatmap',
                        colorscale: 'RdBu',
                        zmin: -1, zmax: 1,
                        text: textMatrix,
                        texttemplate: '%{text}',
                        textfont: { size: 11, color: 'black' },
                        hovertemplate: '%{customdata}<extra></extra>',
                        customdata: hoverMatrix,
                        xgap: 3,
                        ygap: 3,
                    } as any]}
                    layout={{
                        height: 600,
                        autosize: true,
                        title: { text: '' },
                        margin: { l: 160, r: 20, t: 20, b: 160 },
                        xaxis: { tickangle: -40 },
                        yaxis: { tickangle: 0 }
                    }}
                    useResizeHandler={true}
                    className="w-full"
                    onClick={handleClick}
                />
            </CardContent>
        </Card>
    );
};

// --- Componente isolado para Scatter com Trend Line ---
interface ScatterPlotProps {
    xKey: string;
    yKey: string;
    timeseriesData: any;
    calcLinearRegression: (x: number[], y: number[]) => { slope: number; intercept: number; xMin: number; xMax: number } | null;
}

const ScatterPlot = ({ xKey, yKey, timeseriesData, calcLinearRegression }: ScatterPlotProps): React.ReactElement => {
    const xVals: number[] = timeseriesData[xKey]?.values ?? [];
    const yVals: number[] = timeseriesData[yKey]?.values ?? [];
    const reg = calcLinearRegression(xVals, yVals);
    const n = xVals.length;
    const xMean = n ? xVals.reduce((a, b) => a + b, 0) / n : 0;
    const yMean = n ? yVals.reduce((a, b) => a + b, 0) / n : 0;
    const num = xVals.reduce((acc, xi, i) => acc + (xi - xMean) * (yVals[i] - yMean), 0);
    const den = Math.sqrt(
        xVals.reduce((acc, xi) => acc + (xi - xMean) ** 2, 0) *
        yVals.reduce((acc, yi) => acc + (yi - yMean) ** 2, 0)
    );
    const r = den === 0 ? 0 : num / den;
    const rLabel = r >= 0.7 ? 'Forte positiva' : r <= -0.7 ? 'Forte negativa' : Math.abs(r) >= 0.3 ? 'Moderada' : 'Fraca';
    const trendTraces: any[] = reg ? [{
        x: [reg.xMin, reg.xMax],
        y: [reg.slope * reg.xMin + reg.intercept, reg.slope * reg.xMax + reg.intercept],
        mode: 'lines',
        type: 'scatter',
        name: `Tendência (r=${r.toFixed(3)})`,
        line: { color: 'red', width: 2, dash: 'dash' }
    }] : [];
    return (
        <div>
            <div className="flex flex-wrap gap-3 mb-3 text-sm">
                <span className="bg-slate-100 px-3 py-1 rounded font-mono">r = {r.toFixed(4)}</span>
                <span className="bg-slate-100 px-3 py-1 rounded">{rLabel}</span>
                {reg && (
                    <span className="bg-slate-100 px-3 py-1 rounded font-mono text-xs">
                        y = {reg.slope.toFixed(4)}x + {reg.intercept.toFixed(4)}
                    </span>
                )}
                <span className="text-gray-400 text-xs self-center">n = {n} pontos</span>
            </div>
            <Plot
                data={[
                    {
                        x: xVals, y: yVals,
                        mode: 'markers', type: 'scatter', name: 'Dados',
                        marker: { color: 'rgba(59,130,246,0.5)', size: 7, line: { color: 'rgba(59,130,246,0.8)', width: 1 } }
                    },
                    ...trendTraces
                ]}
                layout={{
                    autosize: true, height: 480,
                    xaxis: { title: { text: xKey } },
                    yaxis: { title: { text: yKey } },
                    legend: { orientation: 'h', y: -0.15 },
                    margin: { l: 50, r: 20, t: 20, b: 60 }
                }}
                useResizeHandler={true}
                className="w-full"
            />
        </div>
    );
};

const LineAnalytics: React.FC = () => {
    const [linhas, setLinhas] = useState<Linha[]>([]);
    // Removed selectedLinhaId
    const [selectedTags, setSelectedTags] = useState<Tag[]>([]);

    // Time Range
    const [date, setDate] = useState<Date | undefined>(new Date());
    const [hoursBack, setHoursBack] = useState<string>('8'); // Default 8h

    // Data
    const [statsData, setStatsData] = useState<any[]>([]);
    const [correlationData, setCorrelationData] = useState<any>(null);
    const [timeseriesData, setTimeseriesData] = useState<any>(null);
    const [trendCharts, setTrendCharts] = useState<TrendChart[]>([]);
    const [scatterX, setScatterX] = useState<string>('');
    const [scatterY, setScatterY] = useState<string>('');
    const [activeTab, setActiveTab] = useState<string>('stats');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [searchTerm, setSearchTerm] = useState('');
    const [corrMethod, setCorrMethod] = useState<'pearson' | 'spearman'>('pearson');
    const [corrMinFilter, setCorrMinFilter] = useState<number>(0);

    // Fetch Structure
    useEffect(() => {
        axios.get(`${DJANGO_API}/linhas/`)
            .then(res => setLinhas(res.data.results || res.data))
            .catch(err => console.error("Erro ao buscar linhas:", err));
    }, []);

    const handleRunAnalysis = async (mode: 'stats' | 'correlation' | 'timeseries') => {
        // ... (logic remains same, just verify it uses selectedTags which is global now)
        if (selectedTags.length === 0) {
            setError("Selecione pelo menos uma variável.");
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const end = new Date(); // Now
            const start = subHours(end, parseInt(hoursBack));

            const payload: any = {
                variables: selectedTags.map(t => ({
                    tag_influx: t.tag_influxdb,
                    equipamento_code: t.equipamento_code,
                    alias: `${t.linha_nome} - ${t.equipamento_nome} - ${t.nome}`,
                    lsl: t.lsl,
                    usl: t.usl,
                    nominal: t.nominal
                })),
                start_time: start.toISOString(),
                end_time: end.toISOString()
            };
            if (mode === 'correlation') {
                payload.method = corrMethod;
            }

            let endpoint = '';
            if (mode === 'stats') endpoint = '/analyze/stats';
            else if (mode === 'correlation') endpoint = '/analyze/correlation';
            else endpoint = '/analyze/timeseries';

            const res = await axios.post(`${FLASK_API}${endpoint}`, payload);

            if (res.data && Array.isArray(res.data) && res.data.length > 0) {
                const allErrors = res.data.every((r: any) => r.error === 'No data found' || r.error === 'Empty data');
                if (allErrors) {
                    setError("Não há dados registrados para este período. Verifique se o equipamento estava operando.");
                    setLoading(false);
                    return;
                }
            }

            if (mode === 'stats') {
                setStatsData(res.data);
                setActiveTab('stats');
            } else if (mode === 'correlation') {
                if (res.data?.error) {
                    setError(`Correlação: ${res.data.error}. Verifique se há dados para as variáveis selecionadas no período.`);
                    setLoading(false);
                    return;
                }
                setCorrelationData(res.data);
                setActiveTab('correlation');
            } else {
                setTimeseriesData(res.data);
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

    // Helper to process trees (memoized ideally, but safe here)
    // Flatten tags logic moved inside render or helper
    // No more getAvailableTags depending on single line.

    const toggleTag = (tag: any) => {
        if (selectedTags.find(t => t.id === tag.id)) {
            setSelectedTags(selectedTags.filter(t => t.id !== tag.id));
        } else {
            setSelectedTags([...selectedTags, tag]);
        }
    };

    // Tag generation helper - Métricas consolidadas da LINHA
    const getLineConsolidatedTags = (linha: Linha) => {
        const consolidatedMetrics = [
            { nome: 'Produção Total (tons)', tag: 'producao_linha_tons', desc: 'Produção acumulada da linha' },
            { nome: 'Descarte Total (tons)', tag: 'descarte_linha_tons', desc: 'Descarte acumulado da linha' },
            { nome: 'Descarte (%)', tag: 'descarte_linha_perc', desc: 'Percentual de descarte' },
            { nome: 'OEE Linha', tag: 'oee_linha', desc: 'OEE agregado da linha' },
            { nome: 'Disponibilidade', tag: 'disponibilidade_linha', desc: 'Disponibilidade da linha' },
            { nome: 'Performance', tag: 'performance_linha', desc: 'Performance da linha' },
            { nome: 'Qualidade', tag: 'qualidade_linha', desc: 'Qualidade da linha' },
            { nome: 'Vazão Real (ton/h)', tag: 'vazao_linha_ton_h', desc: 'Taxa de produção' },
            { nome: 'Give Away (kg)', tag: 'giveaway_linha_kg', desc: 'Excesso de peso (kg)' },
            { nome: 'Give Away (%)', tag: 'giveaway_linha_perc', desc: 'Percentual de perda por peso' }
        ];

        return consolidatedMetrics.map(m => ({
            id: `linha-${linha.codigo}-${m.tag}`,
            nome: m.nome,
            tag_influxdb: m.tag,
            equipamento_nome: '📊 Consolidado',
            equipamento_code: linha.codigo,  // Usa código da linha para query especial
            linha_nome: linha.nome,
            isConsolidated: true,
            isStandard: false
        }));
    };

    // Tag generation helper - Métricas por EQUIPAMENTO
    const getEquipmentTags = (linha: Linha, eq: Equipamento) => {
        let tags: any[] = [];
        // Standard Metrics
        const standardMetrics = [
            { nome: 'Velocidade', tag: 'velocidade_atual' },
            { nome: 'OEE', tag: 'oee' },
            { nome: 'Produção', tag: 'contagem_saida' },
            { nome: 'Descarte', tag: 'descarte' },
            { nome: 'Estado', tag: 'estado', isDiscrete: true, valueMapping: ESTADO_VALUE_MAPPING }
        ];

        standardMetrics.forEach(m => {
            tags.push({
                id: `std-${eq.codigo}-${m.tag}`,
                nome: m.nome,
                tag_influxdb: m.tag,
                equipamento_nome: eq.nome,
                equipamento_code: eq.codigo,
                linha_nome: linha.nome,
                isStandard: true,
                isDiscrete: (m as any).isDiscrete ?? false,
                valueMapping: (m as any).valueMapping ?? undefined,
            });
        });

        // Dynamic Sensors
        if (eq.sensores) {
            eq.sensores.forEach((s: any) => {
                tags.push({
                    id: s.id,
                    nome: s.nome,
                    tag_influxdb: s.tag_influxdb,
                    equipamento_nome: eq.nome,
                    equipamento_code: eq.codigo,
                    linha_nome: linha.nome,
                    lsl: s.lsl,
                    usl: s.usl,
                    nominal: s.nominal,
                    isStandard: false
                });
            });
        }
        return tags;
    };

    // Filter Logic
    const filterMatch = (text: string) => {
        if (!searchTerm) return true;
        return text.toLowerCase().includes(searchTerm.toLowerCase());
    };

    // Regressão linear simples para trend line no scatter
    const calcLinearRegression = (xArr: number[], yArr: number[]) => {
        const n = xArr.length;
        if (n < 2) return null;
        const xMean = xArr.reduce((a, b) => a + b, 0) / n;
        const yMean = yArr.reduce((a, b) => a + b, 0) / n;
        const ssXY = xArr.reduce((acc, xi, i) => acc + (xi - xMean) * (yArr[i] - yMean), 0);
        const ssXX = xArr.reduce((acc, xi) => acc + (xi - xMean) ** 2, 0);
        if (ssXX === 0) return null;
        const slope = ssXY / ssXX;
        const intercept = yMean - slope * xMean;
        const xMin = Math.min(...xArr);
        const xMax = Math.max(...xArr);
        return { slope, intercept, xMin, xMax };
    };

    // P-value → marcador de significância
    const pvalToStars = (p: number) => {
        if (p < 0.001) return '***';
        if (p < 0.01) return '**';
        if (p < 0.05) return '*';
        return '';
    };

    // Export CSV da matriz de correlação
    const downloadCorrelationCSV = () => {
        if (!correlationData?.correlation_matrix) return;
        const { columns, values, p_values } = correlationData.correlation_matrix;
        let csv = 'Variável,' + columns.join(',') + '\n';
        values.forEach((row: number[], i: number) => {
            const cells = row.map((v: number, j: number) => {
                const p = p_values?.[i]?.[j];
                const stars = p !== undefined ? pvalToStars(p) : '';
                return `${v.toFixed(4)}${stars}`;
            });
            csv += `${columns[i]},${cells.join(',')}\n`;
        });
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `correlacao_${corrMethod}_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };

    const downloadCSV = () => {
        if (!timeseriesData) return;
        let csvContent = "data:text/csv;charset=utf-8,";
        csvContent += "Time,Variable,Value\n";

        // Export simplified CSV (first variable timestamps logic or union)
        // For simplicity, iterating all data
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

    // Carregar perfil salvo
    const loadProfile = (config: any) => {
        setSelectedTags(
            (config.selectedTags || []).map((t: any) => {
                if (t.tag_influxdb === 'estado' && !t.isDiscrete) {
                    return { ...t, isDiscrete: true, valueMapping: ESTADO_VALUE_MAPPING };
                }
                return t;
            })
        );
        setHoursBack(config.hoursBack || '8');
        setActiveTab(config.activeTab || 'stats');
        setTrendCharts(config.trendCharts || []);
        setScatterX(config.scatterX || '');
        setScatterY(config.scatterY || '');
    };

    return (
        <div className="w-full h-full p-2 bg-slate-50/50 dark:bg-slate-950/50">
            <div className="flex h-[calc(100vh-80px)] gap-2">
                {/* Sidebar Filter */}
                <Card className="w-96 flex flex-col shadow-lg border-l-4 border-l-blue-600 dark:border-l-blue-500 rounded-lg">
                    <CardHeader className="pb-2">
                        <CardTitle className="flex items-center gap-2 text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-cyan-500">
                            <Settings className="h-6 w-6 text-blue-600" />
                            Variáveis
                        </CardTitle>
                        <CardDescription>
                            Selecione variáveis de múltiplas linhas<br />
                            <span className="text-xs font-mono bg-slate-100 p-1 rounded">{selectedTags.length} selecionadas</span>
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="flex-1 flex flex-col gap-4 overflow-hidden pt-2">
                        <div>
                            <Label>Período</Label>
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

                        <div className="relative">
                            <Input
                                placeholder="Buscar equipamento ou variável..."
                                value={searchTerm}
                                onChange={e => setSearchTerm(e.target.value)}
                                className="pl-8"
                            />
                            <Filter className="w-4 h-4 absolute left-2.5 top-2.5 text-gray-400" />
                        </div>

                        <ScrollArea className="flex-1 w-full h-full border rounded-md px-2 bg-slate-50 dark:bg-slate-900/50">
                            <Accordion type="multiple" className="w-full pr-3">
                                {linhas.map(linha => {
                                    return (
                                        <AccordionItem key={linha.id} value={`line-${linha.id}`} className="border-b last:border-0">
                                            <AccordionTrigger className="hover:no-underline py-2 sticky top-0 bg-slate-50 dark:bg-slate-900/50 z-10">
                                                <span className="font-semibold text-sm text-left">{linha.nome} ({linha.codigo})</span>
                                            </AccordionTrigger>
                                            <AccordionContent className="pb-2">
                                                <div className="pl-1 flex flex-col gap-1">
                                                    {/* === CONSOLIDADO DA LINHA === */}
                                                    {(() => {
                                                        const consolidatedTags = getLineConsolidatedTags(linha);
                                                        const visibleConsolidated = searchTerm
                                                            ? consolidatedTags.filter(t => filterMatch(t.nome) || filterMatch('consolidado'))
                                                            : consolidatedTags;

                                                        if (visibleConsolidated.length === 0) return null;

                                                        return (
                                                            <div className="mb-2">
                                                                <div className="text-xs font-bold text-emerald-600 mb-2 mt-1 flex items-center gap-1">
                                                                    <Layers className="w-3 h-3" />
                                                                    📊 Consolidado da Linha
                                                                </div>
                                                                <div className="pl-2 space-y-1">
                                                                    {visibleConsolidated.map(tag => (
                                                                        <div
                                                                            key={tag.id}
                                                                            className="flex items-center space-x-2 p-1.5 rounded hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-colors cursor-pointer border border-transparent hover:border-emerald-200 dark:hover:border-emerald-800 bg-emerald-50/30"
                                                                        >
                                                                            <Checkbox
                                                                                id={`tag-${tag.id}`}
                                                                                checked={!!selectedTags.find(t => t.id === tag.id)}
                                                                                onCheckedChange={() => toggleTag(tag)}
                                                                            />
                                                                            <label htmlFor={`tag-${tag.id}`} className="text-xs cursor-pointer flex-1 font-medium text-emerald-700 dark:text-emerald-300">
                                                                                {tag.nome}
                                                                            </label>
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        );
                                                    })()}

                                                    {/* === EQUIPAMENTOS (NESTED ACCORDION) === */}
                                                    <Accordion type="multiple" className="w-full">
                                                        {linha.equipamentos.map(eq => {
                                                            const tags = getEquipmentTags(linha, eq);
                                                            const visibleTags = searchTerm
                                                                ? tags.filter(t => filterMatch(t.nome) || filterMatch(eq.nome))
                                                                : tags;

                                                            if (searchTerm && visibleTags.length === 0) return null;

                                                            return (
                                                                <AccordionItem key={eq.id} value={`eq-${eq.id}`} className="border-none">
                                                                    <AccordionTrigger className="py-2 hover:no-underline text-xs font-bold text-gray-500">
                                                                        <div className="flex items-center gap-2 text-left">
                                                                            <div className="w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0"></div>
                                                                            {eq.nome}
                                                                        </div>
                                                                    </AccordionTrigger>
                                                                    <AccordionContent className="pt-0 pb-2">
                                                                        <div className="pl-3 space-y-1">
                                                                            {visibleTags.map(tag => (
                                                                                <div
                                                                                    key={tag.id}
                                                                                    className="flex items-center space-x-2 p-1.5 rounded hover:bg-white dark:hover:bg-slate-800 transition-colors cursor-pointer border border-transparent hover:border-slate-200 dark:hover:border-slate-700 bg-white/50"
                                                                                >
                                                                                    <Checkbox
                                                                                        id={`tag-${tag.id}`}
                                                                                        checked={!!selectedTags.find(t => t.id === tag.id)}
                                                                                        onCheckedChange={() => toggleTag(tag)}
                                                                                    />
                                                                                    <label htmlFor={`tag-${tag.id}`} className="text-xs cursor-pointer flex-1 font-medium text-slate-700 dark:text-slate-300 truncate" title={tag.nome}>
                                                                                        {tag.nome}
                                                                                        {tag.isStandard && <Badge variant="outline" className="ml-1 text-[9px] h-3 px-1 py-0 border-blue-200 text-blue-400">Std</Badge>}
                                                                                    </label>
                                                                                </div>
                                                                            ))}
                                                                        </div>
                                                                    </AccordionContent>
                                                                </AccordionItem>
                                                            );
                                                        })}
                                                    </Accordion>
                                                </div>
                                            </AccordionContent>
                                        </AccordionItem>
                                    );
                                })}
                            </Accordion>
                        </ScrollArea>

                        {selectedTags.length > 0 && (
                            <Button variant="outline" size="sm" onClick={() => setSelectedTags([])} className="text-red-500 hover:text-red-700">
                                <Trash2 className="w-4 h-4 mr-2" /> Limpar Seleção
                            </Button>
                        )}
                    </CardContent>
                </Card>

                {/* Main Content (Tabs) */}
                <div className="flex-1 overflow-auto">
                    {/* ... Same Tabs content as before ... */}
                    <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full h-full flex flex-col">
                        <div className="flex justify-between items-center mb-4 bg-white dark:bg-slate-900 p-2 rounded-lg shadow-sm border">
                            <TabsList className="grid grid-cols-6 gap-2 w-[720px]">
                                {/* ... Triggers ... */}
                                <TabsTrigger value="stats" className="flex items-center gap-2">
                                    <BarChart2 className="h-4 w-4" /> Stats
                                </TabsTrigger>
                                <TabsTrigger value="boxplot" className="flex items-center gap-2">
                                    <Box className="h-4 w-4" /> Boxplot
                                </TabsTrigger>
                                <TabsTrigger value="trend" className="flex items-center gap-2">
                                    <TrendingUp className="h-4 w-4" /> Tendência
                                </TabsTrigger>
                                <TabsTrigger value="spc" className="flex items-center gap-2">
                                    <Activity className="h-4 w-4" /> SPC
                                </TabsTrigger>
                                <TabsTrigger value="scatter" className="flex items-center gap-2">
                                    <ScatterIcon className="h-4 w-4" /> Dispersão
                                </TabsTrigger>
                                <TabsTrigger value="correlation" className="flex items-center gap-2">
                                    <Grid className="h-4 w-4" /> Correlação
                                </TabsTrigger>
                            </TabsList>
                            <div className="flex gap-2">
                                {linhas.length > 0 && (
                                    <ProfileManager
                                        linhaId={linhas[0]?.id}
                                        currentState={{
                                            selectedTags,
                                            hoursBack,
                                            activeTab,
                                            trendCharts,
                                            scatterX,
                                            scatterY
                                        }}
                                        onLoadProfile={loadProfile}
                                    />
                                )}
                                <Button onClick={() => handleRunAnalysis('stats')} variant="secondary" size="sm">Stats</Button>
                                <Button onClick={() => handleRunAnalysis('timeseries')} variant="default" size="sm">Gerar Gráficos</Button>
                                <Button onClick={() => handleRunAnalysis('correlation')} variant="outline" size="sm">Correlação</Button>
                                {timeseriesData && (
                                    <Button onClick={downloadCSV} variant="ghost" size="sm">Exportar CSV</Button>
                                )}
                            </div>
                        </div>

                        {error && <div className="p-4 bg-red-100 text-red-700 rounded mb-4">{error}</div>}

                        {/* TABS CONTENT (Reused) */}
                        <TabsContent value="stats" className="space-y-4">
                            {statsData.map((res, idx) => {
                                const tagMatch = selectedTags.find(t => `${t.linha_nome} - ${t.equipamento_nome} - ${t.nome}` === res.variable);
                                const isDiscrete = tagMatch?.isDiscrete || res.is_discrete;
                                const mapping = tagMatch?.valueMapping;

                                return (
                                <Card key={idx}>
                                    <CardHeader>
                                        <CardTitle>{res.variable}</CardTitle>
                                        {res.error ? (
                                            <div className="text-red-500 text-sm font-medium bg-red-50 p-2 rounded border border-red-200 dark:bg-red-900/20 dark:border-red-800">
                                                {res.error === 'No data found' ? 'Sem dados para o período selecionado' : res.error}
                                            </div>
                                        ) : (
                                            <div className="flex gap-4 text-sm text-gray-500">
                                                {!isDiscrete && (
                                                    <>
                                                        <span>Média: {res.stats?.mean?.toFixed(2) ?? 'N/A'}</span>
                                                        <span>Std: {res.stats?.std?.toFixed(2) ?? 'N/A'}</span>
                                                        {res.stats?.cpk !== undefined && res.stats.cpk !== null && (
                                                            <span className={res.stats.cpk < 1.33 ? 'text-red-500 font-bold' : 'text-green-600 font-bold'}>
                                                                Cpk: {res.stats.cpk.toFixed(2)}
                                                            </span>
                                                        )}
                                                        {res.stats?.cp !== undefined && res.stats.cp !== null && (
                                                            <span className={res.stats.cp < 1.33 ? 'text-red-500 font-bold ml-4' : 'text-green-600 font-bold ml-4'}>
                                                                Cp: {res.stats.cp.toFixed(2)}
                                                            </span>
                                                        )}
                                                    </>
                                                )}
                                                {isDiscrete && (
                                                    <>
                                                        <span>Valores Únicos: {res.n_unique || res.stats?.count || 'N/A'}</span>
                                                        <span>Contagem Total: {res.stats?.count || 'N/A'}</span>
                                                    </>
                                                )}
                                            </div>
                                        )}
                                    </CardHeader>
                                    <CardContent>
                                        {!res.error && res.histogram && (() => {
                                            const bins: number[] = res.histogram.bins;
                                            const counts: number[] = res.histogram.counts;

                                            if (isDiscrete) {
                                                const colors = bins.map(val => mapping?.[val]?.color || '#3b82f6');
                                                const labels = bins.map(val => mapping?.[val]?.label || `Valor: ${val}`);

                                                return (
                                                    <Plot
                                                        data={[{
                                                            x: labels,
                                                            y: counts,
                                                            type: 'bar',
                                                            name: 'Frequência',
                                                            marker: { color: colors, line: { color: colors, width: 1 } }
                                                        }]}
                                                        layout={{
                                                            height: 320,
                                                            autosize: true,
                                                            title: { text: 'Distribuição de Frequência' },
                                                            bargap: 0.2,
                                                            xaxis: { title: { text: 'Estado/Categoria' } },
                                                            yaxis: { title: { text: 'Contagem' } }
                                                        }}
                                                        useResizeHandler={true}
                                                        className="w-full"
                                                    />
                                                );
                                            }

                                            // Continuous format
                                            const mean: number = res.stats?.mean ?? 0;
                                            const std: number = res.stats?.std ?? 1;
                                            const n: number = res.stats?.count ?? 1;
                                            const binWidth = bins.length > 1 ? bins[1] - bins[0] : 1;
                                            // Gera curva normal usando os centros dos bins
                                            const xCurve = bins.slice(0, -1).map(b => b + binWidth / 2);
                                            const yCurve = xCurve.map((x: number) =>
                                                n * binWidth * (1 / (std * Math.sqrt(2 * Math.PI))) * Math.exp(-0.5 * ((x - mean) / std) ** 2)
                                            );
                                            return (
                                                <Plot
                                                    data={[
                                                        {
                                                            x: bins,
                                                            y: counts,
                                                            type: 'bar',
                                                            name: 'Frequência',
                                                            marker: { color: 'rgba(59,130,246,0.6)', line: { color: 'rgba(59,130,246,1)', width: 1 } }
                                                        },
                                                        {
                                                            x: xCurve,
                                                            y: yCurve,
                                                            type: 'scatter',
                                                            mode: 'lines',
                                                            name: 'Dist. Normal',
                                                            line: { color: 'red', width: 2, dash: 'dash' }
                                                        }
                                                    ]}
                                                    layout={{
                                                        height: 320,
                                                        autosize: true,
                                                        title: { text: 'Histograma com Distribuição Normal' },
                                                        bargap: 0.05,
                                                        legend: { orientation: 'h', y: -0.2 },
                                                        xaxis: { title: { text: 'Valor' } },
                                                        yaxis: { title: { text: 'Frequência' } }
                                                    }}
                                                    useResizeHandler={true}
                                                    className="w-full"
                                                />
                                            );
                                        })()}
                                    </CardContent>
                                </Card>
                            )})}
                            {statsData.length === 0 && !loading && (
                                <div className="flex items-center justify-center h-64 border-2 border-dashed rounded-lg text-gray-400">
                                    Selecione variáveis na árvore e clique em Analisar
                                </div>
                            )}
                        </TabsContent>

                        {/* === BOXPLOT TAB === */}
                        <TabsContent value="boxplot">
                            {timeseriesData ? (
                                <div className="space-y-4">
                                    <Card>
                                        <CardHeader>
                                            <CardTitle className="flex items-center gap-2">
                                                <Box className="h-5 w-5 text-purple-600" />
                                                Análise de Distribuição (Boxplot)
                                            </CardTitle>
                                            <CardDescription>
                                                Visualização de quartis, mediana e outliers para cada variável selecionada
                                            </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                            <Plot
                                                data={Object.entries(timeseriesData).map(([alias, d]: [string, any]) => ({
                                                    y: d.values,
                                                    type: 'box',
                                                    name: alias.split(' - ').pop() || alias, // Usar nome curto
                                                    boxpoints: 'outliers',
                                                    jitter: 0.3,
                                                    pointpos: -1.8,
                                                    marker: { size: 4, opacity: 0.6 },
                                                    hovertext: alias
                                                }))}
                                                layout={{
                                                    title: { text: 'Comparação de Distribuições' },
                                                    autosize: true,
                                                    height: 500,
                                                    showlegend: true,
                                                    boxmode: 'group',
                                                    yaxis: { title: { text: 'Valor' } }
                                                }}
                                                useResizeHandler={true}
                                                className="w-full"
                                            />
                                        </CardContent>
                                    </Card>

                                    {/* Boxplots individuais */}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {Object.entries(timeseriesData).map(([alias, d]: [string, any]) => (
                                            <Card key={alias} className="border-l-4 border-l-purple-500">
                                                <CardHeader className="pb-2">
                                                    <CardTitle className="text-sm truncate" title={alias}>{alias}</CardTitle>
                                                </CardHeader>
                                                <CardContent>
                                                    <Plot
                                                        data={[{
                                                            y: d.values,
                                                            type: 'box',
                                                            name: 'Distribuição',
                                                            boxpoints: 'all',
                                                            jitter: 0.5,
                                                            pointpos: 0,
                                                            marker: { color: 'rgb(107, 70, 193)', size: 4, opacity: 0.5 },
                                                            line: { color: 'rgb(107, 70, 193)' },
                                                            fillcolor: 'rgba(107, 70, 193, 0.3)'
                                                        }]}
                                                        layout={{
                                                            autosize: true,
                                                            height: 250,
                                                            margin: { l: 40, r: 20, t: 20, b: 30 },
                                                            showlegend: false
                                                        }}
                                                        useResizeHandler={true}
                                                        className="w-full"
                                                    />
                                                    <div className="flex justify-between text-xs text-gray-500 mt-2">
                                                        <span>Min: {d.values.length > 0 ? Math.min(...d.values).toFixed(2) : 'N/A'}</span>
                                                        <span>Mediana: {d.values.length > 0 ? d.values.sort((a: number, b: number) => a - b)[Math.floor(d.values.length / 2)]?.toFixed(2) : 'N/A'}</span>
                                                        <span>Max: {d.values.length > 0 ? Math.max(...d.values).toFixed(2) : 'N/A'}</span>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))}
                                    </div>
                                </div>
                            ) : (
                                <div className="flex flex-col items-center justify-center h-64 border-2 border-dashed rounded-lg text-gray-400 gap-2">
                                    <Box className="h-8 w-8 opacity-50" />
                                    <span>Clique em "Gerar Gráficos" para visualizar os Boxplots</span>
                                </div>
                            )}
                        </TabsContent>

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
                                                                <Button variant="ghost" size="sm" className="h-8 w-8 p-0"><Settings className="h-4 w-4" /></Button>
                                                            </PopoverTrigger>
                                                            <PopoverContent className="w-64 p-2" align="end">
                                                                <div className="flex flex-col gap-2 mb-2">
                                                                    <Label htmlFor={`name-${chart.id}`} className="text-xs font-semibold text-gray-500">Nome do Painel</Label>
                                                                    <Input id={`name-${chart.id}`} value={chart.name} onChange={(e) => updateChartName(chart.id, e.target.value)} className="h-7 text-sm" />
                                                                </div>
                                                                <div className="mb-2 font-medium text-xs text-gray-500 mt-2">Variáveis neste gráfico</div>
                                                                <ScrollArea className="h-40 border rounded bg-slate-50 dark:bg-slate-900/50">
                                                                    {Object.keys(timeseriesData).map(alias => (
                                                                        <div key={alias} className="flex items-center space-x-2 py-1 px-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded cursor-pointer" onClick={() => toggleChartVariable(chart.id, alias)}>
                                                                            <Checkbox checked={chart.selectedAliases.includes(alias)} onCheckedChange={() => toggleChartVariable(chart.id, alias)} />
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
                                                            data={chart.selectedAliases.map((alias: string, idx: number) => {
                                                                const tagMatch = selectedTags.find(t => `${t.linha_nome} - ${t.equipamento_nome} - ${t.nome}` === alias);
                                                                const isDiscrete = tagMatch?.isDiscrete;
                                                                return {
                                                                    x: timeseriesData[alias]?.timestamps || [],
                                                                    y: timeseriesData[alias]?.values || [],
                                                                    type: 'scatter',
                                                                    mode: 'lines',
                                                                    line: { shape: isDiscrete ? 'hv' : 'linear' },
                                                                    name: alias.split(' - ').pop() || alias,
                                                                    hovertext: alias,
                                                                    yaxis: idx === 0 ? 'y' : `y${idx + 1}`,
                                                                };
                                                            })}
                                                            layout={{
                                                                title: undefined,
                                                                autosize: true,
                                                                height: 350,
                                                                margin: { l: 60, r: 60, t: 20, b: 60 },
                                                                showlegend: true,
                                                                legend: { orientation: 'h', y: -0.25 },
                                                                xaxis: { type: 'date' },
                                                                ...Object.fromEntries(
                                                                    chart.selectedAliases.map((alias: string, idx: number) => {
                                                                        const tagMatch = selectedTags.find(t => `${t.linha_nome} - ${t.equipamento_nome} - ${t.nome}` === alias);
                                                                        const isDiscrete = tagMatch?.isDiscrete;
                                                                        const mapping = tagMatch?.valueMapping;
                                                                        return [
                                                                            idx === 0 ? 'yaxis' : `yaxis${idx + 1}`,
                                                                            {
                                                                                title: { text: '' },
                                                                                overlaying: idx === 0 ? undefined : 'y',
                                                                                side: idx % 2 === 0 ? 'left' : 'right',
                                                                                showgrid: idx === 0,
                                                                                autorange: true,
                                                                                ...(isDiscrete && mapping ? {
                                                                                    tickvals: Object.keys(mapping).map(Number),
                                                                                    ticktext: Object.keys(mapping).map(k => mapping[Number(k)].label),
                                                                                } : {})
                                                                            }
                                                                        ];
                                                                    })
                                                                )
                                                            } as any}
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

                        {/* SPC and Scatter Tabs remain similar ... */}
                        <TabsContent value="spc">
                            {timeseriesData ? (
                                <div className="space-y-4">
                                    {Object.entries(timeseriesData).map(([alias, d]: [string, any]) => {
                                        const tagMatch = selectedTags.find(t => `${t.linha_nome} - ${t.equipamento_nome} - ${t.nome}` === alias);
                                        const isDiscrete = tagMatch?.isDiscrete;
                                        const mapping = tagMatch?.valueMapping;

                                        if (isDiscrete) {
                                            const counts: Record<number, number> = {};
                                            d.values.forEach((v: number) => { counts[v] = (counts[v] || 0) + 1; });
                                            const x = Object.keys(counts).map(Number);
                                            const y = Object.values(counts);
                                            const colors = x.map(val => mapping?.[val]?.color || '#94a3b8');
                                            const labels = x.map(val => mapping?.[val]?.label || `Val: ${val}`);

                                            return (
                                                <Card key={alias}>
                                                    <CardHeader><CardTitle>Frequência de Estados - {alias}</CardTitle></CardHeader>
                                                    <CardContent>
                                                        <Plot
                                                            data={[{
                                                                x: labels,
                                                                y: y,
                                                                type: 'bar',
                                                                marker: { color: colors }
                                                            }]}
                                                            layout={{ title: { text: `Distribuição de Tempo: ${alias}` }, autosize: true, height: 400, yaxis: { title: 'Registros (Freq)' } }}
                                                            useResizeHandler={true}
                                                            className="w-full"
                                                        />
                                                    </CardContent>
                                                </Card>
                                            );
                                        }

                                        return (
                                            <Card key={alias}>
                                                <CardHeader><CardTitle>SPC - {alias}</CardTitle></CardHeader>
                                                <CardContent>
                                                    <Plot
                                                        data={[
                                                            { x: d.timestamps, y: d.values, type: 'scatter', mode: 'lines+markers', name: 'Valor Real' },
                                                            { x: d.timestamps, y: Array(d.timestamps.length).fill(d.stats?.mean ?? 0), type: 'scatter', mode: 'lines', name: 'Média', line: { color: 'green', dash: 'dash' } },
                                                            { x: d.timestamps, y: Array(d.timestamps.length).fill(d.stats?.ucl ?? 0), type: 'scatter', mode: 'lines', name: 'UCL (+3σ)', line: { color: 'red' } },
                                                            { x: d.timestamps, y: Array(d.timestamps.length).fill(d.stats?.lcl ?? 0), type: 'scatter', mode: 'lines', name: 'LCL (-3σ)', line: { color: 'red' } },
                                                        ]}
                                                        layout={{ title: { text: `Carta de Controle: ${alias}` }, autosize: true, height: 400 }}
                                                        useResizeHandler={true}
                                                        className="w-full"
                                                    />
                                                </CardContent>
                                            </Card>
                                        );
                                    })}
                                </div>
                            ) : <div className="text-center p-8 text-gray-500">Clique em "Gerar Gráficos" para visualizar.</div>}
                        </TabsContent>

                        <TabsContent value="correlation">
                            {/* Aviso de Spearman caso haja vars discretas */}
                            {selectedTags.some(t => t.isDiscrete) && (
                                <div className="mb-4 p-3 bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300 rounded border border-blue-200 dark:border-blue-800 text-sm flex items-start gap-2">
                                    <Info className="h-5 w-5 shrink-0 mt-0.5" />
                                    <div>
                                        <strong>Variáveis Discretas Detectadas.</strong> Como existem variáveis categóricas/ordinais selecionadas (ex: Estado), é recomendado utilizar o método de correlação de <strong>Spearman</strong> ao invés de Pearson.
                                        {corrMethod === 'pearson' && (
                                            <Button variant="link" size="sm" className="p-0 h-auto ml-2 text-blue-700 dark:text-blue-300 underline font-semibold" onClick={() => setCorrMethod('spearman')}>
                                                Mudar para Spearman
                                            </Button>
                                        )}
                                    </div>
                                </div>
                            )}
                            
                            {/* Controles da aba de correlação */}
                            <div className="flex flex-wrap items-center gap-4 mb-4 p-3 bg-white dark:bg-slate-900 rounded-lg border shadow-sm">
                                <div className="flex items-center gap-2">
                                    <Label className="text-xs font-semibold text-gray-500 whitespace-nowrap">Método</Label>
                                    <Select value={corrMethod} onValueChange={(v: string) => setCorrMethod(v as 'pearson' | 'spearman')}>
                                        <SelectTrigger className="w-36 h-8 text-xs"><SelectValue /></SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="pearson">Pearson (linear)</SelectItem>
                                            <SelectItem value="spearman">Spearman (rank)</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="flex items-center gap-2 flex-1 min-w-[200px]">
                                    <Label className="text-xs font-semibold text-gray-500 whitespace-nowrap">
                                        Filtro mínimo: {(corrMinFilter * 100).toFixed(0)}%
                                    </Label>
                                    <input
                                        type="range" min="0" max="0.99" step="0.05"
                                        value={corrMinFilter}
                                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCorrMinFilter(parseFloat(e.target.value))}
                                        className="flex-1 h-2 accent-blue-600 cursor-pointer"
                                    />
                                </div>
                                {correlationData?.correlation_matrix && (
                                    <div className="flex items-center gap-3 text-xs text-gray-500">
                                        <span className="bg-slate-100 px-2 py-1 rounded font-mono">
                                            n={correlationData.correlation_matrix.n_points} pts
                                        </span>
                                        <span className="bg-slate-100 px-2 py-1 rounded font-mono">
                                            resample: {correlationData.correlation_matrix.resample_rule}
                                        </span>
                                        <span className="text-[10px] text-gray-400">
                                            {'* p<0.05  ** p<0.01  *** p<0.001'}
                                        </span>
                                        <Button variant="outline" size="sm" className="h-7 text-xs gap-1" onClick={downloadCorrelationCSV}>
                                            <Download className="h-3 w-3" /> CSV
                                        </Button>
                                    </div>
                                )}
                            </div>

                            {correlationData?.correlation_matrix ? (
                                <CorrMatrixPlot
                                    matrix={correlationData.correlation_matrix}
                                    corrMinFilter={corrMinFilter}
                                    pvalToStars={pvalToStars}
                                    timeseriesData={timeseriesData}
                                    setScatterX={setScatterX}
                                    setScatterY={setScatterY}
                                    setActiveTab={setActiveTab}
                                    handleRunAnalysis={handleRunAnalysis}
                                />
                            ) : !loading && (
                                <div className="flex flex-col items-center justify-center h-64 border-2 border-dashed rounded-lg text-gray-400 gap-2">
                                    <Grid className="h-8 w-8 opacity-40" />
                                    <span>Configure o método acima e clique em Correlação</span>
                                </div>
                            )}
                        </TabsContent>

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
                                        {scatterX && scatterY
                                            ? <ScatterPlot xKey={scatterX} yKey={scatterY} timeseriesData={timeseriesData} calcLinearRegression={calcLinearRegression} />
                                            : <div className="p-8 text-center text-gray-500">Selecione as variáveis para os Eixos X e Y.</div>
                                        }
                                    </CardContent>
                                </Card>
                            ) : <div className="text-center p-8 text-gray-500">Clique em "Gerar Gráficos" para visualizar.</div>}
                        </TabsContent>

                    </Tabs>
                </div>
            </div>
        </div>
    );
};

export default LineAnalytics;
