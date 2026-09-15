import { Gift, Wallet } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { errorMessage } from '@/api/client'
import { useAssignPlan, useGrantCredits, usePlans } from '@/api/queries'
import type { TeacherDetail } from '@/api/types'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input, Textarea } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { displayName, formatLimit, formatMoney } from '@/lib/format'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  teacher: TeacherDetail
}

const STATUS_OPTIONS = [
  { value: 'active', label: 'Faol' },
  { value: 'trial', label: 'Sinov muddati' },
]

/** Muddatsiz obuna uchun maxsus qiymat. */
const UNLIMITED = '__unlimited__'

const DURATION_OPTIONS = [
  { value: '30', label: '1 oy' },
  { value: '90', label: '3 oy' },
  { value: '180', label: '6 oy' },
  { value: '365', label: '1 yil' },
  { value: UNLIMITED, label: 'Muddatsiz' },
]

/**
 * Tarif almashtirish va bonus kredit berish.
 *
 * Ikki amal bitta oynada, lekin alohida tab'da — chunki ular boshqa-boshqa
 * endpoint va boshqa-boshqa audit yozuviga tushadi.
 */
export function ChangePlanDialog({ open, onOpenChange, teacher }: Props) {
  const { data: plans, isLoading: plansLoading } = usePlans()
  const assignPlan = useAssignPlan()
  const grantCredits = useGrantCredits()

  const [planId, setPlanId] = useState<string>('')
  const [status, setStatus] = useState('active')
  const [duration, setDuration] = useState('30')
  const [resetUsage, setResetUsage] = useState(false)
  const [note, setNote] = useState('')
  const [credits, setCredits] = useState('100')

  // Oyna ochilganda joriy tarifni tanlab qo'yamiz.
  useEffect(() => {
    if (open && teacher.subscription) {
      setPlanId(String(teacher.subscription.plan_id))
    }
  }, [open, teacher.subscription])

  const selectedPlan = plans?.find((plan) => String(plan.id) === planId)

  function handleAssign() {
    if (!planId) {
      toast.error('Tarifni tanlang')
      return
    }
    assignPlan.mutate(
      {
        userId: teacher.id,
        planId: Number(planId),
        status,
        durationDays: duration === UNLIMITED ? null : Number(duration),
        resetUsage,
        note: note.trim() || undefined,
      },
      {
        onSuccess: (sub) => {
          toast.success(`Tarif o'zgartirildi: ${sub.plan_name}`)
          setNote('')
          onOpenChange(false)
        },
        onError: (error) => toast.error(errorMessage(error, 'Tarif biriktirilmadi')),
      },
    )
  }

  function handleCredits() {
    const amount = Number(credits)
    if (!Number.isInteger(amount) || amount === 0) {
      toast.error("Kredit noldan farqli butun son bo'lishi kerak")
      return
    }
    grantCredits.mutate(
      { userId: teacher.id, credits: amount, note: note.trim() || undefined },
      {
        onSuccess: (sub) => {
          toast.success(
            `Bonus yangilandi: ${sub.bonus_credits} ta qo'shimcha skan`,
          )
          setNote('')
          onOpenChange(false)
        },
        onError: (error) => toast.error(errorMessage(error, 'Kredit berilmadi')),
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Obunani boshqarish</DialogTitle>
          <DialogDescription>
            {displayName(teacher.full_name, teacher.username, teacher.telegram_id)}
            {teacher.subscription && ` · Joriy: ${teacher.subscription.plan_name}`}
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="plan">
          <TabsList className="w-full">
            <TabsTrigger value="plan" className="flex-1">
              <Wallet className="h-3.5 w-3.5" />
              Tarif
            </TabsTrigger>
            <TabsTrigger value="credits" className="flex-1">
              <Gift className="h-3.5 w-3.5" />
              Bonus kredit
            </TabsTrigger>
          </TabsList>

          {/* ── Tarif almashtirish ── */}
          <TabsContent value="plan" className="space-y-4">
            <div className="space-y-1.5">
              <Label>Tarif</Label>
              <Select value={planId} onValueChange={setPlanId} disabled={plansLoading}>
                <SelectTrigger>
                  <SelectValue placeholder="Tarifni tanlang" />
                </SelectTrigger>
                <SelectContent>
                  {plans?.map((plan) => (
                    <SelectItem key={plan.id} value={String(plan.id)}>
                      {plan.name} — {formatMoney(plan.price_uzs)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {selectedPlan && (
                <p className="text-xs text-muted-foreground">
                  {formatLimit(selectedPlan.monthly_scan_limit)} skan/oy ·{' '}
                  {formatLimit(selectedPlan.max_groups)} guruh ·{' '}
                  {formatLimit(selectedPlan.max_students_per_group)} o'quvchi/guruh
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Holat</Label>
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STATUS_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label>Muddat</Label>
                <Select value={duration} onValueChange={setDuration}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DURATION_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <p className="text-sm font-medium">Sarfni nolga tushirish</p>
                <p className="text-xs text-muted-foreground">
                  Joriy davrdagi ishlatilgan skanlar hisobi qayta boshlanadi
                </p>
              </div>
              <Switch checked={resetUsage} onCheckedChange={setResetUsage} />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="plan-note">Izoh (audit uchun)</Label>
              <Textarea
                id="plan-note"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Masalan: to'lov qabul qilindi, chek №123"
                maxLength={500}
                className="min-h-[60px]"
              />
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Bekor qilish
              </Button>
              <Button onClick={handleAssign} loading={assignPlan.isPending}>
                Tarifni biriktirish
              </Button>
            </DialogFooter>
          </TabsContent>

          {/* ── Bonus kredit ── */}
          <TabsContent value="credits" className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="credits">Qo'shimcha skan krediti</Label>
              <Input
                id="credits"
                type="number"
                value={credits}
                onChange={(event) => setCredits(event.target.value)}
                placeholder="100"
              />
              <p className="text-xs text-muted-foreground">
                Joriy davr limitiga qo'shiladi. Qaytarib olish uchun manfiy son
                kiriting (masalan −50).
                {teacher.subscription &&
                  ` Hozirgi bonus: ${teacher.subscription.bonus_credits}`}
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="credit-note">Izoh (audit uchun)</Label>
              <Textarea
                id="credit-note"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Masalan: texnik nosozlik uchun kompensatsiya"
                maxLength={500}
                className="min-h-[60px]"
              />
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Bekor qilish
              </Button>
              <Button onClick={handleCredits} loading={grantCredits.isPending}>
                Kredit berish
              </Button>
            </DialogFooter>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
