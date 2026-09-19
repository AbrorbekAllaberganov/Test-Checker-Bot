import { useQueryClient } from '@tanstack/react-query'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import {
  AUTH_EXPIRED_EVENT,
  api,
  clearAuth,
  loadAuth,
  logoutRequest,
  saveAuth,
} from '@/api/client'
import type { AdminProfile, AdminRole, TokenPair } from '@/api/types'

/**
 * Autentifikatsiya konteksti.
 *
 * Sahifa yangilanganda `localStorage` dagi token bilan `/auth/me` chaqirilib
 * sessiya tiklanadi — shu bilan birga token hali kuchdami yoki rol o'zgarganmi
 * tekshiriladi (backend rolni bazadan o'qiydi).
 */

interface AuthContextValue {
  profile: AdminProfile | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (tokens: TokenPair) => void
  logout: () => void
  /** Minimal rol talabini tekshiradi (iyerarxik). */
  hasRole: (minimum: AdminRole) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

const ROLE_WEIGHT: Record<AdminRole, number> = {
  ANALYST: 10,
  SUPPORT_OPERATOR: 20,
  SUPERADMIN: 30,
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<AdminProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const queryClient = useQueryClient()

  const logout = useCallback(() => {
    // Serverda ham bekor qilamiz — aks holda token 14 kun amal qilardi.
    // Javobni kutmaymiz: UI darhol login sahifasiga o'tadi.
    void logoutRequest()
    clearAuth()
    setProfile(null)
    queryClient.clear()
  }, [queryClient])

  const login = useCallback((tokens: TokenPair) => {
    saveAuth({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
    })
    setProfile(tokens.profile)
  }, [])

  // Sahifa ochilganda sessiyani tiklash.
  useEffect(() => {
    let cancelled = false

    async function restore() {
      if (!loadAuth()?.accessToken) {
        setIsLoading(false)
        return
      }
      try {
        const { data } = await api.get<AdminProfile>('/api/admin/auth/me')
        if (!cancelled) setProfile(data)
      } catch {
        // Token eskirgan yoki rol olib qo'yilgan — tozalab login'ga yuboramiz.
        if (!cancelled) clearAuth()
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    void restore()
    return () => {
      cancelled = true
    }
  }, [])

  // Axios interceptor refresh'ni uddalay olmasa shu hodisani yuboradi.
  useEffect(() => {
    // Token allaqachon yaroqsiz — serverga logout yuborish keraksiz.
    const handler = () => {
      clearAuth()
      setProfile(null)
      queryClient.clear()
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, handler)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handler)
  }, [queryClient])

  const value = useMemo<AuthContextValue>(
    () => ({
      profile,
      isLoading,
      isAuthenticated: profile !== null,
      login,
      logout,
      hasRole: (minimum: AdminRole) =>
        profile ? ROLE_WEIGHT[profile.admin_role] >= ROLE_WEIGHT[minimum] : false,
    }),
    [profile, isLoading, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth faqat <AuthProvider> ichida ishlatiladi')
  }
  return context
}
