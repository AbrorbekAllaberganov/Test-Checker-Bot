import { CheckCircle2 } from 'lucide-react'
import { useState } from 'react'

import { useReviewQueue } from '@/api/queries'
import { DataTable } from '@/components/DataTable'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { Badge } from '@/components/ui/badge'
import { OmrInspectorModal } from './OmrInspectorModal'
import { useScanColumns } from './ScansListPage'

/**
 * Qo'lda ko'rik navbati.
 *
 * Eng eskisi birinchi (FIFO) — backend shunday saralaydi, chunki kutib
 * qolgan ustozga javob birinchi navbatda kerak.
 */
export function ReviewQueuePage() {
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const { data, isLoading } = useReviewQueue(page)
  const columns = useScanColumns()

  const total = data?.meta.total ?? 0

  return (
    <div className="space-y-5">
      <PageHeader
        title="Ko'rik navbati"
        description="Ikkilangan yoki xato bilan o'qilgan varaqlar — eng eskisi birinchi"
        actions={
          total > 0 ? (
            <Badge variant="warning">{total} ta kutmoqda</Badge>
          ) : undefined
        }
      />

      {!isLoading && total === 0 ? (
        <EmptyState
          icon={CheckCircle2}
          title="Navbat bo'sh"
          description="Barcha varaqlar muvaffaqiyatli o'qilgan yoki allaqachon ko'rikdan o'tgan."
        />
      ) : (
        <DataTable
          columns={columns}
          data={data?.items ?? []}
          meta={data?.meta}
          isLoading={isLoading}
          onPageChange={setPage}
          onRowClick={(row) => setSelectedId(row.id)}
        />
      )}

      <OmrInspectorModal
        attemptId={selectedId}
        onClose={() => setSelectedId(null)}
      />
    </div>
  )
}
