import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw, AlertTriangle } from 'lucide-react';

import Header from '../components/LineDeepView/Header';
import Progress from '../components/LineDeepView/Progress';
import KPIs from '../components/LineDeepView/KPIs';
import EquipmentCard from '../components/LineDeepView/EquipmentCard';
import MultiEquipmentTimeline from '../components/MultiEquipmentTimeline';
import Diagnostics from '../components/LineDeepView/Diagnostics';
import Upstream from '../components/LineDeepView/Upstream';
import Downstream from '../components/LineDeepView/Downstream';
import LossTreeCard from '../components/LossAnalysis/LossTreeCard';
import { LossWasteAnalysis } from '../components/LossAnalysis/LossWasteAnalysis';
import AnalyticsTab from '../components/LineDeepView/AnalyticsTab';

// Importar funções utilitárias
import {
    safeArray,
    safeNumber,
    safeString,
    isValidArray,
    extractValue
} from '../utils/dataValidation';
import {
    calculateProduction,
    createSafeProductionData
} from '../utils/productionCalculations';
import { DJANGO_API_URL, FASTAPI_V2_URL, FLASK_API_URL } from '@/config/api';
import { MOCK_LINE_OVERVIEW_STATUS, MOCK_LINE_KPIS, MOCK_LINE_OLE, MOCK_EQUIPMENT_DADOS, MOCK_DIAGNOSTICS_ALERTS } from '@/mocks/demoData';



interface EquipamentoConfig {
    id: number;
    nome: string;
    codigo: string;
    tipo: string;
    ordem_na_linha: number;
    velocidade_nominal?: number;
}

interface LinhaConfig {
    id: number;
    nome: string;
    codigo: string;
}

interface MedicoesCombinadas {
    velocidade_atual: number;
    estado: string;
    pecas_produzidas_equipamento: number;
    cuc: string;
    sku_codigo: string;
    descricao: string;
    ordem_producao: string;
    formato_gramas: number;
    planejado_op: number;
    produzido_op: number;
    produzido_turno: number;
    descarte_turno: number;
    refugo_turno: number;
    pecas_ruins_turno: number;
    diferenca_op: number;
    toneladas_op: number;
    oee: number;
    pecas_boas: number;
    pecas_ruins: number;
    timestamp: string;
}

interface EquipamentoCompleto extends EquipamentoConfig {
    medicoes?: MedicoesCombinadas;
    status: string;
    timestamp?: string;
    ultimaParada?: string;
}

interface FullEquipmentStatus {
    codigo: string;
    linha_id?: number;
    estado?: string | number;
    velocidade_atual?: number;
    oee?: number;
    status?: string;
    comunicacao_online?: boolean;
    ingested_at?: string | null;
    data_age_s?: number | null;
}

