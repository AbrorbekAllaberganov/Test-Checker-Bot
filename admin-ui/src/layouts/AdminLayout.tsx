import {
  Activity,
  BarChart3,
  Bell,
  FolderTree,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  ScanLine,
  ScrollText,
  Sun,
  Users,
  Wallet,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { useAuth } from '@/hooks/useAuth'
import { displayName, initials } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { AdminRole } from '@/api/types'

interface NavItem {
  to: string
  label: string
  icon: typeof LayoutDashboard
  /** Shu roldan pastdagilarga ko'rinmaydi. */
  minRole?: AdminRole
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Boshqaruv paneli', icon: LayoutDashboard },
  { to: '/teachers', label: 'Ustozlar', icon: Users },
  { to: '/explorer', label: 'Guruh va testlar', icon: FolderTree },
  { to: '/scans', label: 'OMR skanlar', icon: ScanLine },
  { to: '/review', label: "Ko'rik navbati", icon: BarChart3 },
  { to: '/subscriptions', label: 'Tariflar', icon: Wallet },
  { to: '/broadcasts', label: "E'lonlar", icon: Bell, minRole: 'SUPPORT_OPERATOR' },
  { to: '/audit', label: 'Audit jurnali', icon: ScrollText },
  { to: '/system', label: 'Tizim holati', icon: Activity },
]

const THEME_KEY = 'omr-admin-theme'

function useTheme() {
  const [isDark, setIsDark] = useState(() => {
    const stored = localStorage.getItem(THEME_KEY)
    if (stored) return stored === 'dark'
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDark)
    localStorage.setItem(THEME_KEY, isDark ? 'dark' : 'light')
  }, [isDark])

  return { isDark, toggle: () => setIsDark((v) => !v) }
}

export function AdminLayout() {
  const { profile, logout, hasRole } = useAuth()
  const { isDark, toggle } = useTheme()
  const [mobileOpen, setMobileOpen] = useState(false)

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.minRole || hasRole(item.minRole),
  )

  return (
    <div className="flex min-h-screen bg-background">
      {/* Yon panel */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r bg-card transition-transform lg:static lg:translate-x-0',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-14 items-center gap-2 border-b px-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ScanLine className="h-4 w-4" />
          </div>
          <div className="leading-tight">
            <p className="text-sm font-semibold">OMR Admin</p>
            <p className="text-[11px] text-muted-foreground">Test Checker Bot</p>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto p-3">
          {visibleItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                )
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        <Separator />

        <div className="p-3">
          <div className="flex items-center gap-3 rounded-md px-2 py-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-semibold">
              {initials(profile?.full_name ?? profile?.username)}
            </div>
            <div className="min-w-0 flex-1 leading-tight">
              <p className="truncate text-sm font-medium">
                {displayName(profile?.full_name, profile?.username, profile?.telegram_id)}
              </p>
              <p className="truncate text-[11px] text-muted-foreground">
                {profile?.admin_role}
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="mt-1 w-full justify-start text-muted-foreground"
            onClick={logout}
          >
            <LogOut className="h-4 w-4" />
            Chiqish
          </Button>
        </div>
      </aside>

      {/* Mobil overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Asosiy qism */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b bg-background/80 px-4 backdrop-blur lg:px-6">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Menyuni ochish"
          >
            <Menu className="h-5 w-5" />
          </Button>

          <div className="flex-1" />

          <Button variant="ghost" size="icon" onClick={toggle} aria-label="Mavzu">
            {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </header>

        <main className="flex-1 p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
