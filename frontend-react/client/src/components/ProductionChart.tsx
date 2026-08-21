import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
    LineChart,
    Line,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    ReferenceLine,
} from 'recharts';
import { TrendingUp, Zap } from 'lucide-react';

interface ProductionChartProps {
    data: Array<{
        timestamp: string;
        toneladas_real: number;
        toneladas_meta?: number;
        contagem?: number;
    }>;
    meta?: number;
    periodo: 'hora' | 'turno' | 'dia' | 'semana';
    loading?: boolean;
}

const ProductionChart: React.FC<ProductionChartProps> = ({
    data,
    meta,
    periodo,
    loading = false,
}) => {
    // Formata timestamp baseado no período
    const formatTimestamp = (timestamp: string) => {
        const date = new Date(timestamp);

        switch (periodo) {
            case 'hora':
                return date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
            case 'turno':
                return date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
            case 'dia':
                return date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
            case 'semana':
                return date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
            default:
                return timestamp;
        }
    };

    // Calcula tonelagem acumulada
    const dataAcumulada = data.reduce((acc, curr, index) => {
        const acumulado = index === 0 ? curr.toneladas_real : acc[index - 1].toneladas_acumuladas + curr.toneladas_real;
        const metaAcumulada = meta && curr.toneladas_meta ? (index === 0 ? curr.toneladas_meta : acc[index - 1].meta_acumulada + curr.toneladas_meta) : undefined;

        return [
            ...acc,
            {
                ...curr,
                timestamp_formatted: formatTimestamp(curr.timestamp),
                toneladas_acumuladas: acumulado,
                meta_acumulada: metaAcumulada,
            },
        ];
    }, [] as any[]);

    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <TrendingUp className="w-5 h-5" />
                        Produção Acumulada
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="h-80 flex items-center justify-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
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
                        <TrendingUp className="w-5 h-5" />
                        Produção Acumulada
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="h-80 flex items-center justify-center text-gray-500">
                        Nenhum dado disponível para o período selecionado
                    </div>
                </CardContent>
            </Card>
        );
    }

    const totalProduzido = dataAcumulada[dataAcumulada.length - 1]?.toneladas_acumuladas || 0;
    const totalMeta = dataAcumulada[dataAcumulada.length - 1]?.meta_acumulada;
    const percentualAtingimento = totalMeta ? (totalProduzido / totalMeta) * 100 : null;

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <TrendingUp className="w-5 h-5" />
                        Produção Acumulada
                    </div>
                    <div className="text-right">
                        <div className="text-2xl font-bold text-gray-900">
                            {totalProduzido.toFixed(3)} t
                        </div>
                        {percentualAtingimento !== null && (
                            <div className={`text-sm ${percentualAtingimento >= 100 ? 'text-green-600' : percentualAtingimento >= 90 ? 'text-yellow-600' : 'text-red-600'}`}>
                                {percentualAtingimento.toFixed(1)}% da meta
                            </div>
                        )}
                    </div>
                </CardTitle>
            </CardHeader>
            <CardContent>
                <ResponsiveContainer width="100%" height={320}>
                    <AreaChart data={dataAcumulada}>
                        <defs>
                            <linearGradient id="colorReal" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8} />
                                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.1} />
                            </linearGradient>
                            <linearGradient id="colorMeta" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#10b981" stopOpacity={0.6} />
                                <stop offset="95%" stopColor="#10b981" stopOpacity={0.05} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                        <XAxis
                            dataKey="timestamp_formatted"
                            stroke="#6b7280"
                            style={{ fontSize: '12px' }}
                        />
                        <YAxis
                            stroke="#6b7280"
                            style={{ fontSize: '12px' }}
                            label={{ value: 'Toneladas (t)', angle: -90, position: 'insideLeft', style: { fontSize: '12px' } }}
                        />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: 'white',
                                border: '1px solid #e5e7eb',
                                borderRadius: '6px',
                                fontSize: '12px'
                            }}
                            formatter={(value: number) => [`${value.toFixed(3)} t`, '']}
                        />
                        <Legend />
                        {meta && (
                            <Area
                                type="monotone"
                                dataKey="meta_acumulada"
                                stroke="#10b981"
                                fill="url(#colorMeta)"
                                name="Meta Acumulada"
                                strokeWidth={2}
                            />
                        )}
                        <Area
                            type="monotone"
                            dataKey="toneladas_acumuladas"
                            stroke="#3b82f6"
                            fill="url(#colorReal)"
                            name="Produção Real"
                            strokeWidth={2}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </CardContent>
        </Card>
    );
};

export default ProductionChart;