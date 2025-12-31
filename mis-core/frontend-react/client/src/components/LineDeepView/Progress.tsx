import React from 'react';

interface ProgressProps {
    producaoReal: number;
    producaoEsperada: number;
    projecao: number;
    metaTurno: number;
    tempoDecorridoPerc: number;
}

const Progress: React.FC<ProgressProps> = ({
    producaoReal,
    producaoEsperada,
    projecao,
    metaTurno,
    tempoDecorridoPerc
}) => {
    // Cálculos de porcentagem para as barras (baseado na Meta Total)
    const percReal = Math.min((producaoReal / metaTurno) * 100, 100);
    const percEsperado = Math.min((producaoEsperada / metaTurno) * 100, 100);
    const percProjecao = Math.min((projecao / metaTurno) * 100, 100);

    const atraso = producaoReal - producaoEsperada;
    const isAtrasado = atraso < 0;

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-bold text-gray-900">Progresso do Turno</h2>
                <span className="text-sm text-gray-500">Meta Total: <span className="font-bold text-gray-900">{metaTurno.toFixed(1)} t</span></span>
            </div>

            <div className="space-y-6">

                {/* Produção Real */}
                <div>
                    <div className="flex justify-between text-sm mb-1">
                        <span className="font-semibold text-blue-700">Produção Real</span>
                        <span className="font-bold text-blue-700">{producaoReal.toFixed(3)} t</span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-4 overflow-hidden">
                        <div
                            className="bg-blue-600 h-4 rounded-full transition-all duration-500"
                            style={{ width: `${percReal}%` }}
                        ></div>
                    </div>
                </div>

                {/* Esperado (Até Agora) */}
                <div>
                    <div className="flex justify-between text-sm mb-1">
                        <span className="font-semibold text-gray-600">Esperado (Até Agora)</span>
                        <span className="font-bold text-gray-600">{producaoEsperada.toFixed(3)} t</span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-4 overflow-hidden relative">
                        <div
                            className="bg-gray-400 h-4 rounded-full transition-all duration-500"
                            style={{ width: `${percEsperado}%` }}
                        ></div>
                        {/* Marcador de Atraso */}
                        {isAtrasado && (
                            <div className="absolute top-5 right-0 text-xs font-bold text-red-600">
                                Atraso: {atraso.toFixed(2)} t
                            </div>
                        )}
                    </div>
                </div>

                {/* Projeção */}
                <div>
                    <div className="flex justify-between text-sm mb-1">
                        <span className={`font-semibold ${projecao >= metaTurno ? 'text-green-600' : 'text-yellow-700'}`}>Projeção (Fim do Turno)</span>
                        <span className={`font-bold ${projecao >= metaTurno ? 'text-green-600' : 'text-yellow-700'}`}>{projecao.toFixed(1)} t</span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-4 overflow-hidden">
                        <div
                            className={`${projecao >= metaTurno ? 'bg-green-500/50' : 'bg-yellow-500'} h-4 rounded-full transition-all duration-500`}
                            style={{ width: `${percProjecao}%` }}
                        ></div>
                    </div>
                </div>

            </div>
        </div>
    );
};

export default Progress;
