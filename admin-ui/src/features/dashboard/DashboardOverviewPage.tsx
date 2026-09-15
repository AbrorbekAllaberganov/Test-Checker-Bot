import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  FileText,
  FolderTree,
  RefreshCw,
  ScanLine,
  Users,
  Wallet,
} from 'lucide-react'
import { useState } from 'react'

import { useOverview } from '@/api/queries'
import { errorMessage } from '@/api/client'
import { EmptyState } from '@/components/EmptyState'
import { KpiCard } from '@/components/KpiCard'
import { PageHeader } from '@/components/PageHeader'
import { HealthBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { formatMoney, formatNumber, formatPercent } from '@/lib/format'
import {
  FailureReasonsCard,
  PlanUsageCard,
  QuestionDistributionChart,
  ScanVolumeChart,
  TeacherActivityChart,
  TopTeachersCard,
} from './charts'

const PERIOD_OPTIONS = [
  { value: '7', label: '7 kun' },
  { value: '30', label: '30 kun' },
  { value: '90', label: '90 kun' },
]

export function DashboardOverviewPage() {
  const [days, setDays] = useState('30')
  const { data, isLoading, isFetching, error, refetch } = useOverview(Number(days))

  if (error) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Ma'lumotni yuklab bo'lmadi"
        description={errorMessage(error)}
        action={
          <Button onClick={() => void refetch()}>
            <RefreshCw className="h-4 w-4" />
            Qayta urinish
          </Button>
        }
      />
    )
  }

  const kpi = data?.kpi

  return (
    <div className="space-y-6">
      <PageHeader
        title="Boshqaruv paneli"
        description="Tizimning umumiy holati va asosiy ko'rsatkichlari"
        actions={
          <>
            <Select value={days} onValueChange={setDays}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PERIOD_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="icon"
              onClick={() => void refetch()}
              disabled={isFetching}
              aria-label="Yangilash"
            >
              <RefreshCw className={isFetching ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
            </Button>
          </>
        }
      />

      {/* Asosiy KPI kartochkalari */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Ustozlar"
          value={formatNumber(kpi?.total_teachers)}
          icon={Users}
          hint={`${formatNumber(kpi?.active_teachers_30d)} tasi faol (30 kun)`}
          isLoading={isLoading}
        />
        <KpiCard
          label="Guruhlar"
          value={formatNumber(kpi?.total_groups)}
          icon={FolderTree}
          hint={`${formatNumber(kpi?.total_students)} o'quvchi`}
          isLoading={isLoading}
        />
        <KpiCard
          label="Testlar"
          value={formatNumber(kpi?.total_tests)}
          icon={FileText}
          hint={`O'rtacha ball ${formatPercent(kpi?.avg_score_percent)}`}
          isLoading={isLoading}
        />
        <KpiCard
          label="Jami skanlar"
          value={formatNumber(kpi?.total_scans)}
          icon={ScanLine}
          hint={`Bugun ${formatNumber(kpi?.scans_today)} ta`}
          isLoading={isLoading}
        />
      </div>

      {/* OMR sifati va biznes ko'rsatkichlari */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="OMR aniqlik darajasi"
          value={formatPercent(kpi?.omr_accuracy)}
          icon={CheckCircle2}
          hint="Qo'lsiz, toza o'qilgan varaqlar ulushi"
          tone={
            (kpi?.omr_accuracy ?? 0) >= 90
              ? 'success'
              : (kpi?.omr_accuracy ?? 0) >= 75
                ? 'warning'
                : 'destructive'
          }
          isLoading={isLoading}
        />
        <KpiCard
          label="Ko'rik kutmoqda"
          value={formatNumber(kpi?.needs_review_count)}
          icon={AlertTriangle}
          hint="Ikkilangan yoki bo'sh javoblar"
          tone={kpi?.needs_review_count ? 'warning' : 'success'}
          isLoading={isLoading}
        />
        <KpiCard
          label="Xato ulushi"
          value={formatPercent(kpi?.error_rate)}
          icon={Ban}
          hint={`${formatNumber(kpi?.blocked_teachers)} ta bloklangan ustoz`}
          tone={(kpi?.error_rate ?? 0) > 10 ? 'destructive' : 'default'}
          isLoading={isLoading}
        />
        <KpiCard
          label="Pullik obunachilar"
          value={formatNumber(kpi?.paying_subscribers)}
          icon={Wallet}
          hint={`Taxminiy oylik: ${formatMoney(
            data?.plans.reduce((sum, plan) => sum + plan.mrr_uzs, 0) ?? 0,
            { zeroAsFree: false },
          )}`}
          tone="success"
          isLoading={isLoading}
        />
      </div>

      {/* Grafiklar */}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ScanVolumeChart data={data?.scan_timeseries ?? []} isLoading={isLoading} />
        </div>
        <QuestionDistributionChart
          data={data?.question_distribution ?? []}
          isLoading={isLoading}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <TeacherActivityChart
            data={data?.teacher_activity ?? []}
            isLoading={isLoading}
          />
        </div>
        <FailureReasonsCard data={data?.failures} isLoading={isLoading} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <PlanUsageCard data={data?.plans ?? []} isLoading={isLoading} />
        </div>
        <TopTeachersCard data={data?.top_teachers ?? []} isLoading={isLoading} />
      </div>

      {/* Tizim holati */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Tizim holati</CardTitle>
              <CardDescription>Navbat va xizmatlar sog'ligi</CardDescription>
            </div>
            {data && <HealthBadge status={data.system.overall} />}
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-20 w-full" />
          ) : (
            <div className="grid gap-3 sm:grid-cols-3">
              {data?.system.components.map((component) => (
                <div
                  key={component.name}
                  className="rounded-lg border p-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium capitalize">
                      {component.name}
                    </span>
                    <HealthBadge status={component.status} />
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground">
                    {component.detail}
                  </p>
                  {component.name === 'redis' && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Navbatda:{' '}
                      <strong className="text-foreground">
                        {formatNumber(
                          Number(component.metrics.queue_length ?? 0),
                        )}
                      </strong>
                    </p>
                  )}
                  {component.name === 'celery' && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Faol vazifalar:{' '}
                      <strong className="text-foreground">
                        {formatNumber(Number(component.metrics.active_total ?? 0))}
                      </strong>
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
