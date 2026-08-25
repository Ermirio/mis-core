import React, { useEffect, useState, useRef } from "react";
import EquipamentoCard from "@/components/EquipamentoCard";
import LineOverview from "@/components/LineOverview";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { RefreshCw, AlertCircle, Sun, Moon } from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";
import { APP_TITLE } from "@/const";
import MultiEquipmentTimeline from "@/components/MultiEquipmentTimeline";

// Importar funções utilitárias
import {
  safeArray,
  safeNumber,
  safeString,
  isValidArray,
  extractValue,
  safeMerge
} from "@/utils/dataValidation";
import {
  calculateProduction,
  createSafeProductionData,
  type ProductionData
} from "@/utils/productionCalculations";
import { DJANGO_API_URL, FASTAPI_V2_URL, FLASK_API_URL } from '@/config/api';

interface EquipamentoConfig {
  id: number;
  nome: string;
  codigo: string;
  tipo: string;
  tipo_display: string;
  linha: number;
  linha_nome: string;
  linha_codigo: string;
  ordem_na_linha?: number;
  velocidade_nominal: number;
  velocidade_maxima: number;
  meta_oee: number;
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

interface LinhaAgrupada {
  linha_id: number;
  linha_nome: string;
  linha_codigo: string;
  equipamentos: EquipamentoCompleto[];
  ole_data?: {
    ole: number;
    producao_real: number;
    producao_planejada_ate_agora: number;
    producao_planejada_total: number;
    producao_esperada?: number;
    equipamentos_online: number;
    equipamentos_total: number;
    sku?: string;
    op?: string;
    descricao?: string;
    cuc?: string;
    formato?: number;
    meta_turno?: number;
    taxa_instantanea?: number;
    projecao?: number;
    ritmo_necessario?: number;
    tempo_decorrido?: number;
    tempo_total_turno?: number;
  };
}



export default function Home() {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const [linhas, setLinhas] = useState<LinhaAgrupada[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [metricasConsolidadas, setMetricasConsolidadas] = useState<any[]>([]);

  // Controle de fetch para evitar race conditions
  const isFetchingRef = useRef(false);

  /**
   * Fetch de configuração de equipamentos com validação robusta
   */
  const fetchConfiguracao = async (): Promise<EquipamentoConfig[]> => {
    try {
      const equipamentos: EquipamentoConfig[] = [];
      let nextUrl: string | null = `${DJANGO_API_URL}/equipamentos/?page_size=100`;

      // A fábrica possui mais equipamentos do que a página padrão da API.
      // Consumir toda a paginação evita linhas inteiras ausentes no painel.
      while (nextUrl) {
        const response = await fetch(nextUrl);
        if (!response.ok) {
          console.error(`Erro ao buscar configuração: ${response.status}`);
          return [];
        }
        const data = await response.json();
        const results = safeArray(data.results || data);
        equipamentos.push(...(results as EquipamentoConfig[]));
        nextUrl = data.next || null;
      }

      return equipamentos;
    } catch (error) {
      console.error("Erro ao buscar configuração:", error);
      return [];
    }
  };

  /**
   * Fetch de métricas consolidadas
   */
  const fetchMetricasConsolidadas = async () => {
    try {
      const response = await fetch(`${DJANGO_API_URL}/metricas_fabrica_consolidadas/`);
      if (response.ok) {
        const data = await response.json();
        setMetricasConsolidadas(safeArray(data));
      }
    } catch (error) {
      console.error("Erro ao buscar métricas:", error);
    }
  };

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

  const equipmentIdentity = (linhaId: number, codigo: string) => `${linhaId}:${codigo}`;

  const fetchFullEquipmentStatus = async (): Promise<Record<string, FullEquipmentStatus>> => {
    try {
      const response = await fetch(`${DJANGO_API_URL}/full_equipment_status/`);
      if (!response.ok) return {};

      const data = await response.json();
      return safeArray(data).reduce((acc: Record<string, FullEquipmentStatus>, item: FullEquipmentStatus) => {
        if (item.codigo && item.linha_id != null) {
          acc[equipmentIdentity(item.linha_id, item.codigo)] = item;
        }
        return acc;
      }, {});
    } catch (error) {
      console.error("Erro ao buscar status completo dos equipamentos:", error);
      return {};
    }
  };

  const mergeStatusFallback = (
    tempoReal: Partial<EquipamentoCompleto> | null,
    _fallback?: FullEquipmentStatus,
  ): Partial<EquipamentoCompleto> | null => {
    // O fallback SQL contém a última métrica/evento histórico, não prova de
    // comunicação atual. Misturá-lo com um ponto OPC vencido produzia cards
    // impossíveis (RUN + velocidade antiga). Sem realtime confiável, Offline.
    return tempoReal;
  };

  /**
   * Fetch de dados em tempo real de um equipamento com validação robusta
   */
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

      // Construir medições com valores seguros
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

  /**
   * Fetch de dados OLE da linha com validação
   */
  const fetchLinhaOLE = async (linhaIdentifier: string): Promise<any> => {
    if (!linhaIdentifier) return null;

    try {
      // Flask-out Onda 2: /linha/<>/ole-realtime migrado para Django.
      const response = await fetch(`${DJANGO_API_URL}/linha/${encodeURIComponent(linhaIdentifier)}/ole-realtime`);
      if (response.ok) {
        return await response.json();
      }
      return null;
    } catch (error) {
      console.error(`Erro ao buscar OLE da linha ${linhaIdentifier}:`, error);
      return null;
    }
  };

  /**
   * Processa dados OLE com cálculos robustos
   */
  const processOLEData = (oleData: any, metricasLinha?: any): any => {
    if (!oleData) return null;

    // Criar dados de produção seguros
    const productionData = createSafeProductionData({
      producaoReal: oleData.producao_real,
      metaTotal: oleData.producao_planejada_total || oleData.meta_turno,
      oleAtual: oleData.ole,
      tempoDecorrido: oleData.tempo_decorrido,
      tempoTotalTurno: oleData.tempo_total_turno,
      taxaInstantanea: oleData.taxa_instantanea || metricasLinha?.vazao_real_ton_hora,
      projecaoBackend: oleData.projecao,
      ritmoNecessarioBackend: oleData.ritmo_necessario
    });

    // Calcular métricas
    const calculations = calculateProduction(productionData);

    // Retornar dados processados
    return {
      ...oleData,
      projecao: calculations.projecao,
      producao_esperada: oleData.producao_planejada_ate_agora || oleData.producao_esperada,
      meta_turno: productionData.metaTotal,
      taxa_instantanea: calculations.vazaoCalculada,
      ritmo_necessario: calculations.ritmoNecessario
    };
  };

  /**
   * Função principal de fetch com controle de concorrência
   */
  const fetchEquipamentos = async () => {
    // Prevenir múltiplas requisições simultâneas
    if (isFetchingRef.current) {
      console.log("Fetch já em andamento, pulando...");
      return;
    }

    isFetchingRef.current = true;

    try {
      // Fetch métricas consolidadas em paralelo
      fetchMetricasConsolidadas();

      // Buscar configurações e fallback de estado consolidado
      const [configuracoes, fullStatusByCode] = await Promise.all([
        fetchConfiguracao(),
        fetchFullEquipmentStatus()
      ]);

      if (configuracoes.length === 0) {
        setLinhas([]);
        setError("Nenhum equipamento configurado");
        return;
      }

      // Buscar dados em tempo real de todos os equipamentos
      const promisesEquipamentos = configuracoes.map(async (config) => {
        const tempoReal = await fetchTempoReal(config.codigo, config.linha_codigo);
        const tempoRealComFallback = mergeStatusFallback(
          tempoReal,
          fullStatusByCode[equipmentIdentity(config.linha, config.codigo)],
        );
        return {
          ...config,
          medicoes: tempoRealComFallback?.medicoes,
          status: tempoRealComFallback?.status || 'Offline',
          timestamp: tempoRealComFallback?.timestamp
        } as EquipamentoCompleto;
      });

      const equipamentosCompletos = await Promise.all(promisesEquipamentos);

      // Agrupar por linha
      const linhasMap = new Map<number, LinhaAgrupada>();
      equipamentosCompletos.forEach(eq => {
        if (!linhasMap.has(eq.linha)) {
          linhasMap.set(eq.linha, {
            linha_id: eq.linha,
            linha_nome: eq.linha_nome,
            linha_codigo: eq.linha_codigo || eq.linha_nome,
            equipamentos: [],
            ole_data: undefined
          });
        }
        linhasMap.get(eq.linha)!.equipamentos.push(eq);
      });

      const linhasArray = Array.from(linhasMap.values());

      // Buscar dados OLE de cada linha
      const promisesLinhas = linhasArray.map(async (linha) => {
        const idParaBusca = linha.linha_codigo || linha.linha_nome;
        const oleData = await fetchLinhaOLE(idParaBusca);
        const metricasLinha = metricasConsolidadas.find(m => m.linha_id === linha.linha_id);

        // Processar dados OLE com cálculos robustos
        linha.ole_data = processOLEData(oleData, metricasLinha);

        // Ordenar equipamentos
        linha.equipamentos.sort((a, b) => (a.ordem_na_linha || 0) - (b.ordem_na_linha || 0));

        return linha;
      });

      const linhasFinais = await Promise.all(promisesLinhas);

      setLinhas(linhasFinais);
      setLastUpdate(new Date());
      setError(null);

    } catch (error) {
      console.error("Erro ao buscar equipamentos:", error);
      if (linhas.length === 0) {
        setError("Erro ao carregar dados. Tentando novamente...");
      }
    } finally {
      setLoading(false);
      isFetchingRef.current = false;
    }
  };

  useEffect(() => {
    fetchEquipamentos();
    const interval = setInterval(fetchEquipamentos, 5000);
    return () => {
      clearInterval(interval);
      isFetchingRef.current = false;
    };
  }, []);

  /**
   * Busca métricas consolidadas de uma linha
   */
  const getMetricasLinha = (linhaId: number) => {
    return metricasConsolidadas.find(m => m.linha_id === linhaId) || {};
  };

  /**
   * Encontra equipamento líder (com OP ativa)
   */
  const findEquipamentoLider = (equipamentos: EquipamentoCompleto[]) => {
    return equipamentos.find(eq =>
      eq.medicoes?.ordem_producao &&
      eq.medicoes?.ordem_producao !== 'N/A' &&
      eq.medicoes?.ordem_producao.trim() !== ''
    ) || equipamentos[0];
  };

  return (
    <div className="min-h-screen bg-neutral-100 dark:bg-neutral-900">
      <header className="border-b border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800">
        <div className="container mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-neutral-800 dark:text-neutral-100">{APP_TITLE}</h1>
            <p className="text-sm text-neutral-600 dark:text-neutral-400">
              Última atualização: {lastUpdate.toLocaleTimeString("pt-BR")}
            </p>
          </div>
          <div className="flex gap-3">
            <Button variant="outline" size="icon" onClick={() => fetchEquipamentos()}>
              <RefreshCw className="w-4 h-4" />
            </Button>
            <Button variant="outline" size="icon" onClick={toggleTheme}>
              {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-6 py-8">
        {loading ? (
          <div className="flex justify-center h-64 items-center">
            <RefreshCw className="w-8 h-8 animate-spin text-neutral-500" />
          </div>
        ) : error && !linhas.length ? (
          <div className="flex flex-col justify-center h-64 items-center text-center">
            <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
            <p className="text-neutral-700 dark:text-neutral-300">{error}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 2xl:grid-cols-2 gap-6 items-start">
            {linhas.map((linha) => {
              const metricas = getMetricasLinha(linha.linha_id);
              const eqLider = findEquipamentoLider(linha.equipamentos);
              const dadosProducao = eqLider?.medicoes;

              return (
                <div key={linha.linha_id} className="flex flex-col gap-4 p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white/50 dark:bg-neutral-900/50 shadow-sm">

                  {/* Line Header */}
                  <div className="-mx-2 -mt-2">
                    <LineOverview
                      nome={linha.linha_nome}
                      ole={safeNumber(linha.ole_data?.ole, 0)}
                      producaoReal={safeNumber(linha.ole_data?.producao_real, 0)}
                      producaoEsperada={safeNumber(linha.ole_data?.producao_esperada, 0)}
                      metaTotal={safeNumber(linha.ole_data?.meta_turno, 0)}
                      totalEquipamentos={linha.equipamentos.length}
                      equipamentosOnline={linha.ole_data?.equipamentos_online ?? linha.equipamentos.filter(eq => eq.status !== 'Offline').length}
                      sku={extractValue(linha.ole_data?.sku, dadosProducao?.sku_codigo, metricas.sku_codigo) || 'N/A'}
                      descricao={extractValue(linha.ole_data?.descricao, dadosProducao?.descricao, metricas.sku_descricao) || 'Produto Genérico'}
                      ordemProducao={extractValue(linha.ole_data?.op, dadosProducao?.ordem_producao, metricas.ordem_producao) || 'N/A'}
                      cuc={extractValue(linha.ole_data?.cuc, dadosProducao?.cuc) || 'N/A'}
                      formatoAtual={safeNumber(extractValue(linha.ole_data?.formato, dadosProducao?.formato_gramas, metricas.formato_gramas), 0)}
                      vazaoTurno={safeNumber(extractValue(linha.ole_data?.taxa_instantanea, metricas.vazao_real_ton_hora), 0)}
                      projecao={safeNumber(linha.ole_data?.projecao, 0)}
                    />
                  </div>

                  {/* Equipment Grid */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-2">
                    {linha.equipamentos.map((eq) => (
                      <EquipamentoCard
                        key={eq.id}
                        id={eq.id}
                        nome={eq.nome}
                        tipo={eq.tipo}
                        estado={safeString(eq.medicoes?.estado || eq.status, 'Desconhecido')}
                        velocidadeAtual={safeNumber(eq.medicoes?.velocidade_atual, 0)}
                        velocidadePadrao={safeNumber(eq.velocidade_nominal, 0)}
                        pecasBoas={safeNumber(eq.medicoes?.produzido_turno, 0)}
                        pecasRuins={safeNumber(eq.medicoes?.pecas_ruins_turno, 0)}
                        oee={safeNumber(eq.medicoes?.oee, 0)}
                        metaOEE={safeNumber(eq.meta_oee, 0)}
                        sku={safeString(eq.medicoes?.sku_codigo, 'N/A')}
                        descricao={safeString(eq.medicoes?.descricao, 'Produto Genérico')}
                        ordemProducao={safeString(eq.medicoes?.ordem_producao, 'N/A')}
                        cuc={safeString(eq.medicoes?.cuc, 'N/A')}
                        planejado={safeNumber(eq.medicoes?.planejado_op, 0)}
                        diferenca={safeNumber(eq.medicoes?.diferenca_op, 0)}
                      />
                    ))}
                  </div>

                  {/* Timeline */}
                  <div className="mt-2 overflow-hidden rounded-lg border border-neutral-200 dark:border-neutral-700">
                    <MultiEquipmentTimeline
                      linhaId={linha.linha_id}
                      linhaNome={linha.linha_nome}
                      equipamentos={linha.equipamentos}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
