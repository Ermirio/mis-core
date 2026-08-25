import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { format } from 'date-fns';
import { CalendarRange, ChevronLeft, ChevronRight, Clock3, RefreshCw } from 'lucide-react';

import { DJANGO_API_URL } from '@/config/api';
import { mapEstado } from '@/utils/equipmentStateUtils';

interface EventoEstado {
    id: number;
    equipamento: number;
    equipamento_nome: string;
    estado: string;
    inicio: string;
    fim: string | null;
}

interface EquipamentoInfo {
    id: number;
    nome: string;
    ordem_na_linha?: number;
    estado_configurado?: boolean;
    fonte_estado?: 'TAG_DEDICADA' | 'SINAIS_BOOLEANOS' | 'NAO_CONFIGURADA';
}

interface MultiEquipmentTimelineProps {
    linhaId: number;
    linhaNome: string;
    equipamentos: EquipamentoInfo[];
}

type WindowPreset = '1' | '4' | '8' | '12' | '24' | 'custom';

const HOUR_MS = 60 * 60 * 1000;
const PRESETS: Array<{ value: WindowPreset; label: string }> = [
    { value: '1', label: '1 hora' },
    { value: '4', label: '4 horas' },
    { value: '8', label: '8 horas' },
    { value: '12', label: '12 horas' },
    { value: '24', label: '24 horas' },
];

const toLocalInputValue = (date: Date) => {
    const offset = date.getTimezoneOffset() * 60 * 1000;
    return new Date(date.getTime() - offset).toISOString().slice(0, 16);
};

const createCurrentWindow = (hours: number) => {
    const end = new Date();
    return { start: new Date(end.getTime() - hours * HOUR_MS), end };
};

