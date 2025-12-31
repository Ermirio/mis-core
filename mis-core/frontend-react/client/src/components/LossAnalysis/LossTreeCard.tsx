
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TreeDeciduous } from 'lucide-react';
import LossFilterBar from './LossFilterBar';
import LossWaterfallChart from './LossWaterfallChart';
import LossEquipmentRanking from './LossEquipmentRanking';

interface LossTreeCardProps {
    linhaId: number;
    djangoUrl: string;
}

const LossTreeCard: React.FC<LossTreeCardProps> = ({ linhaId, djangoUrl }) => {
    const [periodo, setPeriodo] = useState('TURNO');
    const [data, setData] = useState<any>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchLossData = async (isInitial = false) => {
        if (!linhaId) return;

        if (isInitial) setIsLoading(true);
        setError(null);
        try {
            const response = await fetch(`${djangoUrl}/linhas/${linhaId}/perdas-analise/?periodo=${periodo}`);
            if (!response.ok) {
                throw new Error('Falha ao buscar dados de perdas');
            }
            const jsonData = await response.json();
            setData(jsonData);
        } catch (err: any) {
            console.error(err);
            setError(err.message);
        } finally {
            if (isInitial) setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchLossData(true);

        // Auto-refresh a cada 5s para feedback rápido
        const interval = setInterval(() => fetchLossData(false), 5000);
        return () => clearInterval(interval);
    }, [linhaId, periodo, djangoUrl]);

    return (
        <Card className="bg-gray-800 border-gray-700 shadow-xl mt-6">
            <CardHeader className="flex flex-row items-center justify-between pb-2 border-b border-gray-700/50">
                <div className="flex items-center gap-2">
                    <div className="p-2 bg-purple-500/20 rounded-lg">
                        <TreeDeciduous className="w-5 h-5 text-purple-400" />
                    </div>
                    <div>
                        <CardTitle className="text-lg font-bold text-white">
                            Árvore de Perdas Consolidada
                        </CardTitle>
                        <p className="text-xs text-gray-200 mt-1">
                            Análise detalhada de disponibilidade, performance e qualidade
                        </p>
                    </div>
                </div>

                <LossFilterBar
                    periodo={periodo}
                    setPeriodo={setPeriodo}
                    isLoading={isLoading}
                />
            </CardHeader>

            <CardContent className="p-6">
                {error ? (
                    <div className="text-red-400 p-4 bg-red-900/20 rounded border border-red-900">
                        Erro: {error}
                    </div>
                ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <LossWaterfallChart data={data?.waterfall} isLoading={isLoading} />
                        <LossEquipmentRanking data={data?.equipment_ranking} isLoading={isLoading} />
                    </div>
                )}

                <div className="mt-4 text-xs text-gray-500 text-center flex justify-center gap-6">
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500"></span> Produção Boa</span>
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500"></span> Perda Planejada (Setup)</span>
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500"></span> Perda Não Planejada (Falhas)</span>
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500"></span> Perda Performance</span>
                </div>
            </CardContent>
        </Card>
    );
};

export default LossTreeCard;
