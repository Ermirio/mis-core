/**
 * WasteAnalysisDashboard — Análise de Descartes (refugo) — POC ISA-101.
 *
 * Reescrita para o padrão da `04_POC_UI.html`:
 *   - Topbar com filtro de período (Turno/Dia/Semana/Mês/Ano/Custom) + linhas
 *   - KPI strip 4 colunas (Total kg, %, Produção, Maior descarte)
 *   - 3 chart-cards: descarte por linha (bar), top equipamentos (pie),
 *     descarte por estado da máquina (donut)
 *   - Panel de detalhamento por linha — tabela densa com badge de status
 *
 * Mantém: mock fallback, auto-refresh de 30s para Turno/Dia, export CSV.
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
    Trash2, TrendingDown, Factory, AlertTriangle, RefreshCw,
    BarChart3, PieChart, Download, ChevronDown
} from 'lucide-react';
import { format, subDays } from 'date-fns';
import Plot from 'react-plotly.js';
import axios from 'axios';

import { DJANGO_API_URL as DJANGO_API } from '@/config/api';
import { MOCK_DESCARTES_LINHAS, MOCK_DESCARTES_RESUMO } from '@/mocks/demoData';
import { KpiStrip, KpiCard, ChartCard, ChartRow, Panel, Tag } from '@/components/v2';
import { fmt as numFmt } from '@/components/v2/stats';

interface WasteData {
    periodo: string;
    periodo_label: string;
    consolidado: {
        descarte_tons: number;
        descarte_percentual: number;
        producao_tons: number;
        total_unidades: number;
    };
    por_linha: Array<{
        linha: string;
        codigo: string;
        descarte_tons: number;
        descarte_percentual: number;
        producao_tons: number;
        unidades_ruins: number;
    }>;
    top_equipamentos: Array<{
        equipamento: string;
        linha: string;
        unidades: number;
        tons: number;
        percentual: number;
    }>;
    linha_maior_descarte: {
        linha: string;
        descarte_tons: number;
        descarte_percentual: number;
    } | null;
    evolucao_temporal: Array<{ hora: string; descarte: number; producao: number; }>;
    descarte_por_estado?: Array<{
        estado_code: number;
        estado_label: string;
        tons: number;
        percentual: number;
    }>;
}

interface LinhaOption { id: number; nome: string; codigo: string; }

// Cores ISA-101 reservadas para gráficos categóricos (sem rosa/laranja-flame
// dramatic do legado; mais sóbrio).
const PIE_COLORS = ['#3f5b7c', '#c9932d', '#2d8659', '#8a6ba8', '#b53a2b', '#657384', '#9ba3ad', '#5c6f8d'];

const WasteAnalysisDashboard: React.FC = () => {
    const [linhasDisponiveis, setLinhasDisponiveis] = useState<LinhaOption[]>([]);
    const [linhasSelecionadas, setLinhasSelecionadas] = useState<string[]>(['todas']);
    const [periodo, setPeriodo] = useState<string>('TURNO');
    const [dateRange, setDateRange] = useState<{ from: Date; to: Date }>({
        from: subDays(new Date(), 7),
        to: new Date()
    });
    const [data, setData] = useState<WasteData | null>(null);
    const [loading, setLoading] = useState(false);
    const [isDemo, setIsDemo] = useState(false);
    const [showLineMenu, setShowLineMenu] = useState(false);

    useEffect(() => {
        axios.get(`${DJANGO_API}/descartes/linhas/`)
            .then(res => {
                const list = res.data || [];
                setLinhasDisponiveis(list.length > 0 ? list : (MOCK_DESCARTES_LINHAS as any));
            })
            .catch(() => setLinhasDisponiveis(MOCK_DESCARTES_LINHAS as any));
    }, []);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            params.append('periodo', periodo);
            if (linhasSelecionadas.includes('todas') || linhasSelecionadas.length === 0) {
                params.append('linhas', 'todas');
            } else {
                params.append('linhas', linhasSelecionadas.join(','));
            }
            if (periodo === 'CUSTOM') {
                params.append('data_inicio', dateRange.from.toISOString());
                params.append('data_fim', dateRange.to.toISOString());
            }
            const res = await axios.get(`${DJANGO_API}/descartes/resumo/?${params.toString()}`);
            if (res.data?.por_linha?.length > 0) {
                setData(res.data);
                setIsDemo(false);
            } else {
                setData(MOCK_DESCARTES_RESUMO as any);
                setIsDemo(true);
            }
        } catch (err) {
            console.error('Descartes fetch falhou — usando mock', err);
            setData(MOCK_DESCARTES_RESUMO as any);
            setIsDemo(true);
        } finally {
            setLoading(false);
        }
    }, [periodo, linhasSelecionadas, dateRange]);

    // Auto-refresh para granularidades curtas
    useEffect(() => {
        fetchData();
        if (periodo === 'TURNO' || periodo === 'DIA') {
            const interval = setInterval(fetchData, 30000);
            return () => clearInterval(interval);
        }
    }, [fetchData, periodo]);

    const toggleLinha = (codigo: string) => {
        if (codigo === 'todas') {
            setLinhasSelecionadas(['todas']);
            return;
        }
        setLinhasSelecionadas(prev => {
            const without = prev.filter(c => c !== 'todas');
            if (without.includes(codigo)) {
                const next = without.filter(c => c !== codigo);
                return next.length === 0 ? ['todas'] : next;
            }
            return [...without, codigo];
        });
    };

    const exportCSV = () => {
        if (!data) return;
        let csv = 'Linha,Descarte (tons),Descarte (%),Produção (tons),Unidades Ruins\n';
        data.por_linha.forEach(l => {
            csv += `${l.linha},${l.descarte_tons},${l.descarte_percentual},${l.producao_tons},${l.unidades_ruins}\n`;
        });
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `descartes_${periodo}_${format(new Date(), 'yyyy-MM-dd')}.csv`;
        a.click();
    };

    return (
        <div className="isa-root" style={{ padding: '16px 20px', minHeight: '100vh' }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: 12, marginBottom: 14 }}>
                <div>
                    <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: 'var(--isa-text)', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Trash2 size={20} style={{ color: 'var(--isa-bad)' }} />
                        Análise de Descartes
                        {isDemo && <Tag tone="warn">SIMULAÇÃO</Tag>}
                    </h1>
                    <div style={{ marginTop: 2, fontSize: 'var(--isa-fs-default)', color: 'var(--isa-text-muted)' }}>
                        {data?.periodo_label || 'Selecione um período'}
                    </div>
                </div>

                <div className="isa-toolbar" style={{ marginBottom: 0 }}>
                    {/* Linhas — popover simples nativo */}
                    <div style={{ position: 'relative' }}>
                        <button
                            type="button" className="ghost"
                            onClick={() => setShowLineMenu(s => !s)}
                            style={{ minWidth: 160 }}
                        >
                            {linhasSelecionadas.includes('todas') ? 'Todas as Linhas' : `${linhasSelecionadas.length} linha(s)`}
                            <ChevronDown size={12} style={{ marginLeft: 4 }} />
                        </button>
                        {showLineMenu && (
                            <div style={{
                                position: 'absolute', top: 'calc(100% + 4px)', right: 0, zIndex: 20,
                                background: 'var(--isa-bg-panel)', border: '1px solid var(--isa-border)',
                                borderRadius: 'var(--isa-radius)', padding: 6, minWidth: 220,
                                maxHeight: 240, overflowY: 'auto', boxShadow: 'var(--isa-shadow-2)',
                            }}>
                                <label style={{ display: 'flex', alignItems: 'center', gap: 6, padding: 6, cursor: 'pointer' }}>
                                    <input type="checkbox" checked={linhasSelecionadas.includes('todas')} onChange={() => toggleLinha('todas')} />
                                    <span style={{ fontWeight: 500 }}>Todas as Linhas</span>
                                </label>
                                <div style={{ borderTop: '1px solid var(--isa-border)', margin: '4px 0' }} />
                                {linhasDisponiveis.map(l => (
                                    <label key={l.codigo} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: 6, cursor: 'pointer' }}>
                                        <input type="checkbox" checked={linhasSelecionadas.includes(l.codigo)} onChange={() => toggleLinha(l.codigo)} />
                                        <span style={{ fontSize: 'var(--isa-fs-body)' }}>{l.nome}</span>
                                    </label>
                                ))}
                            </div>
                        )}
                    </div>

                    <label htmlFor="periodo">Período</label>
                    <select id="periodo" value={periodo} onChange={e => setPeriodo(e.target.value)}>
                        <option value="TURNO">Turno atual</option>
                        <option value="DIA">Hoje</option>
                        <option value="SEMANA">Esta semana</option>
                        <option value="MES">Este mês</option>
                        <option value="ANO">Este ano</option>
                        <option value="CUSTOM">Personalizado</option>
                    </select>
                    {periodo === 'CUSTOM' && (
                        <>
                            <input
                                type="date"
                                value={format(dateRange.from, 'yyyy-MM-dd')}
                                onChange={e => setDateRange({ ...dateRange, from: new Date(e.target.value) })}
                            />
                            <input
                                type="date"
                                value={format(dateRange.to, 'yyyy-MM-dd')}
                                onChange={e => setDateRange({ ...dateRange, to: new Date(e.target.value) })}
                            />
                        </>
                    )}
                    <button type="button" onClick={fetchData} disabled={loading}>
                        <RefreshCw size={12} style={{ marginRight: 4, verticalAlign: -1 }} />
                        {loading ? 'Atualizando…' : 'Atualizar'}
                    </button>
                    <button type="button" className="ghost" onClick={exportCSV} disabled={!data}>
                        <Download size={12} style={{ marginRight: 4, verticalAlign: -1 }} />
                        CSV
                    </button>
                </div>
            </div>

            {/* KPI strip */}
            <KpiStrip cols={4}>
                <KpiCard
                    label="Descarte Total"
                    value={numFmt.num(data?.consolidado.descarte_tons, 3)}
                    unit="t"
                    delta={
                        data
                            ? { value: `${data.consolidado.total_unidades.toLocaleString('pt-BR')} unidades`, tone: 'neutral' }
                            : undefined
                    }
                />
                <KpiCard
                    label="Percentual"
                    value={numFmt.num(data?.consolidado.descarte_percentual, 2)}
                    unit="%"
                    delta={
                        data
                            ? { value: 'sobre produção total', tone: data.consolidado.descarte_percentual > 1 ? 'down' : 'up' }
                            : undefined
                    }
                />
                <KpiCard
                    label="Produção Total"
                    value={numFmt.num(data?.consolidado.producao_tons, 2)}
                    unit="t"
                    delta={
                        data
                            ? { value: `${data.por_linha?.length || 0} linha(s)`, tone: 'neutral' }
                            : undefined
                    }
                />
                <KpiCard
                    label="Maior Descarte"
                    value={data?.linha_maior_descarte?.linha || '—'}
                    delta={
                        data?.linha_maior_descarte
                            ? { value: `${data.linha_maior_descarte.descarte_percentual.toFixed(2)}% (${data.linha_maior_descarte.descarte_tons.toFixed(3)} t)`, tone: 'down' }
                            : undefined
                    }
                />
            </KpiStrip>

            {/* Chart row 3 col */}
            <ChartRow cols={3}>
                <ChartCard title="Descarte por Linha" desc="Comparação entre linhas selecionadas">
                    {data?.por_linha && data.por_linha.length > 0 ? (
                        <Plot
                            data={[{
                                x: data.por_linha.map(l => l.linha),
                                y: data.por_linha.map(l => l.descarte_tons),
                                type: 'bar',
                                name: 'Descarte (t)',
                                marker: { color: '#b53a2b' },
                                text: data.por_linha.map(l => `${l.descarte_percentual.toFixed(2)}%`),
                                textposition: 'outside',
                            }]}
                            layout={{
                                autosize: true,
                                height: undefined,
                                margin: { l: 50, r: 20, t: 10, b: 70 },
                                xaxis: { tickangle: -40 },
                                yaxis: { title: { text: 'Toneladas' } },
                                showlegend: false,
                                paper_bgcolor: 'transparent',
                                plot_bgcolor: 'transparent',
                                font: { family: 'system-ui', color: '#657384', size: 11 },
                            } as any}
                            useResizeHandler
                            style={{ width: '100%', height: '100%' }}
                        />
                    ) : (
                        <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--isa-text-muted)' }}>
                            Sem dados disponíveis
                        </div>
                    )}
                </ChartCard>

                <ChartCard title="Top Geradores de Refugo" desc="Equipamentos com maior descarte">
                    {data?.top_equipamentos && data.top_equipamentos.length > 0 ? (
                        <Plot
                            data={[{
                                labels: data.top_equipamentos.map(e => `${e.equipamento} (${e.linha})`),
                                values: data.top_equipamentos.map(e => e.tons),
                                type: 'pie',
                                hole: 0.4,
                                textinfo: 'percent',
                                textposition: 'outside',
                                marker: { colors: PIE_COLORS },
                            }]}
                            layout={{
                                autosize: true,
                                margin: { l: 10, r: 10, t: 10, b: 30 },
                                showlegend: true,
                                legend: { orientation: 'h', y: -0.15, font: { size: 10 } },
                                paper_bgcolor: 'transparent',
                                plot_bgcolor: 'transparent',
                                font: { family: 'system-ui', color: '#657384', size: 11 },
                            } as any}
                            useResizeHandler
                            style={{ width: '100%', height: '100%' }}
                        />
                    ) : (
                        <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--isa-text-muted)' }}>
                            Sem dados disponíveis
                        </div>
                    )}
                </ChartCard>

                <ChartCard title="Descarte por Estado" desc="Associação com estado da máquina">
                    {data?.descarte_por_estado && data.descarte_por_estado.length > 0 ? (
                        <Plot
                            data={[{
                                labels: data.descarte_por_estado.map(d => d.estado_label),
                                values: data.descarte_por_estado.map(d => d.tons),
                                type: 'pie',
                                hole: 0.6,
                                textinfo: 'percent',
                                textposition: 'outside',
                                marker: { colors: PIE_COLORS },
                            }]}
                            layout={{
                                autosize: true,
                                margin: { l: 10, r: 10, t: 10, b: 30 },
                                showlegend: true,
                                legend: { orientation: 'h', y: -0.15, font: { size: 10 } },
                                paper_bgcolor: 'transparent',
                                plot_bgcolor: 'transparent',
                                font: { family: 'system-ui', color: '#657384', size: 11 },
                            } as any}
                            useResizeHandler
                            style={{ width: '100%', height: '100%' }}
                        />
                    ) : (
                        <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--isa-text-muted)' }}>
                            Sem dados disponíveis
                        </div>
                    )}
                </ChartCard>
            </ChartRow>

            {/* Tabela detalhada */}
            <Panel title="Detalhamento por Linha" style={{ marginTop: 12 }}>
                <div style={{ overflowX: 'auto' }}>
                    <table className="isa-tbl">
                        <thead>
                            <tr>
                                <th>Linha</th>
                                <th style={{ textAlign: 'right' }}>Produção (t)</th>
                                <th style={{ textAlign: 'right' }}>Descarte (t)</th>
                                <th style={{ textAlign: 'right' }}>Descarte (%)</th>
                                <th style={{ textAlign: 'right' }}>Unidades</th>
                                <th style={{ textAlign: 'center' }}>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data?.por_linha
                                ?.slice()
                                .sort((a, b) => b.descarte_percentual - a.descarte_percentual)
                                .map(linha => {
                                    const tone: 'ok' | 'warn' | 'bad' =
                                        linha.descarte_percentual > 1 ? 'bad'
                                        : linha.descarte_percentual > 0.5 ? 'warn'
                                        : 'ok';
                                    return (
                                        <tr key={linha.codigo}>
                                            <td style={{ fontWeight: 500 }}>{linha.linha}</td>
                                            <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{linha.producao_tons.toFixed(2)}</td>
                                            <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--isa-bad)', fontWeight: 600 }}>{linha.descarte_tons.toFixed(4)}</td>
                                            <td style={{ textAlign: 'right' }}>
                                                <Tag tone={tone}>{linha.descarte_percentual.toFixed(2)}%</Tag>
                                            </td>
                                            <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{linha.unidades_ruins.toLocaleString('pt-BR')}</td>
                                            <td style={{ textAlign: 'center' }}>
                                                {tone === 'bad' && <span style={{ color: 'var(--isa-bad)', fontWeight: 500 }}>Alto</span>}
                                                {tone === 'warn' && <span style={{ color: 'var(--isa-warn)', fontWeight: 500 }}>Atenção</span>}
                                                {tone === 'ok'   && <span style={{ color: 'var(--isa-ok)',   fontWeight: 500 }}>OK</span>}
                                            </td>
                                        </tr>
                                    );
                                })}
                            {(!data?.por_linha || data.por_linha.length === 0) && (
                                <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--isa-text-muted)', padding: 20 }}>Sem dados de descarte no período.</td></tr>
                            )}
                        </tbody>
                        {data?.por_linha && data.por_linha.length > 0 && (
                            <tfoot>
                                <tr style={{ background: 'var(--isa-bg-muted)' }}>
                                    <td style={{ fontWeight: 700 }}>TOTAL</td>
                                    <td style={{ textAlign: 'right', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{data.consolidado.producao_tons.toFixed(2)}</td>
                                    <td style={{ textAlign: 'right', fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: 'var(--isa-bad)' }}>{data.consolidado.descarte_tons.toFixed(4)}</td>
                                    <td style={{ textAlign: 'right', fontWeight: 600 }}>{data.consolidado.descarte_percentual.toFixed(2)}%</td>
                                    <td style={{ textAlign: 'right', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{data.consolidado.total_unidades.toLocaleString('pt-BR')}</td>
                                    <td></td>
                                </tr>
                            </tfoot>
                        )}
                    </table>
                </div>
            </Panel>
        </div>
    );
};

export default WasteAnalysisDashboard;
