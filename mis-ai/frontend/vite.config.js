import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],

  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },

  // ==================== CONFIGURAÇÃO PARA PROXY NGINX ====================
  // Base URL para quando a aplicação rodar atrás do proxy
  base: '/mis-ai/',

  // Configuração do servidor de desenvolvimento
  server: {
    host: '0.0.0.0',
    port: 3007,
    strictPort: true,
    // Proxy para API durante desenvolvimento
    proxy: {
      '/predicao-api': {
        target: 'http://localhost:5004',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/predicao-api/, '/api'),
      },
    },
  },

  // Configuração de build para produção
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    // Gerar sourcemaps para debug
    sourcemap: false,
    // Otimizações
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true, // Remove console.log em produção
      },
    },
  },

  // Preview (para testar build localmente)
  preview: {
    host: '0.0.0.0',
    port: 3007,
    strictPort: true,
  },
})

