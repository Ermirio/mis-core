import React from 'react';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Users } from 'lucide-react';

interface ShiftData {
    turno: string;
    producao_total: number;
    oee_medio: number;
    disponibilidade_media: number;
    performance_media: number;
    qualidade_media: number;
    descarte_total: number;
    tempo_producao_total: number;
    velocidade_media: number;
}

interface ShiftComparisonChartProps {
    data: ShiftData[];
    loading?: boolean;
}

export default function ShiftComparisonChart({ data, loading = false }: ShiftComparisonChartProps) {
    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Users className="w-5 h-5" />
                        Performance por Turno
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="h-80 flex items-center justify-center">
                        <div className="animate-pulse space-y-3 w-full">
                            <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                            <div className="h-4 bg-gray-200 rounded w-1/2"></div>
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
                        <Users className="w-5 h-5" />
                        Performance por Turno
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="h-80 flex items-center justify-center text-gray-400">
                        Sem dados de turnos no período selecionado
                    </div>
                </CardContent>
            </Card>
        );
    }

    // Formata dados para o gráfico
    const chartData = data.map(item => ({
        turno: `Turno ${item.turno}`,
        Produção: item.producao_total,
        OEE: item.oee_medio,
        Disponibilidade: item.disponibilidade_media,
        Performance: item.performance_media,
        Qualidade: item.qualidade_media,
        Descarte: item.descarte_total
    }));

    // Identifica melhor turno
    const bestShift = data.reduce((best, current) =>
        current.oee_medio > best.oee_medio ? current : best
        , data[0]);

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Users className="w-5 h-5 text-blue-500" />
                    Performance por Turno
                </CardTitle>
                <p className="text-sm text-gray-500 mt-1">
                    Comparativo de métricas entre equipes - Benchmarking interno
                </p>
            </CardHeader>
            <CardContent>
                <ResponsiveContainer width="100%" height={350}>
                    <BarChart
                        data={chartData}
                        margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                    >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="turno" />
                        <YAxis
                            label={{ value: 'Valores (%)', angle: -90, position: 'insideLeft' }}
                        />
                        <Tooltip
                            contentStyle={{ backgroundColor: 'white', border: '1px solid #ccc' }}
                            formatter={(value: number, name: string) => {
                                if (name === 'Produção') return [value.toLocaleString(), 'Produção (un)'];
                                if (name === 'Descarte') return [value.toLocaleString(), 'Descarte (un)'];
                                return [`${value.toFixed(1)}%`, name];
                            }}
                        />
                        <Legend />
                        <Bar dataKey="OEE" fill="#22c55e" name="OEE (%)" />
                        <Bar dataKey="Disponibilidade" fill="#3b82f6" name="Disponibilidade (%)" />
                        <Bar dataKey="Performance" fill="#f59e0b" name="Performance (%)" />
                        <Bar dataKey="Qualidade" fill="#8b5cf6" name="Qualidade (%)" />
                    </BarChart>
                </ResponsiveContainer>

                {/* Summary Stats */}
                <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
                    {data.map(shift => (
                        <div
                            key={shift.turno}
                            className={`p-3 rounded-lg border ${shift.turno === bestShift.turno
                                    ? 'border-green-500 bg-green-50'
                                    : 'border-gray-200'
                                }`}
                        >
                            <p className="text-xs text-gray-500 mb-1">Turno {shift.turno}</p>
                            <p className="text-2xl font-bold text-gray-900">
                                {shift.oee_medio.toFixed(1)}%
                            </p>
                            <p className="text-xs text-gray-500">OEE Médio</p>
                            {shift.turno === bestShift.turno && (
                                <p className="text-xs text-green-600 font-medium mt-1">🏆 Melhor Turno</p>
                            )}
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}
