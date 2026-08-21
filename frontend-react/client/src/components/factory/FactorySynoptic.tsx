/**
 * Sinotico hierarquico fabrica -> localizacao -> linha -> equipamentos.
 *
 * Consome GET /api/fabrica/arvore/ (FactoryTreeView no backend Django).
 * Mantem layout responsivo via CSS Grid sem posicoes absolutas, para
 * suportar fabricas com qualquer numero de linhas/equipamentos sem
 * precisar editar coordenadas x/y.
 *
 * Em conformidade com ISA-101: tipografia neutra, sem sombras agressivas,
 * estado por semaforo (verde/amarelo/vermelho/cinza) sem dependencia de
 * piscar.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
// Flask-out Onda 1: /realtime/all migrado para Django.
import { DJANGO_API_URL } from '@/config/api';

interface EquipamentoNode {
    id: number;
    codigo: string;
    nome: string;
    tipo: string;
    ordem_na_linha: number;
    status: string;
}

interface LinhaNode {
    id: number;
    codigo: string;
    nome: string;
    area_nome?: string | null;
    meta_oee: number;
    equipamentos: EquipamentoNode[];
}

interface LocalizacaoNode {
    nome: string;
    linhas: LinhaNode[];
}

interface FabricaNode {
    fabrica: {
        id: number | null;
        codigo: string;
        nome: string;
        localizacao: string;
    };
    localizacoes: LocalizacaoNode[];
}

const statusColor = (status: string): string => {
    const s = (status || '').toUpperCase();
    if (s === 'ATIVO') return 'var(--isa-ok)';
    if (s === 'MANUTENCAO') return 'var(--isa-warn)';
    if (s === 'INATIVO') return 'var(--isa-text-muted)';
    return 'var(--isa-text-muted)';
};

// Real-time: mapeia estado_maquina vindo do Influx (codigo numerico ou
// string) -> cor do tile. ISA-101: verde/amarelo/vermelho/cinza, sem
// piscar agressivo.
const realtimeStateColor = (raw: unknown): string => {
    if (raw === null || raw === undefined || raw === '') return '';
    const txt = String(raw).toUpperCase();
    if (['1', 'PRODUZINDO', 'RUN', 'RUNNING', '11', 'PARTINDO', 'STARTUP'].includes(txt)) return 'var(--isa-ok)';
    if (['4', 'FALHA', 'PARADO/FALHA', 'BREAKDOWN', '0', 'PARADO', 'STOPPED'].includes(txt)) return 'var(--isa-bad)';
    if (['2', '3', '5', '7', '8', '9', '12', '13', 'MANUTENCAO', 'SETUP', 'AGUARDANDO'].includes(txt)) return 'var(--isa-warn)';
    return 'var(--isa-text-muted)';
};

interface RealtimeMap {
    [equipamentoCodigo: string]: { state?: unknown; oee?: number | null };
}

const FactorySynoptic: React.FC = () => {
    const navigate = useNavigate();
    const [tree, setTree] = useState<FabricaNode[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [realtime, setRealtime] = useState<RealtimeMap>({});

    useEffect(() => {
        let alive = true;
        const fetchTree = async () => {
            setLoading(true);
            setError(null);
            try {
                const res = await fetch(`${DJANGO_API_URL}/fabrica/arvore/`);
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                if (alive) setTree(Array.isArray(data) ? data : []);
            } catch (err: any) {
                if (alive) setError(err?.message || 'Falha ao carregar arvore da fabrica.');
            } finally {
                if (alive) setLoading(false);
            }
        };
        fetchTree();
        return () => { alive = false; };
    }, []);

    // Real-time: /realtime/all do Flask -> mapa equipamento->estado/oee.
    // Atualiza a cada 5s. Falha silenciosa: se Flask cair, tiles ficam
    // com cor cinza (status do cadastro Django).
    useEffect(() => {
        let alive = true;
        const fetchRealtime = async () => {
            try {
                const res = await fetch(`${DJANGO_API_URL}/realtime/all`);
                if (!res.ok) return;
                const data = await res.json();
                if (!alive) return;
                const map: RealtimeMap = {};
                for (const [code, eq] of Object.entries<any>(data || {})) {
                    const med = eq?.medicoes || {};
                    map[code] = {
                        state: med.estado_maquina ?? med.estado ?? med.status,
                        oee: typeof med.oee === 'number' ? med.oee : null,
                    };
                }
                setRealtime(map);
            } catch {
                // sem realtime: nao quebra a renderizacao
            }
        };
        fetchRealtime();
        const iv = setInterval(fetchRealtime, 5000);
        return () => { alive = false; clearInterval(iv); };
    }, []);

    if (loading) {
        return <div style={{ padding: 16, color: 'var(--isa-text-muted)' }}>Carregando hierarquia...</div>;
    }

    if (error) {
        return (
            <div style={{ padding: 16, color: 'var(--isa-bad)' }}>
                {error}
            </div>
        );
    }

    if (tree.length === 0) {
        return (
            <div style={{ padding: 16, color: 'var(--isa-text-muted)' }}>
                Nenhuma fábrica cadastrada.
            </div>
        );
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {tree.map(fabNode => (
                <div
                    key={fabNode.fabrica.codigo}
                    style={{
                        border: '1px solid var(--isa-border)',
                        borderRadius: 'var(--isa-radius)',
                        background: 'var(--isa-bg-panel)',
                        padding: 12,
                    }}
                >
                    <div style={{
                        fontSize: 14, fontWeight: 600, marginBottom: 8,
                        color: 'var(--isa-text)',
                        display: 'flex', alignItems: 'baseline', gap: 8,
                    }}>
                        <span>{fabNode.fabrica.codigo}</span>
                        <span style={{ color: 'var(--isa-text-muted)', fontWeight: 400 }}>
                            {fabNode.fabrica.nome}
                        </span>
                    </div>

                    {fabNode.localizacoes.map(loc => (
                        <div key={loc.nome} style={{ marginTop: 8 }}>
                            <div style={{
                                fontSize: 'var(--isa-fs-meta)',
                                color: 'var(--isa-text-muted)',
                                textTransform: 'uppercase',
                                letterSpacing: 0.5,
                                marginBottom: 4,
                            }}>
                                {loc.nome}
                            </div>

                            <div style={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                                gap: 8,
                            }}>
                                {loc.linhas.map(linha => (
                                    <div
                                        key={linha.codigo}
                                        onClick={() => navigate(`/linha/${linha.codigo}/detalhes`)}
                                        style={{
                                            border: '1px solid var(--isa-border)',
                                            borderRadius: 'var(--isa-radius)',
                                            padding: 8,
                                            background: 'var(--isa-bg)',
                                            cursor: 'pointer',
                                        }}
                                    >
                                        <div style={{
                                            fontSize: 'var(--isa-fs-default)',
                                            fontWeight: 600,
                                            marginBottom: 6,
                                            display: 'flex', justifyContent: 'space-between',
                                        }}>
                                            <span>{linha.codigo} · {linha.nome}</span>
                                            {linha.area_nome && (
                                                <span style={{ color: 'var(--isa-text-muted)', fontWeight: 400, fontSize: 'var(--isa-fs-meta)' }}>
                                                    {linha.area_nome}
                                                </span>
                                            )}
                                        </div>

                                        {linha.equipamentos.length === 0 ? (
                                            <div style={{ color: 'var(--isa-text-muted)', fontSize: 'var(--isa-fs-meta)' }}>
                                                Sem equipamentos cadastrados.
                                            </div>
                                        ) : (
                                            <div style={{
                                                display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center',
                                            }}>
                                                {linha.equipamentos.map((eq, idx) => {
                                                    // Cor: real-time tem prioridade sobre status do cadastro
                                                    const rt = realtime[eq.codigo];
                                                    const rtColor = realtimeStateColor(rt?.state);
                                                    const corBorda = rtColor || statusColor(eq.status);
                                                    const rtLabel = rt?.state !== undefined && rt?.state !== null
                                                        ? `estado=${rt.state}` : 'sem real-time';
                                                    return (
                                                        <React.Fragment key={eq.codigo}>
                                                            <div
                                                                title={`${eq.tipo} · cadastro=${eq.status} · ${rtLabel}${rt?.oee != null ? ` · OEE ${rt.oee.toFixed(0)}` : ''}`}
                                                                style={{
                                                                    border: `1px solid ${corBorda}`,
                                                                    borderLeftWidth: rtColor ? 3 : 1,
                                                                    background: 'var(--isa-bg-panel)',
                                                                    borderRadius: 4,
                                                                    padding: '2px 6px',
                                                                    fontSize: 'var(--isa-fs-meta)',
                                                                    color: 'var(--isa-text)',
                                                                    display: 'flex', flexDirection: 'column',
                                                                    minWidth: 64, lineHeight: 1.1,
                                                                }}
                                                            >
                                                                <span style={{ fontWeight: 600 }}>{eq.codigo}</span>
                                                                <span style={{ color: 'var(--isa-text-muted)' }}>
                                                                    {eq.tipo}
                                                                </span>
                                                                {rt?.oee != null && (
                                                                    <span style={{ color: corBorda, fontWeight: 600 }}>
                                                                        {rt.oee.toFixed(0)}%
                                                                    </span>
                                                                )}
                                                            </div>
                                                            {idx < linha.equipamentos.length - 1 && (
                                                                <span style={{ color: 'var(--isa-text-muted)' }}>→</span>
                                                            )}
                                                        </React.Fragment>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            ))}
        </div>
    );
};

export default FactorySynoptic;
