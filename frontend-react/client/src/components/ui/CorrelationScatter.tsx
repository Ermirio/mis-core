import React from 'react';
import {
    ScatterChart,
    Scatter,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
    ZAxis
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp } from 'lucide-react';

interface CorrelationDataPoint {
    velocidade_media: number;
    percentual_descarte: number;
    data_hora: string;
    producao: number;
}

interface CorrelationScatterProps {
    data: CorrelationDataPoint[];
    loading?: boolean;
}

export default function CorrelationScatter({ data, loading = false }: CorrelationScatterProps) {
    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <TrendingUp className="w-5 h-5" />
                        Correlação: Velocidade x % de Refugo
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="h-96 flex items-center justify-center">
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
                        <TrendingUp className="w-5 h-5" />
                        Correlação: Velocidade x % de Refugo
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="h-96 flex items-center justify-center text-gray-400">
                        Sem dados para análise de correlação no período
                    </div>
                </CardContent>
            </Card>
        );
    }

    // Calcula correlação de Pearson
    const calculateCorrelation = (points: CorrelationDataPoint[]) => {
        const n = points.length;
        if (n < 2) return 0;

        const sumX = points.reduce((sum, p) => sum + p.velocidade_media, 0);
        const sumY = points.reduce((sum, p) => sum + p.percentual_descarte, 0);
        const sumXY = points.reduce((sum, p) => sum + (p.velocidade_media * p.percentual_descarte), 0);
        const sumX2 = points.reduce((sum, p) => sum + (p.velocidade_media ** 2), 0);
        const sumY2 = points.reduce((sum, p) => sum + (p.percentual_descarte ** 2), 0);

        const numerator = (n * sumXY) - (sumX * sumY);
        const denominator = Math.sqrt(((n * sumX2) - (sumX ** 2)) * ((n * sumY2) - (sumY ** 2)));

        return denominator === 0 ? 0 : numerator / denominator;
    };

    const correlation = calculateCorrelation(data);

    // Formata dados para scatter
    const scatterData = data.map(point => ({
        x: point.velocidade_media,
        y: point.percentual_descarte,
        z: point.producao // Usado para tamanho do ponto
    }));

    // Calcula linha de tendência (regressão linear simples)
    const calculateTrendLine = () => {
        const n = data.length;
        const sumX = data.reduce((sum, p) => sum + p.velocidade_media, 0);
        const sumY = data.reduce((sum, p) => sum + p.percentual_descarte, 0);
        const sumXY = data.reduce((sum, p) => sum + (p.velocidade_media * p.percentual_descarte), 0);
        const sumX2 = data.reduce((sum, p) => sum + (p.velocidade_media ** 2), 0);

        const slope = ((n * sumXY) - (sumX * sumY)) / ((n * sumX2) - (sumX ** 2));
        const intercept = (sumY - (slope * sumX)) / n;

        const minX = Math.min(...data.map(p => p.velocidade_media));
        const maxX = Math.max(...data.map(p => p.velocidade_media));

        return [
            { x: minX, y: (slope * minX) + intercept },
            { x: maxX, y: (slope * maxX) + intercept }
        ];
    };

    const trendLine = data.length >= 2 ? calculateTrendLine() : [];

    // Interpretação da correlação
    const getCorrelationInsight = (r: number) => {
        const absR = Math.abs(r);
        if (absR < 0.3) return { text: 'Correlação Fraca', color: 'text-gray-600' };
        if (absR < 0.7) return { text: 'Correlação Moderada', color: 'text-yellow-600' };
        return { text: 'Correlação Forte', color: 'text-red-600' };
    };

    const insight = getCorrelationInsight(correlation);

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-purple-500" />
                    Correlação: Velocidade x % de Refugo
                </CardTitle>
                <p className="text-sm text-gray-500 mt-1">
                    Identifique o ponto ótimo de operação - Máxima velocidade com mínimo descarte
                </p>
            </CardHeader>
            <CardContent>
                <ResponsiveContainer width="100%" height={400}>
                    <ScatterChart
                        margin={{ top: 20, right: 30, bottom: 20, left: 20 }}
                    >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                            type="number"
                            dataKey="x"
                            name="Velocidade"
                            unit=" un/min"
                            label={{ value: 'Velocidade (un/min)', position: 'insideBottom', offset: -10 }}
                        />
                        <YAxis
                            type="number"
                            dataKey="y"
                            name="Descarte"
                            unit="%"
                            label={{ value: '% Descarte', angle: -90, position: 'insideLeft' }}
                        />
                        <ZAxis type="number" dataKey="z" range={[50, 400]} />
                        <Tooltip
                            cursor={{ strokeDasharray: '3 3' }}
                            contentStyle={{ backgroundColor: 'white', border: '1px solid #ccc' }}
                            formatter={(value: number, name: string) => {
                                if (name === 'Velocidade') return [`${value.toFixed(1)} un/min`, 'Velocidade'];
                                if (name === 'Descarte') return [`${value.toFixed(2)}%`, '% Descarte'];
                                if (name === 'z') return [`${value} un`, 'Produção'];
                                return [value, name];
                            }}
                        />
                        <Legend />
                        <Scatter
                            name="Pontos Horários"
                            data={scatterData}
                            fill="#8b5cf6"
                        />
                        {trendLine.length > 0 && (
                            <Scatter
                                name="Linha de Tendência"
                                data={trendLine}
                                fill="#ef4444"
                                line
                                shape="circle"
                                lineType="fitting"
                            />
                        )}
                    </ScatterChart>
                </ResponsiveContainer>

                {/* Correlation Statistics */}
                <div className="mt-6 grid grid-cols-3 gap-4 text-center border-t pt-4">
                    <div>
                        <p className="text-sm text-gray-500">Coeficiente de Correlação</p>
                        <p className={`text-2xl font-bold ${insight.color}`}>
                            {correlation.toFixed(3)}
                        </p>
                        <p className={`text-xs ${insight.color} mt-1`}>{insight.text}</p>
                    </div>
                    <div>
                        <p className="text-sm text-gray-500">Total de Pontos</p>
                        <p className="text-2xl font-bold text-gray-900">{data.length}</p>
                    </div>
                    <div>
                        <p className="text-sm text-gray-500">Interpretação</p>
                        <p className="text-sm text-gray-700 mt-1">
                            {correlation > 0.3
                                ? '⚠️ Velocidade alta aumenta descarte'
                                : correlation < -0.3
                                    ? '✅ Velocidade alta reduz descarte'
                                    : '➖ Sem correlação clara'}
                        </p>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
