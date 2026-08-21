/**
 * Funções utilitárias para cálculos de produção
 * Centraliza lógica de projeção, vazão, ritmo necessário, etc.
 */

import { safeDivide, safeNumber, isValidNumber } from './dataValidation';

/**
 * Dados necessários para cálculos de produção
 */
export interface ProductionData {
  producaoReal: number;
  metaTotal: number;
  oleAtual: number;
  tempoDecorrido: number;      // em segundos
  tempoTotalTurno: number;     // em segundos
  taxaInstantanea?: number;    // t/h do backend
  projecaoBackend?: number;    // projeção do backend
  ritmoNecessarioBackend?: number; // ritmo necessário do backend
}

/**
 * Resultado dos cálculos de produção
 */
export interface ProductionCalculations {
  tempoDecorridoHoras: number;
  tempoTotalHoras: number;
  tempoDecorridoPerc: number;
  vazaoCalculada: number;      // t/h
  projecao: number;            // toneladas projetadas
  ritmoNecessario: number;     // t/h necessário
  desvioProjetado: number;     // toneladas de desvio
  horasRestantes: number;
}

/**
 * Calcula vazão (taxa de produção) em t/h
 * Prioridade: backend > cálculo baseado em tempo decorrido
 */
export function calculateVazao(data: ProductionData): number {
  // Prioridade 1: Taxa instantânea do backend
  if (data.taxaInstantanea && isValidNumber(data.taxaInstantanea) && data.taxaInstantanea > 0) {
    return data.taxaInstantanea;
  }

  // Prioridade 2: Cálculo baseado em produção real e tempo decorrido
  const tempoDecorridoHoras = safeDivide(data.tempoDecorrido, 3600, 0);
  
  if (tempoDecorridoHoras > 0 && data.producaoReal > 0) {
    return safeDivide(data.producaoReal, tempoDecorridoHoras, 0);
  }

  return 0;
}

/**
 * Calcula projeção de produção para fim do turno
 * Prioridade: backend > cálculo baseado em vazão > regra de três simples
 */
export function calculateProjecao(data: ProductionData, vazaoCalculada: number): number {
  // Prioridade 1: Projeção do backend
  if (data.projecaoBackend && isValidNumber(data.projecaoBackend) && data.projecaoBackend > 0) {
    return data.projecaoBackend;
  }

  const tempoDecorridoHoras = safeDivide(data.tempoDecorrido, 3600, 0);
  const tempoTotalHoras = safeDivide(data.tempoTotalTurno, 3600, 0);
  const horasRestantes = Math.max(0, tempoTotalHoras - tempoDecorridoHoras);

  // Prioridade 2: Cálculo baseado em vazão
  if (vazaoCalculada > 0 && tempoDecorridoHoras > 0) {
    if (horasRestantes > 0) {
      // Projeção = Produção Real + (Vazão * Horas Restantes)
      return data.producaoReal + (vazaoCalculada * horasRestantes);
    } else {
      // Turno já terminou, projeção = produção real
      return data.producaoReal;
    }
  }

  // Prioridade 3: Regra de três simples baseada em OLE
  if (data.metaTotal > 0 && data.oleAtual > 0) {
    return safeDivide(data.metaTotal * data.oleAtual, 100, 0);
  }

  // Fallback: retorna produção real
  return data.producaoReal;
}

/**
 * Calcula ritmo necessário para atingir meta (em t/h)
 * Prioridade: backend > cálculo baseado em tempo restante
 */
