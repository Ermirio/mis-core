import React from 'react';
import { CheckCircle, Clock, AlertTriangle, XCircle, HelpCircle, Settings, FileText, PenTool, AlertOctagon, PlayCircle, Activity, PauseCircle } from 'lucide-react';

// Definição das cores base (Hex) conforme MultiEquipmentTimeline
const STATE_COLORS: Record<string, string> = {
    'PRODUZINDO': '#16a34a', // green-600
    'WAIT_PREV': '#06b6d4',  // cyan-500
    'BLOCK_NEXT': '#f97316', // orange-500
    'PARADO': '#dc2626',     // red-600
    'SETUP': '#a855f7',      // purple-500
    'TESTE_PROJ': '#3b82f6', // blue-500
    'AGUARD_MNT': '#eab308', // yellow-500
    'MANUTENCAO': '#991b1b', // red-800
    'FALTA_MAT': '#d97706',  // amber-600
    'PARTINDO': '#84cc16',   // lime-500
    'AGUARD_COND': '#0ea5e9', // sky-500
    'PARANDO': '#f43f5e',    // rose-500
    'DEFAULT': '#9ca3af'     // gray-400
};

// Labels em Português conforme MultiEquipmentTimeline
const STATE_LABELS: Record<string, string> = {
    'PRODUZINDO': 'Produzindo',
    'WAIT_PREV': 'Aguardando Anterior',
    'BLOCK_NEXT': 'Bloqueado Próximo',
    'PARADO': 'Parado/Falha',
    'SETUP': 'Setup',
    'TESTE_PROJ': 'Teste/Projeto',
    'AGUARD_MNT': 'Aguardando Manutenção',
    'MANUTENCAO': 'Manutenção',
    'FALTA_MAT': 'Falta de Material',
    'PARTINDO': 'Partindo',
    'AGUARD_COND': 'Aguardando Condições',
    'PARANDO': 'Parando',
    'DEFAULT': 'Desconhecido'
};

// Mapeamento de Ícones
const STATE_ICONS: Record<string, React.ReactNode> = {
    'PRODUZINDO': <CheckCircle className="w-5 h-5" />,
    'WAIT_PREV': <Clock className="w-5 h-5" />,
    'BLOCK_NEXT': <AlertTriangle className="w-5 h-5" />,
    'PARADO': <XCircle className="w-5 h-5" />,
    'SETUP': <Settings className="w-5 h-5" />,
    'TESTE_PROJ': <FileText className="w-5 h-5" />,
    'AGUARD_MNT': <AlertOctagon className="w-5 h-5" />,
    'MANUTENCAO': <PenTool className="w-5 h-5" />,
    'FALTA_MAT': <AlertTriangle className="w-5 h-5" />,
    'PARTINDO': <PlayCircle className="w-5 h-5" />,
    'AGUARD_COND': <Activity className="w-5 h-5" />,
    'PARANDO': <PauseCircle className="w-5 h-5" />,
    'DEFAULT': <HelpCircle className="w-5 h-5" />
};

export interface EstadoMapeado {
    chave: string;
    nome: string;
    corHex: string;
    corFundo: string; // Hex com transparência ou classe Tailwind
    corTexto: string; // Classe Tailwind ou Hex
    icon: React.ReactNode;
}

export const normalizeState = (estado: string | number): string => {
    const estadoStr = String(estado || '').toUpperCase().trim();

    // Mapeamento numérico e de texto para chaves padronizadas
    if (['RUN', 'PRODUZINDO', '1', 'ONLINE'].includes(estadoStr)) return 'PRODUZINDO';
    if (['WAIT_PREV', '2', 'AGUARDANDO', 'AGUARDANDO ANTERIOR'].includes(estadoStr)) return 'WAIT_PREV';
    if (['BLOCK_NEXT', '3', 'BLOQUEADO', 'BLOQUEADO PRÓXIMO', 'BLOQUEADO PROXIMO'].includes(estadoStr)) return 'BLOCK_NEXT';
    if (['FAULT', 'PARADO', 'PARADA', '4', 'FALHA', 'PARADO/FALHA', '0', 'OUTRO'].includes(estadoStr)) return 'PARADO';
    if (['SETUP', '5'].includes(estadoStr)) return 'SETUP';
    if (['TESTE_PROJ', '6', 'TESTE', 'TESTE/PROJETO'].includes(estadoStr)) return 'TESTE_PROJ';
    if (['AGUARD_MNT', '7', 'AGUARDANDO MANUTENÇÃO', 'AGUARDANDO MANUTENCAO'].includes(estadoStr)) return 'AGUARD_MNT';
    if (['MANUTENCAO', '8', 'MANUTENÇÃO'].includes(estadoStr)) return 'MANUTENCAO';
    if (['FALTA_MAT', '9', 'FALTA MATERIAL', 'FALTA DE MATERIAL'].includes(estadoStr)) return 'FALTA_MAT';

    // Novos Estados
    if (['PARTINDO', '11'].includes(estadoStr)) return 'PARTINDO';
    if (['AGUARD_COND', '12', 'AGUARDANDO CONDIÇÕES', 'AGUARDANDO CONDICOES'].includes(estadoStr)) return 'AGUARD_COND';
    if (['PARANDO', '13'].includes(estadoStr)) return 'PARANDO';

    return 'DEFAULT';
};

export const mapEstado = (estado: string | number): EstadoMapeado => {
    const chave = normalizeState(estado);
    const corBase = STATE_COLORS[chave] || STATE_COLORS['DEFAULT'];

    return {
        chave,
        nome: STATE_LABELS[chave] || estado.toString(),
        corHex: corBase,
        // Usando estilo inline para background com opacidade baseada na cor Hex
        corFundo: `${corBase}20`, // 20 = ~12% de opacidade (hex alpha)
        corTexto: corBase,
        icon: STATE_ICONS[chave] || STATE_ICONS['DEFAULT']
    };
};
