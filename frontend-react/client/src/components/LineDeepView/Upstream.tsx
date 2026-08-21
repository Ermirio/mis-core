import React from 'react';
import { ArrowDown } from 'lucide-react';

const Upstream: React.FC = () => {
    // Mock data
    const items = [
        { name: 'Silo 04', status: 'Normal', detail: 'Nível 78%', color: 'text-green-600' },
        { name: 'Rosca 02', status: 'Warning', detail: 'Vibração Alta', color: 'text-orange-600' },
        { name: 'Misturador 01', status: 'Normal', detail: 'Disponível', color: 'text-green-600' }
    ];

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Suprimento (Upstream)</h2>

            <div className="space-y-4">
                {items.map((item, idx) => (
                    <div key={idx} className="flex justify-between items-center border-b border-gray-50 pb-2 last:border-0">
                        <div>
                            <p className="font-semibold text-gray-800">{item.name}</p>
                            <p className={`text-xs font-bold ${item.color}`}>{item.detail}</p>
                        </div>
                        <div className={`w-2 h-2 rounded-full ${item.status === 'Normal' ? 'bg-green-500' : 'bg-orange-500'}`}></div>
                    </div>
                ))}
            </div>

            <div className="mt-4 flex justify-center text-gray-400">
                <ArrowDown className="w-5 h-5 animate-bounce" />
            </div>
        </div>
    );
};

export default Upstream;
