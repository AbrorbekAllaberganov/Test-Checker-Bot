import * as React from 'react'

import { cn } from '@/lib/utils'

interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  /** 0..100 */
  value: number
  indicatorClassName?: string
}

/**
 * Oddiy progress bar (kvota sarfini ko'rsatish uchun).
 * Radix Progress o'rniga qo'lda — chunki bizga faqat vizual chiziq kerak.
 */
function Progress({ value, className, indicatorClassName, ...props }: ProgressProps) {
  const clamped = Math.min(100, Math.max(0, value))
  return (
    <div
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn('h-2 w-full overflow-hidden rounded-full bg-muted', className)}
      {...props}
    >
      <div
        className={cn('h-full rounded-full bg-primary transition-all', indicatorClassName)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  )
}

export { Progress }
