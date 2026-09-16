import { ChevronRight, Download } from 'lucide-react'
import { toast } from 'sonner'

import { downloadFile, errorMessage } from '@/api/client'
import { useGroup } from '@/api/queries'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { formatDate, formatNumber, formatPercent } from '@/lib/format'
import { DrillBackButton } from './DrillBackButton'

interface Props {
  groupId: number | null
  onClose: () => void
  onBack?: () => void
  onOpenStudent: (studentId: number) => void
  onOpenTest: (testId: number) => void
}

function PercentBadge({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted-foreground">—</span>
  return (
    <Badge variant={value >= 60 ? 'success' : value >= 40 ? 'warning' : 'destructive'}>
      {formatPercent(value)}
    </Badge>
  )
}

/**
 * Guruh tafsiloti: o'quvchilar va testlar ro'yxati.
 *
 * Qatorga bosilganda drill-down davom etadi: o'quvchi → uning testlari,
 * test → natijalar va savol tahlili.
 */
export function GroupDetailDialog({
  groupId,
  onClose,
  onBack,
  onOpenStudent,
  onOpenTest,
}: Props) {
  const { data: group, isLoading } = useGroup(groupId)

  async function handleExport() {
    if (!group) return
    try {
      await downloadFile(
        `/api/admin/groups/${group.id}/export`,
        `group_${group.id}.xlsx`,
      )
      toast.success('Excel fayl yuklab olindi')
    } catch (error) {
      toast.error(errorMessage(error, 'Eksport qilinmadi'))
    }
  }

  return (
    <Dialog open={groupId !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent size="lg">
        {isLoading || !group ? (
          <div className="space-y-4">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-96 w-full" />
          </div>
        ) : (
          <>
            <DialogHeader>
              <DrillBackButton onBack={onBack} />
              <DialogTitle>{group.name}</DialogTitle>
              <DialogDescription>
                {group.owner_name ?? "Noma'lum ustoz"} ·{' '}
                {formatNumber(group.students.length)} o'quvchi ·{' '}
                {formatNumber(group.tests.length)} test · {formatDate(group.created_at)}
              </DialogDescription>
            </DialogHeader>

            <Tabs defaultValue="students">
              <div className="flex items-center justify-between gap-2">
                <TabsList>
                  <TabsTrigger value="students">O'quvchilar</TabsTrigger>
                  <TabsTrigger value="tests">Testlar</TabsTrigger>
                </TabsList>
                <Button variant="outline" size="sm" onClick={handleExport}>
                  <Download className="h-4 w-4" />
                  Excel
                </Button>
              </div>

              <TabsContent value="students">
                <div className="max-h-[55vh] overflow-y-auto">
                  {group.students.length === 0 ? (
                    <p className="py-10 text-center text-sm text-muted-foreground">
                      Guruhda o'quvchi yo'q
                    </p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-background">
                        <tr className="border-b text-xs uppercase text-muted-foreground">
                          <th className="py-2 text-left font-medium">O'quvchi</th>
                          <th className="py-2 text-right font-medium">Urinish</th>
                          <th className="py-2 text-right font-medium">O'rtacha</th>
                          <th className="w-8" />
                        </tr>
                      </thead>
                      <tbody>
                        {group.students.map((student) => (
                          <tr
                            key={student.id}
                            onClick={() => onOpenStudent(student.id)}
                            className="cursor-pointer border-b last:border-0 hover:bg-muted/50"
                          >
                            <td className="py-2">
                              <p className="font-medium">{student.full_name}</p>
                              {student.telegram_id && (
                                <p className="text-xs text-muted-foreground">
                                  TG: {student.telegram_id}
                                </p>
                              )}
                            </td>
                            <td className="py-2 text-right tabular-nums">
                              {formatNumber(student.attempts_count)}
                            </td>
                            <td className="py-2 text-right">
                              <PercentBadge value={student.avg_percent} />
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
              </TabsContent>

              <TabsContent value="tests">
                <div className="max-h-[55vh] overflow-y-auto">
                  {group.tests.length === 0 ? (
                    <p className="py-10 text-center text-sm text-muted-foreground">
                      Guruhda test yo'q
                    </p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-background">
                        <tr className="border-b text-xs uppercase text-muted-foreground">
                          <th className="py-2 text-left font-medium">Test</th>
                          <th className="py-2 text-right font-medium">Urinish</th>
                          <th className="py-2 text-right font-medium">O'rtacha</th>
                          <th className="w-8" />
                        </tr>
                      </thead>
                      <tbody>
                        {group.tests.map((test) => (
                          <tr
                            key={test.id}
                            onClick={() => onOpenTest(test.id)}
                            className="cursor-pointer border-b last:border-0 hover:bg-muted/50"
                          >
                            <td className="py-2">
                              <p className="font-medium">{test.title}</p>
                              <p className="text-xs text-muted-foreground">
                                {test.question_count} savol · {test.variant_count}{' '}
                                variant · {formatDate(test.created_at)}
                              </p>
                            </td>
                            <td className="py-2 text-right tabular-nums">
                              {formatNumber(test.attempts_count)}
                            </td>
                            <td className="py-2 text-right">
                              <PercentBadge value={test.avg_percent} />
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
              </TabsContent>
            </Tabs>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
