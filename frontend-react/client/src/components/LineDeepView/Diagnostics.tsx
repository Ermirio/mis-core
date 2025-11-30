import React from 'react';
import { AlertCircle } from 'lucide-react';

const Diagnostics: React.FC = () => {
    // Mock alerts for now
    const alerts = [
        "ZUCHINNI com performance abaixo de 80% nos últimos 6 min.",
        "ACMA apresentou 4 microparadas nas últimas 2 horas.",
        "Projeção indica atraso de 7.6 t no fechamento do turno."
    ];

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-orange-500" />
                Diagnósticos Inteligentes
            </h2>

            <ul className="space-y-3">
                {alerts.map((alert, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm text-gray-700 bg-orange-50 p-3 rounded border border-orange-100">
                        <span className="w-1.5 h-1.5 rounded-full bg-orange-500 mt-1.5 flex-shrink-0"></span>
                        {alert}
                    </li>
                ))}
            </ul>
        </div>
    );
};

export default Diagnostics;
