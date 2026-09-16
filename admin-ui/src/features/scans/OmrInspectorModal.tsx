import {
  AlertTriangle,
  Check,
  CheckCheck,
  ImageOff,
  RotateCcw,
  Save,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { errorMessage } from '@/api/client'
import { useOverrideScan, useResolveScan, useScan } from '@/api/queries'
import type { OmrInspector, ScanQuestionRow } from '@/api/types'
import { ScanStatusBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuthedBlobUrl } from '@/hooks/useAuthedBlobUrl'
import { formatDateTime, formatPercent } from '@/lib/format'
import { cn } from '@/lib/utils'
import { ConfidenceMeter } from './ConfidenceMeter'

interface Props {
  attemptId: number | null
  onClose: () => void
}

/** Tuzatilayotgan javoblar: savol → harf yoki null (bo'sh). */
type Draft = Record<string, string | null>

/**
 * Doira to'ldirilganligini rang bilan ko'rsatadi.
 *
 * `fill_ratio` 0..1 — bu KETMA-KET (sequential) o'lchov, shu sababli bitta
 * hue ning shaffofligi bilan beriladi (kamalak emas). Tanlangan javob
 * qo'shimcha ramka bilan ajratiladi — rang yagona belgi bo'lib qolmasligi
 * uchun.
 */
function BubbleView({
  letter,
  fillRatio,
  isSelected,
  isCorrectKey,
  isDraftPick,
  onPick,
}: {
  letter: string
  fillRatio: number
  isSelected: boolean
  isCorrectKey: boolean
  isDraftPick: boolean
  onPick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onPick}
      title={`${letter} — to'ldirilganlik ${Math.round(fillRatio * 100)}%${
        isCorrectKey ? ' (to’g’ri javob)' : ''
      }`}
      className={cn(
        'bubble-cell relative',
        isDraftPick
          ? 'border-primary ring-2 ring-primary'
          : isSelected
            ? 'border-foreground/60'
            : 'border-border',
      )}
      style={{
        // Sequential: bitta hue, to'ldirilganlikka mos zichlik.
        background: `color-mix(in srgb, var(--series-1) ${Math.round(
          fillRatio * 100,
        )}%, transparent)`,
      }}
    >
      <span className={cn(fillRatio > 0.55 && 'text-white')}>{letter}</span>
      {isCorrectKey && (
        <span
          className="absolute -right-1 -top-1 flex h-3 w-3 items-center justify-center rounded-full"
          style={{ background: 'var(--status-good)' }}
        >
          <Check className="h-2 w-2 text-white" />
        </span>
      )}
    </button>
  )
}

