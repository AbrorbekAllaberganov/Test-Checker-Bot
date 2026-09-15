import type { LucideIcon } from 'lucide-react'
import { TrendingDown, TrendingUp } from 'lucide-react'

import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface KpiCardProps {
  label: string
  value: string
  icon: LucideIcon
  /** Qo'shimcha izoh (masalan "bugun +12"). */
  hint?: string
  /** Ijobiy/salbiy o'zgarish foizi. */
  trend?: number
  /** Trend o'sishi yomon bo'lsa (masalan xatolar) — rangni teskari qiladi. */
  invertTrend?: boolean
  tone?: 'default' | 'success' | 'warning' | 'destructive'
  isLoading?: boolean
}

const TONE_CLASSES: Record<NonNullable<KpiCardProps['tone']>, string> = {
  default: 'bg-primary/10 text-primary',
  success: 'bg-success/10 text-success',
  warning: 'bg-warning/15 text-warning',
  destructive: 'bg-destructive/10 text-destructive',
}

export function KpiCard({
  label,
  value,
  icon: Icon,
  hint,
  trend,
  invertTrend = false,
  tone = 'default',
  isLoading = false,
}: KpiCardProps) {
  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-5">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="mt-3 h-8 w-20" />
          <Skeleton className="mt-2 h-3 w-16" />
        </CardContent>
      </Card>
    )
  }

  const isPositive = (trend ?? 0) >= 0
  const trendIsGood = invertTrend ? !isPositive : isPositive

  return (
    <Card className="transition-shadow hover:shadow-md">
      <CardContent className="flex items-start justify-between gap-4 p-5">
        <div className="min-w-0">
          {/* Yorliqlar o'zbekcha va uzun — kesish o'rniga ikkinchi qatorga
              o'tkazamiz, aks holda 4 ustunli tor gridda o'qib bo'lmaydi. */}
          <p className="text-sm leading-tight text-muted-foreground">{label}</p>
          <p className="mt-1.5 text-2xl font-semibold tracking-tight">{value}</p>

          {(hint || trend !== undefined) && (
            <div className="mt-1.5 flex flex-wrap items-center gap-x-1.5 text-xs">
              {trend !== undefined && (
                <span
                  className={cn(
                    'flex items-center gap-0.5 font-medium',
                    trendIsGood ? 'text-success' : 'text-destructive',
                  )}
                >
                  {isPositive ? (
                    <TrendingUp className="h-3 w-3" />
                  ) : (
                    <TrendingDown className="h-3 w-3" />
                  )}
                  {Math.abs(trend).toFixed(1)}%
                </span>
              )}
              {hint && <span className="text-muted-foreground">{hint}</span>}
            </div>
          )}
        </div>

        <div className={cn('rounded-lg p-2.5', TONE_CLASSES[tone])}>
          <Icon className="h-5 w-5" />
        </div>
      </CardContent>
    </Card>
  )
}
