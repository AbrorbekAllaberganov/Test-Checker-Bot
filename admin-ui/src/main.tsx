import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'sonner'

import { App } from './App'
import { AuthProvider } from './hooks/useAuth'
import './index.css'

/**
 * Global QueryClient sozlamalari.
 *
 * `retry` — 4xx xatolarda qayta urinmaymiz (401/403/404 qayta urinishdan
 * tuzalmaydi), faqat tarmoq/5xx xatolarda ikki marta urinamiz.
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        const status = (error as { response?: { status?: number } })?.response?.status
        if (status && status >= 400 && status < 500) return false
        return failureCount < 2
      },
    },
    mutations: { retry: false },
  },
})

const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('#root elementi topilmadi')

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* basename — panel FastAPI ostida /admin da xizmat qilinadi */}
      <BrowserRouter basename="/admin">
        <AuthProvider>
          <App />
          <Toaster richColors position="top-right" closeButton />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
