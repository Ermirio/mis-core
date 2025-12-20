
import React from 'react';

interface LossFilterBarProps {
    periodo: string;
    setPeriodo: (p: string) => void;
    isLoading: boolean;
}

const LossFilterBar: React.FC<LossFilterBarProps> = ({ periodo, setPeriodo, isLoading }) => {
    const options = [
        { value: 'TURNO', label: 'Turno Atual' },
        { value: 'DIA', label: 'Hoje' },
        { value: 'SEMANA', label: 'Esta Semana' },
        { value: 'MES', label: 'Este Mês' },
    ];

    return (
        <div className="flex space-x-2 bg-gray-800 p-1 rounded-lg inline-flex">
            {options.map((opt) => (
                <button
                    key={opt.value}
                    onClick={() => setPeriodo(opt.value)}
                    disabled={isLoading}
                    className={`
            px-3 py-1.5 text-sm font-medium rounded-md transition-all duration-200
            ${periodo === opt.value
                            ? 'bg-blue-600 text-white shadow-sm'
                            : 'text-gray-400 hover:text-white hover:bg-gray-700'
                        }
            ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}
          `}
                >
                    {opt.label}
                </button>
            ))}
        </div>
    );
};

export default LossFilterBar;
