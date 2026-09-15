import path from 'node:path'

import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

/**
 * Vite konfiguratsiyasi.
 *
 * `base: '/admin/'` — FastAPI panelni `/admin` ostida xizmat qiladi
 * (app/api/main.py: _mount_admin_spa), shu sababli asset yo'llari ham
 * shu prefiks bilan generatsiya qilinishi kerak.
 *
 * Dev rejimida `/api` so'rovlari FastAPI'ga proksi qilinadi — shunda
 * frontend va backend bir origin'da ko'rinadi va CORS umuman kerak bo'lmaydi.
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

  return {
    base: '/admin/',
    plugins: [react()],
    resolve: {
      alias: { '@': path.resolve(__dirname, './src') },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
        // OMR inspektoridagi rasmlar ham backend'dan keladi.
        '/static': { target: apiTarget, changeOrigin: true },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: mode !== 'production',
      rollupOptions: {
        output: {
          // Recharts og'ir — alohida chunk'ga ajratamiz, shunda jadval
          // sahifalari uni yuklamaydi.
          manualChunks: {
            react: ['react', 'react-dom', 'react-router-dom'],
            charts: ['recharts'],
            query: ['@tanstack/react-query', '@tanstack/react-table'],
          },
        },
      },
    },
  }
})