export function calculateRitmoNecessario(data: ProductionData): number {
  // Prioridade 1: Ritmo necessário do backend
  if (data.ritmoNecessarioBackend && isValidNumber(data.ritmoNecessarioBackend)) {
    return data.ritmoNecessarioBackend;
  }

  const tempoDecorridoHoras = safeDivide(data.tempoDecorrido, 3600, 0);
  const tempoTotalHoras = safeDivide(data.tempoTotalTurno, 3600, 0);
  const horasRestantes = Math.max(0, tempoTotalHoras - tempoDecorridoHoras);

  // Prioridade 2: Cálculo baseado em déficit e tempo restante
  const deficit = data.metaTotal - data.producaoReal;
  
  if (horasRestantes > 0 && deficit > 0) {
    return safeDivide(deficit, horasRestantes, 0);
  }

  // Se não há tempo restante ou já atingiu meta, ritmo necessário é 0
  return 0;
}

/**
 * Calcula desvio projetado em relação à meta
 */
export function calculateDesvio(projecao: number, metaTotal: number): number {
  return projecao - metaTotal;
}

/**
 * Calcula porcentagem de tempo decorrido
 */
export function calculateTempoDecorridoPerc(tempoDecorrido: number, tempoTotalTurno: number): number {
  return safeDivide(tempoDecorrido * 100, tempoTotalTurno, 0);
}

/**
 * Função principal que executa todos os cálculos de produção
 */
export function calculateProduction(data: ProductionData): ProductionCalculations {
  // Normalizar dados de entrada
  const normalizedData: ProductionData = {
    producaoReal: safeNumber(data.producaoReal, 0),
    metaTotal: safeNumber(data.metaTotal, 0),
    oleAtual: safeNumber(data.oleAtual, 0),
    tempoDecorrido: safeNumber(data.tempoDecorrido, 0),
    tempoTotalTurno: safeNumber(data.tempoTotalTurno, 28800), // 8h default
    taxaInstantanea: data.taxaInstantanea,
    projecaoBackend: data.projecaoBackend,
    ritmoNecessarioBackend: data.ritmoNecessarioBackend
  };

  // Conversões de tempo
  const tempoDecorridoHoras = safeDivide(normalizedData.tempoDecorrido, 3600, 0);
  const tempoTotalHoras = safeDivide(normalizedData.tempoTotalTurno, 3600, 0);
  const horasRestantes = Math.max(0, tempoTotalHoras - tempoDecorridoHoras);

  // Cálculos principais
  const vazaoCalculada = calculateVazao(normalizedData);
  const projecao = calculateProjecao(normalizedData, vazaoCalculada);
  const ritmoNecessario = calculateRitmoNecessario(normalizedData);
  const desvioProjetado = calculateDesvio(projecao, normalizedData.metaTotal);
  const tempoDecorridoPerc = calculateTempoDecorridoPerc(
    normalizedData.tempoDecorrido,
    normalizedData.tempoTotalTurno
  );

  return {
    tempoDecorridoHoras,
    tempoTotalHoras,
    tempoDecorridoPerc,
    vazaoCalculada,
    projecao,
    ritmoNecessario,
    desvioProjetado,
    horasRestantes
  };
}

/**
 * Valida se dados de produção são suficientes para cálculos
 */
export function isProductionDataValid(data: Partial<ProductionData>): data is ProductionData {
  return (
    isValidNumber(data.producaoReal) &&
    isValidNumber(data.metaTotal) &&
    isValidNumber(data.oleAtual) &&
    isValidNumber(data.tempoDecorrido) &&
    isValidNumber(data.tempoTotalTurno)
  );
}

/**
 * Cria objeto ProductionData com valores padrão seguros
 */
export function createSafeProductionData(data: Partial<ProductionData>): ProductionData {
  return {
    producaoReal: safeNumber(data.producaoReal, 0),
    metaTotal: safeNumber(data.metaTotal, 0),
    oleAtual: safeNumber(data.oleAtual, 0),
    tempoDecorrido: safeNumber(data.tempoDecorrido, 0),
    tempoTotalTurno: safeNumber(data.tempoTotalTurno, 28800),
    taxaInstantanea: data.taxaInstantanea,
    projecaoBackend: data.projecaoBackend,
    ritmoNecessarioBackend: data.ritmoNecessarioBackend
  };
}
