import { zodResolver } from '@hookform/resolvers/zod'
import { AlertTriangle } from 'lucide-react'
import { useEffect } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { errorMessage } from '@/api/client'
import { useSavePlan } from '@/api/queries'
import type { PlanOut } from '@/api/types'
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
import { Switch } from '@/components/ui/switch'

interface Props {
  plan: PlanOut | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

/**
 * Limit maydonlari: bo'sh qoldirilsa "cheksiz" (backend'da NULL).
 * Shu sababli ular string sifatida olinadi va yuborishdan oldin
 * `null | number` ga aylantiriladi — `0` va "cheksiz" ni chalkashtirmaslik
 * uchun (0 = umuman ruxsat yo'q, bu boshqa ma'no).
 */
const limitField = z
  .string()
  .refine((value) => value === '' || /^\d+$/.test(value), {
    message: "Manfiy bo'lmagan butun son yoki bo'sh (cheksiz)",
  })

const schema = z.object({
  code: z
    .string()
    .min(2, 'Kamida 2 belgi')
    .regex(/^[A-Z0-9_]+$/, 'Faqat A-Z, 0-9 va _'),
  name: z.string().min(1, 'Nomi majburiy').max(64),
  description: z.string().max(500).optional(),
  price_uzs: z.string().regex(/^\d+$/, "Manfiy bo'lmagan son"),
  monthly_scan_limit: limitField,
  max_groups: limitField,
  max_students_per_group: limitField,
  is_active: z.boolean(),
  sort_order: z.string().regex(/^\d+$/, "Manfiy bo'lmagan son"),
})

type FormValues = z.infer<typeof schema>

function toLimit(value: string): number | null {
  return value === '' ? null : Number(value)
}

function fromLimit(value: number | null | undefined): string {
  return value === null || value === undefined ? '' : String(value)
}

export function PlanEditorDialog({ plan, open, onOpenChange }: Props) {
  const savePlan = useSavePlan()
  const isEditing = plan !== null

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      code: '',
      name: '',
      description: '',
      price_uzs: '0',
      monthly_scan_limit: '',
      max_groups: '',
      max_students_per_group: '',
      is_active: true,
      sort_order: '0',
    },
  })

  // Oyna ochilganda formani joriy tarif bilan to'ldiramiz.
  useEffect(() => {
    if (!open) return
    form.reset(
      plan
        ? {
            code: plan.code,
            name: plan.name,
            description: plan.description ?? '',
            price_uzs: String(plan.price_uzs),
            monthly_scan_limit: fromLimit(plan.monthly_scan_limit),
            max_groups: fromLimit(plan.max_groups),
            max_students_per_group: fromLimit(plan.max_students_per_group),
            is_active: plan.is_active,
            sort_order: String(plan.sort_order),
          }
        : {
            code: '',
            name: '',
            description: '',
            price_uzs: '0',
            monthly_scan_limit: '',
            max_groups: '',
            max_students_per_group: '',
            is_active: true,
            sort_order: '0',
          },
    )
  }, [open, plan, form])

  function onSubmit(values: FormValues) {
    savePlan.mutate(
      {
        id: plan?.id,
        payload: {
          code: values.code,
          name: values.name,
          description: values.description || null,
          price_uzs: Number(values.price_uzs),
          monthly_scan_limit: toLimit(values.monthly_scan_limit),
          max_groups: toLimit(values.max_groups),
          max_students_per_group: toLimit(values.max_students_per_group),
          is_active: values.is_active,
          sort_order: Number(values.sort_order),
        },
      },
      {
        onSuccess: (saved) => {
          toast.success(
            isEditing ? `"${saved.name}" yangilandi` : `"${saved.name}" yaratildi`,
          )
          onOpenChange(false)
        },
        onError: (error) => toast.error(errorMessage(error, 'Saqlanmadi')),
      },
    )
  }

  const errors = form.formState.errors

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Tarifni tahrirlash' : 'Yangi tarif'}</DialogTitle>
          <DialogDescription>
            Limit maydonini bo'sh qoldirsangiz — cheksiz. 0 esa "umuman ruxsat
            yo'q" degani.
          </DialogDescription>
        </DialogHeader>

        {isEditing && plan.subscribers_count > 0 && (
          <div className="flex gap-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-xs">
            <AlertTriangle className="h-4 w-4 shrink-0 text-warning" />
            <p className="text-muted-foreground">
              Bu tarifda {plan.subscribers_count} ta faol obunachi bor. Limitni
              o'zgartirsangiz, u <strong>darhol</strong> ularning hammasiga
              qo'llanadi.
            </p>
          </div>
        )}

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="code">Kod</Label>
              <Input id="code" placeholder="PREMIUM" {...form.register('code')} />
              {errors.code && (
                <p className="text-xs text-destructive">{errors.code.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="name">Nomi</Label>
              <Input id="name" placeholder="Premium" {...form.register('name')} />
              {errors.name && (
                <p className="text-xs text-destructive">{errors.name.message}</p>
              )}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="description">Tavsif</Label>
            <Textarea
              id="description"
              className="min-h-[60px]"
              placeholder="Kim uchun mo'ljallangani…"
              {...form.register('description')}
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="price_uzs">Narxi (so'm/oy)</Label>
              <Input id="price_uzs" inputMode="numeric" {...form.register('price_uzs')} />
              {errors.price_uzs && (
                <p className="text-xs text-destructive">{errors.price_uzs.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="monthly_scan_limit">Oylik skan limiti</Label>
              <Input
                id="monthly_scan_limit"
                inputMode="numeric"
                placeholder="Cheksiz"
                {...form.register('monthly_scan_limit')}
              />
              {errors.monthly_scan_limit && (
                <p className="text-xs text-destructive">
                  {errors.monthly_scan_limit.message}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="max_groups">Maksimal guruh</Label>
              <Input
                id="max_groups"
                inputMode="numeric"
                placeholder="Cheksiz"
                {...form.register('max_groups')}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="max_students_per_group">Guruhda o'quvchi</Label>
              <Input
                id="max_students_per_group"
                inputMode="numeric"
                placeholder="Cheksiz"
                {...form.register('max_students_per_group')}
              />
            </div>
          </div>

          <div className="flex items-center justify-between gap-4">
            <div className="w-32 space-y-1.5">
              <Label htmlFor="sort_order">Tartib</Label>
              <Input
                id="sort_order"
                inputMode="numeric"
                {...form.register('sort_order')}
              />
            </div>

            <div className="flex items-center gap-2 rounded-md border px-3 py-2">
              <Controller
                control={form.control}
                name="is_active"
                render={({ field }) => (
                  <Switch
                    id="is_active"
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                )}
              />
              <Label htmlFor="is_active" className="text-xs">
                Faol (yangi obunalar uchun ochiq)
              </Label>
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Bekor qilish
            </Button>
            <Button type="submit" loading={savePlan.isPending}>
              Saqlash
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
