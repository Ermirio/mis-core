import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Calendar, Clock, ChevronDown } from 'lucide-react';

/**
 * DateRangePicker - Componente de seleção de período de tempo
 * 
 * Props:
 * - startDate: Date - Data/hora inicial
 * - endDate: Date - Data/hora final
 * - onRangeChange: (start, end) => void - Callback quando o período muda
 * - showPresets: boolean - Mostrar botões de preset (default: true)
 * - allowNow: boolean - Permitir "now" como fim (default: true)
 */
export function DateRangePicker({
    startDate,
    endDate,
    onRangeChange,
    showPresets = true,
    allowNow = true,
    className = ''
}) {
    const [isOpen, setIsOpen] = useState(false);
    const [activePreset, setActivePreset] = useState('12h');
    const [customStart, setCustomStart] = useState('');
    const [customEnd, setCustomEnd] = useState('');
    const [useNow, setUseNow] = useState(true);

    // Presets de período
    const presets = [
        { label: '1h', hours: 1 },
        { label: '6h', hours: 6 },
        { label: '12h', hours: 12 },
        { label: '24h', hours: 24 },
        { label: '7d', hours: 24 * 7 },
        { label: '30d', hours: 24 * 30 },
    ];

    // Aplicar preset
    const applyPreset = (preset) => {
        const end = new Date();
        const start = new Date(end.getTime() - preset.hours * 60 * 60 * 1000);
        setActivePreset(preset.label);
        setUseNow(true);
        onRangeChange(start, end);
    };

    // Aplicar range customizado
    const applyCustomRange = () => {
        if (customStart) {
            const start = new Date(customStart);
            const end = useNow ? new Date() : (customEnd ? new Date(customEnd) : new Date());
            setActivePreset('custom');
            onRangeChange(start, end);
            setIsOpen(false);
        }
    };

    // Inicializar com preset padrão
    useEffect(() => {
        if (!startDate && !endDate) {
            applyPreset({ label: '12h', hours: 12 });
        }
    }, []);

    // Formatar data para exibição
    const formatDateDisplay = (date) => {
        if (!date) return '-';
        return date.toLocaleString('pt-BR', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    return (
        <div className={`relative ${className}`}>
            {/* Trigger Button */}
            <Button
                variant="outline"
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 min-w-[200px] justify-between"
            >
                <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-slate-500" />
                    <span className="text-sm">
                        {formatDateDisplay(startDate)} - {useNow ? 'Agora' : formatDateDisplay(endDate)}
                    </span>
                </div>
                <ChevronDown className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </Button>

            {/* Dropdown */}
            {isOpen && (
                <div className="absolute top-full left-0 mt-2 z-50 bg-white dark:bg-slate-900 rounded-lg shadow-lg border p-4 min-w-[320px]">
                    {/* Presets */}
                    {showPresets && (
                        <div className="mb-4">
                            <p className="text-xs font-medium text-slate-500 mb-2">Período Rápido</p>
                            <div className="flex flex-wrap gap-2">
                                {presets.map((preset) => (
                                    <Button
                                        key={preset.label}
                                        variant={activePreset === preset.label ? 'default' : 'outline'}
                                        size="sm"
                                        onClick={() => {
                                            applyPreset(preset);
                                            setIsOpen(false);
                                        }}
                                        className="px-3 py-1 h-8"
                                    >
                                        {preset.label}
                                    </Button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Custom Range */}
                    <div className="border-t pt-4">
                        <p className="text-xs font-medium text-slate-500 mb-2">Período Personalizado</p>
                        <div className="space-y-3">
                            <div>
                                <label className="text-xs text-slate-400">Início</label>
                                <Input
                                    type="datetime-local"
                                    value={customStart}
                                    onChange={(e) => setCustomStart(e.target.value)}
                                    className="h-9 text-sm"
                                />
                            </div>
                            <div>
                                <label className="text-xs text-slate-400">Fim</label>
                                <div className="flex items-center gap-2">
                                    {allowNow ? (
                                        <>
                                            <Button
                                                variant={useNow ? 'default' : 'outline'}
                                                size="sm"
                                                onClick={() => setUseNow(true)}
                                                className="h-9"
                                            >
                                                <Clock className="h-3 w-3 mr-1" />
                                                Agora
                                            </Button>
                                            <Input
                                                type="datetime-local"
                                                value={customEnd}
                                                onChange={(e) => {
                                                    setCustomEnd(e.target.value);
                                                    setUseNow(false);
                                                }}
                                                onFocus={() => setUseNow(false)}
                                                className={`h-9 text-sm flex-1 ${useNow ? 'opacity-50 cursor-pointer' : ''}`}
                                            />
                                        </>
                                    ) : (
                                        <Input
                                            type="datetime-local"
                                            value={customEnd}
                                            onChange={(e) => setCustomEnd(e.target.value)}
                                            className="h-9 text-sm"
                                        />
                                    )}
                                </div>
                            </div>
                            <Button onClick={applyCustomRange} className="w-full h-9">
                                Aplicar
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
