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
            <Card>
                <CardContent className="p-4">
                    <p className="text-sm text-gray-500">Carregando timeline...</p>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-lg">Timeline de Estados - {linhaNome}</CardTitle>
                <p className="text-sm text-gray-500">
                    Últimas 24 horas (último → primeiro equipamento)
                </p>
            </CardHeader>
            <CardContent>
                <div className="space-y-2">
                    {/* Eixo de tempo (topo) - Últimas 24h */}
                    <div className="flex justify-between text-xs text-gray-500 mb-2 px-2">
                        <span>24h atrás</span>
                        <span>18h atrás</span>
                        <span>12h atrás</span>
                        <span>6h atrás</span>
                        <span>Agora</span>
                    </div>

                    {/* Linhas de equipamentos */}
                    {eventosPorEquipamento.map(({ equipamento, eventos: eqEventos }) => (
                        <div key={equipamento.id} className="flex items-center gap-2">
                            {/* Nome do equipamento (fixo à esquerda) */}
                            <div className="w-40 flex-shrink-0 text-sm font-medium truncate">
                                {equipamento.nome}
                            </div>

                            {/* Timeline do equipamento */}
                            <div className="flex-1 relative h-8 bg-gray-100 dark:bg-gray-800 rounded">
                                {eqEventos.map((evento) => {
                                    const pos = calcularPosicao(evento.inicio, evento.fim);
                                    const estadoInfo = mapEstado(evento.estado);

                                    return (
                                        <div
                                            key={evento.id}
                                            className="absolute top-0 bottom-0 rounded transition-all hover:opacity-80 cursor-pointer group"
                                            style={{
                                                left: pos.left,
                                                width: pos.width,
                                                backgroundColor: estadoInfo.corHex,
                                                minWidth: '2px' // Garantir visibilidade de eventos curtos
                                            }}
                                            title={`${estadoInfo.nome}\n${format(new Date(evento.inicio), 'HH:mm')} - ${evento.fim ? format(new Date(evento.fim), 'HH:mm') : 'Agora'}`}
                                        >
                                            {/* Tooltip on hover */}
                                            <div className="hidden group-hover:block absolute bottom-full left-1/2 transform -translate-x-1/2 mb-1 px-2 py-1 bg-black text-white text-xs rounded whitespace-nowrap z-10">
                                                {estadoInfo.nome}
                                                <br />
                                                {format(new Date(evento.inicio), 'HH:mm')} - {evento.fim ? format(new Date(evento.fim), 'HH:mm') : 'Agora'}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    ))}

                    {/* Legenda Padronizada */}
                    <div className="flex flex-wrap gap-3 mt-4 pt-4 border-t text-xs">
                        {estadosLegenda.map((estadoInfo) => (
                            <div key={estadoInfo.chave} className="flex items-center gap-1">
                                <div className="w-3 h-3 rounded" style={{ backgroundColor: estadoInfo.corHex }} />
                                <span className="text-gray-600 dark:text-gray-400">{estadoInfo.nome}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}