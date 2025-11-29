import React from "react";
import { Activity, Zap, Scale, Gauge, Box } from "lucide-react";

/**
 * LineOverview - Visão consolidada de uma linha de produção
 * * Mostra o OEE agregado, status geral e Projeções de Turno.
 * Design ISA 101: Grande, claro, foco no KPI principal
 */

interface LineOverviewProps {
  nome: string;
  oee: number;
  totalEquipamentos: number;
  equipamentosOnline: number;
  toneladasTurno?: number;
  vazaoTurno?: number;
  formatoAtual?: number;
  sku?: string;
  descricao?: string;
  ordemProducao?: string;
  metaProducao?: number;
  toneladasProduzidasOP?: number;
  diferencaOP?: number; // <--- NOVO: Recebe a diferença já calculada do Backend
  projecao?: {
    produzido: number;
    meta: number;
    meta_atual?: number;
    projecao_realista: number;
    projecao_otimista: number;
    status: string;
  };
}

const LineOverview: React.FC<LineOverviewProps> = ({
  nome,
  oee,
  totalEquipamentos,
  equipamentosOnline,
  toneladasTurno = 0,
  vazaoTurno = 0,
  formatoAtual,
  sku,
  descricao,
  ordemProducao,
  metaProducao,
  toneladasProduzidasOP,
  diferencaOP, // Usar este valor se disponível
  projecao,
}) => {

  /**
   * Determina cor do OEE baseado em thresholds industriais
   */
  const getOEEColor = (valor: number): string => {
    if (valor >= 85) return 'text-green-600 dark:text-green-400';
    if (valor >= 70) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  const percentualOnline = totalEquipamentos > 0
    ? (equipamentosOnline / totalEquipamentos) * 100
    : 0;

  // Lógica de Diferença: Prioriza o dado do backend (diferencaOP)
  // Se não vier, calcula localmente como fallback
  const diffCalculado = diferencaOP !== undefined
    ? diferencaOP
    : (toneladasProduzidasOP || 0) - (metaProducao || 0);

  const isPositive = diffCalculado >= 0;

  return (
    <div className="bg-gradient-to-r from-neutral-50 to-neutral-100 dark:from-neutral-800 dark:to-neutral-900 border border-neutral-300 dark:border-neutral-700 rounded-lg shadow-md p-6">

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

            {/* OP e Meta - ISA 88: Rastreabilidade de Batch/Lote */}
            {ordemProducao && (
              <div className="flex items-center gap-3 mt-2 mb-1 p-2 bg-blue-50 dark:bg-blue-900/20 rounded border border-blue-200 dark:border-blue-800">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold px-2 py-1 bg-blue-600 text-white rounded">
                    OP
                  </span>
                  <span className="text-sm font-bold text-blue-900 dark:text-blue-100">
                    {ordemProducao.replace(/^0+/, '')}
                  </span>
                </div>
                {metaProducao !== undefined && metaProducao !== null && (
                  <div className="flex items-center gap-2 text-xs text-neutral-600 dark:text-neutral-400 border-l border-blue-300 dark:border-blue-700 pl-3">
                    <div className="flex items-center gap-1">
                      <span>Meta:</span>
                      <span className="font-semibold">{metaProducao.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} ton</span>
                    </div>

                    {/* Produzido na OP */}
                    <div className="flex items-center gap-1 border-l border-gray-300 dark:border-gray-700 pl-2">
                      <span>Prod:</span>
                      <span className="font-semibold">
                        {toneladasProduzidasOP?.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) || '0.0'} ton
                      </span>
                    </div>

                    {/* Diferença (Saldo) - Lógica atualizada */}
                    <div className={`flex items-center gap-1 border-l border-gray-300 dark:border-gray-700 pl-2 ${isPositive ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                      <span>Dif:</span>
                      <span className="font-semibold">
                        {isPositive ? '+' : ''}{diffCalculado.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} ton
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* SKU e Descrição */}
            <div className="flex flex-col mt-1 mb-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold px-2 py-0.5 bg-neutral-200 dark:bg-neutral-700 rounded text-neutral-800 dark:text-neutral-200">
                  SKU: {sku || '-'}
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

        {/* Coluna 2: Métricas de Produção (Tonelagem e Formato) */}
        <div className="flex-1 grid grid-cols-3 gap-4 border-l border-r border-neutral-200 dark:border-neutral-700 px-6 mx-2">
          {/* Formato */}
          <div className="flex flex-col items-center justify-center text-center">
            <div className="flex items-center gap-1.5 mb-1 text-neutral-500 dark:text-neutral-400">
              <Box className="w-4 h-4" />
              <span className="text-xs font-medium uppercase tracking-wide">Formato</span>
            </div>
            <span className="text-lg font-semibold text-neutral-800 dark:text-neutral-200">
              {formatoAtual ? `${formatoAtual}g` : '--'}
            </span>
          </div>

          {/* Toneladas Turno */}
          <div className="flex flex-col items-center justify-center text-center">
            <div className="flex items-center gap-1.5 mb-1 text-neutral-500 dark:text-neutral-400">
              <Scale className="w-4 h-4" />
              <span className="text-xs font-medium uppercase tracking-wide">Ton. Turno</span>
            </div>
            <span className="text-lg font-semibold text-neutral-800 dark:text-neutral-200">
              {toneladasTurno.toFixed(3)} t
            </span>
          </div>

          {/* Vazão Média */}
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

        {/* Coluna 3: OEE Principal */}
        <div className="text-right min-w-[120px]">
          <div className="flex items-center gap-2 justify-end mb-1">
            <Zap className="w-5 h-5 text-neutral-500" />
            <span className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
              OEE Médio
            </span>
          </div>
          <div className={`text-5xl font-bold ${getOEEColor(oee)}`}>
            {oee.toFixed(1)}%
          </div>
        </div>
      </div>

      {/* SEÇÃO INFERIOR: WIDGET DE PROJEÇÃO (Restaurado) */}
      {projecao && (
        <div className="mt-4 pt-4 border-t border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-neutral-500 uppercase">Projeção do Turno</span>
            <span className={`text-xs font-bold px-2 py-0.5 rounded ${projecao.status === 'AHEAD' || projecao.status === 'ON_TRACK' ? 'bg-green-100 text-green-700' :
                projecao.status === 'RISK' ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'
              }`}>
              {projecao.status === 'AHEAD' ? 'Adiantado' :
                projecao.status === 'ON_TRACK' ? 'No Prazo' :
                  projecao.status === 'RISK' ? 'Risco' : 'Atrasado'}
            </span>
          </div>

          <div className="space-y-3">
            {/* 1. Produzido (Real) */}
            <div className="relative">
              <div className="flex justify-between text-xs mb-1">
                <span className="font-medium text-neutral-700 dark:text-neutral-300">Produzido</span>
                <span className="font-bold text-blue-600 dark:text-blue-400">{projecao.produzido.toLocaleString()}</span>
              </div>
              <div className="h-3 bg-neutral-100 dark:bg-neutral-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-600 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(((projecao.produzido || 0) / (projecao.meta || 1)) * 100, 100)}%` }}
                />
              </div>
            </div>

            {/* 2. Esperado (Meta Atual) */}
            <div className="relative">
              <div className="flex justify-between text-xs mb-1">
                <span className="font-medium text-neutral-600 dark:text-neutral-400">Esperado (Agora)</span>
                <span className="font-bold text-neutral-600 dark:text-neutral-400">
                  {projecao.meta_atual ? projecao.meta_atual.toLocaleString() : '-'}
                </span>
              </div>
              <div className="h-3 bg-neutral-100 dark:bg-neutral-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-neutral-400 dark:bg-neutral-600 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(((projecao.meta_atual || 0) / (projecao.meta || 1)) * 100, 100)}%` }}
                />
              </div>
            </div>

            {/* 3. Projeção Otimista */}
            <div className="relative">
              <div className="flex justify-between text-xs mb-1">
                <span className="font-medium text-neutral-500 dark:text-neutral-500">Proj. Otimista</span>
                <span className="font-bold text-green-600 dark:text-green-500">
                  {projecao.projecao_otimista.toLocaleString()}
                </span>
              </div>
              <div className="h-3 bg-neutral-100 dark:bg-neutral-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-green-500/50 dark:bg-green-500/30 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(((projecao.projecao_otimista || 0) / (projecao.meta || 1)) * 100, 100)}%` }}
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end mt-2 text-xs text-neutral-500 border-t border-neutral-100 dark:border-neutral-800 pt-2 gap-4">
            {projecao.meta_atual !== undefined && (
              <span className="flex items-center gap-1">
                Dif:
                <span className={`font-bold ${projecao.produzido - projecao.meta_atual >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {(projecao.produzido - projecao.meta_atual) > 0 ? '+' : ''}
                  {(projecao.produzido - projecao.meta_atual).toLocaleString()}
                </span>
              </span>
            )}
            <span>Meta Turno: <span className="font-bold text-neutral-700 dark:text-neutral-300">{projecao.meta?.toLocaleString() ?? '-'}</span></span>
          </div>
        </div>
      )}

      {/* RODAPÉ: Barra de Disponibilidade */}
      <div className="mt-6 pt-4 border-t border-neutral-200 dark:border-neutral-800">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-neutral-500 uppercase tracking-wider">
            Disponibilidade da Linha
          </span>
          <span className="text-xs font-semibold text-neutral-700 dark:text-neutral-300">
            {percentualOnline.toFixed(0)}%
          </span>
        </div>

        <div className="h-2 bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ${percentualOnline >= 90 ? 'bg-green-500' :
              percentualOnline >= 70 ? 'bg-yellow-500' :
                'bg-red-500'
              }`}
            style={{ width: `${percentualOnline}%` }}
          />
        </div>
      </div>

    </div>
  );
};

export default LineOverview;