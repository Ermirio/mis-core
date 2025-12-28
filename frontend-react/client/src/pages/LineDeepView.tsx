import React, { useState, useEffect } from 'react';
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

    const fetchTempoReal = async (codigoEquipamento: string): Promise<Partial<EquipamentoCompleto> | null> => {
        try {
            const [resOperacao, resEquipamento] = await Promise.all([
                fetch(`${FLASK_API_URL}/operacao/dados/${codigoEquipamento}`),
                fetch(`${FLASK_API_URL}/equipamento/dados/${codigoEquipamento}`)
            ]);

            if (!resOperacao.ok || !resEquipamento.ok) return null;

            const dadosOp = await resOperacao.json();
            const dadosEq = await resEquipamento.json();

            const medicoes: MedicoesCombinadas = {
                velocidade_atual: dadosEq.velocidade_atual,
                estado: dadosEq.estado_atual,
                pecas_produzidas_equipamento: dadosEq.pecas_produzidas,
                cuc: dadosOp.cuc,
                sku_codigo: dadosOp.sku,
                descricao: dadosOp.descricao,
                ordem_producao: dadosOp.ordem_producao,
                formato_gramas: dadosOp.formato_gramas,
                planejado_op: dadosOp.planejado_op,
                produzido_op: dadosOp.produzido_op,
                diferenca_op: dadosOp.diferenca_op,
                toneladas_op: dadosOp.toneladas_op,
                oee: dadosOp.oee || dadosEq.oee_atual || 0,
                pecas_boas: dadosOp.pecas_boas,
                pecas_ruins: dadosOp.pecas_ruins,
                timestamp: dadosEq.timestamp
            };

            return {
                medicoes,
                status: dadosEq.estado_atual || 'Offline',
                timestamp: dadosEq.timestamp
            };
        } catch (error) {
            return null;
        }
    };

    const fetchData = async () => {
        try {
            setLoading(true);

            // 1. Fetch Line Config from Django (Robust Resolution: Code or Name)
            let resLinha = await fetch(`${DJANGO_API_URL}/linhas/?codigo=${linhaId}`);
            let linhaData = await resLinha.json();
            let results = linhaData.results || linhaData;

            // If not found by code, try searching by name/search
            if (!results || results.length === 0) {
                resLinha = await fetch(`${DJANGO_API_URL}/linhas/?search=${linhaId}`);
                linhaData = await resLinha.json();
                results = linhaData.results || linhaData;
            }

            let linhaIdNumeric = 0;
            let linhaIdentifier = linhaId || '';
            let currentEquipamentosConfig: EquipamentoConfig[] = [];

            if (results && results.length > 0) {
                // Fix: Fuzzy search returns multiple lines. Ensure exact match if possible.
                const lConfig = results.find((r: any) =>
                    r.codigo === linhaId ||
                    r.nome === linhaId ||
                    r.nome.toLowerCase() === linhaId?.toLowerCase()
                ) || results[0];

                setLinhaConfig(lConfig);
                linhaIdNumeric = lConfig.id;

                // CRITICAL: Always use the CODE for Flask API calls
                linhaIdentifier = lConfig.codigo;

                // 2. Fetch Equipments Config from Django (using numeric ID)
                const resEquipamentos = await fetch(`${DJANGO_API_URL}/equipamentos/?linha=${linhaIdNumeric}`);
                if (resEquipamentos.ok) {
                    const dataEq = await resEquipamentos.json();
                    currentEquipamentosConfig = dataEq.results || dataEq;
                    setEquipamentosConfig(currentEquipamentosConfig);
                }
            }

            // 3. Parallel requests for Flask Realtime Data (Line Level) - Using resolved identifier
            const [resStatus, resOle, resKpis, resConsolidadas] = await Promise.all([
                fetch(`${FLASK_API_URL}/linha/${encodeURIComponent(linhaIdentifier)}/overview-status`),
                fetch(`${FLASK_API_URL}/linha/${encodeURIComponent(linhaIdentifier)}/realtime`), // CORRECTED to match routes.py
                fetch(`${FLASK_API_URL}/linha/${encodeURIComponent(linhaIdentifier)}/kpis`),
                fetch(`${DJANGO_API_URL}/metricas_fabrica_consolidadas/`)
            ]);

            if (resStatus.ok) setLineStatus(await resStatus.json());
            if (resOle.ok) setOleData(await resOle.json());
            if (resKpis.ok) setKpisData(await resKpis.json());

            let metricasLinha = null;
            if (resConsolidadas.ok) {
                const consolidadas = await resConsolidadas.json();
                metricasLinha = consolidadas.find((m: any) => m.linha_id === linhaIdNumeric);
            }

            // 4. Fetch Detailed Data for Each Equipment AND Diagnostics
            const allAlerts: string[] = [];
            if (currentEquipamentosConfig.length > 0) {
                const promises = currentEquipamentosConfig.map(async (eq) => {
                    const [dadosReais, resAlerts] = await Promise.all([
                        fetchTempoReal(eq.codigo),
                        fetch(`${FLASK_API_URL}/diagnostics/alerts/${eq.codigo}`)
                    ]);

                    // Collect Alerts
                    if (resAlerts.ok) {
                        const alertsData = await resAlerts.json();
                        if (alertsData.alerts && Array.isArray(alertsData.alerts)) {
                            alertsData.alerts.forEach((a: any) => {
                                allAlerts.push(`${eq.nome}: ${a.message}`);
                            });
                        }
                    }

                    return {
                        ...eq,
                        ...dadosReais
                    } as EquipamentoCompleto;
                });

                const equipamentosDetalhadosResult = await Promise.all(promises);
                // Sort by order
                equipamentosDetalhadosResult.sort((a, b) => (a.ordem_na_linha || 0) - (b.ordem_na_linha || 0));
                setEquipamentosDetalhados(equipamentosDetalhadosResult);
            }

            setDiagnosticAlerts(allAlerts);
            setMetricasConsolidadas(metricasLinha);

            setLastUpdate(new Date());
        } catch (error) {
            console.error("Error fetching line details:", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 5000); // 5s refresh
        return () => clearInterval(interval);
    }, [linhaId]);

    if (loading && !lineStatus && equipamentosDetalhados.length === 0) {
        return <div className="p-10 text-center">Carregando Detalhes da Linha...</div>;
    }

    // Fallback if lineStatus fails but we have detailed data, or vice versa
    // But header relies on lineStatus or detailed data.

    // Leader Equipment Logic (Prioritize Detailed Data)
    const eqLider = equipamentosDetalhados.find(eq =>
        eq.medicoes?.ordem_producao && eq.medicoes?.ordem_producao !== 'N/A'
    ) || equipamentosDetalhados[0];

    const dadosProducao = eqLider?.medicoes;

    // Calculations
    const tempoDecorrido = oleData?.tempo_decorrido || 0;
    const tempoTotalTurno = oleData?.tempo_total_turno || 28800; // 8h default
    const tempoDecorridoHoras = tempoDecorrido / 3600;
    const tempoTotalHoras = tempoTotalTurno / 3600;

    const producaoReal = oleData?.producao_real || 0;
    const metaTotal = oleData?.meta_turno || oleData?.producao_planejada_total || 0; // Fallback for Stale Backend
    const oleAtual = oleData?.ole || 0;
    const taxaInstantanea = oleData?.taxa_instantanea || 0;

    // Vazão (t/h) - Use Realtime (Flask) > Consolidated (Django) > Calc
    const vazaoCalculada = taxaInstantanea || (metricasConsolidadas?.vazao_real_ton_hora ?? (tempoDecorridoHoras > 0 ? (producaoReal / tempoDecorridoHoras) : 0));

    // Projeção: Use backend value (Dynamic) or Fallback to Client Calc
    let projecao = oleData?.projecao || 0;
    if (!projecao && tempoTotalHoras > 0 && tempoDecorridoHoras > 0) {
        // Client-Side Projection Calculation (for Stale Backend)
        // Proj = Real + (Rate * RemainingTime)
        const remainingHours = tempoTotalHoras - tempoDecorridoHoras;
        if (remainingHours > 0) {
            projecao = producaoReal + (vazaoCalculada * remainingHours);
        } else {
            projecao = producaoReal;
        }
    }
    // Final Fallback (Simples Rule of Three if no rate)
    if (!projecao && metaTotal > 0) {
        projecao = metaTotal * (oleAtual / 100);
    }

    // Tempo Decorrido %
    const tempoDecorridoPerc = tempoTotalTurno > 0 ? (tempoDecorrido / tempoTotalTurno) * 100 : 0;

    // Ritmo Necessário: Use backend value (Dynamic) or Fallback
    const ritmoNecessario = oleData?.ritmo_necessario ?? (tempoTotalHoras > 0 && (metaTotal - producaoReal) > 0 ? ((metaTotal - producaoReal) / (tempoTotalHoras - tempoDecorridoHoras)) : 0);

    // Desvio
    const desvioProjetado = projecao - metaTotal;

    // Prepare data for Header
    const currentStatus = lineStatus?.status || 'Carregando...';
    const isSystemOffline = currentStatus === 'Sem Comunicação' || currentStatus === 'Offline';

    const headerProps = {
        linha: linhaConfig?.nome || linhaId || 'Linha Desconhecida',
        op: oleData?.op || dadosProducao?.ordem_producao || 'N/A',
        sku: oleData?.sku || dadosProducao?.sku_codigo || 'N/A',
        produto: oleData?.descricao || dadosProducao?.descricao || 'Produto Genérico',
        cuc: oleData?.cuc || dadosProducao?.cuc || 'N/A',
        formato: oleData?.formato || dadosProducao?.formato_gramas || 0,
        equipamentosOnline: oleData?.equipamentos_online || 0,
        totalEquipamentos: oleData?.equipamentos_total || equipamentosConfig.length,
        vazao: vazaoCalculada,
        ole: oleAtual,
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
                        producaoReal={producaoReal}
                        producaoEsperada={oleData?.producao_esperada || oleData?.producao_planejada_ate_agora || 0}
                        projecao={projecao}
                        metaTurno={metaTotal}
                        tempoDecorridoPerc={tempoDecorridoPerc}
                    />

                    {/* Equipment Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {equipamentosDetalhados.map((eq, idx) => (
                            <EquipmentCard
                                key={idx}
                                nome={eq.nome}
                                funcao={eq.tipo}
                                estado={eq.medicoes?.estado ?? 0} // Pass raw state (string or number)
                                oee={eq.medicoes?.oee || 0}
                                velocidadeAtual={eq.medicoes?.velocidade_atual || 0}
                                velocidadeNominal={eq.velocidade_nominal || 100}
                                boas={eq.medicoes?.pecas_boas || 0}
                                ruins={eq.medicoes?.pecas_ruins || 0}
                                ultimaParada="N/A"
                            />
                        ))}
                    </div>

                    {/* Timeline Section (Moved to Bottom) */}
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
                        availability={kpisData?.kpis?.disponibilidade || 0}
                        performance={kpisData?.kpis?.performance || 0}
                        quality={kpisData?.kpis?.qualidade || 0}
                        bottleneck={{
                            name: kpisData?.gargalo?.nome || 'N/A',
                            oee: kpisData?.gargalo?.oee || 0
                        }}
                        ritmoAtual={vazaoCalculada}
                        ritmoNecessario={ritmoNecessario}
                        desvioProjetado={desvioProjetado}
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
