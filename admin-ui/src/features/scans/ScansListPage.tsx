import type { ColumnDef } from '@tanstack/react-table'
import { useMemo, useState } from 'react'

import { useScans, type ScanListParams } from '@/api/queries'
import type { ScanListItem } from '@/api/types'
import { DataTable } from '@/components/DataTable'
import { PageHeader } from '@/components/PageHeader'
import { ScanStatusBadge } from '@/components/StatusBadge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { formatDateTime, formatPercent } from '@/lib/format'
import { ConfidenceMeter } from './ConfidenceMeter'
import { OmrInspectorModal } from './OmrInspectorModal'

const PAGE_SIZE = 25
const ALL = '__all__'

/** Skanlar jadvalining ustunlari — inspektor sahifasida ham qayta ishlatiladi. */
export function useScanColumns(): ColumnDef<ScanListItem, unknown>[] {
  return useMemo(
    () => [
      {
        id: 'student',
        header: "O'quvchi / Test",
        cell: ({ row }) => {
          const scan = row.original
          return (
            <div className="min-w-0">
              <p className="truncate font-medium">
                {scan.student_name ?? "Aniqlanmagan (QR o'qilmadi)"}
              </p>
              <p className="truncate text-xs text-muted-foreground">
                {scan.test_title ?? '—'}
                {scan.group_name && ` · ${scan.group_name}`}
              </p>
            </div>
          )
        },
      },
      {
        id: 'owner',
        header: 'Ustoz',
        cell: ({ row }) => (
          <span className="text-sm text-muted-foreground">
            {row.original.owner_name ?? '—'}
          </span>
        ),
      },
      {
        id: 'result',
        header: 'Natija',
        cell: ({ row }) => {
          const scan = row.original
          if (scan.score === null) {
            return <span className="text-sm text-muted-foreground">—</span>
          }
          return (
            <div>
              <p className="font-medium">
                {scan.score}/{scan.total}
              </p>
              <p className="text-xs text-muted-foreground">
                {formatPercent(scan.percent)}
              </p>
            </div>
          )
        },
      },
      {
        id: 'confidence',
        header: 'Ishonchlilik',
        cell: ({ row }) => <ConfidenceMeter value={row.original.confidence} />,
      },
      {
        id: 'status',
        header: 'Holat',
        cell: ({ row }) => (
          <div className="space-y-1">
            <ScanStatusBadge
              status={row.original.status}
              needsReview={row.original.needs_review}
              manualOverride={row.original.manual_override}
            />
            {row.original.error_msg && (
              <p
                className="max-w-[180px] truncate text-xs text-destructive"
                title={row.original.error_msg}
              >
                {row.original.error_msg}
              </p>
            )}
          </div>
        ),
      },
      {
        accessorKey: 'created_at',
        header: 'Sana',
        cell: ({ row }) => (
          <span className="whitespace-nowrap text-xs text-muted-foreground">
            {formatDateTime(row.original.created_at)}
          </span>
        ),
      },
    ],
    [],
  )
}

export function ScansListPage() {
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState(ALL)
  const [review, setReview] = useState(ALL)
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const params = useMemo<ScanListParams>(
    () => ({
      page,
      page_size: PAGE_SIZE,
      status: status === ALL ? undefined : status,
      needs_review: review === ALL ? undefined : review === 'yes',
    }),
    [page, status, review],
  )

  const { data, isLoading } = useScans(params)
  const columns = useScanColumns()

  return (
    <div className="space-y-5">
      <PageHeader
        title="OMR skanlar"
        description="Barcha tekshirilgan varaqlar — qatorni bosib inspektorni oching"
      />

      <div className="flex flex-col gap-2 sm:flex-row">
        <Select
          value={status}
          onValueChange={(value) => {
            setStatus(value)
            setPage(1)
          }}
        >
          <SelectTrigger className="sm:w-48">
            <SelectValue placeholder="Holat" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Barcha holatlar</SelectItem>
            <SelectItem value="done">Tayyor</SelectItem>
            <SelectItem value="pending">Navbatda</SelectItem>
            <SelectItem value="error">Xato</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={review}
          onValueChange={(value) => {
            setReview(value)
            setPage(1)
          }}
        >
          <SelectTrigger className="sm:w-56">
            <SelectValue placeholder="Ko'rik" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Ko'rikdan qat'i nazar</SelectItem>
            <SelectItem value="yes">Faqat ko'rik kerak</SelectItem>
            <SelectItem value="no">Ko'rik kerak emas</SelectItem>
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
        emptyMessage="Skan topilmadi"
      />

      <OmrInspectorModal
        attemptId={selectedId}
        onClose={() => setSelectedId(null)}
      />
    </div>
  )
}
