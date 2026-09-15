import type { ColumnDef } from '@tanstack/react-table'
import { Download, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'

import { downloadFile, errorMessage } from '@/api/client'
import { useGroups, useStudents, useTests } from '@/api/queries'
import type { GroupListItem, StudentListItem, TestListItem } from '@/api/types'
import { DataTable } from '@/components/DataTable'
import { PageHeader } from '@/components/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useDebounce } from '@/hooks/useDebounce'
import { formatDate, formatNumber, formatPercent } from '@/lib/format'
import { TestDetailDialog } from './TestDetailDialog'

const PAGE_SIZE = 25

async function exportUrl(url: string, name: string) {
  try {
    await downloadFile(url, name)
    toast.success('Excel fayl yuklab olindi')
  } catch (error) {
    toast.error(errorMessage(error, 'Eksport qilinmadi'))
  }
}

/** Iyerarxiya: Ustoz → Guruh → O'quvchi → Natijalar. */
export function ExplorerPage() {
  const [tab, setTab] = useState('groups')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selectedTestId, setSelectedTestId] = useState<number | null>(null)

  const debouncedSearch = useDebounce(search)
  const commonParams = {
    page,
    page_size: PAGE_SIZE,
    search: debouncedSearch || undefined,
  }

  const groups = useGroups(commonParams)
  const students = useStudents(commonParams)
  const tests = useTests(commonParams)

  const groupColumns = useMemo<ColumnDef<GroupListItem, unknown>[]>(
    () => [
      {
        accessorKey: 'name',
        header: 'Guruh',
        cell: ({ row }) => (
          <div className="min-w-0">
            <p className="truncate font-medium">{row.original.name}</p>
            <p className="truncate text-xs text-muted-foreground">
              {row.original.owner_name ?? "Noma'lum ustoz"}
            </p>
          </div>
        ),
      },
      {
        id: 'counts',
        header: 'Tarkibi',
        cell: ({ row }) => (
          <div className="text-xs text-muted-foreground">
            <p>
              <span className="font-medium text-foreground">
                {formatNumber(row.original.students_count)}
              </span>{' '}
              o'quvchi
            </p>
            <p>
              <span className="font-medium text-foreground">
                {formatNumber(row.original.tests_count)}
              </span>{' '}
              test ·{' '}
              <span className="font-medium text-foreground">
                {formatNumber(row.original.scans_count)}
              </span>{' '}
              skan
            </p>
          </div>
        ),
      },
      {
        accessorKey: 'created_at',
        header: 'Yaratilgan',
        cell: ({ row }) => (
          <span className="whitespace-nowrap text-xs text-muted-foreground">
            {formatDate(row.original.created_at)}
          </span>
        ),
      },
      {
        id: 'actions',
        header: '',
        cell: ({ row }) => (
          <Button
            variant="ghost"
            size="sm"
            onClick={(event) => {
              event.stopPropagation()
              void exportUrl(
                `/api/admin/groups/${row.original.id}/export`,
                `group_${row.original.id}.xlsx`,
              )
            }}
          >
            <Download className="h-4 w-4" />
          </Button>
        ),
      },
    ],
    [],
  )

  const studentColumns = useMemo<ColumnDef<StudentListItem, unknown>[]>(
    () => [
      {
        accessorKey: 'full_name',
        header: "O'quvchi",
        cell: ({ row }) => (
          <div className="min-w-0">
            <p className="truncate font-medium">{row.original.full_name}</p>
            <p className="truncate text-xs text-muted-foreground">
              {row.original.group_name ?? '—'}
            </p>
          </div>
        ),
      },
      {
        id: 'attempts',
        header: 'Urinishlar',
        cell: ({ row }) => (
          <span className="text-sm">{formatNumber(row.original.attempts_count)}</span>
        ),
      },
      {
        id: 'avg',
        header: "O'rtacha ball",
        cell: ({ row }) =>
          row.original.avg_percent === null ? (
            <span className="text-sm text-muted-foreground">—</span>
          ) : (
            <Badge
              variant={
                row.original.avg_percent >= 60
                  ? 'success'
                  : row.original.avg_percent >= 40
                    ? 'warning'
                    : 'destructive'
              }
            >
              {formatPercent(row.original.avg_percent)}
            </Badge>
          ),
      },
      {
        id: 'actions',
        header: '',
        cell: ({ row }) => (
          <Button
            variant="ghost"
            size="sm"
            onClick={(event) => {
              event.stopPropagation()
              void exportUrl(
                `/api/admin/students/${row.original.id}/export`,
                `student_${row.original.id}.xlsx`,
              )
            }}
          >
            <Download className="h-4 w-4" />
          </Button>
        ),
      },
    ],
    [],
  )

  const testColumns = useMemo<ColumnDef<TestListItem, unknown>[]>(
    () => [
      {
        accessorKey: 'title',
        header: 'Test',
        cell: ({ row }) => (
          <div className="min-w-0">
            <p className="truncate font-medium">{row.original.title}</p>
            <p className="truncate text-xs text-muted-foreground">
              {row.original.group_name ?? '—'}
              {row.original.owner_name && ` · ${row.original.owner_name}`}
            </p>
          </div>
        ),
      },
      {
        id: 'format',
        header: 'Format',
        cell: ({ row }) => (
          <Badge variant="outline">
            {row.original.question_count} savol · {row.original.variant_count} variant
          </Badge>
        ),
      },
      {
        id: 'results',
        header: 'Natijalar',
        cell: ({ row }) => (
          <div className="text-xs text-muted-foreground">
            <p>
              <span className="font-medium text-foreground">
                {formatNumber(row.original.attempts_count)}
              </span>{' '}
              urinish
            </p>
            <p>
              O'rtacha:{' '}
              <span className="font-medium text-foreground">
                {formatPercent(row.original.avg_percent)}
              </span>
            </p>
          </div>
        ),
      },
      {
        accessorKey: 'created_at',
        header: 'Sana',
        cell: ({ row }) => (
          <span className="whitespace-nowrap text-xs text-muted-foreground">
            {formatDate(row.original.created_at)}
          </span>
        ),
      },
      {
        id: 'actions',
        header: '',
        cell: ({ row }) => (
          <Button
            variant="ghost"
            size="sm"
            onClick={(event) => {
              event.stopPropagation()
              void exportUrl(
                `/api/admin/tests/${row.original.id}/export`,
                `test_${row.original.id}.xlsx`,
              )
            }}
          >
            <Download className="h-4 w-4" />
          </Button>
        ),
      },
    ],
    [],
  )

  return (
    <div className="space-y-5">
      <PageHeader
        title="Guruh va testlar"
        description="Ustoz → guruh → o'quvchi → natijalar bo'yicha ko'rish va eksport"
      />

      <Tabs
        value={tab}
        onValueChange={(value) => {
          setTab(value)
          setPage(1)
          setSearch('')
        }}
      >
        <TabsList>
          <TabsTrigger value="groups">Guruhlar</TabsTrigger>
          <TabsTrigger value="students">O'quvchilar</TabsTrigger>
          <TabsTrigger value="tests">Testlar</TabsTrigger>
        </TabsList>

        <div className="relative mt-4">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value)
              setPage(1)
            }}
            placeholder="Nomi bo'yicha qidirish…"
            className="pl-9"
          />
        </div>

        <TabsContent value="groups">
          <DataTable
            columns={groupColumns}
            data={groups.data?.items ?? []}
            meta={groups.data?.meta}
            isLoading={groups.isLoading}
            onPageChange={setPage}
            emptyMessage="Guruh topilmadi"
          />
        </TabsContent>

        <TabsContent value="students">
          <DataTable
            columns={studentColumns}
            data={students.data?.items ?? []}
            meta={students.data?.meta}
            isLoading={students.isLoading}
            onPageChange={setPage}
            emptyMessage="O'quvchi topilmadi"
          />
        </TabsContent>

        <TabsContent value="tests">
          <DataTable
            columns={testColumns}
            data={tests.data?.items ?? []}
            meta={tests.data?.meta}
            isLoading={tests.isLoading}
            onPageChange={setPage}
            onRowClick={(row) => setSelectedTestId(row.id)}
            emptyMessage="Test topilmadi"
          />
        </TabsContent>
      </Tabs>

      <TestDetailDialog
        testId={selectedTestId}
        onClose={() => setSelectedTestId(null)}
      />
    </div>
  )
}
