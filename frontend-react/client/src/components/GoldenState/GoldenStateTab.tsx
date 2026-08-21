import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Award, AlertTriangle, CheckCircle2, ChevronRight, Info, RefreshCw,
    Plus, X, Trash2, Sparkles, Wand2, Zap, Bot,
} from 'lucide-react';
import { DJANGO_API_URL } from '@/config/api';

/**
 * Golden State — "Receita de Ouro" da linha.
 *
 * Elementos:
 *   1. Hero: score gigante de aderência ao estado de ouro AGORA.
 *   2. Recipe Card grid: variáveis golden vs faixa derivada dos runs.
 *   3. Janelas de referência: turnos catalogados que viraram a receita.
 *   4. Calendário 30 dias: heatmap de aderência.
 *   5. Botão "Capturar momento" + lista completa dos runs salvos.
 */

interface GoldenVar {
    id: number;
    codigo: string;
    nome: string;
    origem: 'sensor' | 'tag';
    tag_influx: string;
    unidade: string;
    equipamento_codigo: string | null;
    equipamento_nome: string;
    valor_atual: number | null;
    ouro_min: number | null;
    ouro_max: number | null;
    ouro_ideal: number | null;
    amostras_ouro: number;
    n_runs_referencia: number;
    status: 'ok' | 'warn' | 'bad' | 'sem_dado';
    drift_pct: number | null;
    tempo_fora_min: number | null;
    tem_node_id: boolean;
}

interface JanelaReferencia {
    id: number;
    nome: string;
    data: string;
    inicio: string;
    fim: string;
    sku_codigo: string | null;
    formato_gramas: number | null;
    fonte: 'AUTO' | 'MANUAL';
    fonte_label: string;
    score: number | null;
    tph: number | null;
    refugo_pct: number | null;
    oee: number | null;
    observacoes: string;
}

interface CalendarioDia {
    data: string;
    score: number | null;
    n_vars: number;
}

interface Run {
    id: number;
    nome: string;
    data: string;
    inicio: string;
    fim: string;
    sku_codigo: string | null;
    formato_gramas: number | null;
    fonte: 'AUTO' | 'MANUAL';
    fonte_label: string;
    score: number | null;
    tph_medio: number | null;
    refugo_pct: number | null;
    oee_medio: number | null;
    observacoes: string;
    ativo: boolean;
    criado_em: string;
    criado_por: string;
    n_variaveis: number;
}

interface GoldenStateResp {
    linha: string;
    linha_nome: string;
    sku_atual: string | null;
    formato_atual: number | null;
    dias_referencia: number;
    filtro_aplicado: 'sku' | 'formato' | 'todos';
    tolerancia_aplicada: 'estreita' | 'padrao' | 'larga';
    ouro_score_atual: number | null;
    janelas_referencia: JanelaReferencia[];
    variaveis: GoldenVar[];
    calendario: CalendarioDia[];
    auto_capture?: {
        ativo: boolean;
        criterio: string;
        ultima_captura: string | null;
        ultima_captura_nome: string | null;
    };
    mensagem?: string;
}

interface Props {
    linhaId: number;
    linhaCodigo?: string;
}

function fmtNum(v: number | null | undefined, digits = 2): string {
    if (v === null || v === undefined || !Number.isFinite(v)) return '—';
    return v.toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function fmtDateBR(iso: string): string {
    try { return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }); }
    catch { return iso; }
}

function scoreTone(score: number | null) {
    if (score === null) return { color: '#657384', bg: '#f0f2f5', label: 'sem dados' };
    if (score >= 85) return { color: '#1f7a3b', bg: '#dff4e3', label: 'em receita' };
    if (score >= 65) return { color: '#a06200', bg: '#fbe9c8', label: 'atenção' };
    return { color: '#b53a2b', bg: '#f4dad6', label: 'fora da receita' };
}

function statusGlyph(status: GoldenVar['status']) {
    switch (status) {
        case 'ok': return { color: '#1f7a3b', bg: '#dff4e3', icon: <CheckCircle2 size={14} />, label: 'dentro' };
        case 'warn': return { color: '#a06200', bg: '#fbe9c8', icon: <AlertTriangle size={14} />, label: 'borda' };
        case 'bad': return { color: '#b53a2b', bg: '#f4dad6', icon: <AlertTriangle size={14} />, label: 'fora' };
        default: return { color: '#657384', bg: '#f0f2f5', icon: <Info size={14} />, label: 'sem dado' };
    }
}

function calendarColor(score: number | null): string {
    if (score === null) return '#eef0f3';
    if (score >= 85) return '#1f7a3b';
    if (score >= 70) return '#7cb46a';
    if (score >= 55) return '#d6a93b';
    if (score >= 40) return '#d77a48';
    return '#b53a2b';
}

