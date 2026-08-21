/**
 * WasteAnalysisDashboard - Análise de Descartes (refugo) - POC ISA-101.
 *
 * Reescrita para o padrão da `04_POC_UI.html`:
 *   - Topbar com filtro de período (Turno/Dia/Semana/Mês/Ano/Custom) + linhas
 *   - KPI strip 4 colunas (Total kg, %, Produção, Maior descarte)
 *   - 3 chart-cards: descarte por linha (bar), top equipamentos (pie),
 *     descarte por estado da máquina (donut)
 *   - Panel de detalhamento por linha - tabela densa com badge de status
 *
 * Mantém: dados reais, auto-refresh de 30s para Turno/Dia, export CSV.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Trash2, TrendingDown, Factory, AlertTriangle, RefreshCw,
    BarChart3, PieChart, Download, ChevronDown, Search
} from 'lucide-react';
import { format, subDays } from 'date-fns';
import Plot from 'react-plotly.js';
import axios from 'axios';

import { DJANGO_API_URL as DJANGO_API } from '@/config/api';
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
        // Sanity check do backend: true quando o descarte excede a produção
        // ou está implausivelmente alto (>50%). UI exibe banner explicativo.
        dados_suspeitos?: boolean;
        motivo_suspeita?: string;
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
    descarte_por_estado_equipamento?: Array<{
        estado_code: number;
        estado_label: string;
        tons: number;
        percentual: number;
    }>;
    descarte_por_estado_linha?: Array<{
        estado_code: number;
        estado_label: string;
        tons: number;
        percentual: number;
    }>;
    descarte_por_produto?: Array<{
        codigo: string;
        produto: string;
        tons: number;
        unidades: number;
        percentual: number;
    }>;
    descarte_por_formato?: Array<{
        codigo: string;
        formato: string;
        tons: number;
        unidades: number;
        percentual: number;
    }>;
    matriz_estado_produto?: Array<{
        estado_code: number;
        estado_label: string;
        produto_codigo: string;
        produto: string;
        tons: number;
        unidades: number;
        percentual: number;
    }>;
    matriz_estado_linha_produto?: Array<{
        estado_code: number;
        estado_label: string;
        produto_codigo: string;
        produto: string;
        tons: number;
        unidades: number;
        percentual: number;
    }>;
    mudancas_estado_linha?: Array<{
        linha: string;
        linha_codigo: string;
        hora: string;
        de: string;
        para: string;
    }>;
    verificacao_estado_linha?: {
        total_mudancas: number;
        criterio: string;
    };
    filtros_disponiveis?: {
        produtos: Array<{ codigo: string; label: string }>;
        formatos: Array<{ codigo: string; label: string }>;
        estados: Array<{ codigo: string; label: string }>;
        estados_equipamento?: Array<{ codigo: string; label: string }>;
        estados_linha?: Array<{ codigo: string; label: string }>;
        turnos?: Array<{ codigo: string; label: string }>;
        // Catálogo de equipamentos das linhas selecionadas (para focar/excluir).
        // slug = "L01.E001"; codigo = "E001" (mostrado na label).
        equipamentos?: Array<{
            codigo: string; slug: string; nome: string;
            linha_codigo: string; linha_nome: string;
        }>;
    };
    diagnostico?: {
        // numero de pontos do Influx que vieram sem 'estado_maquina' na janela
        // (ver PR 8 do backend). Quando > 0, alertar o usuario que a
        // distribuicao por estado pode estar imprecisa.
        pontos_sem_estado?: number;
    };
    insight?: {
        titulo: string;
        mensagem: string;
        estado_critico?: { estado_label: string; percentual: number; tons: number } | null;
        estado_linha_critico?: { estado_label: string; percentual: number; tons: number } | null;
        estado_equipamento_critico?: { estado_label: string; percentual: number; tons: number } | null;
        produto_critico?: { produto: string; percentual: number; tons: number } | null;
        formato_critico?: { formato: string; percentual: number; tons: number } | null;
    };
}

interface LinhaOption { id: number; nome: string; codigo: string; }

// Cores ISA-101 reservadas para gráficos categóricos (sem rosa/laranja-flame
// dramatic do legado; mais sóbrio).
const PIE_COLORS = ['#3f5b7c', '#c9932d', '#2d8659', '#8a6ba8', '#b53a2b', '#657384', '#9ba3ad', '#5c6f8d'];

const WasteAnalysisDashboard: React.FC = () => {
    const navigate = useNavigate();
    const [linhasDisponiveis, setLinhasDisponiveis] = useState<LinhaOption[]>([]);
    const [linhasSelecionadas, setLinhasSelecionadas] = useState<string[]>(['todas']);
    const [periodo, setPeriodo] = useState<string>('TURNO');
    const [dateRange, setDateRange] = useState<{ from: Date; to: Date }>({
        from: subDays(new Date(), 7),
        to: new Date()
    });
    const [data, setData] = useState<WasteData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showLineMenu, setShowLineMenu] = useState(false);
    const [produtoFiltro, setProdutoFiltro] = useState('todos');
    const [formatoFiltro, setFormatoFiltro] = useState('todos');
    const [estadoEquipamentoFiltro, setEstadoEquipamentoFiltro] = useState('todos');
    const [estadoLinhaFiltro, setEstadoLinhaFiltro] = useState('todos');
    const [turnoFiltro, setTurnoFiltro] = useState('todos');
    // Filtros de equipamento (Onda atual — análise focada).
    // `equipamentoFiltro`: slug de UM equipamento — vê só ele. 'todos' = sem filtro.
    // `excluirEquipamentos`: lista de slugs — excluídos da análise.
    // Mutuamente exclusivos na UI: ativar um zera o outro.
    const [equipamentoFiltro, setEquipamentoFiltro] = useState<string>('todos');
    const [excluirEquipamentos, setExcluirEquipamentos] = useState<string[]>([]);

    useEffect(() => {
        axios.get(`${DJANGO_API}/descartes/linhas/`)
            .then(res => {
                const list = res.data || [];
                setLinhasDisponiveis(Array.isArray(list) ? list : []);
            })
            .catch(() => setLinhasDisponiveis([]));
    }, []);

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
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
            if (produtoFiltro !== 'todos') params.append('produto', produtoFiltro);
            if (formatoFiltro !== 'todos') params.append('formato', formatoFiltro);
            if (estadoEquipamentoFiltro !== 'todos') params.append('estado_equipamento', estadoEquipamentoFiltro);
            if (estadoLinhaFiltro !== 'todos') params.append('estado_linha', estadoLinhaFiltro);
            if (turnoFiltro !== 'todos') params.append('turno', turnoFiltro);
            // Equipamento focado tem precedência sobre lista de exclusão
            if (equipamentoFiltro !== 'todos') {
                params.append('equipamento', equipamentoFiltro);
            } else if (excluirEquipamentos.length > 0) {
                params.append('excluir_equipamento', excluirEquipamentos.join(','));
            }
            const res = await axios.get(`${DJANGO_API}/descartes/resumo/?${params.toString()}`);
            setData(res.data || null);
        } catch (err) {
            console.error('Descartes fetch falhou', err);
            setData(null);
            setError('Não foi possível carregar dados reais de descarte.');
        } finally {
            setLoading(false);
        }
    }, [periodo, linhasSelecionadas, dateRange, produtoFiltro, formatoFiltro, estadoEquipamentoFiltro, estadoLinhaFiltro, turnoFiltro, equipamentoFiltro, excluirEquipamentos]);

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

    const estadoEquipamentoData = data?.descarte_por_estado_equipamento || data?.descarte_por_estado || [];
    const estadoLinhaData = data?.descarte_por_estado_linha || [];

    return (
        <div className="isa-root" style={{ padding: '16px 20px', minHeight: '100vh' }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: 12, marginBottom: 14 }}>
                <div>
                    <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: 'var(--isa-text)', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Trash2 size={20} style={{ color: 'var(--isa-bad)' }} />
                        Análise de Descartes
                    </h1>
                    <div style={{ marginTop: 2, fontSize: 'var(--isa-fs-default)', color: 'var(--isa-text-muted)' }}>
                        {data?.periodo_label || 'Selecione um período'}
                    </div>
                </div>

                <div className="isa-toolbar" style={{ marginBottom: 0 }}>
                    {/* Linhas - popover simples nativo */}
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
                    <label htmlFor="produtoFiltro">Produto</label>
                    <select
                        id="produtoFiltro"
                        value={produtoFiltro}
                        onChange={e => setProdutoFiltro(e.target.value)}
                        style={{ minWidth: 170 }}
                    >
                        <option value="todos">Todos</option>
                        {(data?.filtros_disponiveis?.produtos || []).map(p => (
                            <option key={p.codigo} value={p.codigo}>{p.label}</option>
                        ))}
                    </select>
                    <label htmlFor="formatoFiltro">Formato</label>
                    <select
                        id="formatoFiltro"
                        value={formatoFiltro}
                        onChange={e => setFormatoFiltro(e.target.value)}
                        style={{ minWidth: 120 }}
                    >
                        <option value="todos">Todos</option>
                        {(data?.filtros_disponiveis?.formatos || []).map(f => (
                            <option key={f.codigo} value={f.codigo}>{f.label}</option>
                        ))}
                    </select>
                    <label htmlFor="turnoFiltro">Turno</label>
                    <select
                        id="turnoFiltro"
                        value={turnoFiltro}
                        onChange={e => setTurnoFiltro(e.target.value)}
                        style={{ minWidth: 135 }}
                    >
                        <option value="todos">Todos</option>
                        {(data?.filtros_disponiveis?.turnos || []).map(t => (
                            <option key={t.codigo} value={t.codigo}>{t.label}</option>
                        ))}
                    </select>
                    <label htmlFor="estadoLinhaFiltro">Estado linha</label>
                    <select
                        id="estadoLinhaFiltro"
                        value={estadoLinhaFiltro}
                        onChange={e => setEstadoLinhaFiltro(e.target.value)}
                        style={{ minWidth: 145 }}
                    >
                        <option value="todos">Todos</option>
                        {(data?.filtros_disponiveis?.estados_linha || []).map(s => (
                            <option key={s.codigo} value={s.codigo}>{s.label}</option>
                        ))}
                    </select>
                    <label htmlFor="estadoEquipamentoFiltro">Estado equip.</label>
                    <select
                        id="estadoEquipamentoFiltro"
                        value={estadoEquipamentoFiltro}
                        onChange={e => setEstadoEquipamentoFiltro(e.target.value)}
                        style={{ minWidth: 145 }}
                    >
                        <option value="todos">Todos</option>
                        {(data?.filtros_disponiveis?.estados_equipamento || data?.filtros_disponiveis?.estados || []).map(s => (
                            <option key={s.codigo} value={s.codigo}>{s.label}</option>
                        ))}
                    </select>

                    {/* Filtro: focar em UM equipamento (mutuamente exclusivo com excluir) */}
                    <label htmlFor="equipamentoFiltro" title="Focar a análise em um único equipamento">
                        Equipamento
                    </label>
                    <select
                        id="equipamentoFiltro"
                        value={equipamentoFiltro}
                        onChange={e => {
                            setEquipamentoFiltro(e.target.value);
                            // Selecionar um equipamento zera a lista de exclusão
                            if (e.target.value !== 'todos') setExcluirEquipamentos([]);
                        }}
                        style={{ minWidth: 165 }}
                        title="Restringir a análise a UM equipamento (mutuamente exclusivo com a lista de exclusão)"
                    >
                        <option value="todos">Todos</option>
                        {(data?.filtros_disponiveis?.equipamentos || []).map(eq => (
                            <option key={eq.slug} value={eq.slug}>
                                {eq.linha_codigo} · {eq.codigo} ({eq.nome})
                            </option>
                        ))}
                    </select>

                    {/* Filtro: excluir equipamentos da análise (multi-select via <select multiple>) */}
                    <label htmlFor="excluirEquipamentos" title="Excluir um ou mais equipamentos">
                        Excluir
                    </label>
                    <select
                        id="excluirEquipamentos"
                        multiple
                        value={excluirEquipamentos}
                        onChange={e => {
                            const opts = Array.from(e.target.selectedOptions).map(o => o.value);
                            setExcluirEquipamentos(opts);
                            // Selecionar exclusão zera o focar-em-um
                            if (opts.length > 0) setEquipamentoFiltro('todos');
                        }}
                        disabled={equipamentoFiltro !== 'todos'}
                        size={3}
                        style={{
                            minWidth: 165,
                            opacity: equipamentoFiltro !== 'todos' ? 0.5 : 1,
                        }}
                        title="Ctrl+clique para múltiplos. Desativado quando há equipamento focado."
                    >
                        {(data?.filtros_disponiveis?.equipamentos || []).map(eq => (
                            <option key={eq.slug} value={eq.slug}>
                                {eq.linha_codigo} · {eq.codigo}
                            </option>
                        ))}
                    </select>

                    <button type="button" onClick={fetchData} disabled={loading}>
                        <RefreshCw size={12} style={{ marginRight: 4, verticalAlign: -1 }} />
                        {loading ? 'Atualizando...' : 'Atualizar'}
                    </button>
                    <button type="button" className="ghost" onClick={exportCSV} disabled={!data}>
                        <Download size={12} style={{ marginRight: 4, verticalAlign: -1 }} />
                        CSV
                    </button>
                </div>
            </div>

            {error && (
                <Panel title="Falha ao carregar dados reais">
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', color: 'var(--isa-bad)' }}>
                        <AlertTriangle size={16} />
                        <span>{error}</span>
                    </div>
                </Panel>
            )}

            {data && (data.diagnostico?.pontos_sem_estado ?? 0) > 0 && (
                <Panel title="Qualidade do dado de estado">
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', color: 'var(--isa-warn)' }}>
                        <AlertTriangle size={16} />
                        <span>
                            {data.diagnostico!.pontos_sem_estado} ponto(s) sem
                            <code style={{ margin: '0 4px' }}>estado_maquina</code>
                            no Influx. A distribuição por estado é uma estimativa
                            (carry-forward + Indefinido) — verifique o coletor.
                        </span>
                    </div>
                </Panel>
            )}

            {data && !loading && data.consolidado.descarte_tons === 0 && (
                <Panel title="Sem descarte no período">
                    <div style={{ color: 'var(--isa-text-muted)' }}>
                        Nenhum descarte registrado para os filtros selecionados.
                        Tente ampliar o período ou remover filtros.
                    </div>
                </Panel>
            )}

            {data && !loading && data.consolidado.dados_suspeitos && (
                <div
                    role="alert"
                    style={{
                        background: 'var(--isa-warn-bg, #fff8e1)',
                        border: '1px solid var(--isa-warn, #c9932d)',
                        borderLeft: '4px solid var(--isa-warn, #c9932d)',
                        padding: '10px 14px',
                        marginBottom: 12,
                        borderRadius: 4,
                        fontSize: 13,
                        color: 'var(--isa-text)',
                        display: 'flex',
                        gap: 10,
                        alignItems: 'flex-start',
                    }}
                >
                    <span aria-hidden="true" style={{ fontSize: 18 }}>⚠️</span>
                    <div>
                        <strong style={{ display: 'block', marginBottom: 4 }}>
                            Dados possivelmente inconsistentes
                        </strong>
                        <div style={{ color: 'var(--isa-text-muted)' }}>
                            {data.consolidado.motivo_suspeita || (
                                'A relação produção × descarte está fora do esperado para este período.'
                            )}
                        </div>
                        <div style={{ color: 'var(--isa-text-muted)', marginTop: 4, fontSize: 12 }}>
                            Causas comuns: sensor de refugo contabilizou antes da contagem
                            de saída, reset/overflow do contador acumulado, ou granularidade
                            do período pegou descarte de turnos diferentes. Use os filtros
                            para isolar o período de interesse antes de tirar conclusões.
                        </div>
                    </div>
                </div>
            )}

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
                    value={data?.linha_maior_descarte?.linha || '-'}
                    delta={
                        data?.linha_maior_descarte
                            ? { value: `${data.linha_maior_descarte.descarte_percentual.toFixed(2)}% (${data.linha_maior_descarte.descarte_tons.toFixed(3)} t)`, tone: 'down' }
                            : undefined
                    }
                />
            </KpiStrip>

            <Panel title="Leitura Estratégica" style={{ marginTop: 12 }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10, alignItems: 'stretch' }}>
                    <div style={{ border: '1px solid var(--isa-border)', borderRadius: 8, padding: 12, background: 'var(--isa-bg-panel)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--isa-text-muted)', fontSize: 'var(--isa-fs-meta)', marginBottom: 8 }}>
                            <Search size={14} />
                            Concentração do período
                        </div>
                        <div style={{ fontSize: 'var(--isa-fs-body)', lineHeight: 1.45, color: 'var(--isa-text)' }}>
                            {data?.insight?.mensagem || 'Aguardando dados reais para leitura do período.'}
                        </div>
                    </div>
                    <div style={{ border: '1px solid var(--isa-border)', borderRadius: 8, padding: 12 }}>
                        <div style={{ color: 'var(--isa-text-muted)', fontSize: 'var(--isa-fs-meta)' }}>Estado da linha</div>
                        <div style={{ marginTop: 6, fontWeight: 700 }}>{data?.insight?.estado_linha_critico?.estado_label || '-'}</div>
                        <div style={{ marginTop: 4, color: 'var(--isa-text-muted)' }}>{data?.insight?.estado_linha_critico ? `${data.insight.estado_linha_critico.percentual}%` : 'Sem ocorrência'}</div>
                    </div>
                    <div style={{ border: '1px solid var(--isa-border)', borderRadius: 8, padding: 12 }}>
                        <div style={{ color: 'var(--isa-text-muted)', fontSize: 'var(--isa-fs-meta)' }}>Mudanças de linha</div>
                        <div style={{ marginTop: 6, fontWeight: 700 }}>{data?.verificacao_estado_linha?.total_mudancas ?? '-'}</div>
                        <div style={{ marginTop: 4, color: 'var(--isa-text-muted)' }}>alterações no período</div>
                    </div>
                    <div style={{ border: '1px solid var(--isa-border)', borderRadius: 8, padding: 12 }}>
                        <div style={{ color: 'var(--isa-text-muted)', fontSize: 'var(--isa-fs-meta)' }}>Produto sensível</div>
                        <div style={{ marginTop: 6, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{data?.insight?.produto_critico?.produto || '-'}</div>
                        <div style={{ marginTop: 4, color: 'var(--isa-text-muted)' }}>{data?.insight?.produto_critico ? `${data.insight.produto_critico.percentual}%` : 'Sem ocorrência'}</div>
                    </div>
                    <div style={{ border: '1px solid var(--isa-border)', borderRadius: 8, padding: 12 }}>
                        <div style={{ color: 'var(--isa-text-muted)', fontSize: 'var(--isa-fs-meta)' }}>Formato sensível</div>
                        <div style={{ marginTop: 6, fontWeight: 700 }}>{data?.insight?.formato_critico?.formato || '-'}</div>
                        <div style={{ marginTop: 4, color: 'var(--isa-text-muted)' }}>{data?.insight?.formato_critico ? `${data.insight.formato_critico.percentual}%` : 'Sem ocorrência'}</div>
                    </div>
                </div>
            </Panel>

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

                <ChartCard title="Top Geradores de Refugo" desc="Clique numa linha para abrir o detalhamento">
                    {data?.top_equipamentos && data.top_equipamentos.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                            <div style={{ flex: 1, minHeight: 0 }}>
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
                                        margin: { l: 10, r: 10, t: 10, b: 10 },
                                        showlegend: false,
                                        paper_bgcolor: 'transparent',
                                        plot_bgcolor: 'transparent',
                                        font: { family: 'system-ui', color: '#657384', size: 11 },
                                    } as any}
                                    useResizeHandler
                                    style={{ width: '100%', height: '100%' }}
                                    onClick={(ev: any) => {
                                        // Drilldown: clique numa fatia abre a linha correspondente.
                                        const idx = ev?.points?.[0]?.pointNumber;
                                        const eq = idx !== undefined ? data.top_equipamentos[idx] : undefined;
                                        const codigoLinha = eq?.linha?.trim();
                                        if (codigoLinha) navigate(`/linha/${encodeURIComponent(codigoLinha)}/detalhes`);
                                    }}
                                />
                            </div>
                            {/* Tabela densa: equipamento | linha | tons | % do total da fábrica */}
                            <div style={{
                                maxHeight: 140, overflowY: 'auto',
                                borderTop: '1px solid var(--isa-border)', marginTop: 8, paddingTop: 6,
                                fontSize: 'var(--isa-fs-meta)',
                            }}>
                                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                    <thead style={{ color: 'var(--isa-text-muted)', textAlign: 'left' }}>
                                        <tr>
                                            <th style={{ padding: '2px 4px' }}>Equipamento</th>
                                            <th style={{ padding: '2px 4px' }}>Linha</th>
                                            <th style={{ padding: '2px 4px', textAlign: 'right' }}>t</th>
                                            <th style={{ padding: '2px 4px', textAlign: 'right' }}>% fáb.</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {data.top_equipamentos.slice(0, 12).map((eq) => {
                                            const pctFab = data.consolidado.descarte_tons > 0
                                                ? (eq.tons / data.consolidado.descarte_tons * 100).toFixed(1)
                                                : '0.0';
                                            return (
                                                <tr
                                                    key={`${eq.linha}-${eq.equipamento}`}
                                                    style={{ cursor: eq.linha ? 'pointer' : 'default' }}
                                                    onClick={() => {
                                                        const codigoLinha = eq.linha?.trim();
                                                        if (codigoLinha) navigate(`/linha/${encodeURIComponent(codigoLinha)}/detalhes`);
                                                    }}
                                                    title={eq.linha ? `Abrir ${eq.linha}` : 'Sem código de linha'}
                                                >
                                                    <td style={{ padding: '2px 4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 100 }}>{eq.equipamento}</td>
                                                    <td style={{ padding: '2px 4px' }}>{eq.linha}</td>
                                                    <td style={{ padding: '2px 4px', textAlign: 'right' }}>{eq.tons.toFixed(3)}</td>
                                                    <td style={{ padding: '2px 4px', textAlign: 'right', fontWeight: 600 }}>{pctFab}%</td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    ) : (
                        <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--isa-text-muted)' }}>
                            Sem dados disponíveis
                        </div>
                    )}
                </ChartCard>

                <ChartCard title="Descarte por Estado do Equipamento" desc="Estado do equipamento que gerou o descarte">
                    {estadoEquipamentoData.length > 0 ? (
                        <Plot
                            data={[{
                                labels: estadoEquipamentoData.map(d => d.estado_label),
                                values: estadoEquipamentoData.map(d => d.tons),
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

            <ChartRow cols={3}>
                <ChartCard title="Descarte por Produto" desc="Produtos mais associados ao refugo">
                    {data?.descarte_por_produto && data.descarte_por_produto.length > 0 ? (
                        <Plot
                            data={[{
                                x: data.descarte_por_produto.slice().reverse().map(p => p.tons),
                                y: data.descarte_por_produto.slice().reverse().map(p => p.produto),
                                type: 'bar',
                                orientation: 'h',
                                marker: { color: '#3f5b7c' },
                                text: data.descarte_por_produto.slice().reverse().map(p => `${p.percentual}%`),
                                textposition: 'auto',
                            }]}
                            layout={{
                                autosize: true,
                                margin: { l: 120, r: 20, t: 10, b: 40 },
                                xaxis: { title: { text: 'Toneladas' } },
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

                <ChartCard title="Descarte por Formato" desc="Peso/formato no momento do descarte">
                    {data?.descarte_por_formato && data.descarte_por_formato.length > 0 ? (
                        <Plot
                            data={[{
                                x: data.descarte_por_formato.map(f => f.formato),
                                y: data.descarte_por_formato.map(f => f.tons),
                                type: 'bar',
                                marker: { color: '#2d8659' },
                                text: data.descarte_por_formato.map(f => `${f.percentual}%`),
                                textposition: 'outside',
                            }]}
                            layout={{
                                autosize: true,
                                margin: { l: 50, r: 20, t: 10, b: 60 },
                                xaxis: { tickangle: -25 },
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

                <ChartCard title="Descarte por Estado da Linha" desc="Estado consolidado da linha no minuto do descarte">
                    {estadoLinhaData.length > 0 ? (
                        <Plot
                            data={[{
                                labels: estadoLinhaData.map(d => d.estado_label),
                                values: estadoLinhaData.map(d => d.tons),
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

            <Panel title="Combinações Estado x Produto" style={{ marginTop: 12 }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
                    <div style={{ overflowX: 'auto' }}>
                        <div style={{ fontWeight: 600, marginBottom: 6 }}>Pelo estado da linha</div>
                        <table className="isa-tbl">
                            <thead>
                                <tr>
                                    <th>Estado</th>
                                    <th>Produto</th>
                                    <th style={{ textAlign: 'right' }}>t</th>
                                    <th style={{ textAlign: 'right' }}>%</th>
                                </tr>
                            </thead>
                            <tbody>
                                {(data?.matriz_estado_linha_produto || []).slice(0, 6).map((item, idx) => (
                                    <tr key={`linha-${item.estado_code}-${item.produto_codigo}-${idx}`}>
                                        <td>{item.estado_label}</td>
                                        <td style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.produto}</td>
                                        <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{item.tons.toFixed(4)}</td>
                                        <td style={{ textAlign: 'right' }}>{item.percentual.toFixed(1)}%</td>
                                    </tr>
                                ))}
                                {(!data?.matriz_estado_linha_produto || data.matriz_estado_linha_produto.length === 0) && (
                                    <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--isa-text-muted)' }}>Sem dados disponíveis</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                    <div style={{ overflowX: 'auto' }}>
                        <div style={{ fontWeight: 600, marginBottom: 6 }}>Pelo estado do equipamento</div>
                        <table className="isa-tbl">
                            <thead>
                                <tr>
                                    <th>Estado</th>
                                    <th>Produto</th>
                                    <th style={{ textAlign: 'right' }}>t</th>
                                    <th style={{ textAlign: 'right' }}>%</th>
                                </tr>
                            </thead>
                            <tbody>
                                {(data?.matriz_estado_produto || []).slice(0, 6).map((item, idx) => (
                                    <tr key={`equip-${item.estado_code}-${item.produto_codigo}-${idx}`}>
                                        <td>{item.estado_label}</td>
                                        <td style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.produto}</td>
                                        <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{item.tons.toFixed(4)}</td>
                                        <td style={{ textAlign: 'right' }}>{item.percentual.toFixed(1)}%</td>
                                    </tr>
                                ))}
                                {(!data?.matriz_estado_produto || data.matriz_estado_produto.length === 0) && (
                                    <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--isa-text-muted)' }}>Sem dados disponíveis</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </Panel>

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

