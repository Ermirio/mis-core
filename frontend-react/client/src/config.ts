declare global {
    interface Window {
        env: {
            VITE_DJANGO_API_URL?: string;
            VITE_FLASK_API_URL?: string;
            [key: string]: string | undefined;
        };
    }
}

export const config = {
    // Prefer runtime config (window.env) over build-time config (import.meta.env)
    // Defaults should match the standard development ports
    DJANGO_API_URL: window.env?.VITE_DJANGO_API_URL || import.meta.env.VITE_DJANGO_API_URL || "http://localhost:8001/api",
    FLASK_API_URL: window.env?.VITE_FLASK_API_URL || import.meta.env.VITE_FLASK_API_URL || "http://localhost:5000/api",
};
