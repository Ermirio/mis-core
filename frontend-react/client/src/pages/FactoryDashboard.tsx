import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import LineOverview from '@/components/LineOverview';
import { Button } from '@/components/ui/button';
import { RefreshCw, LayoutDashboard } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { StrategicAnalysis } from '@/components/StrategicAnalysis';

interface FactoryMetric {
    linha_id: number;
    linha_nome: string;
    status: string;
    oee: number;
    toneladas_produzidas: number;
    toneladas_produzidas_op?: number;
    vazao_real_ton_hora: number;
    formato_gramas: number;
    sku_codigo: string;
    sku_descricao: string;
    ordem_producao?: string;
    meta_producao?: number;
    projecao?: {
        produzido: number;
        meta: number;
        projecao_realista: number;
        projecao_otimista: number;
        status: string;
        meta_atual?: number;
    };
    contagem_saida: number;
    equipamentos_online?: number;
    total_equipamentos?: number;
}

const FactoryDashboard: React.FC = () => {
    const navigate = useNavigate();
    const [metrics, setMetrics] = useState<FactoryMetric[]>([]);
    const [loading, setLoading] = useState(true);
    const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

    const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || 'http://127.0.0.1:8000/api';

    const fetchData = async () => {
        setLoading(true);
        try {
            const response = await fetch(`${DJANGO_API_URL}/metricas_fabrica_consolidadas/`);
            if (response.ok) {
                const data = await response.json();
                setMetrics(data);
                setLastUpdate(new Date());
            }
        } catch (error) {
            console.error("Erro ao buscar métricas da fábrica:", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 30000); // 30s refresh
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="min-h-screen bg-gray-50 p-6">
            <div className="max-w-7xl mx-auto space-y-6">

                {/* Header */}
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
                            <LayoutDashboard className="w-8 h-8 text-blue-600" />
                            Painel da Fábrica
                        </h1>
                        <p className="text-gray-500 mt-1">
                            Visão consolidada de todas as linhas de produção
                        </p>
                    </div>

                    <div className="flex items-center gap-4">
                        <span className="text-sm text-gray-500">
                            Atualizado em: {lastUpdate.toLocaleTimeString()}
                        </span>
                        <Button onClick={fetchData} variant="outline" size="sm" className="gap-2">
                            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                            Atualizar
                        </Button>
                    </div>
                </div>

                <Tabs defaultValue="overview" className="w-full">
                    <TabsList className="grid w-full grid-cols-2 max-w-[400px]">
                        <TabsTrigger value="overview">Visão Geral</TabsTrigger>
                        <TabsTrigger value="strategic">Análise Estratégica</TabsTrigger>
                    </TabsList>

                    <TabsContent value="overview" className="mt-6">
                        {/* Grid de Linhas */}
                        <div className="grid grid-cols-1 gap-6">
                            {metrics.map((metric) => (
                                <div
                                    key={metric.linha_id}
                                    onClick={() => navigate(`/linha/${metric.linha_id}`)}
                                    className="cursor-pointer transition-transform hover:scale-[1.01]"
                                >
                                    <LineOverview
                                        nome={metric.linha_nome}
                                        ole={metric.oee || 0}
                                        totalEquipamentos={metric.total_equipamentos || 0}
                                        equipamentosOnline={metric.equipamentos_online || 0}
                                        toneladasTurno={metric.toneladas_produzidas || 0}
                                        toneladasProduzidasOP={metric.toneladas_produzidas_op || 0}
                                        vazaoTurno={metric.vazao_real_ton_hora}
                                        formatoAtual={metric.formato_gramas}
                                        sku={metric.sku_codigo}
                                        descricao={metric.sku_descricao}
                                        ordemProducao={metric.ordem_producao}
                                        metaProducao={metric.meta_producao}
                                        projecao={metric.projecao}
                                    />
                                </div>
                            ))}

                            {metrics.length === 0 && !loading && (
                                <div className="text-center py-12 text-gray-500 bg-white rounded-lg border border-dashed border-gray-300">
                                    Nenhuma linha ativa encontrada.
                                </div>
                            )}
                        </div>
                    </TabsContent>

                    <TabsContent value="strategic" className="mt-6">
                        {metrics.length > 0 ? (
                            <StrategicAnalysis linhaId={metrics[0].linha_id} />
                        ) : (
                            <div className="text-center py-12 text-gray-500">
                                Carregando dados ou nenhuma linha disponível...
                            </div>
                        )}
                    </TabsContent>
                </Tabs>
            </div>
        </div>
    );
};

export default FactoryDashboard;