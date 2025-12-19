import React from 'react';
import { Activity, Box, Package, Tag, Zap, Scale } from 'lucide-react';

interface HeaderProps {
    linha: string;
    op: string;
    sku: string;
    produto: string;
    cuc: string;
    equipamentosOnline: number;
    totalEquipamentos: number;
    vazao: number;
    ole: number;
    status?: string;
    formato?: number; // NEW
}

const Header: React.FC<HeaderProps> = ({
    linha,
    op,
    sku,
    produto,
    cuc,
    equipamentosOnline,
    totalEquipamentos,
    vazao,
    ole,
    status = 'Em Produção',
    formato = 0
}) => {
    const isOffline = status === 'Sem Comunicação' || status === 'Offline';

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">

                {/* Left Info */}
                <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                        <h1 className="text-2xl font-bold text-gray-900">{linha}</h1>
                        <span className={`px-2 py-1 text-xs font-semibold rounded-full ${isOffline ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
                            }`}>
                            {status}
                        </span>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
                        <div className="flex items-center gap-2">
                            <Tag className="w-4 h-4 text-gray-400" />
                            <div>
                                <p className="text-xs text-gray-500">OP</p>
                                <p className="font-semibold text-gray-900">{op}</p>
                            </div>
                        </div>

                        <div className="flex items-center gap-2">
                            <Package className="w-4 h-4 text-gray-400" />
                            <div>
                                <p className="text-xs text-gray-500">SKU</p>
                                <p className="font-semibold text-gray-900">{sku}</p>
                            </div>
                        </div>

                        <div className="flex items-center gap-2">
                            <Box className="w-4 h-4 text-gray-400" />
                            <div>
                                <p className="text-xs text-gray-500">Produto</p>
                                <p className="font-semibold text-gray-900 truncate max-w-[150px]" title={produto}>{produto}</p>
                            </div>
                        </div>

                        <div className="flex items-center gap-2">
                            <Activity className="w-4 h-4 text-gray-400" />
                            <div>
                                <p className="text-xs text-gray-500">Vazão</p>
                                <p className="font-semibold text-gray-900">{vazao.toFixed(1)} t/h</p>
                            </div>
                        </div>

                        <div className="flex items-center gap-2">
                            <Scale className="w-4 h-4 text-gray-400" />
                            <div>
                                <p className="text-xs text-gray-500">Formato</p>
                                <p className="font-semibold text-gray-900">{formato ? `${formato}g` : 'N/A'}</p>
                            </div>
                        </div>
                    </div>

                    <div className="mt-4 flex items-center gap-4 text-sm text-gray-600">
                        <span className="flex items-center gap-1">
                            <Zap className="w-4 h-4 text-green-500" />
                            Equipamentos Online: <span className="font-semibold text-gray-900">{equipamentosOnline} de {totalEquipamentos}</span>
                        </span>
                        <span className="text-gray-300">|</span>
                        <span>CUC: <span className="font-mono text-gray-900">{cuc}</span></span>
                    </div>
                </div>

                {/* Right OLE */}
                <div className="flex flex-col items-center justify-center p-4 bg-gray-50 rounded-xl border border-gray-100 min-w-[180px]">
                    <span className="text-sm font-semibold text-gray-500 mb-1">OLE (OMAC)</span>
                    <span className={`text-4xl font-bold ${ole >= 85 ? 'text-green-600' : ole >= 70 ? 'text-yellow-600' : 'text-red-600'}`}>
                        {ole.toFixed(1)}%
                    </span>
                    <span className="text-xs text-gray-400 mt-1">Eficiência da Linha</span>
                </div>

            </div>
        </div>
    );
};

export default Header;
