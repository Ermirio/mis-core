import React from 'react';
import { ArrowRight } from 'lucide-react';

const Downstream: React.FC = () => {
    // Mock data
    const items = [
        { name: 'Armazém / Expedição', percentage: 84 },
        { name: 'WIP', percentage: 12 },
        { name: 'Reprocesso', percentage: 4 }
    ];

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Destino (Downstream)</h2>

            <div className="space-y-4">
                {items.map((item, idx) => (
                    <div key={idx}>
                        <div className="flex justify-between text-sm mb-1">
                            <span className="font-semibold text-gray-700">{item.name}</span>
                            <span className="font-bold text-gray-900">{item.percentage}%</span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
                            <div
                                className="bg-blue-600 h-2 rounded-full"
                                style={{ width: `${item.percentage}%` }}
                            ></div>
                        </div>
                    </div>
                ))}
            </div>

            <div className="mt-4 flex justify-center text-gray-400">
                <ArrowRight className="w-5 h-5" />
            </div>
        </div>
    );
};

export default Downstream;
