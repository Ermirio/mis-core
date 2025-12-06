import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Clock, Activity, CheckCircle, AlertTriangle, XCircle, Settings, PenTool, PauseCircle } from 'lucide-react';

interface EquipmentCardProps {
    id?: number; // Added id prop
    nome: string;
    funcao?: string;
    estado: number; // 0-9
    oee: number;
    velocidadeAtual: number;
    velocidadeNominal: number;
    boas: number;
    ruins: number;
    ultimaParada: string; // "12 min atrás"
}

const EquipmentCard: React.FC<EquipmentCardProps> = ({
    id,
    nome,
    funcao,
    estado,
    oee,
    velocidadeAtual,
    velocidadeNominal,
    boas,
    ruins,
    ultimaParada
}) => {
    const navigate = useNavigate();

    const getStatusInfo = (code: number) => {
        switch (code) {
            case 1: return { label: 'Produzindo', color: 'text-green-600', bg: 'bg-green-100', icon: CheckCircle };
            case 2: return { label: 'Aguardando', color: 'text-yellow-600', bg: 'bg-yellow-100', icon: PauseCircle };
            case 3: return { label: 'Bloqueado', color: 'text-orange-600', bg: 'bg-orange-100', icon: XCircle };
            case 4: return { label: 'Falha', color: 'text-red-600', bg: 'bg-red-100', icon: AlertTriangle };
            case 5: return { label: 'Setup', color: 'text-blue-600', bg: 'bg-blue-100', icon: Settings };
            case 8: return { label: 'Manutenção', color: 'text-gray-600', bg: 'bg-gray-100', icon: PenTool };
            default: return { label: 'Parado', color: 'text-gray-500', bg: 'bg-gray-100', icon: PauseCircle };
        }
    };

    const status = getStatusInfo(estado);
    const StatusIcon = status.icon;

    return (
        <div
            className={`bg-white rounded-lg shadow-sm border border-gray-200 p-4 transition-all hover:shadow-md ${id ? 'cursor-pointer hover:border-indigo-300' : ''}`}
            onClick={() => id && navigate(`/equipamento/${id}`)}
        >
            <div className="flex justify-between items-start mb-3">
                <div>
                    <h3 className="font-bold text-gray-900">{nome}</h3>
                    {funcao && <p className="text-xs text-gray-500">{funcao}</p>}
                </div>
                <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-bold ${status.bg} ${status.color}`}>
                    <StatusIcon className="w-3 h-3" />
                    {status.label.toUpperCase()}
                </div>
            </div>

            <div className="space-y-3">
                {/* OEE */}
                <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">OEE</span>
                    <span className={`font-bold ${oee >= 85 ? 'text-green-600' : oee >= 70 ? 'text-yellow-600' : 'text-red-600'}`}>
                        {oee.toFixed(1)}%
                    </span>
                </div>

                {/* Velocidade */}
                <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Velocidade</span>
                    <span className="font-semibold text-gray-900">
                        {velocidadeAtual.toFixed(0)} <span className="text-gray-400 text-xs">/ {velocidadeNominal} ppm</span>
                    </span>
                </div>

                {/* Produção */}
                <div className="flex justify-between items-center text-sm">
                    <span className="text-gray-600">Boas / Ruins</span>
                    <div>
                        <span className="font-bold text-green-600">{boas.toLocaleString()}</span>
                        <span className="text-gray-300 mx-1">|</span>
                        <span className="font-bold text-red-600">{ruins}</span>
                    </div>
                </div>

                {/* Última Parada */}
                <div className="pt-2 border-t border-gray-100 flex items-center gap-2 text-xs text-gray-500">
                    <Clock className="w-3 h-3" />
                    Última Parada: {ultimaParada}
                </div>
            </div>
        </div>
    );
};

export default EquipmentCard;
