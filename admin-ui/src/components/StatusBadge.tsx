import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Clock,
  PencilLine,
  ShieldCheck,
  XCircle,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type {
  BroadcastStatus,
  ScanStatus,
  SubscriptionStatus,
} from '@/api/types'

/** Skan holati (OMR natijasi) uchun nishon. */
export function ScanStatusBadge({
  status,
  needsReview,
  manualOverride,
}: {
  status: ScanStatus
  needsReview?: boolean
  manualOverride?: boolean
}) {
  if (status === 'pending') {
    return (
      <Badge variant="secondary">
        <Clock className="h-3 w-3" />
        Navbatda
      </Badge>
    )
  }
  if (status === 'error') {
    return (
      <Badge variant="destructive">
        <XCircle className="h-3 w-3" />
        Xato
      </Badge>
    )
  }
  if (manualOverride) {
    return (
      <Badge variant="default">
        <PencilLine className="h-3 w-3" />
        Qo'lda tuzatilgan
      </Badge>
    )
  }
  if (needsReview) {
    return (
      <Badge variant="warning">
        <AlertTriangle className="h-3 w-3" />
        Ko'rik kerak
      </Badge>
    )
  }
  return (
    <Badge variant="success">
      <CheckCircle2 className="h-3 w-3" />
      Tayyor
    </Badge>
  )
}

const SUBSCRIPTION_LABELS: Record<SubscriptionStatus, string> = {
  active: 'Faol',
  trial: 'Sinov',
  expired: 'Muddati tugagan',
  cancelled: 'Bekor qilingan',
}

export function SubscriptionBadge({
  status,
}: {
  status: SubscriptionStatus | null | undefined
}) {
  if (!status) return <Badge variant="outline">Obuna yo'q</Badge>

  const variant =
    status === 'active'
      ? 'success'
      : status === 'trial'
        ? 'default'
        : status === 'expired'
          ? 'warning'
          : 'secondary'

  return <Badge variant={variant}>{SUBSCRIPTION_LABELS[status]}</Badge>
}

const BROADCAST_LABELS: Record<BroadcastStatus, string> = {
  draft: 'Qoralama',
  queued: 'Navbatda',
  sending: 'Yuborilmoqda',
  sent: 'Yuborildi',
  failed: 'Xato',
  cancelled: 'Bekor qilindi',
}

export function BroadcastStatusBadge({ status }: { status: BroadcastStatus }) {
  const variant =
    status === 'sent'
      ? 'success'
      : status === 'failed'
        ? 'destructive'
        : status === 'sending' || status === 'queued'
          ? 'warning'
          : 'secondary'

  return <Badge variant={variant}>{BROADCAST_LABELS[status]}</Badge>
}

export function BlockedBadge({ blocked }: { blocked: boolean }) {
  return blocked ? (
    <Badge variant="destructive">
      <Ban className="h-3 w-3" />
      Bloklangan
    </Badge>
  ) : (
    <Badge variant="success">
      <ShieldCheck className="h-3 w-3" />
      Faol
    </Badge>
  )
}

/** Komponent sog'lig'i (up/down/degraded). */
export function HealthBadge({ status }: { status: string }) {
  const variant =
    status === 'up' ? 'success' : status === 'down' ? 'destructive' : 'warning'
  const label =
    status === 'up'
      ? 'Ishlayapti'
      : status === 'down'
        ? "Ishlamayapti"
        : status === 'degraded'
          ? 'Qisman'
          : "Noma'lum"
  return <Badge variant={variant}>{label}</Badge>
}
