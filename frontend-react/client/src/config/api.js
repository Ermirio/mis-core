/**
 * Centralized API Configuration
 *
 * Priority (highest → lowest):
 *   1. window.ENV  — injected at runtime by docker-entrypoint.sh (hub can override per-deployment)
 *   2. import.meta.env — baked in at Vite build time
 *   3. hardcoded default — works for standalone mode (nginx inside the frontend container)
 *
 * This three-layer approach lets the SAME Docker image run in the hub proxy
 * (which uses /mis-core-api, /mis-core-flask-api) AND in standalone mode
 * (which uses /api, /flask-api), without separate builds.
 */
const runtimeEnv = (key) => typeof window !== 'undefined' ? window.ENV?.[key] : undefined;
export const DJANGO_API_URL = runtimeEnv('VITE_DJANGO_API_URL') ||
    import.meta.env.VITE_DJANGO_API_URL ||
    '/api';
export const FLASK_API_URL = runtimeEnv('VITE_FLASK_API_URL') ||
    import.meta.env.VITE_FLASK_API_URL ||
    '/api';
export const FASTAPI_V2_URL = runtimeEnv('VITE_FASTAPI_V2_URL') ||
    import.meta.env.VITE_FASTAPI_V2_URL ||
    '/api/v2';
