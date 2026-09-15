import { Eye, Megaphone, Send, Users } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { errorMessage } from '@/api/client'
import {
  useBroadcasts,
  useCreateBroadcast,
  usePreviewBroadcast,
  type BroadcastPayload,
} from '@/api/queries'
import type { BroadcastAudience, BroadcastPreview } from '@/api/types'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { BroadcastStatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input, Textarea } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateTime, formatNumber } from '@/lib/format'
import { BroadcastDetailDialog } from './BroadcastDetailDialog'
import { TelegramPreview } from './TelegramPreview'

const MAX_LENGTH = 4096

const AUDIENCES: { value: BroadcastAudience; label: string; hint: string }[] = [
  { value: 'all', label: 'Barcha ustozlar', hint: 'Bloklanmagan barcha foydalanuvchilar' },
  {
    value: 'active_subscribers',
    label: 'Pullik obunachilar',
    hint: 'Narxi 0 dan katta tarifdagi faol obunachilar',
  },
  { value: 'free_tier', label: 'Bepul tarifdagilar', hint: 'FREE va obunasi yo’qlar' },
]

export function BroadcastPage() {
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [audience, setAudience] = useState<BroadcastAudience>('all')
  const [preview, setPreview] = useState<BroadcastPreview | null>(null)
  const [openId, setOpenId] = useState<number | null>(null)
  const [page, setPage] = useState(1)

  const previewMutation = usePreviewBroadcast()
  const createMutation = useCreateBroadcast()
  const { data: history, isLoading: historyLoading } = useBroadcasts(page)

  function buildPayload(sendNow: boolean): BroadcastPayload {
    return {
      title: title.trim() || null,
      body: body.trim(),
      parse_mode: 'HTML',
      audience,
      send_now: sendNow,
    }
  }

  function handlePreview() {
    if (!body.trim()) {
      toast.error('Xabar matnini yozing')
      return
    }
    previewMutation.mutate(buildPayload(false), {
      onSuccess: setPreview,
      onError: (error) => toast.error(errorMessage(error, "Ko'rib chiqilmadi")),
    })
  }

  function handleSend(sendNow: boolean) {
    if (!body.trim()) {
      toast.error('Xabar matnini yozing')
      return
    }
    if (sendNow && !preview) {
      toast.error("Avval «Ko'rib chiqish» tugmasini bosing")
      return
    }
    if (
      sendNow &&
      !window.confirm(
        `${preview?.recipients_count ?? 0} ta ustozga xabar yuborilsinmi? ` +
          'Yuborilgan xabarni qaytarib bo’lmaydi.',
      )
    ) {
      return
    }

    createMutation.mutate(buildPayload(sendNow), {
      onSuccess: (created) => {
        toast.success(
          sendNow
            ? `E'lon navbatga qo'yildi (${created.total_count} ta qabul qiluvchi)`
            : 'Qoralama saqlandi',
        )
        setTitle('')
        setBody('')
        setPreview(null)
        if (sendNow) setOpenId(created.id)
      },
      onError: (error) => toast.error(errorMessage(error, 'Saqlanmadi')),
    })
  }

  const remaining = MAX_LENGTH - body.length - (title.length + 4)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Telegram e'lonlari"
        description="Ustozlarga bot orqali ommaviy xabar yuborish"
      />

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Yozish */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle>Yangi e'lon</CardTitle>
            <CardDescription>
              HTML formatlash qo'llab-quvvatlanadi: &lt;b&gt;, &lt;i&gt;,
              &lt;code&gt;, &lt;a href=""&gt;
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="audience">Kimga</Label>
              <Select
                value={audience}
                onValueChange={(value) => {
                  setAudience(value as BroadcastAudience)
                  setPreview(null)
                }}
              >
                <SelectTrigger id="audience">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {AUDIENCES.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {AUDIENCES.find((item) => item.value === audience)?.hint}
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="title">Sarlavha (ixtiyoriy)</Label>
              <Input
                id="title"
                value={title}
                onChange={(event) => {
                  setTitle(event.target.value)
                  setPreview(null)
                }}
                placeholder="Yangilik!"
                maxLength={128}
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="body">Xabar matni</Label>
                <span
                  className={
                    remaining < 0
                      ? 'text-xs text-destructive'
                      : 'text-xs text-muted-foreground'
                  }
                >
                  {remaining} belgi qoldi
                </span>
              </div>
              <Textarea
                id="body"
                value={body}
                onChange={(event) => {
                  setBody(event.target.value)
                  setPreview(null)
                }}
                placeholder="Hurmatli ustozlar! …"
                className="min-h-[180px] font-mono text-xs"
              />
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={handlePreview}
                loading={previewMutation.isPending}
              >
                <Eye className="h-4 w-4" />
                Ko'rib chiqish
              </Button>
              <Button
                variant="ghost"
                onClick={() => handleSend(false)}
                loading={createMutation.isPending && !preview}
              >
                Qoralama saqlash
              </Button>
              <Button
                className="ml-auto"
                onClick={() => handleSend(true)}
                disabled={!preview || remaining < 0}
                loading={createMutation.isPending}
              >
                <Send className="h-4 w-4" />
                Yuborish
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Ko'rinishi */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle>Telegram'da qanday ko'rinadi</CardTitle>
            <CardDescription>
              {preview
                ? `${formatNumber(preview.recipients_count)} ta ustozga yuboriladi`
                : "«Ko'rib chiqish» tugmasini bosing"}
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4">
            <TelegramPreview title={title} body={body} />

            {preview && (
              <>
                <div className="flex items-center gap-2 rounded-lg border p-3">
                  <Users className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">
                    <strong>{formatNumber(preview.recipients_count)}</strong> ta
                    qabul qiluvchi
                  </span>
                </div>

                {preview.sample_recipients.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">
                      Namuna (birinchi {preview.sample_recipients.length} ta):
                    </p>
                    <ul className="space-y-0.5 text-xs text-muted-foreground">
                      {preview.sample_recipients.map((recipient) => (
                        <li key={recipient.user_id} className="truncate">
                          {recipient.full_name ??
                            (recipient.username
                              ? `@${recipient.username}`
                              : recipient.telegram_id)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Tarix */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>E'lonlar tarixi</CardTitle>
        </CardHeader>
        <CardContent>
          {historyLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : !history || history.items.length === 0 ? (
            <EmptyState
              icon={Megaphone}
              title="Hali e'lon yuborilmagan"
              description="Yuqoridagi shakl orqali birinchi e'loningizni yarating."
            />
          ) : (
            <div className="space-y-2">
              {history.items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setOpenId(item.id)}
                  className="flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-colors hover:bg-accent"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {item.title ?? item.body_preview}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {formatDateTime(item.created_at)}
                      {item.created_by && ` · ${item.created_by}`}
                    </p>
                  </div>

                  <div className="w-32 shrink-0">
                    <Progress
                      value={
                        item.total_count
                          ? (100 * (item.sent_count + item.failed_count)) /
                            item.total_count
                          : 0
                      }
                    />
                    <p className="mt-1 text-right text-[11px] text-muted-foreground">
                      {formatNumber(item.sent_count)} / {formatNumber(item.total_count)}
                      {item.failed_count > 0 && ` · ${item.failed_count} xato`}
                    </p>
                  </div>

                  <BroadcastStatusBadge status={item.status} />
                </button>
              ))}

              {history.meta.total_pages > 1 && (
                <div className="flex justify-end gap-2 pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    Oldingi
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= history.meta.total_pages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Keyingi
                  </Button>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <BroadcastDetailDialog
        broadcastId={openId}
        onClose={() => setOpenId(null)}
      />
    </div>
  )
}
