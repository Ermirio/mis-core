import React, { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { format } from 'date-fns';
import { mapEstado, EstadoMapeado } from '@/utils/equipmentStateUtils';

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
}

interface MultiEquipmentTimelineProps {
    linhaId: number;
    linhaNome: string;
    equipamentos: EquipamentoInfo[];
}

const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || "http://127.0.0.1:8000/api";

export default function MultiEquipmentTimeline({
    linhaId,
    linhaNome,
    equipamentos
}: MultiEquipmentTimelineProps) {
    const [eventos, setEventos] = useState<EventoEstado[]>([]);
    const [loading, setLoading] = useState(true);

    // Ordenar equipamentos por ordem_na_linha DESC (último ao primeiro)
    const equipamentosOrdenados = [...equipamentos].sort(
        (a, b) => (b.ordem_na_linha || 0) - (a.ordem_na_linha || 0)
    );

    useEffect(() => {
        const fetchEventos = async () => {
            try {
                // Buscar últimas 24 horas de eventos
                const agora = new Date();
                const ontem = new Date(agora.getTime() - 24 * 60 * 60 * 1000);

                const params = new URLSearchParams({
                    linha_id: linhaId.toString(),
                    data_inicio: ontem.toISOString(),
                    data_fim: agora.toISOString(),
                    ordering: '-inicio'
                });

                const response = await fetch(`${DJANGO_API_URL}/eventos-estado/?${params}`);
                if (!response.ok) throw new Error('Falha ao buscar eventos');

                const data = await response.json();
                setEventos(data.results || []);
            } catch (error) {
                console.error('Erro ao buscar eventos:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchEventos();
        const interval = setInterval(fetchEventos, 10000); // Atualiza a cada 10s
        return () => clearInterval(interval);
    }, [linhaId]);

    // Calcular posição e largura de cada evento no timeline (últimas 24h)
    const calcularPosicao = (inicio: string, fim: string | null) => {
        const agora = new Date();
        const inicio24h = new Date(agora.getTime() - 24 * 60 * 60 * 1000);

        const inicioEvento = new Date(inicio);
        const fimEvento = fim ? new Date(fim) : agora; // Se não terminou, usa agora

        // Calcular posição relativa às últimas 24h (0-100%)
        const total24h = agora.getTime() - inicio24h.getTime();
        const inicioRelativo = Math.max(0, inicioEvento.getTime() - inicio24h.getTime());
        const fimRelativo = Math.min(total24h, fimEvento.getTime() - inicio24h.getTime());

        const left = (inicioRelativo / total24h) * 100;
        const width = ((fimRelativo - inicioRelativo) / total24h) * 100;

        return { left: `${left}%`, width: `${Math.max(width, 0.5)}%` }; // Mínimo 0.5% para visibilidade
    };

    // Agrupar eventos por equipamento
    const eventosPorEquipamento = equipamentosOrdenados.map(eq => ({
        equipamento: eq,
        eventos: eventos.filter(e => e.equipamento === eq.id)
    }));

    // Gera lista de estados únicos para a legenda (baseado no utilitário)
    // Vamos mostrar todos os estados possíveis definidos no utilitário para consistência
    const estadosLegenda = [
        'PRODUZINDO', 'WAIT_PREV', 'BLOCK_NEXT', 'PARADO',
        'SETUP', 'TESTE_PROJ', 'AGUARD_MNT', 'MANUTENCAO', 'FALTA_MAT'
    ].map(chave => mapEstado(chave));

    if (loading) {
        return (
            <div className="p-4 text-sm text-neutral-500 text-center">
                Carregando timeline...
            </div>
        );
    }

    return (
        <div className="p-4 bg-white dark:bg-neutral-900">
            <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-sm text-neutral-900 dark:text-neutral-100">
                    Timeline de Estados
                    <span className="ml-2 font-normal text-xs text-neutral-500 hidden sm:inline">
                        (último → primeiro)
                    </span>
                </h3>
                <span className="text-xs text-neutral-500 bg-neutral-100 dark:bg-neutral-800 px-2 py-1 rounded">
                    Últimas 24h
                </span>
            </div>

            <div className="space-y-3">
                {/* Eixo de tempo visível apenas em telas maiores para economizar espaço */}
                <div className="flex justify-between text-[10px] text-neutral-400 mb-2 px-0 sm:px-2 font-mono">
                    <span>-24h</span>
                    <span className="hidden sm:inline">-18h</span>
                    <span>-12h</span>
                    <span className="hidden sm:inline">-6h</span>
                    <span>Agora</span>
                </div>

                {/* Linhas de equipamentos */}
                {eventosPorEquipamento.map(({ equipamento, eventos: eqEventos }) => (
                    <div key={equipamento.id} className="flex items-center gap-3">
                        {/* Nome do equipamento - Responsivo */}
                        <div className="w-20 sm:w-28 xl:w-36 flex-shrink-0 text-xs font-medium text-neutral-700 dark:text-neutral-300 truncate" title={equipamento.nome}>
                            {equipamento.nome}
                        </div>

                        {/* Timeline do equipamento */}
                        <div className="flex-1 relative h-6 bg-neutral-100 dark:bg-neutral-800 rounded overflow-hidden min-w-0">
                            {eqEventos.map((evento) => {
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
                                            minWidth: '1px'
                                        }}
                                        title={`${estadoInfo.nome}\n${format(new Date(evento.inicio), 'HH:mm')} - ${evento.fim ? format(new Date(evento.fim), 'HH:mm') : 'Agora'}`}
                                    />
                                );
                            })}
                        </div>
                    </div>
                ))}

                {/* Legenda Compacta */}
                <div className="flex flex-wrap gap-x-4 gap-y-2 mt-4 pt-3 border-t border-neutral-100 dark:border-neutral-800 text-[10px]">
                    {estadosLegenda.map((estadoInfo) => (
                        <div key={estadoInfo.chave} className="flex items-center gap-1.5">
                            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: estadoInfo.corHex }} />
                            <span className="text-neutral-600 dark:text-neutral-400">{estadoInfo.nome}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}