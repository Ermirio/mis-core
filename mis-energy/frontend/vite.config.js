import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite' // <-- 1. IMPORTE O PLUGIN
import { fileURLToPath, URL } from 'url'

export default defineConfig({
  base: '/mis-energy/',
  plugins: [
    react(),
    tailwindcss(), // <-- 2. USE O PLUGIN AQUI
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5005',
        changeOrigin: true
      }
    }
  }
})