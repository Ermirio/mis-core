import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    LayoutDashboard,
    RefreshCw,
    TrendingUp,
    TrendingDown,
    AlertTriangle,
    Activity,
    Factory
} from 'lucide-react';
import { KpiStrip, KpiCard, Panel, SectionHead, Tag } from '@/components/v2';
import { fmt as numFmt } from '@/components/v2/stats';
import FactorySynoptic from '@/components/factory/FactorySynoptic';

// Interface matching the API response
interface LineKPI {
    linha: string;
    oee_real: number;
    oee_planejado: number | null;
    producao_real_t: number;
    producao_planejada_t: number;
    tph_real: number;
    status: string;
}

interface LayoutItem {
    linha: string;
    area: string;
    posicao_x: number;
    posicao_y: number;
    w?: number;
    h?: number;
    critico: boolean;
}

interface FactoryData {
    oee_fabril_real: number;
    oee_fabril_planejado: number;
    producao_real_t: number;
    producao_planejada_t: number;
    vazao_total_tph: number;
    vazao_necessaria_tph: number; // New field
    linhas: LineKPI[];
    layout_fabrica: LayoutItem[];
}

// Flask-out Onda 3: /fabrica/kpis e /fabrica/mapa migrados para Django.
import { DJANGO_API_URL } from '@/config/api';
import { MOCK_FABRICA_KPIS, MOCK_FABRICA_MAPA } from '@/mocks/demoData';

