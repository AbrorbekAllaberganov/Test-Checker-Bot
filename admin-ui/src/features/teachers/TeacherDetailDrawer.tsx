import {
  Ban,
  CalendarClock,
  FolderTree,
  GraduationCap,
  ScanLine,
  ShieldCheck,
  Wallet,
} from 'lucide-react'
import { useState } from 'react'

import { useTeacher } from '@/api/queries'
import { ScanStatusBadge, SubscriptionBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuth } from '@/hooks/useAuth'
import {
  displayName,
  formatDate,
  formatDateTime,
  formatLimit,
  formatNumber,
  formatPercent,
  formatRelative,
} from '@/lib/format'
import { BlockUserDialog } from './BlockUserDialog'
import { ChangePlanDialog } from './ChangePlanDialog'

interface Props {
  teacherId: number | null
  onClose: () => void
}

function StatTile({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof FolderTree
  label: string
  value: string
}) {
  return (
    <div className="rounded-lg border p-3">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </div>
  )
}

/**
 * Ustoz profili — o'ngdan chiqadigan panel.
 * Bloklash va tarif almashtirish shu yerdan modal orqali bajariladi.
 */
export function TeacherDetailDrawer({ teacherId, onClose }: Props) {
  const { hasRole } = useAuth()
  const { data: teacher, isLoading } = useTeacher(teacherId)
  const [blockOpen, setBlockOpen] = useState(false)
  const [planOpen, setPlanOpen] = useState(false)

  return (
    <>
      <Sheet open={teacherId !== null} onOpenChange={(open) => !open && onClose()}>
        <SheetContent>
          {isLoading || !teacher ? (
            <div className="space-y-4">
              <Skeleton className="h-8 w-48" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-64 w-full" />
            </div>
          ) : (
            <>
              <SheetHeader>
                <SheetTitle className="flex flex-wrap items-center gap-2">
                  {displayName(teacher.full_name, teacher.username, teacher.telegram_id)}
                  {teacher.admin_role && (
                    <Badge variant="secondary">{teacher.admin_role}</Badge>
                  )}
                </SheetTitle>
                <SheetDescription>
                  Telegram ID: {teacher.telegram_id}
                  {teacher.username && ` · @${teacher.username}`}
                  {' · '}
                  {formatDate(teacher.created_at)} dan beri
                </SheetDescription>
              </SheetHeader>

              {teacher.is_blocked && (
                <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3">
                  <p className="flex items-center gap-1.5 text-sm font-medium text-destructive">
                    <Ban className="h-4 w-4" />
                    Hisob bloklangan
                  </p>
                  {teacher.blocked_reason && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Sabab: {teacher.blocked_reason}
                    </p>
                  )}
                  <p className="mt-1 text-xs text-muted-foreground">
                    {formatDateTime(teacher.blocked_at)}
                    {teacher.blocked_by && ` · ${teacher.blocked_by}`}
                  </p>
                </div>
              )}

              {/* Amallar */}
              {hasRole('SUPPORT_OPERATOR') && (
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant={teacher.is_blocked ? 'success' : 'destructive'}
                    size="sm"
                    onClick={() => setBlockOpen(true)}
                  >
                    {teacher.is_blocked ? (
                      <>
                        <ShieldCheck className="h-4 w-4" />
                        Blokdan chiqarish
                      </>
                    ) : (
                      <>
                        <Ban className="h-4 w-4" />
                        Bloklash
                      </>
                    )}
                  </Button>

                  {hasRole('SUPERADMIN') && (
                    <Button variant="outline" size="sm" onClick={() => setPlanOpen(true)}>
                      <Wallet className="h-4 w-4" />
                      Tarifni o'zgartirish
                    </Button>
                  )}
                </div>
              )}

              <Separator />

              {/* Statistika */}
              <div className="grid grid-cols-2 gap-3">
                <StatTile
                  icon={FolderTree}
                  label="Guruhlar"
                  value={formatNumber(teacher.stats.groups_count)}
                />
                <StatTile
                  icon={GraduationCap}
                  label="O'quvchilar"
                  value={formatNumber(teacher.stats.students_count)}
                />
                <StatTile
                  icon={ScanLine}
                  label="Jami skanlar"
                  value={formatNumber(teacher.stats.scans_count)}
                />
                <StatTile
                  icon={CalendarClock}
                  label="30 kunda"
                  value={formatNumber(teacher.stats.scans_30d)}
                />
              </div>

              {/* Obuna */}
              {teacher.subscription && (
                <div className="rounded-lg border p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="text-sm font-medium">
                        {teacher.subscription.plan_name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(teacher.subscription.period_start)} —{' '}
                        {formatDate(teacher.subscription.period_end)}
                      </p>
                    </div>
                    <SubscriptionBadge status={teacher.subscription.status} />
                  </div>

                  <div className="mt-3 space-y-1">
                    <Progress
                      value={teacher.subscription.usage_percent}
                      indicatorClassName={
                        teacher.subscription.usage_percent >= 100
                          ? 'bg-destructive'
                          : teacher.subscription.usage_percent >= 80
                            ? 'bg-warning'
                            : undefined
                      }
                    />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>
                        {formatNumber(teacher.subscription.scans_used)} /{' '}
                        {formatLimit(teacher.subscription.scan_limit)} skan
                      </span>
                      {teacher.subscription.bonus_credits > 0 && (
                        <span>
                          +{formatNumber(teacher.subscription.bonus_credits)} bonus
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Guruhlar va faollik */}
              <Tabs defaultValue="groups">
                <TabsList className="w-full">
                  <TabsTrigger value="groups" className="flex-1">
                    Guruhlar ({teacher.groups.length})
                  </TabsTrigger>
                  <TabsTrigger value="activity" className="flex-1">
                    Oxirgi skanlar
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="groups" className="space-y-2">
                  {teacher.groups.length === 0 ? (
                    <p className="py-6 text-center text-sm text-muted-foreground">
                      Guruh ochilmagan
                    </p>
                  ) : (
                    teacher.groups.map((group) => (
                      <div
                        key={group.id}
                        className="flex items-center justify-between rounded-lg border p-3"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">{group.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {formatDate(group.created_at)}
                          </p>
                        </div>
                        <div className="shrink-0 text-right text-xs text-muted-foreground">
                          <p>{formatNumber(group.students_count)} o'quvchi</p>
                          <p>{formatNumber(group.tests_count)} test</p>
                        </div>
                      </div>
                    ))
                  )}
                </TabsContent>

                <TabsContent value="activity" className="space-y-2">
                  {teacher.recent_activity.length === 0 ? (
                    <p className="py-6 text-center text-sm text-muted-foreground">
                      Hali skan yuborilmagan
                    </p>
                  ) : (
                    teacher.recent_activity.map((item) => (
                      <div
                        key={item.attempt_id}
                        className="flex items-center justify-between gap-3 rounded-lg border p-3"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">
                            {item.student_name ?? "Noma'lum o'quvchi"}
                          </p>
                          <p className="truncate text-xs text-muted-foreground">
                            {item.test_title ?? "Noma'lum test"} ·{' '}
                            {formatRelative(item.created_at)}
                          </p>
                        </div>
                        <div className="shrink-0 text-right">
                          <ScanStatusBadge
                            status={item.status}
                            needsReview={item.needs_review}
                          />
                          {item.score !== null && (
                            <p className="mt-1 text-xs text-muted-foreground">
                              {item.score}/{item.total} ·{' '}
                              {formatPercent(item.percent)}
                            </p>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </TabsContent>
              </Tabs>
            </>
          )}
        </SheetContent>
      </Sheet>

      {teacher && (
        <>
          <BlockUserDialog
            open={blockOpen}
            onOpenChange={setBlockOpen}
            teacher={teacher}
          />
          <ChangePlanDialog
            open={planOpen}
            onOpenChange={setPlanOpen}
            teacher={teacher}
          />
        </>
      )}
    </>
  )
}
