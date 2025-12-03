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
    Area
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

const VariablesTab: React.FC<VariablesTabProps> = ({ equipamento, historico, timeRange, isConsolidated }) => {
    const [lineHistory, setLineHistory] = useState<any[]>([]);
    const [loadingLine, setLoadingLine] = useState(false);

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

    // Identify dynamic keys from equipment history
    const dynamicKeys = useMemo(() => {
        if (historico.length === 0) return [];
        const allKeys = Object.keys(historico[0]);
        const excluded = ['id', 'data_hora', 'periodo', 'contagem_entrada', 'contagem_saida', 'descarte', 'percentual_descarte', 'velocidade_real', 'disponibilidade', 'performance', 'qualidade', 'oee', 'tempo_producao'];
        return allKeys.filter(k => !excluded.includes(k));
    }, [historico]);

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
                <h3 className="text-lg font-semibold mb-4 text-gray-700">Variáveis do Equipamento ({equipamento.nome})</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">

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

                    {/* Dynamic Variables (Sensors) */}
                    {dynamicKeys.map(key => (
                        <Card key={key}>
                            <CardHeader className="pb-2"><CardTitle className="text-sm capitalize">{key.replace(/_/g, ' ')}</CardTitle></CardHeader>
                            <CardContent className="h-[200px]">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={historico}>
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis dataKey="data_hora" hide />
                                        <YAxis />
                                        <Tooltip labelFormatter={(v) => format(new Date(v), 'dd/MM HH:mm')} />
                                        <Line type="monotone" dataKey={key} stroke="#9333ea" dot={false} name={key} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default VariablesTab;
