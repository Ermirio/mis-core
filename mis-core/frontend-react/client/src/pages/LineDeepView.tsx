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

const FLASK_API_URL = import.meta.env.VITE_FLASK_API_URL || 'http://localhost:5000/api';
const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || 'http://localhost:8000/api';

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

    /**
     * Fetch de dados em tempo real de um equipamento com validação robusta
     */
    const fetchTempoReal = async (codigoEquipamento: string): Promise<Partial<EquipamentoCompleto> | null> => {
        if (!codigoEquipamento) return null;

        try {
            const [resOperacao, resEquipamento] = await Promise.allSettled([
                fetch(`${FLASK_API_URL}/operacao/dados/${codigoEquipamento}`),
                fetch(`${FLASK_API_URL}/equipamento/dados/${codigoEquipamento}`)
            ]);

            // Verificar se ambas as requisições foram bem-sucedidas
            if (resOperacao.status !== 'fulfilled' || resEquipamento.status !== 'fulfilled') {
                return null;
            }

            const [respOp, respEq] = [resOperacao.value, resEquipamento.value];

            if (!respOp.ok || !respEq.ok) return null;

            const dadosOp = await respOp.json();
            const dadosEq = await respEq.json();

            const medicoes: MedicoesCombinadas = {
                velocidade_atual: safeNumber(dadosEq.velocidade_atual, 0),
                estado: safeString(dadosEq.estado_atual, 'Desconhecido'),
                pecas_produzidas_equipamento: safeNumber(dadosEq.pecas_produzidas, 0),
                cuc: safeString(dadosOp.cuc, 'N/A'),
                sku_codigo: safeString(dadosOp.sku, 'N/A'),
                descricao: safeString(dadosOp.descricao, 'Produto Genérico'),
                ordem_producao: safeString(dadosOp.ordem_producao, 'N/A'),
                formato_gramas: safeNumber(dadosOp.formato_gramas, 0),
                planejado_op: safeNumber(dadosOp.planejado_op, 0),
                produzido_op: safeNumber(dadosOp.produzido_op, 0),
                diferenca_op: safeNumber(dadosOp.diferenca_op, 0),
                toneladas_op: safeNumber(dadosOp.toneladas_op, 0),
                oee: safeNumber(dadosOp.oee || dadosEq.oee_atual, 0),
                pecas_boas: safeNumber(dadosOp.pecas_boas, 0),
                pecas_ruins: safeNumber(dadosOp.pecas_ruins, 0),
                timestamp: safeString(dadosEq.timestamp, new Date().toISOString())
            };

            return {
                medicoes,
                status: safeString(dadosEq.estado_atual, 'Offline'),
                timestamp: dadosEq.timestamp
            };
        } catch (error) {
            console.error(`Erro ao buscar dados de ${codigoEquipamento}:`, error);
            return null;
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
            let response = await fetch(`${DJANGO_API_URL}/linhas/?codigo=${encodeURIComponent(identifier)}`);
            let data = await response.json();
            let results = safeArray(data.results || data);

            // Se encontrou resultado exato por código
            if (results.length > 0) {
                const exactMatch = results.find((r: any) => r.codigo === identifier);
                if (exactMatch) return exactMatch;
            }

            // Tentativa 2: Buscar por nome/search
            response = await fetch(`${DJANGO_API_URL}/linhas/?search=${encodeURIComponent(identifier)}`);
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

            console.error(`Linha "${identifier}" não encontrada`);
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
                const resEquipamentos = await fetch(`${DJANGO_API_URL}/equipamentos/?linha=${linhaIdNumeric}`);
                if (resEquipamentos.ok) {
                    const dataEq = await resEquipamentos.json();
                    currentEquipamentosConfig = safeArray(dataEq.results || dataEq);
                    setEquipamentosConfig(currentEquipamentosConfig);
                }
            } catch (error) {
                console.error('Erro ao buscar equipamentos:', error);
            }

            // 3. Buscar dados em tempo real da linha (Flask) - com tratamento individual
            const fetchPromises = [
                fetch(`${FLASK_API_URL}/linha/${encodeURIComponent(linhaIdentifier)}/overview-status`)
                    .then(res => res.ok ? res.json() : null)
                    .catch(() => null),
                fetch(`${FLASK_API_URL}/linha/${encodeURIComponent(linhaIdentifier)}/ole-realtime`)
                    .then(res => res.ok ? res.json() : null)
                    .catch(() => null),
                fetch(`${FLASK_API_URL}/linha/${encodeURIComponent(linhaIdentifier)}/kpis`)
                    .then(res => res.ok ? res.json() : null)
                    .catch(() => null),
                fetch(`${DJANGO_API_URL}/metricas_fabrica_consolidadas/`)
                    .then(res => res.ok ? res.json() : null)
                    .catch(() => null)
            ];

            const [statusData, oleDataRaw, kpisDataRaw, consolidadasData] = await Promise.all(fetchPromises);

            // Atualizar estados com dados válidos
            if (statusData) setLineStatus(statusData);
            if (oleDataRaw) setOleData(oleDataRaw);
            if (kpisDataRaw) setKpisData(kpisDataRaw);

            // Buscar métricas consolidadas da linha específica
            let metricasLinha = null;
            if (consolidadasData && isValidArray(consolidadasData)) {
                metricasLinha = consolidadasData.find((m: any) => m.linha_id === linhaIdNumeric);
            }
            setMetricasConsolidadas(metricasLinha);

            // 4. Buscar dados detalhados de cada equipamento + diagnósticos
            const allAlerts: string[] = [];
            if (currentEquipamentosConfig.length > 0) {
                const promises = currentEquipamentosConfig.map(async (eq) => {
                    // Buscar dados em tempo real
                    const dadosReais = await fetchTempoReal(eq.codigo);

                    // Buscar alertas de diagnóstico
                    try {
                        const resAlerts = await fetch(`${FLASK_API_URL}/diagnostics/alerts/${eq.codigo}`);
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
                    }

                    return {
                        ...eq,
                        ...dadosReais
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

    return (
        <div className="min-h-screen bg-gray-50 p-6">
            {/* ALERT BANNER if Offline */}
            {isSystemOffline && (
                <div className="bg-red-50 border-l-4 border-red-500 p-4 mb-6 rounded shadow-sm flex items-start gap-4">
                    <AlertTriangle className="w-6 h-6 text-red-500 flex-shrink-0" />
                    <div>
                        <h3 className="font-bold text-red-700">Sistema Offline ou Sem Comunicação</h3>
                        <p className="text-sm text-red-600 mt-1">
                            Não estamos recebendo dados do coletor há mais de 30 segundos.
                            Verifique a conexão de rede ou se o serviço do coletor está rodando.
                        </p>
                    </div>
                </div>
            )}

            {/* Top Bar */}
            <div className="flex items-center justify-between mb-6">
                <button
                    onClick={() => navigate('/')}
                    className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition"
                >
                    <ArrowLeft className="w-5 h-5" />
                    Voltar para Visão Geral
                </button>
                <div className="text-sm text-gray-500 flex items-center gap-2">
                    Última atualização: {lastUpdate.toLocaleTimeString()}
                    <button onClick={fetchData} className="p-1 hover:bg-gray-200 rounded">
                        <RefreshCw className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

                {/* Left Column (Main Info) - Span 8 */}
                <div className="lg:col-span-8 space-y-6">
                    <Header {...headerProps} />

                    <Progress
                        producaoReal={productionData.producaoReal}
                        producaoEsperada={safeNumber(oleData?.producao_esperada || oleData?.producao_planejada_ate_agora, 0)}
                        projecao={calculations.projecao}
                        metaTurno={productionData.metaTotal}
                        tempoDecorridoPerc={calculations.tempoDecorridoPerc}
                    />

                    {/* Equipment Grid */}
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
                                boas={safeNumber(eq.medicoes?.pecas_boas, 0)}
                                ruins={safeNumber(eq.medicoes?.pecas_ruins, 0)}
                                ultimaParada="N/A"
                            />
                        ))}
                    </div>

                    {/* Timeline Section */}
                    {linhaConfig && (
                        <>
                            <MultiEquipmentTimeline
                                linhaId={linhaConfig.id}
                                linhaNome={linhaConfig.nome}
                                equipamentos={equipamentosConfig}
                            />

                            <LossTreeCard
                                linhaId={linhaConfig.id}
                                djangoUrl={DJANGO_API_URL}
                            />
                            <LossWasteAnalysis
                                lineId={String(linhaConfig.id)}
                            />
                        </>
                    )}
                </div>

                {/* Right Column (KPIs & Details) - Span 4 */}
                <div className="lg:col-span-4 space-y-6">
                    <KPIs
                        availability={safeNumber(kpisData?.kpis?.disponibilidade, 0)}
                        performance={safeNumber(kpisData?.kpis?.performance, 0)}
                        quality={safeNumber(kpisData?.kpis?.qualidade, 0)}
                        bottleneck={{
                            name: safeString(kpisData?.gargalo?.nome, 'N/A'),
                            oee: safeNumber(kpisData?.gargalo?.oee, 0)
                        }}
                        ritmoAtual={calculations.vazaoCalculada}
                        ritmoNecessario={calculations.ritmoNecessario}
                        desvioProjetado={calculations.desvioProjetado}
                        equipamentos={equipamentosConfig}
                    />

                    <Diagnostics alerts={diagnosticAlerts} />

                    <Upstream />
                    <Downstream />
                </div>
            </div>
        </div>
    );
};

export default LineDeepView;
