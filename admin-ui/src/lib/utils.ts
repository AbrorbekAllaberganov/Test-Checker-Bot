import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Tailwind sinflarini xavfsiz birlashtirish (shadcn/ui standarti). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
