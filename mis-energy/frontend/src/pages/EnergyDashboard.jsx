import { useState, useEffect, useRef } from 'react';
import api from '../services/api';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DateRangePicker } from "@/components/ui/DateRangePicker";
import {
    TrendingUp, TrendingDown, Minus, Zap, DollarSign, Activity, Clock,
    Download, RefreshCw, AlertTriangle, CheckCircle, Info, Loader2
} from 'lucide-react';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    PieChart, Pie, Cell, BarChart, Bar
} from 'recharts';
import { format, subDays } from 'date-fns';
import { ptBR } from 'date-fns/locale';

// Paleta de cores
const COLORS = {
    primary: '#3B82F6',
    secondary: '#10B981',
    warning: '#F59E0B',
    danger: '#EF4444',
    purple: '#8B5CF6',
    cyan: '#06B6D4',
    pink: '#EC4899'
};

const ENERGY_COLORS = ['#3B82F6', '#F59E0B', '#10B981', '#8B5CF6'];

export function EnergyDashboard() {
    const [loading, setLoading] = useState(true);
    const [summary, setSummary] = useState(null);
    const [timeSeries, setTimeSeries] = useState([]);
    const [breakdown, setBreakdown] = useState([]);
    const [heatmapData, setHeatmapData] = useState([]);
    const [insights, setInsights] = useState([]);
    const [period, setPeriod] = useState('hourly');
    const [unit, setUnit] = useState('kwh');
    const chartRef = useRef(null);

    // Date range state
    const [startDate, setStartDate] = useState(() => {
        const d = new Date();
        d.setHours(d.getHours() - 12);
        return d;
    });
    const [endDate, setEndDate] = useState(new Date());

    // Handle date range change
    const handleDateRangeChange = (start, end) => {
        setStartDate(start);
        setEndDate(end);
        // Re-fetch data with new date range (if API supports it)
        fetchDashboardData();
    };

    // Fetch all dashboard data
    const fetchDashboardData = async () => {
        setLoading(true);
        try {
            // Format dates for API
            const startParam = startDate.toISOString();
            const endParam = endDate.toISOString();
            const dateParams = `start_time=${startParam}&end_time=${endParam}`;

            const [summaryRes, timeSeriesRes, breakdownRes, heatmapRes, insightsRes] = await Promise.all([
                api.get(`/analytics/dashboard-summary?${dateParams}`),
                api.get(`/analytics/time-series?period=${period}&${dateParams}`),
                api.get(`/analytics/energy-breakdown?${dateParams}`),
                api.get(`/analytics/heatmap?${dateParams}`),
                api.get(`/analytics/insights?${dateParams}`)
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

    useEffect(() => {
        fetchDashboardData();
        const interval = setInterval(fetchDashboardData, 60000); // Atualizar a cada minuto
        return () => clearInterval(interval);
    }, [period, startDate, endDate]);

    // Export to CSV
    const handleExportCSV = async () => {
        try {
            const response = await fetch('/mis-energy-api/api/analytics/export-csv?type=time-series');
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `energy_data_${format(new Date(), 'yyyyMMdd_HHmmss')}.csv`;
            a.click();
        } catch (error) {
            console.error('Erro ao exportar CSV:', error);
        }
    };

    // Trend Icon Component
    const TrendIcon = ({ value }) => {
        if (value > 0) return <TrendingUp className="h-4 w-4 text-red-500" />;
        if (value < 0) return <TrendingDown className="h-4 w-4 text-green-500" />;
        return <Minus className="h-4 w-4 text-gray-500" />;
    };

    // Summary Card Component - COMPACT VERSION
    const SummaryCard = ({ title, value, unit: cardUnit, delta, icon: Icon, color }) => (
        <Card className="relative overflow-hidden">
            <CardContent className="p-3 flex items-center gap-3">
                <div className={`p-2 rounded-lg flex-shrink-0`} style={{ backgroundColor: `${color}20` }}>
                    <Icon className="h-5 w-5" style={{ color }} />
                </div>
                <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-slate-500 truncate">{title}</p>
                    <div className="flex items-baseline gap-1">
                        <p className="text-lg font-bold text-slate-900 dark:text-white truncate">
                            {typeof value === 'number' ? value.toLocaleString('pt-BR') : value}
                        </p>
                        {cardUnit && <span className="text-xs text-slate-500">{cardUnit}</span>}
                    </div>
                </div>
                {delta !== undefined && (
                    <div className={`flex items-center text-xs flex-shrink-0 ${delta > 0 ? 'text-red-600' : delta < 0 ? 'text-green-600' : 'text-gray-500'}`}>
                        <TrendIcon value={delta} />
                        <span className="ml-0.5">{Math.abs(delta).toFixed(1)}%</span>
                    </div>
                )}
            </CardContent>
        </Card>
    );

    // Heatmap Component
    const Heatmap = ({ data }) => {
        if (!data?.data) return null;

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
                <div className="grid gap-1" style={{ gridTemplateColumns: `60px repeat(24, 1fr)` }}>
                    {/* Header */}
                    <div></div>
                    {Array.from({ length: 24 }, (_, i) => (
                        <div key={i} className="text-xs text-center text-slate-500 py-1">
                            {i}h
                        </div>
                    ))}

                    {/* Rows */}
                    {days.map((day, dayIdx) => (
                        <>
                            <div key={`day-${dayIdx}`} className="text-xs text-right pr-2 py-2 text-slate-600 font-medium">
                                {day}
                            </div>
                            {Array.from({ length: 24 }, (_, hour) => {
                                const cellData = data.data.find(d => d.day_index === dayIdx && d.hour === hour);
                                const value = cellData?.value || 0;
                                return (
                                    <div
                                        key={`${dayIdx}-${hour}`}
                                        className="h-8 rounded-sm cursor-pointer transition-transform hover:scale-110 hover:z-10"
                                        style={{ backgroundColor: getColor(value) }}
                                        title={`${day} ${hour}:00 - ${value} kWh`}
                                    />
                                );
                            })}
                        </>
                    ))}
                </div>

                {/* Legend */}
                <div className="flex items-center justify-center gap-4 mt-4 text-xs">
                    <div className="flex items-center gap-1">
                        <div className="w-4 h-4 rounded" style={{ backgroundColor: '#10B981' }} />
                        <span>Baixo</span>
                    </div>
                    <div className="flex items-center gap-1">
                        <div className="w-4 h-4 rounded" style={{ backgroundColor: '#F59E0B' }} />
                        <span>Médio</span>
                    </div>
                    <div className="flex items-center gap-1">
                        <div className="w-4 h-4 rounded" style={{ backgroundColor: '#EF4444' }} />
                        <span>Alto</span>
                    </div>
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
                        <p className="font-medium">{insight.title}</p>
                        <p className="text-sm mt-1 opacity-80">{insight.description}</p>
                        {insight.recommendation && (
                            <p className="text-xs mt-2 italic opacity-70">
                                💡 {insight.recommendation}
                            </p>
                        )}
                    </div>
                </div>
            </div>
        );
    };

    if (loading && !summary) {
        return (
            <div className="flex items-center justify-center h-screen">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            </div>
        );
    }

    return (
        <div className="p-6 space-y-6 bg-slate-50/50 dark:bg-slate-950/50 min-h-screen">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white tracking-tight">
                        Analytics de Energia
                    </h1>
                    <p className="text-slate-500 mt-1">
                        Monitoramento e análise de consumo energético
                    </p>
                </div>

                <div className="flex items-center gap-3">
                    <DateRangePicker
                        startDate={startDate}
                        endDate={endDate}
                        onRangeChange={handleDateRangeChange}
                    />

                    <Select value={unit} onValueChange={setUnit}>
                        <SelectTrigger className="w-32">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="kwh">kWh</SelectItem>
                            <SelectItem value="cost">R$</SelectItem>
                            <SelectItem value="intensity">kWh/ton</SelectItem>
                        </SelectContent>
                    </Select>

                    <Button variant="outline" size="icon" onClick={fetchDashboardData}>
                        <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                    </Button>

                    <Button variant="outline" onClick={handleExportCSV}>
                        <Download className="h-4 w-4 mr-2" />
                        Exportar CSV
                    </Button>
                </div>
            </div>

            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <SummaryCard
                    title="Consumo Total"
                    value={summary?.current?.consumption_kwh || 0}
                    unit="kWh"
                    delta={summary?.delta?.consumption_percent}
                    icon={Zap}
                    color={COLORS.primary}
                />
                <SummaryCard
                    title="Custo Total"
                    value={`R$ ${(summary?.current?.cost_brl || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`}
                    unit=""
                    delta={summary?.delta?.cost_percent}
                    icon={DollarSign}
                    color={COLORS.secondary}
                />
                <SummaryCard
                    title="Eficiência"
                    value={summary?.current?.efficiency_kwh_ton || 0}
                    unit="kWh/ton"
                    delta={summary?.delta?.efficiency_percent}
                    icon={Activity}
                    color={COLORS.purple}
                />
                <SummaryCard
                    title="Dias no Período"
                    value={summary?.period?.days || 7}
                    unit="dias"
                    icon={Clock}
                    color={COLORS.warning}
                />
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Time Series Chart */}
                <Card className="lg:col-span-2">
                    <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-lg">Consumo ao Longo do Tempo</CardTitle>
                            <Tabs value={period} onValueChange={setPeriod}>
                                <TabsList className="h-8">
                                    <TabsTrigger value="hourly" className="text-xs px-3">Horário</TabsTrigger>
                                    <TabsTrigger value="daily" className="text-xs px-3">Diário</TabsTrigger>
                                    <TabsTrigger value="weekly" className="text-xs px-3">Semanal</TabsTrigger>
                                </TabsList>
                            </Tabs>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div ref={chartRef} className="h-[300px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={timeSeries}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                                    <XAxis
                                        dataKey="label"
                                        tick={{ fontSize: 12 }}
                                        stroke="#94A3B8"
                                    />
                                    <YAxis
                                        yAxisId="left"
                                        tick={{ fontSize: 12 }}
                                        stroke="#94A3B8"
                                        tickFormatter={(v) => `${v}`}
                                    />
                                    <YAxis
                                        yAxisId="right"
                                        orientation="right"
                                        tick={{ fontSize: 12 }}
                                        stroke="#94A3B8"
                                        tickFormatter={(v) => `R$${v}`}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: '#1E293B',
                                            border: 'none',
                                            borderRadius: '8px',
                                            color: '#fff'
                                        }}
                                        formatter={(value, name) => [
                                            name === 'consumption_kwh'
                                                ? `${value.toLocaleString('pt-BR')} kWh`
                                                : `R$ ${value.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`,
                                            name === 'consumption_kwh' ? 'Consumo' : 'Custo'
                                        ]}
                                    />
                                    <Legend />
                                    <Line
                                        yAxisId="left"
                                        type="monotone"
                                        dataKey="consumption_kwh"
                                        name="Consumo (kWh)"
                                        stroke={COLORS.primary}
                                        strokeWidth={2}
                                        dot={false}
                                        activeDot={{ r: 6 }}
                                    />
                                    <Line
                                        yAxisId="right"
                                        type="monotone"
                                        dataKey="cost_brl"
                                        name="Custo (R$)"
                                        stroke={COLORS.secondary}
                                        strokeWidth={2}
                                        dot={false}
                                        activeDot={{ r: 6 }}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </CardContent>
                </Card>

                {/* Breakdown Chart */}
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-lg">Consumo por Tipo</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="h-[300px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie
                                        data={breakdown}
                                        dataKey="value_kwh"
                                        nameKey="name"
                                        cx="50%"
                                        cy="50%"
                                        outerRadius={80}
                                        innerRadius={50}
                                        paddingAngle={2}
                                        label={({ name, percentage }) => `${name} (${percentage}%)`}
                                        labelLine={false}
                                    >
                                        {breakdown.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={entry.color || ENERGY_COLORS[index % ENERGY_COLORS.length]} />
                                        ))}
                                    </Pie>
                                    <Tooltip
                                        formatter={(value, name) => [`${value.toLocaleString('pt-BR')} kWh`, name]}
                                    />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                        {/* Legend below chart */}
                        <div className="grid grid-cols-2 gap-2 mt-4">
                            {breakdown.map((item, index) => (
                                <div key={index} className="flex items-center gap-2 text-sm">
                                    <div
                                        className="w-3 h-3 rounded-full"
                                        style={{ backgroundColor: item.color || ENERGY_COLORS[index % ENERGY_COLORS.length] }}
                                    />
                                    <span className="text-slate-600 dark:text-slate-400">{item.name}</span>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Bottom Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Heatmap */}
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-lg">Consumo por Dia/Hora</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <Heatmap data={heatmapData} />
                    </CardContent>
                </Card>

                {/* Insights Panel */}
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-lg">Insights e Recomendações</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-3">
                            {insights.length > 0 ? (
                                insights.map((insight, index) => (
                                    <InsightCard key={index} insight={insight} />
                                ))
                            ) : (
                                <div className="text-center text-slate-500 py-8">
                                    <Info className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                    <p>Nenhum insight disponível no momento</p>
                                </div>
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Footer */}
            <div className="text-center text-sm text-slate-400 pt-4 border-t">
                Última atualização: {format(new Date(), "dd 'de' MMMM 'de' yyyy 'às' HH:mm", { locale: ptBR })}
            </div>
        </div>
    );
}
