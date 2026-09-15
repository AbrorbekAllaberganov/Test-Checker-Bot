import { cn } from '@/lib/utils'

/**
 * OMR ishonchliligi ko'rsatkichi (0..1).
 *
 * Rang holat palitrasidan olinadi va HECH QACHON yolg'iz ma'no tashimaydi —
 * yonida doim raqam yozuvi turadi.
 */
export function ConfidenceMeter({
  value,
  className,
}: {
  value: number | null | undefined
  className?: string
}) {
  if (value === null || value === undefined) {
    return (
      <span className="text-xs text-muted-foreground" title="Eski skan — o'lchov saqlanmagan">
        —
      </span>
    )
  }

  const percent = Math.round(value * 100)
  const tone =
    percent >= 85
      ? 'var(--status-good)'
      : percent >= 65
        ? 'var(--status-warning)'
        : 'var(--status-critical)'

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full"
          style={{ width: `${percent}%`, background: tone }}
        />
      </div>
      <span className="text-xs tabular-nums text-muted-foreground">{percent}%</span>
    </div>
  )
}
