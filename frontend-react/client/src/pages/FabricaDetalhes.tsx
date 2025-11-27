import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ArrowLeft, Activity, TrendingUp, AlertTriangle, Factory } from 'lucide-react';

// ===== TIPOS =====

interface MetricaLinha {
    linha_id: number;
    linha_codigo: string;
    linha_nome: string;
    status: string;
    oee: number;
    disponibilidade: number;
    performance: number;
    qualidade: number;
    contagem_saida: number;
    descarte: number;
    percentual_descarte: number;
    velocidade_real: number;
    data_hora: string | null;
}

interface MetricasFabrica {
    oee_medio: number;
    producao_total: number;
    descarte_total: number;
    linhas: MetricaLinha[];
}

// ===== COMPONENTE PRINCIPAL =====

const FabricaDetalhes: React.FC = () => {
    const navigate = useNavigate();
    const [dados, setDados] = useState<MetricasFabrica | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || 'http://127.0.0.1:8000/api';

    useEffect(() => {
        const fetchDados = async () => {
            try {
                const response = await fetch(`${DJANGO_API_URL}/metricas_fabrica_consolidadas/`);
                if (!response.ok) throw new Error('Falha ao buscar dados da fábrica');

                const linhas: MetricaLinha[] = await response.json();

                // Cálculos consolidados
                const totalLinhas = linhas.length;
                const oeeTotal = linhas.reduce((acc, curr) => acc + curr.oee, 0);
                const producaoTotal = linhas.reduce((acc, curr) => acc + curr.contagem_saida, 0);
                const descarteTotal = linhas.reduce((acc, curr) => acc + curr.descarte, 0);

                setDados({
                    oee_medio: totalLinhas > 0 ? oeeTotal / totalLinhas : 0,
                    producao_total: producaoTotal,
                    descarte_total: descarteTotal,
                    linhas: linhas
                });

            } catch (err) {
                setError(err instanceof Error ? err.message : 'Erro desconhecido');
            } finally {
                setLoading(false);
            }
        };

        fetchDados();
        const interval = setInterval(fetchDados, 30000); // Atualiza a cada 30s
        return () => clearInterval(interval);
    }, [DJANGO_API_URL]);

    // Funções auxiliares de cor
    const getOEEColor = (oee: number): string => {
        if (oee >= 85) return 'text-green-600';
        if (oee >= 70) return 'text-yellow-600';
        return 'text-red-600';
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-screen">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
                    <p className="mt-4 text-gray-600">Carregando dados da fábrica...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-screen">
                <div className="text-center">
                    <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
                    <p className="text-red-600">{error}</p>
                    <Button onClick={() => navigate('/')} className="mt-4">
                        Voltar
                    </Button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 p-6">
            {/* Header */}
            <div className="mb-6">
                <Button
                    variant="ghost"
                    onClick={() => navigate('/')}
                    className="mb-4"
                >
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Voltar
                </Button>

                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
                            <Factory className="h-8 w-8 text-gray-700" />
                            Visão Geral da Fábrica
                        </h1>
                        <p className="text-gray-600 mt-1">
                            Monitoramento consolidado de todas as linhas de produção
                        </p>
                    </div>
                    <div className="text-right">
                        <p className="text-sm text-gray-500">Última atualização</p>
                        <p className="font-medium">{new Date().toLocaleTimeString()}</p>
                    </div>
                </div>
            </div>

            {/* KPIs Globais */}
            {dados && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                    <Card className="bg-white shadow-sm border-l-4 border-l-blue-500">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-gray-600">
                                OEE Médio da Fábrica
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className={`text-4xl font-bold ${getOEEColor(dados.oee_medio)}`}>
                                {dados.oee_medio.toFixed(1)}%
                            </div>
                            <p className="text-xs text-gray-500 mt-1">
                                Média de {dados.linhas.length} linhas ativas
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="bg-white shadow-sm border-l-4 border-l-green-500">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-gray-600">
                                Produção Total (Turno)
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-4xl font-bold text-green-700">
                                {dados.producao_total.toLocaleString()}
                            </div>
                            <p className="text-xs text-gray-500 mt-1">
                                Unidades produzidas
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="bg-white shadow-sm border-l-4 border-l-red-500">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-gray-600">
                                Descarte Total (Turno)
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-4xl font-bold text-red-700">
                                {dados.descarte_total.toLocaleString()}
                            </div>
                            <p className="text-xs text-gray-500 mt-1">
                                Unidades descartadas
                            </p>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* Lista de Linhas */}
            <h2 className="text-xl font-semibold text-gray-800 mb-4">Detalhamento por Linha</h2>
            <div className="grid grid-cols-1 gap-4">
                {dados?.linhas.map((linha) => (
                    <Card
                        key={linha.linha_id}
                        className="hover:shadow-md transition-shadow cursor-pointer"
                        onClick={() => navigate(`/linha/${linha.linha_id}`)}
                    >
                        <CardContent className="p-6">
                            <div className="flex flex-col md:flex-row items-center justify-between gap-4">

                                {/* Info da Linha */}
                                <div className="flex-1 min-w-[200px]">
                                    <div className="flex items-center gap-2 mb-1">
                                        <h3 className="text-lg font-bold text-gray-900">{linha.linha_nome}</h3>
                                        <Badge variant={linha.status === 'Online' ? 'default' : 'secondary'}>
                                            {linha.status}
                                        </Badge>
                                    </div>
                                    <p className="text-sm text-gray-500">{linha.linha_codigo}</p>
                                </div>

                                {/* KPIs da Linha */}
                                <div className="flex flex-1 justify-between gap-8 w-full md:w-auto">
                                    <div className="text-center">
                                        <p className="text-xs text-gray-500 uppercase font-semibold">OEE</p>
                                        <p className={`text-2xl font-bold ${getOEEColor(linha.oee)}`}>
                                            {linha.oee.toFixed(1)}%
                                        </p>
                                    </div>

                                    <div className="text-center">
                                        <p className="text-xs text-gray-500 uppercase font-semibold">Produção</p>
                                        <p className="text-2xl font-bold text-gray-700">
                                            {linha.contagem_saida.toLocaleString()}
                                        </p>
                                    </div>

                                    <div className="text-center">
                                        <p className="text-xs text-gray-500 uppercase font-semibold">Descarte</p>
                                        <p className="text-2xl font-bold text-red-600">
                                            {linha.descarte.toLocaleString()}
                                        </p>
                                        <p className="text-xs text-gray-400">
                                            {linha.percentual_descarte.toFixed(2)}%
                                        </p>
                                    </div>

                                    <div className="text-center hidden md:block">
                                        <p className="text-xs text-gray-500 uppercase font-semibold">Velocidade</p>
                                        <p className="text-2xl font-bold text-blue-600">
                                            {linha.velocidade_real.toFixed(1)}
                                        </p>
                                        <p className="text-xs text-gray-400">un/min</p>
                                    </div>
                                </div>

                                <div className="hidden md:flex items-center justify-end min-w-[100px]">
                                    <Button variant="outline" size="sm">
                                        Detalhes
                                    </Button>
                                </div>

                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
};

export default FabricaDetalhes;