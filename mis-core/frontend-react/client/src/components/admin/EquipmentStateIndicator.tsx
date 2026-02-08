import React from "react";
import { Activity, AlertTriangle, Settings, Clock, Pause, Play, Wrench, Package } from "lucide-react";

export type EquipmentState = 
  | 'RUN' 
  | 'PARTINDO' 
  | 'PARANDO' 
  | 'WAIT_PREV' 
  | 'BLOCK_NEXT' 
  | 'FAULT' 
  | 'SETUP' 
  | 'TESTE_PROJ' 
  | 'AGUARD_MNT' 
  | 'MANUTENCAO' 
  | 'FALTA_MAT' 
  | 'OUTRO';

interface EquipmentStateIndicatorProps {
  state: EquipmentState;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  showIcon?: boolean;
  className?: string;
}

const stateConfig: Record<EquipmentState, {
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
  icon: React.ReactNode;
  textColor: string;
}> = {
  RUN: {
    label: 'Produzindo',
    color: '#10b981',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500',
    textColor: 'text-emerald-400',
    icon: <Play className="w-4 h-4" />
  },
  PARTINDO: {
    label: 'Partindo',
    color: '#06b6d4',
    bgColor: 'bg-cyan-500/10',
    borderColor: 'border-cyan-500',
    textColor: 'text-cyan-400',
    icon: <Activity className="w-4 h-4" />
  },
  PARANDO: {
    label: 'Parando',
    color: '#06b6d4',
    bgColor: 'bg-cyan-500/10',
    borderColor: 'border-cyan-500',
    textColor: 'text-cyan-400',
    icon: <Pause className="w-4 h-4" />
  },
  WAIT_PREV: {
    label: 'Aguardando Anterior',
    color: '#3b82f6',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500',
    textColor: 'text-blue-400',
    icon: <Clock className="w-4 h-4" />
  },
  BLOCK_NEXT: {
    label: 'Bloqueado',
    color: '#8b5cf6',
    bgColor: 'bg-purple-500/10',
    borderColor: 'border-purple-500',
    textColor: 'text-purple-400',
    icon: <AlertTriangle className="w-4 h-4" />
  },
  FAULT: {
    label: 'Falha',
    color: '#ef4444',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500',
    textColor: 'text-red-400',
    icon: <AlertTriangle className="w-4 h-4" />
  },
  SETUP: {
    label: 'Setup / Troca SKU',
    color: '#f59e0b',
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500',
    textColor: 'text-amber-400',
    icon: <Settings className="w-4 h-4" />
  },
  TESTE_PROJ: {
    label: 'Teste de Projeto',
    color: '#14b8a6',
    bgColor: 'bg-teal-500/10',
    borderColor: 'border-teal-500',
    textColor: 'text-teal-400',
    icon: <Activity className="w-4 h-4" />
  },
  AGUARD_MNT: {
    label: 'Aguardando Manutenção',
    color: '#f97316',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500',
    textColor: 'text-orange-400',
    icon: <Clock className="w-4 h-4" />
  },
  MANUTENCAO: {
    label: 'Em Manutenção',
    color: '#f97316',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500',
    textColor: 'text-orange-400',
    icon: <Wrench className="w-4 h-4" />
  },
  FALTA_MAT: {
    label: 'Falta de Material',
    color: '#ec4899',
    bgColor: 'bg-pink-500/10',
    borderColor: 'border-pink-500',
    textColor: 'text-pink-400',
    icon: <Package className="w-4 h-4" />
  },
  OUTRO: {
    label: 'Outro',
    color: '#6b7280',
    bgColor: 'bg-gray-500/10',
    borderColor: 'border-gray-500',
    textColor: 'text-gray-400',
    icon: <Activity className="w-4 h-4" />
  }
};

const sizeClasses = {
  sm: 'px-2 py-1 text-xs',
  md: 'px-3 py-1.5 text-sm',
  lg: 'px-4 py-2 text-base'
};

const EquipmentStateIndicator: React.FC<EquipmentStateIndicatorProps> = ({
  state,
  size = 'md',
  showLabel = true,
  showIcon = true,
  className = ''
}) => {
  const config = stateConfig[state] || stateConfig.OUTRO;

  return (
    <div
      className={`
        inline-flex items-center gap-2 rounded-md border
        ${config.bgColor} ${config.borderColor} ${config.textColor}
        ${sizeClasses[size]}
        font-medium transition-all duration-200
        ${className}
      `}
    >
      {showIcon && (
        <div className="flex-shrink-0">
          {config.icon}
        </div>
      )}
      {showLabel && (
        <span className="font-mono uppercase tracking-wider">
          {config.label}
        </span>
      )}
      <div
        className="w-2 h-2 rounded-full animate-pulse"
        style={{ backgroundColor: config.color }}
      />
    </div>
  );
};

export default EquipmentStateIndicator;
