import type { ColumnDef } from '@tanstack/react-table'
import { useMemo, useState } from 'react'

import { useAuditActions, useAuditLogs, type AuditListParams } from '@/api/queries'
import type { AuditLogItem } from '@/api/types'
import { DataTable } from '@/components/DataTable'
import { PageHeader } from '@/components/PageHeader'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { formatDateTime } from '@/lib/format'

const PAGE_SIZE = 30
const ALL = '__all__'

/** Amal kodidan (`user.block`) o'qilarli nom. */
const ACTION_LABELS: Record<string, string> = {
  'user.block': 'Foydalanuvchi bloklandi',
  'user.unblock': 'Blokdan chiqarildi',
  'user.role_change': "Rol o'zgartirildi",
  'subscription.assign': 'Tarif biriktirildi',
  'subscription.renew': 'Obuna uzaytirildi',
  'subscription.cancel': 'Obuna bekor qilindi',
  'subscription.grant_credits': 'Bonus kredit berildi',
  'plan.create': 'Tarif yaratildi',
  'plan.update': 'Tarif tahrirlandi',
  'attempt.override': "Natija qo'lda tuzatildi",
  'broadcast.send': "E'lon yuborildi",
  'broadcast.cancel': "E'lon bekor qilindi",
  'admin.login': 'Admin panelga kirdi',
}

function actionVariant(action: string) {
  if (action.startsWith('user.block')) return 'destructive' as const
  if (action.startsWith('broadcast')) return 'warning' as const
  if (action === 'admin.login') return 'secondary' as const
  return 'default' as const
}

export function AuditLogPage() {
  const [page, setPage] = useState(1)
  const [action, setAction] = useState(ALL)

  const { data: actions } = useAuditActions()

  const params = useMemo<AuditListParams>(
    () => ({
      page,
      page_size: PAGE_SIZE,
      action: action === ALL ? undefined : action,
    }),
    [page, action],
  )

  const { data, isLoading } = useAuditLogs(params)

  const columns = useMemo<ColumnDef<AuditLogItem, unknown>[]>(
    () => [
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
        accessorKey: 'actor_label',
        header: 'Kim',
        cell: ({ row }) => (
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{row.original.actor_label}</p>
            {row.original.ip_address && (
              <p className="truncate text-xs text-muted-foreground">
                {row.original.ip_address}
              </p>
            )}
          </div>
        ),
      },
      {
        accessorKey: 'action',
        header: 'Amal',
        cell: ({ row }) => (
          <Badge variant={actionVariant(row.original.action)}>
            {ACTION_LABELS[row.original.action] ?? row.original.action}
          </Badge>
        ),
      },
      {
        id: 'object',
        header: 'Obyekt',
        cell: ({ row }) =>
          row.original.object_type ? (
            <span className="text-xs text-muted-foreground">
              {row.original.object_type} #{row.original.object_id}
            </span>
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          ),
      },
      {
        id: 'payload',
        header: 'Tafsilot',
        cell: ({ row }) => {
          if (!row.original.payload) {
            return <span className="text-xs text-muted-foreground">—</span>
          }
          const text = JSON.stringify(row.original.payload)
          return (
            <details className="max-w-md">
              <summary className="cursor-pointer truncate text-xs text-muted-foreground">
                {text.slice(0, 60)}
                {text.length > 60 && '…'}
              </summary>
              <pre className="mt-1 max-h-48 overflow-auto rounded-md bg-muted p-2 text-[11px] leading-relaxed">
                {JSON.stringify(row.original.payload, null, 2)}
              </pre>
            </details>
          )
        },
      },
    ],
    [],
  )

  return (
    <div className="space-y-5">
      <PageHeader
        title="Audit jurnali"
        description="Adminlar bajargan barcha o'zgartiruvchi amallar — faqat o'qish uchun"
        actions={
          <Select
            value={action}
            onValueChange={(value) => {
              setAction(value)
              setPage(1)
            }}
          >
            <SelectTrigger className="w-60">
              <SelectValue placeholder="Amal turi" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Barcha amallar</SelectItem>
              {actions?.map((item) => (
                <SelectItem key={item} value={item}>
                  {ACTION_LABELS[item] ?? item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      />

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        meta={data?.meta}
        isLoading={isLoading}
        onPageChange={setPage}
        emptyMessage="Jurnal bo'sh"
      />
    </div>
  )
}
