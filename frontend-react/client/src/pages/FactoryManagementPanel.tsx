import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    LayoutDashboard,
    RefreshCw,
    TrendingUp,
    TrendingDown,
    AlertTriangle,
    Activity,
    Factory
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';

// Interface matching the API response
interface LineKPI {
    linha: string;
    oee_real: number;
    oee_planejado: number | null;
    producao_real_t: number;
    producao_planejada_t: number;
    tph_real: number;
    status: string;
}

interface LayoutItem {
    linha: string;
    area: string;
    posicao_x: number;
    posicao_y: number;
    w?: number;
    h?: number;
    critico: boolean;
}

interface FactoryData {
    oee_fabril_real: number;
    oee_fabril_planejado: number;
    producao_real_t: number;
    producao_planejada_t: number;
    vazao_total_tph: number;
    vazao_necessaria_tph: number; // New field
    linhas: LineKPI[];
    layout_fabrica: LayoutItem[];
}

const FLASK_API_URL = import.meta.env.VITE_FLASK_API_URL || 'http://localhost:5000/api';

const FactoryManagementPanel: React.FC = () => {
    const navigate = useNavigate();
    const [data, setData] = useState<FactoryData | null>(null);
    const [loading, setLoading] = useState(true);
    const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
    const [period, setPeriod] = useState<string>('turno');

    const [mapData, setMapData] = useState<any[]>([]);

    const fetchData = async () => {
        setLoading(true);
        try {
            // Fetch KPIs
            const responseKpis = await fetch(`${FLASK_API_URL}/fabrica/kpis?period=${period}`);
            if (responseKpis.ok) {
                const jsonData = await responseKpis.json();
                setData(jsonData);
            }

            // Fetch Map Data (Dedicated Route)
            // Add timestamp to prevent caching
            const responseMap = await fetch(`${FLASK_API_URL}/fabrica/mapa?t=${new Date().getTime()}`);
            if (responseMap.ok) {
                const jsonMap = await responseMap.json();
                setMapData(jsonMap);
            }

            setLastUpdate(new Date());
        } catch (error) {
            console.error("Error fetching factory data:", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 10000); // 10s refresh
        return () => clearInterval(interval);
    }, [period]);

    if (loading && !data) {
        return <div className="p-10 text-center">Carregando Painel Fabril...</div>;
    }

    if (!data) {
        return <div className="p-10 text-center text-red-500">Erro ao carregar dados.</div>;
    }

    // Sort lines for ranking (by OEE)
    const sortedLines = [...data.linhas].sort((a, b) => b.oee_real - a.oee_real);

    return (
        <div className="min-h-screen bg-gray-50 p-6">
            <div className="max-w-7xl mx-auto space-y-6">

                {/* Header */}
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
                            <Factory className="w-8 h-8 text-indigo-600" />
                            Fábrica – Visão Geral
                        </h1>
                        <p className="text-gray-500 mt-1">
                            Monitoramento consolidado em tempo real
                        </p>
                    </div>

                    <div className="flex items-center gap-4">
                        <div className="bg-white rounded-lg border border-gray-200 p-1 flex">
                            {['turno', 'dia', 'semana', 'mes'].map((p) => (
                                <button
                                    key={p}
                                    onClick={() => setPeriod(p)}
                                    className={`
                                        px-3 py-1 text-xs font-medium rounded-md transition-colors capitalize
                                        ${period === p ? 'bg-indigo-100 text-indigo-700' : 'text-gray-500 hover:bg-gray-50'}
                                    `}
                                >
                                    {p === 'mes' ? 'Mês' : p}
                                </button>
                            ))}
                        </div>

                        <span className="text-sm text-gray-500">
                            Atualizado: {lastUpdate.toLocaleTimeString()}
                        </span>
                        <Button onClick={fetchData} variant="outline" size="sm" className="gap-2">
                            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                            Atualizar
                        </Button>
                    </div>
                </div>

                {/* Top KPIs Cards */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    {/* OEE Fabril */}
                    <Card className="border-l-4 border-l-indigo-500">
                        <CardContent className="pt-6">
                            <div className="flex justify-between items-start">
                                <div>
                                    <p className="text-sm font-medium text-gray-500">OEE Fabril</p>
                                    <h3 className="text-3xl font-bold text-indigo-700 mt-2">{data.oee_fabril_real}%</h3>
                                </div>
                                <Activity className="w-6 h-6 text-indigo-200" />
                            </div>
                            <div className="mt-4">
                                <div className="flex justify-between text-xs mb-1">
                                    <span>Meta: {data.oee_fabril_planejado || 85}%</span>
                                </div>
                                <Progress value={data.oee_fabril_real} className="h-2" />
                            </div>
                        </CardContent>
                    </Card>

                    {/* Vazão Total */}
                    <Card className="border-l-4 border-l-blue-500">
                        <CardContent className="pt-6">
                            <div className="flex justify-between items-start">
                                <div>
                                    <p className="text-sm font-medium text-gray-500">Vazão Total</p>
                                    <h3 className="text-3xl font-bold text-blue-700 mt-2">{data.vazao_total_tph} t/h</h3>
                                </div>
                                <TrendingUp className="w-6 h-6 text-blue-200" />
                            </div>
                            <p className="text-xs text-gray-400 mt-4">
                                Necessária: <span className="font-bold text-blue-600">{data.vazao_necessaria_tph || 0} t/h</span>
                            </p>
                        </CardContent>
                    </Card>

                    {/* Produção Real */}
                    <Card className="border-l-4 border-l-green-500">
                        <CardContent className="pt-6">
                            <div className="flex justify-between items-start">
                                <div>
                                    <p className="text-sm font-medium text-gray-500">Produção Real</p>
                                    <h3 className="text-3xl font-bold text-green-700 mt-2">{data.producao_real_t} t</h3>
                                </div>
                                <Factory className="w-6 h-6 text-green-200" />
                            </div>
                            <div className="mt-4 text-xs text-gray-500">
                                Planejado: {data.producao_planejada_t} t
                            </div>
                        </CardContent>
                    </Card>

                    {/* Linhas Ativas */}
                    <Card className="border-l-4 border-l-orange-500">
                        <CardContent className="pt-6">
                            <div className="flex justify-between items-start">
                                <div>
                                    <p className="text-sm font-medium text-gray-500">Linhas Ativas</p>
                                    <h3 className="text-3xl font-bold text-orange-700 mt-2">
                                        {data.linhas.filter(l => ['Rodando', 'Produzindo', 'Online'].includes(l.status)).length} / {data.linhas.length}
                                    </h3>
                                </div>
                                <AlertTriangle className="w-6 h-6 text-orange-200" />
                            </div>
                            <p className="text-xs text-gray-400 mt-4">Monitoramento em tempo real</p>
                        </CardContent>
                    </Card>
                </div>

                {/* Ranking de Linhas (Horizontal) */}
                <Card>
                    <CardHeader>
                        <CardTitle>Ranking de Performance</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                            {sortedLines.map((line, idx) => {
                                let rankStyle = {
                                    emoji: '',
                                    bg: 'bg-gray-50',
                                    border: 'border-gray-100',
                                    badge: 'bg-gray-200 text-gray-600'
                                };

                                if (idx === 0) rankStyle = { emoji: '🥇', bg: 'bg-yellow-50', border: 'border-yellow-200', badge: 'bg-yellow-100 text-yellow-700' };
                                else if (idx === 1) rankStyle = { emoji: '🥈', bg: 'bg-slate-50', border: 'border-slate-200', badge: 'bg-slate-200 text-slate-700' };
                                else if (idx === 2) rankStyle = { emoji: '🥉', bg: 'bg-orange-50', border: 'border-orange-200', badge: 'bg-orange-100 text-orange-800' };

                                return (
                                    <div
                                        key={line.linha}
                                        className={`flex items-center justify-between p-3 rounded-lg hover:bg-white hover:shadow-md cursor-pointer transition border ${rankStyle.bg} ${rankStyle.border}`}
                                        onClick={() => navigate(`/linha/${line.linha}/detalhes`)}
                                    >
                                        <div className="flex items-center gap-3">
                                            <div className={`
                                                w-8 h-8 flex items-center justify-center rounded-full text-sm font-bold shadow-sm
                                                ${rankStyle.badge}
                                            `}>
                                                {rankStyle.emoji || idx + 1}
                                            </div>
                                            <div>
                                                <p className="font-bold text-gray-900 text-sm">{line.linha}</p>
                                                <p className="text-[10px] text-gray-500">{line.status}</p>
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <p className="font-bold text-indigo-600 text-sm">{line.oee_real}%</p>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>

                {/* Mapa do Chão de Fábrica (Full Width) */}
                <Card>
                    <CardHeader>
                        <CardTitle>Mapa do Chão de Fábrica</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="relative w-full h-[600px] bg-gray-100 rounded-xl border border-gray-200 p-6 overflow-hidden">
                            {/* Background */}
                            <div className="absolute inset-0 opacity-10"
                                style={{ backgroundImage: 'radial-gradient(#4f46e5 1px, transparent 1px)', backgroundSize: '20px 20px' }}>
                            </div>

                            {/* Layout Rendering */}
                            {mapData.map((item) => {
                                // item structure: { linha, status, ole, layout: { ... } }
                                const layout = item.layout;
                                const isRunning = item.status === 'Produzindo' || item.status === 'Rodando' || item.status === 'Online';
                                const isGhost = !item.status || item.status === 'Sem Dados';
                                // Fix: Critical lines shouldn't be red unless there's an issue
                                const isAlert = (item.ole < 60 && !isGhost) || item.status === 'Falha' || item.status === 'Parado/Falha';

                                // Positioning logic (14x5 grid approx based on previous code)
                                const unitW = 100 / 14;
                                const unitH = 100 / 5;

                                const left = `${layout.pos_x * unitW}%`;
                                const top = `${layout.pos_y * unitH}%`;
                                const width = `${(layout.w || 1) * unitW - 1}%`; // -1% gap
                                const height = `${(layout.h || 1) * unitH - 1}%`; // -1% gap

                                return (
                                    <div
                                        key={item.linha}
                                        className={`
                                            absolute p-2 rounded-lg shadow-sm border-2 transition-all hover:scale-105 cursor-pointer flex flex-col justify-between
                                            ${isGhost ? 'border-gray-200 bg-gray-50 opacity-60' :
                                                isAlert ? 'border-red-400 bg-red-50' :
                                                    isRunning ? 'border-green-400 bg-white' : 'border-gray-300 bg-gray-50'}
                                        `}
                                        style={{ left, top, width, height }}
                                        onClick={() => !isGhost && navigate(`/linha/${item.linha}/detalhes`)}
                                    >
                                        <div className="flex justify-between items-start">
                                            <span className={`font-bold text-xs truncate ${isGhost ? 'text-gray-400' : 'text-gray-800'}`}>{item.linha}</span>
                                            {isAlert && <AlertTriangle className="w-3 h-3 text-red-500 animate-pulse" />}
                                        </div>

                                        {!isGhost ? (
                                            <div className="space-y-1 mt-1">
                                                <div className="flex justify-between text-[10px]">
                                                    <span>OLE</span>
                                                    <span className="font-bold">{item.ole}%</span>
                                                </div>
                                                <div className="w-full bg-gray-200 rounded-full h-1">
                                                    <div
                                                        className={`h-1 rounded-full ${item.ole < 60 ? 'bg-red-500' : 'bg-green-500'}`}
                                                        style={{ width: `${Math.min(item.ole, 100)}%` }}
                                                    />
                                                </div>
                                                <div className="text-[9px] text-gray-500 truncate">
                                                    {item.status}
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="flex items-center justify-center h-full">
                                                <span className="text-[10px] text-gray-400">Sem dados</span>
                                            </div>
                                        )}
                                    </div>
                                );
                            })}

                            {/* Legend */}
                            <div className="absolute bottom-4 right-4 bg-white/90 p-2 rounded text-xs space-y-1 shadow-sm">
                                <div className="flex items-center gap-2"><div className="w-3 h-3 bg-white border-2 border-green-400 rounded"></div> Operando</div>
                                <div className="flex items-center gap-2"><div className="w-3 h-3 bg-red-50 border-2 border-red-400 rounded"></div> Crítico / Parado</div>
                                <div className="flex items-center gap-2"><div className="w-3 h-3 bg-gray-50 border-2 border-gray-200 rounded"></div> Sem Dados</div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};

export default FactoryManagementPanel;
