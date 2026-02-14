/**
 * Centralized API Configuration
 * 
 * Reads from environment variables (VITE_*) to allow dynamic configuration.
 * Defaults to relative paths to work seamlessly with the Nginx Reverse Proxy.
 */

// Django API URL
// Default: '/api' (Relative path, handled by Nginx proxy)
export const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || '/api';

// Flask API URL
// Default: '/flask-api' (Relative path, handled by Nginx proxy)
// Note: Some legacy code might expect direct port access, but for portability, we prefer the proxy.
export const FLASK_API_URL = import.meta.env.VITE_FLASK_API_URL || '/flask-api';

console.log('API Configuration Loaded:', { DJANGO_API_URL, FLASK_API_URL });
