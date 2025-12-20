import React, { useEffect, useState, useMemo } from 'react';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
    AreaChart,
    Area,
    ReferenceLine
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { format } from 'date-fns';

interface VariablesTabProps {
    equipamento: any;
    historico: any[]; // Equipment history with dynamic keys
    timeRange: { start: Date; end: Date; interval: string };
    isConsolidated: boolean;
}

const FLASK_API_URL = import.meta.env.VITE_FLASK_API_URL || 'http://127.0.0.1:5000/api';
const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || 'http://127.0.0.1:8000/api';

import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, AlertTriangle } from "lucide-react";

const VariablesTab: React.FC<VariablesTabProps> = ({ equipamento, historico, timeRange, isConsolidated }) => {
    const [lineHistory, setLineHistory] = useState<any[]>([]);
    const [loadingLine, setLoadingLine] = useState(false);
    const [currentPage, setCurrentPage] = useState(1);
    const ITEMS_PER_PAGE = 6;

    const [sensorLimits, setSensorLimits] = useState<{ [key: string]: { min?: number, max?: number } }>({});

    // Fetch Line History
    useEffect(() => {
        const fetchLineHistory = async () => {
            if (!equipamento?.linha_nome) return;
            setLoadingLine(true);
            try {
                const params = new URLSearchParams({
                    start: timeRange.start.toISOString(),
                    end: timeRange.end.toISOString(),
                    interval: timeRange.interval
                });
                const response = await fetch(`${FLASK_API_URL}/linha/${equipamento.linha_nome}/historico?${params.toString()}`);
                if (response.ok) {
                    const data = await response.json();
                    setLineHistory(data.historico || []);
                }
            } catch (error) {
                console.error("Error fetching line history:", error);
            } finally {
                setLoadingLine(false);
            }
        };
        fetchLineHistory();
    }, [equipamento, timeRange]);

    // Fetch Sensor Limits
    useEffect(() => {
        const fetchSensorLimits = async () => {
            if (!equipamento?.id) return;
            try {
                const response = await fetch(`${DJANGO_API_URL}/sensores/?equipamento=${equipamento.id}`);
                if (response.ok) {
                    const data = await response.json();
                    const results = Array.isArray(data) ? data : data.results || [];

                    const limits: { [key: string]: { min?: number, max?: number } } = {};
                    results.forEach((s: any) => {
                        if (s.nome) {
                            const key = s.nome;
                            limits[key] = { min: s.valor_min, max: s.valor_max };
                            limits[key.toLowerCase()] = { min: s.valor_min, max: s.valor_max };
                        }
                    });
                    setSensorLimits(limits);
                }
            } catch (error) {
                console.error("Error fetching sensor limits:", error);
            }
        };
        fetchSensorLimits();
    }, [equipamento]);

    const [showStandard, setShowStandard] = useState(true);

    // Identify dynamic keys from equipment history
    const dynamicKeys = useMemo(() => {
        if (historico.length === 0) return [];
        const uniqueKeys = new Set<string>();
        // Scan all items to ensure we catch keys that only appear in recent records
        historico.forEach(item => {
            Object.keys(item).forEach(key => uniqueKeys.add(key));
        });

        const allKeys = Array.from(uniqueKeys);
        // Filter out known keys to find dynamic sensors
        const excluded = ['id', 'data_hora', 'periodo', 'contagem_entrada', 'contagem_saida', 'descarte', 'percentual_descarte', 'velocidade_real', 'disponibilidade', 'performance', 'qualidade', 'oee', 'tempo_producao', 'oee_medio', 'producao_total'];
        // Also exclude temporary fields if any
        return allKeys.filter(k => !excluded.includes(k) && !k.startsWith('last_'));
    }, [historico]);

    // Pagination Logic
    const totalPages = Math.ceil(dynamicKeys.length / ITEMS_PER_PAGE);
    const currentKeys = dynamicKeys.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE);

    const formatXAxis = (tickItem: string) => {
        if (isConsolidated) return 'Total';
        return format(new Date(tickItem), 'dd/MM HH:mm');
    };

    return (
        <div className="space-y-6">
            {/* SECTION 1: LINE VARIABLES (Common to all equipment) */}
            <div>
                <h3 className="text-lg font-semibold mb-4 text-gray-700">Variáveis da Linha ({equipamento.linha_nome})</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Line Production */}
                    <Card>
                        <CardHeader className="pb-2"><CardTitle className="text-sm">Produção Total da Linha</CardTitle></CardHeader>
                        <CardContent className="h-[250px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={lineHistory}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="data_hora" tickFormatter={formatXAxis} />
                                    <YAxis />
                                    <Tooltip labelFormatter={(v) => format(new Date(v), 'dd/MM HH:mm')} />
                                    <Area type="monotone" dataKey="producao_total" stroke="#8884d8" fill="#8884d8" name="Produção" />
                                </AreaChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>

                    {/* Line OEE */}
                    <Card>
                        <CardHeader className="pb-2"><CardTitle className="text-sm">OEE Médio da Linha</CardTitle></CardHeader>
                        <CardContent className="h-[250px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={lineHistory}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="data_hora" tickFormatter={formatXAxis} />
                                    <YAxis domain={[0, 100]} />
                                    <Tooltip labelFormatter={(v) => format(new Date(v), 'dd/MM HH:mm')} />
                                    <Line type="monotone" dataKey="oee_medio" stroke="#82ca9d" strokeWidth={2} name="OEE %" />
                                </LineChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>
                </div>
            </div>

            {/* SECTION 2: EQUIPMENT VARIABLES */}
            <div>
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-semibold text-gray-700">Variáveis do Equipamento ({equipamento.nome})</h3>
                    <Button variant="ghost" size="sm" onClick={() => setShowStandard(!showStandard)}>
                        {showStandard ? 'Recolher Padrão' : 'Expandir Padrão'}
                    </Button>
                </div>

                {/* Standard Variables Grid - Collapsible */}
                {showStandard && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
                        {/* Standard Variables */}
                        <Card>
                            <CardHeader className="pb-2"><CardTitle className="text-sm">Velocidade</CardTitle></CardHeader>
                            <CardContent className="h-[200px]">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={historico}>
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis dataKey="data_hora" hide />
                                        <YAxis />
                                        <Tooltip labelFormatter={(v) => format(new Date(v), 'dd/MM HH:mm')} />
                                        <Line type="monotone" dataKey="velocidade_real" stroke="#2563eb" dot={false} name="Velocidade" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="pb-2"><CardTitle className="text-sm">Produção</CardTitle></CardHeader>
                            <CardContent className="h-[200px]">
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={historico}>
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis dataKey="data_hora" hide />
                                        <YAxis />
                                        <Tooltip labelFormatter={(v) => format(new Date(v), 'dd/MM HH:mm')} />
                                        <Area type="monotone" dataKey="contagem_saida" stroke="#16a34a" fill="#16a34a" name="Produção" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="pb-2"><CardTitle className="text-sm">OEE</CardTitle></CardHeader>
                            <CardContent className="h-[200px]">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={historico}>
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis dataKey="data_hora" hide />
                                        <YAxis domain={[0, 100]} />
                                        <Tooltip labelFormatter={(v) => format(new Date(v), 'dd/MM HH:mm')} />
                                        <Line type="monotone" dataKey="oee" stroke="#d97706" strokeWidth={2} dot={false} name="OEE %" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="pb-2"><CardTitle className="text-sm">Descarte</CardTitle></CardHeader>
                            <CardContent className="h-[200px]">
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={historico}>
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis dataKey="data_hora" hide />
                                        <YAxis />
                                        <Tooltip labelFormatter={(v) => format(new Date(v), 'dd/MM HH:mm')} />
                                        <Area type="monotone" dataKey="descarte" stroke="#dc2626" fill="#dc2626" name="Descarte" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </CardContent>
                        </Card>
                    </div>
                )}

                {/* Dynamic Variables (Sensors) - PAGINATED */}
                {dynamicKeys.length > 0 && (
                    <div className="space-y-4">
                        <div className="flex justify-between items-center">
                            <h4 className="text-sm font-medium text-gray-500 uppercase tracking-wider">Sensores Adicionais ({dynamicKeys.length})</h4>
                            {totalPages > 1 && (
                                <div className="flex gap-2">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                        disabled={currentPage === 1}
                                    >
                                        <ChevronLeft className="w-4 h-4" />
                                    </Button>
                                    <span className="text-sm py-2">Pág {currentPage} de {totalPages}</span>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                                        disabled={currentPage === totalPages}
                                    >
                                        <ChevronRight className="w-4 h-4" />
                                    </Button>
                                </div>
                            )}
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {currentKeys.map(key => {
                                const limit = sensorLimits[key] || sensorLimits[key.toLowerCase()];
                                const rawValue = historico.length > 0 ? historico[historico.length - 1][key] : undefined;
                                const lastValue = rawValue !== undefined ? Number(rawValue) : undefined;

                                const isAlarm = limit && lastValue !== undefined && !isNaN(lastValue) && (
                                    (limit.min !== undefined && lastValue < limit.min) ||
                                    (limit.max !== undefined && lastValue > limit.max)
                                );

                                // Show raw value safely
                                const formatValue = (v: any) => {
                                    if (v === undefined || v === null) return '-';
                                    const n = Number(v);
                                    return isNaN(n) ? String(v) : n.toFixed(1);
                                };

                                // Determine Y-Axis Domain to ensure limits are visible
                                const yDomain: any = ['auto', 'auto'];
                                if (limit) {
                                    if (limit.min !== undefined) yDomain[0] = (dataMin: number) => Math.min(dataMin, limit.min! * 0.95);
                                    if (limit.max !== undefined) yDomain[1] = (dataMax: number) => Math.max(dataMax, limit.max! * 1.05);
                                }

                                const chartColor = isAlarm ? "#dc2626" : "#2563eb"; // Red or Blue

                                return (
                                    <Card key={key} className={`transition-all duration-500 ${isAlarm ? 'border-red-500 bg-red-50/50 shadow-md ring-2 ring-red-200' : 'hover:shadow-lg hover:border-blue-200'}`}>
                                        <CardHeader className="pb-2 flex flex-row items-center justify-between">
                                            <CardTitle className="text-sm capitalize flex flex-col gap-1">
                                                {key.replace(/_/g, ' ')}
                                                {isAlarm ?
                                                    <span className="text-[10px] text-red-600 font-bold uppercase animate-pulse flex items-center gap-1">
                                                        <AlertTriangle className="h-3 w-3" /> Fora do Limite
                                                    </span>
                                                    :
                                                    <span className="text-[10px] text-muted-foreground font-normal">Monitoramento em tempo real</span>
                                                }
                                            </CardTitle>
                                            <div className="flex flex-col items-end">
                                                <div className={`text-2xl font-bold ${isAlarm ? 'text-red-600' : 'text-gray-800'}`}>
                                                    {formatValue(rawValue)}
                                                </div>
                                                <div className="text-[10px] text-gray-400">Atualizado agora</div>
                                            </div>
                                        </CardHeader>
                                        <CardContent className="h-[200px]">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <AreaChart data={historico} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                                    <defs>
                                                        <linearGradient id={`gradient-${key}`} x1="0" y1="0" x2="0" y2="1">
                                                            <stop offset="5%" stopColor={chartColor} stopOpacity={0.8} />
                                                            <stop offset="95%" stopColor={chartColor} stopOpacity={0} />
                                                        </linearGradient>
                                                    </defs>
                                                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.2} stroke="#888" />
                                                    <XAxis dataKey="data_hora" hide />
                                                    <YAxis domain={yDomain} tick={{ fontSize: 10, fill: '#666' }} axisLine={false} tickLine={false} />
                                                    <Tooltip
                                                        contentStyle={{
                                                            borderRadius: '12px',
                                                            border: 'none',
                                                            boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
                                                            backgroundColor: 'rgba(255, 255, 255, 0.95)',
                                                            backdropFilter: 'blur(4px)',
                                                            padding: '12px'
                                                        }}
                                                        labelFormatter={(v) => format(new Date(v), 'dd/MM HH:mm')}
                                                        formatter={(value: any) => [formatValue(value), key]}
                                                    />
                                                    {limit?.min !== undefined && (
                                                        <ReferenceLine
                                                            y={limit.min}
                                                            stroke="#ef4444"
                                                            strokeDasharray="4 4"
                                                            strokeWidth={1.5}
                                                            label={{ value: 'MÍN', position: 'insideBottomRight', fill: '#ef4444', fontSize: 10, fontWeight: 'bold' }}
                                                        />
                                                    )}
                                                    {limit?.max !== undefined && (
                                                        <ReferenceLine
                                                            y={limit.max}
                                                            stroke="#ef4444"
                                                            strokeDasharray="4 4"
                                                            strokeWidth={1.5}
                                                            label={{ value: 'MÁX', position: 'insideTopRight', fill: '#ef4444', fontSize: 10, fontWeight: 'bold' }}
                                                        />
                                                    )}
                                                    <Area
                                                        type="monotone"
                                                        dataKey={key}
                                                        stroke={chartColor}
                                                        fillOpacity={1}
                                                        fill={`url(#gradient-${key})`}
                                                        strokeWidth={2}
                                                        activeDot={{ r: 6, strokeWidth: 0, fill: chartColor, className: "animate-pulse" }}
                                                        isAnimationActive={false}
                                                    />
                                                </AreaChart>
                                            </ResponsiveContainer>
                                        </CardContent>
                                    </Card>
                                );
                            })}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default VariablesTab;
