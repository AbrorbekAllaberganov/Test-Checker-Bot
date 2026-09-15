import { Loader2 } from 'lucide-react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { useAuth } from '@/hooks/useAuth'
import { AdminLayout } from '@/layouts/AdminLayout'
import { AuditLogPage } from '@/features/audit/AuditLogPage'
import { BroadcastPage } from '@/features/broadcasts/BroadcastPage'
import { DashboardOverviewPage } from '@/features/dashboard/DashboardOverviewPage'
import { ExplorerPage } from '@/features/explorer/ExplorerPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { ReviewQueuePage } from '@/features/scans/ReviewQueuePage'
import { ScansListPage } from '@/features/scans/ScansListPage'
import { SubscriptionsPage } from '@/features/subscriptions/SubscriptionsPage'
import { SystemStatusPage } from '@/features/system/SystemStatusPage'
import { TeachersTablePage } from '@/features/teachers/TeachersTablePage'

function FullPageLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  )
}

/** Login qilmagan foydalanuvchini `/login` ga yo'naltiradi. */
function ProtectedRoutes() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) return <FullPageLoader />
  if (!isAuthenticated) return <Navigate to="/login" replace />

  return <AdminLayout />
}

export function App() {
  const { isAuthenticated, isLoading } = useAuth()

  return (
    <Routes>
      <Route
        path="/login"
        element={
          isLoading ? (
            <FullPageLoader />
          ) : isAuthenticated ? (
            <Navigate to="/" replace />
          ) : (
            <LoginPage />
          )
        }
      />

      <Route element={<ProtectedRoutes />}>
        <Route path="/" element={<DashboardOverviewPage />} />
        <Route path="/teachers" element={<TeachersTablePage />} />
        <Route path="/explorer" element={<ExplorerPage />} />
        <Route path="/scans" element={<ScansListPage />} />
        <Route path="/review" element={<ReviewQueuePage />} />
        <Route path="/subscriptions" element={<SubscriptionsPage />} />
        <Route path="/broadcasts" element={<BroadcastPage />} />
        <Route path="/audit" element={<AuditLogPage />} />
        <Route path="/system" element={<SystemStatusPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
