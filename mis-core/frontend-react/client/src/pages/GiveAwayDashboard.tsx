import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
    Scale, TrendingUp, AlertTriangle, RefreshCw,
    CalendarIcon, BarChart3, Factory
} from "lucide-react";
import axios from 'axios';

const DJANGO_API = import.meta.env.VITE_DJANGO_API_URL;

interface GiveAwayData {
    consolidado: {
        giveaway_kg: number;
        giveaway_percent: number;
        producao_ref_kg: number;
    };
    por_linha: Array<{
        linha: string;
        codigo: string;
        equipamento_leitura: string;
        giveaway_kg: number;
        giveaway_percent: number;
        producao_unidades: number;
        producao_nominal_kg: number;
    }>;
}

const GiveAwayDashboard: React.FC = () => {
    const [periodo, setPeriodo] = useState<string>('TURNO');
    const [data, setData] = useState<GiveAwayData | null>(null);
    const [loading, setLoading] = useState(false);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const res = await axios.get(`${DJANGO_API}/giveaway/resumo/?periodo=${periodo}`);
            setData(res.data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, [periodo]);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 60000);
        return () => clearInterval(interval);
    }, [fetchData]);

    return (
        <div className="w-full h-full p-6 bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900 overflow-auto">
            <div className="flex justify-between items-center mb-8">
                <div>
                    <h1 className="text-3xl font-bold flex items-center gap-3 text-slate-800 dark:text-white">
                        <Scale className="h-8 w-8 text-blue-500" />
                        Gestão de Give Away
                    </h1>
                    <p className="text-slate-500 mt-1">Controle de excesso de peso em produtos acabados</p>
                </div>

                <div className="flex gap-4">
                    <Select value={periodo} onValueChange={setPeriodo}>
                        <SelectTrigger className="w-[180px]">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="TURNO">Turno Atual</SelectItem>
                            <SelectItem value="DIA">Hoje</SelectItem>
                            <SelectItem value="MES">Este Mês</SelectItem>
                        </SelectContent>
                    </Select>

                    <Button onClick={fetchData} disabled={loading}>
                        <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                        Atualizar
                    </Button>
                </div>
            </div>

            {/* KPIs */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <Card className="bg-gradient-to-br from-blue-500 to-blue-600 text-white border-0 shadow-lg">
                    <CardContent className="pt-6">
                        <div className="flex justify-between items-start">
                            <div>
                                <p className="text-blue-100 font-medium mb-1">Give Away Total</p>
                                <h2 className="text-4xl font-bold">{data?.consolidado.giveaway_kg.toFixed(1)} kg</h2>
                                <p className="text-blue-200 text-sm mt-2">Neste período</p>
                            </div>
                            <Scale className="h-10 w-10 text-blue-300 opacity-60" />
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-gradient-to-br from-indigo-500 to-violet-600 text-white border-0 shadow-lg">
                    <CardContent className="pt-6">
                        <div className="flex justify-between items-start">
                            <div>
                                <p className="text-indigo-100 font-medium mb-1">Percentual Global</p>
                                <h2 className="text-4xl font-bold">{data?.consolidado.giveaway_percent.toFixed(2)}%</h2>
                                <p className="text-indigo-200 text-sm mt-2">Sobre massa teórica</p>
                            </div>
                            <TrendingUp className="h-10 w-10 text-indigo-300 opacity-60" />
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-white dark:bg-slate-800 border shadow-lg text-slate-800 dark:text-white">
                    <CardContent className="pt-6">
                        <div className="flex justify-between items-start">
                            <div>
                                <p className="text-slate-500 dark:text-slate-400 font-medium mb-1">Produção Teórica</p>
                                <h2 className="text-4xl font-bold">{data?.consolidado.producao_ref_kg.toFixed(0)} kg</h2>
                                <p className="text-slate-500 dark:text-slate-400 text-sm mt-2">Referência de cálculo</p>
                            </div>
                            <Factory className="h-10 w-10 text-slate-300 dark:text-slate-600" />
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Tabela Detalhada */}
            <Card className="shadow-lg">
                <CardHeader>
                    <CardTitle>Detalhamento por Linha</CardTitle>
                    <CardDescription>Ranking de excesso de peso por linha de produção</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b bg-slate-50 dark:bg-slate-800">
                                    <th className="text-left p-4 font-semibold text-slate-600 dark:text-slate-300">Linha</th>
                                    <th className="text-left p-4 font-semibold text-slate-600 dark:text-slate-300">Equipamento (Sensor)</th>
                                    <th className="text-right p-4 font-semibold text-slate-600 dark:text-slate-300">Produção (unid)</th>
                                    <th className="text-right p-4 font-semibold text-slate-600 dark:text-slate-300">Give Away (kg)</th>
                                    <th className="text-right p-4 font-semibold text-slate-600 dark:text-slate-300">% Excesso</th>
                                    <th className="text-center p-4 font-semibold text-slate-600 dark:text-slate-300">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data?.por_linha.map((linha) => (
                                    <tr key={linha.codigo} className="border-b hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                                        <td className="p-4 font-medium">{linha.linha}</td>
                                        <td className="p-4 text-slate-500">{linha.equipamento_leitura}</td>
                                        <td className="p-4 text-right">{linha.producao_unidades.toLocaleString()}</td>
                                        <td className="p-4 text-right font-bold text-red-600 dark:text-red-400">
                                            {linha.giveaway_kg.toFixed(2)}
                                        </td>
                                        <td className="p-4 text-right">
                                            <Badge variant={linha.giveaway_percent > 1.5 ? "destructive" : "secondary"}>
                                                {linha.giveaway_percent.toFixed(2)}%
                                            </Badge>
                                        </td>
                                        <td className="p-4 text-center">
                                            {linha.giveaway_percent > 2.0 ? (
                                                <span className="flex items-center justify-center gap-1 text-red-500 font-medium">
                                                    <AlertTriangle className="h-4 w-4" /> Crítico
                                                </span>
                                            ) : (
                                                <span className="text-green-500 font-medium">Normal</span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

export default GiveAwayDashboard;
