import React from 'react';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    Line,
    ComposedChart,
    ResponsiveContainer
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertTriangle } from 'lucide-react';

interface ParetoDataPoint {
    motivo: string;
    descricao: string;
    tempo_total_minutos: number;
    frequencia: number;
    percentual: number;
    percentual_acumulado: number;
}

interface ParetoChartProps {
    data: ParetoDataPoint[];
    loading?: boolean;
}

export default function ParetoChart({ data, loading = false }: ParetoChartProps) {
    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <AlertTriangle className="w-5 h-5" />
                        Principais Motivos de Parada (Pareto)
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="h-80 flex items-center justify-center">
                        <div className="animate-pulse space-y-3 w-full">
                            <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                            <div className="h-4 bg-gray-200 rounded w-1/2"></div>
                            <div className="h-4 bg-gray-200 rounded w-5/6"></div>
                        </div>
                    </div>
                </CardContent>
            </Card>
        );
    }

    if (!data || data.length === 0) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <AlertTriangle className="w-5 h-5" />
                        Principais Motivos de Parada (Pareto)
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="h-80 flex items-center justify-center text-gray-400">
                        Sem dados de paradas no período selecionado
                    </div>
                </CardContent>
            </Card>
        );
    }

    // Formata dados para o gráfico
    const chartData = data.slice(0, 10).map(item => ({
        name: item.descricao.substring(0, 20) + (item.descricao.length > 20 ? '...' : ''),
        tempo: item.tempo_total_minutos,
        acumulado: item.percentual_acumulado,
        frequencia: item.frequencia
    }));

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5 text-red-500" />
                    Principais Motivos de Parada (Pareto)
                </CardTitle>
                <p className="text-sm text-gray-500 mt-1">
                    Top 10 causas de downtime - Identifique onde atuar prioritariamente
                </p>
            </CardHeader>
            <CardContent>
                <ResponsiveContainer width="100%" height={400}>
                    <ComposedChart
                        data={chartData}
                        margin={{ top: 20, right: 30, left: 20, bottom: 70 }}
                    >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                            dataKey="name"
                            angle={-45}
                            textAnchor="end"
                            height={100}
                            tick={{ fontSize: 12 }}
                        />
                        <YAxis
                            yAxisId="left"
                            orientation="left"
                            label={{ value: 'Tempo (min)', angle: -90, position: 'insideLeft' }}
                        />
                        <YAxis
                            yAxisId="right"
                            orientation="right"
                            label={{ value: '% Acumulado', angle: 90, position: 'insideRight' }}
                            domain={[0, 100]}
                        />
                        <Tooltip
                            contentStyle={{ backgroundColor: 'white', border: '1px solid #ccc' }}
                            formatter={(value: number, name: string) => {
                                if (name === 'tempo') return [`${value.toFixed(2)} min`, 'Tempo de Parada'];
                                if (name === 'acumulado') return [`${value.toFixed(1)}%`, '% Acumulado'];
                                if (name === 'frequencia') return [`${value}x`, 'Ocorrências'];
                                return [value, name];
                            }}
                        />
                        <Legend />
                        <Bar
                            yAxisId="left"
                            dataKey="tempo"
                            fill="#ef4444"
                            name="Tempo de Parada (min)"
                        />
                        <Line
                            yAxisId="right"
                            type="monotone"
                            dataKey="acumulado"
                            stroke="#2563eb"
                            strokeWidth={2}
                            name="% Acumulado"
                            dot={{ r: 4 }}
                        />
                    </ComposedChart>
                </ResponsiveContainer>

                {/* Summary Statistics */}
                <div className="mt-4 grid grid-cols-3 gap-4 text-center border-t pt-4">
                    <div>
                        <p className="text-sm text-gray-500">Total de Causas</p>
                        <p className="text-xl font-bold">{data.length}</p>
                    </div>
                    <div>
                        <p className="text-sm text-gray-500">Tempo Total de Parada</p>
                        <p className="text-xl font-bold text-red-600">
                            {data.reduce((sum, item) => sum + item.tempo_total_minutos, 0).toFixed(0)} min
                        </p>
                    </div>
                    <div>
                        <p className="text-sm text-gray-500">Top 3 Representa</p>
                        <p className="text-xl font-bold text-blue-600">
                            {data.slice(0, 3).reduce((sum, item) => sum + item.percentual, 0).toFixed(1)}%
                        </p>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
