import React from "react";
import { useNavigate } from "react-router-dom";
import { Activity, Zap, Scale, Gauge, Box, TrendingUp } from "lucide-react";

/**
 * LineOverview - Visão consolidada de uma linha de produção
 * Versão: 3.1 (OLE Oficial + Projeção Restaurada)
 */

interface LineOverviewProps {
  nome: string;
  ole: number;
  totalEquipamentos: number;
  equipamentosOnline: number;

  // Novos Campos OLE
  producaoReal?: number;
  producaoEsperada?: number;
  metaTotal?: number;

  // Campos Legados (Mantidos para compatibilidade visual se necessário)
  toneladasTurno?: number;
  vazaoTurno?: number;
  formatoAtual?: number;
  sku?: string;
  cuc?: string;
  descricao?: string;
  ordemProducao?: string;
  metaProducao?: number;
  toneladasProduzidasOP?: number;
  diferencaOP?: number;
  projecao?: any;
}

const LineOverview: React.FC<LineOverviewProps> = ({
  nome,
  ole,
  totalEquipamentos,
  equipamentosOnline,
  producaoReal = 0,
  producaoEsperada = 0,
  metaTotal = 0,
  vazaoTurno = 0,
  formatoAtual,
  sku,
  cuc,
  descricao,
  ordemProducao,
}) => {
  const navigate = useNavigate();

  const getOLEColor = (valor: number): string => {
    if (valor >= 85) return 'text-green-600 dark:text-green-400';
    if (valor >= 70) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  const calculateProgress = (valor: number, meta: number): number => {
    if (!meta || meta === 0) return 0;
    const percent = (valor / meta) * 100;
    return Math.min(percent, 100);
  };

  const percentualOnline = totalEquipamentos > 0
    ? (equipamentosOnline / totalEquipamentos) * 100
    : 0;

  const diferenca = producaoReal - producaoEsperada;
  const isPositive = diferenca >= 0;

  // Cálculo da Projeção Estimada baseada no OLE atual
  // Se mantivermos a eficiência atual (OLE), quanto produziremos?
  // Projeção = Meta * (OLE / 100)
  const projecaoEstimada = metaTotal > 0 ? metaTotal * (ole / 100) : 0;

  return (
    <div
      onClick={() => navigate(`/linha/${nome}/detalhes`)}
      className="bg-gradient-to-r from-neutral-50 to-neutral-100 dark:from-neutral-800 dark:to-neutral-900 border border-neutral-300 dark:border-neutral-700 rounded-lg shadow-md p-6 cursor-pointer hover:shadow-lg transition-shadow"
    >

      {/* SEÇÃO SUPERIOR: KPI's Principais */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">

        {/* Coluna 1: Identificação e Status */}
        <div className="flex items-center gap-4">
          <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
            <Activity className="w-8 h-8 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-neutral-900 dark:text-neutral-100">
              {nome}
            </h2>

            {/* OP, CUC e Meta */}
            {ordemProducao && ordemProducao !== 'N/A' && (
              <div className="flex items-center gap-3 mt-2 mb-1 p-2 bg-blue-50 dark:bg-blue-900/20 rounded border border-blue-200 dark:border-blue-800">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold px-2 py-1 bg-blue-600 text-white rounded">
                    OP
                  </span>
                  <span className="text-sm font-bold text-blue-900 dark:text-blue-100">
                    {ordemProducao.replace(/^0+/, '')}
                  </span>
                </div>

                {cuc && cuc !== 'N/A' && (
                  <div className="flex items-center gap-1 border-l border-blue-300 dark:border-blue-700 pl-2">
                    <span className="text-xs text-neutral-500 font-semibold">CUC:</span>
                    <span className="text-sm font-bold text-neutral-700 dark:text-neutral-300">{cuc}</span>
                  </div>
                )}
              </div>
            )}

            {/* SKU e Descrição */}
            <div className="flex flex-col mt-1 mb-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold px-2 py-0.5 bg-neutral-200 dark:bg-neutral-700 rounded text-neutral-800 dark:text-neutral-200">
                  SKU: {sku && sku !== 'N/A' ? sku : '-'}
                </span>
                <span className="text-base text-neutral-700 dark:text-neutral-300 font-medium truncate max-w-[400px]" title={descricao}>
                  <span className="font-bold mr-1">Produto:</span>
                  {descricao || '-'}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2 mt-1">
              <div className={`w-2.5 h-2.5 rounded-full ${percentualOnline > 0 ? 'bg-green-500' : 'bg-red-500'}`} />
              <p className="text-sm text-neutral-600 dark:text-neutral-400">
                {equipamentosOnline} de {totalEquipamentos} online
              </p>
            </div>
          </div>
        </div>

        {/* Coluna 2: Métricas de Produção */}
        <div className="flex-1 grid grid-cols-3 gap-4 border-l border-r border-neutral-200 dark:border-neutral-700 px-6 mx-2">
          <div className="flex flex-col items-center justify-center text-center">
            <div className="flex items-center gap-1.5 mb-1 text-neutral-500 dark:text-neutral-400">
              <Box className="w-4 h-4" />
              <span className="text-xs font-medium uppercase tracking-wide">Formato</span>
            </div>
            <span className="text-lg font-semibold text-neutral-800 dark:text-neutral-200">
              {formatoAtual ? `${formatoAtual}g` : '--'}
            </span>
          </div>

          <div className="flex flex-col items-center justify-center text-center">
            <div className="flex items-center gap-1.5 mb-1 text-neutral-500 dark:text-neutral-400">
              <Scale className="w-4 h-4" />
              <span className="text-xs font-medium uppercase tracking-wide">Produzido (t)</span>
            </div>
            <span className="text-lg font-semibold text-neutral-800 dark:text-neutral-200">
              {producaoReal.toFixed(3)} t
            </span>
          </div>

          <div className="flex flex-col items-center justify-center text-center">
            <div className="flex items-center gap-1.5 mb-1 text-neutral-500 dark:text-neutral-400">
              <Gauge className="w-4 h-4" />
              <span className="text-xs font-medium uppercase tracking-wide">Vazão (t/h)</span>
            </div>
            <span className="text-lg font-semibold text-neutral-800 dark:text-neutral-200">
              {vazaoTurno.toFixed(1)}
            </span>
          </div>
        </div>

        {/* Coluna 3: OLE Principal */}
        <div className="text-right min-w-[120px]">
          <div className="flex items-center gap-2 justify-end mb-1">
            <Zap className="w-5 h-5 text-neutral-500" />
            <span className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
              OLE (OMAC)
            </span>
          </div>
          <div className={`text-5xl font-bold ${getOLEColor(ole)}`}>
            {ole.toFixed(1)}%
          </div>
        </div>
      </div>

      {/* SEÇÃO INFERIOR: Monitoramento de Produção (OLE & Projeção) */}
      <div className="mt-4 pt-4 border-t border-neutral-200 dark:border-neutral-800">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-neutral-500" />
            <span className="text-xs font-medium text-neutral-500 uppercase">Progresso e Projeção</span>
          </div>
          <span className={`text-xs font-bold px-2 py-0.5 rounded ${isPositive ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
            {isPositive ? 'Adiantado' : 'Atrasado'} ({diferenca > 0 ? '+' : ''}{diferenca.toFixed(2)} t)
          </span>
        </div>

        <div className="space-y-3">
          {/* 1. Produção Real */}
          <div className="relative">
            <div className="flex justify-between text-xs mb-1">
              <span className="font-medium text-neutral-700 dark:text-neutral-300">Produção Real</span>
              <span className="font-bold text-blue-600 dark:text-blue-400">{producaoReal.toFixed(3)} t</span>
            </div>
            <div className="h-3 bg-neutral-100 dark:bg-neutral-800 rounded-full overflow-hidden" title={`Meta: ${metaTotal.toFixed(1)} t`}>
              <div
                className="h-full bg-blue-600 rounded-full transition-all duration-500"
                style={{ width: `${calculateProgress(producaoReal, metaTotal)}%` }}
              />
            </div>
          </div>

          {/* 2. Produção Esperada (Até Agora) */}
          <div className="relative">
            <div className="flex justify-between text-xs mb-1">
              <span className="font-medium text-neutral-600 dark:text-neutral-400">Esperado (Até Agora)</span>
              <span className="font-bold text-neutral-600 dark:text-neutral-400">
                {producaoEsperada.toFixed(3)} t
              </span>
            </div>
            <div className="h-3 bg-neutral-100 dark:bg-neutral-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-neutral-400 dark:bg-neutral-600 rounded-full transition-all duration-500"
                style={{ width: `${calculateProgress(producaoEsperada, metaTotal)}%` }}
              />
            </div>
          </div>

          {/* 3. Projeção (Estimada com base no OLE atual) */}
          {producaoEsperada > 0 && (
            <div className="relative">
              <div className="flex justify-between text-xs mb-1">
                <span className="font-medium text-neutral-500 dark:text-neutral-500">Projeção (Fim do Turno)</span>
                <span className={`font-bold ${ole >= 100 ? 'text-green-600' : 'text-yellow-600'}`}>
                  {projecaoEstimada.toFixed(1)} t
                </span>
              </div>
              <div className="h-3 bg-neutral-100 dark:bg-neutral-800 rounded-full overflow-hidden">
                <div
                  className={`h-full ${ole >= 100 ? 'bg-green-500/50' : 'bg-yellow-500/50'} rounded-full transition-all duration-500`}
                  style={{ width: `${calculateProgress(projecaoEstimada, metaTotal)}%` }}
                />
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end mt-2 text-xs text-neutral-500 border-t border-neutral-100 dark:border-neutral-800 pt-2 gap-4">
          <span>Meta Total do Turno: <span className="font-bold text-neutral-700 dark:text-neutral-300">{metaTotal.toFixed(1)} t</span></span>
        </div>
      </div>

    </div>
  );
};

export default LineOverview;