function QuestionRow({
  row,
  letters,
  draftValue,
  onChange,
}: {
  row: ScanQuestionRow
  letters: string[]
  draftValue: string | null | undefined
  onChange: (value: string | null) => void
}) {
  const current = draftValue !== undefined ? draftValue : row.detected
  const isChanged = draftValue !== undefined && draftValue !== row.detected
  const isCorrectNow = current !== null && current === row.correct

  return (
    <div
      className={cn(
        'flex items-center gap-3 rounded-lg border p-2',
        isChanged && 'border-primary/60 bg-primary/5',
        row.flag === 'ambiguous' && !isChanged && 'border-warning/50',
      )}
    >
      <span className="w-8 shrink-0 text-xs font-medium tabular-nums text-muted-foreground">
        {row.question}
      </span>

      <div className="flex flex-wrap gap-1.5">
        {letters.map((letter) => {
          const bubble = row.bubbles.find((b) => b.letter === letter)
          return (
            <BubbleView
              key={letter}
              letter={letter}
              fillRatio={bubble?.fill_ratio ?? 0}
              isSelected={row.detected === letter}
              isCorrectKey={row.correct === letter}
              isDraftPick={current === letter}
              // Bosilgan harf allaqachon tanlangan bo'lsa — bo'sh qilamiz.
              onPick={() => onChange(current === letter ? null : letter)}
            />
          )
        })}
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-2">
        {row.flag === 'ambiguous' && (
          <Badge variant="warning">
            <AlertTriangle className="h-3 w-3" />
            Ikkilanish
          </Badge>
        )}
        {row.flag === 'blank' && <Badge variant="secondary">Bo'sh</Badge>}

        <span className="w-16 text-right text-xs">
          {isCorrectNow ? (
            <span style={{ color: 'var(--status-good)' }}>To'g'ri</span>
          ) : (
            <span style={{ color: 'var(--status-critical)' }}>
              Kalit: {row.correct ?? '—'}
            </span>
          )}
        </span>

        {current !== null && (
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            title="Javobni bo'sh qilish"
            onClick={() => onChange(null)}
          >
            <X className="h-3 w-3" />
          </Button>
        )}
      </div>
    </div>
  )
}

/**
 * Auth'li endpointdan skan fayli. `<img src>` to'g'ridan-to'g'ri ishlamaydi —
 * Bearer token kerak, shu sababli blob URL orqali (useAuthedBlobUrl).
 *
 * Fayl PDF ham bo'lishi mumkin (bot PDF hujjatni qabul qiladi) — u holda
 * `<img>` buzilgan rasm ko'rsatardi, shu sababli brauzerning PDF ko'ruvchisi
 * `<iframe>` da beriladi (Mini App'dagi mantiq bilan bir xil).
 */
function AuthedFilePreview({ url, alt }: { url: string; alt: string }) {
  const { blobUrl, isPdf, loading, error } = useAuthedBlobUrl(url)

  if (loading) {
    return <Skeleton className="h-[52vh] w-full rounded-lg" />
  }
  if (error || !blobUrl) {
    return (
      <div className="flex h-[32vh] flex-col items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
        <ImageOff className="mb-2 h-8 w-8 opacity-40" />
        Fayl yuklanmadi
      </div>
    )
  }
  if (isPdf) {
    return (
      <>
        <iframe
          src={`${blobUrl}#toolbar=0&navpanes=0`}
          title={alt}
          className="h-[52vh] w-full rounded-lg border bg-white"
        />
        <p className="mt-1 text-center text-xs text-muted-foreground">
          <a
            href={blobUrl}
            target="_blank"
            rel="noreferrer"
            className="underline underline-offset-2"
          >
            PDF'ni alohida oynada ochish
          </a>
        </p>
      </>
    )
  }
  return (
    <>
      <a href={blobUrl} target="_blank" rel="noreferrer">
        <img
          src={blobUrl}
          alt={alt}
          className="max-h-[52vh] w-full rounded-lg border object-contain"
        />
      </a>
      <p className="mt-1 text-center text-xs text-muted-foreground">
        Kattalashtirish uchun rasmni bosing
      </p>
    </>
  )
}

function ImagePanel({ scan }: { scan: OmrInspector }) {
  const [tab, setTab] = useState(scan.debug_url ? 'debug' : 'source')

  const images = [
    { key: 'source', label: 'Asl surat', url: scan.source_url },
    { key: 'debug', label: 'OMR annotatsiya', url: scan.debug_url },
  ].filter((image) => image.url)

  if (images.length === 0) {
    return (
      <div className="flex min-h-[300px] flex-col items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
        <ImageOff className="mb-2 h-8 w-8 opacity-40" />
        Rasm saqlanmagan
        <p className="mt-1 max-w-xs px-4 text-center text-xs">
          Annotatsiya rasmi faqat <code>OMR_DEBUG=true</code> bo'lganda saqlanadi.
        </p>
      </div>
    )
  }

  return (
    // `h-full` YO'Q: chap ustun grid qatoriga cho'zilgan bo'ladi va rasm
    // paneli 100% balandlikni egallab, pastdagi "Natija"/"Ishonchlilik"
    // kartochkalarini ustundan tashqariga (footer ustiga) itarib yuborardi.
    <Tabs value={tab} onValueChange={setTab} className="flex flex-col">
      <TabsList className="w-full">
        {images.map((image) => (
          <TabsTrigger key={image.key} value={image.key} className="flex-1">
            {image.label}
          </TabsTrigger>
        ))}
      </TabsList>

      {images.map((image) => (
        <TabsContent key={image.key} value={image.key} className="mt-2">
          <AuthedFilePreview url={image.url!} alt={image.label} />
        </TabsContent>
      ))}
    </Tabs>
  )
}

export function OmrInspectorModal({ attemptId, onClose }: Props) {
  const { data: scan, isLoading } = useScan(attemptId)
  const override = useOverrideScan()
  const resolve = useResolveScan()

  const [draft, setDraft] = useState<Draft>({})
  const [notifyTeacher, setNotifyTeacher] = useState(true)
  const [onlyProblems, setOnlyProblems] = useState(false)

  // Boshqa skanga o'tilganda qoralama tozalanadi.
  useEffect(() => {
    setDraft({})
    setOnlyProblems(false)
  }, [attemptId])

  const changedCount = Object.keys(draft).length

  const visibleQuestions = useMemo(() => {
    if (!scan) return []
    if (!onlyProblems) return scan.questions
    return scan.questions.filter(
      (row) => !row.is_correct || row.flag !== null || row.detected === null,
    )
  }, [scan, onlyProblems])

  function handleSave() {
    if (!scan || changedCount === 0) return
    override.mutate(
      {
        attemptId: scan.id,
        answers: draft,
        notifyTeacher,
      },
      {
        onSuccess: (updated) => {
          toast.success(
            `Natija yangilandi: ${updated.score}/${updated.total} (${formatPercent(
              updated.percent,
            )})`,
          )
          setDraft({})
        },
        onError: (error) => toast.error(errorMessage(error, 'Saqlanmadi')),
      },
    )
  }

  function handleResolve() {
    if (!scan) return
    resolve.mutate(
      { attemptId: scan.id },
      {
        onSuccess: () => toast.success("Ko'rik navbatidan chiqarildi"),
        onError: (error) => toast.error(errorMessage(error, 'Amal bajarilmadi')),
      },
    )
  }

  return (
    <Dialog open={attemptId !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent size="xl" className="max-h-[92vh]">
        {isLoading || !scan ? (
          <div className="space-y-4">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-[60vh] w-full" />
          </div>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="flex flex-wrap items-center gap-2">
                OMR inspektori — #{scan.id}
                <ScanStatusBadge
                  status={scan.status}
                  needsReview={scan.needs_review}
                  manualOverride={scan.manual_override}
                />
              </DialogTitle>
              <DialogDescription>
                {scan.student_name ?? "Aniqlanmagan o'quvchi"}
                {scan.test_title && ` · ${scan.test_title}`}
                {scan.group_name && ` · ${scan.group_name}`}
                {' · '}
                {formatDateTime(scan.created_at)}
              </DialogDescription>
            </DialogHeader>

            {scan.error_msg && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                {scan.error_msg}
              </div>
            )}

            <div className="grid gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
              {/* Chap: rasmlar va xulosa */}
              <div className="space-y-3">
                <ImagePanel scan={scan} />

                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-lg border p-3">
                    <p className="text-xs text-muted-foreground">Natija</p>
                    <p className="mt-0.5 text-lg font-semibold">
                      {scan.score ?? '—'}/{scan.total ?? '—'}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatPercent(scan.percent)}
                    </p>
                  </div>
                  <div className="rounded-lg border p-3">
                    <p className="text-xs text-muted-foreground">Ishonchlilik</p>
                    <div className="mt-2">
                      <ConfidenceMeter value={scan.confidence} />
                    </div>
                  </div>
                </div>

                {scan.reviewed_by && (
                  <p className="text-xs text-muted-foreground">
                    Ko'rikdan o'tkazgan: {scan.reviewed_by} ·{' '}
                    {formatDateTime(scan.reviewed_at)}
                  </p>
                )}
              </div>

              {/* O'ng: javoblar */}
              <div className="flex min-h-0 flex-col">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Switch
                      id="only-problems"
                      checked={onlyProblems}
                      onCheckedChange={setOnlyProblems}
                    />
                    <label htmlFor="only-problems" className="text-xs">
                      Faqat muammoli savollar
                    </label>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {visibleQuestions.length} / {scan.questions.length} savol
                  </span>
                </div>

                <div className="max-h-[52vh] space-y-1.5 overflow-y-auto pr-1">
                  {visibleQuestions.length === 0 ? (
                    <p className="py-8 text-center text-sm text-muted-foreground">
                      Muammoli savol yo'q — barchasi to'g'ri o'qilgan
                    </p>
                  ) : (
                    visibleQuestions.map((row) => (
                      <QuestionRow
                        key={row.question}
                        row={row}
                        letters={scan.variant_letters}
                        draftValue={draft[row.question]}
                        onChange={(value) =>
                          setDraft((prev) => {
                            // Asl qiymatga qaytarilsa — qoralamadan olib tashlaymiz.
                            if (value === row.detected) {
                              const { [row.question]: _removed, ...rest } = prev
                              return rest
                            }
                            return { ...prev, [row.question]: value }
                          })
                        }
                      />
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* Pastki panel */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
              <div className="flex items-center gap-2">
                <Switch
                  id="notify"
                  checked={notifyTeacher}
                  onCheckedChange={setNotifyTeacher}
                />
                <label htmlFor="notify" className="text-xs text-muted-foreground">
                  Ustozga Telegram orqali xabar berish
                </label>
              </div>

              <div className="flex flex-wrap gap-2">
                {changedCount > 0 && (
                  <Button variant="ghost" onClick={() => setDraft({})}>
                    <RotateCcw className="h-4 w-4" />
                    Bekor qilish
                  </Button>
                )}

                {scan.needs_review && changedCount === 0 && (
                  <Button
                    variant="outline"
                    onClick={handleResolve}
                    loading={resolve.isPending}
                  >
                    <CheckCheck className="h-4 w-4" />
                    To'g'ri, tuzatish shart emas
                  </Button>
                )}

                <Button
                  onClick={handleSave}
                  disabled={changedCount === 0}
                  loading={override.isPending}
                >
                  <Save className="h-4 w-4" />
                  {changedCount > 0
                    ? `${changedCount} ta javobni saqlash`
                    : "O'zgarish yo'q"}
                </Button>
              </div>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
