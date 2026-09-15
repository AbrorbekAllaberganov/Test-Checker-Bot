import { AlertTriangle } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { errorMessage } from '@/api/client'
import { useBlockTeacher } from '@/api/queries'
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
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/input'
import { displayName } from '@/lib/format'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  teacher: TeacherDetail
}

/**
 * Bloklash / blokdan chiqarish oynasi.
 *
 * Sabab ixtiyoriy emas: u ustozga Telegram orqali yuboriladi va audit
 * jurnaliga yoziladi, shu sababli bloklashda majburiy qilingan.
 */
export function BlockUserDialog({ open, onOpenChange, teacher }: Props) {
  const [reason, setReason] = useState('')
  const mutation = useBlockTeacher()
  const isBlocking = !teacher.is_blocked

  function handleSubmit() {
    if (isBlocking && reason.trim().length < 3) {
      toast.error('Bloklash sababini yozing (kamida 3 belgi)')
      return
    }

    mutation.mutate(
      {
        userId: teacher.id,
        blocked: isBlocking,
        reason: isBlocking ? reason.trim() : undefined,
      },
      {
        onSuccess: () => {
          toast.success(
            isBlocking
              ? 'Ustoz bloklandi va bu haqda xabardor qilindi'
              : 'Ustoz blokdan chiqarildi',
          )
          setReason('')
          onOpenChange(false)
        },
        onError: (error) => toast.error(errorMessage(error, 'Amal bajarilmadi')),
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isBlocking ? 'Ustozni bloklash' : 'Blokdan chiqarish'}
          </DialogTitle>
          <DialogDescription>
            {displayName(teacher.full_name, teacher.username, teacher.telegram_id)}
          </DialogDescription>
        </DialogHeader>

        {isBlocking ? (
          <>
            <div className="flex gap-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-xs">
              <AlertTriangle className="h-4 w-4 shrink-0 text-warning" />
              <p className="text-muted-foreground">
                Bloklangan ustoz botdan ham, admin paneldan ham darhol uziladi.
                Uning guruhlari va natijalari o'chirilmaydi.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="reason">Bloklash sababi</Label>
              <Textarea
                id="reason"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder="Masalan: Xizmat shartlari buzilgani uchun…"
                maxLength={500}
              />
              <p className="text-xs text-muted-foreground">
                Bu matn ustozga Telegram orqali yuboriladi.
              </p>
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            Ustoz botdan qayta foydalana boshlaydi va bu haqda xabar oladi.
          </p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Bekor qilish
          </Button>
          <Button
            variant={isBlocking ? 'destructive' : 'success'}
            onClick={handleSubmit}
            loading={mutation.isPending}
          >
            {isBlocking ? 'Bloklash' : 'Blokdan chiqarish'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
