import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Package, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface TonnageCardProps {
    toneladas: number;
    meta?: number;
    vazao: number;
    formato?: number;
    periodo: 'hora' | 'turno' | 'dia';
    loading?: boolean;
}

export default function TonnageCard({
    toneladas,
    meta,
    vazao,
    formato,
    periodo,
    loading = false
}: TonnageCardProps) {
    // Calcular percentual da meta
    const percentualMeta = meta && meta > 0 ? (vazao / meta) * 100 : 0;

    // Determinar cor baseado no percentual da meta (ISA-101)
    const getStatusColor = () => {
        if (!meta) return 'text-gray-600 dark:text-gray-400';
        if (percentualMeta >= 100) return 'text-green-600 dark:text-green-400';
        if (percentualMeta >= 90) return 'text-yellow-600 dark:text-yellow-400';
        return 'text-red-600 dark:text-red-400';
    };

    // Ícone de tendência
    const getTrendIcon = () => {
        if (!meta) return <Minus className="w-4 h-4" />;
        if (percentualMeta >= 100) return <TrendingUp className="w-4 h-4 text-green-600" />;
        if (percentualMeta >= 90) return <Minus className="w-4 h-4 text-yellow-600" />;
        return <TrendingDown className="w-4 h-4 text-red-600" />;
    };

    // Label do período
    const getPeriodoLabel = () => {
        switch (periodo) {
            case 'hora': return 'Hora Atual';
            case 'turno': return 'Turno';
            case 'dia': return 'Dia';
            default: return 'Período';
        }
    };

    if (loading) {
        return (
            <Card className="border-gray-200 dark:border-gray-700">
                <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400 flex items-center gap-2">
                        <Package className="w-4 h-4" />
                        Produção - {getPeriodoLabel()}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="animate-pulse space-y-3">
                        <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-24"></div>
                        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-32"></div>
                        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-28"></div>
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="border-gray-200 dark:border-gray-700 hover:shadow-lg transition-shadow">
            <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400 flex items-center gap-2">
                    <Package className="w-4 h-4" />
                    Produção - {getPeriodoLabel()}
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
                {/* Toneladas Produzidas */}
                <div>
                    <div className="flex items-baseline gap-2">
                        <span className={`text-3xl font-bold ${getStatusColor()}`}>
                            {toneladas.toFixed(3)}
                        </span>
                        <span className="text-sm text-gray-500 dark:text-gray-400">t</span>
                    </div>

                    {/* Meta e Percentual */}
                    {meta && (
                        <div className="flex items-center gap-2 mt-1">
                            <span className="text-sm text-gray-600 dark:text-gray-400">
                                Meta: {meta.toFixed(1)} t
                            </span>
                            <Badge
                                variant={percentualMeta >= 100 ? 'default' : percentualMeta >= 90 ? 'secondary' : 'destructive'}
                                className="text-xs"
                            >
                                {percentualMeta.toFixed(1)}%
                            </Badge>
                            {getTrendIcon()}
                        </div>
                    )}
                </div>

                {/* Vazão */}
                <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                    <div className="flex justify-between items-center">
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                            Vazão
                        </span>
                        <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                            {vazao.toFixed(3)} t/h
                        </span>
                    </div>
                </div>

                {/* Formato */}
                {formato && (
                    <div className="flex justify-between items-center">
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                            Formato
                        </span>
                        <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                            {formato.toFixed(0)}g
                        </span>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}