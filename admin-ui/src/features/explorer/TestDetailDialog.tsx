import { Download } from 'lucide-react'
import { toast } from 'sonner'

import { downloadFile, errorMessage } from '@/api/client'
import { useTest } from '@/api/queries'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { formatDateTime, formatNumber, formatPercent } from '@/lib/format'

interface Props {
  testId: number | null
  onClose: () => void
}

/**
 * Test tafsiloti: javob kaliti, natijalar jadvali va savol tahlili.
 *
 * Savol tahlili (item analysis) — qaysi savol ko'p xato qilinganini
 * ko'rsatadi: past foiz yo savol qiyin, yo kalit noto'g'ri kiritilgan.
 */
export function TestDetailDialog({ testId, onClose }: Props) {
  const { data: test, isLoading } = useTest(testId)

  async function handleExport() {
    if (!test) return
    try {
      await downloadFile(
        `/api/admin/tests/${test.id}/export`,
        `test_${test.id}.xlsx`,
      )
      toast.success('Excel fayl yuklab olindi')
    } catch (error) {
      toast.error(errorMessage(error, 'Eksport qilinmadi'))
    }
  }

  return (
    <Dialog open={testId !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent size="lg">
        {isLoading || !test ? (
          <div className="space-y-4">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-96 w-full" />
          </div>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>{test.title}</DialogTitle>
              <DialogDescription>
                {test.group_name}
                {test.owner_name && ` · ${test.owner_name}`}
                {' · '}
                {test.question_count} savol, {test.variant_count} variant ·{' '}
                {formatNumber(test.attempts_count)} urinish
              </DialogDescription>
            </DialogHeader>

            <Tabs defaultValue="results">
              <div className="flex items-center justify-between gap-2">
                <TabsList>
                  <TabsTrigger value="results">Natijalar</TabsTrigger>
                  <TabsTrigger value="analysis">Savol tahlili</TabsTrigger>
                  <TabsTrigger value="key">Javob kaliti</TabsTrigger>
                </TabsList>
                <Button variant="outline" size="sm" onClick={handleExport}>
                  <Download className="h-4 w-4" />
                  Excel
                </Button>
              </div>

              <TabsContent value="results">
                <div className="max-h-[55vh] overflow-y-auto">
                  {test.results.length === 0 ? (
                    <p className="py-10 text-center text-sm text-muted-foreground">
                      Hali natija yo'q
                    </p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-background">
                        <tr className="border-b text-xs uppercase text-muted-foreground">
                          <th className="py-2 text-left font-medium">O'quvchi</th>
                          <th className="py-2 text-right font-medium">Ball</th>
                          <th className="py-2 text-right font-medium">Foiz</th>
                          <th className="py-2 text-right font-medium">Sana</th>
                        </tr>
                      </thead>
                      <tbody>
                        {test.results.map((result) => (
                          <tr
                            key={`${result.student_id}-${result.attempt_id}`}
                            className="border-b last:border-0"
                          >
                            <td className="py-2">
                              <span className="flex items-center gap-1.5">
                                {result.student_name}
                                {result.needs_review && (
                                  <Badge variant="warning">ko'rik</Badge>
                                )}
                              </span>
                            </td>
                            <td className="py-2 text-right tabular-nums">
                              {result.score ?? '—'}/{result.total ?? '—'}
                            </td>
                            <td className="py-2 text-right tabular-nums">
                              {formatPercent(result.percent)}
                            </td>
                            <td className="py-2 text-right text-xs text-muted-foreground">
                              {formatDateTime(result.created_at)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </TabsContent>

              <TabsContent value="analysis">
                <div className="max-h-[55vh] space-y-1.5 overflow-y-auto pr-1">
                  {test.item_analysis.map((item) => (
                    <div key={item.question} className="flex items-center gap-3">
                      <span className="w-8 shrink-0 text-xs tabular-nums text-muted-foreground">
                        {item.question}
                      </span>
                      <Progress
                        value={item.correct_percent}
                        className="flex-1"
                        indicatorClassName={
                          item.correct_percent >= 60
                            ? 'bg-[var(--status-good)]'
                            : item.correct_percent >= 30
                              ? 'bg-[var(--status-warning)]'
                              : 'bg-[var(--status-critical)]'
                        }
                      />
                      <span className="w-14 shrink-0 text-right text-xs tabular-nums">
                        {formatPercent(item.correct_percent, 0)}
                      </span>
                      <span className="w-28 shrink-0 text-right text-xs text-muted-foreground">
                        {item.correct_count}✓ {item.incorrect_count}✗{' '}
                        {item.unmarked_count}·
                      </span>
                    </div>
                  ))}
                </div>
                <p className="mt-3 text-xs text-muted-foreground">
                  Past foizli savollar — yoki qiyin, yoki kalit xato kiritilgan.
                </p>
              </TabsContent>

              <TabsContent value="key">
                <div className="max-h-[55vh] overflow-y-auto">
                  <div className="grid grid-cols-6 gap-2 sm:grid-cols-10">
                    {Object.entries(test.answer_key)
                      .sort(([a], [b]) => Number(a) - Number(b))
                      .map(([question, answer]) => (
                        <div
                          key={question}
                          className="rounded-md border px-2 py-1.5 text-center"
                        >
                          <p className="text-[10px] text-muted-foreground">
                            {question}
                          </p>
                          <p className="text-sm font-semibold">{answer}</p>
                        </div>
                      ))}
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
