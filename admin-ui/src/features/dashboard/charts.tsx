import { Award, ShieldAlert } from 'lucide-react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type {
  FailureBreakdown,
  PlanUsage,
  QuestionDistributionItem,
  ScanPoint,
  TeacherActivityPoint,
  TopTeacher,
} from '@/api/types'
import { EmptyState } from '@/components/EmptyState'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import {
  displayName,
  formatChartDate,
  formatMoney,
  formatNumber,
  formatPercent,
} from '@/lib/format'

/**
 * Dashboard grafiklari.
 *
 * Rang qoidalari (src/index.css da tokenlar):
 *   • `--series-1..3` — KATEGORIK slotlar, qat'iy tartibda, aylantirilmaydi.
 *   • `--status-*`    — holat ranglari (yaxshi/ogohlantirish/xato); ular
 *     hech qachon oddiy "qator rangi" sifatida ishlatilmaydi.
 *
 * Har bir grafikda legend va tooltip bor — rang yagona ma'no tashuvchi
 * kanal bo'lib qolmasligi uchun (rang ko'rlik va bosma nusxa uchun).
 *
 * Ikki y-o'qli ("dual axis") grafik yo'q: o'lchovi har xil ko'rsatkichlar
 * alohida grafiklarga ajratilgan.
 */

const SERIES = {
  one: 'var(--series-1)',
  two: 'var(--series-2)',
  three: 'var(--series-3)',
} as const

const STATUS = {
  good: 'var(--status-good)',
  warning: 'var(--status-warning)',
  critical: 'var(--status-critical)',
} as const

const AXIS_PROPS = {
  stroke: 'hsl(var(--muted-foreground))',
  fontSize: 11,
  tickLine: false,
  axisLine: false,
} as const

/** Recharts tooltip'i uchun umumiy uslub — shadcn popover tokenlariga mos. */
const TOOLTIP_STYLE = {
  contentStyle: {
    background: 'hsl(var(--popover))',
    border: '1px solid hsl(var(--border))',
    borderRadius: '8px',
    fontSize: '12px',
    color: 'hsl(var(--popover-foreground))',
  },
  labelStyle: { color: 'hsl(var(--muted-foreground))', marginBottom: 4 },
  // Matn har doim matn rangida — qator rangida emas (o'qilishi uchun).
  itemStyle: { color: 'hsl(var(--popover-foreground))' },
} as const

const LEGEND_STYLE = { fontSize: 12, paddingTop: 8 } as const

function ChartFrame({
  title,
  description,
  isLoading,
  isEmpty,
  emptyLabel,
  children,
}: {
  title: string
  description?: string
  isLoading: boolean
  isEmpty?: boolean
  emptyLabel?: string
  children: React.ReactNode
}) {
  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : isEmpty ? (
          <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
            {emptyLabel ?? "Ma'lumot yo'q"}
          </div>
        ) : (
          children
        )}
      </CardContent>
    </Card>
  )
}

// ── Skan hajmi (holat bo'yicha) ─────────────────────────────────────────

