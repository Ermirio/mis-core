/**
 * Funções utilitárias para validação e tratamento robusto de dados
 * Criado para garantir qualidade e confiabilidade dos dados nas telas Home e LineDeepView
 */
/**
 * Valida se um valor é um número válido (não NaN, não Infinity)
 */
export function isValidNumber(value) {
    return typeof value === 'number' && !isNaN(value) && isFinite(value);
}
/**
 * Retorna um número seguro ou valor padrão
 */
export function safeNumber(value, defaultValue = 0) {
    if (isValidNumber(value))
        return value;
    if (typeof value === 'string') {
        const parsed = parseFloat(value);
        if (isValidNumber(parsed))
            return parsed;
    }
    return defaultValue;
}
/**
 * Valida se um array é válido e não vazio
 */
export function isValidArray(value) {
    return Array.isArray(value) && value.length > 0;
}
/**
 * Retorna array seguro ou array vazio
 */
export function safeArray(value) {
    return isValidArray(value) ? value : [];
}
/**
 * Valida se uma string é válida e não vazia
 */
export function isValidString(value) {
    return typeof value === 'string' && value.trim().length > 0;
}
/**
 * Retorna string segura ou valor padrão
 */
export function safeString(value, defaultValue = 'N/A') {
    return isValidString(value) ? value.trim() : defaultValue;
}
/**
 * Divisão segura que retorna 0 se divisor for zero ou inválido
 */
export function safeDivide(numerator, denominator, defaultValue = 0) {
    if (!isValidNumber(numerator) || !isValidNumber(denominator))
        return defaultValue;
    if (denominator === 0)
        return defaultValue;
    const result = numerator / denominator;
    return isValidNumber(result) ? result : defaultValue;
}
/**
 * Calcula porcentagem de forma segura
 */
export function safePercentage(value, total) {
    return safeDivide(value * 100, total, 0);
}
/**
 * Valida e retorna objeto com campos obrigatórios
 */
export function validateObject(obj, requiredFields, defaults = {}) {
    if (!obj || typeof obj !== 'object')
        return null;
    const hasAllRequired = requiredFields.every(field => obj.hasOwnProperty(field) && obj[field] !== undefined && obj[field] !== null);
    if (!hasAllRequired)
        return null;
    return { ...defaults, ...obj };
}
/**
 * Extrai valor de múltiplas fontes com priorização
 */
export function extractValue(...sources) {
    for (const source of sources) {
        if (source !== undefined && source !== null) {
            return source;
        }
    }
    return undefined;
}
/**
 * Normaliza estado de equipamento (pode vir como string ou número)
 */
export function normalizeEstado(estado) {
    if (typeof estado === 'string')
        return estado;
    if (typeof estado === 'number') {
        // Mapeamento comum de estados numéricos
        const estadoMap = {
            0: 'Parado',
            1: 'Produzindo',
            2: 'Aguardando',
            3: 'Manutenção',
            4: 'Offline'
        };
        return estadoMap[estado] || 'Desconhecido';
    }
    return 'Desconhecido';
}
/**
 * Valida timestamp e retorna Date ou null
 */
export function safeDate(timestamp) {
    if (!timestamp)
        return null;
    try {
        const date = new Date(timestamp);
        if (isNaN(date.getTime()))
            return null;
        return date;
    }
    catch {
        return null;
    }
}
/**
 * Verifica se dados estão desatualizados (mais de X segundos)
 */
export function isDataStale(timestamp, maxAgeSeconds = 30) {
    const date = safeDate(timestamp);
    if (!date)
        return true;
    const now = new Date();
    const ageSeconds = (now.getTime() - date.getTime()) / 1000;
    return ageSeconds > maxAgeSeconds;
}
/**
 * Clamp: limita valor entre min e max
 */
export function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}
/**
 * Arredonda para N casas decimais
 */
export function roundTo(value, decimals = 2) {
    if (!isValidNumber(value))
        return 0;
    const multiplier = Math.pow(10, decimals);
    return Math.round(value * multiplier) / multiplier;
}
/**
 * Formata número como toneladas (2 casas decimais)
 */
export function formatToneladas(value) {
    return `${roundTo(value, 2)} t`;
}
/**
 * Formata número como porcentagem
 */
export function formatPercentage(value) {
    return `${roundTo(value, 1)}%`;
}
/**
 * Merge seguro de objetos com validação
 */
export function safeMerge(target, ...sources) {
    const result = { ...target };
    for (const source of sources) {
        if (source && typeof source === 'object') {
            Object.keys(source).forEach(key => {
                const value = source[key];
                if (value !== undefined && value !== null) {
                    result[key] = value;
                }
            });
        }
    }
    return result;
}
