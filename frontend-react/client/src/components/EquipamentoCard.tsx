import React from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, CheckCircle, XCircle, HelpCircle, Clock, TrendingUp } from "lucide-react";

/**
 * EquipamentoCard - Card de equipamento individual
 * 
 * Design baseado em ISA 101 (High Performance HMI):
 * - Background neutro (cinza)
 * - Cores fortes APENAS para estados anormais
 * - Tipografia clara e hierárquica
 * - Foco em KPIs principais (OEE, Produção)
 * - Dados secundários menores e discretos
 */

interface EquipamentoCardProps {
  id?: number;
  nome: string;
  tipo: string;
  estado: string;
  velocidadeAtual?: number;
  velocidadePadrao?: number;

  // NOVOS: métricas de produção
  oee?: number;
  pecasBoas?: number;
  pecasRuins?: number;
  contagem_entrada?: number;
  contagem_saida?: number;

  metaOEE?: number;
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
}) => {
  const navigate = useNavigate();

  /**
   * Determina a cor do estado seguindo ISA 101
   */
  const getEstadoStyle = (estadoStr: string | number) => {
    const estadoUpper = String(estadoStr || '').toUpperCase();
    const estadoNum = Number(estadoStr);

    // Estados de PRODUÇÃO (Verde)
    if (
      ['PRODUZINDO', 'ONLINE', 'RUN', '1'].includes(estadoUpper) ||
      estadoNum === 1
    ) {
      return {
        color: 'text-green-700 dark:text-green-400',
        bg: 'bg-green-50 dark:bg-green-900/20',
        icon: <CheckCircle className="w-5 h-5" />
      };
    }

    // Estado 2: AGUARDANDO (Azul Turquesa)
    if (
      ['WAIT_PREV', '2'].includes(estadoUpper) ||
      estadoNum === 2
    ) {
      return {
        color: 'text-cyan-700 dark:text-cyan-400',
        bg: 'bg-cyan-50 dark:bg-cyan-900/20',
        icon: <Clock className="w-5 h-5" />
      };
    }

    // Estados de PARADA / ERRO (Vermelho)
    if (
      ['PARADA', 'PARADO', 'FAULT', 'MANUTENCAO', '4', '8'].includes(estadoUpper) ||
      [4, 8].includes(estadoNum)
    ) {
      return {
        color: 'text-red-700 dark:text-red-400',
        bg: 'bg-red-50 dark:bg-red-900/20',
        icon: <XCircle className="w-5 h-5" />
      };
    }

    // Estados de ALERTA / ATENÇÃO (Amarelo)
    if (
      ['ALERTA', 'ATENCAO', 'BLOCK_NEXT', 'SETUP', 'AGUARD_MNT', 'FALTA_MAT', '3', '5', '7', '9'].includes(estadoUpper) ||
      [3, 5, 7, 9].includes(estadoNum)
    ) {
      return {
        color: 'text-yellow-700 dark:text-yellow-400',
        bg: 'bg-yellow-50 dark:bg-yellow-900/20',
        icon: <AlertTriangle className="w-5 h-5" />
      };
    }

    // Estados NEUTROS / DESCONHECIDO
    return {
      color: 'text-neutral-600 dark:text-neutral-400',
      bg: 'bg-neutral-100 dark:bg-neutral-800',
      icon: <HelpCircle className="w-5 h-5" />
    };
  };

  /**
   * Traduz códigos de estado para texto legível
   */
  const getEstadoTexto = (estadoStr: string | number): string => {
    const val = String(estadoStr || '').toUpperCase();
    const num = Number(estadoStr);

    if (val === 'RUN' || num === 1) return 'Produzindo';
    if (val === 'WAIT_PREV' || num === 2) return 'Aguardando';
    if (val === 'BLOCK_NEXT' || num === 3) return 'Bloqueado';
    if (val === 'FAULT' || num === 4) return 'Falha';
    if (val === 'SETUP' || num === 5) return 'Setup';
    if (val === 'TESTE_PROJ' || num === 6) return 'Teste';
    if (val === 'AGUARD_MNT' || num === 7) return 'Aguard. Manut.';
    if (val === 'MANUTENCAO' || num === 8) return 'Manutenção';
    if (val === 'FALTA_MAT' || num === 9) return 'Falta Material';
    if (val === 'ONLINE') return 'Online';
    if (val === 'OFFLINE' || val === 'SEM_DADOS') return 'Sem Dados';

    return String(estadoStr);
  };

  /**
   * Calcula performance simplificada
   */
  const calcularPerformance = (): number => {
    if (!velocidadePadrao || velocidadePadrao === 0) return 0;
    return Math.min(100, (velocidadeAtual / velocidadePadrao) * 100);
  };

  /**
   * Cor do OEE baseada em threshold
   */
  const getOEEColor = (oeeVal: number): string => {
    if (oeeVal >= metaOEE) return 'text-green-600 dark:text-green-400';
    if (oeeVal >= metaOEE * 0.7) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  const estadoStyle = getEstadoStyle(estado);
  const performance = calcularPerformance();

  // Calcula peças boas e ruins se não fornecidas
  const calculatedPecasBoas = pecasBoas ?? contagem_saida ?? 0;
  const calculatedPecasRuins = pecasRuins ?? (contagem_entrada && contagem_saida ? contagem_entrada - contagem_saida : 0);
  const calculatedOEE = oee ?? performance;

  const handleClick = () => {
    if (id) {
      navigate(`/equipamento/${id}`);
    }
  };

  return (
    <div
      className={`bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-700 rounded-lg shadow-sm hover:shadow-md transition-all ${id ? 'cursor-pointer hover:border-blue-400' : ''}`}
      onClick={handleClick}
    >
      {/* Header - Nome e Tipo */}
      <div className="px-4 pt-4 pb-2 border-b border-neutral-200 dark:border-neutral-700">
        <h3 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100 truncate">
          {nome}
        </h3>
        <p className="text-sm text-neutral-600 dark:text-neutral-400">
          {tipo}
        </p>
      </div>

      {/* Estado - Badge com cor ISA 101 */}
      <div className="px-4 py-3">
        <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md ${estadoStyle.bg}`}>
          {estadoStyle.icon}
          <span className={`font-medium text-sm ${estadoStyle.color}`}>
            {getEstadoTexto(estado)}
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
          <span className={`text-3xl font-bold ${getOEEColor(calculatedOEE ?? 0)}`}>
            {(calculatedOEE ?? 0).toFixed(1)}%
          </span>
        </div>

        {/* Barra de progresso do OEE */}
        <div className="h-2 bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all ${(calculatedOEE ?? 0) >= metaOEE ? 'bg-green-500' :
              (calculatedOEE ?? 0) >= metaOEE * 0.7 ? 'bg-yellow-500' :
                'bg-red-500'
              }`}
            style={{ width: `${Math.min(100, calculatedOEE ?? 0)}%` }}
          />
        </div>
        <div className="mt-1 text-xs text-neutral-500 dark:text-neutral-400 text-right">
          Meta: {metaOEE}%
        </div>
      </div>

      {/* Dados de Produção - Peças Boas e Ruins */}
      <div className="px-4 py-3 grid grid-cols-2 gap-4">
        <div>
          <span className="text-xs text-neutral-600 dark:text-neutral-400 block mb-1">Peças Boas</span>
          <span className="text-xl font-bold text-green-600 dark:text-green-400">
            {calculatedPecasBoas.toLocaleString()}
          </span>
        </div>

        <div>
          <span className="text-xs text-neutral-600 dark:text-neutral-400 block mb-1">Peças Ruins</span>
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