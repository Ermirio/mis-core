import { useState, useEffect, useCallback } from 'react';

interface UseRealTimeDataOptions {
  endpoint: string;
  interval?: number; // em milissegundos
  enabled?: boolean;
  onError?: (error: Error) => void;
}

interface UseRealTimeDataReturn<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  lastUpdate: Date | null;
}

export function useRealTimeData<T = any>({
  endpoint,
  interval = 5000,
  enabled = true,
  onError
}: UseRealTimeDataOptions): UseRealTimeDataReturn<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    if (!enabled) return;

    try {
      const response = await fetch(endpoint);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json();
      setData(result);
      setError(null);
      setLastUpdate(new Date());
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Unknown error');
      setError(error);
      onError?.(error);
      console.error('Error fetching real-time data:', error);
    } finally {
      setLoading(false);
    }
  }, [endpoint, enabled, onError]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    // Fetch inicial
    fetchData();

    // Configurar polling
    const intervalId = setInterval(fetchData, interval);

    // Cleanup
    return () => {
      clearInterval(intervalId);
    };
  }, [fetchData, interval, enabled]);

  return {
    data,
    loading,
    error,
    refetch: fetchData,
    lastUpdate
  };
}

export default useRealTimeData;
