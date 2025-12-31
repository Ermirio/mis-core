import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Area, AreaChart } from 'recharts';
import { TrendingUp } from 'lucide-react';

interface ThroughputDataPoint {
    timestamp: string;
    vazao: number;
    toneladas: number;
}

interface ThroughputChartProps {
    data: ThroughputDataPoint[];
    meta?: number;
    periodo: 'hora' | 'turno' | 'dia';
    loading?: boolean;
}

export default function ThroughputChart({
    data,
    meta,
    periodo,
    loading = false
}: ThroughputChartProps) {
    // Formatar timestamp para exibição
    const formatTimestamp = (timestamp: string) => {
        const date = new Date(timestamp);

        switch (periodo) {
            case 'hora':
                return date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
            case 'turno':
                return date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
            case 'dia':
                return date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
            default:
                return date.toLocaleString('pt-BR');
        }
    };

    // Tooltip customizado
    const CustomTooltip = ({ active, payload }: any) => {
        if (active && payload && payload.length) {
            const data = payload[0].payload;
            return (
                <div className="bg-white dark:bg-gray-800 p-3 border border-gray-200 dark:border-gray-700 rounded shadow-lg">
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                        {formatTimestamp(data.timestamp)}
                    </p>
                    <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                        Vazão: <span className="text-blue-600 dark:text-blue-400">{data.vazao.toFixed(3)} t/h</span>
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                        Total: {data.toneladas.toFixed(3)} t
                    </p>
                    {meta && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                            Meta: {meta.toFixed(1)} t/h ({((data.vazao / meta) * 100).toFixed(1)}%)
                        </p>
                    )}
                </div>
            );
        }
        return null;
    };

    if (loading) {
        return (
            <Card className="border-gray-200 dark:border-gray-700">
                <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                        <TrendingUp className="w-5 h-5" />
                        Vazão ao Longo do Tempo
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="h-64 flex items-center justify-center">
                        <div className="animate-pulse text-gray-400">Carregando dados...</div>
                    </div>
                </CardContent>
            </Card>
        );
    }

    if (!data || data.length === 0) {
        return (
            <Card className="border-gray-200 dark:border-gray-700">
                <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                        <TrendingUp className="w-5 h-5" />
                        Vazão ao Longo do Tempo
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="h-64 flex items-center justify-center text-gray-400">
                        Sem dados disponíveis
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="border-gray-200 dark:border-gray-700">
            <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                    <TrendingUp className="w-5 h-5" />
                    Vazão ao Longo do Tempo
                </CardTitle>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    Toneladas por hora - {data.length} registros
                </p>
            </CardHeader>
            <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                        <defs>
                            <linearGradient id="colorVazao" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" className="dark:stroke-gray-700" />
                        <XAxis
                            dataKey="timestamp"
                            tickFormatter={formatTimestamp}
                            stroke="#9ca3af"
                            style={{ fontSize: '12px' }}
                        />
                        <YAxis
                            stroke="#9ca3af"
                            style={{ fontSize: '12px' }}
                            label={{ value: 't/h', angle: -90, position: 'insideLeft', style: { fontSize: '12px', fill: '#9ca3af' } }}
                        />
                        <Tooltip content={<CustomTooltip />} />

                        {/* Linha de meta */}
                        {meta && (
                            <ReferenceLine
                                y={meta}
                                stroke="#10b981"
                                strokeDasharray="5 5"
                                label={{
                                    value: `Meta: ${meta.toFixed(1)} t/h`,
                                    position: 'right',
                                    fill: '#10b981',
                                    fontSize: 12
                                }}
                            />
                        )}

                        {/* Área e linha de vazão */}
                        <Area
                            type="monotone"
                            dataKey="vazao"
                            stroke="#3b82f6"
                            strokeWidth={2}
                            fill="url(#colorVazao)"
                        />
                    </AreaChart>
                </ResponsiveContainer>

                {/* Legenda */}
                <div className="flex items-center justify-center gap-6 mt-4 text-xs">
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                        <span className="text-gray-600 dark:text-gray-400">Vazão Real</span>
                    </div>
                    {meta && (
                        <div className="flex items-center gap-2">
                            <div className="w-3 h-0.5 bg-green-500"></div>
                            <span className="text-gray-600 dark:text-gray-400">Meta</span>
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}