const FactoryManagementPanel: React.FC = () => {
    const navigate = useNavigate();
    const [data, setData] = useState<FactoryData | null>(null);
    const [loading, setLoading] = useState(true);
    const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
    const [period, setPeriod] = useState<string>('turno');

    const [mapData, setMapData] = useState<any[]>([]);

    const fetchData = async () => {
        setLoading(true);
        try {
            let kpisOk = false;
            let mapOk  = false;

            try {
                const responseKpis = await fetch(`${DJANGO_API_URL}/fabrica/kpis?period=${period}`);
                if (responseKpis.ok) { setData(await responseKpis.json()); kpisOk = true; }
            } catch { /* fall through */ }
            // Sem fallback para mock — modo produção mostra vazio se backend sem dados.
            if (!kpisOk) setData(null);

            try {
                const responseMap = await fetch(`${DJANGO_API_URL}/fabrica/mapa?t=${new Date().getTime()}`);
                if (responseMap.ok) { setMapData(await responseMap.json()); mapOk = true; }
            } catch { /* fall through */ }
            if (!mapOk) setMapData(null);

            setLastUpdate(new Date());
        } catch (error) {
            console.error("Error fetching factory data:", error);
            setData(null);
            setMapData(null);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 10000); // 10s refresh
        return () => clearInterval(interval);
    }, [period]);

    if (loading && !data) {
        return <div className="p-10 text-center">Carregando Painel Fabril...</div>;
    }

    if (!data) {
        return <div className="p-10 text-center text-red-500">Erro ao carregar dados.</div>;
    }

    // Sort lines for ranking (by OEE)
    const sortedLines = [...data.linhas].sort((a, b) => b.oee_real - a.oee_real);

    const ativas = data.linhas.filter(l => ['Rodando', 'Produzindo', 'Online'].includes(l.status)).length;

    return (
        <div className="isa-root" style={{ padding: '16px 20px', minHeight: '100vh' }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: 12, marginBottom: 14 }}>
                <div>
                    <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: 'var(--isa-text)', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Factory size={20} style={{ color: 'var(--isa-accent)' }} />
                        Fábrica · Visão Geral
                    </h1>
                    <div style={{ marginTop: 2, fontSize: 'var(--isa-fs-default)', color: 'var(--isa-text-muted)' }}>
                        Monitoramento consolidado em tempo real · atualizado {lastUpdate.toLocaleTimeString('pt-BR')}
                    </div>
                </div>

                <div className="isa-toolbar" style={{ marginBottom: 0 }}>
                    <div className="isa-chips">
                        {(['turno', 'dia', 'semana', 'mes'] as const).map(p => (
                            <button
                                key={p}
                                type="button"
                                className={`isa-chip ${period === p ? 'isa-chip--active' : ''}`}
                                onClick={() => setPeriod(p)}
                            >
                                {p === 'mes' ? 'Mês' : p.charAt(0).toUpperCase() + p.slice(1)}
                            </button>
                        ))}
                    </div>
                    <button type="button" onClick={fetchData} disabled={loading}>
                        <RefreshCw size={12} style={{ marginRight: 4, verticalAlign: -1 }} />
                        {loading ? 'Atualizando…' : 'Atualizar'}
                    </button>
                </div>
            </div>

            {/* Top KPIs */}
            <KpiStrip cols={4}>
                <KpiCard
                    label="OEE Fabril"
                    value={numFmt.num(data.oee_fabril_real, 1)}
                    unit="%"
                    delta={
                        data.oee_fabril_planejado
                            ? {
                                value: `Meta ${data.oee_fabril_planejado}%`,
                                tone: data.oee_fabril_real >= data.oee_fabril_planejado ? 'up' : 'down'
                            }
                            : undefined
                    }
                />
                <KpiCard
                    label="Vazão Total"
                    value={numFmt.num(data.vazao_total_tph, 1)}
                    unit="t/h"
                    delta={
                        data.vazao_necessaria_tph
                            ? { value: `Necessária ${data.vazao_necessaria_tph} t/h`, tone: 'neutral' }
                            : undefined
                    }
                />
                <KpiCard
                    label="Produção Real"
                    value={numFmt.num(data.producao_real_t, 1)}
                    unit="t"
                    delta={{ value: `Plano ${data.producao_planejada_t} t`, tone: 'neutral' }}
                />
                <KpiCard
                    label="Linhas Ativas"
                    value={`${ativas} / ${data.linhas.length}`}
                    delta={
                        ativas < data.linhas.length
                            ? { value: `${data.linhas.length - ativas} fora`, tone: 'down' }
                            : { value: 'todas operando', tone: 'up' }
                    }
                />
            </KpiStrip>

            {/* Ranking */}
            <Panel title="Ranking de Performance">
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 8 }}>
                    {sortedLines.map((line, idx) => {
                        const tone: 'ok' | 'warn' | 'bad' =
                            line.oee_real >= 75 ? 'ok' :
                            line.oee_real >= 55 ? 'warn' : 'bad';
                        return (
                            <div
                                key={line.linha}
                                role="button"
                                tabIndex={0}
                                onClick={() => navigate(`/linha/${line.linha}/detalhes`)}
                                style={{
                                    display: 'flex', alignItems: 'center', gap: 10,
                                    padding: '8px 10px',
                                    background: 'var(--isa-bg)',
                                    border: '1px solid var(--isa-border)',
                                    borderRadius: 'var(--isa-radius)',
                                    cursor: 'pointer',
                                }}
                            >
                                <div style={{
                                    width: 22, height: 22, borderRadius: '50%',
                                    display: 'grid', placeItems: 'center',
                                    background: idx === 0 ? '#f4e8cf' : 'var(--isa-bg-muted)',
                                    color: idx === 0 ? 'var(--isa-warn)' : 'var(--isa-text-muted)',
                                    fontSize: 11, fontWeight: 700,
                                }}>
                                    {idx + 1}
                                </div>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ fontWeight: 600, fontSize: 'var(--isa-fs-default)', color: 'var(--isa-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{line.linha}</div>
                                    <div style={{ fontSize: 'var(--isa-fs-meta)', color: 'var(--isa-text-muted)' }}>{line.status}</div>
                                </div>
                                <Tag tone={tone}>{numFmt.num(line.oee_real, 0)}%</Tag>
                            </div>
                        );
                    })}
                </div>
            </Panel>

            {/* Sinotico hierarquico (PR 12): fabrica -> localizacao -> linha -> equipamentos */}
            <div style={{ marginTop: 12 }}>
                <SectionHead
                    title="Sinótico hierárquico"
                    desc="Fábrica → Localização → Linha → Equipamentos (clique na linha para detalhes)"
                />
                <FactorySynoptic />
            </div>

            {/* Mapa do chão de fábrica */}
            <div style={{ marginTop: 12 }}>
                <SectionHead title="Mapa do Chão de Fábrica" desc="Layout das linhas e estado em tempo real" />
                <div style={{
                    background: 'var(--isa-bg-panel)',
                    border: '1px solid var(--isa-border)',
                    borderRadius: 'var(--isa-radius)',
                    padding: 14,
                }}>
                    <div className="relative w-full h-[600px] rounded border" style={{ background: 'var(--isa-bg)', borderColor: 'var(--isa-border)', position: 'relative', overflow: 'hidden' }}>
                            {/* Background */}
                            <div className="absolute inset-0 opacity-10"
                                style={{ backgroundImage: 'radial-gradient(#4f46e5 1px, transparent 1px)', backgroundSize: '20px 20px' }}>
                            </div>

                            {/* Layout Rendering */}
                            {mapData.map((item) => {
                                // item structure: { linha, status, ole, layout: { ... } }
                                const layout = item.layout;
                                const isRunning = item.status === 'Produzindo' || item.status === 'Rodando' || item.status === 'Online';
                                const isGhost = !item.status || item.status === 'Sem Dados';
                                // Fix: Critical lines shouldn't be red unless there's an issue
                                const isAlert = (item.ole < 60 && !isGhost) || item.status === 'Falha' || item.status === 'Parado/Falha';

                                // Positioning logic (14x5 grid approx based on previous code)
                                const unitW = 100 / 14;
                                const unitH = 100 / 5;

                                const left = `${layout.pos_x * unitW}%`;
                                const top = `${layout.pos_y * unitH}%`;
                                const width = `${(layout.w || 1) * unitW - 1}%`; // -1% gap
                                const height = `${(layout.h || 1) * unitH - 1}%`; // -1% gap

                                return (
                                    <div
                                        key={item.linha}
                                        className={`
                                            absolute p-2 rounded-lg shadow-sm border-2 transition-all hover:scale-105 cursor-pointer flex flex-col justify-between
                                            ${isGhost ? 'border-gray-200 bg-gray-50 opacity-60' :
                                                isAlert ? 'border-red-400 bg-red-50' :
                                                    isRunning ? 'border-green-400 bg-white' : 'border-gray-300 bg-gray-50'}
                                        `}
                                        style={{ left, top, width, height }}
                                        onClick={() => !isGhost && navigate(`/linha/${item.linha}/detalhes`)}
                                    >
                                        <div className="flex justify-between items-start">
                                            <span className={`font-bold text-xs truncate ${isGhost ? 'text-gray-400' : 'text-gray-800'}`}>{item.linha}</span>
                                            {isAlert && <AlertTriangle className="w-3 h-3 text-red-500 animate-pulse" />}
                                        </div>

                                        {!isGhost ? (
                                            <div className="space-y-1 mt-1">
                                                <div className="flex justify-between text-[10px]">
                                                    <span>OLE</span>
                                                    <span className="font-bold">{item.ole}%</span>
                                                </div>
                                                <div className="w-full bg-gray-200 rounded-full h-1">
                                                    <div
                                                        className={`h-1 rounded-full ${item.ole < 60 ? 'bg-red-500' : 'bg-green-500'}`}
                                                        style={{ width: `${Math.min(item.ole, 100)}%` }}
                                                    />
                                                </div>
                                                <div className="text-[9px] text-gray-500 truncate">
                                                    {item.status}
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="flex items-center justify-center h-full">
                                                <span className="text-[10px] text-gray-400">Sem dados</span>
                                            </div>
                                        )}
                                    </div>
                                );
                            })}

                            {/* Legend */}
                            <div style={{
                                position: 'absolute', bottom: 12, right: 12,
                                background: 'var(--isa-bg-panel)',
                                border: '1px solid var(--isa-border)',
                                borderRadius: 'var(--isa-radius)',
                                padding: 8, fontSize: 'var(--isa-fs-meta)',
                                display: 'flex', flexDirection: 'column', gap: 4,
                                boxShadow: 'var(--isa-shadow-1)',
                            }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span className="isa-dot isa-dot--ok" />Operando</div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span className="isa-dot isa-dot--bad" />Crítico / Parado</div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span className="isa-dot isa-dot--off" />Sem Dados</div>
                            </div>
                        </div>
                </div>
            </div>
        </div>
    );
};

export default FactoryManagementPanel;
