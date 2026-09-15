import type { ColumnDef } from '@tanstack/react-table'
import { Plus, Search } from 'lucide-react'
import { useMemo, useState } from 'react'

import { usePlans, useSubscriptions, type SubscriptionListParams } from '@/api/queries'
import type { PlanOut, SubscriptionRow } from '@/api/types'
import { DataTable } from '@/components/DataTable'
import { PageHeader } from '@/components/PageHeader'
import { SubscriptionBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { useAuth } from '@/hooks/useAuth'
import { useDebounce } from '@/hooks/useDebounce'
import {
  displayName,
  formatDate,
  formatLimit,
  formatMoney,
  formatNumber,
} from '@/lib/format'
import { PlanEditorDialog } from './PlanEditorDialog'

const PAGE_SIZE = 25
const ALL = '__all__'

function PlanCard({
  plan,
  onEdit,
  canEdit,
}: {
  plan: PlanOut
  onEdit: () => void
  canEdit: boolean
}) {
  return (
    <Card className={plan.is_active ? undefined : 'opacity-60'}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate font-semibold">{plan.name}</p>
            <p className="text-xs text-muted-foreground">{plan.code}</p>
          </div>
          {!plan.is_active && <Badge variant="secondary">Nofaol</Badge>}
        </div>

        <p className="mt-2 text-lg font-semibold">{formatMoney(plan.price_uzs)}</p>

        <dl className="mt-3 space-y-1 text-xs text-muted-foreground">
          <div className="flex justify-between">
            <dt>Oylik skan</dt>
            <dd className="font-medium text-foreground">
              {formatLimit(plan.monthly_scan_limit)}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt>Guruhlar</dt>
            <dd className="font-medium text-foreground">
              {formatLimit(plan.max_groups)}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt>Guruhda o'quvchi</dt>
            <dd className="font-medium text-foreground">
              {formatLimit(plan.max_students_per_group)}
            </dd>
          </div>
          <div className="flex justify-between border-t pt-1">
            <dt>Obunachilar</dt>
            <dd className="font-medium text-foreground">
              {formatNumber(plan.subscribers_count)}
            </dd>
          </div>
        </dl>

        {canEdit && (
          <Button
            variant="outline"
            size="sm"
            className="mt-3 w-full"
            onClick={onEdit}
          >
            Tahrirlash
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

export function SubscriptionsPage() {
  const { hasRole } = useAuth()
  const canEdit = hasRole('SUPERADMIN')

  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [planFilter, setPlanFilter] = useState(ALL)
  const [overQuota, setOverQuota] = useState(false)
  const [editingPlan, setEditingPlan] = useState<PlanOut | null>(null)
  const [isCreating, setIsCreating] = useState(false)

  const debouncedSearch = useDebounce(search)
  const { data: plans, isLoading: plansLoading } = usePlans(true)

  const params = useMemo<SubscriptionListParams>(
    () => ({
      page,
      page_size: PAGE_SIZE,
      search: debouncedSearch || undefined,
      plan_code: planFilter === ALL ? undefined : planFilter,
      over_quota: overQuota || undefined,
    }),
    [page, debouncedSearch, planFilter, overQuota],
  )

  const { data, isLoading } = useSubscriptions(params)

  const columns = useMemo<ColumnDef<SubscriptionRow, unknown>[]>(
    () => [
      {
        id: 'teacher',
        header: 'Ustoz',
        cell: ({ row }) => (
          <div className="min-w-0">
            <p className="truncate font-medium">
              {displayName(
                row.original.full_name,
                row.original.username,
                row.original.telegram_id,
              )}
            </p>
            <p className="truncate text-xs text-muted-foreground">
              {row.original.telegram_id}
            </p>
          </div>
        ),
      },
      {
        id: 'plan',
        header: 'Tarif',
        cell: ({ row }) => {
          const sub = row.original.subscription
          if (!sub) return <SubscriptionBadge status={null} />
          return (
            <div className="flex items-center gap-1.5">
              <Badge variant="outline">{sub.plan_name}</Badge>
              <SubscriptionBadge status={sub.status} />
            </div>
          )
        },
      },
      {
        id: 'quota',
        header: 'Kvota (joriy davr)',
        cell: ({ row }) => {
          const sub = row.original.subscription
          if (!sub) return <span className="text-sm text-muted-foreground">—</span>
          const isOver = sub.scan_limit !== null && sub.scans_used >= sub.scan_limit
          return (
            <div className="w-40 space-y-1">
              <Progress
                value={sub.usage_percent}
                indicatorClassName={
                  isOver
                    ? 'bg-[var(--status-critical)]'
                    : sub.usage_percent >= 80
                      ? 'bg-[var(--status-warning)]'
                      : undefined
                }
              />
              <p className="text-xs text-muted-foreground">
                {formatNumber(sub.scans_used)} / {formatLimit(sub.scan_limit)}
                {sub.bonus_credits > 0 && ` (+${sub.bonus_credits} bonus)`}
              </p>
            </div>
          )
        },
      },
      {
        id: 'period',
        header: 'Davr tugashi',
        cell: ({ row }) => {
          const sub = row.original.subscription
          return (
            <span className="whitespace-nowrap text-xs text-muted-foreground">
              {sub ? formatDate(sub.period_end) : '—'}
            </span>
          )
        },
      },
      {
        id: 'ends',
        header: 'Obuna muddati',
        cell: ({ row }) => {
          const sub = row.original.subscription
          if (!sub) return <span className="text-xs text-muted-foreground">—</span>
          return (
            <span className="whitespace-nowrap text-xs text-muted-foreground">
              {sub.ends_at ? formatDate(sub.ends_at) : 'Muddatsiz'}
            </span>
          )
        },
      },
    ],
    [],
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tariflar va obunalar"
        description="Tarif limitlarini boshqarish va ustozlarning kvota sarfini kuzatish"
        actions={
          canEdit ? (
            <Button onClick={() => setIsCreating(true)}>
              <Plus className="h-4 w-4" />
              Yangi tarif
            </Button>
          ) : undefined
        }
      />

      {/* Tarif kartochkalari */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {plansLoading
          ? Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-56 w-full" />
            ))
          : plans?.map((plan) => (
              <PlanCard
                key={plan.id}
                plan={plan}
                canEdit={canEdit}
                onEdit={() => setEditingPlan(plan)}
              />
            ))}
      </div>

      {/* Obunalar jadvali */}
      <div className="space-y-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPage(1)
              }}
              placeholder="Ustozni qidirish…"
              className="pl-9"
            />
          </div>

          <Select
            value={planFilter}
            onValueChange={(value) => {
              setPlanFilter(value)
              setPage(1)
            }}
          >
            <SelectTrigger className="sm:w-44">
              <SelectValue placeholder="Tarif" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Barcha tariflar</SelectItem>
              {plans?.map((plan) => (
                <SelectItem key={plan.id} value={plan.code}>
                  {plan.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <div className="flex items-center gap-2 rounded-md border px-3 py-2">
            <Switch
              id="over-quota"
              checked={overQuota}
              onCheckedChange={(checked) => {
                setOverQuota(checked)
                setPage(1)
              }}
            />
            <label htmlFor="over-quota" className="whitespace-nowrap text-xs">
              Limitdan oshganlar
            </label>
          </div>
        </div>

        <DataTable
          columns={columns}
          data={data?.items ?? []}
          meta={data?.meta}
          isLoading={isLoading}
          onPageChange={setPage}
          emptyMessage="Obuna topilmadi"
        />
      </div>

      <PlanEditorDialog
        plan={editingPlan}
        open={editingPlan !== null || isCreating}
        onOpenChange={(open) => {
          if (!open) {
            setEditingPlan(null)
            setIsCreating(false)
          }
        }}
      />
    </div>
  )
}
