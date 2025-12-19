
import React from 'react';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell
} from 'recharts';
import { Loader2 } from 'lucide-react';

interface LossEquipmentRankingProps {
    data: any[]; // Array of equipments
    isLoading: boolean;
}

const LossEquipmentRanking: React.FC<LossEquipmentRankingProps> = ({ data, isLoading }) => {
    if (isLoading) {
        return (
            <div className="h-64 w-full flex items-center justify-center bg-gray-800/50 rounded-lg">
                <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
            </div>
        );
    }

    if (!data || data.length === 0) {
        return (
            <div className="h-80 w-full flex items-center justify-center bg-gray-800/30 rounded-lg text-gray-500">
                Nenhuma perda registrada no período.
            </div>
        )
    }

    // Prepara dados: Ordena por total loss
    const chartData = [...data]
        .sort((a, b) => b.total_loss_min - a.total_loss_min)
        .slice(0, 10); // Top 10

    const CustomTooltip = ({ active, payload, label }: any) => {
        if (active && payload && payload.length) {
            const item = payload[0].payload;
            return (
                <div className="bg-gray-900 border border-gray-700 p-3 rounded shadow-xl">
                    <p className="font-bold text-gray-200">{item.nome}</p>
                    <div className="mt-2 space-y-1 text-xs">
                        <p className="text-red-400">Não Plan: {item.breakdown.unplanned.toFixed(1)} min</p>
                        <p className="text-blue-400">Plan: {item.breakdown.planned.toFixed(1)} min</p>
                        <p className="text-amber-400">Perf: {item.breakdown.performance.toFixed(1)} min</p>
                        <div className="border-t border-gray-700 pt-1 mt-1">
                            <p className="text-white font-bold">Total: {item.total_loss_min.toFixed(1)} min</p>
                        </div>
                    </div>
                </div>
            );
        }
        return null;
    };

    return (
        <div className="h-80 w-full bg-gray-900/50 p-4 rounded-lg flex flex-col">
            <h3 className="text-gray-400 text-sm font-medium mb-4 uppercase tracking-wider">
                Top Equipamentos com Perdas
            </h3>

            <div className="flex-1 w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                        layout="vertical"
                        data={chartData}
                        margin={{
                            top: 5,
                            right: 30,
                            left: 40,
                            bottom: 5,
                        }}
                    >
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" horizontal={true} vertical={false} />
                        <XAxis type="number" stroke="#9CA3AF" hide />
                        <YAxis
                            dataKey="nome"
                            type="category"
                            stroke="#9CA3AF"
                            tick={{ fill: '#E5E7EB', fontSize: 11 }}
                            width={100}
                            tickFormatter={(val) => val.length > 15 ? val.substring(0, 12) + '...' : val}
                        />
                        <Tooltip content={<CustomTooltip />} cursor={{ fill: '#374151', opacity: 0.2 }} />

                        {/* Stacked bars for breakdown */}
                        <Bar dataKey="breakdown.unplanned" stackId="a" fill="#EF4444" radius={[0, 4, 4, 0]} name="Não Planejado" />
                        <Bar dataKey="breakdown.performance" stackId="a" fill="#F59E0B" name="Performance" />
                        <Bar dataKey="breakdown.planned" stackId="a" fill="#3B82F6" name="Planejado" />

                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default LossEquipmentRanking;
