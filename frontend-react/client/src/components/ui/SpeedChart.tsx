import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    ReferenceLine,
} from 'recharts';
import { Gauge } from 'lucide-react';

interface SpeedChartProps {
    data: Array<{
        timestamp: string;
        velocidade_real: number;
        velocidade_ideal: number;
        eficiencia?: number;
    }>;
    periodo: 'hora' | 'turno' | 'dia' | 'semana';
    loading?: boolean;
}

const SpeedChart: React.FC<SpeedChartProps> = ({
    data,
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

    const dataFormatada = data.map(d => ({
        ...d,
        timestamp_formatted: formatTimestamp(d.timestamp),
        eficiencia: d.eficiencia || (d.velocidade_ideal > 0 ? (d.velocidade_real / d.velocidade_ideal) * 100 : 0),
    }));

    // Calcula médias
    const velocidadeRealMedia = data.reduce((acc, d) => acc + d.velocidade_real, 0) / data.length;
    const velocidadeIdealMedia = data.reduce((acc, d) => acc + d.velocidade_ideal, 0) / data.length;
    const eficienciaMedia = velocidadeIdealMedia > 0 ? (velocidadeRealMedia / velocidadeIdealMedia) * 100 : 0;

    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Gauge className="w-5 h-5" />
                        Velocidade da Linha
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
                        <Gauge className="w-5 h-5" />
                        Velocidade da Linha
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

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Gauge className="w-5 h-5" />
                        Velocidade da Linha
                    </div>
                    <div className="text-right">
                        <div className="text-2xl font-bold text-gray-900">
                            {velocidadeRealMedia.toFixed(1)} un/min
                        </div>
                        <div className={`text-sm ${eficienciaMedia >= 95 ? 'text-green-600' : eficienciaMedia >= 85 ? 'text-yellow-600' : 'text-red-600'}`}>
                            {eficienciaMedia.toFixed(1)}% de eficiência
                        </div>
                    </div>
                </CardTitle>
            </CardHeader>
            <CardContent>
                <ResponsiveContainer width="100%" height={320}>
                    <LineChart data={dataFormatada}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                        <XAxis
                            dataKey="timestamp_formatted"
                            stroke="#6b7280"
                            style={{ fontSize: '12px' }}
                        />
                        <YAxis
                            stroke="#6b7280"
                            style={{ fontSize: '12px' }}
                            label={{ value: 'Velocidade (un/min)', angle: -90, position: 'insideLeft', style: { fontSize: '12px' } }}
                        />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: 'white',
                                border: '1px solid #e5e7eb',
                                borderRadius: '6px',
                                fontSize: '12px'
                            }}
                            formatter={(value: number, name: string) => {
                                if (name === 'eficiencia') {
                                    return [`${value.toFixed(1)}%`, 'Eficiência'];
                                }
                                return [`${value.toFixed(1)} un/min`, name];
                            }}
                        />
                        <Legend />
                        <Line
                            type="monotone"
                            dataKey="velocidade_ideal"
                            stroke="#10b981"
                            strokeWidth={2}
                            dot={false}
                            name="Velocidade Ideal"
                            strokeDasharray="5 5"
                        />
                        <Line
                            type="monotone"
                            dataKey="velocidade_real"
                            stroke="#3b82f6"
                            strokeWidth={2}
                            dot={{ fill: '#3b82f6', r: 3 }}
                            activeDot={{ r: 5 }}
                            name="Velocidade Real"
                        />
                    </LineChart>
                </ResponsiveContainer>

                {/* Legenda adicional */}
                <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
                    <div className="text-center">
                        <div className="text-gray-500">Velocidade Real Média</div>
                        <div className="text-lg font-semibold text-blue-600">
                            {velocidadeRealMedia.toFixed(1)} un/min
                        </div>
                    </div>
                    <div className="text-center">
                        <div className="text-gray-500">Velocidade Ideal</div>
                        <div className="text-lg font-semibold text-green-600">
                            {velocidadeIdealMedia.toFixed(1)} un/min
                        </div>
                    </div>
                    <div className="text-center">
                        <div className="text-gray-500">Eficiência Média</div>
                        <div className={`text-lg font-semibold ${eficienciaMedia >= 95 ? 'text-green-600' : eficienciaMedia >= 85 ? 'text-yellow-600' : 'text-red-600'}`}>
                            {eficienciaMedia.toFixed(1)}%
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

export default SpeedChart;