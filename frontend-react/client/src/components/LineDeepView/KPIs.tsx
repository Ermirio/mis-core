import React from 'react';
import { AlertTriangle, TrendingUp, TrendingDown } from 'lucide-react';

interface KPIsProps {
    availability: number;
    performance: number;
    quality: number;
    bottleneck: { name: string; oee: number };
    ritmoAtual: number;
    ritmoNecessario: number;
    desvioProjetado: number;
}

const KPIs: React.FC<KPIsProps> = ({
    availability,
    performance,
    quality,
    bottleneck,
    ritmoAtual,
    ritmoNecessario,
    desvioProjetado
}) => {
    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">KPIs da Linha</h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                {/* Availability */}
                <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
                    <p className="text-sm text-blue-700 font-semibold mb-1">Disponibilidade</p>
                    <p className="text-2xl font-bold text-blue-900">{availability.toFixed(1)}%</p>
                </div>

                {/* Performance */}
                <div className="p-4 bg-purple-50 rounded-lg border border-purple-100">
                    <p className="text-sm text-purple-700 font-semibold mb-1">Performance</p>
                    <p className="text-2xl font-bold text-purple-900">{performance.toFixed(1)}%</p>
                </div>

                {/* Quality */}
                <div className="p-4 bg-green-50 rounded-lg border border-green-100">
                    <p className="text-sm text-green-700 font-semibold mb-1">Qualidade</p>
                    <p className="text-2xl font-bold text-green-900">{quality.toFixed(1)}%</p>
                </div>
            </div>

            <div className="border-t border-gray-100 pt-4 grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Bottleneck */}
                <div>
                    <p className="text-sm text-gray-500 mb-2">Gargalo Atual</p>
                    <div className="flex items-center gap-2 text-red-600 bg-red-50 p-3 rounded-lg border border-red-100">
                        <AlertTriangle className="w-5 h-5" />
                        <span className="font-bold">{bottleneck.name}</span>
                        <span className="text-sm">({bottleneck.oee.toFixed(1)}%)</span>
                    </div>
                </div>

                {/* Ritmo e Desvio */}
                <div className="space-y-3">
                    <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">Ritmo Atual:</span>
                        <span className="font-bold text-gray-900">{ritmoAtual.toFixed(1)} t/h</span>
                    </div>
                    <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">Ritmo Necessário:</span>
                        <span className="font-bold text-gray-900">{ritmoNecessario.toFixed(1)} t/h</span>
                    </div>
                    <div className="flex justify-between items-center pt-2 border-t border-gray-100">
                        <span className="text-sm text-gray-600">Desvio Projetado:</span>
                        <div className={`flex items-center gap-1 font-bold ${desvioProjetado < 0 ? 'text-red-600' : 'text-green-600'}`}>
                            {desvioProjetado < 0 ? <TrendingDown className="w-4 h-4" /> : <TrendingUp className="w-4 h-4" />}
                            {desvioProjetado > 0 ? '+' : ''}{desvioProjetado.toFixed(1)} t
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default KPIs;
