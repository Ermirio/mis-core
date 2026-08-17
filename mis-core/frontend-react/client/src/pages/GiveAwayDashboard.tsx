/**
 * GiveAwayDashboard — gestão de excesso de peso (g/un) — POC ISA-101.
 *
 * Reescrita para o padrão da `04_POC_UI.html`:
 *   - Topbar com filtro de período (Turno/Dia/Mês) e refresh
 *   - KPI strip 3 colunas (kg total, % global, produção teórica de referência)
 *   - Painel de detalhamento por linha — tabela densa, ranking por excesso
 *
 * Dados continuam vindo de Django `/giveaway/resumo/?periodo=...` e caem em
 * mock determinístico se a API estiver offline (modo "simulação").
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Scale, RefreshCw, AlertTriangle } from "lucide-react";
import axios from 'axios';

import { DJANGO_API_URL as DJANGO_API } from '@/config/api';
import { MOCK_GIVEAWAY_RESUMO } from '@/mocks/demoData';
import { KpiStrip, KpiCard, Panel, Tag } from '@/components/v2';
import { fmt as numFmt } from '@/components/v2/stats';

interface GiveAwayData {
    consolidado: {
        giveaway_kg: number;
        giveaway_percent: number;
        producao_ref_kg: number;
    };
    por_linha: Array<{
        linha: string;
        codigo: string;
        equipamento_leitura: string;
        giveaway_kg: number;
        giveaway_percent: number;
        producao_unidades: number;
        producao_nominal_kg: number;
    }>;
}

const PERIODO_LABEL: Record<string, string> = {
    TURNO: 'Turno atual',
    DIA: 'Hoje',
    MES: 'Este mês',
};

const GiveAwayDashboard: React.FC = () => {
    const [periodo, setPeriodo] = useState<string>('TURNO');
    const [data, setData] = useState<GiveAwayData | null>(null);
    const [loading, setLoading] = useState(false);
    const [isDemo, setIsDemo] = useState(false);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const res = await axios.get(`${DJANGO_API}/giveaway/resumo/?periodo=${periodo}`);
            if (res.data?.consolidado) {
                setData(res.data);
                setIsDemo(false);
            } else {
                setData(MOCK_GIVEAWAY_RESUMO as any);
                setIsDemo(true);
            }
        } catch (err) {
            console.error('GiveAway fetch falhou — usando mock', err);
            setData(MOCK_GIVEAWAY_RESUMO as any);
            setIsDemo(true);
        } finally {
            setLoading(false);
        }
    }, [periodo]);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 60000);
        return () => clearInterval(interval);
    }, [fetchData]);

    return (
        <div className="isa-root" style={{ padding: '16px 20px', minHeight: '100vh' }}>
            {/* Cabeçalho */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: 12, marginBottom: 14 }}>
                <div>
                    <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: 'var(--isa-text)', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Scale size={20} style={{ color: 'var(--isa-accent)' }} />
                        Gestão de Give Away
                        {isDemo && <Tag tone="warn">SIMULAÇÃO</Tag>}
                    </h1>
                    <div style={{ marginTop: 2, fontSize: 'var(--isa-fs-default)', color: 'var(--isa-text-muted)' }}>
                        Excesso de peso vs referência teórica · {PERIODO_LABEL[periodo]}
                    </div>
                </div>

                <div className="isa-toolbar" style={{ marginBottom: 0 }}>
                    <label htmlFor="periodo">Período</label>
                    <select
                        id="periodo"
                        value={periodo}
                        onChange={e => setPeriodo(e.target.value)}
                    >
                        <option value="TURNO">Turno atual</option>
                        <option value="DIA">Hoje</option>
                        <option value="MES">Este mês</option>
                    </select>
                    <button type="button" className="ghost" onClick={fetchData} disabled={loading}>
                        <RefreshCw size={12} style={{ marginRight: 4, verticalAlign: -1 }} />
                        {loading ? 'Atualizando…' : 'Atualizar'}
                    </button>
                </div>
            </div>

            {/* KPI strip */}
            <KpiStrip cols={3}>
                <KpiCard
                    label="Give Away Total"
                    value={numFmt.num(data?.consolidado.giveaway_kg, 1)}
                    unit="kg"
                />
                <KpiCard
                    label="Percentual Global"
                    value={numFmt.num(data?.consolidado.giveaway_percent, 2)}
                    unit="%"
                    delta={
                        data && data.consolidado.giveaway_percent > 1.5
                            ? { value: 'Acima do limite (1,5%)', tone: 'down' }
                            : data
                              ? { value: 'Dentro do limite', tone: 'up' }
                              : undefined
                    }
                />
                <KpiCard
                    label="Produção Teórica"
                    value={numFmt.int(data?.consolidado.producao_ref_kg)}
                    unit="kg"
                    delta={{ value: 'Referência de cálculo', tone: 'neutral' }}
                />
            </KpiStrip>

            {/* Tabela detalhada */}
            <Panel title="Detalhamento por Linha" desc="Ranking de excesso de peso por linha de produção">
                <div style={{ overflowX: 'auto' }}>
                    <table className="isa-tbl">
                        <thead>
                            <tr>
                                <th>Linha</th>
                                <th>Equipamento (sensor)</th>
                                <th style={{ textAlign: 'right' }}>Produção (un)</th>
                                <th style={{ textAlign: 'right' }}>Give Away (kg)</th>
                                <th style={{ textAlign: 'right' }}>% Excesso</th>
                                <th style={{ textAlign: 'center' }}>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data?.por_linha
                                .slice()
                                .sort((a, b) => b.giveaway_percent - a.giveaway_percent)
                                .map(linha => {
                                    const tone: 'ok' | 'warn' | 'bad' =
                                        linha.giveaway_percent > 2.0 ? 'bad'
                                        : linha.giveaway_percent > 1.5 ? 'warn'
                                        : 'ok';
                                    return (
                                        <tr key={linha.codigo}>
                                            <td style={{ fontWeight: 500 }}>{linha.linha}</td>
                                            <td style={{ color: 'var(--isa-text-muted)' }}>{linha.equipamento_leitura}</td>
                                            <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                                                {linha.producao_unidades.toLocaleString('pt-BR')}
                                            </td>
                                            <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: 'var(--isa-bad)' }}>
                                                {linha.giveaway_kg.toFixed(2)}
                                            </td>
                                            <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                                                <Tag tone={tone}>{linha.giveaway_percent.toFixed(2)}%</Tag>
                                            </td>
                                            <td style={{ textAlign: 'center' }}>
                                                {linha.giveaway_percent > 2.0 ? (
                                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--isa-bad)', fontWeight: 500, fontSize: 'var(--isa-fs-body)' }}>
                                                        <AlertTriangle size={14} /> Crítico
                                                    </span>
                                                ) : (
                                                    <span style={{ color: 'var(--isa-ok)', fontWeight: 500, fontSize: 'var(--isa-fs-body)' }}>Normal</span>
                                                )}
                                            </td>
                                        </tr>
                                    );
                                })}
                            {(!data || data.por_linha.length === 0) && (
                                <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--isa-text-muted)', padding: 20 }}>Sem dados de give-away no período.</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </Panel>
        </div>
    );
};

export default GiveAwayDashboard;
