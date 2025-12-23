import React, { useEffect, useState } from "react";
import EquipamentoCard from "@/components/EquipamentoCard";
import LineOverview from "@/components/LineOverview";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { RefreshCw, AlertCircle, Sun, Moon, ExternalLink } from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";
import { APP_TITLE } from "@/const";
import MultiEquipmentTimeline from "@/components/MultiEquipmentTimeline";

interface EquipamentoConfig {
  id: number;
  nome: string;
  codigo: string;
  tipo: string;
  tipo_display: string;
  linha: number;
  linha_nome: string;
  linha_codigo: string; // Added
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

interface LinhaAgrupada {
  linha_id: number;
  linha_nome: string;
  linha_codigo: string; // Added
  equipamentos: EquipamentoCompleto[];
  ole_data?: {
    ole: number;
    producao_real: number;
    producao_planejada_ate_agora: number;
    producao_planejada_total: number;
    producao_esperada?: number; // Added
    equipamentos_online: number;
    equipamentos_total: number;
    sku?: string; // Added
    op?: string; // Added
    descricao?: string; // Added
    cuc?: string; // Added
    formato?: number; // Added
    meta_turno?: number; // Added
    taxa_instantanea?: number; // Added (vazaoTurno)
    projecao?: number; // Added
    ritmo_necessario?: number; // Added
  };
}

const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || "http://127.0.0.1:8000/api";
const FLASK_API_URL = import.meta.env.VITE_FLASK_API_URL || "http://127.0.0.1:5000/api";

export default function Home() {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const [linhas, setLinhas] = useState<LinhaAgrupada[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [metricasConsolidadas, setMetricasConsolidadas] = useState<any[]>([]);

  const fetchConfiguracao = async (): Promise<EquipamentoConfig[]> => {
    try {
      const response = await fetch(`${DJANGO_API_URL}/equipamentos/`);
      if (!response.ok) throw new Error(`Erro Config: ${response.status}`);
      const data = await response.json();
      return data.results || data;
    } catch (error) {
      console.error("Erro Config:", error);
      throw error;
    }
  };

  const fetchMetricasConsolidadas = async () => {
    try {
      const response = await fetch(`${DJANGO_API_URL}/metricas_fabrica_consolidadas/`);
      if (response.ok) {
        const data = await response.json();
        setMetricasConsolidadas(data);
      }
    } catch (error) {
      console.error("Erro Métricas:", error);
    }
  };

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

  const fetchLinhaOLE = async (nomeLinha: string): Promise<any> => {
    try {
      const response = await fetch(`${FLASK_API_URL}/linha/${encodeURIComponent(nomeLinha)}/realtime`);
      if (response.ok) {
        return await response.json();
      }
      return null;
    } catch (error) {
      return null;
    }
  };

  const fetchEquipamentos = async () => {
    try {
      fetchMetricasConsolidadas();
      const configuracoes = await fetchConfiguracao();

      if (!configuracoes.length) {
        setLinhas([]);
        return;
      }

      const promisesEquipamentos = configuracoes.map(async (config) => {
        const tempoReal = await fetchTempoReal(config.codigo);
        return {
          ...config,
          medicoes: tempoReal?.medicoes,
          status: tempoReal?.status || 'Offline',
          timestamp: tempoReal?.timestamp
        } as EquipamentoCompleto;
      });

      const equipamentosCompletos = await Promise.all(promisesEquipamentos);

      const linhasMap = new Map<number, LinhaAgrupada>();
      equipamentosCompletos.forEach(eq => {
        if (!linhasMap.has(eq.linha)) {
          linhasMap.set(eq.linha, {
            linha_id: eq.linha,
            linha_nome: eq.linha_nome,
            linha_codigo: eq.linha_codigo || eq.linha_nome, // Fallback
            equipamentos: [],
            ole_data: undefined
          });
        }
        linhasMap.get(eq.linha)!.equipamentos.push(eq);
      });

      const linhasArray = Array.from(linhasMap.values());

      const promisesLinhas = linhasArray.map(async (linha) => {
        // Use linha_codigo if available, otherwise name
        const idParaBusca = linha.linha_codigo || linha.linha_nome;
        const oleData = await fetchLinhaOLE(idParaBusca);

        if (oleData) {
          // Replicate LineDeepView Projection Logic
          const tempoDecorrido = oleData.tempo_decorrido || 0;
          const tempoTotalTurno = oleData.tempo_total_turno || 28800;
          const tempoDecorridoHoras = tempoDecorrido / 3600;
          const tempoTotalHoras = tempoTotalTurno / 3600;
          const producaoReal = oleData.producao_real || 0;
          const metaTotal = oleData.producao_planejada_total || 0;
          const oleAtual = oleData.ole || 0;

          let projecao = oleData.projecao || 0;

          if (!projecao && tempoTotalHoras > 0 && tempoDecorridoHoras > 0) {
            const remainingHours = tempoTotalHoras - tempoDecorridoHoras;
            const vazaoCalculada = producaoReal / tempoDecorridoHoras;
            if (remainingHours > 0) {
              projecao = producaoReal + (vazaoCalculada * remainingHours);
            } else {
              projecao = producaoReal;
            }
          }

          if (!projecao && metaTotal > 0) {
            projecao = metaTotal * (oleAtual / 100);
          }

          // Map fields for UI
          oleData.projecao = projecao;
          oleData.producao_esperada = oleData.producao_planejada_ate_agora;
          oleData.meta_turno = metaTotal;
        }

        linha.ole_data = oleData;
        linha.equipamentos.sort((a, b) => (a.ordem_na_linha || 0) - (b.ordem_na_linha || 0));
        return linha;
      });

      const linhasFinais = await Promise.all(promisesLinhas);

      console.log("DEBUG Linhas Finais:", linhasFinais.map(l => ({
        nome: l.linha_nome,
        codigo: l.linha_codigo,
        oleData: l.ole_data,
        equipamentos: l.equipamentos.map(e => ({
          code: e.codigo,
          metrics: e.medicoes
        }))
      })));

      setLinhas(linhasFinais);
      setLastUpdate(new Date());
      setError(null);

    } catch (error) {
      console.error("Erro fetch:", error);
      if (linhas.length === 0) setError("Erro ao carregar dados.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEquipamentos();
    const interval = setInterval(fetchEquipamentos, 5000);
    return () => clearInterval(interval);
  }, []);

  const getMetricasLinha = (linhaId: number) => {
    return metricasConsolidadas.find(m => m.linha_id === linhaId) || {};
  };

  return (
    <div className="min-h-screen bg-neutral-100 dark:bg-neutral-900">
      <header className="border-b border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800">
        <div className="container mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-neutral-800 dark:text-neutral-100">{APP_TITLE}</h1>
            <p className="text-sm text-neutral-600 dark:text-neutral-400">Última atualização: {lastUpdate.toLocaleTimeString("pt-BR")}</p>
          </div>
          <div className="flex gap-3">
            <Button variant="outline" size="icon" onClick={() => fetchEquipamentos()}><RefreshCw className="w-4 h-4" /></Button>
            <Button variant="outline" size="icon" onClick={toggleTheme}>{theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}</Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-6 py-8">
        {loading ? (
          <div className="flex justify-center h-64 items-center"><RefreshCw className="w-8 h-8 animate-spin text-neutral-500" /></div>
        ) : error && !linhas.length ? (
          <div className="flex justify-center h-64 items-center text-center"><AlertCircle className="w-12 h-12 text-red-500 mb-4" /><p>{error}</p></div>
        ) : (
          <div className="grid grid-cols-1 2xl:grid-cols-2 gap-6 items-start">
            {linhas.map((linha) => {
              const metricas = getMetricasLinha(linha.linha_id);

              const eqLider = linha.equipamentos.find(eq =>
                eq.medicoes?.ordem_producao && eq.medicoes?.ordem_producao !== 'N/A'
              ) || linha.equipamentos[0];

              const dadosProducao = eqLider?.medicoes;

              return (
                <div key={linha.linha_id} className="flex flex-col gap-4 p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white/50 dark:bg-neutral-900/50 shadow-sm">

                  {/* Line Header */}
                  <div className="-mx-2 -mt-2">
                    <LineOverview
                      nome={linha.linha_nome}
                      ole={linha.ole_data?.ole || 0}
                      producaoReal={linha.ole_data?.producao_real}
                      producaoEsperada={linha.ole_data?.producao_esperada}
                      metaTotal={linha.ole_data?.meta_turno} // Changed from producao_planejada_total to matches API (meta_turno) or fallback
                      totalEquipamentos={linha.equipamentos.length}
                      equipamentosOnline={linha.equipamentos.filter(eq => eq.status !== 'Offline').length}
                      sku={linha.ole_data?.sku || dadosProducao?.sku_codigo || metricas.sku_codigo}
                      descricao={linha.ole_data?.descricao || dadosProducao?.descricao || metricas.sku_descricao}
                      ordemProducao={linha.ole_data?.op || dadosProducao?.ordem_producao || metricas.ordem_producao}
                      cuc={linha.ole_data?.cuc || dadosProducao?.cuc}
                      formatoAtual={linha.ole_data?.formato || dadosProducao?.formato_gramas || metricas.formato_gramas}
                      vazaoTurno={linha.ole_data?.taxa_instantanea || metricas.vazao_real_ton_hora}
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
                        estado={eq.medicoes?.estado || eq.status}
                        velocidadeAtual={eq.medicoes?.velocidade_atual}
                        velocidadePadrao={eq.velocidade_nominal}
                        pecasBoas={eq.medicoes?.produzido_op}
                        pecasRuins={eq.medicoes?.pecas_ruins}
                        oee={eq.medicoes?.oee}
                        metaOEE={eq.meta_oee}
                        sku={eq.medicoes?.sku_codigo}
                        descricao={eq.medicoes?.descricao}
                        ordemProducao={eq.medicoes?.ordem_producao}
                        cuc={eq.medicoes?.cuc}
                        planejado={eq.medicoes?.planejado_op}
                        diferenca={eq.medicoes?.diferenca_op}
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