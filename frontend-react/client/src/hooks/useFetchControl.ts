/**
 * Hook customizado para controlar fetching com debounce e prevenção de race conditions
 */

import { useRef, useCallback } from 'react';

interface UseFetchControlOptions {
  minInterval?: number; // Intervalo mínimo entre requests em ms
  onError?: (error: Error) => void;
}

export function useFetchControl(options: UseFetchControlOptions = {}) {
  const { minInterval = 1000, onError } = options;
  
  const isFetchingRef = useRef(false);
  const lastFetchTimeRef = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  /**
   * Verifica se pode fazer novo fetch baseado no intervalo mínimo
   */
  const canFetch = useCallback((): boolean => {
    if (isFetchingRef.current) {
      return false;
    }

    const now = Date.now();
    const timeSinceLastFetch = now - lastFetchTimeRef.current;
    
    return timeSinceLastFetch >= minInterval;
  }, [minInterval]);

  /**
   * Inicia um novo fetch
   */
  const startFetch = useCallback((): AbortSignal | null => {
    if (!canFetch()) {
      return null;
    }

    // Cancela fetch anterior se existir
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Cria novo AbortController
    abortControllerRef.current = new AbortController();
    isFetchingRef.current = true;
    lastFetchTimeRef.current = Date.now();

    return abortControllerRef.current.signal;
  }, [canFetch]);

  /**
   * Finaliza fetch atual
   */
  const endFetch = useCallback(() => {
    isFetchingRef.current = false;
    abortControllerRef.current = null;
  }, []);

  /**
   * Cancela fetch em andamento
   */
  const cancelFetch = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    isFetchingRef.current = false;
  }, []);

  /**
   * Wrapper para executar fetch com controle automático
   */
  const executeFetch = useCallback(async <T>(
    fetchFn: (signal: AbortSignal) => Promise<T>
  ): Promise<T | null> => {
    const signal = startFetch();
    
    if (!signal) {
      // Fetch bloqueado por intervalo mínimo
      return null;
    }

    try {
      const result = await fetchFn(signal);
      endFetch();
      return result;
    } catch (error) {
      endFetch();
      
      // Ignora erros de abort (são esperados)
      if (error instanceof Error && error.name === 'AbortError') {
        return null;
      }

      // Reporta outros erros
      if (onError && error instanceof Error) {
        onError(error);
      }
      
      throw error;
    }
  }, [startFetch, endFetch, onError]);

  /**
   * Reseta estado do controle
   */
  const reset = useCallback(() => {
    cancelFetch();
    lastFetchTimeRef.current = 0;
  }, [cancelFetch]);

  return {
    canFetch,
    startFetch,
    endFetch,
    cancelFetch,
    executeFetch,
    reset,
    isFetching: isFetchingRef.current
  };
}

/**
 * Hook para criar fetch function com retry automático
 */
export function useRetryFetch(maxRetries: number = 3, retryDelay: number = 1000) {
  const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

  const fetchWithRetry = useCallback(async <T>(
    fetchFn: () => Promise<T>,
    retries: number = maxRetries
  ): Promise<T | null> => {
    try {
      return await fetchFn();
    } catch (error) {
      if (retries > 0) {
        await sleep(retryDelay);
        return fetchWithRetry(fetchFn, retries - 1);
      }
      
      console.error('Fetch failed after retries:', error);
      return null;
    }
  }, [maxRetries, retryDelay]);

  return { fetchWithRetry };
}
