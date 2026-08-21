import { useState, useEffect } from 'react';

// Flask-out Onda 1: /health migrado para Django (/api/health).
// Mantemos a constante por compat até remover totalmente.
const DJANGO_API_URL = (import.meta.env.VITE_DJANGO_API_URL as string) || '/api';

export type SystemHealth = 'ok' | 'warning' | 'critical';

export const useSystemHealth = () => {
    const [health, setHealth] = useState<SystemHealth>('ok');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const checkHealth = async () => {
            try {
                // Check Flask Health
                // We can add a specialized endpoint later, for now check diagnostics/status if exists
                // Or check alerts count

                // Assuming we have an endpoint that returns active alerts count
                // If not, we can assume 'ok' unless fetch fails

                // Let's try to hit a light endpoint. 
                // Maybe just assume 'ok' for now until we implement the backend heartbeat?
                // User said: "parece não estar funcioanando tambem." 
                // We need to implement the backend logic first to have a REAL status.

                // For Phase 1 (Quick Wins), let's implement the UI logic to receive this state.
                // We can fetch from /api/health if we create it, or /api/diagnostics/alerts/summary

                const res = await fetch(`${DJANGO_API_URL}/health`);
                if (!res.ok) {
                    setHealth('critical');
                } else {
                    const data = await res.json();
                    if (data.status === 'offline' || data.plc_offline) setHealth('critical');
                    else if (data.alerts > 0) setHealth('warning');
                    else setHealth('ok');
                }
            } catch (err) {
                setHealth('critical');
            } finally {
                setLoading(false);
            }
        };

        checkHealth();
        const interval = setInterval(checkHealth, 30000); // 30s poll
        return () => clearInterval(interval);
    }, []);

    return { health, loading };
};
