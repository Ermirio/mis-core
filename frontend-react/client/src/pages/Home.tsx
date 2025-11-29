import React, { useEffect, useState } from "react";
import EquipamentoCard from "@/components/EquipamentoCard";
import LineOverview from "@/components/LineOverview";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { RefreshCw, AlertCircle, Sun, Moon, ExternalLink } from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";
import { APP_TITLE } from "@/const";
import MultiEquipmentTimeline from "@/components/MultiEquipmentTimeline";

/**
 * Home - Dashboard Principal
 * * Atualizado para consumir as novas rotas segregadas do Flask API:
 * - /api/operacao/dados/:id -> Dados de Produto, OP, Contadores
 * - /api/equipamento/dados/:id -> Dados de Estado, Velocidade, Sensores
 */

interface EquipamentoConfig {
  id: number;
  nome: string;
  codigo: string;
  tipo: string;
  tipo_display: string;
  linha: number;
  linha_nome: string;
  ordem_na_linha?: number;
  velocidade_nominal: number;
  velocidade_maxima: number;
  meta_oee: number;
  temperatura_min?: number;
  temperatura_max?: number;
  pressao_min?: number;
  pressao_max?: number;
}

// Interface combinada dos dados que vêm do Flask
interface MedicoesCombinadas {
  // Dados de Equipamento
  velocidade_atual: number;
  estado: string; // "estado_atual" da API
  pecas_produzidas_equipamento: number; // contador físico da máquina

  // Dados de Operação
  cuc: string;
  sku_codigo: string;
  descricao: string;
  ordem_producao: string;
  formato_gramas: number;
  planejado_op: number;
  produzido_op: number;
  diferenca_op: number;
  pecas_boas: number;
  pecas_ruins: number;

  // Timestamps
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
  equipamentos: EquipamentoCompleto[];
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

  /**
   * Busca configuração dos equipamentos do Django
   */
  const fetchConfiguracao = async (): Promise<EquipamentoConfig[]> => {
    try {
      const response = await fetch(`${DJANGO_API_URL}/equipamentos/`);

      if (!response.ok) {
        throw new Error(`Erro ao buscar configuração: ${response.status}`);
      }

      const data = await response.json();
      return data.results || data;

    } catch (error) {
      console.error("Erro ao buscar configuração:", error);
      throw error;
    }
  };

  /**
   * Busca métricas consolidadas da fábrica (incluindo tonelagem)
   */
  const fetchMetricasConsolidadas = async () => {
    try {
      const response = await fetch(`${DJANGO_API_URL}/metricas_fabrica_consolidadas/`);
      if (response.ok) {
        const data = await response.json();
        setMetricasConsolidadas(data);
      }
    } catch (error) {
      console.error("Erro ao buscar métricas consolidadas:", error);
    }
  };

  /**
   * Busca dados de tempo real do Flask para um equipamento.
   * AGORA FAZ 2 CHAMADAS: Operação e Equipamento
   */
  const fetchTempoReal = async (codigoEquipamento: string): Promise<Partial<EquipamentoCompleto> | null> => {
    try {
      // Executa as duas requisições em paralelo para performance
      const [resOperacao, resEquipamento] = await Promise.all([
        fetch(`${FLASK_API_URL}/operacao/dados/${codigoEquipamento}`),
        fetch(`${FLASK_API_URL}/equipamento/dados/${codigoEquipamento}`)
      ]);

      // Se alguma falhar, retornamos null ou dados parciais
      if (!resOperacao.ok || !resEquipamento.ok) {
        console.warn(`Dados incompletos para ${codigoEquipamento}`);
        return null;
      }

      const dadosOp = await resOperacao.json();
      const dadosEq = await resEquipamento.json();

      // Combina os dados
      const medicoes: MedicoesCombinadas = {
        // Dados Equipamento
        velocidade_atual: dadosEq.velocidade_atual,
        estado: dadosEq.estado_atual,
        pecas_produzidas_equipamento: dadosEq.pecas_produzidas, // Contador bruto

        // Dados Operação
        cuc: dadosOp.cuc,
        sku_codigo: dadosOp.sku,
        descricao: dadosOp.descricao,
        ordem_producao: dadosOp.ordem_producao,
        formato_gramas: dadosOp.formato_gramas,
        planejado_op: dadosOp.planejado_op,
        produzido_op: dadosOp.produzido_op,
        diferenca_op: dadosOp.diferenca_op,
        pecas_boas: dadosOp.pecas_boas,
        pecas_ruins: dadosOp.pecas_ruins,

        timestamp: dadosEq.timestamp // Usa o do equipamento como referência
      };

      return {
        medicoes,
        status: dadosEq.estado_atual || 'Offline',
        timestamp: dadosEq.timestamp
      };

    } catch (error) {
      console.error(`Erro ao buscar tempo real de ${codigoEquipamento}:`, error);
      return null;
    }
  };

