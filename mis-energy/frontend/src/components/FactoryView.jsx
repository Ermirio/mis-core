import { useState, useEffect } from 'react';
import api from '../services/api';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, RefreshCw, Factory, Layers, Activity, Zap, DollarSign } from "lucide-react";
import { Button } from "@/components/ui/button";

export function FactoryView() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [lastUpdate, setLastUpdate] = useState(new Date());

    const fetchData = async () => {
        setRefreshing(true);
        try {
            const response = await api.get('/analytics/factory-view');
            if (response.success) {
                setData(response.data);
                setLastUpdate(new Date());
            }
        } catch (error) {
            console.error("Erro ao buscar dados da fábrica:", error);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 30000); // 30s refresh
        return () => clearInterval(interval);
    }, []);

    if (loading && !data) {
        return (
            <div className="flex items-center justify-center h-screen bg-slate-50 dark:bg-slate-950">
                <Loader2 className="h-10 w-10 animate-spin text-blue-500" />
            </div>
        );
    }

    const AggregationCard = ({ title, icon: Icon, colorClass, data }) => (
        <Card className="border-none shadow-md bg-white dark:bg-slate-900 overflow-hidden relative group">
            <div className={`absolute top-0 left-0 w-1 h-full ${colorClass.replace('text-', 'bg-')} opacity-60`}></div>
            <CardContent className="p-6">
                <div className="flex justify-between items-start mb-4">
                    <div className={`p-3 rounded-2xl ${colorClass.replace('text-', 'bg-').replace('500', '50')} dark:bg-opacity-20`}>
                        <Icon className={`h-8 w-8 ${colorClass}`} />
                    </div>
                    <div className="text-right">
                        <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest">{title}</p>
                    </div>
                </div>

                <div className="space-y-4">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <Zap className="h-4 w-4 text-slate-400" />
                            <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Potência Total</span>
                        </div>
                        <p className="text-3xl font-bold text-slate-900 dark:text-white tracking-tight">
                            {data ? data.power_kw.toLocaleString('pt-BR', { minimumFractionDigits: 1 }) : '--'}
                            <span className="text-lg text-slate-400 font-normal ml-1">kW</span>
                        </p>
                    </div>

                    <div className="pt-4 border-t border-slate-100 dark:border-slate-800">
                        <div className="flex items-center gap-2 mb-1">
                            <DollarSign className="h-4 w-4 text-slate-400" />
                            <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Custo Estimado</span>
                        </div>
                        <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 tracking-tight">
                            R$ {data ? data.cost_hour.toLocaleString('pt-BR', { minimumFractionDigits: 2 }) : '--'}
                            <span className="text-sm text-slate-400 font-normal ml-1">/ hora</span>
                        </p>
                    </div>
                </div>
            </CardContent>
        </Card>
    );

    return (
        <div className="flex flex-col h-[calc(100vh-80px)] p-6 bg-slate-50/50 dark:bg-slate-950/50 gap-6 overflow-y-auto">
            {/* Header */}
            <div className="flex items-center justify-between bg-white dark:bg-slate-900 rounded-xl p-5 shadow-sm border border-slate-200/50 dark:border-slate-800 shrink-0">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
                        <Factory className="h-6 w-6 text-slate-700" />
                        Visão Geral da Fábrica
                    </h1>
                    <p className="text-sm text-slate-500 mt-1">
                        Monitoramento consolidado de energia e custos em tempo real
                    </p>
                </div>

                <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded-md border border-slate-200 dark:border-slate-700">
                        Atualizado: {lastUpdate.toLocaleTimeString()}
                    </span>
                    <Button
                        variant="outline"
                        size="icon"
                        onClick={fetchData}
                        disabled={refreshing}
                        className="hover:bg-blue-50 hover:text-blue-600 border-slate-200 dark:border-slate-700"
                    >
                        <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
                    </Button>
                </div>
            </div>

            {/* Main Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <AggregationCard
                    title="Total Fábrica"
                    icon={Factory}
                    colorClass="text-blue-600"
                    data={data?.factory}
                />
                <AggregationCard
                    title="Total Áreas"
                    icon={Layers}
                    colorClass="text-purple-600"
                    data={data?.areas}
                />
                <AggregationCard
                    title="Total Linhas"
                    icon={Activity}
                    colorClass="text-amber-600"
                    data={data?.lines}
                />
                <AggregationCard
                    title="Total Equipamentos"
                    icon={Zap}
                    colorClass="text-orange-600"
                    data={data?.equipments}
                />
            </div>

            {/* Detailed Analysis Section (Placeholder / Future Expansion) */}
            <div className="mt-4 p-6 bg-white dark:bg-slate-900 rounded-xl border border-slate-200/50 dark:border-slate-800 shadow-sm flex-1">
                <div className="flex items-center gap-2 mb-6">
                    <Activity className="h-5 w-5 text-slate-400" />
                    <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-200">Detalhamento de Distribuição</h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 h-64">
                    <div className="flex items-center justify-center bg-slate-50/50 border border-dashed border-slate-200 rounded-lg">
                        <p className="text-slate-400 text-sm">Gráfico de Pizza: Consumo por Área (Em Breve)</p>
                    </div>
                    <div className="flex items-center justify-center bg-slate-50/50 border border-dashed border-slate-200 rounded-lg">
                        <p className="text-slate-400 text-sm">Tendência de Custo Total - Últimas 24h (Em Breve)</p>
                    </div>
                </div>
            </div>
        </div>
    );
}