const LineDeepView: React.FC = () => {
    const { linhaId } = useParams<{ linhaId: string }>();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

    // State for all data sections
    const [lineStatus, setLineStatus] = useState<any>(null);
    const [oleData, setOleData] = useState<any>(null);
    const [kpisData, setKpisData] = useState<any>(null);

    // Detailed Equipment Data
    const [equipamentosDetalhados, setEquipamentosDetalhados] = useState<EquipamentoCompleto[]>([]);

    // Django Config State
    const [linhaConfig, setLinhaConfig] = useState<LinhaConfig | null>(null);
    const [equipamentosConfig, setEquipamentosConfig] = useState<EquipamentoConfig[]>([]);

    // New State for Consolidated Metrics and Diagnostics
    const [metricasConsolidadas, setMetricasConsolidadas] = useState<any>(null);
    const [diagnosticAlerts, setDiagnosticAlerts] = useState<string[]>([]);

    // Controle de fetch para evitar race conditions
    const isFetchingRef = useRef(false);

    // Tab navigation — ISA-101 layout
    const [activeTab, setActiveTab] = useState<'home' | 'analytics' | 'equipment' | 'losses'>('home');

    /**
     * Fetch de dados em tempo real de um equipamento com validação robusta
     */
    const fetchRealtimeEndpoint = async (path: string): Promise<Response | null> => {
        try {
            const fastApiResponse = await fetch(`${FASTAPI_V2_URL}${path}`);
            if (fastApiResponse.ok) return fastApiResponse;
        } catch (error) {
            console.warn(`FastAPI v2 indisponível para ${path}, usando Flask legado`, error);
        }

        try {
            // Flask-out completo: tudo agora vem do Django.
            const djangoResponse = await fetch(`${DJANGO_API_URL}${path}`);
            return djangoResponse.ok ? djangoResponse : null;
        } catch (error) {
            console.error(`Erro ao buscar endpoint legado ${path}:`, error);
            return null;
        }
    };

    const fetchLineEndpoint = async (path: string): Promise<any | null> => {
        try {
            const fastApiResponse = await fetch(`${FASTAPI_V2_URL}${path}`);
            if (fastApiResponse.ok) return await fastApiResponse.json();
        } catch (error) {
            console.warn(`FastAPI v2 indisponível para ${path}, usando Flask legado`, error);
        }

        try {
            // Flask-out completo: tudo agora vem do Django.
            const djangoResponse = await fetch(`${DJANGO_API_URL}${path}`);
            return djangoResponse.ok ? await djangoResponse.json() : null;
        } catch (error) {
            console.error(`Erro ao buscar endpoint legado ${path}:`, error);
            return null;
        }
    };

    const fetchFullEquipmentStatus = async (linhaNumericId: number): Promise<Record<string, FullEquipmentStatus>> => {
        try {
            const response = await fetch(
                `${DJANGO_API_URL}/full_equipment_status/?linha_id=${encodeURIComponent(linhaNumericId)}`
            );
            if (!response.ok) return {};

            const data = await response.json();
            return safeArray(data).reduce((acc: Record<string, FullEquipmentStatus>, item: FullEquipmentStatus) => {
                if (item.codigo && item.linha_id === linhaNumericId) acc[item.codigo] = item;
                return acc;
            }, {});
        } catch (error) {
            console.error('Erro ao buscar status completo dos equipamentos:', error);
            return {};
        }
    };

    const mergeStatusFallback = (
        tempoReal: Partial<EquipamentoCompleto> | null,
        _fallback?: FullEquipmentStatus,
    ): Partial<EquipamentoCompleto> | null => {
        // Evento/métrica SQL é histórico e não pode ressuscitar um estado OPC
        // vencido. Sem resposta realtime comprovadamente online, fica Offline.
        return tempoReal;
    };

    const fetchTempoReal = async (codigoEquipamento: string, linhaCodigo: string): Promise<Partial<EquipamentoCompleto> | null> => {
        if (!codigoEquipamento) return null;

        try {
            const [resOperacao, resEquipamento] = await Promise.allSettled([
                fetchRealtimeEndpoint(`/operacao/dados/${encodeURIComponent(codigoEquipamento)}?linha=${encodeURIComponent(linhaCodigo)}`),
                fetchRealtimeEndpoint(`/equipamento/dados/${encodeURIComponent(codigoEquipamento)}?linha=${encodeURIComponent(linhaCodigo)}`)
            ]);

            const respOp = resOperacao.status === 'fulfilled' ? resOperacao.value : null;
            const respEq = resEquipamento.status === 'fulfilled' ? resEquipamento.value : null;

            if (!respOp && !respEq) return null;

            const dadosOp = respOp ? await respOp.json() : {};
            const dadosEq = respEq ? await respEq.json() : {};
            const comunicacaoOnline = dadosEq.comunicacao_online === true;

            const medicoes: MedicoesCombinadas = {
                velocidade_atual: comunicacaoOnline ? safeNumber(dadosEq.velocidade_atual, 0) : 0,
                estado: comunicacaoOnline ? safeString(dadosEq.estado_atual, 'Desconhecido') : 'Offline',
                pecas_produzidas_equipamento: safeNumber(dadosEq.pecas_produzidas, 0),
                cuc: safeString(dadosOp.cuc, 'N/A'),
                sku_codigo: safeString(dadosOp.sku, 'N/A'),
                descricao: safeString(dadosOp.descricao, 'Produto Genérico'),
                ordem_producao: safeString(dadosOp.ordem_producao, 'N/A'),
                formato_gramas: safeNumber(dadosOp.formato_gramas, 0),
                planejado_op: safeNumber(dadosOp.planejado_op, 0),
                produzido_op: safeNumber(dadosOp.produzido_op, 0),
                produzido_turno: safeNumber(dadosOp.produzido_turno, 0),
                descarte_turno: safeNumber(dadosOp.descarte_turno, 0),
                refugo_turno: safeNumber(dadosOp.refugo_turno, 0),
                pecas_ruins_turno: safeNumber(dadosOp.pecas_ruins_turno ?? dadosOp.descarte_turno, 0),
                diferenca_op: safeNumber(dadosOp.diferenca_op, 0),
                toneladas_op: safeNumber(dadosOp.toneladas_op, 0),
                oee: comunicacaoOnline ? safeNumber(dadosOp.oee || dadosEq.oee_atual, 0) : 0,
                pecas_boas: safeNumber(dadosOp.pecas_boas, 0),
                pecas_ruins: safeNumber(dadosOp.pecas_ruins, 0),
                timestamp: safeString(dadosEq.ingested_at || dadosEq.timestamp, '')
            };

            return {
                medicoes,
                status: comunicacaoOnline ? safeString(dadosEq.estado_atual, 'Offline') : 'Offline',
                timestamp: dadosEq.timestamp
            };
        } catch (error) {
            console.error(`Erro ao buscar dados de ${codigoEquipamento}:`, error);
            return null;
        }
    };

    const fetchUltimaParada = async (equipamentoId: number): Promise<string> => {
        try {
            const response = await fetch(`${DJANGO_API_URL}/eventos-estado/?equipamento_id=${equipamentoId}&page_size=10`);
            if (!response.ok) return 'N/A';

            const data = await response.json();
            const eventos = safeArray(data.results || data);
            const parada = eventos.find((evento: any) => {
                const estado = safeString(evento.estado, '').toUpperCase();
                return estado && !['RUN', 'PRODUZINDO'].includes(estado);
            });
            if (!parada) return 'N/A';

            const inicio = parada.inicio ? new Date(parada.inicio).toLocaleString('pt-BR', {
                day: '2-digit',
                month: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
            }) : '';
            const estado = safeString(parada.estado_display || parada.estado, 'Parada');
            return inicio ? `${estado} - ${inicio}` : estado;
        } catch (error) {
            console.error(`Erro ao buscar ultima parada de ${codigoEquipamento}:`, error);
            return 'N/A';
        }
    };

    /**
     * Busca configuração de linha com estratégia robusta de resolução
     * Prioridade: código exato > busca por nome > primeiro resultado
     */
    const fetchLinhaConfig = async (identifier: string): Promise<LinhaConfig | null> => {
        if (!identifier) return null;

        try {
            // Tentativa 1: Buscar por código exato
            let response = await fetch(`${DJANGO_API_URL}/linhas/?compact=1&codigo=${encodeURIComponent(identifier)}`);
            let data = await response.json();
            let results = safeArray(data.results || data);

            // Se encontrou resultado exato por código
            if (results.length > 0) {
                const exactMatch = results.find((r: any) => r.codigo === identifier);
                if (exactMatch) return exactMatch;
            }

            // Tentativa 2: Buscar por nome/search
            response = await fetch(`${DJANGO_API_URL}/linhas/?compact=1&search=${encodeURIComponent(identifier)}`);
            data = await response.json();
            results = safeArray(data.results || data);

            if (results.length > 0) {
                // Tentar match exato por nome
                const exactNameMatch = results.find((r: any) =>
                    r.nome === identifier ||
                    r.nome.toLowerCase() === identifier.toLowerCase() ||
                    r.codigo === identifier
                );

                if (exactNameMatch) return exactNameMatch;

                // Fallback: retornar primeiro resultado
                console.warn(`Match exato não encontrado para "${identifier}", usando primeiro resultado`);
                return results[0];
            }

            return null;
        } catch (error) {
            console.error('Erro ao buscar configuração de linha:', error);
            return null;
        }
    };

    /**
     * Função principal de fetch com controle de concorrência e tratamento robusto
     */
    const fetchData = async () => {
        // Prevenir múltiplas requisições simultâneas
        if (isFetchingRef.current) {
            console.log("Fetch já em andamento, pulando...");
            return;
        }

        isFetchingRef.current = true;

        try {
            setLoading(true);

            // 1. Buscar configuração da linha com estratégia robusta
            const lConfig = await fetchLinhaConfig(linhaId || '');

            if (!lConfig) {
                console.error(`Não foi possível encontrar configuração para linha: ${linhaId}`);
                setLoading(false);
                isFetchingRef.current = false;
                return;
            }

            setLinhaConfig(lConfig);
            const linhaIdNumeric = lConfig.id;
            const linhaIdentifier = lConfig.codigo; // SEMPRE usar código para Flask API

            // 2. Buscar configuração de equipamentos
            let currentEquipamentosConfig: EquipamentoConfig[] = [];
            try {
                const resEquipamentos = await fetch(`${DJANGO_API_URL}/equipamentos/?compact=1&linha=${linhaIdNumeric}`);
                if (resEquipamentos.ok) {
                    const dataEq = await resEquipamentos.json();
                    currentEquipamentosConfig = safeArray(dataEq.results || dataEq);
                }
            } catch (error) {
                console.error('Erro ao buscar equipamentos:', error);
            }
            // Django não tem equipamentos cadastrados para esta linha.
            // Tentar resolver via InfluxDB: Flask /linha/{id}/status retorna os
            // equipamentos reais pelo tag "equipment" — evita códigos fictícios
            // que jamais são encontrados no InfluxDB (raiz do dado mock "Produzindo").
            if (currentEquipamentosConfig.length === 0) {
                try {
                    const resInflux = await fetch(
                        // Flask-out Onda 2: /linha/<>/status migrado para Django.
                        `${DJANGO_API_URL}/linha/${encodeURIComponent(linhaIdentifier)}/status`
                    );
                    if (resInflux.ok) {
                        const influxData = await resInflux.json();
                        const eqs: any[] = safeArray(influxData.equipamentos);
                        if (eqs.length > 0) {
                            currentEquipamentosConfig = eqs.map((eq: any, idx: number) => ({
                                id:              idx + 1,
                                codigo:          eq.nome,   // "nome" aqui é o tag equipment do InfluxDB
                                nome:            eq.nome,
                                tipo:            'equipamento',
                                ordem_na_linha:  idx + 1,
                                velocidade_nominal: 120,
                            }));
                            console.info(
                                `[LineDeepView] Django sem equipamentos para ${linhaIdentifier}. ` +
                                `Usando ${eqs.length} equipamento(s) reais do InfluxDB.`
                            );
                        }
                    }
                } catch (e) {
                    console.warn('[LineDeepView] Falha ao buscar equipamentos do InfluxDB:', e);
                }
            }
            setEquipamentosConfig(currentEquipamentosConfig);

            // 3. Buscar dados em tempo real da linha (FastAPI v2, com fallback legado)
            const fetchPromises = [
                fetchLineEndpoint(`/linha/${encodeURIComponent(linhaIdentifier)}/overview-status`),
                fetchLineEndpoint(`/linha/${encodeURIComponent(linhaIdentifier)}/ole-realtime`),
                fetchLineEndpoint(`/linha/${encodeURIComponent(linhaIdentifier)}/kpis`),
                fetch(`${DJANGO_API_URL}/metricas_fabrica_consolidadas/`)
                    .then(res => res.ok ? res.json() : null)
                    .catch(() => null)
            ];

            const [statusData, oleDataRaw, kpisDataRaw, consolidadasData] = await Promise.all(fetchPromises);

            // Sem fallback de mock — se backend retornar null/erro, mostra vazio
            setLineStatus(statusData || null);
            setOleData(oleDataRaw || null);
            setKpisData(kpisDataRaw || null);

            // Buscar métricas consolidadas da linha específica
            let metricasLinha = null;
            if (consolidadasData && isValidArray(consolidadasData)) {
                metricasLinha = consolidadasData.find((m: any) => m.linha_id === linhaIdNumeric);
            }
            setMetricasConsolidadas(metricasLinha);

            // 4. Buscar dados detalhados de cada equipamento + diagnósticos
            const allAlerts: string[] = [];
            if (currentEquipamentosConfig.length > 0) {
                const fullStatusByCode = await fetchFullEquipmentStatus(linhaIdNumeric);
                const promises = currentEquipamentosConfig.map(async (eq) => {
                    // Buscar dados em tempo real
                    const dadosReais = await fetchTempoReal(eq.codigo, linhaIdentifier);
                    const dadosComFallback = mergeStatusFallback(dadosReais, fullStatusByCode[eq.codigo]);
                    const ultimaParada = await fetchUltimaParada(eq.id);

                    // Buscar alertas de diagnóstico
                    try {
                        // Flask-out Onda 5: /diagnostics/alerts/<> migrado para Django.
                        const resAlerts = await fetch(`${DJANGO_API_URL}/diagnostics/alerts/${eq.codigo}`);
                        if (resAlerts.ok) {
                            const alertsData = await resAlerts.json();
                            if (alertsData.alerts && Array.isArray(alertsData.alerts)) {
                                alertsData.alerts.forEach((a: any) => {
                                    allAlerts.push(`${eq.nome}: ${a.message || 'Alerta sem mensagem'}`);
                                });
                            }
                        }
                    } catch (error) {
                        console.error(`Erro ao buscar alertas de ${eq.codigo}:`, error);
                        MOCK_DIAGNOSTICS_ALERTS.forEach(a => allAlerts.push(`${eq.nome}: ${a.descricao}`));
                    }

                    const temDadosReais = dadosComFallback != null && Object.keys(dadosComFallback).length > 0;
                    return {
                        ...eq,
                        ...(temDadosReais ? dadosComFallback : {}),
                        ultimaParada,
                    } as EquipamentoCompleto;
                });

                const equipamentosDetalhadosResult = await Promise.all(promises);
                // Ordenar por ordem na linha
                equipamentosDetalhadosResult.sort((a, b) => (a.ordem_na_linha || 0) - (b.ordem_na_linha || 0));
                setEquipamentosDetalhados(equipamentosDetalhadosResult);
            }

            setDiagnosticAlerts(allAlerts);
            setLastUpdate(new Date());

        } catch (error) {
            console.error("Erro ao buscar detalhes da linha:", error);
        } finally {
            setLoading(false);
            isFetchingRef.current = false;
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 5000); // 5s refresh
        return () => {
            clearInterval(interval);
            isFetchingRef.current = false;
        };
    }, [linhaId]);

    // Loading state
    if (loading && !lineStatus && equipamentosDetalhados.length === 0) {
        return (
            <div className="p-10 text-center">
                <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4 text-gray-500" />
                <p className="text-gray-600">Carregando Detalhes da Linha...</p>
            </div>
        );
    }

    // Encontrar equipamento líder
    const eqLider = equipamentosDetalhados.find(eq =>
        eq.medicoes?.ordem_producao &&
        eq.medicoes?.ordem_producao !== 'N/A' &&
        eq.medicoes?.ordem_producao.trim() !== ''
    ) || equipamentosDetalhados[0];

    const dadosProducao = eqLider?.medicoes;

    // Criar dados de produção seguros para cálculos
    const productionData = createSafeProductionData({
        producaoReal: oleData?.producao_real,
        metaTotal: oleData?.meta_turno || oleData?.producao_planejada_total,
        oleAtual: oleData?.ole,
        tempoDecorrido: oleData?.tempo_decorrido,
        tempoTotalTurno: oleData?.tempo_total_turno,
        taxaInstantanea: oleData?.taxa_instantanea || metricasConsolidadas?.vazao_real_ton_hora,
        projecaoBackend: oleData?.projecao,
        ritmoNecessarioBackend: oleData?.ritmo_necessario
    });

    // Calcular métricas de produção
    const calculations = calculateProduction(productionData);

    // Preparar dados para componentes
    const currentStatus = safeString(lineStatus?.status, 'Carregando...');
    const isSystemOffline = currentStatus === 'Sem Comunicação' || currentStatus === 'Offline';

    const headerProps = {
        linha: linhaConfig?.nome || linhaId || 'Linha Desconhecida',
        op: extractValue(oleData?.op, dadosProducao?.ordem_producao) || 'N/A',
        sku: extractValue(oleData?.sku, dadosProducao?.sku_codigo) || 'N/A',
        produto: extractValue(oleData?.descricao, dadosProducao?.descricao) || 'Produto Genérico',
        cuc: extractValue(oleData?.cuc, dadosProducao?.cuc) || 'N/A',
        formato: safeNumber(extractValue(oleData?.formato, dadosProducao?.formato_gramas), 0),
        equipamentosOnline: safeNumber(oleData?.equipamentos_online, 0),
        totalEquipamentos: safeNumber(oleData?.equipamentos_total, equipamentosConfig.length),
        vazao: calculations.vazaoCalculada,
        ole: productionData.oleAtual,
        status: currentStatus
    };

    // Estilos ISA-101 — agora consomem os tokens globais de styles/isa101.css.
    // Centralizado num objeto `S` pra evitar criar mais um .css avulso.
    const S = {
      page:    { minHeight: '100vh', background: 'var(--isa-bg)', fontFamily: 'var(--isa-font)', color: 'var(--isa-text)' } as React.CSSProperties,
      topbar:  { padding: '10px 20px', background: 'var(--isa-bg-panel)', borderBottom: '1px solid var(--isa-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' } as React.CSSProperties,
      crumb:   { fontSize: 'var(--isa-fs-body)', color: 'var(--isa-text-muted)' } as React.CSSProperties,
      crumbB:  { color: 'var(--isa-text)', fontWeight: 500 } as React.CSSProperties,
      topRight:{ display: 'flex', gap: 10, alignItems: 'center' } as React.CSSProperties,
      shift:   { fontSize: 'var(--isa-fs-meta)', color: 'var(--isa-text-muted)' } as React.CSSProperties,
      btnGhost:{ padding: '5px 10px', border: '1px solid var(--isa-border)', borderRadius: 'var(--isa-radius)', cursor: 'pointer', background: 'var(--isa-bg-panel)', color: 'var(--isa-text)', fontSize: 'var(--isa-fs-body)', display: 'flex', alignItems: 'center', gap: 5 } as React.CSSProperties,
      tabBar:  { display: 'flex', borderBottom: '1px solid var(--isa-border)', background: 'var(--isa-bg-panel)', padding: '0 20px' } as React.CSSProperties,
      tab:     (active: boolean) => ({
        padding: '10px 16px', border: 'none', cursor: 'pointer', fontSize: 'var(--isa-fs-default)', background: 'transparent',
        borderBottom: active ? '2px solid var(--isa-accent)' : '2px solid transparent',
        color: active ? 'var(--isa-text)' : 'var(--isa-text-muted)', fontWeight: active ? 500 : 400,
      }) as React.CSSProperties,
      content: { padding: '20px', overflow: 'auto' } as React.CSSProperties,
      banner:  { background: 'var(--isa-bad-bg)', borderLeft: '4px solid var(--isa-bad)', padding: '12px 16px', marginBottom: 16, borderRadius: '0 6px 6px 0', display: 'flex', gap: 12, alignItems: 'flex-start' } as React.CSSProperties,
    };

    const tabs = [
      { id: 'home',      label: 'Home' },
      { id: 'analytics', label: 'Analytics' },
      { id: 'equipment', label: 'Equipamento' },
      { id: 'losses',    label: 'Árvore de Perdas' },
    ] as const;

    return (
        <div className="isa-root" style={S.page}>
            {/* ---- Topbar ISA-101 ---- */}
            <div style={S.topbar}>
                <div style={S.crumb}>
                    Fábrica Norte&nbsp;/&nbsp;
                    <b style={S.crumbB}>{linhaConfig?.nome || linhaId}</b>
                </div>
                <div style={S.topRight}>
                    <span style={S.shift}>
                        Atualizado {lastUpdate.toLocaleTimeString('pt-BR')}
                    </span>
                    <button style={S.btnGhost} onClick={fetchData} title="Atualizar">
                        <RefreshCw size={13} />
                        Refresh
                    </button>
                    <button style={S.btnGhost} onClick={() => navigate('/')} title="Voltar">
                        <ArrowLeft size={13} />
                        Voltar
                    </button>
                </div>
            </div>

            {/* ---- Tabs ISA-101 ---- */}
            <div style={S.tabBar}>
                {tabs.map(t => (
                    <button key={t.id} style={S.tab(activeTab === t.id)} onClick={() => setActiveTab(t.id)}>
                        {t.label}
                    </button>
                ))}
            </div>

            {/* ---- Conteúdo ---- */}
            <div style={S.content}>
                {/* Alert banner offline */}
                {isSystemOffline && (
                    <div style={S.banner}>
                        <AlertTriangle size={18} color="#b53a2b" style={{ flexShrink: 0, marginTop: 1 }} />
                        <div>
                            <div style={{ fontWeight: 600, color: '#b53a2b', fontSize: 13 }}>Sistema Offline ou Sem Comunicação</div>
                            <div style={{ fontSize: 12, color: '#657384', marginTop: 2 }}>
                                Não estamos recebendo dados do coletor. Verifique a conexão de rede.
                            </div>
                        </div>
                    </div>
                )}

                {/* === TAB: HOME === */}
                {activeTab === 'home' && (
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                        <div className="lg:col-span-8 space-y-6">
                            <Header {...headerProps} />
                            <Progress
                                producaoReal={productionData.producaoReal}
                                producaoEsperada={safeNumber(oleData?.producao_esperada || oleData?.producao_planejada_ate_agora, 0)}
                                projecao={calculations.projecao}
                                metaTurno={productionData.metaTotal}
                                tempoDecorridoPerc={calculations.tempoDecorridoPerc}
                            />
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {equipamentosDetalhados.map((eq, idx) => (
                                    <EquipmentCard
                                        key={idx}
                                        nome={eq.nome}
                                        funcao={eq.tipo}
                                        estado={eq.medicoes?.estado ?? 'Desconhecido'}
                                        oee={safeNumber(eq.medicoes?.oee, 0)}
                                        velocidadeAtual={safeNumber(eq.medicoes?.velocidade_atual, 0)}
                                        velocidadeNominal={safeNumber(eq.velocidade_nominal, 100)}
                                        boas={safeNumber(eq.medicoes?.produzido_turno, 0)}
                                        ruins={safeNumber(eq.medicoes?.pecas_ruins_turno, 0)}
                                        ultimaParada={safeString(eq.ultimaParada, 'N/A')}
                                    />
                                ))}
                            </div>
                            {linhaConfig && (
                                <MultiEquipmentTimeline
                                    linhaId={linhaConfig.id}
                                    linhaNome={linhaConfig.nome}
                                    equipamentos={equipamentosConfig}
                                />
                            )}
                        </div>

                        <div className="lg:col-span-4 space-y-6">
                            <KPIs
                                availability={safeNumber(kpisData?.kpis?.disponibilidade, 0)}
                                performance={safeNumber(kpisData?.kpis?.performance, 0)}
                                quality={safeNumber(kpisData?.kpis?.quality ?? kpisData?.kpis?.qualidade, 0)}
                                bottleneck={{
                                    name: safeString(kpisData?.gargalo?.nome, 'N/A'),
                                    oee: safeNumber(kpisData?.gargalo?.oee, 0)
                                }}
                                ritmoAtual={calculations.vazaoCalculada}
                                ritmoNecessario={calculations.ritmoNecessario}
                                desvioProjetado={calculations.desvioProjetado}
                                equipamentos={equipamentosConfig}
                            />
                            <div className="bg-white rounded-lg border border-gray-200 p-4">
                                <div className="flex justify-between items-baseline mb-3">
                                    <h3 className="text-sm font-semibold text-gray-700">Descarte da Linha</h3>
                                    <a
                                        href={`/mis-core/descartes?linhas=${encodeURIComponent(linhaConfig?.codigo || '')}`}
                                        style={{ fontSize: 11, color: 'var(--isa-accent)', textDecoration: 'none' }}
                                        title="Abre o dashboard de descartes com filtros do período"
                                    >
                                        Análise detalhada →
                                    </a>
                                </div>
                                <div className="grid grid-cols-2 gap-3">
                                    <div style={{ background: '#f4dad6', padding: '10px 12px', borderRadius: 6 }}>
                                        <div style={{ fontSize: 10, color: '#b53a2b', textTransform: 'uppercase', fontWeight: 600 }}>Total (Tons)</div>
                                        <div style={{ fontSize: 18, fontWeight: 700, color: '#b53a2b' }}>
                                            {(equipamentosDetalhados.reduce((acc, eq) =>
                                                acc + (safeNumber(eq.medicoes?.pecas_ruins_turno, 0) * safeNumber(eq.medicoes?.formato_gramas, 0) / 1000000), 0
                                            )).toFixed(3)} t
                                        </div>
                                    </div>
                                    <div style={{ background: '#f4dad6', padding: '10px 12px', borderRadius: 6 }}>
                                        <div style={{ fontSize: 10, color: '#b53a2b', textTransform: 'uppercase', fontWeight: 600 }}>Percentual</div>
                                        <div style={{ fontSize: 18, fontWeight: 700, color: '#b53a2b' }}>
                                            {(() => {
                                                let totalWasteTons = 0;
                                                equipamentosDetalhados.forEach(eq => {
                                                    const fmt = safeNumber(eq.medicoes?.formato_gramas, 0);
                                                    const ruins = safeNumber(eq.medicoes?.pecas_ruins_turno, 0);
                                                    if (fmt > 0) totalWasteTons += (ruins * fmt) / 1000000;
                                                });
                                                return productionData.producaoReal > 0
                                                    ? ((totalWasteTons / productionData.producaoReal) * 100).toFixed(2)
                                                    : '0.00';
                                            })()}%
                                        </div>
                                    </div>
                                </div>
                                <div style={{ fontSize: 10, color: 'var(--isa-text-muted)', marginTop: 8, lineHeight: 1.4 }}>
                                    ⓘ Snapshot do turno corrente (último valor de <code>pecas_ruins_turno</code>).
                                    A tela <a href="/mis-core/descartes" style={{ color: 'var(--isa-accent)' }}>/descartes</a> usa
                                    janela configurável e <code>refugo_turno_acumulado</code> com delta reset-tolerante —
                                    pode divergir deste card. Padronização total no PR-C do Flask-out.
                                </div>
                            </div>
                            <Diagnostics alerts={diagnosticAlerts} />
                            <Upstream />
                            <Downstream />
                        </div>
                    </div>
                )}

                {/* === TAB: ANALYTICS === */}
                {activeTab === 'analytics' && (
                    <AnalyticsTab linhaId={linhaId} linhaNome={linhaConfig?.nome} equipamentos={equipamentosConfig} />
                )}

                {/* === TAB: EQUIPAMENTOS === */}
                {activeTab === 'equipment' && (
                    <div className="space-y-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                            {equipamentosDetalhados.map((eq, idx) => {
                                const estado = eq.medicoes?.estado || 'N/A';
                                const stateBg = estado === 'Produzindo' ? '#e3efe7' : estado === 'Parado' ? '#f4dad6' : '#e9ecef';
                                const stateColor = estado === 'Produzindo' ? '#2d8659' : estado === 'Parado' ? '#b53a2b' : '#657384';
                                return (
                                    <div key={idx} style={{ background: '#ffffff', border: '1px solid #d7dbe0', borderRadius: 6, padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
                                        <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
                                            <div style={{ width: 44, height: 44, borderRadius: 6, background: '#3f5b7c', color: '#fff', display: 'grid', placeItems: 'center', fontWeight: 700, fontSize: 16, flexShrink: 0 }}>
                                                {(eq.nome || 'E').charAt(0)}
                                            </div>
                                            <div style={{ flex: 1 }}>
                                                <div style={{ fontWeight: 600, fontSize: 14, color: '#2c3138' }}>{eq.nome}</div>
                                                <div style={{ fontSize: 11, color: '#657384' }}>{eq.tipo} · {eq.codigo}</div>
                                            </div>
                                            <span style={{ padding: '4px 10px', borderRadius: 5, fontSize: 11, fontWeight: 600, textTransform: 'uppercase', background: stateBg, color: stateColor }}>
                                                {estado}
                                            </span>
                                        </div>
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                                            {[
                                                { l: 'OEE', v: `${safeNumber(eq.medicoes?.oee, 0).toFixed(1)}%` },
                                                { l: 'Velocidade', v: `${safeNumber(eq.medicoes?.velocidade_atual, 0)} u/min` },
                                                { l: 'Peças Boas', v: safeNumber(eq.medicoes?.produzido_turno, 0).toLocaleString() },
                                                { l: 'Descartes', v: safeNumber(eq.medicoes?.pecas_ruins_turno, 0).toLocaleString() },
                                            ].map(kpi => (
                                                <div key={kpi.l} style={{ background: '#f4f5f7', padding: '8px 10px', borderRadius: 5 }}>
                                                    <div style={{ fontSize: 10, color: '#657384', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{kpi.l}</div>
                                                    <div style={{ fontSize: 17, fontWeight: 600, color: '#2c3138', fontVariantNumeric: 'tabular-nums' }}>{kpi.v}</div>
                                                </div>
                                            ))}
                                        </div>
                                        <button
                                            onClick={() => navigate(`/equipamento/${eq.id || eq.codigo}`)}
                                            style={{ width: '100%', padding: '7px 0', border: '1px solid #d7dbe0', borderRadius: 5, background: '#f4f5f7', color: '#3f5b7c', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}
                                        >
                                            Ver Detalhes →
                                        </button>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* === TAB: ÁRVORE DE PERDAS === */}
                {activeTab === 'losses' && linhaConfig && (
                    <div className="space-y-6">
                        <LossTreeCard linhaId={linhaConfig.id} djangoUrl={DJANGO_API_URL} />
                        <LossWasteAnalysis lineId={String(linhaConfig.id)} />
                    </div>
                )}
                {activeTab === 'losses' && !linhaConfig && (
                    <div style={{ padding: 40, textAlign: 'center', color: '#657384' }}>
                        Carregando configuração da linha…
                    </div>
                )}
            </div>
        </div>
    );
};

export default LineDeepView;
