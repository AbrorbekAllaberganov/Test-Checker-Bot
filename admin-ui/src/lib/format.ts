import { format, formatDistanceToNow, parseISO } from 'date-fns'

/**
 * Formatlash yordamchilari.
 *
 * Backend barcha sanalarni ISO-8601 (UTC, timezone bilan) qaytaradi;
 * brauzer ularni foydalanuvchi mintaqasida ko'rsatadi.
 */

const DATE_TIME = 'dd.MM.yyyy HH:mm'
const DATE_ONLY = 'dd.MM.yyyy'

function toDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null
  const date = typeof value === 'string' ? parseISO(value) : value
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatDateTime(value: string | Date | null | undefined): string {
  const date = toDate(value)
  return date ? format(date, DATE_TIME) : '—'
}

export function formatDate(value: string | Date | null | undefined): string {
  const date = toDate(value)
  return date ? format(date, DATE_ONLY) : '—'
}

/** "3 kun oldin" ko'rinishidagi nisbiy vaqt. */
export function formatRelative(value: string | Date | null | undefined): string {
  const date = toDate(value)
  return date ? formatDistanceToNow(date, { addSuffix: true }) : '—'
}

/** Grafik o'qi uchun qisqa sana: "15.09". */
export function formatChartDate(value: string): string {
  const date = toDate(value)
  return date ? format(date, 'dd.MM') : value
}

/** 1234567 → "1 234 567" */
export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat('uz-UZ').format(value)
}

/**
 * 99000 → "99 000 so'm"
 *
 * `zeroAsFree` — TARIF narxi uchun 0 "Bepul" degani, lekin JAMI daromad
 * uchun 0 "Bepul" emas, "0 so'm". Shu sababli chaqiruvchi o'zi tanlaydi.
 */
export function formatMoney(
  value: number | null | undefined,
  { zeroAsFree = true }: { zeroAsFree?: boolean } = {},
): string {
  if (value === null || value === undefined) return '—'
  if (value === 0 && zeroAsFree) return 'Bepul'
  return `${new Intl.NumberFormat('uz-UZ').format(value)} so'm`
}

export function formatPercent(
  value: number | null | undefined,
  digits = 1,
): string {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(digits)}%`
}

/** Limit `null` bo'lsa "Cheksiz". */
export function formatLimit(value: number | null | undefined): string {
  return value === null || value === undefined ? 'Cheksiz' : formatNumber(value)
}

export function displayName(
  fullName?: string | null,
  username?: string | null,
  telegramId?: number | null,
): string {
  if (fullName) return fullName
  if (username) return `@${username}`
  return telegramId ? `tg:${telegramId}` : '—'
}

/** Ism-familiyadan avatar uchun bosh harflar. */
export function initials(name?: string | null): string {
  if (!name) return '?'
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}