  /**
   * Combina configuração com dados de tempo real
   */
  const fetchEquipamentos = async () => {
    try {
      // Não limpa o erro imediatamente para evitar "flicker" se falhar uma atualização parcial
      // setError(null);

      // 0. Inicia busca de métricas consolidadas em paralelo
      fetchMetricasConsolidadas();

      // 1. Busca configuração do Django
      const configuracoes = await fetchConfiguracao();

      if (!configuracoes || configuracoes.length === 0) {
        setError("Nenhum equipamento configurado no sistema");
        setLinhas([]);
        return;
      }

      // 2. Busca dados de tempo real do Flask para cada equipamento
      const promises = configuracoes.map(async (config) => {
        const tempoReal = await fetchTempoReal(config.codigo);

        // Considera dados válidos se houver medicoes
        const temDadosValidos = tempoReal && tempoReal.medicoes;

        return {
          ...config,
          medicoes: temDadosValidos ? tempoReal.medicoes : undefined,
          status: tempoReal?.status || 'Offline',
          timestamp: tempoReal?.timestamp
        } as EquipamentoCompleto;
      });

      const equipamentosCompletos = await Promise.all(promises);

      // 3. Agrupa por linha
      const linhasMap = new Map<number, LinhaAgrupada>();

      equipamentosCompletos.forEach(eq => {
        if (!linhasMap.has(eq.linha)) {
          linhasMap.set(eq.linha, {
            linha_id: eq.linha,
            linha_nome: eq.linha_nome,
            equipamentos: []
          });
        }

        linhasMap.get(eq.linha)!.equipamentos.push(eq);
      });

      // Converte para array e ordena equipamentos por ordem_na_linha
      const linhasArray = Array.from(linhasMap.values());
      linhasArray.forEach(linha => {
        linha.equipamentos.sort((a, b) => (a.ordem_na_linha || 0) - (b.ordem_na_linha || 0));
      });

      setLinhas(linhasArray);
      setLastUpdate(new Date());
      setError(null); // Limpa erro apenas se tudo der certo

    } catch (error) {
      console.error("Erro ao buscar dados:", error);
      // Mantém os dados antigos se houver erro de rede temporário
      if (linhas.length === 0) {
        setError("Erro ao carregar dados. Verifique se o Backend (Flask) está rodando.");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEquipamentos();

    // Atualiza a cada 5 segundos
    const interval = setInterval(fetchEquipamentos, 5000);

    return () => clearInterval(interval);
  }, []);

  /**
   * Calcula OEE médio de uma linha (Visualização simplificada)
   */
  const calcularOEELinha = (equipamentos: EquipamentoCompleto[]): number => {
    const equipamentosComDados = equipamentos.filter(eq => eq.status !== 'Offline' && eq.status !== 'Parado/Falha');

    if (equipamentosComDados.length === 0) return 0;

    // Simplificação: média das performances baseada na velocidade
    const somaPerformance = equipamentosComDados.reduce((acc, eq) => {
      const velocidadeAtual = eq.medicoes?.velocidade_atual || 0;
      const velocidadeNominal = eq.velocidade_nominal || 1;
      const performance = Math.min(100, (velocidadeAtual / velocidadeNominal) * 100);
      return acc + performance;
    }, 0);

    return somaPerformance / equipamentosComDados.length;
  };

  /**
   * Obtém métricas consolidadas para uma linha específica
   */
  const getMetricasLinha = (linhaId: number) => {
    return metricasConsolidadas.find(m => m.linha_id === linhaId) || {};
  };

  return (
    <div className="min-h-screen bg-neutral-100 dark:bg-neutral-900">
      {/* Header - ISA 101: Discreto e funcional */}
      <header className="border-b border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800">
        <div className="container mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-neutral-800 dark:text-neutral-100">
              {APP_TITLE}
            </h1>
            <p className="text-sm text-neutral-600 dark:text-neutral-400">
              Última atualização: {lastUpdate.toLocaleTimeString("pt-BR")}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="icon"
              onClick={() => fetchEquipamentos()}
              title="Atualizar dados"
              className="border-neutral-300 dark:border-neutral-600"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>

            <Button
              variant="outline"
              size="icon"
              onClick={toggleTheme}
              title="Alternar tema"
              className="border-neutral-300 dark:border-neutral-600"
            >
              {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        {loading ? (
          // Loading State
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4 text-neutral-500" />
              <p className="text-neutral-600 dark:text-neutral-400">Carregando dados...</p>
            </div>
          </div>
        ) : error && linhas.length === 0 ? (
          // Error State (Apenas se não tiver dados anteriores)
          <div className="flex items-center justify-center h-64">
            <div className="text-center max-w-md">
              <AlertCircle className="w-12 h-12 mx-auto mb-4 text-red-500" />
              <p className="text-neutral-700 dark:text-neutral-300 text-lg mb-2">
                {error}
              </p>
              <Button onClick={() => fetchEquipamentos()} variant="outline">
                Tentar Novamente
              </Button>
            </div>
          </div>
        ) : linhas.length === 0 ? (
          // Empty State
          <div className="text-center py-12">
            <p className="text-neutral-600 dark:text-neutral-400 text-lg">
              Nenhum equipamento encontrado. Configure equipamentos no Django Admin.
            </p>
          </div>
        ) : (
          // Data Display
          <div className="space-y-10">
            {linhas.map((linha) => {
              const metricas = getMetricasLinha(linha.linha_id);
              return (
                <div key={linha.linha_id} className="space-y-4">
                  {/* Line Overview - Visão consolidada da linha */}
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex-1">
                      <LineOverview
                        nome={linha.linha_nome}
                        oee={calcularOEELinha(linha.equipamentos)}
                        totalEquipamentos={linha.equipamentos.length}
                        equipamentosOnline={linha.equipamentos.filter(eq => eq.status !== 'Offline').length}
                        toneladasTurno={metricas.toneladas_produzidas}
                        vazaoTurno={metricas.vazao_real_ton_hora}
                        formatoAtual={metricas.formato_gramas}
                        sku={metricas.sku_codigo}
                        descricao={metricas.sku_descricao}
                        ordemProducao={metricas.ordem_producao}
                        metaProducao={metricas.meta_producao}
                        toneladasProduzidasOP={metricas.toneladas_produzidas_op}
                        projecao={metricas.projecao}
                      />
                    </div>
                    <Button
                      onClick={() => navigate(`/linha-management/${linha.linha_id}`)}
                      className="h-fit"
                      title="Abrir gerenciamento detalhado da linha"
                    >
                      <ExternalLink className="w-4 h-4 mr-2" />
                      Gerenciar
                    </Button>
                  </div>

                  {/* Equipment Cards - Grid de equipamentos */}
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    {linha.equipamentos.map((eq) => (
                      <EquipamentoCard
                        key={eq.id}
                        id={eq.id}
                        nome={eq.nome}
                        tipo={eq.tipo}
                        // Estado vem da API de Equipamento
                        estado={eq.medicoes?.estado || eq.status}
                        // Velocidade vem da API de Equipamento
                        velocidadeAtual={eq.medicoes?.velocidade_atual}
                        velocidadePadrao={eq.velocidade_nominal}

                        // Dados de Produção vêm da API de Operação
                        pecasBoas={eq.medicoes?.produzido_op} // Usamos o produzido_op (acumulado da OP)
                        pecasRuins={eq.medicoes?.pecas_ruins}

                        // OEE (Se não tiver calculado na API, o Card pode calcular ou mostramos 0)
                        oee={0}
                        metaOEE={eq.meta_oee}

                        // Dados de Contexto (Operação)
                        sku={eq.medicoes?.sku_codigo}
                        descricao={eq.medicoes?.descricao}
                        ordemProducao={eq.medicoes?.ordem_producao}
                        cuc={eq.medicoes?.cuc} // Passando CUC (novo)
                        planejado={eq.medicoes?.planejado_op} // Passando Meta (novo)
                        diferenca={eq.medicoes?.diferenca_op} // Passando Diferença (novo)
                      />
                    ))}
                  </div>

                  {/* Timeline Multi-Equipamento */}
                  <MultiEquipmentTimeline
                    linhaId={linha.linha_id}
                    linhaNome={linha.linha_nome}
                    equipamentos={linha.equipamentos}
                  />
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}