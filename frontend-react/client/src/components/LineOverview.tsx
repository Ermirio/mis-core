import React from "react";
import { Activity, Zap, Scale, Gauge, Box, TrendingUp, AlertCircle } from "lucide-react";

/**
 * LineOverview - Visão consolidada de uma linha de produção
 * 
 * Design ISA 101: Grande, claro, foco no KPI principal
 * Inclui barras de status visual para andamento da produção
 */

interface LineOverviewProps {
  nome: string;
  oee: number;
  totalEquipamentos: number;
  equipamentosOnline: number;
  toneladasTurno?: number;
  toneladasProduzidasOP?: number;
  vazaoTurno?: number;
  formatoAtual?: number;
  sku?: string;
  descricao?: string;
  ordemProducao?: string;
  metaProducao?: number;
  disponibilidade?: number;
  performance?: number;
  qualidade?: number;
}

const LineOverview: React.FC<LineOverviewProps> = ({
  nome,
  oee = 0,
  totalEquipamentos,
  equipamentosOnline,
  toneladasTurno = 0,
  toneladasProduzidasOP = 0,
  vazaoTurno = 0,
  formatoAtual,
  sku,
  descricao,
  ordemProducao,
  metaProducao = 0,
  disponibilidade = 0,
  performance = 0,
  qualidade = 0,
}) => {
  /**
   * Determina cor do OEE baseado em thresholds industriais
   */
  const getOEEColor = (valor: number): string => {
    if (valor >= 85) return "text-green-600 dark:text-green-400";
    if (valor >= 70) return "text-yellow-600 dark:text-yellow-400";
    return "text-red-600 dark:text-red-400";
  };

  /**
   * Calcula percentual de produção realizada vs meta
   */
  const percentualProducao = metaProducao > 0 ? (toneladasProduzidasOP / metaProducao) * 100 : 0;
  const percentualProducaoLimitado = Math.min(100, percentualProducao);

  /**
   * Status dos equipamentos
   */
  const percentualOnline = totalEquipamentos > 0 ? (equipamentosOnline / totalEquipamentos) * 100 : 0;

  /**
   * Determina cor da barra de produção
   */
  const getBarColor = (percentual: number): string => {
    if (percentual >= 100) return "bg-green-500";
    if (percentual >= 80) return "bg-green-400";
    if (percentual >= 60) return "bg-yellow-500";
    if (percentual >= 40) return "bg-orange-500";
    return "bg-red-500";
  };

  return (
    <div className="bg-gradient-to-r from-neutral-50 to-neutral-100 dark:from-neutral-800 dark:to-neutral-900 border border-neutral-300 dark:border-neutral-700 rounded-lg shadow-md p-6">
      {/* Seção Superior: Identificação e OEE Principal */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-6 pb-6 border-b border-neutral-300 dark:border-neutral-700">
        {/* Coluna Esquerda: Nome da Linha */}
        <div className="flex items-center gap-4">
          <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
            <Activity className="w-8 h-8 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-neutral-900 dark:text-neutral-100">{nome}</h2>
            <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1">
              {equipamentosOnline}/{totalEquipamentos} equipamentos online
            </p>
          </div>
        </div>

        {/* Coluna Direita: OEE Principal (Grande e Destacado) */}
        <div className="flex flex-col items-center justify-center p-4 bg-white dark:bg-neutral-900/50 rounded-lg border border-neutral-200 dark:border-neutral-700">
          <div className="text-sm font-medium text-neutral-600 dark:text-neutral-400 mb-1">OEE da Linha</div>
          <div className={`text-4xl font-bold ${getOEEColor(oee)}`}>{oee.toFixed(1)}%</div>
          <div className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">Meta: 85%</div>
        </div>
      </div>

      {/* Seção de Ordem de Produção e SKU */}
      {ordemProducao && (
        <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* OP */}
            <div>
              <span className="text-xs font-bold px-2 py-1 bg-blue-600 text-white rounded inline-block mb-2">
                OP
              </span>
              <div className="text-lg font-bold text-blue-900 dark:text-blue-100">
                {ordemProducao.replace(/^0+/, "")}
              </div>
            </div>

            {/* SKU */}
            {sku && (
              <div>
                <span className="text-xs font-bold text-neutral-600 dark:text-neutral-400 block mb-1">SKU</span>
                <div className="text-lg font-bold text-neutral-900 dark:text-neutral-100">{sku}</div>
                {descricao && (
                  <p className="text-xs text-neutral-600 dark:text-neutral-400 mt-1">{descricao}</p>
                )}
              </div>
            )}

            {/* Formato */}
            {formatoAtual && (
              <div>
                <span className="text-xs font-bold text-neutral-600 dark:text-neutral-400 block mb-1">Formato</span>
                <div className="text-lg font-bold text-neutral-900 dark:text-neutral-100">
                  {formatoAtual.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })} g
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Seção de Barras de Status - ISA 101 */}
      <div className="space-y-4 mb-6">
        {/* Barra 1: Produção da OP */}
        {metaProducao > 0 && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Box className="w-4 h-4 text-neutral-600 dark:text-neutral-400" />
                <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300">Produção da OP</span>
              </div>
              <span className="text-sm font-bold text-neutral-900 dark:text-neutral-100">
                {toneladasProduzidasOP.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} / {metaProducao.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} ton
              </span>
            </div>
            <div className="h-3 bg-neutral-300 dark:bg-neutral-700 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all ${getBarColor(percentualProducaoLimitado)}`}
                style={{ width: `${percentualProducaoLimitado}%` }}
              />
            </div>
            <div className="text-xs text-neutral-500 dark:text-neutral-400 text-right mt-1">
              {percentualProducaoLimitado.toFixed(0)}% concluído
            </div>
          </div>
        )}

        {/* Barra 2: Produção do Turno */}
        {toneladasTurno > 0 && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-neutral-600 dark:text-neutral-400" />
                <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300">Produção do Turno</span>
              </div>
              <span className="text-sm font-bold text-neutral-900 dark:text-neutral-100">
                {toneladasTurno.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} ton
              </span>
            </div>
            <div className="h-3 bg-neutral-300 dark:bg-neutral-700 rounded-full overflow-hidden">
              <div className="h-full bg-green-500 w-3/4" />
            </div>
          </div>
        )}

        {/* Barra 3: Disponibilidade */}
        {disponibilidade > 0 && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-neutral-600 dark:text-neutral-400" />
                <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300">Disponibilidade</span>
              </div>
              <span className="text-sm font-bold text-neutral-900 dark:text-neutral-100">
                {disponibilidade.toFixed(1)}%
              </span>
            </div>
            <div className="h-2 bg-neutral-300 dark:bg-neutral-700 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all ${disponibilidade >= 80 ? "bg-green-500" : disponibilidade >= 60 ? "bg-yellow-500" : "bg-red-500"}`}
                style={{ width: `${Math.min(100, disponibilidade)}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Seção Inferior: KPIs Secundários */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* KPI: Vazão */}
        {vazaoTurno > 0 && (
          <div className="p-3 bg-white dark:bg-neutral-900/50 rounded border border-neutral-200 dark:border-neutral-700">
            <div className="text-xs text-neutral-600 dark:text-neutral-400 font-medium mb-1">Vazão</div>
            <div className="text-lg font-bold text-neutral-900 dark:text-neutral-100">
              {vazaoTurno.toFixed(1)} ton/h
            </div>
          </div>
        )}

        {/* KPI: Performance */}
        {performance > 0 && (
          <div className="p-3 bg-white dark:bg-neutral-900/50 rounded border border-neutral-200 dark:border-neutral-700">
            <div className="text-xs text-neutral-600 dark:text-neutral-400 font-medium mb-1">Performance</div>
            <div className="text-lg font-bold text-neutral-900 dark:text-neutral-100">
              {performance.toFixed(1)}%
            </div>
          </div>
        )}

        {/* KPI: Qualidade */}
        {qualidade > 0 && (
          <div className="p-3 bg-white dark:bg-neutral-900/50 rounded border border-neutral-200 dark:border-neutral-700">
            <div className="text-xs text-neutral-600 dark:text-neutral-400 font-medium mb-1">Qualidade</div>
            <div className="text-lg font-bold text-neutral-900 dark:text-neutral-100">
              {qualidade.toFixed(1)}%
            </div>
          </div>
        )}

        {/* KPI: Status */}
        <div className="p-3 bg-white dark:bg-neutral-900/50 rounded border border-neutral-200 dark:border-neutral-700">
          <div className="text-xs text-neutral-600 dark:text-neutral-400 font-medium mb-1">Status</div>
          <div className={`text-lg font-bold ${percentualOnline === 100 ? "text-green-600 dark:text-green-400" : percentualOnline >= 75 ? "text-yellow-600 dark:text-yellow-400" : "text-red-600 dark:text-red-400"}`}>
            {percentualOnline.toFixed(0)}%
          </div>
        </div>
      </div>
    </div>
  );
};

export default LineOverview;
