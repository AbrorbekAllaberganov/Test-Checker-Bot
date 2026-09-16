import { ChevronLeft } from 'lucide-react'

import { Button } from '@/components/ui/button'

/**
 * Drill-down zanjiridagi "orqaga" tugmasi.
 *
 * Guruh → o'quvchi → test bo'ylab kirib borilganda har bosqichda bitta
 * modal ochiq turadi (ichma-ich emas) — orqaga qaytish shu tugma orqali.
 * `onBack` berilmasa (zanjir boshi) hech narsa chizilmaydi.
 */
export function DrillBackButton({ onBack }: { onBack?: () => void }) {
  if (!onBack) return null
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={onBack}
      className="-ml-2 h-7 w-fit px-2 text-xs text-muted-foreground"
    >
      <ChevronLeft className="h-3.5 w-3.5" />
      Orqaga
    </Button>
  )
}
