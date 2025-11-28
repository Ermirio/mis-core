import React from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, CheckCircle, XCircle, HelpCircle, Clock, TrendingUp, Zap } from "lucide-react";

/**
 * EquipamentoCard - Card de equipamento individual
 * 
 * Design baseado em ISA 101 (High Performance HMI):
 * - Background neutro (cinza)
 * - Cores fortes APENAS para estados anormais
 * - Tipografia clara e hierárquica
 * - Foco em KPIs principais (OEE, Produção)
 * - Dados secundários menores e discretos
 * 
 * Estados Numéricos (0-9) conforme ISA 88:
 * 0: Parado
 * 1: Produzindo
 * 2: Aguardando
 * 3: Bloqueado
 * 4: Falha
 * 5: Setup
 * 6: Teste
 * 7: Aguardando Manutenção
 * 8: Manutenção
 * 9: Falta de Material
 */

interface EquipamentoCardProps {
  id?: number;
  nome: string;
  tipo: string;
  estado: string | number;
  velocidadeAtual?: number;
  velocidadePadrao?: number;
  oee?: number;
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
  metaOEE = 85,
}) => {
  const navigate = useNavigate();

  /**
   * Mapeia estados numéricos (0-9) para estilos visuais conforme ISA 101
   */
  const getEstadoStyle = (estadoVal: string | number) => {
    const estadoNum = typeof estadoVal === "number" ? estadoVal : parseInt(String(estadoVal), 10);
    const estadoStr = String(estadoVal || "").toUpperCase();

    // Estado 1: PRODUZINDO (Verde)
    if (estadoNum === 1 || estadoStr === "RUN" || estadoStr === "PRODUZINDO") {
      return {
        color: "text-green-700 dark:text-green-400",
        bg: "bg-green-50 dark:bg-green-900/20",
        icon: <CheckCircle className="w-5 h-5" />,
        texto: "Produzindo",
      };
    }

    // Estado 2: AGUARDANDO (Azul Turquesa)
    if (estadoNum === 2 || estadoStr === "WAIT_PREV" || estadoStr === "AGUARDANDO") {
      return {
        color: "text-cyan-700 dark:text-cyan-400",
        bg: "bg-cyan-50 dark:bg-cyan-900/20",
        icon: <Clock className="w-5 h-5" />,
        texto: "Aguardando",
      };
    }

    // Estado 3: BLOQUEADO (Laranja)
    if (estadoNum === 3 || estadoStr === "BLOCK_NEXT" || estadoStr === "BLOQUEADO") {
      return {
        color: "text-orange-700 dark:text-orange-400",
        bg: "bg-orange-50 dark:bg-orange-900/20",
        icon: <AlertTriangle className="w-5 h-5" />,
        texto: "Bloqueado",
      };
    }

    // Estados 4, 8: FALHA / MANUTENÇÃO (Vermelho)
    if ([4, 8].includes(estadoNum) || ["FAULT", "MANUTENCAO", "FALHA"].includes(estadoStr)) {
      return {
        color: "text-red-700 dark:text-red-400",
        bg: "bg-red-50 dark:bg-red-900/20",
        icon: <XCircle className="w-5 h-5" />,
        texto: estadoNum === 8 ? "Manutenção" : "Falha",
      };
    }

    // Estados 5, 6, 7, 9: SETUP, TESTE, AGUARD_MNT, FALTA_MAT (Amarelo)
    if ([5, 6, 7, 9].includes(estadoNum) || ["SETUP", "TESTE", "AGUARD_MNT", "FALTA_MAT"].includes(estadoStr)) {
      const textoEstado = {
        5: "Setup",
        6: "Teste",
        7: "Aguard. Manut.",
        9: "Falta Material",
      }[estadoNum] || "Atenção";

      return {
        color: "text-yellow-700 dark:text-yellow-400",
        bg: "bg-yellow-50 dark:bg-yellow-900/20",
        icon: <AlertTriangle className="w-5 h-5" />,
        texto: textoEstado,
      };
    }

    // Estado 0: PARADO (Cinza)
    if (estadoNum === 0 || estadoStr === "OFFLINE" || estadoStr === "PARADO" || estadoStr === "SEM_DADOS") {
      return {
        color: "text-neutral-600 dark:text-neutral-400",
        bg: "bg-neutral-100 dark:bg-neutral-800",
        icon: <HelpCircle className="w-5 h-5" />,
        texto: "Parado",
      };
    }

    // Default: DESCONHECIDO
    return {
      color: "text-neutral-600 dark:text-neutral-400",
      bg: "bg-neutral-100 dark:bg-neutral-800",
      icon: <HelpCircle className="w-5 h-5" />,
      texto: "Desconhecido",
    };
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
  const getOEEColor = (oeeVal: number | undefined): string => {
    if (!oeeVal) return "text-neutral-500 dark:text-neutral-400";
    if (oeeVal >= metaOEE) return "text-green-600 dark:text-green-400";
    if (oeeVal >= metaOEE * 0.7) return "text-yellow-600 dark:text-yellow-400";
    return "text-red-600 dark:text-red-400";
  };

  const estadoStyle = getEstadoStyle(estado);
  const performance = calcularPerformance();
  const oeeDisplay = oee ?? performance;

  const handleClick = () => {
    if (id) {
      navigate(`/equipamento/${id}`);
    }
  };

  return (
    <div
      className={`bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-700 rounded-lg shadow-sm hover:shadow-md transition-all ${id ? "cursor-pointer hover:border-blue-400" : ""}`}
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
            {estadoStyle.texto}
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
          <span className={`text-3xl font-bold ${getOEEColor(oeeDisplay)}`}>
            {(oeeDisplay ?? 0).toFixed(1)}%
          </span>
        </div>

        {/* Barra de progresso do OEE */}
        <div className="h-2 bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all ${
              (oeeDisplay ?? 0) >= metaOEE
                ? "bg-green-500"
                : (oeeDisplay ?? 0) >= metaOEE * 0.7
                ? "bg-yellow-500"
                : "bg-red-500"
            }`}
            style={{ width: `${Math.min(100, oeeDisplay ?? 0)}%` }}
          />
        </div>
        <div className="mt-1 text-xs text-neutral-500 dark:text-neutral-400 text-right">
          Meta: {metaOEE}%
        </div>
      </div>

      {/* Dados de Velocidade */}
      <div className="px-4 py-3 border-t border-neutral-200 dark:border-neutral-700">
        <div className="flex items-baseline justify-between text-sm">
          <div className="flex items-center gap-1">
            <Zap className="w-4 h-4 text-neutral-600 dark:text-neutral-400" />
            <span className="text-neutral-600 dark:text-neutral-400">Velocidade</span>
          </div>
          <div>
            <span className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">
              {(velocidadeAtual ?? 0).toFixed(1)}
            </span>
            <span className="text-neutral-500 dark:text-neutral-400 ml-1">
              / {(velocidadePadrao ?? 0).toFixed(1)} ppm
            </span>
          </div>
        </div>
        {/* Barra de velocidade */}
        <div className="h-1.5 bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden mt-2">
          <div
            className={`h-full transition-all ${performance >= 90 ? "bg-green-500" : performance >= 70 ? "bg-yellow-500" : "bg-orange-500"}`}
            style={{ width: `${Math.min(100, performance)}%` }}
          />
        </div>
      </div>
    </div>
  );
};

export default EquipamentoCard;
