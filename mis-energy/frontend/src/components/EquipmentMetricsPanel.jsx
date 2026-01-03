import { useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
    X, Zap, Activity, TrendingUp, TrendingDown, DollarSign, Gauge,
    AlertTriangle, RefreshCw, Clock, ArrowUp, ArrowDown
} from 'lucide-react';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    AreaChart, Area, BarChart, Bar
} from 'recharts';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

const METRIC_LABELS = {
    'power_kw': 'Potência (kW)',
    'energy_kwh': 'Energia (kWh)',
    'demand_kw': 'Demanda (kW)',
    'power_factor': 'Fator de Potência'
};

/**
 * EquipmentMetricsPanel - Painel completo de métricas de equipamento
 * 
 * Exibe:
 * - 4 KPIs principais: Potência (kW), Energia (kWh), Demanda (kW max), Fator de Potência
 * - Gráfico de tendência com média móvel
 * - Análise de custo (R$/hora, R$/dia, timeline)
 * - Qualidade de energia (V/A por fase, se disponível)
 */
export function EquipmentMetricsPanel({ equipment, onClose }) {
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [metrics, setMetrics] = useState(null);
    const [history, setHistory] = useState([]);
    const [costAnalysis, setCostAnalysis] = useState(null);
    const [powerQuality, setPowerQuality] = useState(null);
    const [selectedMetric, setSelectedMetric] = useState('power_kw');
    const [selectedPeriod, setSelectedPeriod] = useState('24h');
    const [activeTab, setActiveTab] = useState('overview');

    // Fetch all data
    const fetchData = useCallback(async () => {
        if (!equipment?.id) return;

        setRefreshing(true);
        try {
            const [metricsRes, historyRes, costRes, pqRes] = await Promise.all([
                api.get(`/equipments/${equipment.id}/metrics`),
                api.get(`/equipments/${equipment.id}/history?metric=${selectedMetric}&period=${selectedPeriod}`),
                api.get(`/equipments/${equipment.id}/cost-analysis?period=${selectedPeriod}`),
                api.get(`/equipments/${equipment.id}/power-quality`)
            ]);

            if (metricsRes.success) setMetrics(metricsRes.data);
            if (historyRes.success) setHistory(historyRes.data.history || []);
            if (costRes.success) setCostAnalysis(costRes.data);
            if (pqRes.success) setPowerQuality(pqRes.data);
        } catch (error) {
            console.error("Error fetching metrics:", error);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, [equipment?.id, selectedMetric, selectedPeriod]);

    useEffect(() => {
        fetchData();
        // Auto-refresh every 10 seconds
        const interval = setInterval(fetchData, 10000);
        return () => clearInterval(interval);
    }, [fetchData]);

    // Re-fetch when period changes
    useEffect(() => {
        fetchData();
    }, [selectedPeriod, selectedMetric]);

    if (!equipment) return null;

    const MetricCard = ({ title, value, unit, icon: Icon, color, alert, subtitle }) => (
        <Card className={`relative overflow-hidden ${alert ? 'border-red-500 border-2' : ''}`}>
            <CardContent className="p-4">
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-xs font-medium text-slate-500">{title}</p>
                        <div className="flex items-baseline gap-1 mt-1">
                            <span className={`text-2xl font-bold ${alert ? 'text-red-600' : 'text-slate-900 dark:text-white'}`}>
                                {value !== null && value !== undefined ? Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 2 }) : '--'}
                            </span>
                            <span className="text-sm text-slate-500">{unit}</span>
                        </div>
                        {subtitle && <p className="text-xs text-slate-400 mt-1">{subtitle}</p>}
                    </div>
                    <div className={`p-3 rounded-xl bg-opacity-20`} style={{ backgroundColor: `${color}20` }}>
                        <Icon className="h-6 w-6" style={{ color }} />
                    </div>
                </div>
                {alert && (
                    <div className="absolute top-2 right-2">
                        <AlertTriangle className="h-4 w-4 text-red-500" />
                    </div>
                )}
            </CardContent>
        </Card>
    );

    return (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl w-full max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b">
                    <div>
                        <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <Zap className="h-5 w-5 text-blue-500" />
                            {equipment.name}
                        </h2>
                        <p className="text-sm text-slate-500">{equipment.hierarchy_path}</p>
                    </div>
                    <div className="flex items-center gap-3">
                        <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
                            <SelectTrigger className="w-24">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="1h">1 hora</SelectItem>
                                <SelectItem value="6h">6 horas</SelectItem>
                                <SelectItem value="12h">12 horas</SelectItem>
                                <SelectItem value="24h">24 horas</SelectItem>
                                <SelectItem value="7d">7 dias</SelectItem>
                                <SelectItem value="30d">30 dias</SelectItem>
                            </SelectContent>
                        </Select>
                        <Button variant="outline" size="icon" onClick={fetchData} disabled={refreshing}>
                            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={onClose}>
                            <X className="h-5 w-5" />
                        </Button>
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                    {loading ? (
                        <div className="flex items-center justify-center h-64">
                            <RefreshCw className="h-8 w-8 animate-spin text-blue-500" />
                        </div>
                    ) : (
                        <>
                            {/* KPI Cards */}
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <MetricCard
                                    title="Potência Ativa"
                                    value={metrics?.metrics?.power_kw}
                                    unit="kW"
                                    icon={Zap}
                                    color="#3B82F6"
                                    subtitle="Em tempo real"
                                />
                                <MetricCard
                                    title="Energia Acumulada"
                                    value={metrics?.metrics?.energy_kwh}
                                    unit="kWh"
                                    icon={Activity}
                                    color="#10B981"
                                    subtitle={`Período: ${selectedPeriod}`}
                                />
                                <MetricCard
                                    title="Demanda Máxima"
                                    value={metrics?.metrics?.demand_kw}
                                    unit="kW"
                                    icon={TrendingUp}
                                    color="#F59E0B"
                                    alert={metrics?.alerts?.high_demand}
                                    subtitle="Pico registrado"
                                />
                                <MetricCard
                                    title="Fator de Potência"
                                    value={metrics?.metrics?.power_factor}
                                    unit=""
                                    icon={Gauge}
                                    color="#8B5CF6"
                                    alert={metrics?.alerts?.low_power_factor}
                                    subtitle={metrics?.metrics?.power_factor && metrics.metrics.power_factor < 0.92 ? '⚠️ Abaixo de 0.92' : 'Normal'}
                                />
                            </div>

                            {/* Tabs */}
                            <Tabs value={activeTab} onValueChange={setActiveTab}>
                                <TabsList className="grid grid-cols-3 w-full max-w-md">
                                    <TabsTrigger value="overview">Tendência</TabsTrigger>
                                    <TabsTrigger value="cost">Custo</TabsTrigger>
                                    <TabsTrigger value="quality">Qualidade</TabsTrigger>
                                </TabsList>

                                {/* Trend Chart */}
                                <TabsContent value="overview" className="mt-4">
                                    <Card>
                                        <CardHeader className="pb-2">
                                            <div className="flex items-center justify-between">
                                                <CardTitle className="text-lg">
                                                    Histórico: {METRIC_LABELS[selectedMetric] || 'Potência'}
                                                </CardTitle>
                                                <Select value={selectedMetric} onValueChange={setSelectedMetric}>
                                                    <SelectTrigger className="w-40">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="power_kw">Potência (kW)</SelectItem>
                                                        <SelectItem value="energy_kwh">Energia (kWh)</SelectItem>
                                                        <SelectItem value="demand_kw">Demanda (kW)</SelectItem>
                                                        <SelectItem value="power_factor">Fator de Potência</SelectItem>
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="h-64">
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <AreaChart data={history}>
                                                        <defs>
                                                            <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                                                                <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
                                                                <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                                                            </linearGradient>
                                                        </defs>
                                                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                                        <XAxis
                                                            dataKey="timestamp"
                                                            tickFormatter={(v) => {
                                                                try {
                                                                    return format(new Date(v), 'HH:mm', { locale: ptBR });
                                                                } catch { return v; }
                                                            }}
                                                            stroke="#94a3b8"
                                                            fontSize={12}
                                                        />
                                                        <YAxis stroke="#94a3b8" fontSize={12} />
                                                        <Tooltip
                                                            labelFormatter={(v) => {
                                                                try {
                                                                    return format(new Date(v), 'dd/MM HH:mm', { locale: ptBR });
                                                                } catch { return v; }
                                                            }}
                                                            formatter={(v) => [v?.toFixed(2), 'Valor']}
                                                        />
                                                        <Area
                                                            type="monotone"
                                                            dataKey="value"
                                                            stroke="#3B82F6"
                                                            fillOpacity={1}
                                                            fill="url(#colorValue)"
                                                        />
                                                    </AreaChart>
                                                </ResponsiveContainer>
                                            </div>
                                        </CardContent>
                                    </Card>
                                </TabsContent>

                                {/* Cost Analysis */}
                                <TabsContent value="cost" className="mt-4">
                                    {/* Helper to get context-aware label */}
                                    {(() => {
                                        const getPeriodLabel = () => {
                                            if (selectedPeriod === '1h') return 'Última Hora';
                                            if (selectedPeriod === '24h') return 'Últimas 24h';
                                            if (selectedPeriod === '7d') return 'Últimos 7 dias';
                                            if (selectedPeriod === '30d') return 'Últimos 30 dias';
                                            return 'Período';
                                        };

                                        const getHoursInPeriod = () => {
                                            if (selectedPeriod === '1h') return 1;
                                            if (selectedPeriod === '6h') return 6;
                                            if (selectedPeriod === '12h') return 12;
                                            if (selectedPeriod === '24h') return 24;
                                            if (selectedPeriod === '7d') return 168;
                                            if (selectedPeriod === '30d') return 720;
                                            return 24;
                                        };

                                        const hours = getHoursInPeriod();
                                        // Calculate total cost from timeline if available, or use backend projection
                                        const totalCost = costAnalysis?.timeline?.reduce((acc, curr) => acc + (curr.cost_brl || 0), 0) || 0;
                                        const avgPerHour = totalCost / (hours || 1);

                                        return (
                                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                                                <Card className="bg-green-50 dark:bg-green-900/20">
                                                    <CardContent className="p-4 text-center">
                                                        <DollarSign className="h-8 w-8 mx-auto text-green-600 mb-2" />
                                                        <p className="text-xs text-slate-500">Custo Total ({getPeriodLabel()})</p>
                                                        <p className="text-xl font-bold text-green-600">
                                                            R$ {totalCost.toFixed(2)}
                                                        </p>
                                                    </CardContent>
                                                </Card>
                                                <Card className="bg-blue-50 dark:bg-blue-900/20">
                                                    <CardContent className="p-4 text-center">
                                                        <Clock className="h-8 w-8 mx-auto text-blue-600 mb-2" />
                                                        <p className="text-xs text-slate-500">Custo Médio / Hora</p>
                                                        <p className="text-xl font-bold text-blue-600">
                                                            R$ {avgPerHour.toFixed(2)}
                                                        </p>
                                                    </CardContent>
                                                </Card>
                                                <Card className="bg-purple-50 dark:bg-purple-900/20">
                                                    <CardContent className="p-4 text-center">
                                                        <TrendingUp className="h-8 w-8 mx-auto text-purple-600 mb-2" />
                                                        <p className="text-xs text-slate-500">Projeção Mensal (Baseada no Período)</p>
                                                        <p className="text-xl font-bold text-purple-600">
                                                            R$ {(avgPerHour * 720).toFixed(2)}
                                                        </p>
                                                    </CardContent>
                                                </Card>
                                            </div>
                                        );
                                    })()}

                                    <Card>
                                        <CardHeader className="pb-2">
                                            <CardTitle className="text-lg">Timeline de Consumo</CardTitle>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="h-64">
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <BarChart data={costAnalysis?.timeline || []}>
                                                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                                        <XAxis
                                                            dataKey="timestamp"
                                                            tickFormatter={(v) => {
                                                                try {
                                                                    return format(new Date(v), 'dd/MM', { locale: ptBR });
                                                                } catch { return v; }
                                                            }}
                                                            stroke="#94a3b8"
                                                            fontSize={12}
                                                        />
                                                        <YAxis stroke="#94a3b8" fontSize={12} />
                                                        <Tooltip
                                                            labelFormatter={(v) => {
                                                                try {
                                                                    return format(new Date(v), 'dd/MM/yyyy', { locale: ptBR });
                                                                } catch { return v; }
                                                            }}
                                                            formatter={(v, name) => [
                                                                name === 'cost_brl' ? `R$ ${v?.toFixed(2)}` : `${v?.toFixed(2)} kWh`,
                                                                name === 'cost_brl' ? 'Custo' : 'Energia'
                                                            ]}
                                                        />
                                                        <Bar dataKey="energy_kwh" fill="#10B981" name="energy_kwh" />
                                                    </BarChart>
                                                </ResponsiveContainer>
                                            </div>
                                        </CardContent>
                                    </Card>
                                </TabsContent>

                                {/* Power Quality */}
                                <TabsContent value="quality" className="mt-4">
                                    {powerQuality?.available === false ? (
                                        <Card>
                                            <CardContent className="p-8 text-center">
                                                <AlertTriangle className="h-12 w-12 mx-auto text-yellow-500 mb-4" />
                                                <p className="text-lg text-slate-600">{powerQuality?.message || 'Qualidade de energia não configurada'}</p>
                                                <p className="text-sm text-slate-400 mt-2">Configure os endereços de tensão e corrente por fase no cadastro do equipamento.</p>
                                            </CardContent>
                                        </Card>
                                    ) : (
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            {/* Voltage */}
                                            <Card>
                                                <CardHeader className="pb-2">
                                                    <CardTitle className="text-lg flex items-center gap-2">
                                                        <Zap className="h-5 w-5 text-yellow-500" />
                                                        Tensão por Fase
                                                    </CardTitle>
                                                </CardHeader>
                                                <CardContent>
                                                    <div className="space-y-3">
                                                        {['a', 'b', 'c'].map((phase) => (
                                                            <div key={phase} className="flex items-center justify-between">
                                                                <span className="font-medium text-slate-600 uppercase">Fase {phase}</span>
                                                                <span className="text-xl font-bold">
                                                                    {powerQuality?.power_quality?.voltage?.[phase]?.toFixed(1) || '--'} V
                                                                </span>
                                                            </div>
                                                        ))}
                                                        <div className="border-t pt-3 mt-3">
                                                            <div className="flex items-center justify-between text-sm">
                                                                <span className="text-slate-500">Desequilíbrio</span>
                                                                <Badge variant={powerQuality?.alerts?.voltage_imbalance ? 'destructive' : 'outline'}>
                                                                    {powerQuality?.analysis?.voltage_imbalance_pct?.toFixed(2) || '0'}%
                                                                </Badge>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>

                                            {/* Current */}
                                            <Card>
                                                <CardHeader className="pb-2">
                                                    <CardTitle className="text-lg flex items-center gap-2">
                                                        <Activity className="h-5 w-5 text-blue-500" />
                                                        Corrente por Fase
                                                    </CardTitle>
                                                </CardHeader>
                                                <CardContent>
                                                    <div className="space-y-3">
                                                        {['a', 'b', 'c'].map((phase) => (
                                                            <div key={phase} className="flex items-center justify-between">
                                                                <span className="font-medium text-slate-600 uppercase">Fase {phase}</span>
                                                                <span className="text-xl font-bold">
                                                                    {powerQuality?.power_quality?.current?.[phase]?.toFixed(1) || '--'} A
                                                                </span>
                                                            </div>
                                                        ))}
                                                        <div className="border-t pt-3 mt-3">
                                                            <div className="flex items-center justify-between text-sm">
                                                                <span className="text-slate-500">Corrente Total</span>
                                                                <span className="font-medium">{powerQuality?.analysis?.total_current?.toFixed(1) || '--'} A</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        </div>
                                    )}
                                </TabsContent>
                            </Tabs>
                        </>
                    )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between p-4 border-t bg-slate-50 dark:bg-slate-800">
                    <div className="text-sm text-slate-500">
                        Tarifa: R$ {metrics?.cost?.tariff_kwh?.toFixed(2) || '0.50'}/kWh
                    </div>
                    <div className="text-sm text-slate-500 flex items-center gap-2">
                        <Clock className="h-4 w-4" />
                        Última atualização: {metrics?.timestamp ? format(new Date(metrics.timestamp), 'HH:mm:ss', { locale: ptBR }) : '--'}
                    </div>
                </div>
            </div >
        </div >
    );
}
