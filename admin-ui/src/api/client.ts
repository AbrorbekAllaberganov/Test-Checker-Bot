import axios, {
  AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from 'axios'

import type { TokenPair } from './types'

/**
 * Axios klienti — JWT access token'ni avtomatik qo'shadi va 401 kelganda
 * refresh token bilan bir marta yangilab, so'rovni qaytadan yuboradi.
 *
 * Bir vaqtda bir nechta so'rov 401 olsa — faqat BITTA refresh ketadi,
 * qolganlari o'sha va'dani (`refreshPromise`) kutib turadi. Aks holda
 * har bir parallel so'rov alohida refresh yuborib, token rotatsiyasini
 * buzib qo'yardi.
 */

const STORAGE_KEY = 'omr-admin-auth'

export interface StoredAuth {
  accessToken: string
  refreshToken: string
}

export function loadAuth(): StoredAuth | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as StoredAuth) : null
  } catch {
    return null
  }
}

export function saveAuth(tokens: StoredAuth): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens))
}

export function clearAuth(): void {
  localStorage.removeItem(STORAGE_KEY)
}

/**
 * Serverda sessiyani bekor qiladi (access + refresh tokenlar).
 *
 * Faqat localStorage'ni tozalash yetarli emas edi: token 14 kun davomida
 * amal qilishda davom etardi (weaknesses.md №19). Xato bo'lsa ham lokal
 * tozalash baribir bajariladi — chiqish hech qachon "ishlamay" qolmasin.
 */
export async function logoutRequest(): Promise<void> {
  const auth = loadAuth()
  if (!auth?.accessToken && !auth?.refreshToken) return

  try {
    // Toza axios: interceptor 401'da refresh urinishi shart emas.
    await axios.post(
      `${import.meta.env.VITE_API_BASE_URL || ''}/api/admin/auth/logout`,
      { refresh_token: auth.refreshToken ?? null },
      {
        headers: {
          'Content-Type': 'application/json',
          ...(auth.accessToken ? { Authorization: `Bearer ${auth.accessToken}` } : {}),
        },
        timeout: 5_000,
      },
    )
  } catch {
    // Tarmoq yo'q bo'lsa ham lokal chiqish davom etadi.
  }
}

/** Sessiya tugaganda AuthProvider shu hodisaga obuna bo'lib login'ga yuboradi. */
export const AUTH_EXPIRED_EVENT = 'omr-admin:auth-expired'

function notifyExpired(): void {
  window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT))
}

export const api: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const auth = loadAuth()
  if (auth?.accessToken) {
    config.headers.set('Authorization', `Bearer ${auth.accessToken}`)
  }
  return config
})

let refreshPromise: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  const auth = loadAuth()
  if (!auth?.refreshToken) throw new Error('Refresh token yo’q')

  // `api` emas, toza axios — aks holda interceptor cheksiz tsiklga kiradi.
  const { data } = await axios.post<TokenPair>(
    `${import.meta.env.VITE_API_BASE_URL || ''}/api/admin/auth/refresh`,
    { refresh_token: auth.refreshToken },
    { headers: { 'Content-Type': 'application/json' } },
  )

  saveAuth({ accessToken: data.access_token, refreshToken: data.refresh_token })
  return data.access_token
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as
      | (InternalAxiosRequestConfig & { _retried?: boolean })
      | undefined

    const isAuthEndpoint = original?.url?.includes('/api/admin/auth/')

    if (
      error.response?.status === 401 &&
      original &&
      !original._retried &&
      !isAuthEndpoint
    ) {
      original._retried = true
      try {
        refreshPromise ??= refreshAccessToken().finally(() => {
          refreshPromise = null
        })
        const token = await refreshPromise
        original.headers.set('Authorization', `Bearer ${token}`)
        return api(original)
      } catch {
        clearAuth()
        notifyExpired()
      }
    }

    return Promise.reject(error)
  },
)

/** Backend xatosidan foydalanuvchiga ko'rsatiladigan matnni ajratib oladi. */
export function errorMessage(error: unknown, fallback = 'Xatolik yuz berdi'): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    // Pydantic validatsiya xatosi: [{loc, msg, type}, ...]
    if (Array.isArray(detail)) {
      const first = detail[0] as { msg?: string } | undefined
      if (first?.msg) return first.msg
    }
    if (error.code === 'ECONNABORTED') return 'So’rov vaqti tugadi'
    if (!error.response) return 'Serverga ulanib bo’lmadi'
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}

/** Fayl (Excel) yuklab olish — blob'ni brauzerga saqlatadi. */
export async function downloadFile(url: string, fallbackName: string): Promise<void> {
  const response = await api.get(url, { responseType: 'blob' })

  const disposition = response.headers['content-disposition'] as string | undefined
  const match = disposition?.match(/filename="?([^"]+)"?/)
  const filename = match?.[1] ?? fallbackName

  const blobUrl = URL.createObjectURL(response.data as Blob)
  const link = document.createElement('a')
  link.href = blobUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(blobUrl)
}
