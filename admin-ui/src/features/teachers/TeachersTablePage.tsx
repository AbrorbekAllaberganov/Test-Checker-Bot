import type { ColumnDef } from '@tanstack/react-table'
import { Download, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'

import { downloadFile, errorMessage } from '@/api/client'
import { useTeachers, type TeacherListParams } from '@/api/queries'
import type { TeacherListItem } from '@/api/types'
import { DataTable } from '@/components/DataTable'
import { PageHeader } from '@/components/PageHeader'
import { BlockedBadge, SubscriptionBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useDebounce } from '@/hooks/useDebounce'
import { displayName, formatDate, formatNumber } from '@/lib/format'
import { TeacherDetailDrawer } from './TeacherDetailDrawer'

const PAGE_SIZE = 25

/** "Barchasi" uchun maxsus qiymat — Radix Select bo'sh string qabul qilmaydi. */
const ALL = '__all__'

export function TeachersTablePage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [blockedFilter, setBlockedFilter] = useState(ALL)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [isExporting, setIsExporting] = useState(false)

  const debouncedSearch = useDebounce(search)

  const params = useMemo<TeacherListParams>(
    () => ({
      page,
      page_size: PAGE_SIZE,
      search: debouncedSearch || undefined,
      blocked: blockedFilter === ALL ? undefined : blockedFilter === 'blocked',
    }),
    [page, debouncedSearch, blockedFilter],
  )

  const { data, isLoading } = useTeachers(params)

  async function handleExport() {
    setIsExporting(true)
    try {
      await downloadFile('/api/admin/users/export', 'teachers.xlsx')
      toast.success('Excel fayl yuklab olindi')
    } catch (error) {
      toast.error(errorMessage(error, 'Eksport qilinmadi'))
    } finally {
      setIsExporting(false)
    }
  }

  const columns = useMemo<ColumnDef<TeacherListItem, unknown>[]>(
    () => [
      {
        id: 'teacher',
        header: 'Ustoz',
        cell: ({ row }) => {
          const t = row.original
          return (
            <div className="min-w-0">
              <p className="truncate font-medium">
                {displayName(t.full_name, t.username, t.telegram_id)}
              </p>
              <p className="truncate text-xs text-muted-foreground">
                {t.username ? `@${t.username} · ` : ''}
                {t.telegram_id}
              </p>
            </div>
          )
        },
      },
      {
        id: 'plan',
        header: 'Tarif',
        cell: ({ row }) => {
          const t = row.original
          if (!t.plan_code) return <SubscriptionBadge status={null} />
          return (
            <div className="space-y-1">
              <div className="flex items-center gap-1.5">
                <Badge variant="outline">{t.plan_name}</Badge>
                <SubscriptionBadge status={t.subscription_status} />
              </div>
              <div className="w-28">
                <Progress
                  value={
                    t.scan_limit ? (100 * t.scans_used) / t.scan_limit : 0
                  }
                  indicatorClassName={
                    t.scan_limit && t.scans_used >= t.scan_limit
                      ? 'bg-destructive'
                      : undefined
                  }
                />
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  {formatNumber(t.scans_used)} /{' '}
                  {t.scan_limit === null ? '∞' : formatNumber(t.scan_limit)}
                </p>
              </div>
            </div>
          )
        },
      },
      {
        id: 'usage',
        header: 'Faollik',
        cell: ({ row }) => {
          const t = row.original
          return (
            <div className="text-xs text-muted-foreground">
              <p>
                <span className="font-medium text-foreground">
                  {formatNumber(t.groups_count)}
                </span>{' '}
                guruh ·{' '}
                <span className="font-medium text-foreground">
                  {formatNumber(t.students_count)}
                </span>{' '}
                o'quvchi
              </p>
              <p>
                <span className="font-medium text-foreground">
                  {formatNumber(t.tests_count)}
                </span>{' '}
                test ·{' '}
                <span className="font-medium text-foreground">
                  {formatNumber(t.scans_count)}
                </span>{' '}
                skan
              </p>
            </div>
          )
        },
      },
      {
        id: 'status',
        header: 'Holat',
        cell: ({ row }) => (
          <div className="space-y-1">
            <BlockedBadge blocked={row.original.is_blocked} />
            {row.original.admin_role && (
              <Badge variant="secondary">{row.original.admin_role}</Badge>
            )}
          </div>
        ),
      },
      {
        accessorKey: 'created_at',
        header: "Ro'yxatdan o'tgan",
        cell: ({ row }) => (
          <span className="whitespace-nowrap text-xs text-muted-foreground">
            {formatDate(row.original.created_at)}
          </span>
        ),
      },
    ],
    [],
  )

  return (
    <div className="space-y-5">
      <PageHeader
        title="Ustozlar"
        description="Botdan foydalanuvchi o'qituvchilar, ularning tariflari va faolligi"
        actions={
          <Button variant="outline" onClick={handleExport} loading={isExporting}>
            <Download className="h-4 w-4" />
            Excel
          </Button>
        }
      />

      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value)
              setPage(1)
            }}
            placeholder="Ism, username yoki Telegram ID bo'yicha qidirish…"
            className="pl-9"
          />
        </div>

        <Select
          value={blockedFilter}
          onValueChange={(value) => {
            setBlockedFilter(value)
            setPage(1)
          }}
        >
          <SelectTrigger className="sm:w-48">
            <SelectValue placeholder="Holat" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Barcha holatlar</SelectItem>
            <SelectItem value="active">Faol</SelectItem>
            <SelectItem value="blocked">Bloklangan</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        meta={data?.meta}
        isLoading={isLoading}
        onPageChange={setPage}
        onRowClick={(row) => setSelectedId(row.id)}
        emptyMessage={
          debouncedSearch
            ? `"${debouncedSearch}" bo'yicha ustoz topilmadi`
            : 'Hali birorta ustoz ro’yxatdan o’tmagan'
        }
      />

      <TeacherDetailDrawer
        teacherId={selectedId}
        onClose={() => setSelectedId(null)}
      />
    </div>
  )
}
