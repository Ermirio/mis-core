import React from 'react';

interface TimelineProps {
    equipamentos: string[];
}

const Timeline: React.FC<TimelineProps> = ({ equipamentos }) => {
    // Mock data generator for visual purposes until backend is fully ready
    const generateMockSegments = () => {
        const segments = [];
        let current = 0;
        while (current < 100) {
            const width = Math.random() * 20 + 5;
            const state = Math.random();
            let color = 'bg-green-500'; // Produzindo
            if (state > 0.8) color = 'bg-yellow-400'; // Aguardando
            else if (state > 0.9) color = 'bg-red-500'; // Falha
            else if (state > 0.95) color = 'bg-blue-500'; // Setup

            segments.push({ width: Math.min(width, 100 - current), color });
            current += width;
        }
        return segments;
    };

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Timeline da Linha (24h)</h2>

            <div className="space-y-4">
                {equipamentos.map((eq, idx) => (
                    <div key={idx} className="flex items-center gap-4">
                        <div className="w-24 text-sm font-semibold text-gray-700 truncate" title={eq}>
                            {eq}
                        </div>
                        <div className="flex-1 h-8 bg-gray-100 rounded overflow-hidden flex">
                            {generateMockSegments().map((seg, i) => (
                                <div
                                    key={i}
                                    className={`${seg.color} h-full border-r border-white/20`}
                                    style={{ width: `${seg.width}%` }}
                                />
                            ))}
                        </div>
                    </div>
                ))}
            </div>

            <div className="flex gap-4 mt-4 text-xs text-gray-500 justify-end">
                <div className="flex items-center gap-1"><div className="w-3 h-3 bg-green-500 rounded-sm"></div> Produzindo</div>
                <div className="flex items-center gap-1"><div className="w-3 h-3 bg-yellow-400 rounded-sm"></div> Aguardando</div>
                <div className="flex items-center gap-1"><div className="w-3 h-3 bg-red-500 rounded-sm"></div> Falha</div>
                <div className="flex items-center gap-1"><div className="w-3 h-3 bg-blue-500 rounded-sm"></div> Setup</div>
            </div>
        </div>
    );
};

export default Timeline;
