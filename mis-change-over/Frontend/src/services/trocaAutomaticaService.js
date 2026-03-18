/**
 * @file trocaAutomaticaService.js
 * @description Service layer for TrocaAutomaticaContent component.
 * Handles all API communications related to SKU synchronization and exchange history.
 */

// --- Constants (Environment Variables or Defaults) ---
const BASE_URL = process.env.REACT_APP_TROCA_AUTOMATICA_BASE_URL || '/api';
const SYNC_SKUS_PATH = process.env.REACT_APP_SYNC_SKUS_ENDPOINT || '/sincronizar-skus/';
const HISTORICO_TROCAS_PATH = process.env.REACT_APP_HISTORICO_TROCAS_ENDPOINT || '/linha/{line}';
const TROCAR_SKU_PATH = process.env.REACT_APP_TROCAR_SKU_PATH || '/trocar_sku/';
const HEALTH_CHECK_PATH = '/health/';

export const trocaAutomaticaService = {
    /**
     * Checks the health status of the Django API.
     * Uses native fetch to avoid axios interceptors if necessary, or for simplicity.
     */
    checkHealth: async () => {
        try {
            const response = await fetch(`${BASE_URL}${HEALTH_CHECK_PATH}`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                },
            });
            return response.ok;
        } catch (error) {
            return false;
        }
    },

    /**
     * Fetches the list of available SKUs for a given line.
     * @param {Object} api - The axios instance.
     * @param {string} linha - The line identifier.
     */
    getSkus: async (api, linha) => {
        // SYNC_SKUS_PATH is usually a root path (e.g., /sincronizar-skus/)
        // If api has baseURL='/api', and we pass '/sincronizar-skus/', axios uses the absolute path.
        const url = `${SYNC_SKUS_PATH}?linha=${linha}`;
        const response = await api.get(url);
        return response.data;
    },

    /**
     * Fetches the exchange history for a given line.
     * @param {Object} api - The axios instance.
     * @param {string} linha - The line identifier.
     * @param {number} page - Page number.
     * @param {number} perPage - Items per page.
     */
    getHistorico: async (api, linha, page, perPage) => {
        let path = HISTORICO_TROCAS_PATH.replace('{line}', linha);
        // Remove leading slash to append to axios baseURL if needed, 
        // but logic depends on how axios is configured. 
        // Original code: if (path.startsWith('/')) path = path.substring(1);
        if (path.startsWith('/')) path = path.substring(1);

        const response = await api.get(`${path}?page=${page}&per_page=${perPage}`);
        return response.data;
    },

    /**
     * Sends a request to exchange the SKU on the line.
     * @param {Object} api - The axios instance.
     * @param {Object} payload - The exchange details (linha, sku, etc.).
     */
    trocarSku: async (api, payload) => {
        let path = TROCAR_SKU_PATH;
        if (path.startsWith('/')) path = path.substring(1);
        const response = await api.post(path, payload);
        return response.data;
    }
};
