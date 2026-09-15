import type { ColumnDef } from '@tanstack/react-table'
import { Cpu, Database, RefreshCw, Server } from 'lucide-react'
import { useMemo, useState } from 'react'

import { api } from '@/api/client'
import { useSystemStatus } from '@/api/queries'
import type { ComponentStatus, Page, ScanListItem } from '@/api/types'
import { DataTable } from '@/components/DataTable'
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
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { formatDateTime, formatNumber } from '@/lib/format'
import { useQuery } from '@tanstack/react-query'

const ICONS: Record<string, typeof Server> = {
  postgres: Database,
  redis: Server,
  celery: Cpu,
}

interface CeleryWorker {
  name: string
  status: string
  active_tasks: number
  reserved_tasks: number
  concurrency: number | null
  total_completed: number
  uptime_seconds: number | null
}

function bytesToMb(value: unknown): string {
  const num = Number(value ?? 0)
  return num ? `${(num / 1024 / 1024).toFixed(1)} MB` : '—'
}

function ComponentCard({ component }: { component: ComponentStatus }) {
  const Icon = ICONS[component.name] ?? Server

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="capitalize">{component.name}</CardTitle>
          </div>
          <HealthBadge status={component.status} />
        </div>
        <CardDescription className="truncate">{component.detail}</CardDescription>
      </CardHeader>

      <CardContent className="space-y-1 text-xs text-muted-foreground">
        {component.name === 'redis' && (
          <>
            <div className="flex justify-between">
              <span>Navbat uzunligi</span>
              <span className="font-medium text-foreground">
                {formatNumber(Number(component.metrics.queue_length ?? 0))}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Xotira</span>
              <span className="font-medium text-foreground">
                {String(component.metrics.used_memory_human ?? '—')}
              </span>
            </div>
          </>
        )}

        {component.name === 'postgres' && (
          <div className="flex justify-between">
            <span>Baza hajmi</span>
            <span className="font-medium text-foreground">
              {bytesToMb(component.metrics.size_bytes)}
            </span>
          </div>
        )}

        {component.name === 'celery' && (
          <>
            <div className="flex justify-between">
              <span>Bajarilmoqda</span>
              <span className="font-medium text-foreground">
                {formatNumber(Number(component.metrics.active_total ?? 0))}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Kutmoqda</span>
              <span className="font-medium text-foreground">
                {formatNumber(Number(component.metrics.reserved_total ?? 0))}
              </span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

function useProblemScans(kind: 'failed-tasks' | 'stuck-tasks', page: number) {
  return useQuery({
    queryKey: ['system', kind, page],
    queryFn: async () => {
      const { data } = await api.get<Page<ScanListItem>>(
        `/api/admin/system/${kind}`,
        { params: { page, page_size: 20 } },
      )
      return data
    },
  })
}

export function SystemStatusPage() {
  const { data, isLoading, isFetching, refetch } = useSystemStatus()
  const [failedPage, setFailedPage] = useState(1)
  const [stuckPage, setStuckPage] = useState(1)

  const failed = useProblemScans('failed-tasks', failedPage)
  const stuck = useProblemScans('stuck-tasks', stuckPage)

  const workers = useMemo<CeleryWorker[]>(() => {
    const celery = data?.components.find((c) => c.name === 'celery')
    return (celery?.metrics.workers as CeleryWorker[] | undefined) ?? []
  }, [data])

  const problemColumns = useMemo<ColumnDef<ScanListItem, unknown>[]>(
    () => [
      { accessorKey: 'id', header: 'Skan ID' },
      {
        accessorKey: 'created_at',
        header: 'Vaqt',
        cell: ({ row }) => (
          <span className="whitespace-nowrap text-xs text-muted-foreground">
            {formatDateTime(row.original.created_at)}
          </span>
        ),
      },
      {
        accessorKey: 'error_msg',
        header: 'Xato',
        cell: ({ row }) => (
          <span className="text-xs text-destructive">
            {row.original.error_msg ?? '—'}
          </span>
        ),
      },
    ],
    [],
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tizim holati"
        description="Navbat, worker'lar va baza sog'lig'i (har 30 sekundda yangilanadi)"
        actions={
          <Button
            variant="outline"
            size="icon"
            onClick={() => void refetch()}
            disabled={isFetching}
            aria-label="Yangilash"
          >
            <RefreshCw className={isFetching ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        {isLoading
          ? Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-40 w-full" />
            ))
          : data?.components.map((component) => (
              <ComponentCard key={component.name} component={component} />
            ))}
      </div>

      {/* Celery worker'lari */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Celery worker'lari</CardTitle>
          <CardDescription>
            {workers.length > 0
              ? `${workers.length} ta worker javob berdi`
              : "Worker'lar javob bermadi"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {workers.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              Worker topilmadi — konteyner ishlab turganini tekshiring
              (<code>docker compose ps worker</code>).
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-xs uppercase text-muted-foreground">
                    <th className="py-2 text-left font-medium">Worker</th>
                    <th className="py-2 text-right font-medium">Bajarilmoqda</th>
                    <th className="py-2 text-right font-medium">Kutmoqda</th>
                    <th className="py-2 text-right font-medium">Parallellik</th>
                    <th className="py-2 text-right font-medium">Jami bajarilgan</th>
                  </tr>
                </thead>
                <tbody>
                  {workers.map((worker) => (
                    <tr key={worker.name} className="border-b last:border-0">
                      <td className="py-2 font-mono text-xs">{worker.name}</td>
                      <td className="py-2 text-right tabular-nums">
                        {worker.active_tasks}
                      </td>
                      <td className="py-2 text-right tabular-nums">
                        {worker.reserved_tasks}
                      </td>
                      <td className="py-2 text-right tabular-nums">
                        {worker.concurrency ?? '—'}
                      </td>
                      <td className="py-2 text-right tabular-nums">
                        {formatNumber(worker.total_completed)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Muammoli vazifalar */}
      <Tabs defaultValue="failed">
        <TabsList>
          <TabsTrigger value="failed">
            Xato bergan ({failed.data?.meta.total ?? 0})
          </TabsTrigger>
          <TabsTrigger value="stuck">
            Qotib qolgan ({stuck.data?.meta.total ?? 0})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="failed">
          <DataTable
            columns={problemColumns}
            data={failed.data?.items ?? []}
            meta={failed.data?.meta}
            isLoading={failed.isLoading}
            onPageChange={setFailedPage}
            emptyMessage="Oxirgi 7 kunda xato bo'lmagan"
          />
        </TabsContent>

        <TabsContent value="stuck">
          <DataTable
            columns={problemColumns}
            data={stuck.data?.items ?? []}
            meta={stuck.data?.meta}
            isLoading={stuck.isLoading}
            onPageChange={setStuckPage}
            emptyMessage="Navbatda qotib qolgan skan yo'q"
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
