import React from "react";
import { useNavigate } from "react-router-dom";
import { TrendingUp } from "lucide-react";
import { mapEstado } from "@/utils/equipmentStateUtils";

interface EquipamentoCardProps {
  id?: number;
  nome: string;
  tipo: string;
  estado: string;
  velocidadeAtual?: number;
  velocidadePadrao?: number;
  oee?: number;
  pecasBoas?: number;
  pecasRuins?: number;
  contagem_entrada?: number;
  contagem_saida?: number;
  metaOEE?: number;
  sku?: string | number;
  descricao?: string;
  ordemProducao?: string | number;
  cuc?: string | number;
  planejado?: number;
  diferenca?: number;
}

const EquipamentoCard: React.FC<EquipamentoCardProps> = ({
  id,
  nome,
  tipo,
  estado,
  velocidadeAtual = 0,
  velocidadePadrao = 0,
  oee,
  pecasBoas,
  pecasRuins,
  contagem_entrada,
  contagem_saida,
  metaOEE = 85,
  sku,
  descricao,
  ordemProducao,
  cuc,
}) => {
  const navigate = useNavigate();
  const estadoInfo = mapEstado(estado);

  const calculatedPecasBoas = pecasBoas ?? contagem_saida ?? 0;
  const calculatedPecasRuins = pecasRuins ?? 0;
  const calculatedOEE = oee ?? 0;

  const handleClick = () => {
    if (id) navigate(`/equipamento/${id}`);
  };

  return (
    <div
      className={`bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-700 rounded-lg shadow-sm hover:shadow-md transition-all ${id ? 'cursor-pointer hover:border-blue-400' : ''}`}
      onClick={handleClick}
    >
      {/* Header - Nome e Tipo */}
      <div className="px-4 pt-4 pb-3 border-b border-neutral-200 dark:border-neutral-700">
        <h3 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100 truncate">
          {nome}
        </h3>
        <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-2">
          {tipo}
        </p>

        {/* --- ÁREA DE CONTEXTO (OP, CUC, SKU, PRODUTO) --- */}
        {(sku || ordemProducao) && (
          <div className="mt-2 pt-2 border-t border-neutral-100 dark:border-neutral-700 space-y-1.5">
            <div className="flex justify-between items-center text-xs">
              <div className="flex items-center gap-2">
                <span className="text-neutral-500">OP: <span className="font-semibold text-neutral-800 dark:text-neutral-200">{ordemProducao || '-'}</span></span>
                {cuc && cuc !== 'N/A' && (
                  <>
                    <span className="text-neutral-300">|</span>
                    <span className="text-neutral-500">CUC: <span className="font-semibold text-blue-600 dark:text-blue-400">{cuc}</span></span>
                  </>
                )}
              </div>
              <span className="text-neutral-500">SKU: <span className="font-medium text-neutral-700 dark:text-neutral-300">{sku || '-'}</span></span>
            </div>
            <div className="text-xs truncate" title={descricao}>
              <span className="text-neutral-500 mr-1">Produto:</span>
              <span className="font-medium text-neutral-800 dark:text-neutral-200">{descricao || '-'}</span>
            </div>
          </div>
        )}
      </div>

      {/* Estado Padronizado */}
      <div className="px-4 py-3">
        <div
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md transition-colors"
          style={{ backgroundColor: estadoInfo.corFundo }}
        >
          <span style={{ color: estadoInfo.corHex }}>{estadoInfo.icon}</span>
          <span
            className="font-medium text-sm"
            style={{ color: estadoInfo.corHex }}
          >
            {estadoInfo.nome}
          </span>
        </div>
      </div>

      {/* KPI Principal - OEE */}
      <div className="px-4 py-4 bg-neutral-50 dark:bg-neutral-900/50">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-neutral-600 dark:text-neutral-400" />
            <span className="text-sm font-medium text-neutral-600 dark:text-neutral-400">OEE</span>
          </div>
          <span className={`text-3xl font-bold ${calculatedOEE >= metaOEE ? 'text-green-600' : calculatedOEE >= metaOEE * 0.7 ? 'text-yellow-600' : 'text-red-600'}`}>
            {calculatedOEE.toFixed(1)}%
          </span>
        </div>
        <div className="h-2 bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all ${calculatedOEE >= metaOEE ? 'bg-green-500' : calculatedOEE >= metaOEE * 0.7 ? 'bg-yellow-500' : 'bg-red-500'}`}
            style={{ width: `${Math.min(100, calculatedOEE)}%` }}
          />
        </div>
      </div>

      {/* Dados de Produção */}
      <div className="px-4 py-3 grid grid-cols-2 gap-4">
        <div>
          <span className="text-xs text-neutral-600 dark:text-neutral-400 block mb-1">Aprovadas</span>
          <span className="text-xl font-bold text-green-600 dark:text-green-400">
            {calculatedPecasBoas.toLocaleString()}
          </span>
        </div>
        <div>
          <span className="text-xs text-neutral-600 dark:text-neutral-400 block mb-1">Reprovadas</span>
          <span className="text-xl font-bold text-red-600 dark:text-red-400">
            {calculatedPecasRuins.toLocaleString()}
          </span>
        </div>
      </div>

      {/* Footer - Velocidade */}
      <div className="px-4 py-3 border-t border-neutral-200 dark:border-neutral-700">
        <div className="flex items-baseline justify-between text-sm">
          <span className="text-neutral-600 dark:text-neutral-400">Velocidade</span>
          <div>
            <span className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">
              {(velocidadeAtual ?? 0).toFixed(1)}
            </span>
            <span className="text-neutral-500 dark:text-neutral-400 ml-1">
              / {(velocidadePadrao ?? 0).toFixed(1)} ppm
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EquipamentoCard;