import React from "react";
import { useNavigate } from "react-router-dom";
import { Activity, Zap, Scale, Gauge, Box, TrendingUp } from "lucide-react";
import { safeNumber, safeString } from "@/utils/dataValidation";

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
  projecao?: number;
}

const LineOverview: React.FC<LineOverviewProps> = (props) => {
  // Normalizar e validar props
  const nome = safeString(props.nome, 'Linha Desconhecida');
  const ole = safeNumber(props.ole, 0);
  const totalEquipamentos = safeNumber(props.totalEquipamentos, 0);
  const equipamentosOnline = safeNumber(props.equipamentosOnline, 0);
  const producaoReal = safeNumber(props.producaoReal, 0);
  const producaoEsperada = safeNumber(props.producaoEsperada, 0);
  const metaTotal = safeNumber(props.metaTotal, 0);
  const vazaoTurno = safeNumber(props.vazaoTurno, 0);
  const formatoAtual = props.formatoAtual ? safeNumber(props.formatoAtual, 0) : undefined;
  const sku = safeString(props.sku, 'N/A');
  const cuc = safeString(props.cuc, 'N/A');
  const descricao = safeString(props.descricao, 'Produto Genérico');
  const ordemProducao = safeString(props.ordemProducao, 'N/A');
  const projecao = props.projecao ? safeNumber(props.projecao, 0) : undefined;
  const navigate = useNavigate();

  const getOLEColor = (valor: number): string => {
    if (valor >= 85) return 'text-green-600 dark:text-green-400';
    if (valor >= 70) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  const calculateProgress = (valor: number, meta: number): number => {
    if (!meta || meta === 0) return 0;
    const percent = (valor / meta) * 100;
    return Math.min(Math.max(percent, 0), 100); // Clamp entre 0 e 100
  };

  const percentualOnline = totalEquipamentos > 0
    ? (equipamentosOnline / totalEquipamentos) * 100
    : 0;

  const diferenca = producaoReal - producaoEsperada;
  const isPositive = diferenca >= 0;

  // Cálculo da Projeção Estimada baseada no OLE atual
  // Se mantivermos a eficiência atual (OLE), quanto produziremos?
  // Projeção = Meta * (OLE / 100)
  // FIX: Se recebermos projecao do backend (mais preciso), usamos.
  const projecaoEstimada = projecao && projecao > 0
    ? projecao
    : (metaTotal > 0 ? metaTotal * (ole / 100) : 0);

  return (
    <div
      onClick={() => navigate(`/linha/${encodeURIComponent(nome)}/detalhes`)}
      className="bg-gradient-to-r from-neutral-50 to-neutral-100 dark:from-neutral-800 dark:to-neutral-900 border border-neutral-300 dark:border-neutral-700 rounded-lg shadow-md p-6 cursor-pointer hover:shadow-lg transition-shadow"
    >

      {/* SEÇÃO SUPERIOR: KPI's Principais */}
      <div className="space-y-4">

        {/* Linha 1: Identificação e OLE */}
        <div className="flex justify-between items-start">

          {/* Esquerda: Identificação */}
          <div className="flex flex-col gap-1 min-w-0">
            <div className="flex items-center gap-3">
              <div className={`p-2 ${percentualOnline === 0 ? 'bg-red-100 dark:bg-red-900/30' : 'bg-blue-100 dark:bg-blue-900/30'} rounded-lg flex-shrink-0 animate-pulse`}>
                {percentualOnline === 0 ? (
                  <Activity className="w-5 h-5 text-red-600 dark:text-red-400" />
                ) : (
                  <Activity className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                )}
              </div>
              <div>
                <h2 className="text-xl font-bold text-neutral-900 dark:text-neutral-100 truncate">
                  {nome}
                </h2>
                {percentualOnline === 0 && (
                  <span className="text-xs font-bold text-red-600 dark:text-red-400 uppercase tracking-wider">
                    OFFLINE / ERRO DE COMUNICAÇÃO
                  </span>
                )}
              </div>
            </div>

            {/* Subtitle Info Group */}
            <div className="flex flex-wrap items-center gap-2 text-xs mt-1">
              {ordemProducao && ordemProducao !== 'N/A' && (
                <span className="px-1.5 py-0.5 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 rounded border border-blue-100 dark:border-blue-800 font-medium whitespace-nowrap">
                  OP: {ordemProducao.replace(/^0+/, '')}
                </span>
              )}

              {sku && sku !== 'N/A' && (
                <span className="text-neutral-500 whitespace-nowrap">
                  | SKU: {sku}
                </span>
              )}
            </div>
            <div className="text-xs text-neutral-500 truncate" title={descricao}>
              {descricao || 'Produto Genérico'}
            </div>
          </div>

          {/* Direita: OLE */}
          <div className="text-right flex-shrink-0 ml-4">
            <div className="flex items-center gap-1.5 justify-end mb-1 text-neutral-500">
              <Zap className="w-3.5 h-3.5" />
              <span className="text-[10px] font-bold uppercase tracking-wider">OLE</span>
            </div>
            <div className={`text-3xl font-bold ${getOLEColor(ole)}`}>
              {ole.toFixed(1)}%
            </div>

            <div className="flex items-center justify-end gap-1.5 mt-1">
              <div className={`w-1.5 h-1.5 rounded-full ${percentualOnline > 0 ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-[10px] text-neutral-500 font-medium">
                {equipamentosOnline}/{totalEquipamentos} EQ
              </span>
            </div>
          </div>
        </div>

        {/* Linha 3: Grid de Métricas Compacto */}
        <div className="grid grid-cols-3 gap-2 p-3 bg-neutral-100/50 dark:bg-neutral-800/30 rounded-lg border border-neutral-200 dark:border-neutral-700">
          {/* Formato */}
          <div className="text-center">
            <div className="flex items-center justify-center gap-1 text-[10px] text-neutral-500 uppercase mb-0.5">
              <Box className="w-3 h-3" />
              <span>Formato</span>
            </div>
            <div className="font-semibold text-neutral-800 dark:text-neutral-200 text-sm">
              {formatoAtual ? `${formatoAtual}g` : '--'}
            </div>
          </div>

          {/* Produzido */}
          <div className="text-center border-l border-neutral-200 dark:border-neutral-700">
            <div className="flex items-center justify-center gap-1 text-[10px] text-neutral-500 uppercase mb-0.5">
              <Scale className="w-3 h-3" />
              <span>Real</span>
            </div>
            <div className="font-semibold text-neutral-800 dark:text-neutral-200 text-sm">
              {producaoReal.toFixed(3)} t
            </div>
          </div>

          {/* Vazão */}
          <div className="text-center border-l border-neutral-200 dark:border-neutral-700">
            <div className="flex items-center justify-center gap-1 text-[10px] text-neutral-500 uppercase mb-0.5">
              <Gauge className="w-3 h-3" />
              <span>Vazão</span>
            </div>
            <div className="font-semibold text-neutral-800 dark:text-neutral-200 text-sm">
              {vazaoTurno.toFixed(1)} t/h
            </div>
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