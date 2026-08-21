import React, { useMemo } from 'react';
import { format, parseISO, differenceInMinutes } from 'date-fns';
import { mapEstado } from '@/utils/equipmentStateUtils';

interface EventoEstado {
    id: number;
    estado: string;
    estado_display: string;
    inicio: string;
    fim?: string | null;
    duracao_segundos?: number;
}

interface StateTimelineChartProps {
    eventos: EventoEstado[];
    dateRange?: { from?: Date; to?: Date };
}

const StateTimelineChart: React.FC<StateTimelineChartProps> = ({ eventos, dateRange }) => {

    // Gera lista de estados para legenda
    const estadosLegenda = [
        'PRODUZINDO', 'WAIT_PREV', 'BLOCK_NEXT', 'PARADO',
        'SETUP', 'TESTE_PROJ', 'AGUARD_MNT', 'MANUTENCAO', 'FALTA_MAT'
    ].map(chave => mapEstado(chave));

    const timelineData = useMemo(() => {
        if (!eventos || eventos.length === 0 || !dateRange?.from || !dateRange?.to) {
            return { segments: [], totalMinutes: 0 };
        }

        const startTime = dateRange.from.getTime();
        const endTime = dateRange.to.getTime();
        const totalMinutes = differenceInMinutes(endTime, startTime);

        const segments = eventos.map((evento) => {
            const eventoStart = Math.max(parseISO(evento.inicio).getTime(), startTime);
            const eventoEnd = evento.fim
                ? Math.min(parseISO(evento.fim).getTime(), endTime)
                : endTime;

            const offsetMinutes = differenceInMinutes(eventoStart, startTime);
            const durationMinutes = differenceInMinutes(eventoEnd, eventoStart);

            const leftPercent = (offsetMinutes / totalMinutes) * 100;
            const widthPercent = (durationMinutes / totalMinutes) * 100;

            const estadoInfo = mapEstado(evento.estado);

            return {
                id: evento.id,
                estado: evento.estado,
                estado_display: estadoInfo.nome, // Usa nome padronizado
                inicio: evento.inicio,
                fim: evento.fim,
                leftPercent,
                widthPercent,
                color: estadoInfo.corHex, // Usa cor padronizada
                durationMinutes
            };
        });

        return { segments, totalMinutes };
    }, [eventos, dateRange]);

    const formatDuration = (minutes: number): string => {
        if (minutes < 60) return `${Math.round(minutes)}m`;
        const hours = Math.floor(minutes / 60);
        const mins = Math.round(minutes % 60);
        return `${hours}h ${mins}m`;
    };

    if (!dateRange?.from || !dateRange?.to) {
        return (
            <div className="flex items-center justify-center h-32 text-gray-500">
                Selecione um intervalo de datas para visualizar a timeline
            </div>
        );
    }

    if (timelineData.segments.length === 0) {
        return (
            <div className="flex items-center justify-center h-32 text-gray-500">
                Nenhum evento encontrado no período selecionado
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex justify-between text-xs text-gray-500 px-2">
                <span>{format(dateRange.from, 'dd/MM HH:mm')}</span>
                <span>{format(dateRange.to, 'dd/MM HH:mm')}</span>
            </div>

            <div className="relative h-16 bg-gray-100 rounded-lg overflow-hidden">
                {timelineData.segments.map((segment) => (
                    <div
                        key={segment.id}
                        className="absolute top-0 h-full flex items-center justify-center text-white text-xs font-medium transition-all hover:opacity-80 cursor-pointer group"
                        style={{
                            left: `${segment.leftPercent}%`,
                            width: `${segment.widthPercent}%`,
                            backgroundColor: segment.color
                        }}
                        title={`${segment.estado_display}\n${format(parseISO(segment.inicio), 'dd/MM HH:mm')}${segment.fim ? ` - ${format(parseISO(segment.fim), 'HH:mm')}` : ' - Ativo'}\nDuração: ${formatDuration(segment.durationMinutes)}`}
                    >
                        {segment.widthPercent > 5 && (
                            <span className="truncate px-1">{segment.estado_display}</span>
                        )}

                        <div className="absolute bottom-full mb-2 hidden group-hover:block bg-gray-900 text-white text-xs rounded py-1 px-2 whitespace-nowrap z-10">
                            <div className="font-semibold">{segment.estado_display}</div>
                            <div>{format(parseISO(segment.inicio), 'dd/MM HH:mm')}</div>
                            {segment.fim && <div>até {format(parseISO(segment.fim), 'HH:mm')}</div>}
                            <div>Duração: {formatDuration(segment.durationMinutes)}</div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Legenda Padronizada */}
            <div className="flex flex-wrap gap-3 text-xs">
                {estadosLegenda.map((estadoInfo) => (
                    <div key={estadoInfo.chave} className="flex items-center gap-1.5">
                        <div className="w-3 h-3 rounded" style={{ backgroundColor: estadoInfo.corHex }}></div>
                        <span>{estadoInfo.nome}</span>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default StateTimelineChart;