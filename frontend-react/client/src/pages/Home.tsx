import React, { useState, useEffect } from "react";
import EquipamentoCard from "@/components/EquipamentoCard";
import LineOverview from "@/components/LineOverview";
import { Button } from "@/components/ui/button";
import { Moon, Sun, RefreshCw, AlertCircle } from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";
import { APP_TITLE } from "@/const";

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
  medicoes?: {
    estado?: number | string;
    velocidade_atual?: number;
    oee?: number;
  };
  status_realtime?: string;
}

interface LinhaMetricas {
  linha_id: number;
  linha_nome: string;
  oee: number;
  sku_codigo: string | null;
  sku_descricao: string | null;
  ordem_producao: string | null;
  formato_gramas: number;
  toneladas_produzidas_turno: number;
  toneladas_produzidas_op: number;
  meta_producao: number;
  vazao_real_ton_hora: number;
  disponibilidade: number;
  performance: number;
  qualidade: number;
  equipamentos_online: number;
  total_equipamentos: number;
}

interface LinhaAgrupada {
  linha_id: number;
  linha_nome: string;
  equipamentos: EquipamentoConfig[];
  metricas: LinhaMetricas;
}

const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || "http://127.0.0.1:8000/api";

export default function Home() {
  const { theme, toggleTheme } = useTheme();
  const [linhas, setLinhas] = useState<LinhaAgrupada[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  // Busca configuração dos equipamentos do Django
  const fetchEquipamentos = async (): Promise<EquipamentoConfig[]> => {
    const response = await fetch(`${DJANGO_API_URL}/equipamentos/`);
    if (!response.ok) throw new Error(`Erro HTTP ${response.status} ao buscar equipamentos.`);
    const data = await response.json();
    return data.results || data;
  };

  // Busca status em tempo real e estado numérico dos equipamentos
  const fetchEquipamentosComStatus = async (): Promise<EquipamentoConfig[]> => {
    const response = await fetch(`${DJANGO_API_URL}/full_equipment_status/`);
    if (!response.ok) throw new Error(`Erro HTTP ${response.status} ao buscar status.`);
    return await response.json();
  };

  // Busca métricas consolidadas da linha
  const fetchMetricasLinha = async (linhaId: number): Promise<LinhaMetricas | null> => {
    try {
      const response = await fetch(`${DJANGO_API_URL}/metricas_linha_consolidadas/?linha_id=${linhaId}`);
      if (!response.ok) return null;
      const data = await response.json();
      return data.metricas && data.metricas.length > 0 ? data.metricas[0] : null;
    } catch (err) {
      console.error(`Erro ao buscar métricas da linha ${linhaId}:`, err);
      return null;
    }
  };

  const fetchDados = async () => {
    try {
      setError(null);
      setLoading(true);

      // 1. Busca equipamentos com status em tempo real (inclui estado numérico 0-9)
      const equipamentosComStatus = await fetchEquipamentosComStatus();
      if (!equipamentosComStatus || equipamentosComStatus.length === 0) {
        setError("Nenhum equipamento configurado no sistema.");
        setLinhas([]);
        return;
      }

      // 2. Agrupa equipamentos por linha
      const linhasMap = new Map<number, LinhaAgrupada>();
      for (const eq of equipamentosComStatus) {
        if (!linhasMap.has(eq.linha)) {
          linhasMap.set(eq.linha, {
            linha_id: eq.linha,
            linha_nome: eq.linha_nome,
            equipamentos: [],
            metricas: {} as LinhaMetricas,
          });
        }
        linhasMap.get(eq.linha)!.equipamentos.push(eq);
      }

      // 3. Busca métricas consolidadas para cada linha
      const linhasArray = Array.from(linhasMap.values());
      for (const linha of linhasArray) {
        const metricas = await fetchMetricasLinha(linha.linha_id);
        if (metricas) {
          linha.metricas = metricas;
          // Atualiza contagem de equipamentos online (baseado no status_realtime)
          linha.metricas.equipamentos_online = linha.equipamentos.filter(eq => eq.status_realtime === 'online').length;
          linha.metricas.total_equipamentos = linha.equipamentos.length;
        }
      }

      // 4. Ordena equipamentos por ordem_na_linha
      linhasArray.forEach(linha => {
        linha.equipamentos.sort((a, b) => (a.ordem_na_linha || 0) - (b.ordem_na_linha || 0));
      });

      setLinhas(linhasArray);
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
    const interval = setInterval(fetchDados, 5000); // Atualiza a cada 5 segundos
    return () => clearInterval(interval);
  }, []);

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
            {linhas.map((linha) => (
              <div key={linha.linha_id} className="space-y-4">
                <LineOverview
                  nome={linha.linha_nome}
                  oee={linha.metricas.oee || 0}
                  totalEquipamentos={linha.metricas.total_equipamentos || 0}
                  equipamentosOnline={linha.metricas.equipamentos_online || 0}
                  toneladasTurno={linha.metricas.toneladas_produzidas_turno || 0}
                  toneladasProduzidasOP={linha.metricas.toneladas_produzidas_op || 0}
                  vazaoTurno={linha.metricas.vazao_real_ton_hora || 0}
                  formatoAtual={linha.metricas.formato_gramas || 0}
                  sku={linha.metricas.sku_codigo}
                  descricao={linha.metricas.sku_descricao}
                  ordemProducao={linha.metricas.ordem_producao}
                  metaProducao={linha.metricas.meta_producao || 0}
                  disponibilidade={linha.metricas.disponibilidade || 0}
                  performance={linha.metricas.performance || 0}
                  qualidade={linha.metricas.qualidade || 0}
                />
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {linha.equipamentos.map((eq) => (
                    <EquipamentoCard
                      key={eq.id}
                      id={eq.id}
                      nome={eq.nome}
                      tipo={eq.tipo}
                      estado={eq.medicoes?.estado || eq.status_realtime || "offline"}
                      velocidadeAtual={eq.medicoes?.velocidade_atual}
                      velocidadePadrao={eq.velocidade_nominal}
                      oee={eq.medicoes?.oee}
                      metaOEE={eq.meta_oee}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
