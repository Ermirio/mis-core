import React, { useEffect, useState } from "react";
import EquipamentoCard from "@/components/EquipamentoCard";
import LineOverview from "@/components/LineOverview";
import { Button } from "@/components/ui/button";
import { Moon, Sun, RefreshCw, AlertCircle } from "lucide-react";
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
  ordem_na_linha?: number;
  velocidade_nominal: number;
  velocidade_maxima: number;
  meta_oee: number;
  temperatura_min?: number;
  temperatura_max?: number;
  pressao_min?: number;
  pressao_max?: number;
}

interface MedicoesTempoReal {
  equipamento: string;
  status: string;
  timestamp: string;
  medicoes: {
    velocidade_atual?: number;
    temperatura?: number;
    pressao?: number;
    contagem?: number;
    contagem_entrada?: number;
    contagem_saida?: number;
    descarte?: number;
    percentual_descarte?: number;
    estado?: string;
    oee?: number;
  };
}

interface EquipamentoCompleto extends EquipamentoConfig {
  medicoes?: MedicoesTempoReal['medicoes'];
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
  const { theme, toggleTheme } = useTheme();
  const [linhas, setLinhas] = useState<LinhaAgrupada[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [metricasConsolidadas, setMetricasConsolidadas] = useState<Record<number, any>>({});

  const fetchConfiguracao = async (): Promise<EquipamentoConfig[]> => {
    const response = await fetch(`${DJANGO_API_URL}/equipamentos/`);
    if (!response.ok) throw new Error(`Erro HTTP ${response.status} ao buscar configuração.`);
    const data = await response.json();
    return data.results || data;
  };

  const fetchTempoReal = async (nomeEquipamento: string): Promise<MedicoesTempoReal | null> => {
    try {
      const response = await fetch(`${FLASK_API_URL}/realtime/status/${nomeEquipamento}`);
      if (!response.ok) return null;
      return await response.json();
    } catch (err) {
      console.warn(`Falha ao buscar dados de tempo real para ${nomeEquipamento}:`, err);
      return null;
    }
  };

  const fetchMetricasConsolidadas = async (linhaId: number): Promise<any | null> => {
    try {
      const response = await fetch(`${DJANGO_API_URL}/metricas_linha_consolidadas/?linha_id=${linhaId}&periodo=TURNO`);
      if (!response.ok) return null;
      const data = await response.json();
      // A API retorna uma lista, pegamos o primeiro (mais recente)
      return data.metricas && data.metricas.length > 0 ? data.metricas[0] : {};
    } catch (err) {
      console.error(`Falha ao buscar métricas consolidadas para linha ${linhaId}:`, err);
      return null;
    }
  };

  const fetchDados = async () => {
    try {
      setError(null);

      // 1. Busca configuração do Django
      const configuracoes = await fetchConfiguracao();
      if (!configuracoes || configuracoes.length === 0) {
        setError("Nenhum equipamento configurado no sistema.");
        setLinhas([]);
        return;
      }

      // 2. Busca dados de tempo real do Flask para cada equipamento
      const tempoRealPromises = configuracoes.map(config => fetchTempoReal(config.codigo));
      const temposReais = await Promise.all(tempoRealPromises);

      // 3. Combina configuração com dados de tempo real
      const equipamentosCompletos = configuracoes.map((config, index) => {
        const tempoReal = temposReais[index];
        const temDadosValidos = tempoReal?.status === 'online';
        return {
          ...config,
          medicoes: temDadosValidos ? tempoReal.medicoes : undefined,
          status: tempoReal?.status || 'offline',
          timestamp: tempoReal?.timestamp,
        } as EquipamentoCompleto;
      });

      // 4. Agrupa por linha
      const linhasMap = new Map<number, LinhaAgrupada>();
      equipamentosCompletos.forEach(eq => {
        if (!linhasMap.has(eq.linha)) {
          linhasMap.set(eq.linha, {
            linha_id: eq.linha,
            linha_nome: eq.linha_nome,
            equipamentos: [],
          });
        }
        linhasMap.get(eq.linha)!.equipamentos.push(eq);
      });

      const linhasArray = Array.from(linhasMap.values());
      linhasArray.forEach(linha => {
        linha.equipamentos.sort((a, b) => (a.ordem_na_linha || 0) - (b.ordem_na_linha || 0));
      });

      // 5. Busca métricas consolidadas para cada linha
      const metricasPromises = linhasArray.map(linha => fetchMetricasConsolidadas(linha.linha_id));
      const metricasResultados = await Promise.all(metricasPromises);

      const novasMetricas: Record<number, any> = {};
      metricasResultados.forEach((resultado, index) => {
        const linhaId = linhasArray[index].linha_id;
        if (resultado) {
          novasMetricas[linhaId] = resultado;
        }
      });

      setLinhas(linhasArray);
      setMetricasConsolidadas(novasMetricas);
      setLastUpdate(new Date());

    } catch (error) {
      console.error("Erro ao buscar dados:", error);
      setError(error instanceof Error ? error.message : "Erro ao carregar dados. Verifique se os serviços estão rodando.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDados();
    const interval = setInterval(fetchDados, 5000);
    return () => clearInterval(interval);
  }, []);

  const getMetricasLinha = (linhaId: number) => {
    return metricasConsolidadas[linhaId] || {};
  };

  return (
    <div className="min-h-screen bg-neutral-100 dark:bg-neutral-900">
      <header className="border-b border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800">
        <div className="container mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-neutral-800 dark:text-neutral-100">{APP_TITLE}</h1>
            <p className="text-sm text-neutral-600 dark:text-neutral-400">Última atualização: {lastUpdate.toLocaleTimeString("pt-BR")}</p>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline" size="icon" onClick={fetchDados} title="Atualizar dados" className="border-neutral-300 dark:border-neutral-600">
              <RefreshCw className="w-4 h-4" />
            </Button>
            <Button variant="outline" size="icon" onClick={toggleTheme} title="Alternar tema" className="border-neutral-300 dark:border-neutral-600">
              {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-6 py-8">
        {loading && linhas.length === 0 ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4 text-neutral-500" />
              <p className="text-neutral-600 dark:text-neutral-400">Carregando dados...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center max-w-md">
              <AlertCircle className="w-12 h-12 mx-auto mb-4 text-red-500" />
              <p className="text-neutral-700 dark:text-neutral-300 text-lg mb-2">{error}</p>
              <Button onClick={fetchDados} variant="outline">Tentar Novamente</Button>
            </div>
          </div>
        ) : linhas.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-neutral-600 dark:text-neutral-400 text-lg">Nenhum equipamento encontrado. Configure equipamentos no Django Admin.</p>
          </div>
        ) : (
          <div className="space-y-10">
            {linhas.map((linha) => {
              const metricas = getMetricasLinha(linha.linha_id);
              return (
                <div key={linha.linha_id} className="space-y-4">
                  <LineOverview
                    nome={linha.linha_nome}
                    oee={metricas.oee}
                    totalEquipamentos={linha.equipamentos.length}
                    equipamentosOnline={linha.equipamentos.filter(eq => eq.status === 'online').length}
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
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    {linha.equipamentos.map((eq) => (
                      <EquipamentoCard
                        key={eq.id}
                        id={eq.id}
                        nome={eq.nome}
                        tipo={eq.tipo}
                        estado={eq.medicoes?.estado || eq.status}
                        velocidadeAtual={eq.medicoes?.velocidade_atual}
                        velocidadePadrao={eq.velocidade_nominal}
                        oee={eq.medicoes?.oee} // OEE do equipamento individual, se vier do coletor
                        contagem_entrada={eq.medicoes?.contagem_entrada}
                        contagem_saida={eq.medicoes?.contagem_saida}
                        pecasRuins={eq.medicoes?.descarte}
                        metaOEE={eq.meta_oee}
                      />
                    ))}
                  </div>
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
