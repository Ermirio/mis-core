import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { AlertCircle, RefreshCw, Trash2 } from 'lucide-react';

interface AnalysisData {
    periodo: string;
    total_waste: number;
    unit?: string;
    by_equipment: { name: string; value: number; share: number }[];
    by_state: { id: string; label: string; value: number; share: number }[];
}

interface LossWasteProps {
    lineId?: string;
    mode?: 'line' | 'factory';
}

const COLORS_BY_STATE: Record<string, string> = {
    'Produzindo': '#22c55e', // Green
    'Parado/Desligado': '#ef4444', // Red
    'Falha/Quebra': '#dc2626', // Dark Red
    'Aguardando': '#eab308', // Yellow
    'Bloqueado': '#f97316', // Orange
    'Setup': '#3b82f6', // Blue
    'Manutenção': '#a855f7', // Purple
    'Teste/Engenharia': '#06b6d4', // Cyan
    'Falta Material': '#ec4899', // Pink
    'Partindo': '#84cc16', // Lime
    'Aguardando Condições': '#f59e0b', // Amber
    'Parando': '#f43f5e', // Rose
    'Outro': '#6b7280' // Gray
};

const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || 'http://localhost:8000/api';

export function LossWasteAnalysis({ lineId, mode = 'line' }: LossWasteProps) {
    const [periodo, setPeriodo] = useState('TURNO');
    const [data, setData] = useState<AnalysisData | null>(null);
    const [loading, setLoading] = useState(false); // Initial load
    const [error, setError] = useState<string | null>(null);

    const fetchData = async (isBackground = false) => {
        if (!isBackground) setLoading(true);
        setError(null);
        try {
            let url = '';
            if (mode === 'factory') {
                url = `${DJANGO_API_URL}/fabrica/waste-analysis/?periodo=${periodo}`;
            } else if (lineId) {
                url = `${DJANGO_API_URL}/linhas/${lineId}/waste-analysis/?periodo=${periodo}`;
            } else {
                return;
            }

            const res = await fetch(url);
            if (!res.ok) throw new Error('Falha ao carregar dados de refugo');

            const json = await res.json();
            setData(json);
        } catch (err: any) {
            console.error(err);
            if (!isBackground) setError(err.message);
        } finally {
            if (!isBackground) setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(() => fetchData(true), 30000); // 30s refresh
        return () => clearInterval(interval);
    }, [lineId, mode, periodo]);

    const formatValue = (val: number) => {
        if (data?.unit === 'ton') return `${val.toFixed(3)} t`;
        // Default: unidades (inteiro)
        return `${Math.round(val)} un`;
    };

    if (error) {
        return (
            <Card className="bg-gray-800 border-gray-700 mt-6">
                <CardContent className="p-6 text-center text-red-400">
                    <AlertCircle className="mx-auto mb-2 w-8 h-8" />
                    <p>{error}</p>
                    <Button variant="outline" size="sm" onClick={() => fetchData()} className="mt-4 border-gray-600 text-gray-300">
                        Tentar Novamente
                    </Button>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="bg-gray-800 border-gray-700 shadow-xl mt-6">
            <CardHeader className="flex flex-row items-center justify-between pb-2 border-b border-gray-700/50">
                <div className="flex items-center gap-2">
                    <div className="p-2 bg-red-500/20 rounded-lg">
                        <Trash2 className="w-5 h-5 text-red-500" />
                    </div>
                    <div>
                        <CardTitle className="text-lg font-bold text-white">
                            {mode === 'factory' ? 'Análise Global de Perdas (Toneladas)' : 'Análise de Descarte'}
                        </CardTitle>
                        <p className="text-xs text-gray-400 mt-1">
                            Refugo acumulado por equipamento e correlação de estados
                        </p>
                    </div>
                </div>

                <div className="flex bg-gray-900 rounded-lg p-1 border border-gray-700">
                    {['TURNO', 'DIA', 'SEMANA', 'MES'].map((p) => (
                        <button
                            key={p}
                            onClick={() => setPeriodo(p)}
                            disabled={loading}
                            className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${periodo === p
                                ? 'bg-red-600 text-white shadow-lg shadow-red-900/20'
                                : 'text-gray-400 hover:text-white hover:bg-gray-800'
                                }`}
                        >
                            {p}
                        </button>
                    ))}
                    <button onClick={() => fetchData()} className="ml-2 p-1 text-gray-400 hover:text-white" disabled={loading}>
                        <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                </div>
            </CardHeader>

            <CardContent className="pt-6">
                {loading && !data ? (
                    <div className="flex justify-center items-center h-64">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-500"></div>
                    </div>
                ) : !data ? (
                    <div className="text-center text-gray-500 py-10">Nenhum dado disponível</div>
                ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                        {/* LEFT: DONUT CHART (Estados) */}
                        <div className="space-y-4">
                            <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                                <span className="w-2 h-2 rounded-full bg-red-500"></span>
                                Origem do Descarte (Por Estado da Máquina)
                            </h3>
                            <div className="h-[250px] w-full relative">
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie
                                            data={data.by_state}
                                            dataKey="value"
                                            nameKey="label"
                                            cx="50%"
                                            cy="50%"
                                            innerRadius={60}
                                            outerRadius={90}
                                            paddingAngle={2}
                                            stroke="none"
                                            label={({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
                                                const RADIAN = Math.PI / 180;
                                                const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
                                                const x = cx + radius * Math.cos(-midAngle * RADIAN);
                                                const y = cy + radius * Math.sin(-midAngle * RADIAN);
                                                return percent > 0.05 ? (
                                                    <text x={x} y={y} fill="white" textAnchor={x > cx ? 'start' : 'end'} dominantBaseline="central" fontSize={10} fontWeight="bold">
                                                        {`${(percent * 100).toFixed(0)}%`}
                                                    </text>
                                                ) : null;
                                            }}
                                        >
                                            {data.by_state.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={COLORS_BY_STATE[entry.label] || COLORS_BY_STATE['Outro']} />
                                            ))}
                                        </Pie>
                                        <Tooltip
                                            contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', borderRadius: '8px' }}
                                            itemStyle={{ color: '#e5e7eb' }}
                                            formatter={(val: number) => formatValue(val)}
                                        />
                                        <Legend
                                            layout="vertical"
                                            verticalAlign="middle"
                                            align="right"
                                            iconType="circle"
                                            iconSize={8}
                                            wrapperStyle={{ fontSize: '11px', color: '#9ca3af' }}
                                        />
                                    </PieChart>
                                </ResponsiveContainer>

                                <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-center pointer-events-none">
                                    <p className="text-2xl font-bold text-white">{data.total_waste.toFixed(data.unit === 'ton' ? 3 : 0)}</p>
                                    <p className="text-xs text-gray-400">{data.unit === 'ton' ? 'Toneladas' : 'Unidades'}</p>
                                </div>
                            </div>
                        </div>

                        {/* RIGHT: RANKING (Equipamentos) */}
                        <div className="space-y-4">
                            <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                                <span className="w-2 h-2 rounded-full bg-orange-500"></span>
                                Top Geradores de Refugo
                            </h3>
                            <div className="space-y-3 pr-2 max-h-[250px] overflow-y-auto custom-scrollbar">
                                {data.by_equipment.map((item, idx) => (
                                    <div key={idx} className="bg-gray-900/50 p-3 rounded-lg border border-gray-800 flex items-center justify-between group hover:border-gray-700 transition-all">
                                        <div className="flex-1 min-w-0">
                                            <div className="flex justify-between mb-1">
                                                <span className="text-sm font-medium text-gray-200 truncate pr-2">{item.name}</span>
                                                <span className="text-sm font-bold text-red-400">{formatValue(item.value)}</span>
                                            </div>
                                            <div className="w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
                                                <div
                                                    className="bg-gradient-to-r from-orange-600 to-red-600 h-1.5 rounded-full shadow-[0_0_10px_rgba(220,38,38,0.5)]"
                                                    style={{ width: `${item.share}%` }}
                                                />
                                            </div>
                                        </div>
                                        <div className="ml-4 text-xs font-mono text-gray-500 min-w-[40px] text-right">
                                            {item.share.toFixed(1)}%
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
