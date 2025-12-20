import { mapEstado } from '@/utils/equipmentStateUtils';
import { Clock } from 'lucide-react';

interface EquipmentCardProps {
    nome: string;
    funcao?: string;
    estado: number | string; // Allow flexible input like Home
    oee: number;
    velocidadeAtual: number;
    velocidadeNominal: number;
    boas: number;
    ruins: number;
    ultimaParada: string; // "12 min atrás"
}

const EquipmentCard: React.FC<EquipmentCardProps> = ({
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

    const estadoInfo = mapEstado(estado);

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex justify-between items-start mb-3">
                <div>
                    <h3 className="font-bold text-gray-900">{nome}</h3>
                    {funcao && <p className="text-xs text-gray-500">{funcao}</p>}
                </div>
                <div
                    className="flex items-center gap-1 px-2 py-1 rounded-full text-xs font-bold"
                    style={{ backgroundColor: estadoInfo.corFundo, color: estadoInfo.corHex }}
                >
                    <span className="w-3 h-3 flex items-center justify-center">{estadoInfo.icon}</span>
                    {estadoInfo.nome.toUpperCase()}
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
