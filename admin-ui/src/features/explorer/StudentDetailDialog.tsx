import { ChevronRight, Download } from 'lucide-react'
import { toast } from 'sonner'

import { downloadFile, errorMessage } from '@/api/client'
import { useStudent } from '@/api/queries'
import type { StudentAttemptItem } from '@/api/types'
import { ScanStatusBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDate, formatDateTime, formatNumber, formatPercent } from '@/lib/format'
import { DrillBackButton } from './DrillBackButton'

interface Props {
  studentId: number | null
  onClose: () => void
  onBack?: () => void
  onOpenTest: (testId: number) => void
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  )
}

/** Varaq chiqarilgan, lekin skan hali tushmagan bo'lsa `attempt_id` NULL. */
function ResultCell({ item }: { item: StudentAttemptItem }) {
  if (item.attempt_id === null) {
    return <Badge variant="outline">Skanlanmagan</Badge>
  }
  if (item.status !== 'done') {
    return (
      <ScanStatusBadge
        status={item.status ?? 'pending'}
        needsReview={item.needs_review}
        manualOverride={item.manual_override}
      />
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="tabular-nums">
        {item.score ?? '—'}/{item.total ?? '—'}
      </span>
      {item.needs_review && <Badge variant="warning">ko'rik</Badge>}
      {item.manual_override && <Badge variant="secondary">qo'lda</Badge>}
    </span>
  )
}

/**
 * O'quvchi tafsiloti: u ishlagan testlar ro'yxati.
 *
 * Qator `tituls` dan keladi — ya'ni varaq berilgan-u hali skanlanmagan
 * testlar ham ko'rinadi. Testga bosilsa drill-down test tafsilotiga o'tadi.
 */
export function StudentDetailDialog({ studentId, onClose, onBack, onOpenTest }: Props) {
  const { data: student, isLoading } = useStudent(studentId)

  async function handleExport() {
    if (!student) return
    try {
      await downloadFile(
        `/api/admin/students/${student.id}/export`,
        `student_${student.id}.xlsx`,
      )
      toast.success('Excel fayl yuklab olindi')
    } catch (error) {
      toast.error(errorMessage(error, 'Eksport qilinmadi'))
    }
  }

  return (
    <Dialog open={studentId !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent size="lg">
        {isLoading || !student ? (
          <div className="space-y-4">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-80 w-full" />
          </div>
        ) : (
          <>
            <DialogHeader>
              <DrillBackButton onBack={onBack} />
              <DialogTitle>{student.full_name}</DialogTitle>
              <DialogDescription>
                {student.group_name ?? '—'}
                {student.owner_name && ` · ${student.owner_name}`}
                {student.telegram_id && ` · TG: ${student.telegram_id}`}
                {' · '}
                {formatDate(student.created_at)} dan beri
              </DialogDescription>
            </DialogHeader>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile label="Varaq" value={formatNumber(student.tituls_count)} />
              <StatTile label="Skan" value={formatNumber(student.attempts_count)} />
              <StatTile
                label="O'rtacha"
                value={formatPercent(student.avg_percent)}
              />
              <StatTile
                label="Eng yaxshi"
                value={formatPercent(student.best_percent)}
              />
            </div>

            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium">Ishlagan testlari</p>
              <Button variant="outline" size="sm" onClick={handleExport}>
                <Download className="h-4 w-4" />
                Excel
              </Button>
            </div>

            <div className="max-h-[45vh] overflow-y-auto">
              {student.attempts.length === 0 ? (
                <p className="py-10 text-center text-sm text-muted-foreground">
                  Bu o'quvchiga hali varaq chiqarilmagan
                </p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-background">
                    <tr className="border-b text-xs uppercase text-muted-foreground">
                      <th className="py-2 text-left font-medium">Test</th>
                      <th className="py-2 text-left font-medium">Natija</th>
                      <th className="py-2 text-right font-medium">Foiz</th>
                      <th className="py-2 text-right font-medium">Sana</th>
                      <th className="w-8" />
                    </tr>
                  </thead>
                  <tbody>
                    {student.attempts.map((item) => (
                      <tr
                        key={`${item.titul_id}-${item.attempt_id ?? 'none'}`}
                        onClick={() => onOpenTest(item.test_id)}
                        className="cursor-pointer border-b last:border-0 hover:bg-muted/50"
                      >
                        <td className="py-2">
                          <p className="font-medium">{item.test_title}</p>
                          <p className="text-xs text-muted-foreground">
                            {item.question_count} savol · {item.variant_count} variant
                          </p>
                        </td>
                        <td className="py-2">
                          <ResultCell item={item} />
                        </td>
                        <td className="py-2 text-right tabular-nums">
                          {formatPercent(item.percent)}
                        </td>
                        <td className="py-2 text-right text-xs text-muted-foreground">
                          {formatDateTime(item.created_at ?? item.titul_created_at)}
                        </td>
                        <td className="py-2 text-right">
                          <ChevronRight className="h-4 w-4 text-muted-foreground" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
