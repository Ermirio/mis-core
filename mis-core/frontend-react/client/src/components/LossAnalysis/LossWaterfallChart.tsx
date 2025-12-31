
import React from 'react';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell,
    LabelList
} from 'recharts';
import { Loader2 } from 'lucide-react';

interface LossWaterfallProps {
    data: any;
    isLoading: boolean;
}

const LossWaterfallChart: React.FC<LossWaterfallProps> = ({ data, isLoading }) => {
    if (isLoading || !data) {
        return (
            <div className="h-64 w-full flex items-center justify-center bg-gray-800/50 rounded-lg">
                <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
            </div>
        );
    }

    // Transformar objeto loss_tree em array para o chart
    // Waterfall Logic:
    // 1. Total Time (Base 0)
    // 2. Planned Loss (Começa no Topo do proximo, desce) -> Aqui simplificamos: Mostramos quanto perdeu
    // Melhor visualização para LEIGOS: Bar Chart lado a lado ou Empilhado?
    // O Waterfall clássico mostra: Barra 1 (Total), Barra 2 (Perda Plan), Barra 3 (Sobra), Barra 4 (Perda Unplan)...
    // Vamos usar um BarChart simples com Cores Distintas para start.

    const chartData = [
        { name: 'Tempo Total', value: data.total_time, color: '#6B7280', type: 'base' }, // Gray
        { name: 'Planejado', value: data.planned_loss, color: '#3B82F6', type: 'loss' }, // Blue
        { name: 'Não Planej.', value: data.unplanned_loss, color: '#EF4444', type: 'loss' }, // Red
        { name: 'Performance', value: data.performance_loss, color: '#F59E0B', type: 'loss' }, // Amber
        { name: 'Qualidade', value: data.quality_loss, color: '#8B5CF6', type: 'loss' }, // Purple
        { name: 'Produção Boa', value: data.good_production, color: '#10B981', type: 'good' }, // Emerald
    ];

    // Configuração de animação para transições suaves
    const animationProps = {
        isAnimationActive: true,
        animationDuration: 1000,
        animationEasing: 'ease-in-out'
    };

    // Filtra valores zerados para limpar o gráfico, mas mantem os principais
    const finalData = chartData.map(d => ({
        ...d,
        value: parseFloat(d.value.toFixed(1))
    }));

    const CustomTooltip = ({ active, payload, label }: any) => {
        if (active && payload && payload.length) {
            return (
                <div className="bg-gray-900 border border-gray-700 p-3 rounded shadow-xl">
                    <p className="font-bold text-gray-200">{label}</p>
                    <p style={{ color: payload[0].payload.color }}>
                        {payload[0].value} min
                    </p>
                    {data.total_time > 0 && (
                        <p className="text-xs text-gray-500">
                            {((payload[0].value / data.total_time) * 100).toFixed(1)}% do total
                        </p>
                    )}
                </div>
            );
        }
        return null;
    };

    return (
        <div className="h-80 w-full bg-gray-900/50 p-4 rounded-lg flex flex-col">
            <h3 className="text-gray-400 text-sm font-medium mb-4 uppercase tracking-wider">
                Cascata de Perdas (Minutos)
            </h3>

            <div className="flex-1 w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                        data={finalData}
                        margin={{
                            top: 20,
                            right: 30,
                            left: 20,
                            bottom: 5,
                        }}
                    >
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
                        <XAxis
                            dataKey="name"
                            stroke="#9CA3AF"
                            tick={{ fill: '#9CA3AF', fontSize: 12 }}
                            axisLine={false}
                            tickLine={false}
                        />
                        <YAxis
                            stroke="#9CA3AF"
                            tick={{ fill: '#9CA3AF', fontSize: 12 }}
                            axisLine={false}
                            tickLine={false}
                        />
                        <Tooltip content={<CustomTooltip />} cursor={{ fill: '#374151', opacity: 0.2 }} />
                        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                            {finalData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                            <LabelList dataKey="value" position="top" fill="#D1D5DB" fontSize={12} formatter={(val: number) => val > 0 ? val : ''} />
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default LossWaterfallChart;