// =============================================================================
// Modal de captura
// =============================================================================
function CapturaModal({
    linhaId, skuAtual, formatoAtual, onClose, onCaptured,
}: {
    linhaId: number;
    skuAtual: string | null;
    formatoAtual: number | null;
    onClose: () => void;
    onCaptured: () => void;
}) {
    const [duracao, setDuracao] = useState<number>(30); // minutos
    const [nome, setNome] = useState('');
    const [observacoes, setObservacoes] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const submit = async () => {
        setSubmitting(true);
        setError(null);
        try {
            const fim = new Date();
            const inicio = new Date(fim.getTime() - duracao * 60_000);
            const res = await fetch(`${DJANGO_API_URL}/linhas/${linhaId}/golden-state/capturar/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    nome: nome.trim(),
                    inicio: inicio.toISOString(),
                    fim: fim.toISOString(),
                    sku_codigo: skuAtual,
                    formato_gramas: formatoAtual,
                    observacoes: observacoes.trim(),
                }),
            });
            const data = await res.json();
            if (!res.ok) {
                setError(data.detail || `HTTP ${res.status}`);
                return;
            }
            onCaptured();
            onClose();
        } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div
            onClick={onClose}
            style={{
                position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                zIndex: 1000,
            }}
        >
            <div
                onClick={e => e.stopPropagation()}
                style={{
                    background: '#fff', borderRadius: 8, padding: 20,
                    width: 'min(480px, 95vw)', boxShadow: '0 12px 32px rgba(0,0,0,0.18)',
                }}
            >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                    <div>
                        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
                            <Sparkles size={18} color="#a06200" /> Capturar momento como referência
                        </h3>
                        <p style={{ margin: '4px 0 0', fontSize: 12, color: '#657384' }}>
                            Salva os valores das variáveis golden agora como uma corrida de referência para futuras comparações.
                        </p>
                    </div>
                    <button type="button" onClick={onClose} style={{
                        background: 'transparent', border: 'none', cursor: 'pointer',
                        color: '#657384', padding: 4,
                    }} aria-label="Fechar">
                        <X size={18} />
                    </button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}>
                    <label style={{ fontSize: 12, color: 'var(--isa-text)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                        Nome curto (opcional)
                        <input
                            type="text" value={nome} onChange={e => setNome(e.target.value)}
                            placeholder="Ex: Turno A 17/05 — depois do ajuste de pressão"
                            style={{
                                padding: '7px 10px', fontSize: 13, border: '1px solid #cfd8dc',
                                borderRadius: 4, fontFamily: 'inherit',
                            }}
                        />
                    </label>

                    <label style={{ fontSize: 12, color: 'var(--isa-text)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                        Duração da janela (minutos antes de agora)
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <input
                                type="range" min={5} max={240} step={5}
                                value={duracao} onChange={e => setDuracao(Number(e.target.value))}
                                style={{ flex: 1 }}
                            />
                            <strong style={{ minWidth: 70, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                                {duracao} min
                            </strong>
                        </div>
                        <span style={{ fontSize: 11, color: '#657384' }}>
                            Período: {new Date(Date.now() - duracao * 60_000).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })} → agora
                        </span>
                    </label>

                    <label style={{ fontSize: 12, color: 'var(--isa-text)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                        Observações (opcional)
                        <textarea
                            value={observacoes} onChange={e => setObservacoes(e.target.value)}
                            placeholder="Anote o que estava diferente neste momento"
                            rows={3}
                            style={{
                                padding: '7px 10px', fontSize: 13, border: '1px solid #cfd8dc',
                                borderRadius: 4, fontFamily: 'inherit', resize: 'vertical',
                            }}
                        />
                    </label>

                    {(skuAtual || formatoAtual !== null) && (
                        <div style={{
                            fontSize: 11, color: '#657384',
                            background: '#f7f8fa', padding: '6px 10px', borderRadius: 4,
                            display: 'flex', gap: 12, flexWrap: 'wrap',
                        }}>
                            {skuAtual && <span>SKU: <strong style={{ color: 'var(--isa-text)' }}>{skuAtual}</strong></span>}
                            {formatoAtual !== null && <span>Formato: <strong style={{ color: 'var(--isa-text)' }}>{fmtNum(formatoAtual, 0)}g</strong></span>}
                            <span style={{ flexBasis: '100%', fontSize: 10, color: '#657384' }}>
                                Esta captura ficará associada ao SKU e formato acima — útil para filtrar receita por SKU ou por formato depois.
                            </span>
                        </div>
                    )}

                    {error && (
                        <div style={{
                            background: '#f4dad6', color: '#b53a2b', padding: '8px 10px',
                            borderRadius: 4, fontSize: 12, display: 'flex', gap: 6, alignItems: 'flex-start',
                        }}>
                            <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                            <span>{error}</span>
                        </div>
                    )}
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
                    <button
                        type="button" onClick={onClose} disabled={submitting}
                        style={{
                            padding: '7px 14px', fontSize: 13, background: '#fff',
                            border: '1px solid #cfd8dc', borderRadius: 4, cursor: 'pointer',
                            color: 'var(--isa-text)',
                        }}
                    >
                        Cancelar
                    </button>
                    <button
                        type="button" onClick={submit} disabled={submitting}
                        style={{
                            padding: '7px 14px', fontSize: 13, background: '#a06200',
                            color: '#fff', border: 'none', borderRadius: 4,
                            cursor: submitting ? 'not-allowed' : 'pointer',
                            opacity: submitting ? 0.7 : 1,
                            display: 'inline-flex', alignItems: 'center', gap: 6,
                        }}
                    >
                        {submitting ? 'Capturando…' : (<>
                            <Wand2 size={14} /> Capturar
                        </>)}
                    </button>
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// Modal de aplicação ao CLP — revisão antes de escrever os setpoints
// =============================================================================
function AplicarReceitaModal({
    variaveis, filtro, tolerancia, linhaNome, onClose, onConfirm, submitting,
}: {
    variaveis: GoldenVar[];
    filtro: 'sku' | 'formato' | 'todos';
    tolerancia: 'estreita' | 'padrao' | 'larga';
    linhaNome: string;
    onClose: () => void;
    onConfirm: () => void;
    submitting: boolean;
}) {
    // Só aplica em variáveis com node_id E com receita (ouro_ideal != null).
    // O resto é mostrado em "Ignoradas" com o motivo, antes do usuário confirmar.
    const aplicaveis = variaveis.filter(v => v.tem_node_id && v.ouro_ideal !== null);
    const ignoradas = variaveis.filter(v => !v.tem_node_id || v.ouro_ideal === null);

    const [confirmado, setConfirmado] = useState(false);

    const filtroLabel = filtro === 'sku' ? 'SKU atual' : filtro === 'formato' ? 'Formato atual' : 'Todas as corridas';
    const tolLabel = tolerancia === 'estreita' ? 'Estreita (mais rígido)' : tolerancia === 'larga' ? 'Larga (mais permissivo)' : 'Padrão (p10–p90)';

    return (
        <div
            onClick={onClose}
            style={{
                position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                zIndex: 1000, padding: 20,
            }}
        >
            <div
                onClick={e => e.stopPropagation()}
                style={{
                    background: '#fff', borderRadius: 8,
                    width: 'min(720px, 100%)', maxHeight: '88vh', overflow: 'hidden',
                    display: 'flex', flexDirection: 'column',
                    boxShadow: '0 16px 40px rgba(0,0,0,0.22)',
                }}
            >
                {/* ===== Header ===== */}
                <div style={{
                    background: '#fff8e1', borderBottom: '1px solid #f0c987',
                    padding: '14px 20px', display: 'flex', justifyContent: 'space-between',
                    alignItems: 'flex-start', gap: 12,
                }}>
                    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                        <div style={{
                            width: 36, height: 36, borderRadius: 18, background: '#a06200',
                            color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                            flexShrink: 0,
                        }}>
                            <Zap size={18} />
                        </div>
                        <div>
                            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: '#7a5400' }}>
                                Revisar e aplicar receita de ouro
                            </h3>
                            <p style={{ margin: '4px 0 0', fontSize: 12, color: '#7a5400', lineHeight: 1.5 }}>
                                Você está prestes a <strong>escrever setpoints físicos no CLP</strong> da linha <strong>{linhaNome}</strong> via OPC.
                                Esta ação altera o comportamento do equipamento — confira a lista antes de confirmar.
                            </p>
                        </div>
                    </div>
                    <button type="button" onClick={onClose} disabled={submitting} style={{
                        background: 'transparent', border: 'none', cursor: 'pointer',
                        color: '#7a5400', padding: 4,
                    }} aria-label="Fechar">
                        <X size={18} />
                    </button>
                </div>

                {/* ===== Contexto: filtro + tolerância + contagens ===== */}
                <div style={{
                    padding: '10px 20px', display: 'flex', gap: 14, flexWrap: 'wrap',
                    background: '#f7f8fa', borderBottom: '1px solid #eef0f3',
                    fontSize: 12, color: 'var(--isa-text-muted)',
                }}>
                    <span><strong style={{ color: 'var(--isa-text)' }}>Receita base:</strong> {filtroLabel}</span>
                    <span><strong style={{ color: 'var(--isa-text)' }}>Tolerância:</strong> {tolLabel}</span>
                    <span style={{ marginLeft: 'auto', display: 'inline-flex', gap: 8 }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                            <CheckCircle2 size={12} color="#1f7a3b" />
                            <strong style={{ color: 'var(--isa-text)' }}>{aplicaveis.length}</strong> a aplicar
                        </span>
                        {ignoradas.length > 0 && (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                                <AlertTriangle size={12} color="#a06200" />
                                <strong style={{ color: 'var(--isa-text)' }}>{ignoradas.length}</strong> ignoradas
                            </span>
                        )}
                    </span>
                </div>

                {/* ===== Lista de aplicáveis ===== */}
                <div style={{ flex: 1, overflowY: 'auto', padding: '12px 20px' }}>
                    {aplicaveis.length === 0 ? (
                        <div style={{
                            padding: 24, textAlign: 'center', color: 'var(--isa-text-muted)',
                            background: '#f4dad6', borderRadius: 6,
                        }}>
                            <AlertTriangle size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                            Nenhuma variável pode ser aplicada agora. Verifique a seção "Ignoradas" abaixo.
                        </div>
                    ) : (
                        <>
                            <div style={{ fontSize: 11, color: 'var(--isa-text-muted)', marginBottom: 8, textTransform: 'uppercase', fontWeight: 600, letterSpacing: 0.3 }}>
                                Valores que serão escritos no CLP ({aplicaveis.length})
                            </div>
                            <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                                <thead>
                                    <tr style={{ background: '#f7f8fa', color: 'var(--isa-text-muted)', fontWeight: 600, fontSize: 11 }}>
                                        <th style={{ padding: '6px 8px', textAlign: 'left' }}>Variável</th>
                                        <th style={{ padding: '6px 8px', textAlign: 'right' }}>Atual</th>
                                        <th style={{ padding: '6px 8px', textAlign: 'center', width: 24 }}></th>
                                        <th style={{ padding: '6px 8px', textAlign: 'right' }}>Vai aplicar</th>
                                        <th style={{ padding: '6px 8px', textAlign: 'right' }}>Δ</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {aplicaveis.map(v => {
                                        const atual = v.valor_atual;
                                        const alvo = v.ouro_ideal!;
                                        const delta = (atual !== null) ? alvo - atual : null;
                                        const deltaPct = (atual !== null && atual !== 0) ? (delta! / Math.abs(atual)) * 100 : null;
                                        const deltaColor = delta === null ? 'var(--isa-text-muted)'
                                            : Math.abs(deltaPct ?? 0) < 1 ? '#1f7a3b'
                                            : Math.abs(deltaPct ?? 0) < 5 ? '#a06200' : '#b53a2b';
                                        return (
                                            <tr key={`${v.origem}-${v.id}`} style={{ borderTop: '1px solid #eef0f3' }}>
                                                <td style={{ padding: '8px 8px', color: 'var(--isa-text)' }}>
                                                    <div style={{ fontWeight: 500 }}>{v.nome}</div>
                                                    <div style={{ fontSize: 10, color: 'var(--isa-text-muted)' }}>
                                                        {v.equipamento_nome} · {v.tag_influx}
                                                    </div>
                                                </td>
                                                <td style={{ padding: '8px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--isa-text-muted)' }}>
                                                    {atual !== null ? `${fmtNum(atual)} ${v.unidade}` : '—'}
                                                </td>
                                                <td style={{ textAlign: 'center', color: '#a06200' }}>
                                                    <ChevronRight size={14} />
                                                </td>
                                                <td style={{ padding: '8px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: '#a06200' }}>
                                                    {fmtNum(alvo)} {v.unidade}
                                                </td>
                                                <td style={{ padding: '8px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontSize: 11, color: deltaColor }}>
                                                    {delta === null ? '—' : (
                                                        <>
                                                            {delta > 0 ? '+' : ''}{fmtNum(delta)}
                                                            {deltaPct !== null && <span style={{ marginLeft: 4, opacity: 0.7 }}>({deltaPct > 0 ? '+' : ''}{deltaPct.toFixed(1)}%)</span>}
                                                        </>
                                                    )}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </>
                    )}

                    {ignoradas.length > 0 && (
                        <div style={{ marginTop: 16 }}>
                            <div style={{ fontSize: 11, color: 'var(--isa-text-muted)', marginBottom: 8, textTransform: 'uppercase', fontWeight: 600, letterSpacing: 0.3 }}>
                                Variáveis ignoradas ({ignoradas.length})
                            </div>
                            <div style={{
                                background: '#fff7e6', border: '1px solid #f0c987',
                                borderRadius: 4, padding: '10px 12px',
                            }}>
                                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: '#7a5400' }}>
                                    {ignoradas.map(v => {
                                        const motivo = !v.tem_node_id
                                            ? 'sem Node ID OPC mapeado — cadastre em Admin › Tag de Coleta'
                                            : 'sem amostras na receita atual';
                                        return (
                                            <li key={`${v.origem}-${v.id}`} style={{ marginBottom: 4 }}>
                                                <strong>{v.nome}</strong> ({v.equipamento_nome}) — <em>{motivo}</em>
                                            </li>
                                        );
                                    })}
                                </ul>
                            </div>
                        </div>
                    )}
                </div>

                {/* ===== Footer com confirmação explícita ===== */}
                <div style={{
                    padding: '12px 20px', borderTop: '1px solid #eef0f3',
                    background: '#fafbfc', display: 'flex', flexDirection: 'column', gap: 10,
                }}>
                    {aplicaveis.length > 0 && (
                        <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 12, color: 'var(--isa-text)', cursor: 'pointer' }}>
                            <input
                                type="checkbox"
                                checked={confirmado}
                                onChange={e => setConfirmado(e.target.checked)}
                                disabled={submitting}
                                style={{ marginTop: 2, flexShrink: 0 }}
                            />
                            <span>
                                Eu entendo que esta ação <strong>escreve setpoints físicos no CLP</strong> da linha {linhaNome}
                                e pode alterar imediatamente o comportamento dos equipamentos.
                            </span>
                        </label>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                        <button
                            type="button" onClick={onClose} disabled={submitting}
                            style={{
                                padding: '8px 16px', fontSize: 13, background: '#fff',
                                border: '1px solid #cfd8dc', borderRadius: 4,
                                cursor: submitting ? 'not-allowed' : 'pointer',
                                color: 'var(--isa-text)',
                            }}
                        >
                            Cancelar
                        </button>
                        <button
                            type="button" onClick={onConfirm}
                            disabled={submitting || !confirmado || aplicaveis.length === 0}
                            style={{
                                padding: '8px 16px', fontSize: 13,
                                background: (submitting || !confirmado || aplicaveis.length === 0) ? '#9ec5ad' : '#1f7a3b',
                                color: '#fff', border: 'none', borderRadius: 4,
                                cursor: (submitting || !confirmado || aplicaveis.length === 0) ? 'not-allowed' : 'pointer',
                                display: 'inline-flex', alignItems: 'center', gap: 6,
                                fontWeight: 600,
                            }}
                        >
                            <Zap size={14} />
                            {submitting ? 'Enviando…' : `Aplicar ${aplicaveis.length} valor${aplicaveis.length !== 1 ? 'es' : ''} ao CLP`}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// Componente principal
// =============================================================================
export default function GoldenStateTab({ linhaId, linhaCodigo }: Props) {
    const [data, setData] = useState<GoldenStateResp | null>(null);
    const [runs, setRuns] = useState<Run[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [showModal, setShowModal] = useState(false);
    const [showAplicarModal, setShowAplicarModal] = useState(false);
    const [filtro, setFiltro] = useState<'sku' | 'formato' | 'todos'>('sku');
    const [tolerancia, setTolerancia] = useState<'estreita' | 'padrao' | 'larga'>('padrao');
    const [aplicando, setAplicando] = useState(false);
    const [aplicacaoResultado, setAplicacaoResultado] = useState<{
        ok: boolean; titulo: string; detalhe: string; batches?: any[]; ignorados?: any[];
    } | null>(null);

    const fetchAll = async () => {
        setLoading(true);
        setError(null);
        try {
            const qp = new URLSearchParams({ filtro, tolerancia });
            const [r1, r2] = await Promise.all([
                fetch(`${DJANGO_API_URL}/linhas/${linhaId}/golden-state/?${qp}`),
                fetch(`${DJANGO_API_URL}/linhas/${linhaId}/golden-state/runs/`),
            ]);
            if (!r1.ok) throw new Error(`HTTP ${r1.status}`);
            setData(await r1.json());
            if (r2.ok) setRuns(await r2.json());
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Falha ao carregar Golden State');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchAll(); }, [linhaId, filtro, tolerancia]);

    // Abre o modal de revisão. A aplicação real só acontece em executarAplicacao().
    const aplicarReceita = () => {
        setAplicacaoResultado(null);
        setShowAplicarModal(true);
    };

    const executarAplicacao = async () => {
        setAplicando(true);
        try {
            const res = await fetch(`${DJANGO_API_URL}/linhas/${linhaId}/golden-state/aplicar/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filtro, tolerancia }),
            });
            const j = await res.json();
            if (res.ok || res.status === 202) {
                setAplicacaoResultado({
                    ok: true,
                    titulo: 'Receita enviada ao CLP',
                    detalhe: `${j.total_comandos || 0} comando(s) enfileirado(s) em ${j.batches?.length || 0} equipamento(s). O coletor irá escrever via OPC.`,
                    batches: j.batches,
                    ignorados: j.ignorados,
                });
                setShowAplicarModal(false);
            } else {
                setAplicacaoResultado({
                    ok: false,
                    titulo: 'Não foi possível aplicar',
                    detalhe: j.detail || 'Erro desconhecido',
                    ignorados: j.ignorados,
                });
            }
        } catch (e) {
            setAplicacaoResultado({
                ok: false, titulo: 'Erro de rede',
                detalhe: e instanceof Error ? e.message : String(e),
            });
        } finally {
            setAplicando(false);
        }
    };

    const tone = useMemo(() => scoreTone(data?.ouro_score_atual ?? null), [data?.ouro_score_atual]);
    const navigate = useNavigate();

    const desativarRun = async (runId: number) => {
        if (!confirm('Desativar esta corrida? Ela deixará de contar na receita.')) return;
        try {
            const res = await fetch(`${DJANGO_API_URL}/linhas/${linhaId}/golden-state/runs/${runId}/`, {
                method: 'DELETE',
            });
            if (res.ok) fetchAll();
        } catch {}
    };

    const calendarMatrix = useMemo(() => {
        if (!data?.calendario?.length) return [];
        const pads: (CalendarioDia | null)[] = [];
        const first = data.calendario[0];
        if (first) {
            const firstDow = new Date(first.data + 'T00:00:00').getDay();
            for (let i = 0; i < firstDow; i++) pads.push(null);
        }
        const all = [...pads, ...data.calendario];
        const rows: ((CalendarioDia | null)[])[] = [];
        for (let i = 0; i < all.length; i += 7) rows.push(all.slice(i, i + 7));
        return rows;
    }, [data?.calendario]);

    if (loading) {
        return <div style={{ padding: 24, textAlign: 'center', color: '#657384' }}>Carregando estado de ouro…</div>;
    }
    if (error) {
        return (
            <div style={{ padding: 24, color: '#b53a2b' }}>
                <AlertTriangle size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                Erro: {error}
            </div>
        );
    }
    if (!data) return null;

    const semVariaveisGolden = data.variaveis.length === 0;
    const semRuns = data.janelas_referencia.length === 0;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8 }}>
                <div>
                    <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: 'var(--isa-text)', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Award size={20} color="#a06200" /> Estado de Ouro — {data.linha_nome ?? linhaCodigo}
                    </h2>
                    <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--isa-text-muted)' }}>
                        Receita derivada das corridas catalogadas
                        {data.sku_atual && <> · rodando <strong style={{ color: 'var(--isa-text)' }}>SKU {data.sku_atual}</strong></>}
                        {data.formato_atual !== null && <> · formato <strong style={{ color: 'var(--isa-text)' }}>{fmtNum(data.formato_atual, 0)}g</strong></>}
                    </p>

                    {/* Seletores discretos (filtro + tolerância) */}
                    <div style={{ display: 'flex', gap: 14, marginTop: 8, fontSize: 11, color: 'var(--isa-text-muted)', alignItems: 'center', flexWrap: 'wrap' }}>
                        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                            <span>Receita por:</span>
                            <select
                                value={filtro}
                                onChange={e => setFiltro(e.target.value as any)}
                                style={{
                                    fontSize: 11, padding: '2px 4px', border: '1px solid #cfd8dc',
                                    borderRadius: 3, background: '#fff', color: 'var(--isa-text)',
                                }}
                            >
                                <option value="sku">SKU atual{data.sku_atual ? ` (${data.sku_atual})` : ''}</option>
                                <option value="formato">Formato{data.formato_atual !== null ? ` (${fmtNum(data.formato_atual, 0)}g)` : ''}</option>
                                <option value="todos">Todas as corridas</option>
                            </select>
                        </label>
                        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }} title="Define a largura da faixa de ouro. Estreita = exigente; Larga = permissiva.">
                            <span>Tolerância:</span>
                            <select
                                value={tolerancia}
                                onChange={e => setTolerancia(e.target.value as any)}
                                style={{
                                    fontSize: 11, padding: '2px 4px', border: '1px solid #cfd8dc',
                                    borderRadius: 3, background: '#fff', color: 'var(--isa-text)',
                                }}
                            >
                                <option value="estreita">Estreita (mais rígido)</option>
                                <option value="padrao">Padrão (p10–p90)</option>
                                <option value="larga">Larga (mais permissivo)</option>
                            </select>
                        </label>
                    </div>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <button
                        type="button" onClick={aplicarReceita}
                        disabled={aplicando || semVariaveisGolden || semRuns}
                        title={
                            semVariaveisGolden ? 'Marque variáveis no admin antes' :
                            semRuns ? 'Capture uma corrida antes' :
                            'Envia o valor ideal (mediana) de cada variável golden ao CLP via OPC'
                        }
                        style={{
                            padding: '7px 12px', fontSize: 12, background: '#1f7a3b',
                            color: '#fff', border: 'none', borderRadius: 4,
                            cursor: (aplicando || semVariaveisGolden || semRuns) ? 'not-allowed' : 'pointer',
                            opacity: (aplicando || semVariaveisGolden || semRuns) ? 0.5 : 1,
                            display: 'inline-flex', alignItems: 'center', gap: 6,
                        }}
                    >
                        <Zap size={14} /> {aplicando ? 'Enviando…' : 'Aplicar ao CLP'}
                    </button>
                    <button
                        type="button" onClick={() => setShowModal(true)}
                        disabled={semVariaveisGolden}
                        title={semVariaveisGolden ? 'Marque variáveis como Golden State no admin antes' : 'Cria uma corrida de referência com os valores atuais'}
                        style={{
                            padding: '7px 12px', fontSize: 12, background: '#a06200',
                            color: '#fff', border: 'none', borderRadius: 4,
                            cursor: semVariaveisGolden ? 'not-allowed' : 'pointer',
                            opacity: semVariaveisGolden ? 0.5 : 1,
                            display: 'inline-flex', alignItems: 'center', gap: 6,
                        }}
                    >
                        <Sparkles size={14} /> Capturar momento
                    </button>
                    <button
                        type="button" onClick={fetchAll}
                        style={{
                            padding: '6px 10px', fontSize: 12, background: '#fff',
                            border: '1px solid #cfd8dc', borderRadius: 4, cursor: 'pointer',
                            display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--isa-text)',
                        }}
                    >
                        <RefreshCw size={12} /> Atualizar
                    </button>
                </div>
            </div>

            {/* Bloco discreto explicando captura automática */}
            {data.auto_capture && (
                <div style={{
                    display: 'flex', alignItems: 'center', gap: 10, fontSize: 11,
                    color: 'var(--isa-text-muted)',
                    padding: '6px 10px', background: 'var(--isa-bg-panel, #f7f8fa)',
                    border: '1px solid var(--isa-border, #eef0f3)', borderRadius: 4,
                }}>
                    <Bot size={14} style={{ flexShrink: 0 }} />
                    <span>
                        <strong>Captura automática:</strong> {data.auto_capture.criterio}.
                        {data.auto_capture.ultima_captura
                            ? <> Última: <span style={{ color: 'var(--isa-text)' }}>{data.auto_capture.ultima_captura_nome}</span> em {fmtDateBR(data.auto_capture.ultima_captura)}.</>
                            : <> Nenhuma corrida capturada automaticamente ainda nesta linha.</>}
                    </span>
                </div>
            )}

            {/* Resultado da aplicação ao CLP */}
            {aplicacaoResultado && (
                <div style={{
                    background: aplicacaoResultado.ok ? '#dff4e3' : '#f4dad6',
                    border: `1px solid ${aplicacaoResultado.ok ? '#7cb46a' : '#d77a48'}`,
                    color: aplicacaoResultado.ok ? '#1f5a2b' : '#7a2920',
                    borderRadius: 6, padding: '10px 14px',
                    display: 'flex', alignItems: 'flex-start', gap: 10,
                }}>
                    {aplicacaoResultado.ok ? <Zap size={18} /> : <AlertTriangle size={18} />}
                    <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600 }}>{aplicacaoResultado.titulo}</div>
                        <div style={{ fontSize: 12, marginTop: 2 }}>{aplicacaoResultado.detalhe}</div>
                        {aplicacaoResultado.batches && aplicacaoResultado.batches.length > 0 && (
                            <ul style={{ margin: '6px 0 0 18px', fontSize: 11 }}>
                                {aplicacaoResultado.batches.flatMap((b: any) =>
                                    (b.comandos || []).map((c: any, i: number) => (
                                        <li key={`${b.batch_id}-${i}`}>
                                            <strong>{c.nome}</strong> → {c.value} {c.unidade} <span style={{ opacity: 0.7 }}>({c.tag} em {b.equipamento_codigo})</span>
                                        </li>
                                    ))
                                )}
                            </ul>
                        )}
                        {aplicacaoResultado.ignorados && aplicacaoResultado.ignorados.length > 0 && (
                            <div style={{ fontSize: 11, marginTop: 6 }}>
                                <strong>Ignoradas:</strong>
                                <ul style={{ margin: '2px 0 0 18px' }}>
                                    {aplicacaoResultado.ignorados.map((ig: any, i: number) => (
                                        <li key={i}>{ig.nome} — <em>{ig.motivo}</em></li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                    <button
                        type="button" onClick={() => setAplicacaoResultado(null)}
                        style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'inherit' }}
                    >
                        <X size={14} />
                    </button>
                </div>
            )}

            {semVariaveisGolden ? (
                <div style={{
                    background: '#fff7e6', border: '1px solid #f0c987', borderRadius: 6,
                    padding: 16, color: '#7a5400', display: 'flex', gap: 12, alignItems: 'flex-start',
                }}>
                    <Info size={20} style={{ flexShrink: 0, marginTop: 1 }} />
                    <div>
                        <div style={{ fontWeight: 600, marginBottom: 4 }}>Nenhuma variável marcada como Golden State</div>
                        <div style={{ fontSize: 13, lineHeight: 1.5 }}>
                            Abra o admin Django, edite um Sensor ou Tag de Coleta e marque a opção "Golden State".
                            <br />
                            <em>Sugestão:</em> marque setpoints (velocidade alvo, pressão alvo) e parâmetros de receita.
                            <em> NÃO marque</em> leituras de ambiente.
                        </div>
                    </div>
                </div>
            ) : semRuns ? (
                <div style={{
                    background: '#eaf4ff', border: '1px solid #9ec5f0', borderRadius: 6,
                    padding: 16, color: '#1b4f8c', display: 'flex', gap: 12, alignItems: 'flex-start',
                }}>
                    <Sparkles size={20} style={{ flexShrink: 0, marginTop: 1 }} />
                    <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, marginBottom: 4 }}>
                            Receita ainda não definida ({data.variaveis.length} variável{data.variaveis.length !== 1 ? 'is' : ''} marcadas, sem corridas catalogadas)
                        </div>
                        <div style={{ fontSize: 13, lineHeight: 1.5 }}>
                            {data.mensagem}
                            <br /><br />
                            <button
                                type="button" onClick={() => setShowModal(true)}
                                style={{
                                    padding: '6px 12px', fontSize: 12, background: '#1b4f8c',
                                    color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer',
                                    display: 'inline-flex', alignItems: 'center', gap: 6,
                                }}
                            >
                                <Sparkles size={13} /> Capturar este momento como referência
                            </button>
                        </div>
                    </div>
                </div>
            ) : (
                <>
                    {/* ===== HERO ===== */}
                    <div style={{
                        background: tone.bg,
                        border: `1px solid ${tone.color}33`,
                        borderRadius: 8, padding: '18px 24px',
                        display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 24, alignItems: 'center',
                    }}>
                        <div style={{
                            fontSize: 56, fontWeight: 700, color: tone.color,
                            lineHeight: 1, fontVariantNumeric: 'tabular-nums', minWidth: 120,
                        }}>
                            {data.ouro_score_atual !== null ? `${data.ouro_score_atual.toFixed(0)}%` : '—'}
                        </div>
                        <div>
                            <div style={{ fontSize: 12, color: tone.color, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                                Aderência à receita de ouro · {tone.label}
                            </div>
                            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--isa-text)', lineHeight: 1.5 }}>
                                {data.variaveis.filter(v => v.status === 'ok').length} de {data.variaveis.length} variáveis dentro da faixa ideal
                                {data.variaveis.filter(v => v.status === 'bad').length > 0 && (
                                    <> · <strong style={{ color: '#b53a2b' }}>{data.variaveis.filter(v => v.status === 'bad').length} fora</strong></>
                                )}
                            </div>
                            <div style={{
                                marginTop: 8, fontSize: 11, color: 'var(--isa-text-muted)',
                                display: 'flex', alignItems: 'center', gap: 6,
                            }} title="A faixa de ouro vem dos percentis das corridas de referência (snapshots p10-p90 por variável). A tolerância acima alarga ou aperta essa faixa.">
                                <Info size={12} />
                                <span>
                                    Faixa = percentis das {data.janelas_referencia.length} corrida(s) de referência ·
                                    <strong> tolerância {tolerancia}</strong>
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* ===== RECIPE CARDS GRID ===== */}
                    <div>
                        <h3 style={{ margin: '0 0 10px', fontSize: 14, fontWeight: 600, color: 'var(--isa-text)' }}>
                            Receita · variáveis golden
                        </h3>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
                            {data.variaveis.map(v => {
                                const g = statusGlyph(v.status);
                                const range = (v.ouro_min !== null && v.ouro_max !== null)
                                    ? `${fmtNum(v.ouro_min)} – ${fmtNum(v.ouro_max)}`
                                    : 'sem amostras';
                                let pctPos: number | null = null;
                                if (v.valor_atual !== null && v.ouro_min !== null && v.ouro_max !== null) {
                                    const amp = v.ouro_max - v.ouro_min || 1;
                                    pctPos = ((v.valor_atual - v.ouro_min) / amp) * 100;
                                }
                                return (
                                    <div key={`${v.origem}-${v.id}`} style={{
                                        background: '#fff', border: '1px solid var(--isa-border, #cfd8dc)', borderRadius: 6,
                                        padding: 12, borderLeft: `4px solid ${g.color}`,
                                    }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                                            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--isa-text)' }}>{v.nome}</div>
                                            <span style={{
                                                fontSize: 10, color: g.color, background: g.bg,
                                                padding: '2px 7px', borderRadius: 10, fontWeight: 600,
                                                display: 'inline-flex', alignItems: 'center', gap: 3,
                                            }}>
                                                {g.icon} {g.label}
                                            </span>
                                        </div>
                                        <div style={{ fontSize: 11, color: 'var(--isa-text-muted)', marginTop: 2 }}>
                                            {v.equipamento_nome}{v.origem === 'sensor' && ` · sensor ${v.codigo}`}
                                        </div>

                                        <div style={{ marginTop: 10, display: 'flex', alignItems: 'baseline', gap: 6 }}>
                                            <span style={{ fontSize: 22, fontWeight: 700, color: g.color, fontVariantNumeric: 'tabular-nums' }}>
                                                {fmtNum(v.valor_atual)}
                                            </span>
                                            <span style={{ fontSize: 12, color: 'var(--isa-text-muted)' }}>{v.unidade}</span>
                                            {v.drift_pct !== null && (
                                                <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--isa-text-muted)', fontVariantNumeric: 'tabular-nums' }}
                                                    title="Desvio em relação ao valor ideal (mediana da faixa de ouro)">
                                                    {v.drift_pct > 0 ? '+' : ''}{v.drift_pct.toFixed(1)}% vs ideal
                                                </span>
                                            )}
                                        </div>

                                        <div style={{ marginTop: 10, position: 'relative', height: 10, background: '#f0f2f5', borderRadius: 5, overflow: 'visible' }}>
                                            <div style={{
                                                position: 'absolute', top: 0, bottom: 0, left: 0, right: 0,
                                                background: 'linear-gradient(to right, #f4dad6 0%, #fbe9c8 8%, #dff4e3 30%, #dff4e3 70%, #fbe9c8 92%, #f4dad6 100%)',
                                                borderRadius: 5,
                                            }} />
                                            {pctPos !== null && (
                                                <div style={{
                                                    position: 'absolute', top: -3, bottom: -3,
                                                    left: `${Math.max(0, Math.min(100, pctPos))}%`,
                                                    width: 3, background: g.color, borderRadius: 2,
                                                    transform: 'translateX(-50%)',
                                                }} title={`Atual: ${fmtNum(v.valor_atual)} ${v.unidade}`} />
                                            )}
                                        </div>
                                        <div style={{ marginTop: 4, display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--isa-text-muted)', fontVariantNumeric: 'tabular-nums' }}>
                                            <span>faixa de ouro {range} {v.unidade}</span>
                                            {v.ouro_ideal !== null && <span>alvo {fmtNum(v.ouro_ideal)}</span>}
                                        </div>
                                        {v.n_runs_referencia > 0 && (
                                            <div style={{ fontSize: 10, color: 'var(--isa-text-muted)', marginTop: 2 }}>
                                                baseado em {v.n_runs_referencia} corrida{v.n_runs_referencia !== 1 ? 's' : ''} de referência
                                            </div>
                                        )}

                                        {v.tempo_fora_min !== null && v.tempo_fora_min > 0 && (
                                            <div style={{
                                                marginTop: 8, fontSize: 11, color: '#7a5400',
                                                background: '#fff7e6', padding: '4px 8px', borderRadius: 4,
                                            }}>
                                                fora da faixa há <strong>~{v.tempo_fora_min} min</strong> nas últimas 4h
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, alignItems: 'start' }}>
                        {/* ===== JANELAS DE REFERÊNCIA ===== */}
                        <div>
                            <h3 style={{ margin: '0 0 10px', fontSize: 14, fontWeight: 600, color: 'var(--isa-text)' }}>
                                Janelas que formam a receita
                            </h3>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                {data.janelas_referencia.map((j, i) => (
                                    <div key={j.id} style={{
                                        background: '#fff', border: '1px solid var(--isa-border, #cfd8dc)',
                                        borderRadius: 6, padding: '10px 12px', display: 'grid',
                                        gridTemplateColumns: 'auto 1fr auto', gap: 12, alignItems: 'center',
                                    }}>
                                        <span style={{
                                            width: 28, height: 28, borderRadius: 14,
                                            background: j.fonte === 'AUTO' ? '#dff4e3' : '#fbe9c8',
                                            color: j.fonte === 'AUTO' ? '#1f7a3b' : '#a06200',
                                            fontWeight: 700, display: 'flex',
                                            alignItems: 'center', justifyContent: 'center', fontSize: 13,
                                        }} title={j.fonte_label}>
                                            #{i + 1}
                                        </span>
                                        <div>
                                            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--isa-text)' }}>
                                                {j.nome}
                                            </div>
                                            <div style={{ fontSize: 11, color: 'var(--isa-text-muted)', fontVariantNumeric: 'tabular-nums' }}>
                                                {j.tph !== null && <>{fmtNum(j.tph)} t/h · </>}
                                                {j.refugo_pct !== null && <>{fmtNum(j.refugo_pct, 1)}% refugo · </>}
                                                {j.oee !== null && <>OEE {fmtNum(j.oee, 1)}%</>}
                                                {j.sku_codigo && <> · SKU {j.sku_codigo}</>}
                                                {j.formato_gramas !== null && <> · {fmtNum(j.formato_gramas, 0)}g</>}
                                            </div>
                                        </div>
                                        {j.score !== null && (
                                            <div style={{ textAlign: 'right' }}>
                                                <div style={{ fontSize: 18, fontWeight: 700, color: '#a06200', fontVariantNumeric: 'tabular-nums' }}>
                                                    {j.score.toFixed(0)}
                                                </div>
                                                <div style={{ fontSize: 9, color: 'var(--isa-text-muted)', textTransform: 'uppercase' }}>
                                                    score
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* ===== CALENDÁRIO ===== */}
                        <div>
                            <h3 style={{ margin: '0 0 10px', fontSize: 14, fontWeight: 600, color: 'var(--isa-text)' }}>
                                Aderência diária · últimos {data.dias_referencia} dias
                            </h3>
                            <div style={{ background: '#fff', border: '1px solid var(--isa-border, #cfd8dc)', borderRadius: 6, padding: 12 }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--isa-text-muted)', marginBottom: 4, fontFamily: 'monospace' }}>
                                    {['D', 'S', 'T', 'Q', 'Q', 'S', 'S'].map((d, i) => (
                                        <span key={i} style={{ width: 26, textAlign: 'center' }}>{d}</span>
                                    ))}
                                </div>
                                {calendarMatrix.map((row, i) => (
                                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: 2, marginBottom: 2 }}>
                                        {row.map((cell, j) => (
                                            <div
                                                key={j}
                                                onClick={() => cell && cell.score !== null && navigate(`/linha/${data.linha}/detalhes`)}
                                                title={cell
                                                    ? (cell.score !== null
                                                        ? `${cell.data}: ${cell.score.toFixed(0)}% aderência · ${cell.n_vars} var.`
                                                        : `${cell.data}: sem dados`)
                                                    : ''}
                                                style={{
                                                    width: 26, height: 26, borderRadius: 4,
                                                    background: cell ? calendarColor(cell.score) : 'transparent',
                                                    cursor: cell?.score !== null ? 'pointer' : 'default',
                                                    border: cell ? '1px solid rgba(0,0,0,0.05)' : 'none',
                                                }}
                                            />
                                        ))}
                                    </div>
                                ))}
                                <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: 'var(--isa-text-muted)', marginTop: 8 }}>
                                    <span>menos</span>
                                    {[null, 40, 55, 70, 85, 100].map(s => (
                                        <span key={String(s)} style={{
                                            width: 12, height: 12, borderRadius: 2,
                                            background: calendarColor(s as number | null),
                                            border: '1px solid rgba(0,0,0,0.06)',
                                        }} />
                                    ))}
                                    <span>mais aderência</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </>
            )}

            {/* ===== CATÁLOGO COMPLETO DE RUNS ===== */}
            {runs.length > 0 && (
                <div>
                    <h3 style={{ margin: '0 0 10px', fontSize: 14, fontWeight: 600, color: 'var(--isa-text)' }}>
                        Corridas catalogadas ({runs.length})
                    </h3>
                    <div style={{ background: '#fff', border: '1px solid var(--isa-border, #cfd8dc)', borderRadius: 6, overflow: 'hidden' }}>
                        <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                            <thead>
                                <tr style={{ background: '#f7f8fa', color: 'var(--isa-text-muted)', fontWeight: 600 }}>
                                    <th style={{ padding: '8px 10px', textAlign: 'left' }}>Nome</th>
                                    <th style={{ padding: '8px 10px', textAlign: 'left' }}>Quando</th>
                                    <th style={{ padding: '8px 10px', textAlign: 'left' }}>SKU</th>
                                    <th style={{ padding: '8px 10px', textAlign: 'right' }}>Formato</th>
                                    <th style={{ padding: '8px 10px', textAlign: 'center' }}>Fonte</th>
                                    <th style={{ padding: '8px 10px', textAlign: 'right' }}>Score</th>
                                    <th style={{ padding: '8px 10px', textAlign: 'right' }}>TPH</th>
                                    <th style={{ padding: '8px 10px', textAlign: 'right' }}>Refugo</th>
                                    <th style={{ padding: '8px 10px', textAlign: 'center' }}>Vars</th>
                                    <th style={{ padding: '8px 10px', textAlign: 'center' }}></th>
                                </tr>
                            </thead>
                            <tbody>
                                {runs.map((r) => (
                                    <tr key={r.id} style={{
                                        borderTop: '1px solid #eef0f3',
                                        opacity: r.ativo ? 1 : 0.4,
                                    }}>
                                        <td style={{ padding: '8px 10px', color: 'var(--isa-text)' }}>
                                            <div style={{ fontWeight: 500 }}>{r.nome}</div>
                                            {r.observacoes && (
                                                <div style={{ fontSize: 11, color: 'var(--isa-text-muted)', marginTop: 2 }}>
                                                    {r.observacoes}
                                                </div>
                                            )}
                                        </td>
                                        <td style={{ padding: '8px 10px', color: 'var(--isa-text-muted)', fontVariantNumeric: 'tabular-nums', fontSize: 11 }}>
                                            {fmtDateBR(r.inicio)}
                                        </td>
                                        <td style={{ padding: '8px 10px', color: 'var(--isa-text)' }}>
                                            {r.sku_codigo || <span style={{ color: 'var(--isa-text-muted)' }}>—</span>}
                                        </td>
                                        <td style={{ padding: '8px 10px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--isa-text-muted)' }}>
                                            {r.formato_gramas !== null ? `${fmtNum(r.formato_gramas, 0)}g` : '—'}
                                        </td>
                                        <td style={{ padding: '8px 10px', textAlign: 'center' }}>
                                            <span style={{
                                                fontSize: 10, padding: '2px 6px', borderRadius: 8, fontWeight: 600,
                                                background: r.fonte === 'AUTO' ? '#dff4e3' : '#fbe9c8',
                                                color: r.fonte === 'AUTO' ? '#1f7a3b' : '#a06200',
                                            }}>
                                                {r.fonte}
                                            </span>
                                        </td>
                                        <td style={{ padding: '8px 10px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: '#a06200' }}>
                                            {r.score !== null ? r.score.toFixed(0) : '—'}
                                        </td>
                                        <td style={{ padding: '8px 10px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--isa-text-muted)' }}>
                                            {fmtNum(r.tph_medio)}
                                        </td>
                                        <td style={{ padding: '8px 10px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--isa-text-muted)' }}>
                                            {r.refugo_pct !== null ? `${fmtNum(r.refugo_pct, 1)}%` : '—'}
                                        </td>
                                        <td style={{ padding: '8px 10px', textAlign: 'center', color: 'var(--isa-text-muted)' }}>
                                            {r.n_variaveis}
                                        </td>
                                        <td style={{ padding: '8px 10px', textAlign: 'center' }}>
                                            {r.ativo && (
                                                <button
                                                    type="button" onClick={() => desativarRun(r.id)}
                                                    title="Desativar (exclui da receita)"
                                                    style={{
                                                        background: 'transparent', border: 'none',
                                                        cursor: 'pointer', color: '#b53a2b', padding: 2,
                                                    }}
                                                >
                                                    <Trash2 size={14} />
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {showModal && (
                <CapturaModal
                    linhaId={linhaId}
                    skuAtual={data.sku_atual}
                    formatoAtual={data.formato_atual}
                    onClose={() => setShowModal(false)}
                    onCaptured={fetchAll}
                />
            )}

            {showAplicarModal && (
                <AplicarReceitaModal
                    variaveis={data.variaveis}
                    filtro={filtro}
                    tolerancia={tolerancia}
                    linhaNome={data.linha_nome ?? linhaCodigo ?? ''}
                    submitting={aplicando}
                    onClose={() => !aplicando && setShowAplicarModal(false)}
                    onConfirm={executarAplicacao}
                />
            )}
        </div>
    );
}
