import { useState, useEffect, useRef } from 'react';
import api from '../services/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DateRangePicker } from "@/components/ui/DateRangePicker";
import { Label } from "@/components/ui/label";
import {
    TrendingUp, TrendingDown, Minus, Zap, DollarSign, Activity, Clock,
    Download, RefreshCw, AlertTriangle, CheckCircle, Info, Loader2, Filter
} from 'lucide-react';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    PieChart, Pie, Cell, BarChart, Bar
} from 'recharts';
import { format, subDays } from 'date-fns';
import { ptBR } from 'date-fns/locale';

// Paleta de cores ISA-101 (Cores neutras para base, fortes para desvios)
const COLORS = {
    primary: '#3B82F6',   // Information
    secondary: '#10B981', // Good/Safe
    warning: '#F59E0B',   // Warning
    danger: '#EF4444',    // Critical
    neutral: '#64748B',   // Context
    purple: '#8B5CF6'     // Special
};

const ENERGY_COLORS = ['#3B82F6', '#F59E0B', '#10B981', '#8B5CF6', '#EC4899'];

export function EnergyDashboard() {
    const [loading, setLoading] = useState(true);
    const [summary, setSummary] = useState(null);
    const [timeSeries, setTimeSeries] = useState([]);
    const [breakdown, setBreakdown] = useState([]);
    const [heatmapData, setHeatmapData] = useState([]);
    const [insights, setInsights] = useState([]);
    const [period, setPeriod] = useState('hourly');

    // View Mode: 'consumption' (kWh) or 'cost' (R$)
    const [viewMode, setViewMode] = useState('consumption');

    const chartRef = useRef(null);

    // Filters
    const [hierarchyTree, setHierarchyTree] = useState([]);
    const [selectedFactoryId, setSelectedFactoryId] = useState('all');
    const [selectedAreaId, setSelectedAreaId] = useState('all');
    const [selectedLineId, setSelectedLineId] = useState('all');

    // Date range state
    const [startDate, setStartDate] = useState(() => {
        const d = new Date();
        d.setDate(d.getDate() - 7); // Default last 7 days
        return d;
    });
    const [endDate, setEndDate] = useState(new Date());

    // Fetch Hierarchy on Mount
    useEffect(() => {
        const fetchHierarchy = async () => {
            try {
                const res = await api.get('/hierarchy/tree');
                if (res.success) setHierarchyTree(res.data || []);
            } catch (e) {
                console.error("Failed to load hierarchy", e);
            }
        };
        fetchHierarchy();
    }, []);

    // Derived Hierarchy Options
    const factories = hierarchyTree.filter(n => n.type === 'factory');
    const selectedFactory = factories.find(f => f.id.toString() === selectedFactoryId);
    const areas = selectedFactory?.children || [];
    const selectedArea = areas.find(a => a.id.toString() === selectedAreaId);
    const lines = selectedArea?.children || [];

    // Determine effective hierarchy_id for API
    const getActiveHierarchyId = () => {
        if (selectedLineId !== 'all') return selectedLineId;
        if (selectedAreaId !== 'all') return selectedAreaId;
        if (selectedFactoryId !== 'all') return selectedFactoryId;
        return null; // Global
    };

    // Handle date range change
    const handleDateRangeChange = (start, end) => {
        setStartDate(start);
        setEndDate(end);
    };

    useEffect(() => {
        fetchDashboardData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [startDate, endDate, period, selectedFactoryId, selectedAreaId, selectedLineId]);


    // Fetch all dashboard data
    const fetchDashboardData = async () => {
        setLoading(true);
        try {
            // Format dates for API
            const startParam = startDate.toISOString();
            const endParam = endDate.toISOString();
            const hierarchyId = getActiveHierarchyId();

            let queryParams = `start_date=${startParam}&end_date=${endParam}`;
            if (hierarchyId) queryParams += `&hierarchy_id=${hierarchyId}`;

            // Add period param to time-series call
            const timeSeriesUrl = `/analytics/time-series?period=${period}&start_time=${startParam}&end_time=${endParam}${hierarchyId ? `&hierarchy_id=${hierarchyId}` : ''}`;

            const [summaryRes, timeSeriesRes, breakdownRes, heatmapRes, insightsRes] = await Promise.all([
                api.get(`/analytics/dashboard-summary?${queryParams}`),
                api.get(timeSeriesUrl),
                api.get(`/analytics/energy-breakdown?${queryParams}`),
                api.get(`/analytics/heatmap?${queryParams}`),
                api.get(`/analytics/insights?${queryParams}`)
            ]);

            if (summaryRes.success) setSummary(summaryRes.data);
            if (timeSeriesRes.success) setTimeSeries(timeSeriesRes.data);
            if (breakdownRes.success) setBreakdown(breakdownRes.data);
            if (heatmapRes.success) setHeatmapData(heatmapRes);
            if (insightsRes.success) setInsights(insightsRes.data);

        } catch (error) {
            console.error('Erro ao carregar dashboard:', error);
        } finally {
            setLoading(false);
        }
    };

    // Helper for cost vs consumption formatting
    const formatValue = (val, mode = viewMode) => {
        if (mode === 'cost') return `R$ ${val?.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
        return `${val?.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} kWh`;
    };

    // Trend Icon Component
    const TrendIcon = ({ value, invert = false }) => {
        if (!value) return <Minus className="h-4 w-4 text-slate-400" />;

        // For cost/consumption: Up is bad (Red), Down is good (Green). 
        // Unless inverted (Efficiency: Up is Good).
        const isPositive = value > 0;
        const isGood = invert ? isPositive : !isPositive;

        const ColorClass = isGood ? "text-emerald-500" : "text-rose-500";
        const Icon = isPositive ? TrendingUp : TrendingDown;

        return (
            <div className={`flex items-center text-xs font-medium ${ColorClass}`}>
                <Icon className="h-3 w-3 mr-1" />
                {Math.abs(value).toFixed(1)}%
            </div>
        );
    };

    // Summary Card Component (ISA-101 Style: Simple, Clean, Context)
    const SummaryCard = ({ title, value, subValue, icon: Icon, trend, invertTrend, loading }) => (
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden">
            <CardContent className="p-4">
                <div className="flex justify-between items-start mb-2">
                    <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{title}</p>
                    <Icon className="h-4 w-4 text-slate-400" />
                </div>

                {loading ? (
                    <div className="space-y-2 animate-pulse">
                        <div className="h-8 bg-slate-200 dark:bg-slate-700 rounded w-24"></div>
                        <div className="h-4 bg-slate-100 dark:bg-slate-800 rounded w-16"></div>
                    </div>
                ) : (
                    <div>
                        <div className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
                            {value}
                        </div>
                        <div className="flex items-center justify-between mt-2">
                            {subValue && <span className="text-xs text-slate-500">{subValue}</span>}
                            <TrendIcon value={trend} invert={invertTrend} />
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );

    // Heatmap Component
    const Heatmap = ({ data }) => {
        if (!data?.data || data.data.length === 0) return (
            <div className="flex flex-col items-center justify-center h-[200px] text-slate-400 text-sm">
                <Info className="h-6 w-6 mb-2 opacity-50" />
                Sem dados suficientes para mapa de calor
            </div>
        );

        const days = data.days || [];
        const range = data.range || { min: 0, max: 1500 };

        const getColor = (value) => {
            const normalized = (value - range.min) / (range.max - range.min);
            if (normalized < 0.33) return '#10B981'; // Green
            if (normalized < 0.66) return '#F59E0B'; // Yellow
            return '#EF4444'; // Red
        };

        return (
            <div className="overflow-x-auto">
                <div className="grid gap-1 min-w-[600px]" style={{ gridTemplateColumns: `60px repeat(24, 1fr)` }}>
                    {/* Header */}
                    <div></div>
                    {Array.from({ length: 24 }, (_, i) => (
                        <div key={i} className="text-[10px] text-center text-slate-500 py-1">
                            {i}h
                        </div>
                    ))}

                    {/* Rows */}
                    {days.map((day, dayIdx) => (
                        <>
                            <div key={`day-${dayIdx}`} className="text-[10px] text-right pr-2 py-1 text-slate-600 font-medium self-center">
                                {day}
                            </div>
                            {Array.from({ length: 24 }, (_, hour) => {
                                const cellData = data.data.find(d => d.day_index === dayIdx && d.hour === hour);
                                const value = cellData?.value || 0;
                                return (
                                    <div
                                        key={`${dayIdx}-${hour}`}
                                        className="h-6 rounded-sm cursor-pointer transition-opacity hover:opacity-80"
                                        style={{ backgroundColor: getColor(value) }}
                                        title={`${day} ${hour}:00 - ${value} kWh`}
                                    />
                                );
                            })}
                        </>
                    ))}
                </div>
            </div>
        );
    };

    // Insight Card Component
    const InsightCard = ({ insight }) => {
        const icons = {
            'trending-up': TrendingUp,
            'trending-down': TrendingDown,
            'clock': Clock,
            'dollar-sign': DollarSign,
            'zap': Zap
        };
        const Icon = icons[insight.icon] || Info;

        const colors = {
            success: 'bg-green-50 border-green-200 text-green-800',
            warning: 'bg-amber-50 border-amber-200 text-amber-800',
            alert: 'bg-red-50 border-red-200 text-red-800',
            info: 'bg-blue-50 border-blue-200 text-blue-800'
        };

        return (
            <div className={`p-4 rounded-lg border ${colors[insight.type] || colors.info}`}>
                <div className="flex items-start gap-3">
                    <Icon className="h-5 w-5 mt-0.5 flex-shrink-0" />
                    <div>
                        <p className="font-medium text-sm">{insight.title}</p>
                        <p className="text-xs mt-1 opacity-80">{insight.description}</p>
                    </div>
                </div>
            </div>
        );
    };

    return (
        <div className="p-6 space-y-6 bg-slate-50/50 dark:bg-slate-950/50 min-h-screen font-sans">
            {/* Header & Controls */}
            <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-6">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
                        Analytics de Energia
                    </h1>
                    <p className="text-slate-500 text-sm mt-1">
                        Monitoramento de alta performance e custos operacionais
                    </p>
                </div>

                <div className="flex flex-col md:flex-row gap-3">
                    {/* Hierarchy Filters */}
                    <div className="flex gap-2">
                        <Select value={selectedFactoryId} onValueChange={(v) => {
                            setSelectedFactoryId(v); setSelectedAreaId('all'); setSelectedLineId('all');
                        }}>
                            <SelectTrigger className="w-[140px] h-9 text-xs">
                                <SelectValue placeholder="Todas Fábricas" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">Todas Fábricas</SelectItem>
                                {factories.map(f => <SelectItem key={f.id} value={String(f.id)}>{f.name}</SelectItem>)}
                            </SelectContent>
                        </Select>

                        <Select value={selectedAreaId} onValueChange={(v) => {
                            setSelectedAreaId(v); setSelectedLineId('all');
                        }} disabled={selectedFactoryId === 'all'}>
                            <SelectTrigger className="w-[140px] h-9 text-xs">
                                <SelectValue placeholder="Todas Áreas" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">Todas Áreas</SelectItem>
                                {areas.map(a => <SelectItem key={a.id} value={String(a.id)}>{a.name}</SelectItem>)}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* View Mode Toggle (Tabs style) */}
                    <div className="flex items-center border rounded-md p-1 bg-white dark:bg-slate-900 h-9">
                        <Tabs value={viewMode} onValueChange={setViewMode}>
                            <TabsList className="h-7 w-auto bg-transparent p-0">
                                <TabsTrigger value="consumption" className="text-xs h-7 px-3 data-[state=active]:bg-slate-100 dark:data-[state=active]:bg-slate-800">kWh</TabsTrigger>
                                <TabsTrigger value="cost" className="text-xs h-7 px-3 data-[state=active]:bg-slate-100 dark:data-[state=active]:bg-slate-800">R$</TabsTrigger>
                            </TabsList>
                        </Tabs>
                    </div>

                    <DateRangePicker
                        startDate={startDate}
                        endDate={endDate}
                        onRangeChange={handleDateRangeChange}
                        className="h-9"
                    />

                    <Button variant="outline" size="sm" onClick={fetchDashboardData} disabled={loading}>
                        <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
                    </Button>
                </div>
            </div>

            {/* Summary Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <SummaryCard
                    title={viewMode === 'cost' ? "Custo Total" : "Consumo Total"}
                    value={viewMode === 'cost'
                        ? `R$ ${summary?.current?.cost_brl?.toLocaleString('pt-BR', { maximumFractionDigits: 0 }) || '0'}`
                        : `${summary?.current?.consumption_kwh?.toLocaleString('pt-BR', { maximumFractionDigits: 0 }) || '0'} kWh`}
                    subValue={viewMode === 'cost' ? `${(summary?.current?.consumption_kwh || 0).toFixed(0)} kWh` : null}
                    icon={viewMode === 'cost' ? DollarSign : Zap}
                    trend={viewMode === 'cost' ? summary?.delta?.cost_percent : summary?.delta?.consumption_percent}
                    loading={loading}
                />
                <SummaryCard
                    title="Demanda Média"
                    value={`${(summary?.current?.consumption_kwh / (summary?.period?.days * 24 || 1) || 0).toFixed(1)} kW`}
                    subValue="Potência Média"
                    icon={Activity}
                    trend={summary?.delta?.consumption_percent} // Proxied by consumption
                    loading={loading}
                />
                <SummaryCard
                    title="Eficiência"
                    value={`${summary?.current?.efficiency_kwh_ton || 0}`}
                    subValue="kWh / Ton"
                    icon={TrendingDown}
                    trend={summary?.delta?.efficiency_percent}
                    invertTrend={false} // Lower is better for kWh/Ton? Usually yes.
                    loading={loading}
                />
                <SummaryCard
                    title="Projeção Mensal"
                    value={viewMode === 'cost'
                        ? `R$ ${(summary?.current?.cost_brl / (summary?.period?.days || 1) * 30 || 0).toLocaleString('pt-BR', { maximumFractionDigits: 0 })}`
                        : `${(summary?.current?.consumption_kwh / (summary?.period?.days || 1) * 30 || 0).toLocaleString('pt-BR', { maximumFractionDigits: 0 })} kWh`
                    }
                    subValue="Baseado na média atual"
                    icon={Clock}
                    loading={loading}
                    trend={0}
                />
            </div>

            {/* Charts Section */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Main Trend Line */}
                <Card className="lg:col-span-2 border-slate-200 dark:border-slate-800 shadow-sm">
                    <CardHeader className="pb-2 flex flex-row items-center justify-between">
                        <div>
                            <CardTitle className="text-base font-medium">
                                {viewMode === 'cost' ? 'Evolução de Custos' : 'Perfil de Consumo'}
                            </CardTitle>
                            <CardDescription>
                                Comparativo histórico e tendências
                            </CardDescription>
                        </div>
                        <Tabs value={period} onValueChange={setPeriod} className="w-auto">
                            <TabsList className="h-7 bg-slate-100 dark:bg-slate-800 p-0.5">
                                <TabsTrigger value="hourly" className="text-xs px-2.5 h-6 data-[state=active]:bg-white">Hora</TabsTrigger>
                                <TabsTrigger value="daily" className="text-xs px-2.5 h-6 data-[state=active]:bg-white">Dia</TabsTrigger>
                            </TabsList>
                        </Tabs>
                    </CardHeader>
                    <CardContent>
                        <div className="h-[320px] w-full">
                            {loading && !timeSeries.length ? (
                                <div className="h-full flex items-center justify-center text-slate-400">
                                    <Loader2 className="h-6 w-6 animate-spin mr-2" /> Carregando dados...
                                </div>
                            ) : (
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={timeSeries} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                                        <XAxis
                                            dataKey="label"
                                            tick={{ fontSize: 11, fill: '#64748B' }}
                                            axisLine={false}
                                            tickLine={false}
                                            dy={10}
                                        />
                                        <YAxis
                                            tick={{ fontSize: 11, fill: '#64748B' }}
                                            axisLine={false}
                                            tickLine={false}
                                            tickFormatter={(val) => val >= 1000 ? `${(val / 1000).toFixed(1)}k` : val}
                                        />
                                        <Tooltip
                                            contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                            formatter={(val) => viewMode === 'cost'
                                                ? [`R$ ${val}`, 'Custo']
                                                : [`${val} kWh`, 'Consumo']}
                                            labelStyle={{ color: '#64748B' }}
                                        />
                                        <Line
                                            type="monotone"
                                            dataKey={viewMode === 'cost' ? 'cost_brl' : 'consumption_kwh'}
                                            stroke={COLORS.primary}
                                            strokeWidth={2}
                                            dot={false}
                                            activeDot={{ r: 4, strokeWidth: 0 }}
                                        />
                                    </LineChart>
                                </ResponsiveContainer>
                            )}
                        </div>
                    </CardContent>
                </Card>

                {/* Secondary: Breakdown or Distribution */}
                <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base font-medium">Distribuição</CardTitle>
                        <CardDescription>Por tipo de energia</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="h-[250px] flex items-center justify-center">
                            {breakdown.length > 0 ? (
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie
                                            data={breakdown}
                                            innerRadius={60}
                                            outerRadius={90}
                                            paddingAngle={2}
                                            dataKey={viewMode === 'cost' ? 'cost_brl' : 'value_kwh'}
                                        >
                                            {breakdown.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={ENERGY_COLORS[index % ENERGY_COLORS.length]} />
                                            ))}
                                        </Pie>
                                        <Tooltip formatter={(val) => viewMode === 'cost' ? `R$ ${val}` : `${val} kWh`} />
                                        <Legend verticalAlign="bottom" height={36} iconType="circle" iconSize={8} wrapperStyle={{ fontSize: '12px' }} />
                                    </PieChart>
                                </ResponsiveContainer>
                            ) : (
                                <p className="text-sm text-slate-400">Sem dados disponíveis</p>
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Disclaimer / Footer */}
            <div className="text-xs text-center text-slate-400 mt-8">
                MIS-Energy Enterprise • Dados em tempo real
            </div>
        </div>
    );
}