export default function MultiEquipmentTimeline({
    linhaId,
    linhaNome,
    equipamentos,
}: MultiEquipmentTimelineProps) {
    const initialWindow = useMemo(() => createCurrentWindow(24), []);
    const [eventos, setEventos] = useState<EventoEstado[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [totalEventos, setTotalEventos] = useState(0);
    const [windowStart, setWindowStart] = useState(initialWindow.start);
    const [windowEnd, setWindowEnd] = useState(initialWindow.end);
    const [preset, setPreset] = useState<WindowPreset>('24');
    const [live, setLive] = useState(true);
    const [customStart, setCustomStart] = useState(toLocalInputValue(initialWindow.start));
    const [customEnd, setCustomEnd] = useState(toLocalInputValue(initialWindow.end));

    const equipamentosOrdenados = useMemo(
        () => [...equipamentos].sort(
            (a, b) => (b.ordem_na_linha || 0) - (a.ordem_na_linha || 0)
        ),
        [equipamentos]
    );

    const windowDurationMs = Math.max(windowEnd.getTime() - windowStart.getTime(), 1);

    const fetchEventos = useCallback(async (signal?: AbortSignal) => {
        setRefreshing(true);
        setError(null);

        try {
            const params = new URLSearchParams({
                linha_id: linhaId.toString(),
                data_inicio: windowStart.toISOString(),
                data_fim: windowEnd.toISOString(),
                ordering: '-inicio',
                page_size: '10000',
            });
            const response = await fetch(`${DJANGO_API_URL}/eventos-estado/?${params}`, { signal });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const data = await response.json();
            const results = Array.isArray(data) ? data : (data.results || []);
            setEventos(results);
            setTotalEventos(Number(data.count ?? results.length));
        } catch (fetchError) {
            if ((fetchError as Error).name !== 'AbortError') {
                console.error('Erro ao buscar eventos:', fetchError);
                setError('Não foi possível carregar os eventos desta janela.');
            }
        } finally {
            if (!signal?.aborted) {
                setLoading(false);
                setRefreshing(false);
            }
        }
    }, [linhaId, windowStart, windowEnd]);

    useEffect(() => {
        const controller = new AbortController();
        fetchEventos(controller.signal);
        return () => controller.abort();
    }, [fetchEventos]);

    useEffect(() => {
        if (!live || preset === 'custom') return;
        const hours = Number(preset);
        const interval = window.setInterval(() => {
            const current = createCurrentWindow(hours);
            setWindowStart(current.start);
            setWindowEnd(current.end);
            setCustomStart(toLocalInputValue(current.start));
            setCustomEnd(toLocalInputValue(current.end));
        }, 10000);
        return () => window.clearInterval(interval);
    }, [live, preset]);

    const setPresetWindow = (value: WindowPreset) => {
        if (value === 'custom') return;
        const hours = Number(value);
        const end = live ? new Date() : windowEnd;
        const start = new Date(end.getTime() - hours * HOUR_MS);
        setPreset(value);
        setWindowStart(start);
        setWindowEnd(end);
        setCustomStart(toLocalInputValue(start));
        setCustomEnd(toLocalInputValue(end));
    };

    const moveWindow = (direction: -1 | 1) => {
        const delta = windowDurationMs * direction;
        let nextEnd = new Date(windowEnd.getTime() + delta);
        let nextStart = new Date(windowStart.getTime() + delta);
        const now = new Date();

        if (nextEnd > now) {
            nextEnd = now;
            nextStart = new Date(now.getTime() - windowDurationMs);
        }

        setLive(false);
        setWindowStart(nextStart);
        setWindowEnd(nextEnd);
        setCustomStart(toLocalInputValue(nextStart));
        setCustomEnd(toLocalInputValue(nextEnd));
    };

    const jumpToNow = () => {
        const duration = preset === 'custom' ? windowDurationMs : Number(preset) * HOUR_MS;
        const end = new Date();
        const start = new Date(end.getTime() - duration);
        setLive(preset !== 'custom');
        setWindowStart(start);
        setWindowEnd(end);
        setCustomStart(toLocalInputValue(start));
        setCustomEnd(toLocalInputValue(end));
    };

    const applyCustomWindow = () => {
        const start = new Date(customStart);
        let end = new Date(customEnd);
        const now = new Date();

        if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start >= end) {
            setError('Selecione um início anterior ao fim da janela.');
            return;
        }
        if (end > now) end = now;
        if (end.getTime() - start.getTime() > 7 * 24 * HOUR_MS) {
            setError('A janela máxima para esta timeline é de 7 dias.');
            return;
        }

        setPreset('custom');
        setLive(false);
        setWindowStart(start);
        setWindowEnd(end);
        setCustomEnd(toLocalInputValue(end));
        setError(null);
    };

    const calcularPosicao = (inicio: string, fim: string | null) => {
        const inicioEvento = Math.max(new Date(inicio).getTime(), windowStart.getTime());
        const fimEvento = Math.min(
            fim ? new Date(fim).getTime() : windowEnd.getTime(),
            windowEnd.getTime()
        );
        const left = ((inicioEvento - windowStart.getTime()) / windowDurationMs) * 100;
        const width = ((fimEvento - inicioEvento) / windowDurationMs) * 100;
        return { left: `${Math.max(0, left)}%`, width: `${Math.max(width, 0.15)}%` };
    };

    const eventosPorEquipamento = equipamentosOrdenados.map(equipamento => ({
        equipamento,
        eventos: eventos.filter(evento => evento.equipamento === equipamento.id),
    }));
    const configurados = equipamentosOrdenados.filter(eq => eq.estado_configurado).length;
    const estadosLegenda = [
        'PRODUZINDO', 'WAIT_PREV', 'BLOCK_NEXT', 'PARADO',
        'SETUP', 'TESTE_PROJ', 'AGUARD_MNT', 'MANUTENCAO', 'FALTA_MAT',
    ].map(chave => mapEstado(chave));
    const axisLabels = [0, 0.25, 0.5, 0.75, 1].map(fraction =>
        new Date(windowStart.getTime() + windowDurationMs * fraction)
    );
    const canMoveForward = windowEnd.getTime() < Date.now() - 1000;

    return (
        <div className="p-4 bg-white dark:bg-neutral-900">
            <div className="flex flex-col gap-3 mb-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                        <h3 className="font-semibold text-sm text-neutral-900 dark:text-neutral-100">
                            Timeline de Estados — {linhaNome}
                        </h3>
                        <div className="mt-1 text-[11px] text-neutral-500">
                            {format(windowStart, 'dd/MM/yyyy HH:mm')} → {format(windowEnd, 'dd/MM/yyyy HH:mm')}
                            {live && <span className="ml-2 text-emerald-600 font-medium">● AO VIVO</span>}
                        </div>
                    </div>
                    <span className="text-xs text-neutral-500 bg-neutral-100 dark:bg-neutral-800 px-2 py-1 rounded">
                        {configurados}/{equipamentosOrdenados.length} com fonte de estado
                    </span>
                </div>

                <div className="flex flex-wrap items-center gap-2 rounded-md border border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800/50 p-2">
                    <button
                        type="button"
                        onClick={() => moveWindow(-1)}
                        className="inline-flex items-center gap-1 rounded border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-800 px-2 py-1.5 text-xs hover:bg-neutral-100 dark:hover:bg-neutral-700"
                        title="Voltar uma janela inteira"
                    >
                        <ChevronLeft size={14} /> Anterior
                    </button>
                    <button
                        type="button"
                        onClick={() => moveWindow(1)}
                        disabled={!canMoveForward}
                        className="inline-flex items-center gap-1 rounded border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-800 px-2 py-1.5 text-xs hover:bg-neutral-100 dark:hover:bg-neutral-700 disabled:opacity-40 disabled:cursor-not-allowed"
                        title="Avançar uma janela inteira"
                    >
                        Próxima <ChevronRight size={14} />
                    </button>
                    <button
                        type="button"
                        onClick={jumpToNow}
                        className="inline-flex items-center gap-1 rounded bg-sky-700 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-sky-800"
                    >
                        <Clock3 size={14} /> Agora
                    </button>
                    <select
                        value={preset}
                        onChange={(event) => setPresetWindow(event.target.value as WindowPreset)}
                        className="rounded border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-800 px-2 py-1.5 text-xs"
                        aria-label="Duração da janela"
                    >
                        {PRESETS.map(option => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                        {preset === 'custom' && <option value="custom">Personalizada</option>}
                    </select>
                    <button
                        type="button"
                        onClick={() => fetchEventos()}
                        disabled={refreshing}
                        className="inline-flex items-center gap-1 rounded border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-800 px-2 py-1.5 text-xs hover:bg-neutral-100 dark:hover:bg-neutral-700 disabled:opacity-50"
                    >
                        <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} /> Atualizar
                    </button>
                </div>

                <div className="flex flex-wrap items-end gap-2 text-xs">
                    <label className="flex flex-col gap-1 text-neutral-500">
                        Início
                        <input
                            type="datetime-local"
                            value={customStart}
                            onChange={(event) => setCustomStart(event.target.value)}
                            className="rounded border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-800 px-2 py-1.5 text-neutral-800 dark:text-neutral-100"
                        />
                    </label>
                    <label className="flex flex-col gap-1 text-neutral-500">
                        Fim
                        <input
                            type="datetime-local"
                            value={customEnd}
                            max={toLocalInputValue(new Date())}
                            onChange={(event) => setCustomEnd(event.target.value)}
                            className="rounded border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-800 px-2 py-1.5 text-neutral-800 dark:text-neutral-100"
                        />
                    </label>
                    <button
                        type="button"
                        onClick={applyCustomWindow}
                        className="inline-flex items-center gap-1 rounded border border-sky-700 px-2.5 py-1.5 font-medium text-sky-700 hover:bg-sky-50 dark:hover:bg-sky-950"
                    >
                        <CalendarRange size={14} /> Aplicar janela
                    </button>
                </div>
            </div>

            {error && (
                <div className="mb-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                    {error}
                </div>
            )}

            {loading ? (
                <div className="p-4 text-sm text-neutral-500 text-center">Carregando timeline...</div>
            ) : (
                <div className="space-y-3">
                    <div className="flex justify-between text-[10px] text-neutral-400 mb-2 pl-20 sm:pl-28 xl:pl-36 font-mono">
                        {axisLabels.map((label, index) => (
                            <span key={label.toISOString()} className={index > 0 && index < 4 ? 'hidden sm:inline' : ''}>
                                {format(label, windowDurationMs <= 12 * HOUR_MS ? 'HH:mm' : 'dd/MM HH:mm')}
                            </span>
                        ))}
                    </div>

                    {eventosPorEquipamento.map(({ equipamento, eventos: eqEventos }) => (
                        <div key={equipamento.id} className="flex items-center gap-3">
                            <div
                                className="w-20 sm:w-28 xl:w-36 flex-shrink-0 text-xs font-medium text-neutral-700 dark:text-neutral-300 truncate"
                                title={equipamento.nome}
                            >
                                {equipamento.nome}
                            </div>
                            <div className="flex-1 relative h-6 bg-neutral-100 dark:bg-neutral-800 rounded overflow-hidden min-w-0">
                                {eqEventos.length === 0 && (
                                    <div className="absolute inset-0 flex items-center px-2 text-[10px] text-neutral-500 dark:text-neutral-400 bg-[repeating-linear-gradient(135deg,transparent,transparent_6px,rgba(148,163,184,0.12)_6px,rgba(148,163,184,0.12)_12px)]">
                                        {equipamento.estado_configurado
                                            ? 'Sem eventos na janela selecionada'
                                            : 'Sem tag de estado configurada'}
                                    </div>
                                )}
                                {eqEventos.map(evento => {
                                    const pos = calcularPosicao(evento.inicio, evento.fim);
                                    const estadoInfo = mapEstado(evento.estado);
                                    return (
                                        <div
                                            key={evento.id}
                                            className="absolute top-0 bottom-0 transition-all hover:brightness-110 cursor-pointer group"
                                            style={{
                                                left: pos.left,
                                                width: pos.width,
                                                backgroundColor: estadoInfo.corHex,
                                                minWidth: '1px',
                                            }}
                                            title={`${estadoInfo.nome}\n${format(new Date(evento.inicio), 'dd/MM HH:mm:ss')} - ${evento.fim ? format(new Date(evento.fim), 'dd/MM HH:mm:ss') : 'Em andamento'}`}
                                        />
                                    );
                                })}
                            </div>
                        </div>
                    ))}

                    <div className="flex flex-wrap items-center justify-between gap-2 mt-4 pt-3 border-t border-neutral-100 dark:border-neutral-800 text-[10px]">
                        <div className="flex flex-wrap gap-x-4 gap-y-2">
                            {estadosLegenda.map(estadoInfo => (
                                <div key={estadoInfo.chave} className="flex items-center gap-1.5">
                                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: estadoInfo.corHex }} />
                                    <span className="text-neutral-600 dark:text-neutral-400">{estadoInfo.nome}</span>
                                </div>
                            ))}
                        </div>
                        <span className="text-neutral-400">
                            {eventos.length} evento(s){totalEventos > eventos.length ? ` de ${totalEventos}` : ''}
                        </span>
                    </div>
                </div>
            )}
        </div>
    );
}
