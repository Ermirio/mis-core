import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    Cell,
} from 'recharts';
import { Package } from 'lucide-react';

interface SKUProductionChartProps {
    data: Array<{
        sku_codigo: string;
        sku_descricao: string;
        toneladas: number;
        percentual: number;
    }>;
    loading?: boolean;
}

const SKUProductionChart: React.FC<SKUProductionChartProps> = ({
    data,
    loading = false,
}) => {
    // Cores para as barras
    const COLORS = [
        '#3b82f6', // blue-500
        '#10b981', // green-500
        '#f59e0b', // amber-500
        '#ef4444', // red-500
        '#8b5cf6', // violet-500
        '#ec4899', // pink-500
        '#14b8a6', // teal-500
        '#f97316', // orange-500
    ];

    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Package className="w-5 h-5" />
                        Produção por SKU
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
                        <Package className="w-5 h-5" />
                        Produção por SKU
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

    // Ordena por toneladas (maior para menor)
    const dataSorted = [...data].sort((a, b) => b.toneladas - a.toneladas);

    // Pega top 10
    const dataTop = dataSorted.slice(0, 10);

    const totalToneladas = dataTop.reduce((acc, d) => acc + d.toneladas, 0);

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Package className="w-5 h-5" />
                        Produção por SKU (Top 10)
                    </div>
                    <div className="text-right">
                        <div className="text-2xl font-bold text-gray-900">
                            {totalToneladas.toFixed(3)} t
                        </div>
                        <div className="text-sm text-gray-500">
                            {dataTop.length} SKUs
                        </div>
                    </div>
                </CardTitle>
            </CardHeader>
            <CardContent>
                <ResponsiveContainer width="100%" height={400}>
                    <BarChart
                        data={dataTop}
                        layout="vertical"
                        margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
                    >
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                        <XAxis
                            type="number"
                            stroke="#6b7280"
                            style={{ fontSize: '12px' }}
                            label={{ value: 'Toneladas (t)', position: 'insideBottom', offset: -5, style: { fontSize: '12px' } }}
                        />
                        <YAxis
                            type="category"
                            dataKey="sku_codigo"
                            stroke="#6b7280"
                            style={{ fontSize: '11px' }}
                            width={90}
                        />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: 'white',
                                border: '1px solid #e5e7eb',
                                borderRadius: '6px',
                                fontSize: '12px'
                            }}
                            formatter={(value: number, name: string, props: any) => {
                                return [
                                    `${value.toFixed(3)} t (${props.payload.percentual.toFixed(1)}%)`,
                                    props.payload.sku_descricao || props.payload.sku_codigo
                                ];
                            }}
                            labelFormatter={(label) => `SKU: ${label}`}
                        />
                        <Bar dataKey="toneladas" radius={[0, 4, 4, 0]}>
                            {dataTop.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>

                {/* Tabela resumo */}
                <div className="mt-4 border-t pt-4">
                    <div className="text-sm font-medium text-gray-700 mb-2">Resumo</div>
                    <div className="space-y-1">
                        {dataTop.slice(0, 5).map((item, index) => (
                            <div key={index} className="flex justify-between items-center text-sm">
                                <div className="flex items-center gap-2">
                                    <div
                                        className="w-3 h-3 rounded-sm"
                                        style={{ backgroundColor: COLORS[index % COLORS.length] }}
                                    />
                                    <span className="font-medium">{item.sku_codigo}</span>
                                    <span className="text-gray-500 truncate max-w-[200px]">
                                        {item.sku_descricao}
                                    </span>
                                </div>
                                <div className="font-semibold">
                                    {item.toneladas.toFixed(3)} t ({item.percentual.toFixed(1)}%)
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

export default SKUProductionChart;
