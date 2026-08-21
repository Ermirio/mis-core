import { useState, useEffect, useCallback } from 'react';
export function useRealTimeData({ endpoint, interval = 5000, enabled = true, onError }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [lastUpdate, setLastUpdate] = useState(null);
    const fetchData = useCallback(async () => {
        if (!enabled)
            return;
        try {
            const response = await fetch(endpoint);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const result = await response.json();
            setData(result);
            setError(null);
            setLastUpdate(new Date());
        }
        catch (err) {
            const error = err instanceof Error ? err : new Error('Unknown error');
            setError(error);
            onError?.(error);
            console.error('Error fetching real-time data:', error);
        }
        finally {
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