export function ScanVolumeChart({
  data,
  isLoading,
}: {
  data: ScanPoint[]
  isLoading: boolean
}) {
  const hasData = data.some((point) => point.total > 0)

  return (
    <ChartFrame
      title="Skanlar hajmi"
      description="Kunlik o'qish natijalari — toza, ko'rik kerak, xato"
      isLoading={isLoading}
      isEmpty={!hasData}
      emptyLabel="Bu davrda skan bo'lmagan"
    >
      <ResponsiveContainer width="100%" height={260}>
        <AreaChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <defs>
            {/* Yumshoq gradient — chiziq ostidagi maydon uchun */}
            {(['good', 'warning', 'critical'] as const).map((key) => (
              <linearGradient key={key} id={`fill-${key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={STATUS[key]} stopOpacity={0.35} />
                <stop offset="100%" stopColor={STATUS[key]} stopOpacity={0.02} />
              </linearGradient>
            ))}
          </defs>

          {/* Tarmoq chizig'i recessiv: faqat gorizontal, ingichka */}
          <CartesianGrid
            strokeDasharray="3 3"
            vertical={false}
            stroke="hsl(var(--border))"
          />
          <XAxis dataKey="date" tickFormatter={formatChartDate} {...AXIS_PROPS} />
          <YAxis allowDecimals={false} {...AXIS_PROPS} />
          <Tooltip
            {...TOOLTIP_STYLE}
            labelFormatter={(label) => formatChartDate(String(label))}
          />
          <Legend wrapperStyle={LEGEND_STYLE} />

          <Area
            type="monotone"
            dataKey="clean"
            name="Toza o'qildi"
            stackId="1"
            stroke={STATUS.good}
            strokeWidth={2}
            fill="url(#fill-good)"
          />
          <Area
            type="monotone"
            dataKey="review"
            name="Ko'rik kerak"
            stackId="1"
            stroke={STATUS.warning}
            strokeWidth={2}
            fill="url(#fill-warning)"
          />
          <Area
            type="monotone"
            dataKey="errors"
            name="Xato"
            stackId="1"
            stroke={STATUS.critical}
            strokeWidth={2}
            fill="url(#fill-critical)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

// ── Ustozlar faolligi ───────────────────────────────────────────────────

export function TeacherActivityChart({
  data,
  isLoading,
}: {
  data: TeacherActivityPoint[]
  isLoading: boolean
}) {
  const hasData = data.some((p) => p.active_teachers > 0 || p.new_teachers > 0)

  return (
    <ChartFrame
      title="Ustozlar faolligi"
      description="Kuniga faol (skan yuborgan) va yangi qo'shilgan ustozlar"
      isLoading={isLoading}
      isEmpty={!hasData}
    >
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid
            strokeDasharray="3 3"
            vertical={false}
            stroke="hsl(var(--border))"
          />
          <XAxis dataKey="date" tickFormatter={formatChartDate} {...AXIS_PROPS} />
          {/* Bitta y-o'q: ikkala qator ham "ustozlar soni" — bir xil o'lchov */}
          <YAxis allowDecimals={false} {...AXIS_PROPS} />
          <Tooltip
            {...TOOLTIP_STYLE}
            labelFormatter={(label) => formatChartDate(String(label))}
          />
          <Legend wrapperStyle={LEGEND_STYLE} />

          <Line
            type="monotone"
            dataKey="active_teachers"
            name="Faol ustozlar"
            stroke={SERIES.one}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
          <Line
            type="monotone"
            dataKey="new_teachers"
            name="Yangi ustozlar"
            stroke={SERIES.two}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

// ── Savollar soni taqsimoti ─────────────────────────────────────────────

export function QuestionDistributionChart({
  data,
  isLoading,
}: {
  data: QuestionDistributionItem[]
  isLoading: boolean
}) {
  const chartData = data.map((item) => ({
    ...item,
    label: `${item.question_count} savol`,
  }))

  return (
    <ChartFrame
      title="Varaq turlari"
      description="40 / 50 / 90 savolli testlar va skanlar"
      isLoading={isLoading}
      isEmpty={chartData.length === 0}
    >
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid
            strokeDasharray="3 3"
            vertical={false}
            stroke="hsl(var(--border))"
          />
          <XAxis dataKey="label" {...AXIS_PROPS} />
          <YAxis allowDecimals={false} {...AXIS_PROPS} />
          <Tooltip {...TOOLTIP_STYLE} cursor={{ fill: 'hsl(var(--muted))' }} />
          <Legend wrapperStyle={LEGEND_STYLE} />

          {/* Ustun uchlari yumaloq, ustunlar orasida 2px oraliq */}
          <Bar
            dataKey="tests"
            name="Testlar"
            fill={SERIES.one}
            radius={[4, 4, 0, 0]}
            maxBarSize={28}
          />
          <Bar
            dataKey="scans"
            name="Skanlar"
            fill={SERIES.three}
            radius={[4, 4, 0, 0]}
            maxBarSize={28}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

// ── Nosozlik sabablari (jadval — grafik emas) ───────────────────────────

export function FailureReasonsCard({
  data,
  isLoading,
}: {
  data?: FailureBreakdown
  isLoading: boolean
}) {
  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle>O'qish muammolari</CardTitle>
        <CardDescription>
          {data
            ? `${data.period_days} kunda ${formatNumber(data.total_scans)} skandan`
            : 'Yuklanmoqda…'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading || !data ? (
          <Skeleton className="h-52 w-full" />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Ikkilanish</p>
                <p className="mt-1 text-lg font-semibold">
                  {formatPercent(data.ambiguity_rate)}
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatNumber(data.ambiguous_count)} ta varaq
                </p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Xato</p>
                <p className="mt-1 text-lg font-semibold">
                  {formatPercent(data.failure_rate)}
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatNumber(data.error_count)} ta varaq
                </p>
              </div>
            </div>

            {data.reasons.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                Bu davrda xato qayd etilmagan
              </p>
            ) : (
              <div className="space-y-2">
                {data.reasons.slice(0, 5).map((reason) => {
                  const share = data.error_count
                    ? (100 * reason.count) / data.error_count
                    : 0
                  return (
                    <div key={reason.reason} className="space-y-1">
                      <div className="flex items-center justify-between gap-2 text-xs">
                        <span className="truncate" title={reason.reason}>
                          {reason.reason}
                        </span>
                        <span className="shrink-0 font-medium">
                          {formatNumber(reason.count)}
                        </span>
                      </div>
                      <Progress
                        value={share}
                        indicatorClassName="bg-[var(--status-critical)]"
                      />
                    </div>
                  )
                })}
              </div>
            )}

            <p className="text-xs text-muted-foreground">
              Qo'lda tuzatilgan: {formatNumber(data.overridden_count)} ta
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}

// ── Tariflar bo'yicha sarf ──────────────────────────────────────────────

export function PlanUsageCard({
  data,
  isLoading,
}: {
  data: PlanUsage[]
  isLoading: boolean
}) {
  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle>Tariflar kesimi</CardTitle>
        <CardDescription>Obunachilar, sarflangan skan va taxminiy daromad</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-52 w-full" />
        ) : data.length === 0 ? (
          <EmptyState icon={ShieldAlert} title="Tariflar topilmadi" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 text-left font-medium">Tarif</th>
                  <th className="py-2 text-right font-medium">Obunachi</th>
                  <th className="py-2 text-right font-medium">Skan</th>
                  <th className="py-2 text-right font-medium">Narx</th>
                  <th className="py-2 text-right font-medium">Oylik</th>
                </tr>
              </thead>
              <tbody>
                {data.map((plan) => (
                  <tr key={plan.plan_code} className="border-b last:border-0">
                    <td className="py-2.5 font-medium">{plan.plan_name}</td>
                    <td className="py-2.5 text-right">
                      {formatNumber(plan.subscribers)}
                    </td>
                    <td className="py-2.5 text-right text-muted-foreground">
                      {formatNumber(plan.scans_used)}
                    </td>
                    <td className="py-2.5 text-right text-muted-foreground">
                      {formatMoney(plan.price_uzs)}
                    </td>
                    <td className="py-2.5 text-right font-medium">
                      {formatMoney(plan.mrr_uzs, { zeroAsFree: false })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ── Eng faol ustozlar ───────────────────────────────────────────────────

export function TopTeachersCard({
  data,
  isLoading,
}: {
  data: TopTeacher[]
  isLoading: boolean
}) {
  const max = Math.max(...data.map((t) => t.scans), 1)

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle>Eng faol ustozlar</CardTitle>
        <CardDescription>Davr bo'yicha skanlar soni</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-52 w-full" />
        ) : data.length === 0 ? (
          <EmptyState icon={Award} title="Hali skan yo'q" />
        ) : (
          <ol className="space-y-2.5">
            {data.map((teacher, index) => (
              <li key={teacher.user_id} className="space-y-1">
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="w-4 shrink-0 text-xs text-muted-foreground">
                      {index + 1}.
                    </span>
                    <span className="truncate">
                      {displayName(
                        teacher.full_name,
                        teacher.username,
                        teacher.telegram_id,
                      )}
                    </span>
                  </span>
                  <span className="shrink-0 font-medium">
                    {formatNumber(teacher.scans)}
                  </span>
                </div>
                <Progress
                  value={(100 * teacher.scans) / max}
                  indicatorClassName="bg-[var(--series-1)]"
                />
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  )
}
