/**
 * API Service - Tonelagem
 * =======================
 * Funções para buscar dados de tonelagem da API Django
 */

import { DJANGO_API_URL } from '../config/api';


export interface TonnageRealtimeData {
    linha_id: number;
    linha_nome: string;
    toneladas_hora_atual: number;
    vazao_real: number;
    meta_vazao: number | null;
    formato_atual: number | null;
    percentual_meta: number;
    timestamp: string;
}

export interface TonnageHistoryData {
    linha_id: number;
    linha_nome: string;
    periodo: 'HORA' | 'TURNO' | 'DIA';
    total_registros: number;
    toneladas_total: number;
    vazao_media: number;
    dados: TonnageDataPoint[];
}

export interface TonnageDataPoint {
    toneladas_produzidas: number;
    vazao_real_ton_hora: number;
    formato_gramas: number | null;
    contagem_saida: number;
    data_hora: string;
    periodo: string;
    turno: string | null;
}

/**
 * Busca tonelagem em tempo real de uma linha
 */
export async function fetchTonnageRealtime(linhaId: number): Promise<TonnageRealtimeData | null> {
    try {
        const url = `${DJANGO_API_URL}/linhas/${linhaId}/tonelagem-tempo-real/`;
        console.log('[TonnageAPI] Fetching realtime:', url);

        const response = await fetch(url);

        if (!response.ok) {
            console.error(`[TonnageAPI] Error ${response.status}:`, response.statusText);
            return null;
        }

        const data = await response.json();
        console.log('[TonnageAPI] Realtime data:', data);
        return data;
    } catch (error) {
        console.error('[TonnageAPI] Exception in fetchTonnageRealtime:', error);
        return null;
    }
}

/**
 * Busca histórico de tonelagem de uma linha
 */
export async function fetchTonnageHistory(
    linhaId: number,
    periodo: 'HORA' | 'TURNO' | 'DIA' = 'TURNO',
    dataInicio?: string,
    dataFim?: string,
    turno?: string
): Promise<TonnageHistoryData | null> {
    try {
        const params = new URLSearchParams({
            periodo
        });

        if (dataInicio) params.append('data_inicio', dataInicio);
        if (dataFim) params.append('data_fim', dataFim);
        if (turno) params.append('turno', turno);

        const url = `${DJANGO_API_URL}/linhas/${linhaId}/historico-tonelagem/?${params.toString()}`;
        console.log('[TonnageAPI] Fetching history:', url);

        const response = await fetch(url);

        if (!response.ok) {
            console.error(`[TonnageAPI] Error ${response.status}:`, response.statusText);
            return null;
        }

        const data = await response.json();
        console.log('[TonnageAPI] History data:', data);
        return data;
    } catch (error) {
        console.error('[TonnageAPI] Exception in fetchTonnageHistory:', error);
        return null;
    }
}

/**
 * Busca tonelagem de um equipamento específico
 */
export async function fetchEquipmentTonnage(
    equipamentoId: number,
    periodo: 'HORA' | 'TURNO' | 'DIA' = 'HORA',
    limite: number = 24
): Promise<any | null> {
    try {
        const params = new URLSearchParams({
            periodo,
            limite: limite.toString()
        });

        const response = await fetch(
            `${DJANGO_API_URL}/equipamentos/${equipamentoId}/tonelagem/?${params.toString()}`
        );

        if (!response.ok) {
            console.error(`Erro ao buscar tonelagem do equipamento: ${response.status}`);
            return null;
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Erro ao buscar tonelagem do equipamento:', error);
        return null;
    }
}