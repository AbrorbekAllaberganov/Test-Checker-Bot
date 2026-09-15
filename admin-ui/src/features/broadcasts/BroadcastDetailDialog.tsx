import { Ban, Send } from 'lucide-react'
import { toast } from 'sonner'

import { errorMessage } from '@/api/client'
import { useBroadcast, useCancelBroadcast, useSendBroadcast } from '@/api/queries'
import { BroadcastStatusBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuth } from '@/hooks/useAuth'
import { formatDateTime, formatNumber } from '@/lib/format'
import { TelegramPreview } from './TelegramPreview'

interface Props {
  broadcastId: number | null
  onClose: () => void
}

const RECIPIENT_LABELS: Record<string, string> = {
  pending: 'Kutmoqda',
  sent: 'Yuborildi',
  failed: 'Xato',
  blocked_bot: 'Botni bloklagan',
}

/**
 * E'lon tafsiloti.
 *
 * `useBroadcast` yuborish davom etayotganda har 2 sekundda yangilanadi,
 * shu sababli progress jonli ko'rinadi.
 */
export function BroadcastDetailDialog({ broadcastId, onClose }: Props) {
  const { hasRole } = useAuth()
  const { data: broadcast, isLoading } = useBroadcast(broadcastId)
  const sendMutation = useSendBroadcast()
  const cancelMutation = useCancelBroadcast()

  const canManage = hasRole('SUPPORT_OPERATOR')
  const isFinished =
    broadcast?.status === 'sent' || broadcast?.status === 'cancelled'

  const failures =
    broadcast?.recipients.filter((r) => r.status !== 'sent' && r.status !== 'pending') ??
    []

  return (
    <Dialog open={broadcastId !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent size="lg">
        {isLoading || !broadcast ? (
          <div className="space-y-4">
            <Skeleton className="h-8 w-56" />
            <Skeleton className="h-64 w-full" />
          </div>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="flex flex-wrap items-center gap-2">
                {broadcast.title ?? `E'lon #${broadcast.id}`}
                <BroadcastStatusBadge status={broadcast.status} />
              </DialogTitle>
              <DialogDescription>
                {formatDateTime(broadcast.created_at)}
                {broadcast.created_by && ` · ${broadcast.created_by}`}
                {' · '}
                {broadcast.audience}
              </DialogDescription>
            </DialogHeader>

            <TelegramPreview title={broadcast.title ?? ''} body={broadcast.body} />

            {/* Progress */}
            <div className="space-y-2">
              <Progress
                value={
                  broadcast.total_count
                    ? (100 * (broadcast.sent_count + broadcast.failed_count)) /
                      broadcast.total_count
                    : 0
                }
              />
              <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                <span>
                  Jami:{' '}
                  <strong className="text-foreground">
                    {formatNumber(broadcast.total_count)}
                  </strong>
                </span>
                <span>
                  Yuborildi:{' '}
                  <strong style={{ color: 'var(--status-good)' }}>
                    {formatNumber(broadcast.sent_count)}
                  </strong>
                </span>
                {broadcast.failed_count > 0 && (
                  <span>
                    Xato:{' '}
                    <strong style={{ color: 'var(--status-critical)' }}>
                      {formatNumber(broadcast.failed_count)}
                    </strong>
                  </span>
                )}
                {broadcast.finished_at && (
                  <span>Tugadi: {formatDateTime(broadcast.finished_at)}</span>
                )}
              </div>
            </div>

            {broadcast.error_msg && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                {broadcast.error_msg}
              </div>
            )}

            {/* Muammoli qabul qiluvchilar */}
            {failures.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-sm font-medium">
                  Yetib bormaganlar ({failures.length})
                </p>
                <div className="max-h-48 space-y-1 overflow-y-auto">
                  {failures.map((recipient) => (
                    <div
                      key={recipient.user_id}
                      className="flex items-center justify-between gap-2 rounded-md border px-3 py-1.5 text-xs"
                    >
                      <span className="truncate">
                        {recipient.full_name ??
                          (recipient.username
                            ? `@${recipient.username}`
                            : recipient.telegram_id)}
                      </span>
                      <Badge
                        variant={
                          recipient.status === 'blocked_bot' ? 'secondary' : 'destructive'
                        }
                      >
                        {RECIPIENT_LABELS[recipient.status] ?? recipient.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {canManage && !isFinished && (
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() =>
                    cancelMutation.mutate(broadcast.id, {
                      onSuccess: () => toast.success("E'lon bekor qilindi"),
                      onError: (error) =>
                        toast.error(errorMessage(error, 'Bekor qilinmadi')),
                    })
                  }
                  loading={cancelMutation.isPending}
                >
                  <Ban className="h-4 w-4" />
                  Bekor qilish
                </Button>

                {broadcast.status === 'draft' && (
                  <Button
                    onClick={() =>
                      sendMutation.mutate(broadcast.id, {
                        onSuccess: () => toast.success("E'lon navbatga qo'yildi"),
                        onError: (error) =>
                          toast.error(errorMessage(error, 'Yuborilmadi')),
                      })
                    }
                    loading={sendMutation.isPending}
                  >
                    <Send className="h-4 w-4" />
                    Yuborish
                  </Button>
                )}
              </DialogFooter>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
